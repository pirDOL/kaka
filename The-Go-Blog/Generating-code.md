## [Generating code](https://blog.golang.org/generate)

### TLDR
1. why
    
    Go tool gets all necessary build information from the Go source, ... There is simply no mechanism to run Yacc from the go tool alone.

2. what

    `go generate` works by scanning for special comments in Go source code that identify general commands to run. It's important to understand that go generate is not part of go build. It contains no dependency analysis and must be run explicitly before running go build. It is intended to be used by the author of the Go package, not its clients.

3. how
    * step1: install **generator exe** that really generates code, eg. goyacc generates \*.go from *.y
    * step2: write meta file with **go:generate comment**, eg. \*.y
    * step3: run go generate command that outputs \*.go for go build
```
#step1
go get golang.org/x/tools/cmd/goyacc

#step2 gopher.y
//go:generate goyacc -o gopher.go -p parser gopher.y
...

#step3
go generate
go build
```

4. golang.org/x/tools/stringer
    
    It automatically writes string methods for sets of integer constants.

22 December 2014 By Rob Pike

图灵机的特性之一是图灵完整性，它是指通过计算机程序能够编写计算机程序。尽管这个想法很伟大，并且实际中也有很多实践的例子，但是却没有得到大众足够的欣赏。例如这个想法是编译器定义的很大一部分内容，另外它还是`go test`命令工作的原理：`go test`扫描被测试的包，然后生成一个Go程序，这个程序中包含为这个包定制的测试框架，然后编译运行这个程序实现对这个包的测试。现代的计算机运算速度足够快，生成Go程序听起来开销很大的操作实际上用不了1秒就能完成。

>This is a powerful idea that is not appreciated as often as it might be, even though it happens frequently. ..., writes out a Go program containing a test harness customized for the package

