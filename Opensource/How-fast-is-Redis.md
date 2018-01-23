## [How fast is Redis?](https://redis.io/topics/benchmarks)

### TLDR
1. key space: run 1M SET operations, using a random key for every operation out of 100k possible keys
2. pipeline:
  1. example: every client sends the next command only when the reply of the previous command is received, this means that the server will likely need a read call in order to read each command from every client.
1. experience data
  1. pipeline: ./redis-benchmark -r 1000000 -n 2000000 -t get,set -P 16
    1. SET QPS: 552k vs 122k
    2. GET QPS: 704k vs 122k
  2. unix-domain vs tcp loopback: numactl -C 6 ./redis-benchmark -q -n 100000 -s /tmp/redis.sock -d 256
    1. SET QPS: 198k vs 142k
    2. GET QPS: 198k vs 142k
1. reproducible result:
  1. set the highest possible fixed frequency for all the CPU cores involved in the benchmark.
  2. avoid putting RDB or AOF files on NAS or NFS shares, or on any other devices impacting your network bandwidth and/or latency (for instance, EBS on Amazon EC2).
1. pitfalls and misconceptions
  1. the golden rule of a useful benchmark is to only compare apples and apples. For instance, Redis and memcached in single-threaded mode can be compared on GET/SET operations. Both are in-memory data stores, working mostly in the same way at the protocol level. 
    1. different versions of Redis can be compared on the same workload.
    2. same versions of Redis can be compared with different options.
    3. Redis is a server: all commands involve network or IPC round trips. It is meaningless to compare it to embedded data stores such as SQLite.
    4. Redis is single-threaded. It is not really fair to compare one single Redis instance to a multi-threaded data store.
    6. It is absolutely pointless to compare the result of redis-benchmark to the result of another benchmark program and extrapolate. 
  1. the throughput achieved by redis-benchmark being somewhat artificial, and not achievable by a real application.
    2. The redis-benchmark program is a quick and useful way to get some figures and evaluate the performance of a Redis instance on a given hardware.
    1. use a pipeline size that is more or less the average pipeline length you'll be able to use in your application.
  2. Naively iterating on synchronous Redis commands does not benchmark Redis itself, especially on high performance hardware, but rather measure your network (or IPC) latency and the client library intrinsic latency. To really test Redis, you need multiple connections (like redis-benchmark) and/or to use pipelining to aggregate several commands and/or scaled out benchmark programs and/or a fast client (hiredis). 
1. Factors impacting Redis performance.
  1. a typical Redis instance running on a low end, untuned box usually provides good enough performance for most applications.
  2. network:
    1. To consolidate several high-throughput Redis instances on a single server, it worth considering putting a 10 Gbit/s NIC or multiple 1 Gbit/s NICs with TCP/IP bonding.
    2. estimate the throughput in Gbit/s and compare it to the theoretical bandwidth of the network: key per second plus payload per key.
    3. unix domain sockets can achieve around 50% more throughput than the TCP/IP loopback (on Linux for instance)
    4. Best throughput is achieved by setting an affinity between Rx/Tx NIC queues and CPU cores, and activating RPS (Receive Packet Steering) support.
  3. CPU:
    1. People are supposed to launch several Redis instances to scale out on several cores if needed. 
    2. Being single-threaded, Redis favors fast CPUs with large caches and not many cores. At this game, Intel CPUs are currently the winners. It is not uncommon to get only half the performance on an AMD Opteron CPU compared to similar Nehalem EP/Westmere EP/Sandy Bridge Intel CPUs with Redis.
    3. On multi CPU sockets servers, Redis performance becomes dependent on the NUMA configuration and process location. The most visible effect is that redis-benchmark results seem non-deterministic because client and server processes are distributed randomly on the cores. To get deterministic results, it is required to use process placement tools (on Linux: taskset or numactl). The most efficient combination is always to put the client and server on two different cores of the same CPU to benefit from the L3 cache.
  1. RAM: For large objects (>10 KB), speed of RAM and memory bandwidth may become noticeable though.
  2. data size: When an ethernet network is used to access Redis, aggregating commands using pipelining is especially efficient when the size of the data is kept under the ethernet packet size (about 1500 bytes).
  3. number of client connections:
    1. Being based on epoll/kqueue, the Redis event loop is quite scalable. Redis has already been benchmarked at more than 60000 connections, and was still able to sustain 50000 q/s in these conditions. 
    2. As a rule of thumb, an instance with 30000 connections can only process half the throughput achievable with 100 connections.
  1. Redis can be compiled against different memory allocators (libc malloc, jemalloc, tcmalloc), which may have different behaviors in term of raw speed, internal and external fragmentation.

