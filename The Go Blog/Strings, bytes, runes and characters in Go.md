## [Strings, bytes, runes and characters in Go](https://blog.golang.org/strings)
23 October 2013
By Rob Pike

### 简介
[上一篇blog](http://blog.golang.org/slices)解释了Go的slice的工作原理，通过一系列的例子说明了它内部实现机制。在此基础上，这篇blog会讨论Go的string。尽管看起来，string作为博客的主题有点太简单了，但是如果想正确的使用它，需要了解它的内部实现以及byte、character和rune的区别，unicode和utf-8、string和string literal等等，还有更多微秒的区别。

我们从一个常见的问题来开始讨论本篇blog的主题：当我索引一个Go字符串的位置n时，为什么我得到的不是第n个字符？回答这个问题需要我们了解现实世界中文本是如何实现和工作的。

Joel Spolsky著名的blog[The Absolute Minimum Every Software Developer Absolutely, Positively Must Know About Unicode and Character Sets (No Excuses!)](http://www.joelonsoftware.com/articles/Unicode.html)是对上面的问题一个很好的介绍，本文也会对他的blog中的问题进行回答。

### string是什么？
我们先从最基础的开始。Go里面的string实际上就是一个只读的[]byte，如果你还不清楚什么是[]byte以及它如何工作，请阅读[上一篇blog](http://blog.golang.org/slices)，我们假定你已经了解了这些内容。

string保存了任意的字节，整个string可以表示unicode、utf-8或者任意格式的数据。下面只要涉及到string，就等效于[]byte。

下面是一个string literal（马上会详细介绍它），通过```\xNN```定义了一个保存特定字节值的字符串（显然byte的取值范围是00-FF）。

```go
const sample = "\xbd\xb2\x3d\xbc\x20\xe2\x8c\x98"
```

### 打印string

因为sample中的一些byte不是合法的ASCII，也不是合法的utf-8，所以之间打印这个字符串输出是乱码（乱码的内容取决于具体的系统环境）。

```
fmt.Println(sample)
��=� ⌘
```

为了知道sample中究竟保存了什么，我们需要把它分成字节，逐个打印出来。可以有多种方法实现，最明显的就是循环打印每个字节。前面的问题中曾经暗示过，索引一个string实际上是访问其中的字节，而不是字符，后面我们会详细讨论开始提出的问题。现在我们还是按照字节来分析sample。从循环打印每个字节的输出我们可以发现，每个字节和sample定义时的```\xNN```格式的值是匹配的。

当然还有更简单的方法输出一个直接打印时乱码的string：fmt.Printf("%x")，它会按照字节序列以16进制的方式输出string，每个字节两个字符。

在%和x之间可以使用空格，输出的结果没有%x那么难看（原文：a little less imposing）。

除此之外，%q可以对字节序列中不能打印的字节以16进制转义的方式输出。当一个string中大部分是可以打印的文本，然后有小部分是不能打印的，这样输出的内容更清晰。通过sample的输出我们可以发现，=和空格是两个可以打印的ASCII，还有一个瑞典字符⌘（它表示Place of Interest），这个字符的unicode编码是U+2318，表示成utf-8是e2 8c 98。

如果你对$q输出的奇怪的字符还是很困惑，我们可以用```%+q```方式输出，对于任何非ASCII字符都会进行转义，utf-8会被转义为格式为```\uNNNN```格式的unicode输出。

这些打印的方法对于调试string的内容是有帮助的，在接下来的讨论中也会使用上面的方法。这些方法对于打印[]byte也是有效的。下面就是打印方法的完整代码，点击右侧的run按钮可以在浏览器中运行。

```go
for i := 0; i < len(sample); i++ {
    fmt.Printf("%x ", sample[i])
}
bd b2 3d bc 20 e2 8c 98

fmt.Printf("%x\n", sample)
bdb23dbc20e28c98

fmt.Printf("% x\n", sample)
bd b2 3d bc 20 e2 8c 98

fmt.Printf("%q\n", sample)
"\xbd\xb2=\xbc ⌘"

fmt.Printf("%+q\n", sample)
"\xbd\xb2=\xbc \u2318"
```

练习：
1. 把sample修改为[]byte。提示：使用类型转换创建slice。
2. 用```%q```循环string的每个字节，输出内容说明了什么？

### utf-8和string literal
如我们所见，索引string返回byte而不是字符，因为string就是一组byte。使用string存储字符时，实际上是把字符编码对应的byte序列保存在string里面。请看下面的例子（原文：Let's look at a *more controlled example* to see how that happens.）。

这个小程序通过三种方法打印了一个string常量，这个string常量中保存了一个字符。第一种方法是直接作为普通字符串打印，第二种方法是只打印string中合法的ASCII（其他byte转义输出），第三种方法是以16进制输出每个字节。为了更清晰的说明问题，我们用反单引号定义一个raw string，这样是为了保证string中只包含文本字符。（用双引号定义string时可以包含转义字节序列。）

根据输出我们可以发现“Place of Interest”符号的unicode值为U+2318，对应的utf-8编码为e2 8c 98，打印出来显示为⌘。

如果你对utf-8很熟悉，那么上面的结果是很容易理解的，反之亦然。这里仍然有必要花一些篇幅解释一下utf-8表示的string是如何产生的。简而言之：string是在编写代码时创建的。

Go的源码约定采用utf-8编码，不允许其他的字符编码方式。这就意味着当我们写代码时，源码中的字符⌘，编辑器会把这个字符替换成对应的utf-8编码。当我们打印这个string的16进制字节时，实际上是把编辑器保存在源码文件中的真实数据打印出来。

简而言之，Go的源码是utf-8编码的，所有源码中的string literal会在文件保存时转换成utf-8编码。如果string literal不包含转义序列，例如raw string那样，那么实际保存在string中的就是引号（双引号或者反单引号）括起来的内容。因此raw string的实际字节永远都是它的内容的utf-8编码。类似的，对于一个常规的string literal（用双引号括起来），如果其中不包含转义序列，它的实际字节也是合法的utf-8编码。

有些人认为Go的string永远是utf-8，这是不对的：就像前面例子里面的那样，string可以保存任意的字节序列；另外，这节的例子中也说明了对于不包含转义字节的string literal，它永远是合法的utf-8字节序列。

总结一下，string可以包含任意的字节，string literal的字节几乎永远是utf-8。

```go
func main() {
    const placeOfInterest = `⌘`

    fmt.Printf("plain string: ")
    fmt.Printf("%s", placeOfInterest)
    fmt.Printf("\n")

    fmt.Printf("quoted string: ")
    fmt.Printf("%+q", placeOfInterest)
    fmt.Printf("\n")

    fmt.Printf("hex bytes: ")
    for i := 0; i < len(placeOfInterest); i++ {
        fmt.Printf("%x ", placeOfInterest[i])
    }
    fmt.Printf("\n")
}

plain string: ⌘
quoted string: "\u2318"
hex bytes: e2 8c 98
```

### code point、character、rune
目前我们对“字符”和“字节”的使用非常小心，这是因为string由byte组成，并且“字符”这个概念本身就很难定义。unicode标准中使用“code point”来表示一个编码所表示的符号。例如：code point U+2318，它的16进制值是0x2318，表示符号⌘。更多关于code point的内容请参考[unicode的网页](http://unicode.org/cldr/utility/character.jsp?a=2318)

举一个最常见的例子：code point U+0061是拉丁字母`A`的小写`a`。但是重音符标记的小写`à`如何表示？显然它也是个字符，有两种不同的code point表示它，一种code point是U+00E0，另一种是结合重音符的code point U+0300和小写`a`的code point U+0061，同样可以表示`à`。通常，一个字符可能被多种不同的code point序列来表示，对应的utf-8也是不同的。

因此计算机科学中“字符”这个概念是模糊的，所以我们很小心的使用它。为了使得编码具有一致性，“标准化”是一种用于确保一个字符永远能够表示为同一种code point，当然“标准化”不是这篇blog的主题，后面会有其他的blog解释Go的标准库是如何实现它的。

因为code point有点拗口，所以Go里面使用一个更短的rune来描述这个概念。在标准库和源码中你都能看到它，它和code point几乎表示的是相同的概念。Go中把rune定义为int32的别名，这样可以很容易的看出来一个整数值表示一个code point。同样，字符常量在Go里面叫做rune常量，例如`⌘`的类型和值分别为rune和0x2318。

总结一下：
* Go的源码是utf-8编码的
* string可以保存任意字符
* 字符串常量（string literal），除了用`\xNN`显式转义的字节以外，都是合法的utf-8
* unicode中的code point在Go中叫做rune
* Go不保证string中的字符是标准化的

### for-range
前面说了Go源码是utf-8编码的，Go在处理utf-8时有一个例外，就是for-range。

常规的循环输出的是string的字节内容，但是for-range循环会对utf-8编码的rune进行解码，返回的index是当前rune在string中的字节位置，返回的value是code point。下面的例子中使用了```%#U```格式化，同时输出code point的unicode值和可打印的字符，通过输出发现每个code point占用多个字节。

练习：在string中增加一个非utf-8的字节序列（使用`\xNN`转义），循环的输出是啥样的？

```go
const nihongo = "日\xff本語"
for index, runeValue := range nihongo {
    fmt.Printf("%#U starts at byte position %d\n", runeValue, index)
}

U+65E5 '日' starts at byte position 0
U+672C '本' starts at byte position 3
U+8A9E '語' starts at byte position 6
U+FFFD '�' starts at byte position 9
```

### 库
Go标准库提供了对utf-8的强大支持，当for-range不能满足需求时，可以使用标准库里面的包。
这些包里面最重要的就是unicode/utf8，它包含了对utf8字符串的验证、解码、编码操作。下面是一个和for-range等效的例子，使用了```DecodeRuneInString```函数实现相同的功能，这个函数的返回值是rune和utf-8编码的字节数。运行代码发现这个函数和for-range的输出是一样的，这是设计时保证的。

关于unicode/utf8包提供的其他方法，请阅读[文档](http://golang.org/pkg/unicode/utf8/)。

```go
 const nihongo = "日本語"
for i, w := 0, 0; i < len(nihongo); i += w {
    runeValue, width := utf8.DecodeRuneInString(nihongo[i:])
    fmt.Printf("%#U starts at byte position %d\n", runeValue, i)
    w = width
}

U+65E5 '日' starts at byte position 0
U+672C '本' starts at byte position 3
U+8A9E '語' starts at byte position 6
```

### 结论
这里回答一下开头提出的问题：string是由字节组成的，索引string返回的是字节位置，不是字符位置。string甚至可以不保存文本字符，事实上，“字符”本身就是一个模糊的概念，所以我们在定义string时没有说string是字符组成的，而是用了byte。

关于unicode、utf-8以及多语言可以有更多的内容值得讨论，留到其他的blog中。目前我们希望你能够理解Go里面的string是如何工作的，尽管string可以保存任意的byte，但是utf-8是string设计时主要针对的场景。
