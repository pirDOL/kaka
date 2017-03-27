## [Share Memory By Communicating](https://blog.golang.org/share-memory-by-communicating)

13 July 2010 By Andrew Gerrand

传统的线程模型（例如Java、C++和Python程序）需要程序员自己通过共享内存实现线程之间通信。通常，共享的数据结构需要锁保护，抢到锁的线程才能访问数据。此外，使用线程安全的数据结构，例如Python中的Queue可以简化线程之间的通信。

Go的并发原语（goroutine和channel）提供了并发程序的一种独特的、优雅的实现方式。goroutine和channel的概念其源自从C. A. R. Hoare的[Communicating Sequential Processes](http://www.usingcsp.com/)开始的[一段有趣的历史](http://swtch.com/~rsc/thread/)。Go鼓励使用channel在goroutine之间传递数据的引用，以此来避免显式使用锁来协调共享数据的访问。这个方法确保某个时刻只有一个goroutine能够访问数据。[Effective Go](http://golang.org/doc/effective_go.html)（所有Go程序员的必读）中这样总结Go的并发编程概念：
>不要使用共享内存实现通信，而是使用通信实现共享内存。
>Do not communicate by sharing memory; instead, share memory by communicating.

考虑一个对URL列表轮询的程序。传统的多线程环境中实现的数据结构以及轮询函数（可能被多个不同的线程同时执行）如下，轮询函数中还没写轮询的逻辑就已经大约占了一页纸，事实上轮询的逻辑可能只有几行，况且下面的代码还没有优雅的处理获取不到URL资源的情况。
>Consider a program that polls a list of URLs.

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
