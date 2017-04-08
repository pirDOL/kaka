## [Go Concurrency Patterns: Timing out, moving on](https://blog.golang.org/go-concurrency-patterns-timing-out-and)

23 September 2010 By Andrew Gerrand

并发程序的编写有自己的习语。超时是一个很好的例子。尽管Go的channel并不直接支持超时，但是超时是很容易实现的。假如我们想从一个channel接收数据，但是还想控制等待的时间最长不超过1秒。
>Concurrent programming has its own idioms.

我们的第一版实现是这样的：创建一个用于通知超时信号的channel，启动一个goroutine，睡眠1秒后向这个channel中发送数据。接收端通过select语句同时等待数据channel和超时channel可读。如果1秒以后，数据channel仍然不可读，超时channel就会被选中，就不会再等待数据channel。

超时channel是带缓冲的，这样可以让写超时channel的goroutine直接退出，这个goroutine其实并不关心超时channel中的数据是不是接收到了。这样也避免了这个goroutine阻塞，如果在超时前数据channel可读，接收端读取了数据channel以后就不再等待超时channel，此时如果超时channel不带缓冲，写超时channel的goroutine会阻塞无法退出。超时channel最终会被GC回收。

在上面这个例子中，我们使用了`time.Sleep`来展示goroutine和channel的工作机制。在实际应用中，应该使用[`time.After`](http://golang.org/pkg/time/#After)，这个函数直接返回一个channel，当指定的超时到达时，会写这个channel。

```go
timeout := make(chan bool, 1)
go func() {
    time.Sleep(1 * time.Second)
    timeout <- true
}()

select {
case <-ch:
    // a read from ch has occurred
case <-timeout:
    // the read from ch has timed out
}
```

让我们再看一个超时模式的变种。在这个例子中，我们有一个从多个副本数据库中同步读取的程序，只要有其中一个副本返回结果，就认为读取成功。
>Let's look at another variation of this pattern. 

Query函数输入一个数据库连接的slice以及一个查询字符串，并行所有的数据库，返回接收到的第一个结果。

在这个例子中，**闭包通过带有default分支的select实现了非阻塞发送**。如果写ch的分支没有就绪（译者注：c.DoQuery没有返回），那么会选择default分支。非阻塞发送的目的是为了保证循环里通过闭包启动的goroutine不会阻塞循环。

然而，如果在Query准备好读取ch之前，c.DoQuery就返回了结果，那么写ch会阻塞，导致select走default分支，也就是说尽管这个结果返回了，但并没有成功写入到ch中去。这个问题是竞态条件的一种，修复的方法很平凡，只需要把ch改为带缓冲的就行了（在make函数第二个参数增加缓冲大小）。确保第一个返回结果的goroutine有地方写结果（译者注：不会因为写ch阻塞导致走default分支），这样就保证了无论程序以什么顺序执行，向ch写的第一个结果一定会成功。
>but the fix is trivial

```go
func Query(conns []Conn, query string) Result {
    ch := make(chan Result, 1)
    for _, conn := range conns {
        go func(c Conn) {
            select {
            case ch <- c.DoQuery(query):
            default:
            }
        }(conn)
    }
    return <-ch
}
```

上面的两个例子展示了Go语言中goroutine之间复杂交互的实现起来是很简洁的。