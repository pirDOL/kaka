## [Error handling in Upspin](https://commandcenter.blogspot.com/2017/12/error-handling-in-upspin.html)

December 06, 2017 by Rob Pike and Andrew Gerrand

### TLDR
1. what is a good error message?
    1. to programmer:
        1. easy to build informative error messages on different language type. We noticed that the elements that go into an error message in Upspin are all of different types: user names, path names, the kind of error (I/O, permission, etc.) and so on. This provided the starting point for the package, which would build on these different types to construct, represent, and report the errors that arise.
        1. helpful as diagnostics
    1. to user: easy to understand for users
    2. There is a tension between making errors helpful and concise for the end user versus making them expansive and analytic for the implementer. Too often the implementer wins and the errors are overly verbose, to the point of including stack traces or other overwhelming detail. Upspin's errors are an attempt to serve both the users and the implementers. The reported errors are reasonably concise, concentrating on information the user should find helpful. But they also contain internal details such as method names an implementer might find diagnostic but not in a way that overwhelms the user. In practice we find that the tradeoff has worked well.
1. a tour of upspin.io/error
    1. The Kind field classifies the error as one of a set of standard conditions (Permission, IO, NotExist, and so on). It makes it easy to see a concise description of what sort of error occurred.（译者注：就是定义了一个枚举作为错误码，实际工程特别是多人协作的项目，错误的分类可能会受主观判断影响，需要严格的评审机制保证。）
    2. To accomplish that communications between Upspin servers preserve the structure of errors, we made Upspin's RPCs aware of these error types, using the errors package's MarshalError and UnmarshalError functions to transcode errors across a network connection.
    2. An unexpected benefit of Upspin's custom error handling was the ease with which we could write error-dependent tests, as well as write error-sensitive code outside of tests.
    3. The Upspin errors package has worked out well for us. We do not advocate that it is the right answer for another system, or even that the approach is right for anyone else.
1. lesson
    1. errors are just values and can be programmed in different ways to suit different situations.
    2. We made sure the error constructor was both easy to use and easy to read. If it were not, programmers would resist using it.
    3. the use of types to discriminate arguments allowed error construction to be idiomatic and fluid. This was made possible by a combination of the existing types in the system (PathName, UserName) and new ones created for the purpose (Op, Kind). Helper types made error construction clean, safe, and easy.

