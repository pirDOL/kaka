## [Errors are values](https://blog.golang.org/errors-are-values)

12 January 2015 By Rob Pike

## TLDR
DRY原则
```
type errWriter struct {  
    w   io.Writer  
    err error  
}
func (ew *errWriter) write(buf []byte) {  
    if ew.err != nil {  
        return 
    }  
    _, ew.err = ew.w.Write(buf)  
}
ew := &errWriter{w: fd}  
ew.write(p0[a:b])  
ew.write(p1[c:d])  
ew.write(p2[e:f])  
// and so on  
if ew.err != nil {  
    return ew.err  
}
```

## 正文
如何处理错误是Go程序员特别是初学者最常讨论的一个问题。讨论经常会随着下面这个程序片段出现的次数增多而变成抱怨。
```golang
if err != nil {
    return err
}
```

我们最近扫描了所有我们能够找到的开源项目，发现这段代码只是每页或者每两页出现了一次，比你想象中的要少很多。然而，如果你还是觉得必须到处写`if err != nil`，那一定是哪里出了问题，并且会认为是Go语言本身的问题。
 
上面的想法是错误的，但是很容易去纠正它。Go初学者通常会提问“（我的程序）如何处理错误？”，得到的回答就是使用`if err != nil`模式，然后就对这种设计模式浅尝辄止了。其他编程语言可以使用try-catch块或者其他类似原理的方式去处理错误。因此，程序员会想当我在别的语言里面使用try-catch的时候，Go语言只需要转换为`if err != nil`就行了。随着时间的推移，这样的片段会越来越多，结果就是感觉很糟糕。
 
抛开这些描述，很明显这些Go程序员忽略了关于错误的基本要点：错误也是值。 
值可以通过程序赋值，因为错误也是值，所以错误也可以通过程序赋值。

>Regardless of whether this explanation fits, it is clear that these Go programmers miss a fundamental point about errors: Errors are values.
>Values can be programmed, and since errors are values, errors can be programmed.

（译者注：this explanation fits是啥意思？）

一个最常见的语句就是测试一个错误值是否为空，但是还有很多其他使用错误值的方式，使用其中的某些东西可以使你的程序更好，可以很大程度上排除用固定模式的if语句去检查错误。
 
