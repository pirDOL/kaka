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