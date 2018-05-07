## [The Go netpoller](http://morsmachine.dk/netpoller)

8 SEPTEMBER 2013 By Daniel Morsing

### TLDR
2. 每个client连接一个线程：
    1. 一个client的线程执行阻塞系统调用时不影响其他client的线程
    2. 线程数和client连接成正比，导致线程数暴增。
3. 每个client连接一个goroutine
    1. Go里面所有的IO接口都是阻塞的。Go生态的思想就是通过goroutine和channel代替callback和future。
    2. Go运行时会把socket设置为非阻塞，让IO操作未就绪时，会调度其他goroutine在当前线程上执行，而不是直接把这个线程阻塞。goroutine数:线程数是M:N的关系。
1. netpoller
    1. 作用：通过epoll把非阻塞同步IO转换为用户态的阻塞同步IO。
    2. 工作原理：当goroutine对一个socket执行读写时，因为socket是非阻塞的，当IO未就绪时会返回EAGAIN。此时Go运行时会把这个socket注册到netpoller线程的epoll上，把goroutine调度走，执行其他goroutine，当IO就绪时，netpoller的epoll会返回，netpoller会维护一个fd到goroutine的映射（一对多），当epoll返回fd就绪时，会找合适的机会把对应的goroutine重新调度执行。这样用户态看起来就是前面的goroutine阻塞了。
    3. 传承不守旧：Go的netpoller思想源自于传统的单线程事件循环，但是二者的差别在于netpoller维护的是goroutine，而传统的单线程事件循环需要维护上下文状态，比如tcp请求被分包导致了多次读回调，是不是读完了一个完整的请求包就是一个上下文状态。而netpoller把这些状态丢给了goroutine自己维护（也就是用户代码）。实现了调度和上下文状态解耦。

### 参考
[(Go语言)Go的网络轮询及IO机制](http://blog.csdn.net/aigoogle/article/details/44196877)

### 翻译
#### 简介
我又感到乏味了，或者我有一些[更重要的事情](http://www.structuredprocrastination.com/)要做。所以是时候写一篇关于Go运行时的博客了。这次我会看一下Go如何处理网络IO。

#### 阻塞
Go语言中，所有的IO都是阻塞的，Go的生态秉承一个思想：你看到的接口，通过goroutine和channel来并发处理，而不是用回调和futures。其中一个例子是net/http包中的http服务器，服务器每接收一个连接都会创建一个新的goroutine处理来自这个连接的所有请求，这种结构意味着我们能用很清晰的思路写request handler的代码：先做这个再做那个。不幸的是，操作系统提供的阻塞IO并不适合构建我们自己的阻塞IO接口。

在我[之前](http://morsmachine.dk/go-scheduler)有关Go运行时的文章中，我介绍了Go调度器如何处理系统调用。为了处理一个阻塞的系统调用，我们需要一个能阻塞在操作系统中的线程，因此如果要在操作系统的阻塞IO层之上构建我们自己的阻塞IO层，我们需要为每一个可能执行阻塞的系统调用的客户端创建一个新线程。当你拥有10000个客户端线程时这种做法开销就很高，因为这些客户端都会阻塞在自己的系统调用上等待IO操作成功。

这里Go通过使用操作系统提供的异步接口来解决上述这个问题，当执行阻塞系统调用时，Go会阻塞goroutine（译者注：goroutine阻塞了，Go运行时调度器会调度其他goroutine到这个线程上执行，而不会把这个线程阻塞）。

#### 网络轮询
将异步IO转为阻塞IO是通过netpoller来完成的，netpoller有自己独立的线程，当goroutine想要执行网络IO时会向netpoller线程发送事件，netpoller使用操作接口提供的IO复用接口来提供对网络socket进行轮询。Linux的实现是epoll，BSDs和Darwin的实现是kqueue，Windows的实现是IoCompletionPort。这些接口的共同之处是它们为用户态提供了一种轮询网络IO状态的高效方法。

当你在Go程序中打开或者接受一个网络连接时，这个连接背后的fd都被设置为非阻塞模式，它意味着如果在IO还没准备好的时候执行读写操作会返回EAGAIN错误。当一个goroutine尝试对一个连接进行读写时，如果没有返回EAGAIN错误就会执行相应的操作，否则调用netpoller，让netpoller在IO就绪的时候通知goroutine，然后goroutine就被从正在运行的线程上调度走，更换其他就绪的goroutine。

当某个fd的IO就绪时，操作系统会让netpoller的IO复用接口返回fd就绪的通知信号，netpoller就会检查内部的数据结构，看看是否有goroutines（译者注：原文是goroutines说明可能会有多个goroutine等待同一个fd）正阻塞在那个文件上，如果有则通知这些goroutines，这些goroutines随后会重新尝试在之前导致它阻塞的IO操作（译者注：实际上这个操作是通过Go的运行时代码实现的，对于用户态只能看到net.Conn.Read阻塞了一段时间然后返回了，用户态不需要执行重试）。

如果你觉得前面netpoller的工作原理和是在使用旧式的Unix系统中的select和poll方法，那恭喜你，基本猜对了，它的思路确实是这样。但是Go的netpoller查询的是能被调度的goroutine，而不是那些函数指针、包含了各种状态变量的结构体，这样你就不用管理这些状态，包括检查是不是收到完整的数据，也不用重新检查函数指针等（译者注：相当于把这些操作都放在goroutine中由用户态维护了），这些都是你在传统Unix网络IO需要操心的问题。