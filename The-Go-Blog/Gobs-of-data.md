## [Gobs of data](https://blog.golang.org/gobs-of-data)

24 March 2011 By Rob Pike

### TLDR
1. when to use

    >But for a Go-specific environment, such as communicating between two servers written in Go, there's an opportunity to build something much easier to use and possibly more efficient.

    >... gobs will never work as well with other languages, but that's OK: gobs are unashamedly Go-centric.

2. goals: gobs end up looking like a sort of generalized, simplified protocol buffer
    * easy to use: reflection, not IDL/protoc
    * efficiency: binary
    * self-describing

3. on giant shoulders: protocal buffer 
    * can't encode an integer or array at the top level
    * required field is costly to implement and brings maintenance problem
    * leave out default value, use Go's zero value instead

4. internal
    * This decoupling from the size of the variable gives some flexibility to the encoding: we can expand the type of the integer variable as the software evolves, but still be able to decode old data.
    * 

### 简介
为了让某个数据结构能够在网络上传输或能够保存至文件，它必须被编码然后再解码。当然，已经有许多可用的编码方式了：[JSON](http://www.json.org/)，[XML](http://www.w3.org/XML/)，Google的[protocol buffers](http://code.google.com/p/protobuf)等。而现在又多了一种，Go的[gob包](http://golang.org/pkg/encoding/gob/)提供的方式。

为什么定义新的编码？这要做许多的工作，而且这些工作可能是多余的。为什么不使用某个现成的格式？一方面我们确实是这样做的，Go已经有刚才提到的所有编码方式的[包](http://golang.org/pkg/)，[protocol buffer包](http://github.com/golang/protobuf)在另外一个代码库中，但它是下载得最多的包之一。在许多情况下，包括与其他语言编写的工具和系统交互，这些都是正确的选择。

但是在特定的Go环境中，例如在两个Go编写的服务之间通讯，提供了一个契机能够定义一种更易用、更高效的编码方式。

Gobs依赖Go语言才能工作，它不能处理那些外部定义的、语言无关的编码方式。另外，重新实现一种编码也提供了从现有编码中吸取经验并改进的机会。。

### 目标
gob包在设计时有许多目标。

首先，也是最显然的，它要容易使用的。首先，由于Go支持反射，所以没有必要弄一个单独的接口定义语言或协议编译器。数据结构本身提供了编码和解码所需要的全部信息。其次，这也意味着gob永远无法同其他语言协同工作，但这没问题：gob是厚颜无耻的以Go 为中心。

效率也是非常重要的，基于文本形式的编码，例如XML和JSON，应用于高效通讯网络会太慢了。二进制编码是必须的。

Gob流必须可以自解释。每个流只要从头开始完整读取，整个流包含足够的信息，以便在终端对其内容毫不知情的前提下对整个流加以解析。这一特性意味着即便你忘记了保存在文件中的gob流表示什么，也总是可以对其解码。

同样，这里有一些从Google protocol buffers获得的经验。

### Protocol buffer的不足
Protocol buffers对gob的设计产生了主要的影响，但是有三个特性被有意的避开了。暂且不说 protocol buffer不是自解释的：如果你不知道数据的定义，你就无法解析它。

首先，protocol buffer仅适用于Go的struct。不能在最顶层的message对一个整数或者数组编码，只可以把它作为struct的一个字段。这个限制至少对于Go没有什么意义。如果你希望传输的仅仅是一个数组或者整数，为什么你要先将其放到struct中？

其次，可能protocol buffer的定义指定字段T.x和T.y是必需的（required），无论是在编码还是解码时。虽然必需字段看起来是个好主意，但是给实现造成了比较大的开销：编解码器中必须维护一个特殊的数据结构，用于报告必需的字段是否丢失。必需字段同样也产生了代码问题。过一段时间后，某人可能希望修改数据定义，移除了必需字段，但这导致现有接收数据的客户端崩溃。最好是在编码时就根本没有这些字段。Protocol buffer也有可选字段。但是如果我们没有必须字段，那么所有的字段就是可选的。等一下还会针对可选字段进行一些讨论。
>It's better not to have them in the encoding at all. Protocol buffers also have optional fields. But if we don't have required fields, all fields are optional and that's that.

第三个protocol buffer的硬伤是默认值。当protocol buffer在某个字段上设置了默认值，而解码后的结构就像那个字段被设置了那个默认值一样。这个想法在有getter和setter控制字段的访问的时候非常棒，但是当message的容器是一个原始结构体的时候就很难控制其保持清晰了（译者注：如果有getter/setter，可以通过它们控制默认值，但是原始的结构体可以用点操作符访问成员，不容易实现默认值机制）。必需字段的默认值也存在同样的麻烦：在哪定义默认值，它们的类型是什么（是UTF-8文本？任意的二进制字节串？浮点用多少位表示？）。尽管默认值机制看起来很简单，protocol buffer 的设计和实现还是很复杂。我们决定让gob不支持默认值，我们基于Go语言的一个很不、平常并且效率高的默认规则：除非你给字段设置了值，否则就使用那个类型的零值，并且零值的字段不需要被传输。

所以gob最终看起来是个通用、简化版的protocol buffer。它又是如何工作的呢？

### 值
编码后的gob数据长得不像int8或者uint16那样的（二进制补码），编码后的数据看起来更象是Go的常量，不论是有符号还是无符号的整数，编码后的整数都是抽象的无大小限制的数值。当你编码一个int8时，其值被转换为一个无大小范围限制的变长整数。当你编码一个int64时，其值也被转换为一个无大小范围限制的变长整数。有符号和无符号编码时是区别对待的，但是无大小范围限制也适用于无符号值。如果int8回头int64编码的都是数值7，通过网络传输的比特流是相同的。接收者解码时将它放入接收者的变量中，可能是任意的整数类型。因此，编码方发送了一个来自int8编码的值7，而接收方可能将其保存在int64中。这没有问题：编码的值首先是一个整数，并且接收方的类型能够容纳解码后的值，如果类型不匹配，会产生错误。在变量的大小上解偶，为编码提供了一些灵活性：我们可以随着软件演化扩展整数类型，但是仍然可以解码旧的数据。

这种灵活性对于指针同样有效。在传输前，所有指针都进行整理。int8、*int8、**int8、\****int8等都被传输为可能被存储于任何大小的 int，或者 *int，或者 ******int等等的整数值。这同样是一种灵活性。

>Before transmission, all pointers are flattened. Values of type int8, *int8, **int8, \****int8, etc. are all transmitted as an integer value, which may then be stored in int of any size, or *int, or ******int, etc. Again, this allows for flexibility.

当解码一个struct时，只有编码方发送的字段才会存储到解码方的struct，这也是gobs的灵活性。考虑下面这个值：
```go
type T struct { X, Y, Z int } // 只有导出字段才会被编码和解码。
var t = T{X: 7, Y: 0, Z: 8}
```

t编码后仅发送7和8，值为0的Y字段不会被发送，因为没有必要发送一个零值。

接收方可能用下面的结构解码：
```go
type U struct { X, Y *int8 } // 注意：成员都是int8的指针
var u U
```

u的成员只有X被赋值，X的值为7的int8变量的地址，Z字段被忽略了（如果不忽略它，你应将其放到U结构体的哪个字段呢？）。解码struct时按照名字和类型匹配，只有编码方和解码方都有的字段才会受到影响。这个简单的办法巧妙处理了可选字段的问题：类型T添加了字段，没有升级协议的接收者仍然能处理它们知道的那部分字段。因此gob在可选字段上提供了很重要的特性——可扩展性，无须任何额外的机制或标识。

通过整数的编码方式可以进一步构建其他类型：字节数组、字符串、数组、slice、map、甚至浮点数。浮点数按照IEEE 754浮点位定义，然后按照整数存储。只要你知道整数存储的类型就能正确的解码，我们总是知道类型。另外，整数使用大端字节序发送，因为一般的浮点数字，就像是值很小的整数数组，在低位上有许多个零是不用传递的。

gob还有一个非常棒的特性是Go允许用户通过[GobEncoder](http://golang.org/pkg/encoding/gob/#GobEncoder)和[GobDecoder](http://golang.org/pkg/encoding/gob/#GobDecoder)接口对自定义类型进行编解码，类似于[JSON包](http://golang.org/pkg/encoding/json/)的[Marshaler](http://golang.org/pkg/encoding/json/#Marshaler)和[Unmarshaler](http://golang.org/pkg/encoding/json/#Unmarshaler)以及[fmt包](http://golang.org/pkg/fmt/)的[Stringer接口](http://golang.org/pkg/fmt/#Stringer)。这个技巧使得你可以表示特殊功能、强制对编码和解码进行约束，或者传输数据的时候隐藏一些信息。阅读[文档](http://golang.org/pkg/encoding/gob/)了解更多细节。

### 类型的传输（Types on the wire）

在第一次传输给定类型的时候，gob包会把这个类型的描述序列化后一起传输。实际上，gob把编码器按照gob标准格式编码后作为类型的描述，编码器是gob内部的一个struct，它包含类型描述以及标识这个类型的唯一编号。（基本类型、类型描述结构的内存结构是在启动时已经定义好了。原文：by the software for bootstrapping。）在类型被描述后，它可以通过编号来引用。

>In fact, what happens is that the encoder is used to encode, in the standard gob encoding format, an internal struct that describes the type and gives it a unique number

因此，当我们第一次发送类型T时，gob编码器发送T的类型描述，并给这个类型一个编号，例如127。包括第一个数据包在内的所有的数据都用这个编号作为前缀，所以一系列T类型的数据流看起来是这样：
```
("define type id" 127, definition of type T)(127, T value)(127, T value), ...
```

类型编号可以实现递归类型的描述以及发送。因此，gob可以对树类型做编码：
```golang
type Node struct {
    Value int
    Left, Right *Node
}
```

这个例子可以作为读者的练习：研究“默认值为零值”规则是如何工作的，gob不会传输指针本身的值。

类型信息使得gob序列化后的字节流是自描述的，except for the set of bootstrap types, which is a well-defined starting point.

### 编译机（Compiling a machine）

在第一次传输给定类型的时候，gob包会构造一个针对这个类型的小翻译机。构造它使用了对所传输类型的反射，一旦翻译机构建完成就不再依赖反射。这个翻译机使用了unsafe和其他一些trick的机制提高编码的速度。理论上是可以使用反射来代替unsafe，但是编码速度会明显变慢。（受gob实现的影响，Go的protocol buffer使用了类似的机制提高速度。）而后的同样类型的值使用已经编译好的翻译机，所以它们也能被正确的编码。

更新：Go1.4中gob包不再使用unsafe，所以性能有一点但是不明显的降低。

解码和编码类似，但是略微复杂。当你解码一个数据，gob包用一个`[]byte`保存编码器实际发送类型以及解码时向解码器传入的类型（译者注：编码发送的类型和解码时承接的类型可以不同，下面一节的例子中编码器实际发送的类型是结构体`P`，解码器传入的承接解码后数据的类型是`Q`）。gob包构造一个翻译机进行映射：把发送端的gob类型和接收端承接解码后的类型做映射。一旦翻译机构造完成就不再使用反射机制了，另外解码也使用了unsafe方法加快解码速度。

### 使用
在gob的表面之下还有很多秘密，但是gob包带来的结果是一个用于数据传输的高效的、容易使用的编码系统。这里有一个完整的例子演示了不同类型的编码和解码。留意发送和接收数据是多么简单；你所需要做的一切，就是将值和变量置入[gob包](http://golang.org/pkg/encoding/gob/)，然后它会完成所有的工作。
```go
package main
 
import (
    "bytes"
    "fmt"
    "gob"
    "log"
)
 
type P struct {
    X, Y, Z int
    Name string
}
 
type Q struct {
    X, Y *int32
    Name string
}
 
func main() {
    // 初始化编码器和解码器。通常 enc 和 dec 会绑定到网络连接，而编码器和解码器会运行在不同的进程中。
    var network bytes.Buffer //代替网络连接
    enc := gob.NewEncoder(&network) // 将会写入网络
    dec := gob.NewDecoder(&network) // 将会从网络中读取
    // 编码（发送）
    err := enc.Encode(P{3, 4, 5, "Pythagoras"})
    if err != nil {
        log.Fatal("encode error:", err)
    }
    // 解码（接收）
    var q Q
    err = dec.Decode(&q)
    if err != nil {
        log.Fatal("decode error:", err)
    }
    fmt.Printf("%q: {%d,%d}\n", q.Name, *q.X, *q.Y)
}
```

你可以复制代码到[Go Playground](http://play.golang.org/p/_-OJV-rwMq)，编译并执行这个例子。

[rpc包](http://golang.org/pkg/net/rpc/)是基于gob实现，当跨网络调用方法时通过gob自动编码/解码，具体的内容在另一篇博客中讨论。

### 细节
[gob包文档](http://golang.org/pkg/encoding/gob/)，尤其是[doc.go](http://golang.org/src/pkg/encoding/gob/doc.go)详细展开了本文所说的许多细节，并且包含了完整的可运行的例子，展示了编码器如何表示结构体。如果你对gob 的实现感兴趣，这是个不错的起点。