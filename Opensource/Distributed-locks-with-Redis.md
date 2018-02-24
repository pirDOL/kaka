## [Distributed locks with Redis](https://github.com/antirez/redis-doc/blob/master/topics/distlock.md)

### TLDR
1. This page is an attempt to provide a more **canonical** algorithm to implement distributed locks with Redis. We propose an algorithm, called Redlock, which implements a DLM which we believe to be safer than the vanilla single instance approach. 
2. failover-based implementation
    1. algorithm: The simplest way to use Redis to lock a resource is to create a key in an instance. The key is usually created with a limited time to live, using the Redis expires feature, so that eventually it will get released (property 2 in our list). When the client needs to release the resource, it deletes the key.
    2. cons: Because Redis replication is asynchronous, during a failure, multiple clients can hold the lock at the same time.
1. redlock implementation
    1. model
        1. safety: Mutual exclusion. At any given moment, only one client can hold a lock.
        2. liveness-A: Deadlock free. Eventually it is always possible to acquire a lock, even if the client that locked a resource crashes or gets partitioned.
        3. liveness-B: Fault tolerance. As long as the majority of Redis nodes are up, clients are able to acquire and release locks.
    1. single instance
        1. acquire: SET resource_name my_random_value NX PX 30000
        2. safe-release: For example a client may acquire the lock, get blocked in some operation for longer than the lock validity time (the time at which the key will expire), and later remove the lock, that was already acquired by some other client. Using just DEL is not safe as a client may remove the lock of another client. With the above script instead every lock is “signed” with a random string, so the lock will be removed only if it is still the one that was set by the client trying to remove it.
        3. random string: Theoretically, it must be unique across all clients and all lock requests. A simpler solution is to use a combination of unix time with microseconds resolution, concatenating it with a client ID, it is not as safe, but probably up to the task in most environments.
        4. expire: The time we use as the key time to live, is called the “lock validity time”. It is both the auto release time, and the time the client has in order to perform the operation required before another client may be able to acquire the lock again, without technically violating the mutual exclusion guarantee, which is only limited to a given window of time from the moment the lock is acquired.
    2. distributed:
        1. acquire:
            1. It gets the current time in milliseconds.
            2. It tries to acquire the lock in all the N instances (sequentially or **ideally multiplexing**, the faster a client tries to acquire the lock in the majority of Redis instances, the smaller the window for a split brain condition ) using the same key name and random value with a small timeout (If the auto-release time is 10 seconds, the timeout could be in the ~ 5-50 milliseconds). The timeout prevents the client from remaining blocked for a long time trying to talk with a Redis node which is down.
            3. The client computes how much time elapsed in order to acquire the lock, by subtracting from the current time the timestamp obtained in step 1. If and only if the client was able to acquire the lock in the majority of the instances (at least 3), and the total time elapsed to acquire the lock is less than lock validity time, the lock is considered to be acquired.
            4. If the lock was acquired, its validity time is considered to be the initial validity time minus the time elapsed (computed in step 3) and some time (just a few milliseconds in order to compensate for clock drift between processes).
            5. If the client failed to acquire the lock for some reason (either it was not able to lock N/2+1 instances or the validity time is negative):
                1. it must unlock all the instances (even the instances it believed it was not able to lock)（译者注：可能是redis set成功了，但是向client发送ack超时，此时client需要做一次解锁）
                2. it should try again after a random delay in order to try to desynchronize multiple clients trying to acquire the lock for the same resource at the same time (this may result in a split brain condition where nobody wins)
        2. performance: multiplexing talk with N redis ervers to reduce latency
        3. crash-recovery: 
            1. no persistency will violate the safety property of exclusivity of lock.
            2. AOF with fsync=1s is same as no persistency under the circumstances that key is not fsynced to disk before restart.
            3. AOF with fsync=always will ruin performance.
            4. Delayed restart(when an instance restarts after a crash, it no longer participates to any currently active lock) can achieve safety even without any kind of Redis persistence available, however note that this may translate into an availability penalty.

### 翻译
在不同进程需要互斥地访问共享资源时，分布式锁是一种非常有用的原语。

