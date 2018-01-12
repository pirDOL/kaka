## [Thread Pools in NGINX Boost Performance 9x!](https://www.nginx.com/blog/thread-pools-boost-performance-9x/)

### TLDR
1. nginx的“异步事件驱动”究竟是啥：
  1. handles multiple connections and requests in one worker process
  2. non-blocking socket + epoll/kqueue
  4. The events can be timeouts, notifications about sockets ready to read or to write, or notifications about an error that occurred. 
  5. Asynchronous, event-driven approach's biggest problem is blocking. NGINX receives a bunch of events and then processes them one by one, ... Thus all the processing is done in a simple loop over a queue in one thread.
2. salesperson example
  1. Everyone in the queue has to wait for the first person’s order
  2. Passing an order to the delivery service unblocks the queue
  3. currently the salesman cannot know if the requested item is in the store and must either always pass all orders to the delivery service or always handle them himself（译者注：这里是说线程池不是银弹，只有需要从磁盘读文件操作才应该让线程池处理，但是因为有pagecache存在，所以被缓存的文件，让线程池也只消耗一点nginx内部架构的开销，把任务“卸载”给线程池，线程池立刻从pagecache读到文件，然后把任务重新添加回事件循环）
3. thread pool
  1. the thread pool is performing the functions of the delivery service. It consists of a task queue and a number of threads that handle the queue. When a worker process needs to do a potentially long operation, instead of processing the operation by itself it puts a task in the pool’s queue, from which it can be taken and processed by any free thread.
  2. At the moment, offloading to thread pools is implemented only for three essential operations: read() on most operating systems, sendfile() on Linux, and aio_write() on Linux which is used when writing some temporary files such as those for the cache. 
  3. best practice:
    1. If you have enough RAM to store the data set, then an operating system will be clever enough to cache frequently used files in page cache. The page cache works pretty well and allows NGINX to demonstrate great performance in almost all common use cases.
    2. It is most useful where the volume of frequently requested content doesn’t fit into the operating system’s VM cache. This might be the case with, for instance, a heavily loaded NGINX-based streaming media server. This is the situation we’ve simulated in our benchmark.
  4. example: Now let’s imagine you have a server with three hard drives and you want this server to work as a “caching proxy” that caches all responses from your backends. The expected amount of cached data far exceeds the available RAM. It’s actually a caching node for your personal CDN. 
4. benchmark
  1. load:
    1. random load: requests files from our server in a random order. Each request is likely to result in a cache miss and a blocking read from disk.
    2. constant load: request the same file. Since this file will be frequently accessed, it will remain in memory all the time. In normal circumstances, NGINX would serve these requests very quickly, but performance will fall if the worker processes are blocked by other requests. 
  4. result: The average time to serve a 4MB file has been reduced from 7.42 seconds to 226.32 milliseconds (33 times less), and the number of requests per second has increased by 31 times (250 vs 8)!