这里有一个bufio包[Scanner类型](http://golang.org/pkg/bufio/#Scanner)的简单示例。[Scan方法](http://golang.org/pkg/bufio/#Scanner.Scan)执行底层的I/O，显然底层I/O不可能没有错误。然而Scan方法不会返回错误，它返回一个boolean值。
同通过一个单独的方法在scan结束的时候运行，返回是否有错误发生。使用Scan方法的代码如下：
```golang
scanner := bufio.NewScanner(input)  
for scanner.Scan() {  
    token := scanner.Text()  
    // process token  
}  
if err := scanner.Err(); err != nil {  
    // process the error  
} 
```

上面的代码里确实有检测错误是否为空的语句，但是它只出现和执行了一次。
Scan方法本可以（但是没有）定义成这样`func (s *Scanner) Scan() (token []byte, error)`，然后用户可能会这样写代码：
```golang
scanner := bufio.NewScanner(input)  
for {  
    token, err := scanner.Scan()  
    if err != nil {  
        return err // or maybe break  
    }  
    // process token  
} 
```

上面这段代码和开始的代码没有明显的差别，但是还有一个很重要的区别。在这段代码里面，每次循环都要检测错误，但是真正的Scanner API把错误处理从关键的扫描API中抽象出来，迭代的时候值返回本次迭代的token。使用真实的API让代码感觉更自然：循环执行完再检测错误。错误处理不会覆盖程序流。
 
上面的代码背后实际发生了什么呢？当Scan遇到I/O错误时，它会记录下来并返回false。
一个独立的[Err方法](http://golang.org/pkg/bufio/#Scanner.Err)，在调用时会返回错误值。虽然Err方法看起来没啥特殊的地方，但是和在客户端代码到处写`if err != nil`并且在每次扫描返回时检测错误相比还是不同的。这就是使用错误值编程方法。这个方法和简单，。
>Simple programming, yes, but programming nonetheless.
 
这里有必要强调的是不论采用那种检查错误方式、不论错误如何被返回，都应该检测错误。这里的讨论的问题不是关于怎么样去避免错误检测，而是关于怎样用Go去优雅的处理错误。
 
我参加在东京的2014年秋GoCon时也遇到了重复的错误检测代码这一主题。一个Twitter名叫[jxck_](https://twitter.com/jxck_)的狂热gopher，对于重复的错误检测代码也深恶痛绝。他展示了一些代码，逻辑上和下面的代码类似：
```golang
_, err = fd.Write(p0[a:b])  
if err != nil {  
    return err  
}  
_, err = fd.Write(p1[c:d])  
if err != nil {  
    return err  
}  
_, err = fd.Write(p2[e:f])  
if err != nil {  
    return err  
}  
// and so on 
```

>The topic of repetitive error-checking code arose when I attended the autumn 2014 GoCon in Tokyo.

代码中有很多重复。真实的代码比上面的代码更长，并且包含其他的处理逻辑，所以仅仅是通过一个辅助函数来重构是不容易的。不过在理想情况下，使用一个闭包来传递错误变量将对消除重复代码有帮助：
```golang
var err error  
write := func(buf []byte) {  
    if err != nil {  
        return 
    }  
    _, err = w.Write(buf)  
}  
write(p0[a:b])  
write(p1[c:d])  
write(p2[e:f])  
// and so on  
if err != nil {  
    return err  
}
```

这种方式可以很好的工作，但是在每个write函数里面都要有一个闭包，（write闭包）是一个比较笨拙的辅助函数，因为err变量在write函数多次调用之间保持值。
 
通过借鉴上面Scan方法的思路，我们可以使它更干净、通用和可复用。我和@jxck_讨论了上面的方法，但是他不知道怎么去使用。因为语言交流有障碍，在一个长时间的交流之后，我问是否可以借他的笔记本电脑给我，然后给他展示一些代码。

我定义了一个叫errWriter的对象，代码如下：
```golang
type errWriter struct {  
    w   io.Writer  
    err error  
}
```

再给它定义一个write方法。它不需要符合标准的Write函数签名，因此我用小写字母开头突出这个区别。write方法内部调用底层Writer的Write方法，记录第一个遇到错误以备后面使用：
```golang
func (ew *errWriter) write(buf []byte) {  
    if ew.err != nil {  
        return 
    }  
    _, ew.err = ew.w.Write(buf)  
}
```

当错误发生以后，后面再调用write方法就什么也不干了，最后一次写操作的错误值保留了下来。基于errWriter类型和write方法，上面的代码可以被重构：
```golang
ew := &errWriter{w: fd}  
ew.write(p0[a:b])  
ew.write(p1[c:d])  
ew.write(p2[e:f])  
// and so on  
if ew.err != nil {  
    return ew.err  
}
```

上面的代码甚至和使用一个闭包相比都更干净，并且使得真实的写操作序列能在一个页面上展示出来。代码中没有杂乱的东西，用错误值（和接口）来编程使得代码更好。

在同一个包里面的某些片段代码可以借鉴这个方法的思想，甚至是直接使用errWriter。

另外，errWriter的存在可以做更多的事情，特别是不是人为的例子。它可以计算字节数，可以合并多个write调用原子的写到一个buffer，还有更多其他用处。

>Also, once errWriter exists, there's more it could do to help, especially in less artificial examples

事实上，这种模式在标准库里面出现了很多。[archive/zip](http://golang.org/pkg/archive/zip/)和[net/http](http://golang.org/pkg/net/http/)都使用了它。
更突出的点是，[bufio包的Writer方法](http://golang.org/pkg/bufio/)实际上就是errWriter思路的一个实现。尽管bufio.Writer.Write返回一个错误，这主要是因为[io.Writer接口](http://golang.org/pkg/io/#Writer)定义的原因。bufio.Writer的Write方法的行为正如我们上面的errWriter.write方法，仅有的区别就是它用Flush来报告错误，所以我们的例子可以这样写：
```golang
b := bufio.NewWriter(fd)  
b.Write(p0[a:b])  
b.Write(p1[c:d])  
b.Write(p2[e:f])  
// and so on  
if b.Flush() != nil {  
    return b.Flush()  
} 
```

>More salient to this discussion, ...

这种方法有个明显的缺点，至少对于某些应用是这样的：没有办法知道在错误发生之前到底有多少处理过程已经成功完成了。但是假如这个信息很重要，就要想一个能够获得这个细粒度信息的方法。然而通常在处理最后检查错误是足够的。
 
我们已经看了一个避免出现重复错误处理代码的技巧。记住errWriter或者bufio.Writer不是简化错误处理代码唯一方法，这种方法也不适用于所有情况。这篇博客最关键的一点是：错误就是值，Go语言完全有能力去处理它们。
 
使用这个语言去简化你的错误处理。 

但是请记住：无论你做什么，请总是要去检测错误。

最后，我和@jxck_交流的完整过程，包括他录制的一个小视频，请看[他的博客](http://jxck.hatenablog.com/entry/golang-error-handling-lesson-by-rob-pike)