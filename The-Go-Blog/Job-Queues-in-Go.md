## [Job Queues in Go](https://www.opsdash.com/blog/job-queues-in-go.html)

<div align="right">Constructs and snippets to build your job queue in Go</div>

### TLDR
1. len(channel): queue length
2. select-default: try enqueue, not block when channel is full
3. close(channel): break for-range loop over channel
4. channel+select: WaitGroup.Wait with timeout
5. Context.cancel()+Context.Done(): notify worker exit
5. Context.Err(): drop rest jobs and exit **immediately** when close(channel)，select如果两个case（Context取消和任务channel可读）都就绪了，会随机选择一个，需要在任务channel中再判断一次Context.Err()才能实现**立即**退出
6. worker pool:
    1. The easiest way is to simply spawn multiple workers and have them read off the same job channel
    2. If 100 jobs were processed by 4 workers, each would do 25. However, this may or may not be the case, and your code should not assume fairness.
7. generic component: 
    1. best practice：you’re probably better off writing job queues tailored to each requirement.
    2. why：
        1. In reality though, the nitty-gritty details for each different place you’d want to use it will likely add to the complexity of the “generic” component
        2. Couple this with the fact that it’s easier to write out a job queue in Go than in most other languages

### 翻译
在[RapidLoop](https://www.rapidloop.com/)，我们几乎所有的开发都是用[Go]()实现的，包括我们的服务端以及[OpsDash](https://www.opsdash.com/)上服务和运行时间监控产品等。

Go在异步处理上有着上佳的表现。因为 goroutines 和 channels 是非常容易使用、不容易误用、并且和其他语言的async/await、promises、futures一样功能强大。下面我们一起来看一看用Go实现任务队列的有趣的代码。

#### “不是任务队列”的任务队列
我们先从一点玄学开始：有些时候，我们不需要一个任务队列，异步处理一个任务实现如下：
```go
go process(job)
```

这的确是很多场景下的绝佳选择，不如在处理一个HTTP请求中（异步）发送一封邮件。是否需要一个精心设计的架构处理任务取主要决于规模和复杂度，给任务增加队列并且通过可控的方式处理任务允许你增加更多的功能，例如限制并发任务数、生产者限流等等。

#### 最简单的任务队列
接下来看一个最简单的“队列和工作者处理队列中的任务”模型，goroutine和channel是这个模型最合适的抽象，使用它们就可以优雅、简洁的实现：
```go
func worker(jobChan <-chan Job) {
    for job := range jobChan {
        process(job)
    }
}

// make a channel with a capacity of 100.
jobChan := make(chan Job, 100)

// start the worker
go worker(jobChan)

// enqueue a job
jobChan <- job
```

代码中创建了一个Job对象的channel, 容量为100。然后开启一个名为worker的goroutine，它从channel 中去取任务并执行。任务的入队操作就是将一个Job对象放入任务 channel 中。

虽然上面只有短短的几行代码，却完成了很多的工作。我们实现了一个线程安全的、能够正确工作的、没有竞态条件的代码，而且不需要操心线程和互斥锁。接下来就需要考虑生产者限流了。

#### 生产者限流
```
// make a channel with a capacity of 100.
jobChan := make(chan Job, 100)

// enqueue a job
jobChan <- job
```

上面的例子中，我们初始化了一个容量为100的channel，这意味着当channel中已经放入 100个任务的时候，再次进行入队操作将会阻塞，直至有任务被工作者处理完成。这通常是一个好事，因为我们通常不希望积压的任务增长的太多，从而打破SLA/QoS的限制。或者是另外一个合理的假设，任务必须在一定的时间内完成。例如，如果一个任务在最坏情况下需要花1s完成，那么容量为100的channel会让任务最慢需要耗时100s。

如果channel满了，你会希望发起任务的调用方能退避一段时间。例如：如果是一个REST API，你可以返回错误码503（服务不可用）以及相应的错误信息告诉让调用者等一会儿再重试。通过这种方法向调用者施加反向压力从而确保服务的质量可控。（原文：This way, you’re applying backpressure up the caller chain to maintain a predictable quality of service.）

#### 非阻塞入队
那么如何实现尝试入队，如果队列满会导致阻塞时返回失败呢？如果返回了失败就可以放弃任务提交操作并返回503。把戏就是使用带default的select：
```go
// TryEnqueue tries to enqueue a job to the given job channel. Returns true if
// the operation was successful, and false if enqueuing would not have been
// possible without blocking. Job is not enqueued in the latter case.
func TryEnqueue(job Job, jobChan <-chan Job) bool {
    select {
    case jobChan <- job:
        return true
    default:
        return false
    }
}
```

这样一来，你就可以像下面这样放弃提交任务：
```go
if !TryEnqueue(job, chan) {
    http.Error(w, "max capacity reached", 503)
    return
}
```

#### 关闭工作者
到目前整个任务队列的实现都还好，那么我们接下来考虑怎么优雅的关闭工作者？假设我们决定不再向任务队列提交任务，我们希望让所有的已入队任务执行完成，我们可以非常简单的实现：
```go
close(jobChan)
```

没错，就是这一行代码，这行代码能工作的原因是因为worker从队列中取任务是通过`for...range`循环实现的，当关闭channel循环就可以退出，所有在关闭channel之前已经入队的任务会正常被woker取走执行：
```go
for job := range jobChan {...}
```

#### 等待worker完成
上面的方法很简单。但是，调用`close(jobChan)`的协程不会等待worker协程，因此我们使用`sync.WaitGroup`：
```go
// use a WaitGroup 
var wg sync.WaitGroup

func worker(jobChan <-chan Job) {
    defer wg.Done()

    for job := range jobChan {
        process(job)
    }
}

// increment the WaitGroup before starting the worker
wg.Add(1)
go worker(jobChan)

// to stop the worker, first close the job channel
close(jobChan)

// then wait using the WaitGroup
wg.Wait()
```

我们通过关闭channel向worker发送停止信号，然后通过`wg.Wait()`等待worker协程退出。注意需要在启动worker协程之前调用`wg.Add()`，并且不论协程如何退出都要立即在协程内调用`wg.Done()`。

### 带超时的等待
上面的例子中`wg.Wait()`会一直等待worker协程退出，但是如果我们不想一直等待，下面是一个helper函数封装了带超时的`wg.Wait()`：
```
// WaitTimeout does a Wait on a sync.WaitGroup object but with a specified
// timeout. Returns true if the wait completed without timing out, false
// otherwise.
func WaitTimeout(wg *sync.WaitGroup, timeout time.Duration) bool {
    ch := make(chan struct{})
    go func() {
        wg.Wait()
        close(ch)
    }()
    select {
    case <-ch:
            return true
    case <-time.After(timeout):
            return false
    }
}

// now use the WaitTimeout instead of wg.Wait()
WaitTimeout(&wg, 5 * time.Second)
```

上面的函数允许你在有限的时间之内等待worker退出。

#### 取消worker
目前我们给予worker足够的自由，即使我们通过关闭channel通知它退出以后，worker还是可以处理任务。如果我们希望“worker丢弃剩余的工作立即退出”，怎么实现呢？

我们可以借助`context.Context`实现：
```go
// create a context that can be cancelled
ctx, cancel := context.WithCancel(context.Background())

// start the goroutine passing it the context
go worker(ctx, jobChan)

func worker(ctx context.Context, jobChan <-chan Job) {
    for {
        select {
        case <-ctx.Done():
            return

        case job := <-jobChan:
            process(job)
        }
    }
}

// Invoke cancel when the worker needs to be stopped. This *does not* wait
// for the worker to exit.
cancel()
```

首先我们创建了一个“可以取消的”Context，并把它传递给worker。worker除了等待任务channel以外，还等待`ctx.Done()`返回的channel，当`cancel`方法被调用时`ctx.Done()`返回的channel可读。

和关闭任务channel类似，`cancel`只发信号不等待worker退出，如果你需要等待worker退出，你需要增加WaitGroup的代码，等待的时间很短，因为worker不会处理队列中剩余的任务立即退出。

然而，上面的代码有一些边界情况（原文：there is a bit of a gotcha with this code）。如果任务channel中积压的任务（`<-jobChan`不会阻塞），此时调用了`cancel`方法（`<-ctx.Done()`也不会阻塞）。因为这两个case语句都不会阻塞，select需要从中选择一个，我们期望是公平选择。

然而在实际中并不是这样，很有可能尽管`<-ctx.Done()`不会阻塞，但是仍然选择了`<-jobChan`，并且实际中这种选择会经常发生。甚至是从任务channel中取出一个任务以后，任务channel中还有其他的任务，此时即使Context取消了，运行时会“犯同样的错误”。

为了公平选择，我们需要的是case语句优先级，而不是公平。Context的取消要比其他的case语句优先级更好，然而，说起来容易，内置的方法确不好实现。

需要通过一个标记来实现：
```go
var flag uint64

func worker(ctx context.Context, jobChan <-chan Job) {
    for {
        select {
        case <-ctx.Done():
            return

        case job := <-jobChan:
            process(job)
            if atomic.LoadUint64(&flag) == 1 {
                return
            }
        }
    }
}

// set the flag first, before cancelling
atomic.StoreUint64(&flag, 1)
cancel()
```

或者使用`Context.Err()`方法：
```go
func worker(ctx context.Context, jobChan <-chan Job) {
    for {
        select {
        case <-ctx.Done():
            return

        case job := <-jobChan:
            process(job)
            if ctx.Err() != nil {
                return
            }
        }
    }
}

cancel()
```

我们不是在处理任务之前检查flag/Err()，是因为既然任务已经从队列中取出来了，还是处理一下吧。当然，如果worker的退出优先级更高，可以在处理任务之前判断。

总之（原文：Bottom line? Either live with the fact that your worker...），要么容忍的你的worker在退出前处理一些额外的任务，要么仔细设计你的代码处理边界问题。

#### 不使用context实现取消
`context.Context`不是银弹，对于特定的问题，不用它可以让代码更简单和清晰：
```go
// create a cancel channel
cancelChan := make(chan struct{})

// start the goroutine passing it the cancel channel 
go worker(jobChan, cancelChan)

func worker(jobChan <-chan Job, cancelChan <-chan struct{}) {
    for {
        select {
        case <-cancelChan:
            return

        case job := <-jobChan:
            process(job)
        }
    }
}

// to cancel the worker, close the cancel channel
close(cancelChan)
```

上面的代码就是`Context.cancel()`内部的工作原理。同样也存在select优先级的问题。
原文：This is essentially what (simple, non-hierarchical) context cancellation does behind the scenes too. The same gotchas exist, unfortunately.

#### worker池
最后，多个worker可以让你增加任务并发度，最简单的方式是简单的创建多个worker，然后让它们从同一个任务队列中读取。其他的代码没有变化，会有很多的worker尝试从同一个任务channel中读取，这个操作是合法的也是安全的。只有一个worker会读取成功，其他的会阻塞。同样，这里也存在调度不公平的问题，如果4个worker处理100个任务，平均每个worker处理25个，然而实际上可能不会这样，你的代码不能假设调度是均匀的。
```go
for i:=0; i<workerCount; i++ {
    go worker(jobChan)
}
```

等待worker退出还是要使用一个WaitGroup：
```go
for i:=0; i<workerCount; i++ {
    wg.Add(1)
    go worker(jobChan)
}

// wait for all workers to exit
wg.Wait()
```

实现worker取消功能，你可以创建一个单独的channel，关闭这个channel通知所有的worker：
```go
// create cancel channel
cancelChan := make(chan struct{})

// pass the channel to the workers, let them wait on it
for i:=0; i<workerCount; i++ {
    go worker(jobChan, cancelChan)
}

// close the channel to signal the workers
close(cancelChan)
```

#### 通用任务队列库
从表面上看，任务队列很简单，很适合抽取成一个泛型、可重用的组件。但是在实际中，不同使用场景的具体细节和使用需求不同，为了适配和满足不同的场景，会增加“通用”组件的复杂性。再加上Go语言相比其他语言很容易写一个任务队列，所以你最好根据不同场景的需要量体裁衣单独实现。

### 参考
[Go 任务队列策略 -- 读《JOB QUEUES IN GO》](http://www.cnblogs.com/artong0416/p/7883381.html)