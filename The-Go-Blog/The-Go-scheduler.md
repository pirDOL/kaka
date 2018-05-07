## [The Go scheduler](http://morsmachine.dk/go-scheduler)

30 JUNE 2013 By Daniel Morsing

### TLDR
1. why
    1. linux上线程和进程都是通过task_struct实现的，但是Go不需要这种实现带来的特性，当goroutine超过100k时会显著增加开销。
    2. GC需要线程的内存得到一致性状态才能进行，Go的调度器能感知这一点
2. casts
    1. M: machine, os thread, This handling of syscalls is why Go programs run with multiple threads, even when GOMAXPROCS is 1. 
    3. G: goroutines, local runqueue, global mutex contention
    2. P: processor, context running goroutine, GOMAXPROCS(), The reason we have contexts is so that we can hand them off to other threads if the running thread needs to block for some reason.
3. syscall：
    1. 调用syscall阻塞的goroutine继续在当前线程阻塞，等syscall返回时
        1. goroutine进入全局runqueue，等待其他context获取
        2. 当前线程放回线程池
    2. 当前线程上的context切换到另一个线程中继续执行runqueue中其他的goroutine
4. context的runqueue都执行完了，按照优先级：
    1. 从全局runqueue获取等待执行的goroutine
    2. 从其他context的runqueue中获取一半的goroutine，获取一半是均衡了负载，保证了同一时间有`GOMAXPROCS`个context在执行goroutine

### 翻译
#### 简介
Go 1.1最大的功能之一就是Dmitry Vyukov实现的新调度器。它显著提升了Go并发程序的性能，并且基本上已经没啥可以优化的了。我发现我应该写一点关于新调度器的文章。

