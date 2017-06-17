## [Go Concurrency Patterns: Pipelines and cancellation](https://blog.golang.org/pipelines)

13 March 2014 By Sameer Ajmani

### 简介
Go的并发原语对于构建流式数据处理流水线很容易，这样能够充分利用I/O和多核。这篇文章展示了流水线的例子，对于处理失败导致的异常分支特别进行了说明，介绍了干净处理异常的技术。

### What is a pipeline?
Go语言中没有对流水线正式的定义，流水线就是很多并发的程序。不严格的说，一个流水线由一系列的阶段通过channel连接，每个阶段都是一组执行相同函数的goroutine，这些goroutine：

* 从输入channel中接收上游的数据
* 对于接收的数据调用函数处理，通常会输出新的结果值
* 把结果发送到下游的channel中

每个阶段可以有任意数量的输入输出channel，第一个阶段和最后一个阶段例外，它们分别只有输入/输出channel，前者通常叫做源或者生产者，后者叫做汇集（sink）或者消费者。

我们通过一个简单的例子来解释关于流水线的概念和技术，然后我们会展示一个更具体的例子。

### Squaring numbers
考虑一个由三个阶段组成的流水线：

* 第一阶段：把一个整数列表转换为一个channel，就是向channel中逐个写入整数。`gen`函数创建一个goroutine向channel中发送整数，发送完成后关闭channel。
```golang
func gen(nums ...int) <-chan int {
    out := make(chan int)
    go func() {
        for _, n := range nums {
            out <- n
        }
        close(out)
    }()
    return out
}
```

* 第二阶段：从一个channel中接收整数，把整数平方写入另一个channel，并返回这个channel。当上游的channel关闭后，这个阶段的处理也就完成了，此时关闭输出的channel。
```golang
func sq(in <-chan int) <-chan int {
    out := make(chan int)
    go func() {
        for n := range in {
            out <- n * n
        }
        close(out)
    }()
    return out
}
```

* 第三阶段：`main`函数配置好整个流水线并执行最后一个阶段，从第二阶段返回的channel中读取数据并打印结果，直到channel关闭。因为`sq`函数的输入channel和输出channel的类型是相同的，我们可以对`sq`函数迭代任意次数。另外，`main`函数也可以像其他阶段一样通过`range loop`实现。
```golang
func main() {
    // Set up the pipeline.
    c := gen(2, 3)
    out := sq(c)

    // Consume the output.
    fmt.Println(<-out) // 4
    fmt.Println(<-out) // 9
}

func main() {
    // Set up the pipeline and consume the output.
    for n := range sq(sq(gen(2, 3))) {
        fmt.Println(n) // 16 then 81
    }
}
```

### Fan-out, fan-in
* 扇出：很多个函数从一个channel中读取数据直到channel关闭。扇出提供了一种向一组worker分发任务从而并行使用CPU和I/O的方法。
* 扇入：一个函数从多个channel中读取输入，直到所有的channel被关闭。扇入就是把多个输入channel多路复用到一个channel中，当所有的输入channel关闭时，输出channel也关闭。

我们可以把前面的流水线改为两个`sq`实例，它们都从相同的输入channel中读取。同时，我们引入一个新函数`merge`，用于扇入两个`sq`的结果。`merge`函数把一个channel列表转换为一个channel，对于输入的每个channel创建一个goroutine，从输入channel中读取数据写入单独的输出channel。当所有的`output`goroutine启动以后，`merge`还会创建一个goroutine，它等待所有的输入channel关闭以后关闭输出channel。向一个被关闭的channel中写数据会导致panic，所以在关闭输出channel之前需要确保所有的发送都已经完成了，`sync.WaitGroup`类型对于这种同步问题提供了简单的实现。
```golang
func main() {
    in := gen(2, 3)

    // Distribute the sq work across two goroutines that both read from in.
    c1 := sq(in)
    c2 := sq(in)

    // Consume the merged output from c1 and c2.
    for n := range merge(c1, c2) {
        fmt.Println(n) // 4 then 9, or 9 then 4
    }
}

func merge(cs ...<-chan int) <-chan int {
    var wg sync.WaitGroup
    out := make(chan int)

    // Start an output goroutine for each input channel in cs.  output
    // copies values from c to out until c is closed, then calls wg.Done.
    output := func(c <-chan int) {
        for n := range c {
            out <- n
        }
        wg.Done()
    }
    wg.Add(len(cs))
    for _, c := range cs {
        go output(c)
    }

    // Start a goroutine to close out once all the output goroutines are
    // done.  This must start after the wg.Add call.
    go func() {
        wg.Wait()
        close(out)
    }()
    return out
}
```