### 翻译
[Upspin](https://upspin.io/)项目使用了一个自定义的包[upspin.io/errors](https://godoc.org/upspin.io/errors)来表示系统中发生的错误。这个包在接口上遵循Go标准库的[error](https://golang.org/pkg/builtin/#error)接口，但是是用自定义的[upspin.io/errors.Error](https://godoc.org/upspin.io/errors#Error)类型实现的，这个类型提供的特性被证明对项目很有价值。

下面我们会展示这个包如何工作和使用，这篇博客对于更大范围的讨论“Go语言中的错误处理”是一个很好的经验。

#### 动机
当项目开发了几个月以后，迫切需要一个一致性的方法来构建、表示、处理错误。我们决定实现一个自定义的error包，于是在一个下午我们手撸了一个（原文：rolled one out in an afternoon）。（目前）这个包的细节和最初实现的版本有些变化，但是包背后基本的思想却没有改变：
* 让构建有用的错误信息更容易
* 让错误更容易被用户理解
* 让错误对于开发者诊断故障更有帮助

随着我们不断完善这个包，也出现了其他一些动机，我们会在下面讨论它们。

####　包概览
[upspin.io/errors](https://godoc.org/upspin.io/errors)包导入后的名字是“errors”，所以在upspin项目中，它替代了Go标准库的errors包的地位。

我们注意到upspin项目中的错误信息中的元素类型都是各不相同的：用户名、路径名、错误类型（I/O、权限等）。这一点是这个包开发的起点动机：当发生错误时，能在不同类型的元素上构建、表示并报告出错误信息。

包的核心是[Error](https://godoc.org/upspin.io/errors#Error)类型，它是upspin项目的错误信息的实际载体，它由一些字段组成，任意的字段都可以不设置。
```go
type Error struct {
  Path upspin.PathName
  User upspin.UserName
  Op  Op
  Kind Kind
  Err error
}
```

Path和User字段表示本次操作影响的路径和用户，注意路径和用户都是字符串，在upspin中我们为它们分别定义不同的类型是为了让使用它们的代码可读性更强，（因为Go是强类型语言）除此之外还可以利用Go语言的类型系统捕捉特定类型程序错误（原文：but have distinct types in Upspin to clarify their usage and to allow the type system to catch certain classes of programming errors.）。

Op字段表示（发生错误时）正在执行的操作，它也是字符串类型，通常它的内容是报告错误的方法名（例如："client.Lookup"）或者服务端的函数名（例如："dir/server.Glob"）等等。

Kind字段用于对错误在标准错误集合中进行分类，例如：权限、IO、文件不存在[等等](https://godoc.org/upspin.io/errors#Kind)，这个字段可以让用户和开发者准确的看到当前发生的错误是哪一类，并且它也是[upspinfs](https://godoc.org/upspin.io/cmd/upspinfs)和其他系统交互的钩子，例如：upspinfs把Kind字段作为upspin错误和unix错误常量（例如：EPERM、EIO等）之间进行转换的key。

最后一个Err字段可能包含另一个错误值，这个错误值通常来自与其他系统，例如[os包](https://golang.org/pkg/os/)的文件系统错误或者[net包](https://golang.org/pkg/net/)的网络错误。它还可以是另一个upspin.io/errors.Error类型的值，从而构成对一系列错误堆栈的跟踪，我们后面会讨论错误跟踪。

#### 构建一个错误
为了让错误容易被创建，包提供了名字为[E](https://godoc.org/upspin.io/errors#E)的函数，这个函数很简短也很容易被输入：
```go
func E(args ...interface{}) error
```
如同[doc comment](https://godoc.org/upspin.io/errors#E)中所说，E函数通过参数构建错误值。每个变量的类型确定了它的含义。E函数根据参数的类型给Error结构体的相应的字段赋值，显然：PathName类型的参数会赋值给Error.Path字段，UserName类型的参数会赋值给Error.User字段，等等。

让我们看个例子：通常的使用中会在一个函数中调用`errors.E`很多次，所以我们（在函数的开头）定义一个常量通常叫做op，它会作为这个函数中所有调用`errors.E`函数的参数，并且把这个常量作为第一个参数，尽管实际上`errors.E`的参数顺序是无关紧要的，但是通常我们会把op放在第一个参数。
```go
func (s *Server) Delete(ref upspin.Reference) error {
  const op errors.Op = "server.Delete"
   ...

  if err := authorize(user); err != nil {
    return errors.E(op, user, errors.Permission, err)
  }
```

`E`类型的的`String`方法能够整洁的格式化输出。如果errors嵌套多层，重复的字段会被压缩，并以缩进表示嵌套层次。注意，下面的错误信息中有多个操作（client.Lookup、dir/remote、dir/server），我们会在后面详细讨论。
```
server.Delete: user ann@example.com: permission denied: user not authorized

client.Lookup: ann@example.com/file: item does not exist:
    dir/remote("upspin.example.net:443").Lookup:
    dir/server.Lookup
```

另一个例子，有时错误是特殊的，通过一个普通的字符串就可以清晰的描述错误。为了适应这种应用场景，`errors.E`可以把字面字符串提升（原文：promote arguments of literal type string）为Go的error类型，提升的方法和Go标准库的[errors.New](https://golang.org/pkg/errors/#New)方法类似。因此你可以像下面这样写，字符串会被赋值给`Error`的`Err`字段，这是一种自然、简单的方法构造特殊类型的错误。
```
errors.E(op, "unexpected failure")
errors.E(op, fmt.Sprintf("could not succeed after %d tries", nTries))
```

#### 错误值的传输（原文：Errors across the wire）
upspin是一个分布式系统，所以在服务端进程之间通信时保存errors结构体。为了实现这一点，我们让upspin的rpc能够识别errors类型，通过errors包的[MarshalError](https://godoc.org/upspin.io/errors#MarshalError)和[UnmarshalError](https://godoc.org/upspin.io/errors#UnmarshalError)函数把errors在网络上传输。这些函数保证了客户端能够看到服务端构建的errors结构体的详细的信息。

考虑下面的错误信息：它是4层`errors.E`嵌套而成的。

1. 从最底下往上看，最内层的错误来自于[upspin.io/store/remote包](http://upspin.io/store/remotehttps://godoc.org/upspin.io/store/remote)（它的功能是访问远程存储服务器），这个错误表示从存储中获取对象遇到了问题。这个错误是像下面这样构造的，对云存储提供商的底层错误进行了封装。
2. 第二层错误来自于[upspin.io/dir/server包](https://godoc.org/upspin.io/dir/server)，这个包是目录服务的实现，这个错误表示目录服务器在执行查询时发生了错误。这个错误的构造方式是这样的，这里第一个使用了Kind字段（errors.NotExist）的错误层次。
3. 目录服务器的错误通过网络传递给调用方（经过序列化和反序列化），然后[upspin.io/dir/remote包](https://godoc.org/upspin.io/dir/remote)，这个包用于和远程目录服务器进行通信，它对通过网络传输的错误进行了一次封装。这个调用中没有设置Kind字段，所以下一层错误的Kind字段就在构造Error时被提升上来。
4. 最后，[upspin.io/client包](https://godoc.org/upspin.io/client)对错误再一次包装。
```
client.Lookup: ann@example.com/test/file: item does not exist:
    dir/remote("dir.example.com:443").Lookup:
    dir/server.Lookup:
    store/remote("store.example.com:443").Get:
    fetching https://storage.googleapis.com/bucket... 404 Not Found

// 1
const op errors.Op = `store/remote("store.example.com:443").Get`
var resp *http.Response
...
return errors.E(op, errors.Sprintf("fetching %s: %s", url, resp.Status))

// 2
const op errors.Op = "dir/server.Lookup"
...
return errors.E(op, pathName, errors.NotExist, err)

// 3
const op errors.Op = "dir/remote.Lookup"
...
return errors.E(op, pathName, err)
```

保存服务端的错误结构体允许客户端能够从程序角度知道这是一个“不存在”错误，有问题的信息是ann\@example.com/file。errors包的[Error方法](https://godoc.org/upspin.io/errors#Error.Error)能够对这个结构体中的冗余字段进行压缩，（否则）如果服务端的错误仅仅是一个字符串，我们会在输出中看到路径名重复了很多次。（原文：If the server error were merely an opaque string we would see the path name multiple times in the output.）

关键的信息（PathName和Kind）会提升到最顶层的错误中以便于更突出的显示。我们希望当用户看到错误信息的第一行时就能得到最需要的信息，下面几行的错误信息在需要进一步诊断时更有用。

回过头来再看错误信息，我们能够从错误生成的位置一路从服务端经过各种各样的网络连接追踪到客户端。完整的图片可以帮助用户，也可以帮助系统的实现者了解非预期或者是罕见的错误。

#### 用户和实现者
让错误信息对终端用户更有帮助、更准确和让它们对程序员更有扩展性和可分析性之间是势不两立的关系（原文：There is a tension between A and B.）。经常是程序员获得了胜利，因此错误信息会很冗长：包含了堆栈信息或是过度的细节。

upspin的错误尝试同时满足用户和实现着。返回给用户的错误（原文：reported error）是足够准确、集中于用户感觉有用的信息。同时，错误信息中同样包含内部的细节，例如方法名，便于程序员诊断问题，细节信息不会让错误信息给用户造成冗余的感觉。事实上我们发现这个折衷效果足够好。

相比而言，堆栈型的错误信息在各个方面都不好：用户没有理解堆栈信息的上下文（译者注：需要结合程序代码看堆栈），实现者看到的堆栈信息缺少一些必要的信息，因为错误是从服务端传给客户端（译者注：我的理解是堆栈信息中看不到关键变量的值，这些信息也不应该传给用户）。因此upspin的错误嵌套是以“操作（原文：operational trace）”的层次来追踪的，展示了请求在系统的各个元素经过的路径。堆栈型错误信息的以“执行（原文：execution trace）”为层次的，展示的是代码执行的路径。这个区别是关键的。

对于一些场景，堆栈型错误信息是很有帮助的，我们允许errors包编译时指定debug标记，这样就能开启堆栈。我们在实际中还没用过这个功能。errors包的默认行为能够满足大多数场景，堆栈型错误信息的开销和丑陋都能够被避免。

#### 比较错误值
upspin自定义的错误处理包的一个未预料的好处是我们可以很容易的编写依赖错误（原文：error-dependent）的测试用例以及错误敏感的非测试代码（原文：An unexpected benefit of Upspin's custom error handling was the ease with which we could write error-dependent tests, as well as write error-sensitive code outside of tests.）。errors包的两个函数支持了这种用法。

第一个函数是[errors.Is](https://godoc.org/upspin.io/errors#Is)，返回一个布尔值表示参数是否为*errors.Error类型并且Kind字段是否和指定参数相等。这个函数让代码能够更直接的根据错误改变行为，例如：对于权限错误的处理行为和网络错误的行为就不同。
```go
func Is(kind Kind, err error) bool

if errors.Is(errors.Permission, err) { ... }
```

另一个函数是[Match](https://godoc.org/upspin.io/errors#Match)，通常在测试中使用。这个函数是我们使用了errors包很久以后才增加的，我们发现很多测试代码依赖于不相干的错误细节。例如：一个测试用例可能只需要检查打开特定文件时是权限错误，但是却需要对错误信息的准确格式敏感（译者注：这是不必要的）。

在修改了很多这样的脆弱的测试用例以后，我们实现了这个函数比较错误是否匹配一个错误模板。这个函数检查err参数是否为*errors.Error类型，并且它的字段值是否和template相等。它只检查tempate中的非零值的字段，其他的字段都被忽略。对于我们前面的例子，我们这样改造后就不受错误其他的字段的影响。我们在测试中大量使用了Match函数，它就像上天的恩赐。
```go
func Match(template, err error) bool

if errors.Match(errors.E(errors.Permission, pathName), err) { … }
```

#### 我们学到的经验
在Go的社区中有很多关于如何进行错误处理的讨论，值得指出的是这个问题没有一个答案。不存在一个包或者一个方法能够满足所有程序的需要。[如同这篇文章指出的](https://blog.golang.org/errors-are-values)，错误是值，因此可以在不同的场景下以不同的方式编程。

upspin的errors包在我们的系统中工作的很好。我们不赞成它能适用于其他系统，errors包的方法也不一定对其他人适用。但是这个包在upspin中工作的很好，并且给我们上了一堂值得记录的课。

upspin的errors包的大小和规模都很适度。最原始的实现只用了几个小时，后来只进行了一些小的修复，原始的设计没有变化。对于其他的项目，一个自定义的error包应该也很容易实现。任何给定环境下的特殊需求应该很容易实现。不要害怕尝试，只是在开工前仔细思考一下，并且要原意做实验。upspin现在的errors包如果仔细考虑一下你的项目的细节，肯定有很多可以改善的地方。

我们确保错误的构造函数容易使用和接口容易阅读，否则，程序员会抵制它们。

errors包的行为对底层系统的数据类型存在一定的耦合和依赖。这是很重要的一点：没有任何的通用错误包能跟我们的包实现相同的功能。因为我们的错误包是定制的。并且，通过类型区分参数是的错误的构造函数更通用和流畅，这一点是利用了系统中现有的类型（PathName、UserName）以及一些特定用途的新类型（Op、Kind）。helper类型让错误构造函数更简洁、安全和简单。我们需要一些额外的工作，例如：定义一类新的类型并通过const op习语那样使用它们，这些额外的工作是值得的。

最后，我们需要强调的是upspin的错误模型中缺少堆栈跟踪功能。相反，errors包以事件序列的方式组织错误，甚至是通过网络传递，最终到达客户端。仔细构造的错误信息（以系统中的操作为线索串联）会比简单的堆栈追踪更简单、更具有描述性、更有帮助。

错误信息不仅仅是给程序员的，也是给用户看的。

### 参考
[Hacker News上的讨论](https://news.ycombinator.com/item?id=15867015)

