## [Errors are values](https://blog.golang.org/errors-are-values)

12 January 2015 By Rob Pike

## TLDR
1. The key lesson, however, is that errors are values and the full power of the Go programming language is available for processing them.
1. clean code：代码整洁之道
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

我们最近扫描了所有我们能够找到的开源项目，发现这段代码只是每一、两页出现一次，比别人跟你描述情况的要少很多。然而如果你还是觉得要写很多`if err != nil`来处理错误，肯定是哪里出了问题，最明显的是Go语言本身设计的有问题（译者注：这句话是个反义表达，Go语言设计是没问题的，所以就不需要到处写`if err != nil`）。
 
如果你通过到处写`if err != nil`来处理错误是很悲催的编程实践，这种做法也会误导其他人，但是很容易去纠正它。Go初学者通常会提问“（我的程序）如何处理错误？”，得到的回答就是使用`if err != nil`模式，然后就对这种设计模式浅尝辄止了。其他编程语言可以使用try-catch块或者其他类似原理的方式去处理错误。因此，程序员会想当我在别的语言里面使用try-catch的时候，Go语言只需要转换为`if err != nil`就行了。随着时间的推移，这样的片段会越来越多，导致代码看起来很笨拙。
 
不管上面（对`if err != nil`误用场景）的描述是否真的符合实际情况，但是很明显这些Go程序员忽略了关于错误的基本要点：错误也是值。 
值是可编程的（译者注：可编程指的是可以对变量赋值、比较等），因为错误也是值，所以错误也是可编程的。

>Regardless of whether this explanation fits, it is clear that these Go programmers miss a fundamental point about errors: Errors are values.
>Values can be programmed, and since errors are values, errors can be programmed.

一个最常见的语句就是测试一个错误值是否为空，但是还有很多其他使用错误值的方法，使用其中的某些方法可以使你的程序更优雅，可以消除很多重复的样板代码——每个错误都生搬硬套的用`if err != nil`语句去检查。

>eliminating much of the boilerplate that arises if every error is checked with a rote if statement.
 