### Stopping short
我们流水线中的函数模式如下：

* 当所有的发送操作都完成以后，关闭输出channel
* 持续从输入channel中接收数据，直到输入channel被关闭

这个模式使得接收阶段可以用`range`循环实现，并且可以确保当所有的数据都发送到下游以后，goroutine能够马上退出。（译者注：输入channel被关闭以后，`range`循环会结束，goroutine就退出了。）

但是在真实的流水线中，接收阶段可能不接收输入channel中的全部数据，比如一个场景：接收者只需要上游数据的一个子集就可以继续处理，另一个更常见的场景是当接收者从channel中读取到一个错误的数据时，接收阶段就要提前退出。不管是哪个场景，接收者都不会等待上游后续的数据，我们希望能够提前终止接收者处理上游的数据。

在我们流水线的例子中，如果一个阶段没有完全接收上游的数据，上游发送数据的goroutine就会永远阻塞不能退出。（译者注：channel没有buffer，下游提前退出了，不从channel中读取数据，上游写channel就会阻塞。）

```golang
func main() {
    in := gen(2, 3)

    // Distribute the sq work across two goroutines that both read from in.
    c1 := sq(in)
    c2 := sq(in)

    // Consume the first value from output.
    out := merge(c1, c2)
    fmt.Println(<-out) // 4 or 9
    return
    // Since we didn't receive the second value from out,
    // one of the output goroutines is hung attempting to send it.
}
```

**这是一种资源泄漏：goroutine会消耗内存和运行时资源，goroutine栈中引用的堆资源不会被垃圾回收。goroutine本身也不会被垃圾回收，必须自己退出。**

我们需要重新设计一下流水线中，当下游goroutine不从channel中接收数据时，上游goroutine也能退出。一种方法是给channel增加buffer，带buffer的channel可以接收固定数量的值，如果buffer足够，写channel就不会阻塞。
```golang
c := make(chan int, 2) // buffer size 2
c <- 1  // succeeds immediately
c <- 2  // succeeds immediately
c <- 3  // blocks until another goroutine does <-c and receives 1
```

当创建channel时能够获得上游发送数据的数量，那么带buffer的channel是最简单的修复方法。例如：我们重写`gen`函数，把整数列表拷贝到带buffer的channel中，（译者注：因为channel的buffer足够，写channel一定不会阻塞，）所以不需要再创建一个新gouroutine。
```golang
func gen(nums ...int) <-chan int {
    out := make(chan int, len(nums))
    for _, n := range nums {
        out <- n
    }
    close(out)
    return out
}
```

我们向`merge`函数返回的输出channel增加长度为1的buffer，这样修复了goroutine阻塞的问题，但是不是最佳的方法。因为`out` channel的buffer长度取1是依赖于已知`merge`函数从上游接收的数据数量的前提下。如果我们向上游`gen`多输入一个值，或者下游阶段少读取一些值，还是会导致goroutine阻塞。所以，我们需要提供一种方法使得下游能够把“自己停止接收数据”的信息告诉上游。
（译者注：从最上游看，`gen(2, 3)`产生的源数据是2个，从最下游看，`fmt.Println(<-out)`只读取了一个数据，所以`out`channel要增加一个长度的buffer，`merge`函数向`out`中写2个数据，一个被`fmt.Println(<-out)`读走，另一个写入到buffer中，所以不会阻塞。如果`gen`输入的数据增加，或者`main`中少读取，都会因为生产数据量>消费数据量+buffer量导致写`out`阻塞。）
```golang
func merge(cs ...<-chan int) <-chan int {
    var wg sync.WaitGroup
    out := make(chan int, 1) // enough space for the unread inputs
    // ... the rest is unchanged ...
```

