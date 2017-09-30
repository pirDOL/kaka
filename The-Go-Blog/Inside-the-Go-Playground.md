## [Inside the Go Playground](https://blog.golang.org/inside-the-go-playgroud)

12 December 2013 By Andrew Gerrand

### TLDR
本文介绍了Go语言官网首页通过浏览器执行Go代码功能的实现细节。关键技术是时间、文件系统和网络栈的模拟。

时间模拟：goroutine调用sleep以后，后台有一个goroutine管理，调度并唤醒定时器到达的goroutine。runtime修改了内部时钟让定时器提前到达，这样内部时钟如何再调整回真实的时间？调快了时间以后，通过浏览器慢放按照正确的时间速率输出。

### 简介
2010年9月，我们[介绍了Go Playground](https://blog.golang.org/introducing-go-playground)，它是一个web服务，可以编译执行任意的Go代码，并返回程序的输出。

如果你是一位Go程序员，那你很可能已经通过直接使用[Go Playground](https://play.golang.org/)、阅读[Go Tour](https://tour.golang.org/)教程或执行Go文档中的[示例程序](https://golang.org/pkg/strings/#pkg-examples)等方式使用过Go Playground了。

你还可以通过点击[talks.golang.org](https://talks.golang.org/)上幻灯片中的Run 按钮或某篇博客上的程序（比如[最近一篇关于字符串的blog](https://blog.golang.org/strings)）使用Go Playground。

本文我们将学习Go playground是如何实现并与其它服务整合的。其实现涉及到一个不同的操作系统和运行时环境，这里我们假设你熟悉使用Go语言进行系统编程。

### 概览
![](Inside-the-Go-Playground/overview.png)

playground服务有三部分：

* 一个运行于Google服务器上的后端。它接收RPC请求，使用gc工具编译用户程序并执行，将程序的输出（或编译错误）作为RPC响应返回。
* 一个运行在[Google App Engine](https://cloud.google.com/appengine/docs/go/)上的前端。它接收来自客户端的HTTP请求并生成相应的RPC请求到后端。它也做一些缓存。
* 一个JavaScript客户端实现的用户界面，并向前端发送HTTP请求。

### 后端
后端程序本身很简单，所以这里我们不讨论它的实现。有趣的部分是我们如何在一个安全环境下安全地执行用户的任意代码，同时还提供如时间、网络及文件系统等的核心功能。

为了将用户程序和Google的基础设施隔离，后端在[原生客户端NaCl](https://developers.google.com/native-client/)中运行用户程序，原生客户端（NaCl）技术由Google开发，允许x86程序在web浏览器中安全执行。后端使用特殊版gc工具编译生成NaCl可执行文件。这个特殊的工具已经合并到Go 1.3中。想了解更多请阅读[设计文档](https://golang.org/s/go13nacl)。

NaCl会限制程序的CPU和RAM使用量，此外还会阻止程序访问网络和文件系统。然而这会导致一个问题，并发和网络访问是Go的关键优势之一，此外访问文件系统对于许多程序也是至关重要的。我们需要通过时间才展现Go高效的并发性能，另外显然展示网络和文件系统的功能不能访问网络和文件系统也是不行的。

尽管现在这些功能都被支持了，但是2010年发布的第一版playground都不支持这些功能。2009年11月10日支持获取当前时间，但是`time.Sleep`还是不能使用的，而且`os`和`net`有关的包中的大部分方法都被去掉了，调用时会返回`EINVALID`错误。

一年前我们在playground上面实现了一个[伪时间](https://groups.google.com/d/msg/golang-nuts/JBsCrDEVyVE/30MaQsiQcWoJ)，这才使得程序的休眠能够正确表现。最近playground的更新引入了伪网络和伪文件系统，这使得playground的工具链与正常的Go工具链更接近。下面会详细介绍这些新引入的功能。

### 伪时间
playground里面的程序可用CPU时间和内存都是有限的。除此以外程序实际使用时间也是有限制的。这是因为每个运行在playground的程序都消耗着后端资源，客户端和后端之间所有的状态都需要基础设施来维护（译者注：例如网络链路、session存储等）。限制每个程序的运行时间让我们的服务行为更加可预测，而且可以保护我们免受拒绝服务攻击。 

但是当程序使用时间功能函数的时候，这些限制将变得非常不合适。[Go Concurrency Patterns](https://talks.golang.org/2012/concurrency.slide)中通过一个例子来演示并发，它使用了时间功能函数比如[time.Sleep](https://golang.org/pkg/time/#Sleep)和[time.After](https://golang.org/pkg/time/#After)。当运行在早期版本的playground中时，这些程序的休眠是没有效果的而且行为很奇怪（有时甚至出现错误）。

通过使用一个聪明的把戏，我们可以使得Go程序认为它是在休眠，而实际上这个休眠没有花费任何时间。在解释它之前，我们需要了解调度程序是如何管理休眠的goroutine。

当一个goroutine调用time.Sleep（或者其他相似函数），调度器会在挂起的计时器堆中添加一个新的计时器，并让goroutine休眠。在这期间，由一个特殊的定时器goroutine管理这个堆。当这个定时器goroutine开始工作时，它告诉调度器当堆中的下一个挂起的计时器计时到达时的时候唤醒自己，然后定时器goroutine开始休眠。当它被唤醒时，首先去检查哪个计时器超时了，并唤醒相应的goroutine，然后又回到休眠状态。

明白了这个原理后，模拟时间的把戏只是改变唤醒定时器管理的goroutine的条件。正常情况下调度器是经过一段时间后进行唤醒，我们把调度器唤醒定时器管理goroutine的条件改为等待死锁（所有的goroutine都阻塞）。

playground版本的runtime维护着一个内部时钟。当修改后的调度器检测到一个死锁，那么它将检查是否有挂起的计时器。如果有的话它会将内部时钟的时间调整到使得计时器到达的最早的时间，然后唤醒定时器管理的goroutine，由它来唤醒调用sleep的goroutine继续执行，这样用户程序就认为时间过去了，而实际上休眠是瞬间完成了。

这些调度器的改变细节详见[proc.c](https://golang.org/cl/73110043)和[time.goc](https://golang.org/cl/73110043)。

伪时间解决了后台资源耗尽的问题，但是程序的输出该怎么办呢？如果一个程序调用了sleep，输出是正确的但是却没有消耗任何时间，这个现象看起来就很奇怪（译者注：就如同拨快了时间齿轮一样）。下面的程序每秒输出当前时间，持续三秒后退出，试着运行一下它。
```golang
func main() {
    stop := time.After(3 * time.Second)
    tick := time.NewTicker(1 * time.Second)
    defer tick.Stop()
    for {
        select {
        case <-tick.C:
            fmt.Println(time.Now())
        case <-stop:
            return
        }
    }
}
```

这是如何做到的? 这其实是后台、前端和客户端合作的结果。当程序每次向标准输出和标准错误输出时，我们会把这个事件捕获起来，并把程序锁认为事件发生的时间（译者注：因为runtime拨快了时间齿轮）和输出的内容一起提供给客户端。然后客户端再以正确的时间间隔输出，所以这个输出就像是本地程序输出的一样。

playground的runtime包提供了一个在每个写入数据之前引入一个小“回放头”的特殊函数[write](https://github.com/golang/go/blob/go1.3/src/pkg/runtime/sys_nacl_amd64p32.s#L54)，回放头中包含：一个magic strig、当前时间（译者注：指的是程序认为的，大端序，纳秒级时间戳，0x1174efede6b32a00->1257894001000000000->2009-11-10 23:00:01 +0000 UTC）、数据长度。一个带有回放头的写操作结构如下：
```
0 0 P B <8-byte time> <4-byte data length> <data>
```

上面例子的写操作原始输出（带回放头）如下：
```
\x00\x00PB\x11\x74\xef\xed\xe6\xb3\x2a\x00\x00\x00\x00\x1e2009-11-10 23:00:01 +0000 UTC
\x00\x00PB\x11\x74\xef\xee\x22\x4d\xf4\x00\x00\x00\x00\x1e2009-11-10 23:00:02 +0000 UTC
\x00\x00PB\x11\x74\xef\xee\x5d\xe8\xbe\x00\x00\x00\x00\x1e2009-11-10 23:00:03 +0000 UTC
```

前端将这些输出解析为一系列事件并返回给客户端一个事件列表的JSON对象：
```json
{
    "Errors": "",
    "Events": [
        {
            "Delay": 1000000000,
            "Message": "2009-11-10 23:00:01 +0000 UTC\n"
        },
        {
            "Delay": 1000000000,
            "Message": "2009-11-10 23:00:02 +0000 UTC\n"
        },
        {
            "Delay": 1000000000,
            "Message": "2009-11-10 23:00:03 +0000 UTC\n"
        }
    ]
}
```
JavaScript客户端（在用户的Web浏览器中运行的）然后使用提供的延迟间隔回放这个事件。对用户来说看起来程序是在实时运行。

### 伪文件系统
用Go的NaCl工具链构建的程序是不能访问本地文件系统的。为了解决这个问题，syscall包中相关的文件访问的函数（Open, Read, Write等）都是操作在一个内存文件系统上的。这个内存文件系统是由syscall包自身实现的。既然syscall包是Go代码与操作系统内核间的一个接口，那么用户程序会将这个伪文件系统当作真实的文件系统一样看待。

下面的示例程序将数据写入一个文件，让后复制内容到标准输出。试着运行一下（你也可以进行编辑）：
```golang
func main() {
    const filename = "/tmp/file.txt"

    err := ioutil.WriteFile(filename, []byte("Hello, file system\n"), 0644)
    if err != nil {
        log.Fatal(err)
    }

    b, err := ioutil.ReadFile(filename)
    if err != nil {
        log.Fatal(err)
    }

    fmt.Printf("%s", b)
}
```

当一个进程启动时，这个伪文件系统会被添加/dev目录下的一些设备以及一个空目录/tmp。那么程序可以对这个文件系统和平常一样进行操作，但是进程退出后，所有对文件系统的改变将会丢失。

伪文件系统初始化的时候会解压一个zip文件（详见[unzip_nacl.go](https://code.google.com/r/rsc-go13nacl/source/browse/src/pkg/syscall/unzip_nacl.go)），迄今为止这个机制只会在进行标准库测试的时候通过解压缩工具来提供测试数据。今后我们打算为playground的伪文件系统提供更多的初始化文件，这些文件可以同于运行文档示例、阅览博客以及Go Tour所需的数据。

具体实现详见[fs_nacl.go](https://code.google.com/r/rsc-go13nacl/source/browse/src/pkg/syscall/fs_nacl.go)和[fd_nacl.go](https://code.google.com/r/rsc-go13nacl/source/browse/src/pkg/syscall/fd_nacl.go)，这些文件后缀都是_nacl的，所以只有当GOOS被设置为nacl时候，这些文件才会被编译到syscall包中。

这个伪文件系统实现的数据结构为[fsysstruct](https://code.google.com/r/rsc-go13nacl/source/browse/src/pkg/syscall/fs_nacl.go?r=5317d308abe4078f68aecc14fd5fb95303d62a06#25)，它是一个全局单例（变量名为fs），在包初始化的时候被创建。各种和文件有关的函数都对fs操作，而不进行真实的系统调用。例如，[syscall.Open](https://code.google.com/r/rsc-go13nacl/source/browse/src/pkg/syscall/fs_nacl.go?r=1f01be1a1dc2#467)函数：
```golang
func Open(path string, openmode int, perm uint32) (fd int, err error) {
    fs.mu.Lock()
    defer fs.mu.Unlock()
    f, err := fs.open(path, openmode, perm&0777|S_IFREG)
    if err != nil {
        return -1, err
    }
    return newFD(f), nil
}
```

伪文件系统中所有的文件描述符被记录在变量名为[files](https://code.google.com/r/rsc-go13nacl/source/browse/src/pkg/syscall/fd_nacl.go?r=1f01be1a1dc2#16)的全局slice中。每个文件描述符对应一个[file](https://code.google.com/r/rsc-go13nacl/source/browse/src/pkg/syscall/fd_nacl.go?r=1f01be1a1dc2#22)，它实现了[fileImpl接口](https://code.google.com/r/rsc-go13nacl/source/browse/src/pkg/syscall/fd_nacl.go?r=1f01be1a1dc2#29)。下面是几个常见接口的实现：

* [fsysFile](https://code.google.com/r/rsc-go13nacl/source/browse/src/pkg/syscall/fs_nacl.go?r=1f01be1a1dc2#58)代表常规文件和设备（例如：/dev/random）
* 标准输入、输出和标准错误都是[naclFile](https://code.google.com/r/rsc-go13nacl/source/browse/src/pkg/syscall/fd_nacl.go?r=1f01be1a1dc2#209)的实例，这三个文件的系统调用会操作真实文件（这是playground中的程序唯一访问外部环境的途径）
* 网络套接字有着自己的实现，下面章节中会讨论。

### 伪网络
和文件系统一样，playground的网络协议栈是由syscall包在进程内部模拟的,它允许playground的项目使用127.0.0.1，请求其他主机会失败。

下面的程序是一个可执行的例子，这个程序首先会监听TCP的端口，接着等待连接的到来，然后将客户端发送的数据复制到标准输出，然后程序退出。在另外一个goroutine中，它会连接监听的端口后向连接里面写入数据以后关闭连接。
```golang
func main() {
    l, err := net.Listen("tcp", "127.0.0.1:4000")
    if err != nil {
        log.Fatal(err)
    }
    defer l.Close()

    go dial()

    c, err := l.Accept()
    if err != nil {
        log.Fatal(err)
    }
    defer c.Close()

    io.Copy(os.Stdout, c)
}

func dial() {
    c, err := net.Dial("tcp", "127.0.0.1:4000")
    if err != nil {
        log.Fatal(err)
    }
    defer c.Close()
    c.Write([]byte("Hello, network\n"))
}
```

网络的接口比文件要复杂的多，所以伪网络的实现会比伪文件系统的规模和复杂程度都要高。伪网络必须模拟读和写的超时以及不同网络地址类型和协议等等。

具体实现详见[net_nacl.go](https://code.google.com/r/rsc-go13nacl/source/browse/src/pkg/syscall/net_nacl.go?r=1f01be1a1dc2)。推荐从[netFile](https://code.google.com/r/rsc-go13nacl/source/browse/src/pkg/syscall/net_nacl.go?r=1f01be1a1dc2#419)开始阅读代码，因为这是网络套接字对于fileImpl接口的实现。

### 前端
playground的前端是另一个简单的程序（不到100行）。它接收客户端的HTTP请求，然后调用后端RPC接口，同时还会完成一些缓存工作。

前端提供一个HTTP接口：http://golang.org/compile，这个接口接受一个POST请求，请求body部分是要运行的Go程序代码，还支持一个可选的version字段（多数客户端的值为2）。

当前端收到一个HTTP编译请求的时候，它首先检查[memcache](https://developers.google.com/appengine/docs/memcache/)中是否有过同样源码的编译执行的结果。如果有就会把缓存的响应直接返回。缓存可以防止像Go主页上请求频率高的程序导致后端过载。如果缓存未命中，那么前端会向后端发送RPC请求，并把后端的响应写入缓存，最后解析回放事件，最后通过HTTP将JSON格式的对象返回到客户端（像上面描述那样）。

### 客户端
各种使用playground的站点，共享着一些同样的Javascript代码来搭建用户访问接口（代码窗口和输出窗口，运行按钮等等），通过这些接口来后playground前端交互。

具体实现在go.tool资源库的playground.js文件中，可以通过go.tools/godoc/static包来导入。 其中一些代码较为简洁，也有一些比较繁杂, 因为这是由几个不同的客户端代码合并出来的。

playground函数使用一些HTML元素，然后构成一个交互式的playground窗口小部件。如果你想将playground添加到你的站点的话，你就可以使用这些函数。 

Transport接口 (非正式的定义,  是JavaScript脚本)的设计是依据网站前端交互方式提。 HTTPTransport 是一个Transport的实现，可以发送如前描述的以HTTP为基础的协议。 SocketTransport 是另外一个实现，发送WebSocket (详见下面的'Playing offline')。

为了遵守同源策略，各种网站服务器（例如godoc）通过playground在http://golang.org/compile下的服务来完成代理请求。这个代理是通过共有的go.tools/playground包来完成的。

### 离线使用
[Go Tour](http://tour.golang.org/)和[Present Tool](http://godoc.org/code.google.com/p/go.talks/present)都可以离线运行。 这对于访问网络有限制的人或者是发布会上的演讲者无法连接到可用的互联网。

离线运行时playground后端的版本取决于本地构建的源码版本。此时后端使用的是常规Go工具链构建，这些工具没有上面提到的那些修改（译者注：也就是说能够操作真实的文件系统和网络系统），后端使用WebSocker来与客户端进行通信。

WebSocket的后端实现详见[go.tools/playground/socket包](http://godoc.org/code.google.com/p/go.tools/playground/socket)。在[Inside Present](http://talks.golang.org/2012/insidepresent.slide#1)的汇报中讨论了代码细节。

### 其他客户端
playground服务不单单只是为了给Go项目官方使用，[Go by Example](https://gobyexample.com/)就是另外一个例子。我们很高兴你能在你的网站使用该服务。我们唯一的要求就是[您事先和我们联系](golang-dev@googlegroups.com)，在您的请求中使用唯一User-Agent（这样我们可以确认您的身份），此外您提供的服务是有益于Go社区的。

### 结论
从godoc到Go Tour，再到这篇博客，playground已经成为Go文档系列中不可或缺的一部分了。随着最近的伪文件系统和伪网络堆栈的引入，我们将激动地完善我们的学习资料来覆盖这些新内容。 

但是最后，playground只是冰山一角，随着本地客户端（Native Client）将要支持Go1.3，我们期盼着社区做出更棒的功能。