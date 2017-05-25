## [JSON-RPC: a tale of interfaces](https://blog.golang.org/json-rpc-tale-of-interfaces)

27 April 2010 By Andrew Gerrand

这里我们展示一个[Go接口](http://golang.org/doc/effective_go.html#interfaces_and_types)使得重构已有的代码，提高代码的灵活性和扩展性。标准库的[RPC包](http://golang.org/pkg/net/rpc/)原生使用Go自定义的总线类型[gob](http://golang.org/pkg/encoding/gob/)，在某个程序中，我们希望使用[JSON](http://golang.org/pkg/encoding/json/)作为总线类型。

首先，我们定义了一系列接口描述现有的总线类型的功能，客户端和服务端分别有一个接口如下：
```golang
type ServerCodec interface {
    ReadRequestHeader(*Request) error
    ReadRequestBody(interface{}) error
    WriteResponse(*Response, interface{}) error
    Close() error
}
```

服务端，我们修改两个内部函数签名，增加一个参数类型为`ServerCodec`接口，代替原生的`gob.Encoder`：
```golang
func sendResponse(sending *sync.Mutex, req *Request, reply interface{}, enc *gob.Encoder, errmsg string)

func sendResponse(sending *sync.Mutex, req *Request, reply interface{}, enc ServerCodec, errmsg string)
```

然后我们通过`gobServerCodec`结构体实现接口`ServerCodec`，其实只需要把原来的功能实现在`ServerCodec`接口相应的函数中。类似的，`jsonServerCodec`结构体也要实现接口`ServerCodec`。

最后对客户端的代码做一些类似的修改以后，就完成了我们对RPC包改造需要做的全部工作，这些工作只需要20分钟。测试完新代码以后的提交[在这里](https://github.com/golang/go/commit/dcff89057bc0e0d7cb14cf414f2df6f5fb1a41ec)。

在面向继承的语言中，例如C++和Java，更常用的方式是对RPC类进行派生，JsonRPC和GobRPC两个子类。但是如果你想在这种类体系结构上进一步扩展正交的子类，这种方法就变得很trick。例如：如果你想再实现一种RPC标准。在GO的包中，我们采用了概念上更简单的方法，需要修改和重写的代码更少。

>In an inheritance-oriented language like Java or C++, the obvious path would be to generalize the RPC class, and create JsonRPC and GobRPC subclasses. However, this approach becomes tricky if you want to make a further generalization orthogonal to that hierarchy. (For example, if you were to implement an alternate RPC standard). In our Go package, we took a route that is both conceptually simpler and requires less code be written or changed.

可维护性是任何代码库的关键质量。当需求变化时，需要代码能够简单、清晰的适配需求，小心谨慎的避免代码变得笨重。我们相信Go轻量级、面向组合的类型系统能够提供一种可扩展的架构代码的方法。