### Explicit cancellation
当`main`函数不从`out`中读取全部的数据就退出时，它必须告诉所有上游的goroutine丢弃它们即将发送的值。具体的实现方法是`main`向一个`done`channel中发送两个值，因为最多可能有两个worker在阻塞等待`out`channel可写。
```golang
func main() {
    in := gen(2, 3)

    // Distribute the sq work across two goroutines that both read from in.
    c1 := sq(in)
    c2 := sq(in)

    // Consume the first value from output.
    done := make(chan struct{}, 2)
    out := merge(done, c1, c2)
    fmt.Println(<-out) // 4 or 9

    // Tell the remaining senders we're leaving.
    done <- struct{}{}
    done <- struct{}{}
}
```

写`out`的上游goroutine用`select`语句替换直接写channel，这样可以同时处理`out`可写和`done`可读两个事件。`done`channel的类型是空结构体，因为channel传递的值的内容是无关紧要的，下游`done`channel可读这个事件告诉上游丢弃掉所有往下游发送的数据。`output`goroutine仍然是循环读取上游的channel`c`，所以上游通过`c`发送数据不会阻塞。

（译者注：`main`函数写一次`done`就可以了，因为`fmt.Println(<-out)`读取了一个数据。）
```golang
func merge(done <-chan struct{}, cs ...<-chan int) <-chan int {
    var wg sync.WaitGroup
    out := make(chan int)

    // Start an output goroutine for each input channel in cs.  output
    // copies values from c to out until c is closed or it receives a value
    // from done, then output calls wg.Done.
    output := func(c <-chan int) {
        for n := range c {
            select {
            case out <- n:
            case <-done:
            }
        }
        wg.Done()
    }
    // ... the rest is unchanged ...

// output伪代码
func output(c <-chan int) {
    for n := range c {
        for true {
            if recv from done:
                drop n
                break
            if send n to out:
                break
        }
    }
}
```

上面的方法有个问题：下游接收者需要知道上游可能阻塞的发送者数量。记录这个数量很麻烦并且容易出错。

我们需要一种方法告诉所有未知数量的goroutine停止向下游发送数据。Go语言通过关闭channel实现，如果一个channel已经关闭，那么从这个channel读取时会立即返回，读取的值是channel传递的数据类型的零值。

这个方法意味着`main`函数可以通过关闭`done`channel来解除所有阻塞的goroutine。换言之，关闭channel是一种向所有发送者高效广播的方法。我们向流水线各个阶段的函数增加一个`done`参数，并且在`main`函数中通过`defer`语句关闭channel，这样当`main`函数返回时会通知所有的流水线阶段退出。

现在流水线的每个阶段都能提前返回，当关闭`done`channel时`sq`可以在循环结束前返回。`sq`通过`defer`语句可以在任意分支返回都能关闭`out`channel。
```golang
func main() {
    // Set up a done channel that's shared by the whole pipeline,
    // and close that channel when this pipeline exits, as a signal
    // for all the goroutines we started to exit.
    done := make(chan struct{})
    defer close(done)

    in := gen(done, 2, 3)

    // Distribute the sq work across two goroutines that both read from in.
    c1 := sq(done, in)
    c2 := sq(done, in)

    // Consume the first value from output.
    out := merge(done, c1, c2)
    fmt.Println(<-out) // 4 or 9

    // done will be closed by the deferred call.
}

func sq(done <-chan struct{}, in <-chan int) <-chan int {
    out := make(chan int)
    go func() {
        defer close(out)
        for n := range in {
            select {
            case out <- n * n:
            case <-done:
                return
            }
        }
    }()
    return out
}
```

**流水线构建的指导原则**

* 当上游阶段所有数据发送完成以后，关闭和下游阶段通信的channel
* 从输入channel中循环读取数据，直到输入channel关闭或者输出channel可写
* 当接收者可能不再从channle中接收数据时，通过使用带buffer的channel或者显式给发送者发送信号，避免发送者阻塞

### Digesting a tree
让我们考虑一个更现实的流水线例子。MD5是一种消息摘要算法，通常用于获取文件的校验和。命令行工具`md5sum`可以打印一系列文件的摘要值。
```
% md5sum *.go
d47c2bbc28298ca9befdfbc5d3aa4e65  bounded.go
ee869afd31f83cbb2d10ee81b2b831dc  parallel.go
b88175e65fdcbc01ac08aaf1fd9b5e96  serial.go
```

