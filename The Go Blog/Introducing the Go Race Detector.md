## [Introducing the Go Race Detector](https://blog.golang.org/race-detector)
26 June 2013

### 简介

[竞态条件](http://en.wikipedia.org/wiki/Race_condition)是程序错误中隐藏最深、最难以理解（insidious and elusive）的一类。它们通常会导致不稳定、不容易理解的错误，即使代码已经被部署到生产环境并且运行了很长时间。尽管Go的并发机制降低了编写正确的并发代码的难度，但是仍然无法避免静态条件。小心编程、勤勉思考和测试是必需的，另外还有一些可以帮助的工具。

我们很高兴的表示Go1.1中引入了[竞态条件检测器](http://golang.org/doc/articles/race_detector.html)，它是一个查找Go代码中的竞态条件的新工具，当前对于64位x86处理器上的Linux系统、OS X以及Windows系统都支持这个工具。

竞态条件检测器是基于C/C++的[运行时线程检查库](https://code.google.com/p/thread-sanitizer/)实现，这个库在Google内部已经检查出来很多的错误，还包括[Chromium浏览器项目](http://www.chromium.org/)。在2012年9月，这个库被集成到Go中，从那时起，已经检查出来标准库中的[42个竞态条件](https://code.google.com/p/go/issues/list?can=1&q=ThreadSanitizer)。现在它是我们持续构建过程中的一部分，一旦有竞态条件出现，它就能马上捕捉。

### 工作原理
竞态条件检查器集成在Go的工具链中，当命令行中设置了-race标志时，编译器会采集所有的内存访问，记录内存访问的时间和方法，运行时库会对未同步的共享对象的访问进行监控。当检测到竞态行为时，会打印出警告信息。关于这个算法详细内容请参考[这篇文章](https://code.google.com/p/thread-sanitizer/wiki/Algorithm)。

由于设计的原因，竞态条件检查器只能在代码运行时发生竞态条件时才能检测到，这就意味着需要对接收真实负载的二进制程序开启-race选项。这样做的代价是CPU和内存的使用增加了10倍，所以一直开启竞态条件检查是不显示的。一种折衷的办法是在测试时开启，例如性能测试和集成测试，因为这些测试中会运行程序中并发部分的代码。另一种方法是在生产环境中部署一个开启了-race条件的实例，其他的服务实例不开启。

### 使用竞态条件检测器
这个工具是集成在Go的工具链中的，编译代码时增加-race参数开启竞态条件检查即可。下面go get中提供了一个例子，你可以体验竞态条件检查器的使用。
```go
$ go test -race mypkg    // test the package
$ go run -race mysrc.go  // compile and run the program
$ go build -race mycmd   // build the command
$ go install -race mypkg // install the package

$ go get -race golang.org/x/blog/support/racy
$ racy
```

### 案例
下面是两个被竞态条件检查器捕捉到的真实案例。

#### Timer.Reset
第一个案例是一个竞态条件检查器发现的真实bug的简化版本代码，代码中使用一个定时器，随机延时0-1秒后打印一个消息，重复这个操作持续5秒。使用[time.AfterFunc](http://golang.org/pkg/time/#AfterFunc)创建一个[Timer](http://golang.org/pkg/time/#Timer)打印第一条消息，然后使用[Reset](http://golang.org/pkg/time/#Timer.Reset)方法调度下一个消息，这样可以重用定时器。

上面的代码看起来是符合逻辑的，但是在某些特定的场合下，代码会奇怪的失败。

到底发生了什么？开启竞态条件检查器运行程序可以得到一些启示。竞态条件检查器指出了问题所在：对于变量t在不同的goroutine中发生了不同步的读写。如果randomDuration()初始化的定时间隔很短，time.AfterFunc()第二个参数定义的函数会先于main goroutine返回，这就意味着t.Reset()在t被赋值之前执行，此时t还是一个nil。

修复这个竞态条件的方法是只从main goroutine中读写变量t。main goroutine全权负责设置和复位定时器t，增加的channel可以实现向main goroutine线程安全的传递复位定时器的请求。更简单但效率略低的方法是[不重用定时器](http://play.golang.org/p/kuWTrY0pS4)。

```go
11 func main() {
12     start := time.Now()
13     var t *time.Timer
14     t = time.AfterFunc(randomDuration(), func() {
15         fmt.Println(time.Now().Sub(start))
16         t.Reset(randomDuration())
17     })
18     time.Sleep(5 * time.Second)
19 }
20 
21 func randomDuration() time.Duration {
22     return time.Duration(rand.Int63n(1e9))
23 }

panic: runtime error: invalid memory address or nil pointer dereference
[signal 0xb code=0x1 addr=0x8 pc=0x41e38a]

goroutine 4 [running]:
time.stopTimer(0x8, 0x12fe6b35d9472d96)
    src/pkg/runtime/ztime_linux_amd64.c:35 +0x25
time.(*Timer).Reset(0x0, 0x4e5904f, 0x1)
    src/pkg/time/sleep.go:81 +0x42
main.func·001()
    race.go:14 +0xe3
created by time.goFunc
    src/pkg/time/sleep.go:122 +0x48

==================
WARNING: DATA RACE
Read by goroutine 5:
  main.func·001()
     race.go:14 +0x169

Previous write by goroutine 1:
  main.main()
      race.go:15 +0x174

Goroutine 5 (running) created at:
  time.goFunc()
      src/pkg/time/sleep.go:122 +0x56
  timerproc()
     src/pkg/runtime/ztime_linux_amd64.c:181 +0x189
==================

11 func main() {
12     start := time.Now()
13     reset := make(chan bool)
14     var t *time.Timer
15     t = time.AfterFunc(randomDuration(), func() {
16         fmt.Println(time.Now().Sub(start))
17         reset <- true
18     })
19     for time.Since(start) < 5*time.Second {
20         <-reset
21         t.Reset(randomDuration())
22     }
23 }
```

#### ioutil.Discard

第二个例子更微秒。ioutil包的[Discard](http://golang.org/pkg/io/ioutil/#Discard)对象实现了[io.Writer](http://golang.org/pkg/io/#Writer)，实现把所有写入其中的数据丢弃。就好像/dev/null一样：它在你需要读取数据但又不想保存时使用，例如配合[io.Copy](http://golang.org/pkg/io/#Copy)排空一个reader。

在2011年7月时，Go开发组就意识到像上面这样使用Discard效率很低：Copy函数每次调用时会分配一个32kB的内部buffer，在使用Discard时，这个buffer就是不必要的，因为我们并不像保存读到的数据。Discard理想的设计和使用不应该有这么大的开销。

当时修复的方法很简单，如果writer实现了一个ReadFrom方法，io.Copy时会调用write的ReadFrom方法。我们给Discard实现了[ReadFrom](https://code.google.com/p/go/source/detail?r=13faa632ba3a#)方法，内部的buffer是所有Discard对象共享的，我们当时知道这里理论上是一个竞态条件，但是因为所有写入到buffer中的数据都应该丢弃，所以我们忽略了这个竞态条件。

当竞态条件检查器被引入Go中时，它马上[把Discard的ReadFrom代码标记出来](https://code.google.com/p/go/issues/detail?id=3970)。我们再次考虑了这段代码可能存在的问题，最终决定这个竞态条件并不是真实存在的。为了消除这个竞态条件的报警，我们实现了一个[非竞态的版本](https://code.google.com/p/go/source/detail?r=1e55cf10aa4f)，这个版本只用于开启了竞态条件检查器时使用。

但是一个月以后，[Brad](http://bradfitz.com/)遇到了[一个令人沮丧并且奇怪的bug](https://code.google.com/p/go/issues/detail?id=4589)。通过几天的追查，他把问题定位到一个由ioutil.Discard导致的竞态条件上。

下面就是io/util中有竞态条件的代码，devNull是Discard的底层数据结构实现，所有的Discard对象共享一个buffer，即blackHole。

Brad的程序实现了一个trackDigestReader类型，封装了io.Reader和读取到的数据的哈希摘要。例如：可以在读取一个文件的同时计算SHA-1摘要。但是在一些情况下，可能不需要保存读取到的文件数据，只需要计算文件的哈希，所以writer可以是一个ioutil.Discard。但是在这种情况下，blackHole就不再仅仅是一个黑洞了，从io.Reader中读取到的数据在写入到hash.Hash之前会暂时保存在这里面。如果多个goroutine同时计算文件的哈希，因为ioutil.Discard共享一个blackHole，竞态条件导致了在读文件和计算哈希之间，blackHole中的数据被写坏。这个问题不会导致error和panic发生，但是计算出来的哈希值是错的，太恶心了。

上面的bug通过给每个ioutil.Discard一个buffer来[修复](https://code.google.com/p/go/source/detail?r=4b61f121966b)，消除了共享buffer中的竞态条件。

```go
io.Copy(ioutil.Discard, reader)

io.Copy(writer, reader)

writer.ReadFrom(reader)

var blackHole [4096]byte // shared buffer

func (devNull) ReadFrom(r io.Reader) (n int64, err error) {
    readSize := 0
    for {
        readSize, err = r.Read(blackHole[:])
        n += int64(readSize)
        if err != nil {
            if err == io.EOF {
                return n, nil
            }
            return
        }
    }
}

type trackDigestReader struct {
    r io.Reader
    h hash.Hash
}

func (t trackDigestReader) Read(p []byte) (n int, err error) {
    n, err = t.r.Read(p)
    t.h.Write(p[:n])
    return
}

tdr := trackDigestReader{r: file, h: sha1.New()}
io.Copy(writer, tdr)
fmt.Printf("File hash: %x", tdr.h.Sum(nil))

io.Copy(ioutil.Discard, tdr)

func (t trackDigestReader) Read(p []byte) (n int, err error) {
    // the buffer p is blackHole
    n, err = t.r.Read(p)
    // p may be corrupted by another goroutine here,
    // between the Read above and the Write below
    t.h.Write(p[:n])
    return
}
```

### 结论
竞态条件检查器是一个强大的工具，可以对并发程序的正确性进行检查。它不会误报，所以对于它的警告要严肃对待。但是它的运行结果是取决于你的测试条件的，必须保证你的代码在测试时构造了完整的并发场景，这样竞态条件检查器才能发挥它的功能。

你还在等等什么？马上在你的代码上运行`go test -race`吧！

By Dmitry Vyukov and Andrew Gerrand