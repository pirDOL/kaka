## [Package names](https://blog.golang.org/package-names)

4 February 2015 By Sameer Ajmani

### TLDR
* simple nouns, lower case, with no under_scores or mixedCaps
* computeServiceClient -> compute.Client.Call
* abbreviate judiciously：strconv -> STRing CONversion
* package-scoped：
    * Avoid stutter：http.Server vs http.HTTPServer
    * list.New vs list.NewList
    * time.New vs time.NewTicker
    * jpeg.Reader, bufio.Reader, csv.Reader
* github.com/user/hello -> $GOPATH/src/github.com/user/hello
* runtime/pprof vs net/http/pprof
* break up generic packages
* avoid using the same name as popular standard packages

### 简介
Go的代码是以包来组织，在一个包内部的代码可以引用这个包的所有go文件中定义的标识符，包的用户只能引用这个包的导出类型、函数、常量和变量（译者注：首字母开头大写的标识符），用户在引用包的导出名称时，需要用包名作为前缀，例如：`foo.Bar`引用了foo包导出的名称`Bar`。

好的包命名会让编码变得更容易，在代码上下文中，包名提供了包内容的信息，用户可以更容易的理解这个包是干啥用的以及如何使用。包名还帮助包的维护者在扩展包时确定哪些代码可以放在这个包里面。良好命名的包可以让你更容易的找到需要的代码。

