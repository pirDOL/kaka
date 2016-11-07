# [进程间通信](http://www.tldp.org/LDP/LG/issue23/flower/ipc.html)

每个进程都是在自己的虚拟地址空间上执行，操作系统保护进程之间的地址空间相互影响。通常用户的进程不能和其他的进程通信，除了使用内核提供的安全机制。很多场景下进程都需要共享资源、同步操作。一种解决方案是使用线程，同一个进程的所有线程是共享内存的，但是由于线程使用中的很多不足，这个解决方案并不是总是奏效的。因此在进程之间传递信息和数据还是必需的。

### Linux

Linux支持下面的通信方法，其中System V IPC指的是相应的IPC方法首先被提出时的Unix版本。

1. 信号：信号用于进程之间异步通信。进程通过定义信号句柄响应事件，或者也可以使用系统默认的行为。大多数信号可以被忽略或者阻塞，然而KILL信号不能被忽略，使得不干净的进程能够退出（原文：and will result in a non clean process exit）。
2. UNIX管道：管道连接一个进程的输出和另一个进程的输入，因此它提供了一种进程之间单向的半双工通信，通常用于父子进程之间。
3. 命名管道：和通常的管道类似，命名管道通过文件系统上的先进先出文件实现。使用它通信的进程不需要保持父子关系。命名管道是持久化的，在初始化以后可以重用。
4. System V IPC消息队列：消息队列是内核空间的链表，消息按顺序添加到队列，可以通过多种方式从队列中提取消息。
5. System V IPC信号量：信号量是用于控制多个进程访问共享资源的计数器。信号量通常被作为锁机制使用，是的当一个进程访问某个资源时，其他的进程会被阻止。信号量是通过set实现的，set里面只有一个成员。
6. System V IPC共享内存：共享内存是多个进程的地址空间中映射的同一块内存。这是最快的IPC方式，因为访问共享数据时不需要访问内核。
7. 全双工管道：STREAMS were introduced by AT&T and are used for character based I/O within the kernel and between it?s associated device drivers as a full duplex transfer path between processes. Internally pipes may be implemented as STREAMS.
8. RPC：基于Sun Microsystem的RPC标准实现的跨网络的进程之间通信协议。
9. 网络套接字：实现本地和网络之间进程的连接，套接字基于域实现，unix域中的套接字文件系统的目录来命名，进程通过它来实现通信。

### Windows NT

Windows NT进程间通信和同步的机制包括：

1. 事件、事件对：在进程创建、复制、继承时，
2. 匿名管道：主要用于相关进程之间通信，不能跨网络。
3. 命名管道：和匿名管道类似，区别在于通过名字而不是句柄来使用，可以跨网络，可以异步I/O和复用I/O（原文：can use asynchronous, overlapped I/O.）
4. 信号量：类似于Linux，NT的信号量对象是通过计数器实现的，用于对一段代码或者资源的保护。
5. 共享内存：section对象是一个Win32 subsystem对象，它通过文件映射的方式在进程之间共享。一个进程（译者注：原文这里用的是thread）创建section对象，另一个进程获取它的句柄》
6. RPC：RPC是分布式计算系统的标准实现，用于跨网络的进程调用。
7. 本地过程调用：和RPC在使用上类似的机制，只能单机工作，但通过内核提供的机制实现客户端和服务器之间的高效信息传递。信息的传递方式有三种：向服务器的端口对象的消息队列中写入消息（适用于较小的信息），也可以通过共享内存对象传递，还可以通过Win32 subsystem实现最小开销、最高速度的消息传递（Quick LPC）。
8. 流：Unix System V驱动环境的实现，用于跨网络的进程通信（原文：An implementation of the Unix System V *driver environment* used in networking.）