### 翻译

#### How fast is Redis?
Redis包含了一个`redis-benchmark`实用工具可以模拟N个客户端同时发送M个查询命令执行，类似于Apache的`ab`工具。下面你会看到在Linux中执行的完整的性能测试执行结果输出。redis-benchmark支持下面的选项：
```
Usage: redis-benchmark [-h <host>] [-p <port>] [-c <clients>] [-n <requests]> [-k <boolean>]

 -h <hostname>      Server hostname (default 127.0.0.1)
 -p <port>          Server port (default 6379)
 -s <socket>        Server socket (overrides host and port)
 -a <password>      Password for Redis Auth
 -c <clients>       Number of parallel connections (default 50)
 -n <requests>      Total number of requests (default 100000)
 -d <size>          Data size of SET/GET value in bytes (default 2)
 --dbnum <db>       SELECT the specified db number (default 0)
 -k <boolean>       1=keep alive 0=reconnect (default 1)
 -r <keyspacelen>   Use random keys for SET/GET/INCR, random values for SADD
  Using this option the benchmark will expand the string __rand_int__
  inside an argument with a 12 digits number in the specified range
  from 0 to keyspacelen-1. The substitution changes every time a command
  is executed. Default tests use this to hit random keys in the
  specified range.
 -P <numreq>        Pipeline <numreq> requests. Default 1 (no pipeline).
 -q                 Quiet. Just show query/sec values
 --csv              Output in CSV format
 -l                 Loop. Run the tests forever
 -t <tests>         Only run the comma separated list of tests. The test
                    names are the same as the ones produced as output.
 -I                 Idle mode. Just open N idle connections and wait.
```

在启动性能测试之前，你需要启动一个Redis服务实例，一个典型的性能测试的例子是：
```
redis-benchmark -q -n 100000
```

使用这个工具很简单，你也可以自己写性能测试工具，但是无论是通过什么工具进行性能测试，都需要避免一些常见的错误。

#### 执行一个测试子集
每次执行redis-benchmark时，你不需要运行所有的测试集合。最简单的方法是像下面的例子中那样，通过-t选项选择要使用的一个测试子集：
```
$ redis-benchmark -t set,lpush -n 100000 -q
SET: 74239.05 requests per second
LPUSH: 79239.30 requests per second
```

在上面的例子中，我们只执行了SET和LPUSH命令，并通过-q选项开启安静模式。

还可以像下面的例子那样直接指定性能测试使用的命令：
```
$ redis-benchmark -n 100000 -q script load "redis.call('set','foo','bar')"
script load redis.call('set','foo','bar'): 69881.20 requests per second
```

#### 选择key空间的大小
benchmark默认只操作一个key，因为redis是一个全内存的系统，这种人为构造的测试场景和真实场景相差不大，然而因为实际中可能会出现“缓存失效”，因此可以通过使用一个更大的key范围模拟更接近真实工作负载。

通过`-r`开关实现，例如：如果我想执行1M次SET操作，每次操作从100k个可能的key中随机选择一个，我可以使用下面的命令：
```
$ redis-cli flushall
OK

$ redis-benchmark -t set -r 100000 -n 1000000
====== SET ======
  1000000 requests completed in 13.86 seconds
  50 parallel clients
  3 bytes payload
  keep alive: 1

99.76% `<=` 1 milliseconds
99.98% `<=` 2 milliseconds
100.00% `<=` 3 milliseconds
100.00% `<=` 3 milliseconds
72144.87 requests per second

$ redis-cli dbsize
(integer) 99993
```