### 翻译
大家都知道NGINX使用[异步事件驱动](http://nginx.com/blog/inside-nginx-how-we-designed-for-performance-scale/)方式来处理请求，这意味着我们不会为每个请求另外创建专门的进程或线程（比如那些传统架构的服务器通常会这样做），而是选择一个工作进程来处理多个连接和请求。为了实现这一点，NGINX使用非阻塞socket以及选择了更有效率的系统调用比如[epoll](http://man7.org/linux/man-pages/man7/epoll.7.html)和[kqueue](https://www.freebsd.org/cgi/man.cgi?query=kqueue)。

因为worker进程（原文是：full-weight，对比light-weight——线程）数量很少（通常是每个cpu核心只占一个）而且是恒定的，这样消耗了更少的内存并且cpu时间片没有被浪费在任务切换上。这个方法的优点可以通过NGINX这个例子来反映出来。它可以非常好的处理上百万的并发请求并且能够很容易扩容（原文：and scales very well）。

![](./Thread-Pools-in-NGINX-Boost-Performance-9x/Traditional-Server-and-NGINX-Worker.png.png)

每个进程消耗额外的内存，每次进程之间的切换会消耗CPU周期以及产生cpu缓存垃圾（译者注：这里是指同一个worker上的多个请求在任务切换时不需要切换时间片。传统架构中，多个请求在任务切换时发生了进程调度，所以导致cpu内部的缓存失效）

但是异步事件驱动模型同样存在问题，我更喜欢把它称作异步事件模型的敌人它就是“阻塞”。不幸的是许多第三方模块都使用了阻塞的调用，而且用户（有时候甚至模块的开发者）没有意识到这么做的弊端。阻塞式操作会毁掉NGINX的性能，所以无论如何一定要被阻止。

即使在现在的官方版本的NGINX源代码中也不可能在任何情况下避免阻塞，为了解决这个问题新的“线程池”特性被引入到[NGINX 1.7.11](http://hg.nginx.org/nginx/rev/466bd63b63d1)以及[NGINX PLUS Release 7](http://nginx.com/blog/nginx-plus-r7-released/#thread-pools)当中来。它是什么以及它如何使用这个我们稍后讨论，现在我们来面对我们的敌人了。

编辑注：想对NGINX PLUS R7有个大概了解可以看我们的博客[Announcing NGINX Plus R7](https://www.nginx.com/blog/nginx-plus-r7-released/)。NGINX PLUS R7其他新特性的具体分析，可以看下边列出来的博客：

* [HTTP/2 Now Fully Supported in NGINX Plus](https://www.nginx.com/blog/http2-r7/)
* [Socket Sharding in NGINX](https://www.nginx.com/blog/socket-sharding-nginx-release-1-9-1/)
* [The New NGINX Plus Dashboard in Release 7](https://www.nginx.com/blog/dashboard-r7)
* [TCP Load Balancing in NGINX Plus R7](https://www.nginx.com/blog/tcp-load-balancing-r7)

#### 问题
首先，为了更好的了解NGINX，我们会用几句话解释一下它是如何工作的。

大体来说，NGINX是一个事件处理器，通过controller从内核接收当前连接的事件信息，然后把接下来做的什么命令告诉操作系统。实际上NGINX通过协调操作系统完成了所有复杂的工作，具体的字节读写操作由操作系统周期性的完成。所以对NGINX来说反应的快速及时是很重要的。

![](./Thread-Pools-in-NGINX-Boost-Performance-9x/NGINX-Event-Loop2-e1434744201287.png.png)

工作进程监听以及处理从内核传过来的事件

具体的事件包括：定时器超时、socket读就绪或者写就绪或者发生了错误。NGINX接收到一串事件接着一个一个的处理它们。所有的操作都在一个线程中完成，这个线程简单的遍历就绪事件队列。NGINX从队列中取出一个事件然后进行相应的处理，比如读写socket。大多数情况下，这个操作会很快（也许这个操作只需要很少的cpu时间拷贝内存中一些数据）并且NGINX可以用很短的时间在这个队列当中处理完所有的事件。

![](./Thread-Pools-in-NGINX-Boost-Performance-9x/Events-Queue-Processing-Cycle.png.png)

所有的事件处理操作都通过一个线程的简单循环完成。

但是如果发生了一个需要很长时间并且重量级的操作会怎么样呢？整个事件处理的循环都会被这个操作所阻塞直到这个操作完成。

因此，这里所谓的“阻塞操作”是指任何导致事件处理循环显著停止一段时间的操作。操作会因为各种各样的原因而被阻塞。比如说，NGINX可能忙于冗长的CPU密集型处理，或者可能访问资源时需要等待（例如：硬盘驱动器、互斥锁或一个库函数以同步方式从数据库获取响应等）。关键的问题在于，处理这样的事情，工作线程不能做其他别的事情，也不能处理其他的事件。即使操作系统的资源足够并且能够被队列中其他就绪的事件使用。

想象一下一个商店销售员面前有长长的一队人。第一个人需要一个不在商店而是在仓库里的东西。销售人员跑到仓库去提货。现在，整个队列必须等待几个小时，队中的每个人都不满意。你能想象人们作何反应吗？队列中的每个人的等待时间都增加了几个小时，但他们打算买的东西有可能就在商店里。

![](./Thread-Pools-in-NGINX-Boost-Performance-9x/Faraway-Warehouse1.png.png)

队列里的每个人都必须因为第一个的订单而等待

相同的情况发生在NGINX当中：当它想要读一个没有缓存在内存中的文件而不得不去访问硬盘的时候。硬盘驱动器很慢（特别是机械硬盘），然而此时队列中的其他请求可能不需要访问硬盘驱动器，所以它们也被迫等待。 因此，请求延迟增加，系统资源未得到充分利用。

![](./Thread-Pools-in-NGINX-Boost-Performance-9x/Blocking-Operation-e1434743587684.png.png)

只有一个阻塞会大幅延迟所有的接下来所有的操作

一些操作系统提供用于读取和发送文件的异步接口，NGINX可以使用此接口（请参阅[aio](http://nginx.org/en/docs/http/ngx_http_core_module.html#aio)指令）。一个典型的例子是FreeBSD。不幸的是，Linux可能不如左边这位那么友好。虽然Linux提供了一种用于读取文件的异步接口，但它有一些显著的缺点。其中一个是文件访问和缓冲区的对齐要求，当然NGINX可以把这个问题处理得很好。但第二个问题更糟糕，异步接口需要在文件描述符上设置`O_DIRECT`标志，这意味着对文件的任何访问将绕过内存中的缓存并增加硬盘上的负载。这导致很多场景实际上并没有起到优化效果。

为了专门解决这个问题，NGINX 1.7.11和NGINX Plus Release 7中引入了线程池。

现在我们来看看什么线程池是关于它们以及它们的工作原理。

#### 线程池
让我们回到那个要从遥远的仓库配货的倒霉的销售助理。这次他变得更聪明（也许是被愤怒的客户群殴后变得更聪明了），他雇佣了送货服务。现在当有人需要遥远的仓库里的一些东西的时候，他不会亲自去仓库而是下了一个订单到送货服务，他们会处理订单，而我们的销售助理会继续为其他客户服务。因此只有那些货物不在商店的客户需要等待交货，而其他客户可以立即得到服务。

![](./Thread-Pools-in-NGINX-Boost-Performance-9x/Your-Order-Next1.png.png)

将订单传递给运送服务从而解除阻塞队列

回到NGINX，线程池执行的就是送货服务的功能。它由一个任务队列和多个处理队列的线程组成。当worker进程需要做一个可能消耗时间很长的操作时，它不会自己处理这个操作，而是将任务放在线程池的队列中，让空闲的线程从队列获取任务并进行处理。

![](./Thread-Pools-in-NGINX-Boost-Performance-9x/thread-pools-worker-process-event-cycle.png.png)
工作进程将阻塞操作卸载（原文是offload）到线程池

看来我们还有一个队列。是的，但是在这种情况下，队列受到特定资源的限制。我们从磁盘读取资源速度永远比磁盘生成数据要慢。但是现在至少磁盘操作不会延迟NGINX主循环中其他请求的处理，只有需要访问文件的请求需要等待。

“从磁盘读取文件”是最常见的阻塞操作例子，但实际上NGINX中的线程池适用于任何不适合在主循环中处理的任务。

目前，“卸载”阻塞操作给线程池仅用于三个基本操作：大多数操作系统上的`read()`系统调用，Linux上的`sendfile()`和Linux上写一些临时文件比如缓存时使用到的`aio_write()`。我们将继续测试和评估，如果有明显的好处，我们可能会在未来的版本中将其他操作也提交到线程池。

编辑注：在[NGINX 1.9.13](http://hg.nginx.org/nginx/rev/fc72784b1f52)和[NGINX Plus R9](https://www.nginx.com/blog/nginx-plus-r9-released/#aio-write)中添加了对`aio_write()`系统调用的支持。

#### 性能测试
现在到了理论通往实践的时候了。为了演示使用线程池的效果，我们将执行一个综合的性能测试，这个测试中模拟了阻塞和非阻塞操作这种最糟糕的组合。

性能测试需要一个内存容纳不下的数据集。在一台48 GB内存的机器上，我们生成了256 GB的随机4M分割数据，然后配置了NGINX version 1.9.0来提供服务。

配置非常简单：
```nginx
worker_processes 16;

events {
    accept_mutex off;
}

http {
    include mime.types;
    default_type application/octet-stream;

    access_log off;
    sendfile on;
    sendfile_max_chunk 512k;

    server {
        listen 8000;

        location / {
            root /storage;
        }
    }
}
```

可以看到的是，为了获得更好的性能而做了一些优化：禁用了[logging](http://nginx.org/en/docs/http/ngx_http_log_module.html?&_ga=2.69429586.354182567.1515763628-1865268522.1506349358#access_log)和[accept_mutex](http://nginx.org/en/docs/ngx_core_module.html?&_ga=2.69429586.354182567.1515763628-1865268522.1506349358#accept_mutex)，启用了[sendfile](http://nginx.org/en/docs/http/ngx_http_core_module.html?&_ga=2.69429586.354182567.1515763628-1865268522.1506349358#sendfile)，并且设置了[sendfile_max_chunk](http://nginx.org/en/docs/http/ngx_http_core_module.html?&_ga=2.69429586.354182567.1515763628-1865268522.1506349358#sendfile_max_chunk)，这个指令可以减少阻止sendfile()调用所花费的最大时间，因为NGINX不会一次尝试发送整个文件，而是分割成512 KB的数据块发送。

测试机器为双核Intel Xeon E5645（12核24线程）处理器、10Gbps网络接口。磁盘子系统由安装在RAID10阵列中的四个西数WD1003FBYX硬盘驱动器表示。操作系统是Ubuntu Server 14.04.1 LTS。

![](./Thread-Pools-in-NGINX-Boost-Performance-9x/Load-Generators1.png.png)

用于性能测试的负载生成器和NGINX的配置

客户端用两台相同配置的机器模拟，一台机器通过[wrk](https://github.com/wg/wrk)加Lua脚本生成负载，脚本以200的并发连接向服务器随机请求文件，每个请求都会导致缓存失效造成从读取磁盘而产生的阻塞。我们就叫它“随机负载”。

第二台客户端机器我们运行另一个wrk副本，但是这个脚本我们使用50的并发连接请求同一个文件。因为这个文件被经常访问的，它将一直被缓存在内存中。在正常情况下，NGINX能够很快的处理这些请求，但是如果其他请求阻塞处理请求的性能将会下降。所以我们把它叫做“常量负载”。

通过`ifstat`工具监控服务器的吞吐率和从第二台客户端获取的wrk工具结果来度量请求的处理性能。

现在，第一次测试没有线程池并没有我们带来让人兴奋的结果：
```
% ifstat -bi eth2
eth2
Kbps in  Kbps out
5531.24  1.03e+06
4855.23  812922.7
5994.66  1.07e+06
5476.27  981529.3
6353.62  1.12e+06
5166.17  892770.3
5522.81  978540.8
6208.10  985466.7
6370.79  1.12e+06
6123.33  1.07e+06
```

如你所见，使用上述配置可以产生一共1G的流量，通过`top`命令我们可以看到所有的工作线程把大量的时间花费在阻塞IO上（下图中worker进程处在D状态）：
```
top - 10:40:47 up 11 days,  1:32，  1 user,  load average: 49.61， 45.77 62.89
Tasks: 375 total,  2 running, 373 sleeping,  0 stopped,  0 zombie
%Cpu(s):  0.0 us,  0.3 sy,  0.0 ni, 67.7 id, 31.9 wa,  0.0 hi,  0.0 si,  0.0 st
KiB Mem:  49453440 total, 49149308 used,   304132 free,    98780 buffers
KiB Swap: 10474236 total,    20124 used, 10454112 free, 46903412 cached Mem

  PID USER     PR  NI    VIRT    RES     SHR S  %CPU %MEM    TIME+ COMMAND
 4639 vbart    20   0   47180  28152     496 D   0.7  0.1  0:00.17 nginx
 4632 vbart    20   0   47180  28196     536 D   0.3  0.1  0:00.11 nginx
 4633 vbart    20   0   47180  28324     540 D   0.3  0.1  0:00.11 nginx
 4635 vbart    20   0   47180  28136     480 D   0.3  0.1  0:00.12 nginx
 4636 vbart    20   0   47180  28208     536 D   0.3  0.1  0:00.14 nginx
 4637 vbart    20   0   47180  28208     536 D   0.3  0.1  0:00.10 nginx
 4638 vbart    20   0   47180  28204     536 D   0.3  0.1  0:00.12 nginx
 4640 vbart    20   0   47180  28324     540 D   0.3  0.1  0:00.13 nginx
 4641 vbart    20   0   47180  28324     540 D   0.3  0.1  0:00.13 nginx
 4642 vbart    20   0   47180  28208     536 D   0.3  0.1  0:00.11 nginx
 4643 vbart    20   0   47180  28276     536 D   0.3  0.1  0:00.29 nginx
 4644 vbart    20   0   47180  28204     536 D   0.3  0.1  0:00.11 nginx
 4645 vbart    20   0   47180  28204     536 D   0.3  0.1  0:00.17 nginx
 4646 vbart    20   0   47180  28204     536 D   0.3  0.1  0:00.12 nginx
 4647 vbart    20   0   47180  28208     532 D   0.3  0.1  0:00.17 nginx
 4631 vbart    20   0   47180    756     252 S   0.0  0.1  0:00.00 nginx
 4634 vbart    20   0   47180  28208     536 D   0.0  0.1  0:00.11 nginx<
 4648 vbart    20   0   25232   1956    1160 R   0.0  0.0  0:00.08 top
25921 vbart    20   0  121956   2232    1056 S   0.0  0.0  0:01.97 sshd
25923 vbart    20   0   40304   4160    2208 S   0.0  0.0  0:00.53 zsh
```

在这种情况下，吞吐率受限于磁盘子系统，而CPU在大部分时间里是空闲的。从`wrk`获得的结果也非常低：
```
Running 1m test @ http://192.0.2.1:8000/1/1/1
  12 threads and 50 connections
  Thread Stats   Avg    Stdev     Max  +/- Stdev
    Latency     7.42s  5.31s   24.41s   74.73%
    Req/Sec     0.15    0.36     1.00    84.62%
  488 requests in 1.01m, 2.01GB read
Requests/sec:      8.08
Transfer/sec:     34.07MB
```

请记住，`wrk`请求的文件是缓存在内存中的，因为第一个客户端的200个连接创建的随机负载，使服务器端的全部的工作进程忙于从磁盘读取文件，因此产生了过大的延迟，并且无法在合适的时间内处理我们的请求。

然后亮出线程池了。为此，我们只需在location块中添加[aio](http://nginx.org/en/docs/http/ngx_http_core_module.html?&_ga=2.70004050.354182567.1515763628-1865268522.1506349358#aio) threads指令：
```nginx
location / {
  root /storage;
  aio threads;
}
```

接着，执行NGINX reload重新加载配置。

然后，我们重复上述的测试：
```
% ifstat -bi eth2
eth2
Kbps in  Kbps out
60915.19  9.51e+06
59978.89  9.51e+06
60122.38  9.51e+06
61179.06  9.51e+06
61798.40  9.51e+06
57072.97  9.50e+06
56072.61  9.51e+06
61279.63  9.51e+06
61243.54  9.51e+06
59632.50  9.50e+06
```

现在我们的服务器产生9.5Gbps的流量，对比之前没有线程池时只有1Gbps。

理论上还可以产生更多的流量，但是这已经达到了机器的最大网络吞吐能力，所以这个测试的瓶颈是网络接口。worker进程的大部分时间只是休眠和等待新的事件（下图`top`中的S状态）：
```
top - 10:43:17 up 11 days,  1:35，  1 user,  load average: 172.71， 93.84， 77.90
Tasks: 376 total,  1 running, 375 sleeping,  0 stopped,  0 zombie
%Cpu(s):  0.2 us,  1.2 sy,  0.0 ni, 34.8 id, 61.5 wa,  0.0 hi,  2.3 si,  0.0 st
KiB Mem:  49453440 total, 49096836 used,   356604 free,    97236 buffers
KiB Swap: 10474236 total,    22860 used, 10451376 free, 46836580 cached Mem

  PID USER     PR  NI    VIRT    RES     SHR S  %CPU %MEM    TIME+ COMMAND
 4654 vbart    20   0  309708  28844     596 S   9.0  0.1  0:08.65 nginx
 4660 vbart    20   0  309748  28920     596 S   6.6  0.1  0:14.82 nginx
 4658 vbart    20   0  309452  28424     520 S   4.3  0.1  0:01.40 nginx
 4663 vbart    20   0  309452  28476     572 S   4.3  0.1  0:01.32 nginx
 4667 vbart    20   0  309584  28712     588 S   3.7  0.1  0:05.19 nginx
 4656 vbart    20   0  309452  28476     572 S   3.3  0.1  0:01.84 nginx
 4664 vbart    20   0  309452  28428     524 S   3.3  0.1  0:01.29 nginx
 4652 vbart    20   0  309452  28476     572 S   3.0  0.1  0:01.46 nginx
 4662 vbart    20   0  309552  28700     596 S   2.7  0.1  0:05.92 nginx
 4661 vbart    20   0  309464  28636     596 S   2.3  0.1  0:01.59 nginx
 4653 vbart    20   0  309452  28476     572 S   1.7  0.1  0:01.70 nginx
 4666 vbart    20   0  309452  28428     524 S   1.3  0.1  0:01.63 nginx
 4657 vbart    20   0  309584  28696     592 S   1.0  0.1  0:00.64 nginx
 4655 vbart    20   0  30958   28476     572 S   0.7  0.1  0:02.81 nginx
 4659 vbart    20   0  309452  28468     564 S   0.3  0.1  0:01.20 nginx
 4665 vbart    20   0  309452  28476     572 S   0.3  0.1  0:00.71 nginx
 5180 vbart    20   0   25232   1952    1156 R   0.0  0.0  0:00.45 top
 4651 vbart    20   0   20032    752     252 S   0.0  0.0  0:00.00 nginx
25921 vbart    20   0  121956   2176    1000 S   0.0  0.0  0:01.98 sshd
25923 vbart    20   0   40304   3840    2208 S   0.0  0.0  0:00.54 zsh
```

现在仍然有充足的CPU资源可以利用。下边是`wrk`的结果：
```
Running 1m test @ http://192.0.2.1:8000/1/1/1
  12 threads and 50 connections
  Thread Stats   Avg      Stdev     Max  +/- Stdev
    Latency   226.32ms  392.76ms   1.72s   93.48%
    Req/Sec    20.02     10.84    59.00    65.91%
  15045 requests in 1.00m, 58.86GB read
Requests/sec:    250.57
Transfer/sec:      0.98GB
```

服务器处理4MB文件的平均时间从7.42秒降到226.32毫秒（减少了33倍），每秒请求处理数提升了31倍（250 vs 8）！

这个结果我们的解释是请求不再因为工作进程因为读文件阻塞，而在事件队列中等待处理，读文件由空闲的线程专门处理。只要磁盘子系统能撑住第一个客户端上的随机负载，NGINX可以使用剩余的CPU资源和网络容量，从内存中读取文件服务于第二个客户端的请求。

#### 线程池不是银弹 
在抛出我们对阻塞操作的担忧并给出一些令人兴奋的结果后，可能大部分人已经打算在你的服务器上配置线程池了。但是先别着急。

实际上很幸运大多数的读或者写文件操作都不会和硬盘打交道。如果我们有足够的内存来存储数据，那么操作系统会聪明地在被称作“page cache”的地方缓存那些频繁使用的文件。

page cache的效果很好，可以让NGINX在几乎所有常见的用例中展示优异的性能。从page cache中读取比较快，没有人会说这种操作是“阻塞”。另一方面，把任务“卸载”到线程池是有一定开销的。

因此，如果你的机器有合理的大小的内存并且待处理的数据集不是很大的话，那么无需使用线程池，NGINX已经工作在最优化的方式下。

“卸载”读操作到线程池是一种适用于非常特殊任务的技术。只有当经常请求的内容比操作系统的虚拟内存大时，这种技术才是最有用的。至于可能适用的场景，比如，基于NGINX的高负载流媒体服务器。这正是我们已经上文模拟的基准测试的场景。

我们如果可以改进“卸载”读操作到线程池将会非常有意义。我们只需要知道所需的文件数据是否在内存中，只有不在内存中的时候读操作才应该“卸载”到线程池的某个线程。

再回到售货员的场景中，这回售货员不知道要买的商品是否在店里，他必须要么总是将所有的订单提交给运货服务，要么总是亲自处理它们。

问题的本质就是操作系统没有这样的特性。2010年人们第一次试图把这个功能作为[`fincore()`](https://lwn.net/Articles/371538/)系统调用加入到Linux当中，但是没有成功。后来还有一些是使用`RWF_NONBLOCK`标记作为`preadv2()`系统调用来实现这一功能的尝试（详情见LWN.net上的[非阻塞缓冲文件读取操作](https://lwn.net/Articles/612483/)和[异步缓冲读操作](https://lwn.net/Articles/636967/)）。但所有这些补丁的命运目前还不明朗。悲催的是，这些补丁没有被内核接受的原因还在持续讨论[bikeshedding](http://bikeshed.com/)。

另一方面，FreeBSD的用户完全不必担心。FreeBSD已经具备足够好的异步读取文件接口，我们应该用它而不是线程池。

#### 配置线程池
所以如果你确信在你的用例中使用线程池会带来好处，那么现在就是时候深入了解线程池的配置了。

线程池的配置非常简单、灵活。首先，获取NGINX 1.7.11及以上版本的源代码，使用`--with-threads`参数执行`configure`，NGINX Plus的用户需要使用Release 7及以上的版本。在最简单的场景中，配置也看起来很简单。所有你需要做的只是在合适的上下文中包含aio threads的指令：
```nginx
# in the 'http'， 'server'， or 'location' context
aio threads;
```

这是线程池的最简配置。实际它是下面配置的简写：
```nginx
# in the 'main' context
thread_pool default threads=32 max_queue=65536;

# in the 'http'， 'server'， or 'location' context
aio threads=default;
```

这里定义了一个名为`default`、包含32个线程、任务队列长度为65536的线程池。如果任务队列过载，NGINX将拒绝请求并输出如下错误日志：
```
thread pool "NAME" queue overflow: N tasks waiting
```

错误输出意味着线程处理任务的速度可能赶不上任务入队的速度了。你可以尝试增加队列长度，但是如果这无济于事，那这意味着你的系统没有能力处理这么多的请求了。

正如你已经注意到的，你可以使用[thread_pool](http://nginx.org/en/docs/ngx_core_module.html?&_ga=2.65613804.354182567.1515763628-1865268522.1506349358#thread_pool)指令，配置线程的数量、队列的最大长度，以及特定线程池的名称。最后要说明的是，可以配置多个相互独立的线程池，并在配置文件的不同位置使用它们来满足不同的用途：
```nginx
# in the 'main' context
thread_pool one threads=128 max_queue=0;
thread_pool two threads=32;

http {
    server {
        location /one {
            aio threads=one;
        }

        location /two {
            aio threads=two;
        }

    }
    #...
}
```

如果没有指定`max_queue`参数的值，默认使用的值是65536。如上所示，可以设置`max_queue`为0。在这种情况下，线程池只能处理线程池中线程个数那么多的任务,队列中不会有等待的任务（译者注：也就是没有队列）。

现在，假设我们有一台3块硬盘的服务器，我们希望把该服务器用作“缓存代理”，缓存后端服务器的全部响应。预期的缓存数据量远大于可用的内存。它实际上是你个人CDN的一个缓存节点。毫无疑问，在这种情况下，最重要的事情是发挥硬盘的最大性能。

我们的选择之一是配置一个RAID阵列。这种方法毁誉参半，现在借助NGINX，我们可以有另外的选择：
```nginx
# We assume that each of the hard drives is mounted on one of these directories:
# /mnt/disk1， /mnt/disk2， or /mnt/disk3

# in the 'main' context
thread_pool pool_1 threads=16;
thread_pool pool_2 threads=16;
thread_pool pool_3 threads=16;

http {
    proxy_cache_path /mnt/disk1 levels=1:2 keys_zone=cache_1:256m max_size=1024G
                     use_temp_path=off;
    proxy_cache_path /mnt/disk2 levels=1:2 keys_zone=cache_2:256m max_size=1024G
                     use_temp_path=off;
    proxy_cache_path /mnt/disk3 levels=1:2 keys_zone=cache_3:256m max_size=1024G
                     use_temp_path=off;

    split_clients $request_uri $disk {
        33.3%     1;
        33.3%     2;
        *         3;
    }

    server {
        #...
        location / {
            proxy_pass http://backend;
            proxy_cache_key $request_uri;
            proxy_cache cache_$disk;
            aio threads=pool_$disk;
            sendfile on;
        }
    }
}
```

在这份配置中，`thread_pool`指令为每块硬盘定义了一个专用、独立的线程池，[proxy_cache_path](http://nginx.org/en/docs/http/ngx_http_proxy_module.html?&_ga=2.2805490.354182567.1515763628-1865268522.1506349358#proxy_cache_path)指令在每个磁盘定义了一个专用、独立的缓存。

[split_clients](http://nginx.org/en/docs/http/ngx_http_split_clients_module.html?_ga=2.2805490.354182567.1515763628-1865268522.1506349358)模块用于缓存的负载均衡（以及磁盘之间的结果），它完全适合这类任务。

在`proxy_cache_path`指令中设置`use_temp_path=off`表示NGINX会将临时文件保存在缓存数据的同一目录中。这是为了避免在更新缓存时在磁盘之间互相复制响应数据。

这些调优将发挥磁盘子系统的最优性能，因为NGINX通过单独的线程池并行且独立地与每块磁盘交互。每个磁盘由16个独立线程处理，并有用于读取和发送文件的专用任务队列。

我们相信你的客户会喜欢这种量身定制的方法。请确保你的磁盘撑得住。

这个示例很好地证明了NGINX可以为硬件专门调优的灵活性。这就像你给NGINX下了一道命令，要求它和你的机器、数据最优配合。而且，通过NGINX在用户空间中细粒度的调优，你可以确保软件、操作系统和硬件工作在最优模式下并且尽可能有效地利用系统资源。

#### 总结
综上所述，线程池是个好功能，它将NGINX的性能提高到新的高度并且干掉了一个众所周知的长期隐患：阻塞，尤其是当我们真正面对大量吞吐的情况下这种优势更加明显。

但是还有更多的惊喜。正如前面所述，这种全新的接口可能允许将任何耗时和阻塞的操作“卸载”而不会造成任何性能的损失。NGINX在大量新模块和功能方面开辟了新的天地。许多受欢迎的库仍然没有提供异步非阻塞接口，以前这使得它们与NGINX的模型不兼容。我们可能花费大量的时间和精力来开发自己的非阻塞原型库，但是这么做可能并不值得。现在使用线程池，我们可以相对容易地使用这些库，并且这些模块不会对性能产生影响。

敬请期待下篇文章。

### 参考
[【译】提高nginx9倍性能的线程池](https://segmentfault.com/a/1190000010008012)