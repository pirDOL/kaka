## [Error handling in Upspin](https://commandcenter.blogspot.com/2017/12/error-handling-in-upspin.html)

December 06, 2017 by Rob Pike and Andrew Gerrand

### TLDR
1. what is a good error message?
    1. to programmer:
        1. easy to build informative error messages on different language type. We noticed that the elements that go into an error message in Upspin are all of different types: user names, path names, the kind of error (I/O, permission, etc.) and so on. This provided the starting point for the package, which would build on these different types to construct, represent, and report the errors that arise.
        1. helpful as diagnostics
    1. to user:
        1. easy to understand for users
1. a tour of upspin.io/error
    1. The Kind field classifies the error as one of a set of standard conditions (Permission, IO, NotExist, and so on). It makes it easy to see a concise description of what sort of error occurred.（译者注：就是定义了一个枚举作为错误码，实际工程特别是多人协作的项目，错误的分类可能会受主观判断影响，需要严格的评审机制保证。）

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

让我们看个例子。

[errors.New](https://golang.org/pkg/errors/#New)
[MarshalError](https://godoc.org/upspin.io/errors#MarshalError)
[UnmarshalError](https://godoc.org/upspin.io/errors#UnmarshalError)
[upspin.io/store/remote](http://upspin.io/store/remotehttps://godoc.org/upspin.io/store/remote)
[upspin.io/dir/server](https://godoc.org/upspin.io/dir/server)
[upspin.io/dir/remote](https://godoc.org/upspin.io/dir/remote)
[upspin.io/client](https://godoc.org/upspin.io/client)
[Error](https://godoc.org/upspin.io/errors#Error.Error)
[errors.Is](https://godoc.org/upspin.io/errors#Is)
[Match](https://godoc.org/upspin.io/errors#Match)
[elsewhere](https://blog.golang.org/errors-are-values)


As the doc comment for the function says, E builds an error value from its arguments. The type of each argument determines its meaning. The idea is to look at the types of the arguments and assign each argument to the field of the corresponding type in the constructed Error struct. There is an obvious correspondence: a PathName goes to Error.Path, a UserName to Error.User, and so on.

Let's look at an example. In typical use, calls to errors.E will arise multiple times within a method, so we define a constant, conventionally called op, that will be passed to all E calls within the method:

  func (s *Server) Delete(ref upspin.Reference) error {
    const op errors.Op = "server.Delete"
     ...

Then through the method we use the constant to prefix each call (although the actual ordering of arguments is irrelevant, by convention op goes first):

  if err := authorize(user); err != nil {
    return errors.E(op, user, errors.Permission, err)
  }

The String method for E will format this neatly:

  server.Delete: user ann@example.com: permission denied: user not authorized

If the errors nest to multiple levels, redundant fields are suppressed and the nesting is formatted with indentation:

  client.Lookup: ann@example.com/file: item does not exist:
          dir/remote("upspin.example.net:443").Lookup:
          dir/server.Lookup

Notice that there are multiple operations mentioned in this error message (client.Lookup, dir/remote, dir/server). We'll discuss this multiplicity in a later section.

As another example, sometimes the error is special and is most clearly described at the call site by a plain string. To make this work in the obvious way, the constructor promotes arguments of literal type string to a Go error type through a mechanism similar to the standard Go function errors.New. Thus one can write:

   errors.E(op, "unexpected failure")

or

   errors.E(op, fmt.Sprintf("could not succeed after %d tries", nTries))

and have the string be assigned to the Err field of the resulting Err type. This is a natural and easy way to build special-case errors.

Errors across the wire

Upspin is a distributed system and so it is critical that communications between Upspin servers preserve the structure of errors. To accomplish this we made Upspin's RPCs aware of these error types, using the errors package's MarshalError and UnmarshalError functions to transcode errors across a network connection. These functions make sure that a client will see all the details that the server provided when it constructed the error.

Consider this error report:

  client.Lookup: ann@example.com/test/file: item does not exist:
         dir/remote("dir.example.com:443").Lookup:
         dir/server.Lookup:
         store/remote("store.example.com:443").Get:
         fetching https://storage.googleapis.com/bucket/C1AF...: 404 Not Found

This is represented by four nested errors.E values.

Reading from the bottom up, the innermost is from the package upspin.io/store/remote (responsible for taking to remote storage servers). The error indicates that there was a problem fetching an object from storage. That error is constructed with something like this, wrapping an underlying error from the cloud storage provider:

  const op errors.Op = `store/remote("store.example.com:443").Get`
  var resp *http.Response
  ...
  return errors.E(op, errors.Sprintf("fetching %s: %s", url, resp.Status))

The next error is from the directory server (package upspin.io/dir/server, our directory server reference implementation), which indicates that the directory server was trying to perform a Lookup when the error occurred. That error is constructed like this:

  const op errors.Op = "dir/server.Lookup"
  ...
  return errors.E(op, pathName, errors.NotExist, err)

This is the first layer at which a Kind (errors.NotExist) is added.

The Lookup error value is passed across the network (marshaled and unmarshaled along the way), and then the upspin.io/dir/remote package (responsible for talking to remote directory servers) wraps it with its own call to errors.E:

  const op errors.Op = "dir/remote.Lookup"
  ...
  return errors.E(op, pathName, err)

There is no Kind set in this call, so the inner Kind (errors.NotExist) is lifted up during the construction of this Error struct.

Finally, the upspin.io/client package wraps the error once more:

  const op errors.Op = "client.Lookup"
  ...
  return errors.E(op, pathName, err)

Preserving the structure of the server's error permits the client to know programmatically that this is a "not exist" error and that the item in question is "ann@example.com/file". The error's Error method can take advantage of this structure to suppress redundant fields. If the server error were merely an opaque string we would see the path name multiple times in the output.

The critical details (the PathName and Kind) are pulled to the top of the error so they are more prominent in the display. The hope is that when seen by a user the first line of the error is usually all that's needed; the details below that are more useful when further diagnosis is required.

Stepping back and looking at the error display as a unit, we can trace the path the error took from its creation back through various network-connected components to the client. The full picture might help the user but is sure to help the system implementer if the problem is unexpected or unusual.

Users and implementers

There is a tension between making errors helpful and concise for the end user versus making them expansive and analytic for the implementer. Too often the implementer wins and the errors are overly verbose, to the point of including stack traces or other overwhelming detail.

Upspin's errors are an attempt to serve both the users and the implementers. The reported errors are reasonably concise, concentrating on information the user should find helpful. But they also contain internal details such as method names an implementer might find diagnostic but not in a way that overwhelms the user. In practice we find that the tradeoff has worked well.

In contrast, a stack trace-like error is worse in both respects. The user does not have the context to understand the stack trace, and an implementer shown a stack trace is denied the information that could be presented if the server-side error was passed to the client. This is why Upspin error nesting behaves as an operational trace, showing the path through the elements of the system, rather than as an execution trace, showing the path through the code. The distinction is vital.

For those cases where stack traces would be helpful, we allow the errors package to be built with the "debug" tag, which enables them. This works fine, but it's worth noting that we have almost never used this feature. Instead the default behavior of the package serves well enough that the overhead and ugliness of stack traces are obviated.

Matching errors

An unexpected benefit of Upspin's custom error handling was the ease with which we could write error-dependent tests, as well as write error-sensitive code outside of tests. Two functions in the errors package enable these uses.

The first is a function, called errors.Is, that returns a boolean reporting whether the argument is of type *errors.Error and, if so, that its Kind field has the specified value.

  func Is(kind Kind, err error) bool

This function makes it straightforward for code to change behavior depending on the error condition, such as in the face of a permission error as opposed to a network error:

  if errors.Is(errors.Permission, err) { ... }

The other function, Match, is useful in tests. It was created after we had been using the errors package for a while and found too many of our tests were sensitive to irrelevant details of the errors. For instance, a test might only need to check that there was a permission error opening a particular file, but was sensitive to the exact formatting of the error message.

After fixing a number of brittle tests like this, we responded by writing a function to report whether the received error, err, matches an error template:

  func Match(template, err error) bool

The function checks whether the error is of type *errors.Error, and if so, whether the fields within equal those within the template. The key is that it checks only those fields that are non-zero in the template, ignoring the rest.

For our example described above, one can write:

  if errors.Match(errors.E(errors.Permission, pathName), err) { … }

and be unaffected by whatever other properties the error has. We use Match countless times throughout our tests; it has been a boon.

Lessons

There is a lot of discussion in the Go community about how to handle errors and it's important to realize that there is no single answer. No one package or approach can do what's needed for every program. As was pointed out elsewhere, errors are just values and can be programmed in different ways to suit different situations.

The Upspin errors package has worked out well for us. We do not advocate that it is the right answer for another system, or even that the approach is right for anyone else. But the package worked well within Upspin and taught us some general lessons worth recording.

The Upspin errors package is modest in size and scope. The original implementation was built in a few hours and the basic design has endured, with a few refinements, since then. A custom error package for another project should be just as easy to create. The specific needs of any given environment should be easy to apply. Don't be afraid to try; just think a bit first and be willing to experiment. What's out there now can surely be improved upon when the details of your own project are considered.

We made sure the error constructor was both easy to use and easy to read. If it were not, programmers would resist using it.

The behavior of the errors package is built in part upon the types intrinsic to the underlying system. This is a small but important point: No general errors package could do what ours does. It truly is a custom package.

Moreover, the use of types to discriminate arguments allowed error construction to be idiomatic and fluid. This was made possible by a combination of the existing types in the system (PathName, UserName) and new ones created for the purpose (Op, Kind). Helper types made error construction clean, safe, and easy. It took a little more work—we had to create the types and use them everywhere, such as through the "const op" idiom—but the payoff was worthwhile.

Finally, we would like to stress the lack of stack traces as part of the error model in Upspin. Instead, the errors package reports the sequence of events, often across the network, that resulted in a problem being delivered to the client. Carefully constructed errors that thread through the operations in the system can be more concise, more descriptive, and more helpful than a simple stack trace.

Errors are for users, not just for programmers.