有很多库和文章描述如何用Redis实现一个分布式锁管理器，但是这些库实现的方式差别很大，而且很多简单的实现其实只需采用稍微增加一点复杂的设计就可以获得更好的可靠性。

这篇文章的目的就是尝试提出一种官方权威的用Redis实现分布式锁管理器的算法，我们把这个算法称为RedLock，我们相信这个算法会比一般的普通方法（原文：be safer than the vanilla single instance approach）更加安全可靠。我们也希望社区能一起分析这个算法，提供一些反馈，然后我们以此为基础设计出更加复杂可靠的算法，或者更好的新算法。

#### 实现
在描述具体的算法之前，下面是已经实现了的项目可以作为参考： 

* [Redlock-rb（ruby实现）](https://github.com/antirez/redlock-rb)，这个库有一个[fork](https://github.com/leandromoreira/redlock-rb)，添加了gem（ruby的包管理）便于分发，类似的fork可能还有很多
* [Redlock-py（python实现）](https://github.com/SPSCommerce/redlock-py)
* [Aioredlock（python asyncio实现）](https://github.com/joanvila/aioredlock)
* [Redlock-php（php实现）](https://github.com/ronnylt/redlock-php)
* [PHPRedisMutex（未来的php实现）](https://github.com/malkusch/lock#phpredismutex)
* [cheprasov/php-redis-lock（lib形式的php实现）](https://github.com/cheprasov/php-redis-lock)
* [Redsync.（go实现）](https://github.com/hjr265/redsync.go)
* [Redisson（java实现）](https://github.com/mrniko/redisson)
* [Redis::DistLock（perl实现）](https://github.com/sbertrang/redis-distlock)
* [Redlock-cpp（c++实现）](https://github.com/jacket-code/redlock-cpp)
* [Redlock-cs（c#/.net实现）](https://github.com/kidfashion/redlock-cs)
* [RedLock.net（c#/.net实现）](https://github.com/samcook/RedLock.net)，支持异步和锁有效期延长
* [ScarletLock（c#/.net实现）](https://github.com/psibernetic/scarletlock)，数据库可配置（译者注：除了redis以外还可以使用其他数据库）
* [node-redlock（nodejs实现）](https://github.com/mike-marcacci/node-redlock)，支持锁有效期延长功能

#### 安全和可靠性保证
在描述我们的设计之前，我们想先提出三个属性，在我们看来它们是实现使用分布式锁的最低保证：

1. 安全性：互斥，任一时间只有一个客户端能持有同一个锁
2. 锁有效期属性A：不会死锁，就算一个持有锁的客户端宕掉或者发生网络分区，最终还是能够获取这个锁
3. 锁有效期属性B：容错，只要大多数Redis节点正常工作，客户端应该都能获取和释放锁

#### 为什么failover的实现不够好
为了理解我们的改进点，我们先看下当前大多数基于Redis的分布式锁第三方库的现状。

用Redis来实现分布式锁最简单的方式就是在Redis实例里创建一个键值，创建出来的键值一般都是有一个超时时间的（这个是Redis自带的超时特性），所以每个锁最终都会释放（锁有效期属性B）。而当一个客户端想要释放锁时，它只需要删除这个键值即可。

表面来看，这个方法似乎很管用，但是这里存在一个问题：在我们的系统架构里存在一个故障单点。如果Redis的master节点宕机了怎么办呢？有人可能会说：加一个slave节点！在master宕机时用slave就行了！但是其实这个方案明显是不可行的，因为这种方案无法保证安全性，因为Redis的复制是异步的。 

这个方案里有一个明显的竞争条件举例来说：

1. 客户端A在master节点拿到了锁
2. master节点在把A创建的key写入slave之前宕机了
3. slave变成了master节点
4. B也得到了和A还持有的相同的锁（因为slave里还没有A持有锁的信息）

当然，在某些特殊场景下，前面提到的这个方案则完全没有问题，比如在宕机期间，多个客户端允许同时都持有锁，如果你可以容忍这个问题的话，那用这个基于复制的方案就完全没有问题，否则的话我们还是建议你采用这篇文章里接下来要描述的方案。

#### 单Redis实例的正确实现
在讲述如何用其他方案克服单实例方案的限制之前，让我们先看下是否有什么办法可以解决这个简单场景的问题，因为如果可以忍受锁的不同超时时间窗口内的竞争条件（原文：a race condition from time to time is acceptable），单实例方实现分布式锁是我们后面要讲的分布式算法的基础。

用下面的命令获取锁：
```redis
SET resource_name my_random_value NX PX 30000
```

这个命令的作用是在只有这个key不存
在的时候才会设置这个key的值（NX选项的作用），超时时间设为30000毫秒（PX选项的作用） 这个key的值设为"my_random_value"。这个值必须在所有获取锁请求的客户端里保持唯一。

这个随机值是用来保证能安全地释放锁，我们可以用下面这个脚本来告诉Redis：删除这个key当且仅当这个key存在而且值是我期望的那个值。
```redis
if redis.call("get",KEYS[1]) == ARGV[1] then
    return redis.call("del",KEYS[1])
else
    return 0
end
```

删除key时比较value很重要，因为这可以避免误删其他客户端得到的锁，举个例子，一个客户端拿到了锁，被某个操作阻塞了很长时间，过了锁的超时时间后自动释放了这个锁，然后这个客户端之后又尝试删除这个其实已经被其他客户端拿到的锁。所以单纯的用DEL指令有可能造成一个客户端删除了其他客户端的锁，用上面这个脚本可以保证每个客户单都用一个随机字符串“签名”了，这样每个锁就只能被获得锁的客户端删除了。

这个随机字符串应该用什么生成呢？我假设这是从/dev/urandom生成的20字节大小的字符串，但是其实你可以有效率更高的方案来保证这个字符串足够唯一。比如你可以用/dev/urandom作为RC4算法的种子，并以此生成一个伪随机流。还有更简单的方案，比如用毫秒的unix时间戳加上客户端id，这个也许不够安全，但是也许在大多数环境下已经够用了。

key值的超时时间也叫做“锁有效时间”，是锁的自动释放时间，也是一个客户端在其他客户端能抢占锁之前可以安全执行操作的时间。这种方法并没有从技术上实现锁的绝对互斥性，只能确保在锁有效时间窗口内，锁是绝对互斥的。

所以现在我们有很好的获取和释放锁的方式，在一个非分布式的、单点的、保证永不宕机的环境下这个方式没有任何问题，接下来我们看看无法保证这些条件的分布式环境下我们该怎么做。

#### Redlock算法
在分布式版本的算法里我们假设我们有N个Redis master节点，这些节点都是完全独立的，我们不用任何复制或者其他隐含的分布式协调算法。我们已经描述了如何在单节点环境下安全地获取和释放锁。因此我们理所当然地应当用这个方法在每个单节点里来获取和释放锁。在我们的例子里面我们把N设成5，这个数字是一个相对比较合理的数值，因此我们需要在不同的计算机或者虚拟机上运行5个master节点来保证他们大多数情况下都不会同时宕机。一个客户端需要做如下操作来获取锁：

1. 获取当前时间（单位是毫秒）
2. 轮流用相同的key和随机值在N个节点上请求锁，在这一步里，客户端和每个master交互的超时要比锁总的释放时间相比小的多。比如锁自动释放时间是10秒，那么和master交互的超时时间可能是5-50毫秒，这个可以防止一个客户端在某个宕掉的master节点上阻塞过长时间，如果一个master节点不可用了，我们应该尽快尝试下一个master节点
3. 客户端计算第二步中获取锁所花的时间（当前时间减去第1步的时间），只有当客户端在大多数master节点上成功获取了锁（在这里是3个），而且总共消耗的时间不超过锁释放时间，这个锁就认为是获取成功了
4. 如果锁获取成功了，锁真正的释放时间就是锁释放时间减去之前获取锁所消耗的时间
5. 如果锁获取失败了，不管是因为获取成功的锁不超过一半，还是因为总消耗时间超过了锁释放时间，客户端要到所有master节点上释放锁，即便是那些没有成功获取锁的master节点。

#### 这个算法是否是异步的？
这个算法是基于一个假设：虽然不存在可以跨进程的同步时钟，但是不同进程时间都是以差不多相同的速度前进，这个假设不一定完全准确，但是和自动释放锁的时间长度相比不同进程时间前进速度差异基本是可以忽略不计的。这个假设就好比真实世界里的计算机：每个计算机都有本地时钟，但是我们可以说大部分情况下不同计算机之间的时间差是很小的。 

现在我们需要更细化我们的锁互斥规则：只有当客户端能在T时间内完成所做的工作才能保证锁是有效的，T要从第3步的锁真正的失效时间中减去一个用来补偿不同进程的时钟差（一般只有几毫秒而已）。

如果想了解更多基于有限时钟差异的类似系统，可以参考这篇有趣的文章：[Leases: an efficient fault-tolerant mechanism for distributed file cache consistency](http://dl.acm.org/citation.cfm?id=74870)

#### 失败重试
当一个客户端获取锁失败时，这个客户端应该在一个随机延时后进行重试，之所以采用随机延时是为了避免在网络分割时不同客户端同时重试导致谁都无法拿到锁的情况出现。一个客户端越快在大多数Redis节点获取锁，出现多个客户端同时竞争锁和重试的时间窗口越小，可能性就越低，所以最完美的情况下，客户端应该用多路传输的方式同时向所有Redis节点发送SET命令。

这里非常有必要强调一下客户端如果没有在多数节点获取到锁，一定要尽快在获取锁成功的节点上释放锁，这样就没必要等到key超时后才能重新获取这个锁（但是如果网络分割的情况发生而且客户端无法连接到Redis节点时，只能等待到key超时，这段时间内锁管理器是不可用的）。

#### 释放锁
释放锁比较简单：只需要在所有节点都释放锁，不管之前有没有在该节点成功获取锁。

#### 安全性论证
这个算法到底是不是安全的呢？我们可以观察不同场景下的情况来理解这个算法为什么是安全的。

开始之前，让我们假设客户端可以在大多数节点都获取到锁，这样所有的节点都会包含一个有相同存活时间的key。但是需要注意的是，这个key是在不同时间点设置的，所以这些key也会在不同的时间超时，我们假设的最坏情况是第一个key是在T1时间设置的（客户端连接到第一个服务器时的时间），最后一个key是在T2时间设置的（客户端收到最后一个服务器返回结果的时间），从T2时间开始，我们可以确认最早超时的key的至少会存在的时间长度为`MIN_VALIDITY=TTL-(T2-T1)-CLOCK_DRIFT`（译者注：T1+TTL-T2-CLOCK_DRIFT），其他的key都会在时间点T1+TTL-CLOCK_DRIFT以后才失效，所以我们可以确定这些key在这个时间点之前至少都是同时存在的。

在大多数节点的key都SET了的时间段内，其他客户端无法抢占这个锁，因为在N/2+1个Redis节点都已经存在key的情况下不可再成功执行N/2+1个SET NX操作，所以如果一个锁获取成功了，就不可能同时重新获取这个锁成功（不然就违反了锁互斥原则）。

然而我们也要确保多个客户端同时尝试获取锁时不会都同时成功。如果一个客户端获取大多数节点锁的耗时接近甚至超过锁的最大有效时间时（就是我们为SET操作设置的TTL值），那么客户端会认为这个锁是无效的同时会删除所有节点上的key，所以我们仅仅需要考虑获取大多数节点锁的耗时小于锁有效时间的情况。在这种情况下，根据前面的证明，在`MIN_VALIDITY`时间内，没有客户端能重新获取锁。所以多个客户端都能同时成功获取锁的结果，只会发生在多数节点获取锁的时间都超过TTL时间的情况下，实际上这种情况下这些锁都会失效。

我们非常期待和欢迎有人能提供这个算法安全性的正式证明，或者和现有的类似算法进行比较，或者发现任何bug。

#### 可用性论证
这个系统的可用性（原文：liveness）主要基于以下三个主要特征：

1. 锁能自动释放（Redis的key超时后会自动释放），一定时间后某个锁都能被再次获取
2. 客户端在获取锁失败时或者任务执行完成之后主动释放锁，这样我们就不用等到超时时间会再去获取这个锁。
3. 当一个客户端需要重试获取锁时，这个客户端会等待一段时间，等待的时间相对来说会比获取大多数锁的时间要长一些，这样可以降低不同客户端竞争锁资源时发生裂脑的概率。

然而，我们在网络分区时要损失TTL的可用性时间，所以如果网络分区持续发生，这个不可用会一直持续。这种情况在每次一个客户端获取到了锁并在释放锁之前被网络分区了时都会出现。

基本来说，如果持续的网络分区发生的话，系统也会在持续不可用。

#### 性能、故障恢复和fsync
很多使用Redis做锁服务器的用户在获取锁和释放锁时不止要求低延时，同时要求高吞吐量，也即单位时间内可以获取和释放的锁数量。为了达到这个要求，一定会使用多路传输来和N个服务器进行通信以降低延时（或者也可以用假多路传输，也就是把socket设置成非阻塞模式，发送所有命令，然后再去读取返回的命令，假设说客户端和不同Redis服务节点的网络往返延时相差不大的话）。

然后如果我们想让系统可以自动故障恢复的话，我们还需要考虑一下数据持久化的问题。

为了更好的描述问题，我们先假设我们Redis都是配置成非持久化的，某个客户端拿到了总共5个节点中的3个锁，3个节点中的一个随后重启了，这样一来我们又有3个节点可以获取锁了（重启的那个加上另外两个），这样一来其他客户端又可以获得这个锁了，这样就违反了我们之前说的锁互斥原则了。

如果我们启用AOF持久化功能，情况会好很多。举例来说，我们可以发送SHUTDOWN命令来升级一个Redis服务器然后重启，因为Redis超时是语义层面实现的，所以在服务器关掉期间时超时时间还是算在内的，我们所有要求还是满足了的。然后这个是基于我们做的是一次正常的shutdown，但是如果是断电这种意外停机呢？如果Redis是默认地配置成每秒在磁盘上执行一次fsync同步文件到磁盘操作，那就可能在一次重启后我们锁的key就丢失了。理论上如果我们想要在所有服务重启的情况下都确保锁的安全性，我们需要在持久化设置里开启`fsync=always`，但是这个反过来又会造成性能远不如其他同级别的传统的分布式锁系统。

问题其实并不像我们第一眼看起来那么糟糕，基本上只要一个服务节点在宕机重启后不去参与现在所有仍在使用的锁的获取请求，算法的安全性就可以维持。这样正在使用的锁集合在这个服务节点重启时，因为这样就可以保证正在使用的锁都被所有没重启的节点持有，而不是重新加入系统的Redis节点。

为了满足这个条件，我们只要让一个宕机重启后的实例，至少保持最大TTL时间不可用状态，超过这个时间之后，所有在这期间获取的锁都会自动释放掉。

使用延时重启的策略基本上可以在不使用任何Redis持久化特性情况下保证安全性，值得注意的是这种做法是以牺牲系统可用性而保持了安全性。举个例子，如果系统里大多数节点都宕机了，那在TTL时间内整个系统都处于全局不可用状态（全局不可用的意思就是在获取不到任何锁）。

#### 扩展锁来使得算法更可靠
如果客户端做的工作都是由一些小的步骤组成，那么就有可能使用更小的默认锁有效时间，而且扩展这个算法来实现一个锁有效时间延长机制。如果客户端在执行计算期间发现锁快要超时了，客户端可以给所有服务实例发送一个Lua脚本让服务端延长锁的时间，只要这个锁的key还存在而且值还等于客户端获取锁时的随机值。

如果在锁的有效时间内大多数redis实例执行Lua脚本成功，客户端就可以认为锁的有效期延长成功（这个算法的具体步骤和获取锁是基本上类似的）。

然而这个并不会对从本质上改变这个算法，所以最大的重新获取锁次数应该被设置成合理的大小，否则会破坏可用性。

#### 想提供帮助？
如果你很了解分布式系统的话，我们非常欢迎你提供一些意见和分析。当然如果能引用其他语言的实现话就更棒了。谢谢！

#### redlock的分析
1. Martin Kleppmann在[这篇文章](http://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html)中分析了redlock，我（antirez）不同意这些分析，[这篇文章](http://antirez.com/news/101)是我对他的分析的回复。

### 参考
[用Redis构建分布式锁](http://ifeve.com/redis-lock/)