#### 使用流水线
默认benchmark会模拟50个client（通过`-c`选项指定其他的值），只有当收到上一个命令的响应时才会发送下一个命令，这意味着server需要对client的每个命令都调用一次网络读取，并且命令收发也有RTT的开销。

redis提供了[流水线机制](https://redis.io/topics/pipelining)，可以一次发送多条命令，现实生活中的应用通常会采用这个特性。redis流水线能够显著提升server每秒能够处理的操作数量。

下面这个例子在MacBook Air 11上测试了大小为16的流水线：使用流水线显著的提升了性能
```
$ redis-benchmark -n 1000000 -t set,get -P 16 -q
SET: 403063.28 requests per second
GET: 508388.41 requests per second
```

#### 陷阱和误解
[更多信息看这篇帖子](https://groups.google.com/forum/#!msg/redis-db/gUhc19gnYgc/BruTPCOroiMJ)

第一点很明显：有效的基准测试的黄金标准是只比较一个变量。不同版本的redis要在相同的工作负载下比较，相同版本的redis但是配置不同也要在相同的工作负载下比较。如果你想比较redis和其他数据库，考虑和评估它们的功能和技术差异是很重要的。

redis是一个服务器程序：所有的命令都涉及到网络和IPC往返通信。把redis和嵌入式数据存储（例如：SQLite、Berkeley DB、Tokyo/Kyoto Cabinet）比较是没有意义的，因为redis大部分操作主要消耗是网络和协议管理。

redis对所有常见的命令都会返回一个应答，其他有些数据库则不同，所以把redis和带有“一问一答”机制的数据库比较才有意义。

用同步命令简单的迭代是不能测试出redis服务器性能的，测试结果受你的网路延时以及client端redis sdk固有的延时制约。为了能真正测试出redis的性能，你需要想redis-benchmark那样使用多个client连接，并且通过流水线聚合发送多条命令，另外还要使用多进程 或者多线程。

redis是一个内存数据存储，同时也支持可选的持久化配置。如果你打算和事务型数据库比较（MySQL、PostgreSQL等），那么你需要考虑开启AOF功能，并设计适合业务需求的fsync策略。对于大部分命令的执行，redis都是以一个单线程的服务器的方式工作（新版本的redis会启动一些辅助线程完成其他的工作），（因为是单线程）redis在设计上就没打算使用多核，如果需要使用多核那么要在一台机器上启动多个redis实例。把单个redis实例和其他多线程的数据库比较有些不公平。

一个常见的误解是redis-benchmark只是让redis看起来性能很出众，redis-benchmark得到的吞吐量都有些虚高，实际生产环境中却达不到。这种想法是不对的。

redis-benchmark程序的目的是提供一种有用且快速的方式获取一些数据用意评估redis实例在给定硬件上的性能。然而这些数据不代表这个redis实例能够稳定输出的最大吞吐。事实上，通过使用流水线和一个高性能的sdk（hiredis），很容易实现比redis-benchmark更高的吞吐量。redis-benchmark的默认行为是通过调整并发影响吞吐量，默认情况下不使用流水线（需要通过-P选项打开）以及其他的并行机制（例如：每个连接只能有一个命令在等待server返回结果，或者多线程机制）。所以如果redis-benchmark的配置不合理，同时又触发了例如[BGSAVE](https://redis.io/commands/bgsave)之类的操作，那么redis-benchmark返回的结果就会很不理想。

使用流水线模式执行基准测试（目的是获得更高的吞吐量），你需要显式指定-P选项。值得注意的是，现实中很多基于redis的应用程序都通过使用流水线来提高性能。注意，你需要使用和你的应用程序相接近的流水线深度来进行测试，这样才能得到可信的数据。

最后，在把redis和其他的数据库比较时，基准测试需要在相同的操作以及相同的工作方式下执行。另外把redis-benchmark和其他基准测试工具的结果进行比较是没有意义的。

例如：redis和单线程模式（“相同的工作方式”）的memcached能够比较GET和SET操作（相同的操作）、二者都是内存数据库，在协议层的工作方式上基本类似，假如redis和memcached的基准测试程序都用流水线的方式聚集发送请求，并且使用相同数量的连接，这样测试结果才有比较的意义。

下面的例子由redis的作者antirez和memcached的作者dormando之间的对话组成，它们完美的展示了如何比较redis和memcached：
[antirez 1 - On Redis, Memcached, Speed, Benchmarks and The Toilet](http://antirez.com/post/redis-memcached-benchmark.html)
[dormando - Redis VS Memcached (slightly better bench)](http://dormando.livejournal.com/525147.html)
[antirez 2 - An update on the Memcached/Redis benchmark](http://antirez.com/post/update-on-memcached-redis-benchmark.html)

你会发现如果方方面面都考虑到了，最后redis和memcached这两种不同的实现之间的差别并没有很令人震惊。注意redis和memcached在这些基准测试之后发布的版本进行了优化。

最后，如果在高性能硬件上进行基准测试（对于redis和memcached这类的存储，通常都是部署在高性能的硬件上，所以它们肯定会遇到这种情况，原文：and stores like Redis or memcached definitely fall in this category），可能很难把服务器的硬件资源用满。有时，性能的瓶颈在于client端而不是server端，在这种情况下，client端（就是基准测试程序本身）必须要进行修复或者把cient分布式化，这样才能得到server端的最大吞吐。

#### 影响redis性能的因素
很多的因素会对redis的性能有直接的影响。我们会在这节列出来，它们会直接改变基准测试的结果，然而值得注意的是运行在低配置、未优化的操作系统上的redis服务实例对于大多数应用都有足够好的性能。

* 网络带宽和延迟通常会对性能有直接影响，好的方法是在基准测试之前用ping命令快速检查client和server之间的延迟是正常的。至于网络带宽，通常要估计所需带宽并和网络实际的带宽比较，例如：基准测试的字符串长度为4KB，吞吐量为100000 q/s，那么实际的带宽消耗是3.2 Gbit/s，如果网卡是10 Gbit/s是能够满足的，但是1 Gbit/s网卡不能满足。现实场景中redis的吞吐量的瓶颈首先是网络，然后才是CPU。如果一台服务上部署多个高吞吐的redis实例，有必要考虑使用10 Gbit/s网卡或者支持TCP/IP绑定的多块1 Gbit/s网卡。
* CPU是另一个重要的因素。redis的单线程架构更亲和缓存大的CPU，而不是多核。对于redis的这种玩儿法，Intel的CPU是当前的首选，在AMD Opteron的CPU上运行的redis只有类似Intel Nehalem EP/Westmere EP/Sandy Bridge的CPU上一半的性能。如果client和server在同机运行，CPU是redis-benchmark的瓶颈（译者注：因为redis-benchmark需要模拟多个client并发）。
* RAM的速度和内存的带宽在大部分基准测试，特别是value长度比较小的场景下不是一个关键的因素。当value超过10KB时，就需要考虑RAM速度和内存带宽了。通常，购买昂贵的高速内存模块来优化redis是不划算的。（译者注：意思是需要业务上拆分value不超过10KB？）
* redis在VM上运行的速度比使用相同硬件的物理机上直接运行的速度要慢。如果可以尽量在物理机上运行redis。然而，这不是意味着redis不适合在虚拟环境中执行，redis在虚拟环境中的性能还是足够好的，你可能遇到的大多数的性能问题都是由于虚拟机资源过度供应、非本地的高延迟磁盘或者老旧监控软件使用操作系统的fork实现很慢。
* 当server和client的benchmark程序在同一台机器上运行，TCP/IP的回环接口和unix domain套接字都能用于client和server通信。在Linux系统实现中，unix domain套接字比TCP/IP回环接口能提高50%的吞吐量。redis-benchmark默认使用TCP/IP回环接口。
* unix domain套接字相比TCP/IP的回环接口在吞吐量上的提升在使用深度较深的流水线时会减少。当使用以太网访问redis时，流水线对命令进行打包发送，如果包的大小不超过以太网的MTU（大约是1500字节），那么使用流水线就很有效。事实上处理10字节、100字节、1000字节的查询在吞吐量上的几乎相同的，如下图：
![](How-fast-is-Redis/Data_size.png)

* 多CPU插槽的服务器上redis的性能会依赖于NUMA的配置以及进程相对CPU的位置。最常见的效应是因为client和server进程随机的分布在CPU的核上，导致基准测试的结果不可信。想要改进这一点，需要使用进程绑核工具（Linux：taskset或者numactl）。最有效的结合是把client和server放在同一个物理CPU的不同物理核上，这样便于共享L3缓存（译者注：网络包能共享）。下面是value大小为4KB的SET操作在3种CPU的服务器上的基准测试（AMD Istanbul、Intel Nehalem EX、and Intel Westmere），测试了不同的进程绑核方式。注意这个测试不是为了比较不同型号的CPU的性能，所以省略了CPU的准确型号和频率。
![](How-fast-is-Redis/NUMA_chart.gif)

* 高并发应用配置下（原文：With high-end configurations），client连接数也是一个重要的因素。redis的事件循环是基于epoll/kqueue实现的，具有良好的可扩展性。redis在60000连接的场景下进行过基准测试，并且能够提供稳定的50000 q/s的吞吐。经验数据是30000连接的redis实例只有100连接的实例一半的处理能力。下面是一个例子展示了单redis实例的吞吐量和连接数的关系：
![](How-fast-is-Redis/Connections_chart.png)

* 高并发应用配置下，通过调整网卡和中断的配置能够获得更高的吞吐量。通过设置网卡多队列并打开RPS（Receive Packet Steering）可以获得最佳的吞吐量。更多的信息请看[这篇帖子](https://groups.google.com/forum/#!msg/redis-db/gUhc19gnYgc/BruTPCOroiMJ)。jumbo框架对于大value的对象可能会提供一些性能提升。
* 某些操作系统能够在编译redis时使用其他的内存分配器（libc malloc、jemalloc、tcmalloc），不同的内存分配器在分配速度、内部和外部的内存碎片（原文：internal and external fragmentation）等方面有不同的行为。如果你不是自己编译redis，你可以通过INFO命令的mem_allocator字段查看内存分配器。注意大部分的基准测试执行的时间都不够长，导致不会生成足够多的外部碎片，然而实际生产环境中的redis则可能运行很长时间。

#### 其他需要考虑的问题
任何性能测试都有的目标之一是获得可重复的结果，这样方便和其他测试的结果比较：
* 尽可能在独立的机器上执行测试，如果这个最佳实践不能满足，需要在测试过程中监控系统指标，检查性能测试是否被其他活动所影响。
* 一些家用电脑、笔记本甚至是一些服务器会有CPU变频的机制，需要在操作系统层面设置这个策略。一些CPU在根据工作负载调整CPU频率上会很激进，为了获得可重复的结果，最好把性能测试使用到的CPU设置为固定的最高频率。
* 根据性能测试调整硬件和操作系统是很重要的，内存需要保证足够并且不能被交换。Linux上别忘了设置overcommit_memory参数，注意redis在32位和64位系统上的内存footprint是不同的。
* 如果你打算在性能测试中使用RDB或者AOF，请检查系统中没有其他的I/O活动，不要把RDB或者AOF文件放在NAS或者NFS上，或者其他网络带宽和网络延时不稳定的硬件上（例如：EBS、Amazon EC2）。
* 设置redis的日志级别为warning或者notice，避免向远程文件系统打印日志。
* 避免使用可能会影响性能测试结果的监控工具，周期的通过INFO命令收集统计信息是可以的，但是MONITOR就会显著的影响性能。

#### 不同服务器上的性能测试结果
警告：注意下面的性能测试中的大多数都是几年前的数据，执行这些测试的机器相比今天已经很落后。这个网页应该更新，but in many cases you can expect twice the numbers you are seeing here using state of hard hardware。另外，redis 4.0比2.6在大多数工作负载下都要块。
* 50个client并发，执行2M个请求
* redis版本是2.6.14
* 使用loopback网络接口
* 测试的key空间是1M
* 分别测试了关闭流水线和深度为16的流水线

* Intel(R) Xeon(R) CPU E5520 @ 2.27GHz (with pipelining)
```
$ ./redis-benchmark -r 1000000 -n 2000000 -t get,set,lpush,lpop -P 16 -q
SET: 552028.75 requests per second
GET: 707463.75 requests per second
LPUSH: 767459.75 requests per second
LPOP: 770119.38 requests per second
```

* Intel(R) Xeon(R) CPU E5520 @ 2.27GHz (without pipelining)
```
$ ./redis-benchmark -r 1000000 -n 2000000 -t get,set,lpush,lpop -q
SET: 122556.53 requests per second
GET: 123601.76 requests per second
LPUSH: 136752.14 requests per second
LPOP: 132424.03 requests per second
```

* Linode 2048 instance (with pipelining)
```
$ ./redis-benchmark -r 1000000 -n 2000000 -t get,set,lpush,lpop -q -P 16
SET: 195503.42 requests per second
GET: 250187.64 requests per second
LPUSH: 230547.55 requests per second
LPOP: 250815.16 requests per second
```

* Linode 2048 instance (without pipelining)
```
$ ./redis-benchmark -r 1000000 -n 2000000 -t get,set,lpush,lpop -q
SET: 35001.75 requests per second
GET: 37481.26 requests per second
LPUSH: 36968.58 requests per second
LPOP: 35186.49 requests per second
```

#### 更多详细的测试（关闭流水线）
```
$ redis-benchmark -n 100000

====== SET ======
  100007 requests completed in 0.88 seconds
  50 parallel clients
  3 bytes payload
  keep alive: 1

58.50% <= 0 milliseconds
99.17% <= 1 milliseconds
99.58% <= 2 milliseconds
99.85% <= 3 milliseconds
99.90% <= 6 milliseconds
100.00% <= 9 milliseconds
114293.71 requests per second

====== GET ======
  100000 requests completed in 1.23 seconds
  50 parallel clients
  3 bytes payload
  keep alive: 1

43.12% <= 0 milliseconds
96.82% <= 1 milliseconds
98.62% <= 2 milliseconds
100.00% <= 3 milliseconds
81234.77 requests per second

====== INCR ======
  100018 requests completed in 1.46 seconds
  50 parallel clients
  3 bytes payload
  keep alive: 1

32.32% <= 0 milliseconds
96.67% <= 1 milliseconds
99.14% <= 2 milliseconds
99.83% <= 3 milliseconds
99.88% <= 4 milliseconds
99.89% <= 5 milliseconds
99.96% <= 9 milliseconds
100.00% <= 18 milliseconds
68458.59 requests per second

====== LPUSH ======
  100004 requests completed in 1.14 seconds
  50 parallel clients
  3 bytes payload
  keep alive: 1

62.27% <= 0 milliseconds
99.74% <= 1 milliseconds
99.85% <= 2 milliseconds
99.86% <= 3 milliseconds
99.89% <= 5 milliseconds
99.93% <= 7 milliseconds
99.96% <= 9 milliseconds
100.00% <= 22 milliseconds
100.00% <= 208 milliseconds
88109.25 requests per second

====== LPOP ======
  100001 requests completed in 1.39 seconds
  50 parallel clients
  3 bytes payload
  keep alive: 1

54.83% <= 0 milliseconds
97.34% <= 1 milliseconds
99.95% <= 2 milliseconds
99.96% <= 3 milliseconds
99.96% <= 4 milliseconds
100.00% <= 9 milliseconds
100.00% <= 208 milliseconds
71994.96 requests per second
```

注意：把value大小从256修改为1024、4096字节不会显著改变测试结果（实际上因为返回结果打包在一起，一个包最大1024字节，所以当value增大时GET命令会变慢）。同样，client数量从50改为256，测试结果是相同的。With only 10 clients it starts to get a bit slower.（译者注：为啥client数量从50减少为10个，响应时间反而变慢了？缓存失效）

如果测试的机器更换，那么测试结果就会发生变化。例如在一台低性能的机器：CPU为Intel core duo T5500 1.66 GHz，操作系统为Linux 2.6，会输出下面的内容：
```
$ ./redis-benchmark -q -n 100000
SET: 53684.38 requests per second
GET: 45497.73 requests per second
INCR: 39370.47 requests per second
LPUSH: 34803.41 requests per second
LPOP: 37367.20 requests per second
```

另一台64位系统，Xeon L5420 2.5 GHz的机器：
```
$ ./redis-benchmark -q -n 100000
PING: 111731.84 requests per second
SET: 108114.59 requests per second
GET: 98717.67 requests per second
INCR: 95241.91 requests per second
LPUSH: 104712.05 requests per second
LPOP: 93722.59 requests per second
```

#### 其他redis性能测试工具
还有很多第三方的工具能够对redis进行性能测试，参考相应工具的文档获得更多关于目标和能力的信息。
* [Redis Labs](https://twitter.com/RedisLabs)的[memtier_benchmark](https://github.com/redislabs/memtier_benchmark)是一个NoSQL Redis和Memcache流量生成和压测工具。
* [Twitter](https://twitter.com/twitter)的[rpc-perf](https://github.com/twitter/rpc-perf)是一个RPC服务的性能测试工具，支持redis和memcache。
* [Yahoo @Yahoo](https://twitter.com/Yahoo)的[YCSB](https://github.com/brianfrankcooper/YCSB)是一个针对很多数据库的性能测试工具，包括redis。

#### redis-benchmark在优化过的高端服务器上的结果
* Redis version 2.4.2
* 50个client，数据大小是256字节
* Linux系统版本为SLES10 SP3 2.6.16.60-0.54.5-smp，CPU是双核Intel X5670 @ 2.93 GHz
* redis-server和redis-benchmark分别在同一个cpu的不同核上运行

使用unix套接字：
```
$ numactl -C 6 ./redis-benchmark -q -n 100000 -s /tmp/redis.sock -d 256
PING (inline): 200803.22 requests per second
PING: 200803.22 requests per second
MSET (10 keys): 78064.01 requests per second
SET: 198412.69 requests per second
GET: 198019.80 requests per second
INCR: 200400.80 requests per second
LPUSH: 200000.00 requests per second
LPOP: 198019.80 requests per second
SADD: 203665.98 requests per second
SPOP: 200803.22 requests per second
LPUSH (again, in order to bench LRANGE): 200000.00 requests per second
LRANGE (first 100 elements): 42123.00 requests per second
LRANGE (first 300 elements): 15015.02 requests per second
LRANGE (first 450 elements): 10159.50 requests per second
LRANGE (first 600 elements): 7548.31 requests per second
```

使用tcp loopback接口：
```
$ numactl -C 6 ./redis-benchmark -q -n 100000 -d 256
PING (inline): 145137.88 requests per second
PING: 144717.80 requests per second
MSET (10 keys): 65487.89 requests per second
SET: 142653.36 requests per second
GET: 142450.14 requests per second
INCR: 143061.52 requests per second
LPUSH: 144092.22 requests per second
LPOP: 142247.52 requests per second
SADD: 144717.80 requests per second
SPOP: 143678.17 requests per second
LPUSH (again, in order to bench LRANGE): 143061.52 requests per second
LRANGE (first 100 elements): 29577.05 requests per second
LRANGE (first 300 elements): 10431.88 requests per second
LRANGE (first 450 elements): 7010.66 requests per second
LRANGE (first 600 elements): 5296.61 requests per second
```