我们的例子和`md5sum`类似，接收目录作为参数，打印这个目录所有文件的摘要值，并按照文件路径排序。
```
% go run serial.go .
d47c2bbc28298ca9befdfbc5d3aa4e65  bounded.go
ee869afd31f83cbb2d10ee81b2b831dc  parallel.go
b88175e65fdcbc01ac08aaf1fd9b5e96  serial.go
```

我们程序的`main`函数调用`MD5All`函数，它返回一个文件路径到摘要值的map，然后按照文件路径排序并输出摘要值。
```golang
func main() {
    // Calculate the MD5 sum of all files under the specified directory,
    // then print the results sorted by path name.
    m, err := MD5All(os.Args[1])
    if err != nil {
        fmt.Println(err)
        return
    }
    var paths []string
    for path := range m {
        paths = append(paths, path)
    }
    sort.Strings(paths)
    for _, path := range paths {
        fmt.Printf("%x  %s\n", m[path], path)
    }
}
```

`MD5All`函数是我们讨论的焦点。`serial.go`的实现没有使用并发，只是顺序遍历目录树，简单的读取文件计算摘要。
```golang
// MD5All reads all the files in the file tree rooted at root and returns a map
// from file path to the MD5 sum of the file's contents.  If the directory walk
// fails or any read operation fails, MD5All returns an error.
func MD5All(root string) (map[string][md5.Size]byte, error) {
    m := make(map[string][md5.Size]byte)
    err := filepath.Walk(root, func(path string, info os.FileInfo, err error) error {
        if err != nil {
            return err
        }
        if info.IsDir() {
            return nil
        }
        data, err := ioutil.ReadFile(path)
        if err != nil {
            return err
        }
        m[path] = md5.Sum(data)
        return nil
    })
    if err != nil {
        return nil, err
    }
    return m, nil
}
```

### Parallel digestion
`parallel.go`把`MD5All`分成两个阶段的流水线

* 第一阶段：`sumFiles`遍历目录树，创建一个新的goroutine计算文件摘要，把类型为`result`的结果通过channel返回
```golang
type result struct {
    path string
    sum  [md5.Size]byte
    err  error
}
```

`sumFiles`返回两个channel：`c`用于传递`result`，`errc`用于传递`filepath.Walk`的错误。Walk函数创建一个goroutine处理每个文件，然后检查如果`done`已经关闭，Walk函数立即返回。
```golang
func sumFiles(done <-chan struct{}, root string) (<-chan result, <-chan error) {
    // For each regular file, start a goroutine that sums the file and sends
    // the result on c.  Send the result of the walk on errc.
    c := make(chan result)
    errc := make(chan error, 1)
    go func() {
        var wg sync.WaitGroup
        err := filepath.Walk(root, func(path string, info os.FileInfo, err error) error {
            if err != nil {
                return err
            }
            if info.IsDir() {
                return nil
            }
            wg.Add(1)
            go func() {
                data, err := ioutil.ReadFile(path)
                select {
                case c <- result{path, md5.Sum(data), err}:
                case <-done:
                }
                wg.Done()
            }()
            // Abort the walk if done is closed.
            select {
            case <-done:
                return errors.New("walk canceled")
            default:
                return nil
            }
        })
        // Walk has returned, so all calls to wg.Add are done.  Start a
        // goroutine to close c once all the sends are done.
        go func() {
            wg.Wait()
            close(c)
        }()
        // No select needed here, since errc is buffered.
        errc <- err
    }()
    return c, errc
}
```

* 第二阶段：`MD5All`从`c`中接收消息，如果遇到错误就立即返回，通过`defer`关闭`done`。
```golang
func MD5All(root string) (map[string][md5.Size]byte, error) {
    // MD5All closes the done channel when it returns; it may do so before
    // receiving all the values from c and errc.
    done := make(chan struct{})
    defer close(done)

    c, errc := sumFiles(done, root)

    m := make(map[string][md5.Size]byte)
    for r := range c {
        if r.err != nil {
            return nil, r.err
        }
        m[r.path] = r.sum
    }
    if err := <-errc; err != nil {
        return nil, err
    }
    return m, nil
}
```

