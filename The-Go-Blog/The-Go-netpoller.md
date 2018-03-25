## [The Go netpoller](http://morsmachine.dk/netpoller)

### TLDR


### 参考
[(Go语言)Go的网络轮询及IO机制](http://blog.csdn.net/aigoogle/article/details/44196877)

### 翻译

#### 简介
这篇介绍了Go的运行时系统——网络I/O部分。

#### 阻塞
Go语言中，所有的I/O都是阻塞的，因此我们在写Go系统的时候要秉持一个思想：不要写阻塞的interface和代码，然后通过goroutines和channels来处理并发，而不是用回调和futures。其中一个例子是“net/http"包中的http服务器，无论何时当http服务器接收一个连接，它都会创建一个新的goroutine处理来自这个连接的所有请求，这样我们就能写出很清晰的代码：先做什么，然后做什么。然而，不幸的是，操作系统提供的阻塞式I/O并不适合构建我们自己的阻塞式I/O接口(interface)。

在我之前有关Go运行时的文章中，其中一篇介绍了Go调度器如何处理系统调用。为了处理一个阻塞式的系统调用，我们需要一个操作系统线程，因此如果要在OS的I/O层之上构建我们自己的阻塞式I/O层,则需要为每一个goroutine客户端连接产生一个新的线程，因为这些连接执行系统调用的时候会阻塞。当你拥有10000个客户端线程时构建我们自己的阻塞式I/O层会变得异常昂贵，因为这些客户端都会阻塞在自己的系统调用上等待I/O操作成功。

这里Go通过使用OS提供的异步接口(epoll等)来解决上述这个问题，但是会阻塞那些正在执行I/O的goroutines。

#### 网络轮询
将异步式I/O转为阻塞式I/O是通过网络轮询(netpoller)这个部分来完成的，netpoller在自己的线程中，接收那些准备进行网络I/O的goroutines发来的消息，netpoller使用操作接口提供的接口来提供对网络sockets的轮询。在linux系统中，这个接口是epoll,在BSDs和Darwin中是kqueue，在Windows中是IoCompletionPort。这些接口的共同之处是它们为用户空间轮询网络IO状态提供了非常高效的方法。

无论何时在Go程序中打开或者接受一个连接，该连接背后的文件描述符都被设置为非阻塞模式。如果在文件描述符还没准备好的时候，试着使用该连接进行I/O，就会返回一个无法进行I/O的错误。当一个goroutine尝试对一个连接进行读或者写的时候，如果没有收到上述报错，则执行这次操作，否则调用netpoller，当可以执行I/O的时候让netpoller通知goroutine，随之goroutine就被从正在运行的线程上调度出去等待通知。

当操作系统通知netpoller可以在一个文件描述符上运行I/O后，它就会检查内部的数据结构，看看是否有goroutines正阻塞在那个文件上，如果有则通知这些goroutines，这些goroutines随后会重新尝试在之前导致它阻塞的I/O操作。

如果你觉得之前的介绍是在使用旧式的Unix系统中的select和poll方法，那恭喜你，基本猜对了。但是Go的netpoller查询的是能被调度的goroutine而不是那些函数指针、包含了各种状态变量的struct等，这样你就不用管理这些状态，也不用重新检查函数指针等，这些都是你在传统Unix网络I/O需要操心的问题，Go中不需要。