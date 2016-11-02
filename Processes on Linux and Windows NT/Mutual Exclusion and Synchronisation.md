# [互斥和同步](http://www.tldp.org/LDP/LG/issue23/flower/mutex.html)

允许多个进程在同一个时间片中访问相同的资源在多处理器系统中会导致很多问题。Allowing multiple processes access to the same resources *in a time sliced manner or potentially consecutively* in the case of multiprocessor systems can cause many problems. 这是因为需要保持数据的一致性、操作之间时序依赖（maintain true temporal dependencies）以及确保每个线程在完成操作时可以正确释放它们请求的资源。

多任务和多处理操作系统中的进程并发带来一系列潜在的问题：

* 进程饿死或无限等待：因为高优先级的进程一直占用CPU，低优先级的进程永远得不到运行机会（原文：A low priority process never gets access to the processor *due to the higher effective processor access of other processes.*）。解决方法是在进程用完CPU时间片时让进程退化（原文：cause processes to *'age'*，我理解就是把进程从运行队列移动到等待队列中？）或者降低进程的优先级
* 进程死锁：两个以上的进程竞争资源时各自占有了一部分，导致相互阻塞彼此。
* 竞态条件：处理结果取决于两个或者更多的进程完成任务的快慢。

数据一致性和竞态条件问题可以通过进程间的互斥和同步机制来处理，然而进程饿死则是调度器的一个功能（是说进程饿死是因为调度器原声的功能导致的？原文：The data consistency and race condition problems may be addressed by the implementation of Mutual Exclusion and Synchronisation rules between processes whereas starvation is a function of the scheduler.）。

几种同步原语：

* 事件：线程会等待诸如标志位、整数、信号以及一个实际存在的对象设置为预期值，在等待事件未就绪时，线程会被从运行队列中删除，并且处于阻塞状态。
* 临界段：一段代码片段，同一时间只允许一个线程访问。
* 互斥：互斥锁是一种对象，可以确保同一时间只有一个线程能够访问一个被锁保护的变量或者代码。
* 信号量：和互斥锁类似，信号量通过计数器允许一定数量的线程同一时间访问被保护的变量或者代码。
* 原子操作：这个机制确保一个不可拆分的事务。在线程完成操作之前，线程对CPU的占用是不可中断的。

死锁是一种一些列进程因为争抢系统资源导致永久阻塞的状态（原文：Deadlock is a permanent blocking of a set of processes that either compute for system resources or communicate with each other）。通过互斥以及死锁避免可以处理死锁。互斥防止了两个线程同时访问相同的资源。死锁避免包括include initiation denial or allocation denial，它们通过消除死锁的必要条件实现避免死锁。

Linux和Windows NT以不同的方式解决这些问题，Windows NT通过函数的方式等效实现上述同步原语的功能。Windows NT和Linux都通过自旋锁实现多处理器互斥机制，它高效使处理器空转（stall）直到临界段加锁成功。

