## [Share Memory By Communicating](https://blog.golang.org/share-memory-by-communicating)

13 July 2010 By Andrew Gerrand

传统的线程模型（例如Java、C++和Python程序）需要程序员自己通过共享内存实现线程之间通信。通常，共享的数据结构需要锁保护，抢到锁的线程才能访问数据。此外，使用线程安全的数据结构，例如Python中的Queue可以简化线程之间的通信。

Go的并发原语（goroutine和channel）提供了并发程序的一种独特的、优雅的实现方式。goroutine和channel的概念其源自从C. A. R. Hoare的[Communicating Sequential Processes](http://www.usingcsp.com/)开始的[一段有趣的历史](http://swtch.com/~rsc/thread/)。Go鼓励使用channel在goroutine之间传递数据的引用，以此来避免显式使用锁来协调共享数据的访问。这个方法确保某个时刻只有一个goroutine能够访问数据。[Effective Go](http://golang.org/doc/effective_go.html)（所有Go程序员的必读）中这样总结Go的并发编程概念：**不要使用共享内存实现通信，而是使用通信实现共享内存**。
>Do not communicate by sharing memory; instead, share memory by communicating.

考虑一个对URL列表轮询的程序。传统的多线程环境中实现的数据结构以及轮询函数（可能被多个不同的线程同时执行）如下，轮询函数中还没写轮询的逻辑就已经大约占了一页纸，事实上轮询的逻辑可能只有几行，况且下面的代码还没有优雅的处理获取不到URL资源的情况。

让我们看一下使用Go风格实现的相同函数，在这个例子中，轮询函数从一个输入channel中接收资源（即URL），然后在处理完成以后，把它发送到输出channel。前一个例子中复杂的逻辑明显不再需要了，表示资源的数据结构中不再需要记录状态的字段，事实上，数据结构中只剩下了最关键的部分，这可能会让你领略到Go语言并发编程的特性是多么的简单和强大。
>Let's take a look at the same functionality implemented using Go idiom. 

```go
type Resource struct {
    url        string
    polling    bool
    lastPolled int64
}

type Resources struct {
    data []*Resource
    lock *sync.Mutex
}

func Poller(res *Resources) {
    for {
        // get the least recently-polled Resource
        // and mark it as being polled
        res.lock.Lock()
        var r *Resource
        for _, v := range res.data {
            if v.polling {
                continue
            }
            if r == nil || v.lastPolled < r.lastPolled {
                r = v
            }
        }
        if r != nil {
            r.polling = true
        }
        res.lock.Unlock()
        if r == nil {
            continue
        }

        // poll the URL

        // update the Resource's polling and lastPolled
        res.lock.Lock()
        r.polling = false
        r.lastPolled = time.Nanoseconds()
        res.lock.Unlock()
    }
}

type Resource string

func Poller(in, out chan *Resource) {
    for r := range in {
        // poll the URL

        // send the processed Resource to out
        out <- r
    }
}
```

上面的代码片段省略了关于Go并发编程的一些内容，完整的Go风格的并发编程代码请参考[这里](http://golang.org/doc/codewalk/sharemem/)。

### [Codewalk: Share Memory By Communicating](https://golang.org/doc/codewalk/sharemem/)

#### 简介
Go的并发方法和传统的使用线程和共享内存的方式不同，从哲学上可以总结为：
>Don't communicate by sharing memory; share memory by communicating.

channel实现了在goroutine之间传递数据结构的引用，如果你把channel看作是数据的所有权（即读写数据的能力）的传递，那么channel就是一种强大、意图清晰的同步机制。

在这个codewalk中，我们会通过一个简单的轮询url列表的程序，通过检查url的http的返回码，并周期的输出状态。

#### State类型
doc/codewalk/urlpoll.go:26,30

State类型表达的是url的状态，Poller把State类型的值传递给StateMonitor，后者维护了一个map，key是url，value是这个url的状态。

#### Resource类型
doc/codewalk/urlpoll.go:60,64

Resource类型表达的是被轮询的url以及这个url最近一次轮询成功以后到现在的错误计数。

当程序开始以后，会给每个url创建一个Resource结构体，主goroutine和Poller goroutine之间通过channel互相传递Resource。（译者注：Poller goroutine->complete channel->主goroutine，主goroutine->pending channel->Poller goroutine）

#### Poller函数
doc/codewalk/urlpoll.go:86,92

每个Poller从输入channel接收Resource指针。这个程序中，我们约定通过channel传递Resource的指针表示的语意是传递指针指向的数据的所有权。基于这个约定，我们知道不会出现接收者和发送者两个goroutine同时访问相同的Resource。这就意味着不需要在访问Resource时加锁。

Poller通过Poll方法处理Resource，然后把轮询的结果以State值的形式通过status channel传递给StateMonitor，最后再把Resource的指针写入out channel，这个操作表示的含义是：Poller已经完成了这个Resource的轮询，把Resource的所有权返回给主goroutine。

有多个goroutine同时执行Poller，并行处理Resource。

#### Poll方法
doc/codewalk/urlpoll.go:66,77

Resource类型的Poll方法向Resource的url发送HTTP的HEAD请求，然后返回HTTP响应报文的状态码。如果HTTP请求发生了错误，那么Poll会把错误记录到标准输出，然后返回错误信息的字符串。

#### main函数
doc/codewalk/urlpoll.go:94,116

main函数创建Poller和StateMonitor goroutine，然后循环从complete channel中读取轮询完成的Resource，在合适的延时后把它放回到pending channel中。

#### 创建channel
doc/codewalk/urlpoll.go:95,96

首先，main函数创建了两个channel：pending和complete，channel传递的数据类型为Resource的指针。

main函数单独创建了一个goroutine，它把每个url生成一个Resource，然后写入pending中。main函数从complete中接收轮询完成的url对应的Resource。

pending和complete这两个channel作为参数传递给Poller goroutine，后者中pending就是输入channel，complete就是输出channel。

#### 初始化StateMonitor
doc/codewalk/urlpoll.go:98,99

StateMonitor初始化并启动一个goroutine，它维护了每个Resource的状态。我们后面再来具体看这个函数。

现在，StateMonitor最重要的地方是它返回了一个channel，channel传递的数据类型为State。在main函数中StateMonitor返回的channel会传递给Poller。

#### 启动Poller goroutine
doc/codewalk/urlpoll.go:101,104
现在Poller goroutine需要的channel我们都介绍完了，main函数启动一定数量的Poller goroutine，把这些channel作为参数传递给它。这些channel实现了Poller、StateMonitor、main这些goroutine之间的通信。

#### 向pending发送Resource
doc/codewalk/urlpoll.go:106,111
main函数创建一个新的goroutine对每个url创建一个Resource，并把它的指针写入pending，这样才能开始工作循环。

通过一个新的goroutine写pending是必须的，因为pending没有buffer，因此收发都是同步的。这就意味着这些channel在发送时会阻塞，直到Poller从pending中读取Resource。

如果直接在主goroutine把url发送到pending会导致死锁。因为Poller的数量比url的数量少，循环向pending发送url会把Poller占满，同时主goroutine又不从complete中读取完成的url，即Poller即使完成了url的轮询，会因为写complete阻塞。

练习：从文件中读取一系列url，顺便把这个新的goroutine放在一个有名字的函数中。

#### 主事件循环
doc/codewalk/urlpoll.go:113,115

当一个Poller完成一个url的轮询时，Poller会把url发送给complete channel。主goroutine从complete中循环读取Resource，对于每个Resource调用Sleep方法，Sleep方法在一个新的goroutine中执行，确保多个Resource的Sleep是并行的。

注意：对于任意一个Resource指针，要么在pending中，要么在complete中。这确保了Poller goroutine和主goroutine只能有一个操作Resource。这样，我们通过channel通信实现了goroutine之间共享Resource。

#### Sleep方法
doc/codewalk/urlpoll.go:79,84

Sleep调用time.Sleep，实现了等待一段时间，然后完成一个url的一次轮询。等待的间隔包含两部分：固定间隔pollInterval加上和连续错误计数正成比例的延时。

Sleep是一种典型的Go习俗：一个在goroutine中执行的函数需要接收一个channel参数，函数的执行结果通过channel返回。

#### StateMonitor
doc/codewalk/urlpoll.go:32,50

从status channel中接收State类型的值，然后周期的输出所有Resource的状态。

#### update channel
doc/codewalk/urlpoll.go:36

update是一个传递State类型的channel，Poller goroutine向update中发送State类型的值。这个channel是StateMonitor函数返回的。

#### urlStatus map
doc/codewalk/urlpoll.go:37

urlStatus是一个map，key为url，value是这个url最近一次轮询的状态。

#### Ticker对象
doc/codewalk/urlpoll.go:38

time.Ticker是一个对象，它按照设定的间隔，重复的向一个channel写入值。在本文的程序中，ticker用于每隔updateInterval纳秒触发一次把所有url最近一次轮询的状态输出到标准输出。

#### StateMonitor goroutine
doc/codewalk/urlpoll.go:39,48

StateMonitor是一个无限循环，select两个channel：ticker.C和update，当任意一个channel就绪时，select结束阻塞状态。

当StateMonitor从ticker.C接收到一次定时时间到达时，StateMonitor调用logState把所有url最近一次轮询的状态输出到标准输出；当StateMonitor从update中接收到State时，会更新urlStatus中url的状态。

注意StateMonitor goroutine拥有urlStatus，确保了这个map只有一个goroutine可以访问，这就避免了多个goroutine同时读写一个map，可能导致的内存竞争。

#### 结论
在这个codewalk中我们探索了一个简单的程序，使用了Go的并发原语通过通信的方式共享内存。

这个codewalk对探索goroutine和channel可以用于编写清晰、准确的并发程序是一个开始探索。

```go
// Copyright 2010 The Go Authors. All rights reserved.
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file.

package main

import (
    "log"
    "net/http"
    "time"
)

const (
    numPollers     = 2                // number of Poller goroutines to launch
    pollInterval   = 60 * time.Second // how often to poll each URL
    statusInterval = 10 * time.Second // how often to log status to stdout
    errTimeout     = 10 * time.Second // back-off timeout on error
)

var urls = []string{
    "http://www.google.com/",
    "http://golang.org/",
    "http://blog.golang.org/",
}

// State represents the last-known state of a URL.
type State struct {
    url    string
    status string
}

// StateMonitor maintains a map that stores the state of the URLs being
// polled, and prints the current state every updateInterval nanoseconds.
// It returns a chan State to which resource state should be sent.
func StateMonitor(updateInterval time.Duration) chan<- State {
    updates := make(chan State)
    urlStatus := make(map[string]string)
    ticker := time.NewTicker(updateInterval)
    go func() {
        for {
            select {
            case <-ticker.C:
                logState(urlStatus)
            case s := <-updates:
                urlStatus[s.url] = s.status
            }
        }
    }()
    return updates
}

// logState prints a state map.
func logState(s map[string]string) {
    log.Println("Current state:")
    for k, v := range s {
        log.Printf(" %s %s", k, v)
    }
}

// Resource represents an HTTP URL to be polled by this program.
type Resource struct {
    url      string
    errCount int
}

// Poll executes an HTTP HEAD request for url
// and returns the HTTP status string or an error string.
func (r *Resource) Poll() string {
    resp, err := http.Head(r.url)
    if err != nil {
        log.Println("Error", r.url, err)
        r.errCount++
        return err.Error()
    }
    r.errCount = 0
    return resp.Status
}

// Sleep sleeps for an appropriate interval (dependent on error state)
// before sending the Resource to done.
func (r *Resource) Sleep(done chan<- *Resource) {
    time.Sleep(pollInterval + errTimeout*time.Duration(r.errCount))
    done <- r
}

func Poller(in <-chan *Resource, out chan<- *Resource, status chan<- State) {
    for r := range in {
        s := r.Poll()
        status <- State{r.url, s}
        out <- r
    }
}

func main() {
    // Create our input and output channels.
    pending, complete := make(chan *Resource), make(chan *Resource)

    // Launch the StateMonitor.
    status := StateMonitor(statusInterval)

    // Launch some Poller goroutines.
    for i := 0; i < numPollers; i++ {
        go Poller(pending, complete, status)
    }

    // Send some Resources to the pending queue.
    go func() {
        for _, url := range urls {
            pending <- &Resource{url: url}
        }
    }()

    for r := range complete {
        go r.Sleep(pending)
    }
}
```