Effective Go里面提供了包、类型、函数和变量命名的[指导原则](https://golang.org/doc/effective_go.html#names)，这篇文章是对这个原则的扩展讨论，并对标准库中的命名进行了调查（看它们是否遵循了上述的原则），另外，这篇文章还讨论了不好的包名以及如何改进它们。

### 包名
好的包名是简短而且清晰的，使用小写，不带下划线和驼峰，通常使用简单的名词，例如：

* time：提供测量和显示时间的函数
* list：实现双链表
* http：提供HTTP客户端和服务端实现

下面的两种命名风格是其他其他语言中很常见的，但是它们不符合Go的语言习惯：

* computeServiceClient
* priority_queue

Go的包可以包含若干的导出类型和函数，例如：`compute`包导出一个`Client`类型，这个类型带有一个使用计算服务的方法以及一个可以把计算任务分发到多个`Client`完成的函数。

**明智而谨慎的缩写包名**。包名可以使用程序员熟悉的缩写词，标准库中常用的包有缩写命名的。相反，如果缩写以后的包名具有二义性，那么就不要使用缩写。

* strconv (string conversion)
* syscall (system call)
* fmt (formatted I/O)

不要从包的用户代码剽窃名字。避免将用户代码中大量使用的名字作为包名。例如：带缓冲的I/O包命名是bufio，而不是buf，因为用户代码中通常会使用buf作为变量名，如果包名也是buf，就造成混乱了。

### 命名包的内容
包名和它的内容的名字是耦合的，因为包的用户是通过包名使用包的内容。所以设计一个包时，需要以用户的视角考虑命名。

**避免结巴**。因为客户端的代码是通过包名作为前缀引用包的内容，所以包的内容的名字就不需要包含包名了。例如：HTTP包提供的HTTP服务器的叫做Server，而不是HTTPServer。因为客户端通过http.Server引用，所以不会有二义性。

简化函数命名。当包里面的函数返回值类型为`pkg.Pkg`或者它的指针时，函数名通常省略类型名，最常见的例子是`pkg.New`函数，它的返回值是`pkg.Pkg`或者指针，这个函数是用户代码使用`pkg.Pkg`类型的标准入口。例如：

```golang
start := time.Now()                                  // start is a time.Time
t, err := time.Parse(time.Kitchen, "6:06PM")         // t is a time.Time
ctx = context.WithTimeout(ctx, 10*time.Millisecond)  // ctx is a context.Context
ip, ok := userip.FromContext(ctx)                    // ip is a net.IP

q := list.New()  // q is a *list.List
```

当函数的返回值类型为`pkg.T`并且`T`不是`Pkg`时，函数名需要包含`T`提高用户代码可读性，最常见的例子是一个包提供了多个`New`函数：
```golang
d, err := time.ParseDuration("10s")  // d is a time.Duration
elapsed := time.Since(start)         // elapsed is a time.Duration
ticker := time.NewTicker(d)          // ticker is a *time.Ticker
timer := time.NewTimer(d)            // timer is a *time.Timer
```

不同包可以由相同的名字，因为用户代码是通过包名作为前缀来区分这些相同的名字。例如：标准库里面有很多`Reader`类型，包括：`jpeg.Reader`、`bufio.Reader`、`csv.Reader`。每个包名限定了`Reader`的作用范围，因此`Reader`不是一个坏名字。

如果你不能想出一个包名，作为包内容的有意义的前缀，那么说明包抽象的边界是错误的。模拟包的用户写一些使用你的包的代码，如果代码看起来很不清晰，那么就要对包进行重构了。这个方法能够让包更容易被用户理解，同时让包更容易被开发者维护。

### 包路径
Go的包由包名和路径组成。包名写在go源码的包声明语句import里面。用户代码用包名作为前缀引用包的导出名字。用户代码通过路径在导入时寻找包。通常来说，路径中最后一个元素就是包名：
```goalng
import (
    "context"                // package context
    "fmt"                    // package fmt
    "golang.org/x/time/rate" // package rate
    "os/exec"                // package exec
)
```

编译工具会把包路径映射为路径，通过[GOPATH](https://golang.org/doc/code.html#GOPATH)环境变量在`$GOPATH/src/github.com/user/hello`这个路径中找`github.com/user/hello`这个包。这个替换看起来很简单，但是我们需要了解有关包结构以及相关的术语。

标准库使用`crypto, container, encoding, image`这些目录把相关的协议和算法包关联起来。同一个目录中的包之间没有任何依赖关系，把几个包放在一个目录中只是一种组织文件的方式。这些包之间都能够相互引用，不会形成环。

就如同不同的包可以有相同名字的变量，并且不会导致二义性，不同目录中的包也可以是相同的名字。例如：[runtime/pprof](https://golang.org/pkg/runtime/pprof)提供了[pprof](https://github.com/google/pprof)工具所需格式的profile数据，[net/http/pprof](https://golang.org/pkg/net/http/pprof)提供了HTTP接口，返回上面格式的数据。客户端需要哪个包就导入哪个，所以不会造成歧义。如果需要同时使用这两个包，需要在客户端的代码导入包时[重命名](https://golang.org/ref/spec#Import_declarations)其中的一个或全部。重命名以后，在客户端代码中需要使用重命名以后的包名作为前缀引用包的内容。重命名需要符合包名的指导原则：小写并且没有下划线和驼峰。

### 不好的包名
不好的包名降低了代码可读性和可维护性，下面给出了鉴别和修复不好的包名的指导原则。

**避免没有意义的包名**，例如：util、common、misc等。用户代码不知道这些包里面提供的是什么功能。因此用户很难使用这些包，同时开发者也很难维护它们。随着时间的累积，这些包里面的依赖增多，导致编译不必要的变慢，特别是对于规模较大的程序。另外，想util这种使用率很高的名字，用户代码导入时很可能不同路径的几个包都叫util，用户不得不重命名它们。

**把没有具体意义的包名分割成包**。把名字中相同元素的类型和函数放在一起单独作为一个包，例如：把`NewStringSet`和`SortStringSet`从util包中提取出来，单独作为一个包stringset。改进一和改进二的区别是把`Sort`函数改为了`stringset.Set`的方法，可以让客户端代码更简单。包的名字是包设计中关键的一步，从你的代码中消除没有意义的名字。
```golang
package util
func NewStringSet(...string) map[string]bool {...}
func SortStringSet(map[string]bool) []string {...}
set := util.NewStringSet("c", "a", "b")
fmt.Println(util.SortStringSet(set))

package stringset
func New(...string) map[string]bool {...}
func Sort(map[string]bool) []string {...}
set := stringset.New("c", "a", "b")
fmt.Println(stringset.Sort(set))

package stringset
type Set map[string]bool
func New(...string) Set {...}
func (s Set) Sort() []string {...}
set := stringset.New("c", "a", "b")
fmt.Println(set.Sort())
```

**不要把你所有的API都放在一个包里面**。很多好心的程序员把一个包所有导出的名字都放在api、types、interface包中，他们考虑的是用户能够很方便的找到入口代码。这样做是错误的，和util、common包的问题类似，api、types、interface包扩展时没有明确的边界、无法对用户提供明确的使用指导（api没有层次）、增加了编译依赖（依赖越复杂，编译越难并行）、容易造成命名冲突（两个库都定义了api包）。把类似api这样的包分拆，使用目录把接口和实现分离到不同的包中。

**避免不必要的包名冲突**。尽管不同的目录下的包名可以相同，但是如果同时使用了这些包，还是需要客户端代码区分它们。从客户端代码的角度考虑，需要减少重复，尽量不做包重命名。同理，自己写的包不要和标准库的包用相同的名字，例如：io、http等。

### 结论
包名是Go程序良好命名的核心，编码时花些时间选择一个好的包名并且合理组织你的代码。这有助于用户理解和使用的包，以及帮助包的维护者优雅的升级包。