## [Organizing Go code](https://blog.golang.org/organizing-go-code)

16 August 2012 By Andrew Gerrand

### 简介
Go的代码组织方式和其他语言不同，这篇文章讨论为了更好的服务用户，如何命名和打包你的Go程序。

### 选择好的名字
你选择名字会影响你如何看待你的代码，当命名你的包和导出的标识符时，需要仔细思考。

包名字提供了包内容的上下文信息。例如：标准库中的[bytes包](http://golang.org/pkg/bytes/)导出了`Buffer`类型。`Buffer`本身不是一个清楚描述的名字，但是当和包名结合起来以后，含义就清晰了，`bytes.Buffer`。如果包名是不太清楚描述的`util`，那么buffer应该使用更长的名字，比如`util.BytesBuffer`。

不要对开发代码时重命名感到羞愧。当你接触你的代码时间越长，你就能更好的理解代码的各个部分是如何相配合工作的，此时你就能定义一个更好的名字。没有必要把自己禁锢在早期的命名中，[gofmt命令](http://golang.org/cmd/gofmt/)提供了一个-r选项，可以实现语意层面的查找和替换，这对于大规模的重构变得容易。

好的名字是软件接口中最重要的一部分：代码的用户首先看到的就是接口的名字。仔细选择的名字是写一个好的代码文档的开始。下面的几条实践经验和命名本质上是相同的。

### 选择好的导入路径（让你的包可以go get）
导入路径是用户导入一个包时的字符串。它指定了包源码位置的目录（相对于$GOROOT/src/pkg或$GOPATH/src）

**译者注：import "fmt"则fmt的代码位于$GOPATH/src/pkg/fmt这个目录下面。这是标准库的包，其他的包在$GOPATH/src目录下**

导入路径必须是全球唯一的，所以使用源码仓库的跟路径。例如：go.net子仓库的`websocket`包的导入路径是`"golang.org/x/net/websocket"`。Go项目自己占用了路径`"github.com/golang"`，所以其他所有的包都不能使用这个路径了。go get命令会自动根据导入路径中的url获取并安装包。

如果你的包没有托管到互联网的仓库中，那么用域名、公司名或者项目名作为导入路径的前缀。例如：Google内部的Go代码的导入路径以`"google"`开头。

导入路径中最后一个元素通常是包名，例如：`"net/http"`这个导入路径导入的包名是http。当然不一定非要这样做，你可以任意定义包的名字，但是最好遵循根据导入路径能够预测包名的惯例：如果导入路径是"foo/bar"，bar包导入了一个quux标识符，那么用户会感觉很奇怪。

>The last element of the import path is typically the same as the package name. For instance, the import path "net/http" contains package http. This is not a requirement - you can make them different if you like - but you should follow the convention for predictability's sake: a user might be surprised that import "foo/bar" introduces the identifier quux into the package name space.

有时，有的人会把GOPATH设置到自己项目源码的根目录，然后把包放在相对于根目录的某个目录下，这样做可以让导入路径更短，例如：GOPATH设置到project，package包放在project/src/my/package，那么导入路径为"my/package"（不用再写"github.com/me/project/my/package"）。但是这样做会破坏go get的默认行为，需要用户重新设置GOPATH才能使用package包，所以不要这样做。

### 最小化导出接口
通常你的代码是有很多可用的代码片段组成，所以“把包里面的大部分功能导出”可能是很有诱惑的想法。不要这样做！

你导出的内容越多，用户对包的要求越多。用户会很快的依赖于你导出的所有类型、函数和常量，这就创建了一个隐式的约定，要始终保留用户使用的接口，（如果你在升级包的时候删除了曾经导出的内容），用户的程序和你的包会有不兼容的危险。在准备Go1的时候，我们认真的审视了标准库的导出接口，把我们不准备提交的部分删除了。当你发布你自己的程序库时，也需要类似这样做。

如果对于某些东西（是否导出）有怀疑，那就不导出它们。

### 包里面放哪些东西
把程序的所有代码都放在一个大杂烩的包里面，这样开发代码很简单，但是会稀释包名字的含义（因为这个大杂烩的包会包含很多不同的功能），用户再使用的时候不得不编译和链接无关的代码。

另一方面，很容易过度的把代码分割成小包，这样会导致你陷入在包之间交互的接口设计上，而不是把注意力放在完成程序的功能。

参考Go的标准库作为指导，有些包很大，有些包很小。例如：[http包](http://golang.org/pkg/net/http/)由17个go源码文件组成（不包含单测），导出了109个标识符；但是[hash包](http://golang.org/pkg/hash/)只有一个文件，导出了3个标识符。对于包的大小，没有短平快的规则，前面两个例子在它们的上下文情况下都是合适的。

照这样说，main包通常比其他包更大，因为功能复杂的二进制命令需要包含很多的代码，执行时二进制时没有被选择的功能的代码就是没用的，通常把main包所有的代码放在一起是比较简单的做法。例如：go tool的12000行代码分散在[34个文件](http://golang.org/src/cmd/go/)。

>Complex commands contain a lot of code that is of little use outside the context of the executable, and often it's simpler to just keep it all in the one place.

### 代码文档
好的文档是可用、可维护代码的必需品质。请阅读[Godoc: documenting Go code](http://golang.org/doc/articles/godoc_documenting_go_code.html)学习如何写一个好的文档注释。