这篇博客中的大多数内容都在[原始设计文档](https://docs.google.com/document/d/1TTj4T2JO42uD5ID9e89oa0sLKhJYD0Y_kqxDv3I3XMw)中描述了。这是一个相当详细的文档，但是有些太技术了。

所有你需要了解的关于新调度器的内容都在设计文档中，但是这篇博客比设计文档更好的地方是有图片。

#### 为什么Go的运行时需要一个调度器？
在我们看新调度器之前我们要理解为什么需要它。为什么操作系统能调度线程还需要创建一个用户态的调度器？

POSIX线程API是对unix现有进程模型的逻辑扩展，因此线程和进程在很多方面都类似。例如，线程有自己的信号掩码、CPU亲和性，可以被放到cgroup，可以查询它们使用的资源。但是有很多特性对于Go程序来说都不需要，并且当线程数很多时反而会增加开销。

另外一个问题是操作系统不能结合Go程序的内存模型进行调度决策。例如，Go在进行垃圾回收需要所有运行的线程都停止，使得内存处于一致的状态。这就要求调度器要能知道当前正在执行的线程运行到了内存一致性的暂停点。

当程序有很多随机调度的线程，你需要等待它们都执行到一个一致性的状态。Go的调度器可以感知到内存是否达到一致性状态，并根据这个进行调度决策。这就意味着当停止程序的运行，进行垃圾回收时，我们只需要等待正在CPU上执行的线程（达到一致性状态）。
>When you have many threads scheduled out at random points, chances are that you're going to have to wait for a lot of them to reach a consistent state. The Go scheduler can make the decision of only scheduling at points where it knows that memory is consistent. This means that when we stop for garbage collection, we only have to wait for the threads that are being actively run on a CPU core.

#### Our Cast of Characters（调度器中的角色）
有三种常见的线程模型：
    * N:1：N个用户态线程在1个内核态线程上运行。这种模型上下文切换非常快但是无法利用多核系统。
    * 1:1：1个用户态线程在1个内核态线程。这种充分利用了机器上的多核但是上下文切换非常慢，因为每一次调度都会在用户态和内核态之间切换。
    * M:N：Go尝试兼顾多核和调度上下文切换，因此选择了M:N模型，任意数量的goroutine可以在任意数量的操作系统线程（译者注：见下面M的解释）上执行。既能享受到快速的上下文切换，又能利用系统中的多核。这种模型的主要缺点是调度器实现比较复杂。

为了实现M:N的调度任务，Go的调度器使用了三种实体：M、P、G：
![](The-Go-scheduler/our-cast.ipg)

* M：三角形，代表操作系统线程，**它的执行由操作系统来管理，很类似于标准的POSIX线程**。在Go的运行时代码中M是machine的简写。
* G：圆形，代表goroutine，它拥有自己的栈，程序计数器和必要的调度信息（如阻塞在哪些channel上）。在Go的运行时代码中G是goroutine的简写。
* P：矩形，代表调度的上下文。可以把它看作是一个局部的调度器，在一个单独的线程上执行的Go代码。**这是让Go从N:1调度器进化为M:N调度器的关键**。在Go的运行时代码中M是processor的简写。

![](The-Go-scheduler/in-motion.ipg)

如上图所示，有两个线程M，每个线程运行了一个goroutine G，所以必须得维持一个上下文P。

上下文的数量由启动时通过环境变量`GOMAXPROCS`或者是由`runtime.GOMAXPROCS()`方法设置。通常在程序执行的过程中，这个数字不发生变化。这意味着在任意时刻最多只有`GOMAXPROCS`个goroutine在同时运行Go代码（译者注：这只是Go的调度器的限制，操作系统调度可能使得同一时间正在执行的线程数比`GOMAXPROCS`少，同一时间执行的线程数最多不超过CPU逻辑核数）。你可以通过这个参数对Go进程在不同的机器上的调用进行调优，例如在一个4核的PC上，同一时间只能有4个线程同时执行Go代码。

灰色的goroutine没有在运行，等待被调度。它们被维护在一个叫做runqueues的队列中。当通过`go`语句创建一个goroutine时，会把它添加到队列尾。当正在运行的goroutine遇到调度点时，就从队列中弹出一个新的goroutine。

为了避免锁的争抢，每一个context拥有一个局部的runqueue。之前版本的Go调度器只有一个全局的带有互斥锁的runqueue，这样线程经常被阻塞在这个锁上，在多核机器上性能表现及其差。

调度器工作在一个稳定循环中：保证所有的P都有goroutine在执行。然而会有些特殊的场景。

#### Who you gonna (sys)call?
你可能会疑惑为什么需要维护多个context，能不能让操作系统的线程直接管理runqueue？不能，我们引入context的目的是当一个操作系统的线程被阻塞时，我们可以把这个线程上的context移到其它的线程中去。操作系统线程阻塞的一个典型场景就是系统调用。操作系统的线程执行系统阻塞时就会被操作系统调度让出CPU，这时我们需要把因为执行系统调用阻塞的goroutine切换到其他线程，而当前线程继续执行其他的goroutine。

![](The-Go-scheduler/syscall.ipg)

如上图所示，当一个线程M0要被阻塞时，M
0会放弃P，让P去另一个线程M1上继续运行。Go的调度器保证了拥有足够的线程运行`GOMAXPROCS()`指定数量的context。上图中的M1线程可能是为了处理系统调用新创建的，也可能是线程池中的空闲线程。因为M0上的goroutine执行了系统调用，M0会被操作系统挂起。

当syscall返回时，M0会尝试获取一个context来运行G0。一般情况下，它会从其它内核线程偷一个过来。如果没有偷到，它会把G0放到一个全局的runqueue内，将自己放回线程池，进入睡眠状态。

当context运行完所有的本地runqueue时，它会从全局runqueue拉取goroutine。context也会周期性检查全局runqueue是否存在goroutine，以防止全局runqueue中的goroutine饿死。

为了处理系统调用，即使设置了`GOMAXPROCS`为1，Go程序也是多线程的。The runtime uses goroutines that call syscalls, leaving threads behind.

#### Stealing work
另外一种导致调度器稳定工作状态改变的情况就是某个context的所有都goroutine运行完了。这种情况会在context的runqueue数量不平衡时出现，这种情况会导致没有goroutine的context提前结束，但是其实系统中还有其他可以执行的goroutine。为了确保context能执行Go代码，context除了在本地runqueue为空时可以从全局runqueue中获得goroutine以外，还需要从其它的地方获取goroutine，显然除了全局runqueue，还可以从其他context的runqueue获取goroutine。

如图所示，context会尝试从其它context的runqueue里面偷一半的goroutine。这样就能确保每个context都有goroutine执行，从而所有的线程都能以最大负荷运行。

![](The-Go-scheduler/steal.ipg)

#### 接下来
关于调度器还有很多细节，例如cgo里面的线程、`LockOSThread()`函数以及和netpoller线程。这些超出了这篇博客的范围，但是仍然值得学习。我后面会介绍这些。在Go的运行时库中肯定有很多有意思的结构。


### 参考
[[翻译]Go语言调度器](https://www.cnblogs.com/lcchuguo/p/5197957.html)
[Golang调度器](https://www.jianshu.com/p/aada4328ddf4)