下面举一个bufio包[Scanner类型](http://golang.org/pkg/bufio/#Scanner)的例子。[Scan方法](http://golang.org/pkg/bufio/#Scanner.Scan)执行底层的I/O，显然底层I/O不可能没有错误。然而Scan方法不返回错误而是返回一个boolean值。
通过一个单独的方法在扫描结束时运行，判断是否有错误发生。使用Scan方法的代码如下：
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

上面的代码里确实有对错误进行空检查的语句，但是它只出现和执行了一次。
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

>and then the example user code might be (depending on how the token is retrieved),

上面的代码和开始的代码没有明显差别，但有一个很重要的区别：在这段代码里面，每次循环都要检查错误，但是真正的Scanner API（译者注：bufio包实际实现的Scan方法）把错误处理从关键的扫描API中抽象出来，扫描API只读取输入文本，循环返回分割后的字段。使用真正的API让用户代码感觉更自然：循环执行完再检测错误。错误处理不会掩盖程序关键执行流。

>In this code, the client must check for an error on every iteration, but in the real Scanner API, the error handling is abstracted away from the key API element, which is iterating over tokens. With the real API, the client's code therefore feels more natural: loop until done, then worry about errors. Error handling does not obscure the flow of control.
 
上面的代码背后实际发生了什么呢？当Scan遇到I/O错误时，它会记录下来并返回false。
一个独立的[Err方法](http://golang.org/pkg/bufio/#Scanner.Err)，在调用时会返回错误值。虽然Err方法看起来没啥特殊的地方，但它和在用户代码到处写`if err != nil`或者每次扫描返回时检测错误还是不同的。这就是使用错误值编程方法。这种方法是很简单的编程方法，是的，但是不知道咋翻译了。

>Simple programming, yes, but programming nonetheless.

有必要强调的是不论采用那种检查错误方式、不论错误如何被返回，都应该检测错误。这里讨论的问题不是怎么避免错误检测，而是关于怎样用Go去优雅的处理错误。
 
我参加东京2014年秋的GoCon时也遇到了重复的错误检测代码这个主题。一个Twitter ID为[jxck_](https://twitter.com/jxck_)的狂热gopher，对于重复的错误检测代码也深恶痛绝。他展示了一些代码，逻辑上像下面这样：
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
>It is very repetitive. In the real code, which was longer, there is more going on so it's not easy to just refactor this using a helper function, but in this idealized form, a function literal closing over the error variable would help:

代码中有很多重复。真实的代码比上面的代码更长，除了Write还包含其他的处理逻辑，所以没法仅仅通过一个辅助函数来重构。但是，在理想情况下（译者注：不考虑真实代码中除了Write以外的逻辑），使用一个闭包来传递错误变量有助于消除重复代码：
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

这种方式可以很好的工作，但是在每个write函数都是一个闭包。（如果不用闭包，而是）使用一个独立辅助函数实现，（如果你试一下就会知道）这种方法会比较笨拙，因为err变量需要在辅助函数多次调用之间传递。

>This pattern works well, but requires a closure in each function doing the writes; a separate helper function is clumsier to use because the err variable needs to be maintained across calls (try it).
 
通过借鉴上面Scan方法的思路，我们可以使代码更整洁、通用和可复用。我和@jxck_讨论了上面的方法，但是他不知道怎么去使用。因为语言交流有障碍，经过长时间交流，我问是否可以借他的笔记本电脑，然后给他展示一些代码。

我定义了一个叫errWriter的对象，代码如下：
```golang
type errWriter struct {  
    w   io.Writer  
    err error  
}
```

再给它定义一个write方法。它不需要符合标准的Write函数签名，因此我用小写字母开头突出这个区别。在write方法里面调用底层Writer的Write方法，记录第一个遇到错误以备后面使用：
```golang
func (ew *errWriter) write(buf []byte) {  
    if ew.err != nil {  
        return 
    }  
    _, ew.err = ew.w.Write(buf)  
}
```

当错误发生以后，后面再调用write方法就什么也不干了（直接返回），最后一次发生写错误的错误值保留了下来。基于errWriter类型和write方法，上面的代码可以被重构：
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

上面的代码甚至和使用闭包相比都更整洁，并且使得真实的写操作序列能在一个页面上展示出来。代码不再杂乱（核心逻辑和错误检查），用错误值（和接口）来编程使得代码更好。

在同一个包里面的某些代码片段也可以借鉴这个方法的思想，甚至是直接使用errWriter。

另外，errWriter的存在可以做更多的事情，特别实际中更常见的例子（译者注：artificial指的是前面write的例子是人为设计的例子？）。它可以计算字节数，可以合并多个write原子的写到一个buffer，还有更多其他用处。

>Also, once errWriter exists, there's more it could do to help, especially in less artificial examples

事实上，这种模式在标准库里面出现了很多。[archive/zip](http://golang.org/pkg/archive/zip/)和[net/http](http://golang.org/pkg/net/http/)都使用了它。
更突出的一点是，[bufio包的Writer方法](http://golang.org/pkg/bufio/)实际上就是errWriter思路的一个实现。尽管bufio.Writer.Write返回一个错误，这主要是因为[io.Writer接口](http://golang.org/pkg/io/#Writer)定义的原因。bufio.Writer的Write方法的行为正如我们上面的errWriter.write方法，仅有的区别就是它用Flush来报告错误，所以我们的例子可以这样写：
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

这种方法有个明显的缺点，至少对于某些应用是这样的：没有办法知道在错误发生之前到底有多少处理过程已经成功完成了。但是假如这个信息很重要，就要想一个能够获得这个细粒度信息的方法。然而通常在处理完成后检查一次错误，要么有要么没有，对于大多数应用来说是足够的。
 
我们已经看了一个避免出现重复错误处理代码的技巧。记住errWriter或者bufio.Writer不是简化错误处理代码唯一方法，这种方法也不适用于所有情况。这篇博客最关键的一点是：错误就是值，Go语言完全有能力去处理它们。
 
使用这个语言去简化你的错误处理。 

但是请记住：无论你做什么，请总是要去检测错误。

最后，我和@jxck_交流的完整过程，包括他录制的一个小视频，请看[他的博客](http://jxck.hatenablog.com/entry/golang-error-handling-lesson-by-rob-pike)