译者注：test harness的[维基百科解释](https://en.wikipedia.org/wiki/Test_harness)
>In software testing, a test harness or automated test framework is a collection of software and test data configured to test a program unit by running it under varying conditions and monitoring its behavior and outputs.

通过程序编写程序的例子有很多，例如：Yacc可以读取语法描述，然后生成一个程序用于解析前面的语法描述；protocol buffer的“编译器”可以读取一个接口描述，然后输出结构体定义、方法以及其他的代码；各类的配置工具也类似：检查元数据或者环境，生成适用于本地环境的脚手架（原文：emitting scaffolding customized to the local state）。

因此，能够编写程序的程序是软件工程中很重要的一部分，但是例如Yacc之类的程序，需要集成在编译过程中，因为它们生成的是源码，这些源码需要参与用户程序的编译。当使用诸如make等外部构建工具时，集成Yacc到编译过程中是很容易做到的。但因为Go是通过go tool只从Go源码中获取所有必需的构建信息，这个问题导致通过go tool不容易运行Yacc命令。

[Go 1.4](http://blog.golang.org/go1.4)发布之前都是上面的情况。这个版本的Go包含了一个新的命令`go generate`用于更容易的执行这些工具。它通过扫描Go源码中的特殊注释，这些注释指定了通过`go generate`执行的命令。很重要的一点需要理解的是`go generate`不是`go build`的一部分，`go generate`不会分析任何依赖，并且必须在`go build`之前显式执行。`go generate`是专门为Go包的作者准备的，Go包的用户通常不会用到这个命令。

`go generate`命令很容易使用，先用生成一个Yacc语法做个热身。加入你有一个Yacc输入文件`gopher.y`，它定义了一种新的语法，为了生成实现这种语法的Go代码，你可以这样正常的调用Yacc的Go版本：`-o`选项指定了输出文件名，`-p`选项指定了包名。
```
go tool yacc -o gopher.go -p parser gopher.y
```

如果想通过`go generate`命令实现上面的功能，可以在Yacc文件同目录下，任意非工具生成的go文件中添加下面的注释：这个注释和上面的命令相比只是多个一个`go generate`前缀，注释必须顶格写，`//`和`go:generate`之间不能有空格，`go:generate`后面的部分就是`go generate`实际执行的命令。
```
//go:generate go tool yacc -o gopher.go -p parser gopher.y
```

现在切换到源码目录，依次执行生成代码、构建等操作：下面的脚本假设执行过程没有遇到错误，`go generate`命令会调用`yacc`生成`gopher.go`，然后当前目录下就有了完整的Go源码，然后我们就能编译、测试以及正常的工作。当修改`gopher.go`以后只需要执行`go generate`就可以重新生成解析器`gopher.go`。
```
$ cd $GOPATH/myrepo/gopher
$ go generate
$ go build
$ go test
```

更多关于`go generate`如何工作的细节，例如：命令选项、环境变量等，可以阅读[设计文档](http://golang.org/s/go1.4-generate)

`go generate`虽然从功能上看和gnu make以及其他构建机制可以完成的操作是相同的，但是因为`go generate`是`go`命令中的一部分，不需要额外安装，因此比gnu make更适合Go语言的生态。请记住它是给Go包作者而不是用户用的，因为`go generate`调用的程序可能在Go包的用户机器上不存在（译者注：前面的例子中，Go包用户的机器上可能没有goyacc，但是只要用户go get下来的包有goyacc生成的gopher.go文件就可以正常编译这个包，原文：if only for the reason that the program it invokes might not be available on the target machine.）。如果使用了`go generate`的包被用户通过`go get`导入，当`go generate`生成了文件（并测试过），记得把这个文件提交到代码库里面，这样用户在导入包的时候才能拿到完整的go文件。

既然我们（Go 1.4版本中）已经有了`go generate`，那么让我们在新的例子中使用它。`golang.org/x/tools`代码库中有一个新的程序`stringer`，这是一个不同的例子可以演示`go generate`的使用。`stringer`程序的功能是给一系列整数常量自动实现转化为字符串的方法，它不在Go的发布版本中，但是很容易安装：
```
$ go get golang.org/x/tools/cmd/stringer
```

下面的例子来自于[stringer](http://godoc.org/golang.org/x/tools/cmd/stringer)文档。假设我们有一些代码，其中包含一些整数定义了不同类型的药片：
```golang
package painkiller

type Pill int

const (
    Placebo Pill = iota
    Aspirin
    Ibuprofen
    Paracetamol
    Acetaminophen = Paracetamol
)
```

为了便于调试，我们希望能够优雅打印这些常量，所以我们想实现一个签名是这样的方法：
```golang
func (p Pill) String() string
```

当然，手工写很容易，一种可能的实现如下：
```golang
func (p Pill) String() string {
    switch p {
    case Placebo:
        return "Placebo"
    case Aspirin:
        return "Aspirin"
    case Ibuprofen:
        return "Ibuprofen"
    case Paracetamol: // == Acetaminophen
        return "Paracetamol"
    }
    return fmt.Sprintf("Pill(%d)", p)
}
```

当然还有其他的方式实现这个函数，比如通过`Pill`索引的字符串切片、map或者其他的技术。不管我们怎么做，如果我们修改了Pill的集合以后需要维护相应的数据结构还是正确的，比如`Acetaminophen`和`Paracetamol`表示同一个字符串会让维护数据结构的工作更复杂（原文：tricker）。再比如使用什么样的数据结构取决于`Pill`的实际类型和值范围，有符号的还是无符号的，稀疏值还是稠密值，值是否从0开始等等。

`stringer`程序可以处理这些细节，尽管可以独立运行这个程序，但是它还是设计为通过`go generate`来驱动。为了使用它，我们在源码中添加一个注释，比如在`Pill`的定义附近：这个注释的含义是让`go generate`执行`stringer`工具为`Pill`类型生成`String`方法。默认输出文件为`pill_string.go`，我们可以通过`-output`选项来自定义。
```
//go:generate stringer -type=Pill
```

运行`go generate`命令结果如下：
```golang
$ go generate
$ cat pill_string.go
// generated by stringer -type Pill pill.go; DO NOT EDIT

package pill

import "fmt"

const _Pill_name = "PlaceboAspirinIbuprofenParacetamol"

var _Pill_index = [...]uint8{0, 7, 14, 23, 34}

func (i Pill) String() string {
    if i < 0 || i+1 >= Pill(len(_Pill_index)) {
        return fmt.Sprintf("Pill(%d)", i)
    }
    return _Pill_name[_Pill_index[i]:_Pill_index[i+1]]
}
$
```

每次修改了`Pill`的定义或者常量以后，只需要重新执行`go generate`就可以更新`String`方法。如果在同一个包里面有多个类型需要用`go generate`生成`String`方法，执行一次`go generate`命令可以更新所有的`String`方法。

当然，生成的`String`方法很难看，但是至少代码是可以正常工作的，并且也不需要人来阅读和修改生成的代码。机器生成的代码通常可读性都很差，但是机器生成的代码努力提升执行效率。所有药片的名字都紧凑的存储在一个字符串`_Pill_name`中，这样可以节省内存（即使有无限多的字符串，也只需要一个`string header`结构体）。`_Pill_index`数组通过一个简单高效率的方法把常量值映射为字符串。注意`_Pill_index`不是一个切片，这样又节省了一个`slice header`结构体。数组元素类型是`uint8`，能够容纳下字符串最长的长度，同时占用内存最少。如果有更多的值，或者有负值，`_Pill_index`的类型可能是`uint16`或者`int8`，哪种类型更合适就用哪种。

`stringer`程序生成`String`方法和常量值的特性有关，例如，如果常量值很稀疏，`stringer`可能会使用map。下面微不足道的例子中的常量值是2的幂指数：
```golang
const _Power_name = "p0p1p2p3p4p5..."

var _Power_map = map[Power]string{
    1:    _Power_name[0:2],
    2:    _Power_name[2:4],
    4:    _Power_name[4:6],
    8:    _Power_name[6:8],
    16:   _Power_name[8:10],
    32:   _Power_name[10:12],
    ...,
}

func (i Power) String() string {
    if str, ok := _Power_map[i]; ok {
        return str
    }
    return fmt.Sprintf("Power(%d)", i)
}
```

简而言之，自动生成方法允许我们比人手工做得更好。`go generate`在Go语言中还有很多应用，例如：生成unicode包的Unicode表，生成encoding/gob包高效率编解码数组的方法，生成time包中的时区信息，等等。

请创新的使用`go generate`，我们鼓励更多的实验。即使你不用`go generate`，至少使用`stringer`工具给你的整数常量生成`String`方法，让机器完成其余工作。

参考翻译[go generate 生成代码](https://www.cnblogs.com/majianguo/p/6653919.html)




