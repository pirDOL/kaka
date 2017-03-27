## [Death of goroutines under control](https://blog.labix.org/2011/10/09/death-of-goroutines-under-control)

毫无疑问，Go语言吸引人的地方就是它一流的并发部分，例如channel、goroutine以及合适的调度策略等特性不仅是Go语言与生俱来的，而且通过一种优雅的方式集成起来。
>Certainly one of the reasons why many people are attracted to the Go language is its first-class concurrency aspects. Features like communication channels, lightweight processes (goroutines), and proper scheduling of these are not only native to the language but are integrated in a tasteful manner.

如果你关注Go社区的交流一段时间，你有很大概率听到有些人自豪的提到这个原则：不要通过共享内存通信，相反，通过通信共享内存。[这篇博客](http://blog.golang.org/2010/07/share-memory-by-communicating.html)详细讨论了这个原则，并且提供了一个有关这个原则的[代码解读](https://blog.labix.org/2011/10/09/death-of-goroutines-under-control)。
>and also a code walk covering it

Go语言的并发模型很容易理解，但是使用这种并发模型解决实际问题使得算法的设计会和常规方法有很大不同，这不是一个好消息。这篇博客中我想讨论一个开放的话题：后台goroutine的终止，这个话题和Go的并发编程模型密切相关。

下面通过一个有一定功能的简单goroutine来作为例子：这个gorontine通过一个channel发送读取到的文本行。`LineReader`类型有两个成员：channel用于客户端从中读取文本行，bufio.Reader作为内部的缓冲区，实现高效率的生产文本行。于是，下面的函数初始化一个reader，开始循环读取文本并返回，这个逻辑很容易理解。
```go
type LineReader struct {
        Ch chan string
        r  *bufio.Reader
}

func NewLineReader(r io.Reader) *LineReader {
        lr := &LineReader{
                Ch: make(chan string),
                r:  bufio.NewReader(r),
        }
        go lr.loop()
        return lr
}
```

现在，我们先看下循环体：循环中首先从buffer中读取一行文本，如果遇到错误就关闭channel并终止循环，否则通过channel把文本发送给客户端，如果客户端正在处理其他任务，那么发送可能会阻塞。这些对于Go开发者来说都是很合理和熟悉的。
```go
func (lr *LineReader) loop() {
        for {
                line, err := lr.r.ReadSlice('\n')
                if err != nil {
                        close(lr.Ch)
                        return
                }
                lr.Ch <- string(line)
        }
}
```

然而，终止循环的逻辑有两点细节值得讨论：首先，错误信息被丢弃了；其次，没有办法从循环外部优雅的终止循环。当然，错误信息可以简单的记录到日志中，但是如果想要把日志存储到数据库中或者发送到远端，甚至是根据错误的类型进行处理？另外，干净的终止循环在很多场景下也是一个很有用的特性，例如在单测中执行上面的逻辑。

（译者注：这里需要解释一下细节一和goroutine终止的关系，如果把错误简单的记录在日志中，那么在loop函数return之前打印一条日志就行了。但是如果想写入到数据库、发送到远端甚至是直接处理错误，就需要把goroutine的错误返回给父goroutine，然而，显然loop函数是通过go lr.loop()调用的，loop是在后台goroutine中执行的，父goroutine拿不到loop返回的错误。）

这里并不是说上面的两点细节很难以实现，而是说至今没有一种约定俗成的方法能够简单、有效的处理这个问题，甚至将来也不可能有。[tomb包](http://gopkg.in/tomb.v2)是目前Go语言中对这个问题的一个尝试。
>The claim is not that this is something difficult to do, but rather that there isn’t today an idiom for handling these aspects in a simple and consistent way. Or maybe there wasn’t. 

tomb的模型很简单：Tomb对象可以跟踪并记录一个或多个goroutine的状态：活跃、将要死亡、已经死亡，以及死亡原因。为了进一步理解这个模型，让我们把这个模型应用到LineReader例子中：
1. 首先，创建LineReader的代码需要修改一下，引入Tomb对象：修改后的代码和之前差别不大，struct中增加一个新字段tomb，并且goroutine的创建被委托给tomb对象。
2. 其次，修改loop函数实现返回error并且外部中断循环，修改后的loop循环有几点很有趣的地方：首先loop函数和Go语言中常规的函数一样，能够返回一个error，之前实现中被丢弃的error现在能被loop函数返回给调用者，调用者就可以知道goroutine异常终止的原因；另外，修改了向channel发送文本行的代码，当goroutine因为某些原因死亡时，不会阻塞在写channel上。
3. 最后，新增了Stop方法用于显式的从loop循环外部干净的终止goroutine。
```go
type LineReader struct {
        Ch chan string
        r  *bufio.Reader
        t  tomb.Tomb
}

func NewLineReader(r io.Reader) *LineReader {
        lr := &LineReader{
                Ch: make(chan string),
                r:  bufio.NewReader(r),
        }
        lr.t.Go(lr.loop)
        return lr
}

func (lr *LineReader) loop() error {
        for {
                line, err := lr.r.ReadSlice('n')
                if err != nil {
                        close(lr.Ch)
                        return err
                }
                select {
                case lr.Ch <- string(line):
                case <-lr.t.Dying():
                        close(lr.Ch)
                        return nil
                }
        }
}

func (lr *LineReader) Stop() error {
        lr.t.Kill(nil)
        return lr.t.Wait()
}
```

Tomb的Dying和Dead方法会分别返回一个channel，当Tomb的状态转换到某个状态时，对应的channel会被关闭，可以显式的阻塞在这些channel上等待相应的状态，也可以通过select语句实现非阻塞的等待。

上面的例子中使用了非阻塞方式。Kill方法可以在goroutine外部把对应的tomb设置为“即将死亡”状态，然后Wait方法会阻塞等待goroutine返回，即goroutine自己终止。如果goroutine已经死亡或者由于内部错误正在异常退出，Wait方法也能正确执行，**only the first call to Kill with an actual error is recorded as the cause for the goroutine death**。kill方法接收的nil参数是使得当goroutine正常退出时，Wait方法返回nil，和Go语言返回error惯例保持一致。
>In this case the Kill method will put the tomb in a dying state from outside the running goroutine, and Wait will block until the goroutine terminates itself by returning. This procedure behaves correctly even if the goroutine was already dead or in a dying state due to internal errors, because only the first call to Kill with an actual error is recorded as the cause for the goroutine death. 

这就是tomb包的完整用法例子，当我初次接触Go语言时，我以为如果想拿出一个优雅地道的方式解决“goroutine终止”这个问题，可能需要语言层面的更多支持，例如像[Erlang](http://www.erlang.org/doc/reference_manual/processes.html)对goroutine的状态进行跟踪。但是，了解到tomb包以后，我意识到这个问题其实只需要对Go语言现有的特性重新组织一下就可以解决了。
>When I started developing in Go I wondered if coming up with a good convention for this sort of problem would require more support from the language, such as some kind of goroutine state tracking in a similar way to what Erlang does with its lightweight processes, but it turns out this is mostly a matter of organizing the workflow with existing building blocks.

tomb包以及它的Tomb类型是对goroutine的终止一种含义清晰的实现，tomb这种实现是受现有的方法启发。如果想要使用它，通过go get安装：
```
$ go get gopkg.in/tomb.v2
```

源码和文档以及更多的细节也请参考[go get中的链接](https://gopkg.in/tomb.v2)

快乐编码！