### Bounded parallelism
`parallel.go`实现的`Md5All`是为每个文件创建一个goroutine，如果一个目录有很多大文件，会导致程序分配的内存超过机器可用范围。

我们通过控制并行读取文件的最大数量来限制内存的分配。`bounded.go`中我们创建固定数量的goroutine读取文件，于是我们的流水线增加为三个阶段：遍历目录树、读取文件并计算摘要、收集摘要。

* 第一阶段：`walkFiles`，发送目录树中的文件路径。
```golang
func walkFiles(done <-chan struct{}, root string) (<-chan string, <-chan error) {
    paths := make(chan string)
    errc := make(chan error, 1)
    go func() {
        // Close the paths channel after Walk returns.
        defer close(paths)
        // No select needed for this send, since errc is buffered.
        errc <- filepath.Walk(root, func(path string, info os.FileInfo, err error) error {
            if err != nil {
                return err
            }
            if info.IsDir() {
                return nil
            }
            select {
            case paths <- path:
            case <-done:
                return errors.New("walk canceled")
            }
            return nil
        })
    }()
    return paths, errc
}
```

* 第二阶段：启动固定数量的`digester`goroutine，从`paths`中接收文件名，然后把计算后的摘要结果通过`c`发送。

和`parallal.go`不同，`digester`不能关闭输出channel，因为同时有多个`digester`goroutine写一个共享的channel。因此需要在`MD5All`中等待所有的`digester`goroutine完成后再关闭`c`。

当然我们也可以每个`digester`创建并返回一个channel（译者注：这样每个`digester`完成以后就可以把自己的输出channel关闭），但是这样我们就需要额外的goroutine扇入这些channel。
```golang
func digester(done <-chan struct{}, paths <-chan string, c chan<- result) {
    for path := range paths {
        data, err := ioutil.ReadFile(path)
        select {
        case c <- result{path, md5.Sum(data), err}:
        case <-done:
            return
        }
    }
}

func MD5All(root string) (map[string][md5.Size]byte, error) {
    // Start a fixed number of goroutines to read and digest files.
    c := make(chan result)
    var wg sync.WaitGroup
    const numDigesters = 20
    wg.Add(numDigesters)
    for i := 0; i < numDigesters; i++ {
        go func() {
            digester(done, paths, c)
            wg.Done()
        }()
    }
    go func() {
        wg.Wait()
        close(c)
    }()

    m := make(map[string][md5.Size]byte)
    for r := range c {
        if r.err != nil {
            return nil, r.err
        }
        m[r.path] = r.sum
    }
    // Check whether the Walk failed.
    if err := <-errc; err != nil {
        return nil, err
    }
    return m, nil
}
```

* 最后一个阶段：从`c`中接收所有的`result`，然后通过`errc`检查错误。必须先读取`c`再读取`errc`，因为`paths <- path`如果阻塞，`filepath.Walk`就不会返回，`errc <- filepath.Walk`就不会写到`errc`中，那么读`errc`就会阻塞。（译者注：如果先读取`c`直到它被close，说明所有的`digester`goroutine都退出了，而`digester`退出就表示`paths`被close了，说明`filepath.Walk`完成了遍历所有文件。）

### 结论
这篇文章展示了Go语言中构建流式数据处理流水线的技术。在这些流水线中处理错误是很棘手的，因为流水线的每个阶段都可能在写下游的channel时阻塞，下游的阶段可能不关心上游发送的数据。我们展示了如何通过关闭一个channel的方法向所有goroutine广播完成信号，除此之外，我们还对正确的构建流水线程序定义了指导原则。

更多阅读：

* [Go Concurrency Patterns](http://talks.golang.org/2012/concurrency.slide#1)([视频](https://www.youtube.com/watch?v=f6kdp27TYZs))展示了Go并发原语的基础内容以及使用方法
* [Advanced Go Concurrency Patterns](http://blog.golang.org/advanced-go-concurrency-patterns)([视频](http://www.youtube.com/watch?v=QDDwwePbDtw))讨论了更复杂的Go原语使用，特别是`select`
* Douglas McIlroy的论文[Squinting at Power Series](http://swtch.com/~rsc/thread/squint.pdf)展示了类似Go语言的并发模式是如何优雅支持复杂计算