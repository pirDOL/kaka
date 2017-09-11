## [Introduction Gofix](https://blog.golang.org/introducing-gofix)

15 April 2011 By Russ Cox

### TLDR
gofix原理：读取go源码解析成语法树，替换新接口再转换回go源码。

### 简介
下一个Go发布版会包含重大的API修改，设计若干Go基础包。[HTTP服务端handler的代码](http://codereview.appspot.com/4239076)、[调用net.Dial的代码](http://codereview.appspot.com/4244055)、[调用os.Open的代码](http://codereview.appspot.com/4357052)、[使reflect包的代码](http://codereview.appspot.com/4281055)如果不升级到最新的API就无法编译通过。Now that our releases are more stable and less frequent, this will be a common situation. Each of these API changes happened in a different weekly snapshot and might have been manageable on its own; 然而，更新已有代码使用的API需要大量的手工劳动。

gofix是一个减少了升级大量已有代码工作的新工具。它从源代码中读取程序，寻找旧的 API，用新API改写它们，然后将程序写回文件。并不是所有API的升级都向前兼容功能，所以gofix不是总能完美工作。当gofix不能改写旧的 API，它打印一条警告给出文件名和行号，这样开发者可以检查并改写代码。gofix处理那些简单的、重复的、机械的修改，这样开发者可以集中精力对付那些真正值得注意的东西。

每次API发生了重大变化，我们都会给gofix添加代码来尽可能处理相应的转换。当升级到新的Go发布版本，并且老代码无法编译通过，只要在代码目录上执行gofix即可。

你可以自己扩展gofix支持非标准库的API改动。gofix 程序是一个简单驱动框架，框架中调用插件，每个插件改写一个特定的API，插件又叫做fix。编写新的fix需要扫描和改写go/ast语法树，通常复杂程度跟API 变化程度成正比。如果想要了解fix的实现，下面四个例子按照从易到难排序：[netdialFix](https://code.google.com/p/go/source/browse/src/cmd/fix/netdial.go?name=go1)、[osopenFix](http://code.google.com/p/go/source/browse/src/cmd/fix/osopen.go?name=go1)、 [httpserverFix](http://code.google.com/p/go/source/browse/src/cmd/fix/httpserver.go?name=go1)和(reflectFix)[http://code.google.com/p/go/source/browse/src/cmd/fix/reflect.go?name=go1]。

我们也写Go代码，所以我们跟你的一样受到这些API变化的影响。通常，我们在API 变化时会升级gofix支持，然后用gofix改写代码树中使用API的地方。我们还在其他Go 代码和个人项目中使用gofix进行升级。我们甚至使用gofix对Google 的内部代码树进行更新，当发布新的Go版本时。

作为一个例子，gofix可以改写这个来自于fmt/print.go的[代码片段](http://codereview.appspot.com/4353043/diff/10001/src/pkg/fmt/print.go#newcode657)，使其适配reflect包的新API：
```golang
switch f := value.(type) {
case *reflect.BoolValue:
    p.fmtBool(f.Get(), verb, field)
case *reflect.IntValue:
    p.fmtInt64(f.Get(), verb, field)
// ...
case reflect.ArrayOrSliceValue:
    // Byte slices are special.
    if f.Type().(reflect.ArrayOrSliceType).Elem().Kind() == reflect.Uint8 {
        // ...
    }   
// ...
}

switch f := value; f.Kind() {
case reflect.Bool:
    p.fmtBool(f.Bool(), verb, field)
case reflect.Int, reflect.Int8, reflect.Int16, reflect.Int32, reflect.Int64:
    p.fmtInt64(f.Int(), verb, field)
// ...
case reflect.Array, reflect.Slice:
    // Byte slices are special.
    if f.Type().Elem().Kind() == reflect.Uint8 {
        // ...
    }   
// ...
}
```

上面的几乎每一行都有一些微小的修改，改动累计起来量很大并且是纯体力劳动，这是计算机非常擅长的工作。

gofix能够工作的原因是Go标准库支持[解析Go源码到语法树](http://golang.org/pkg/go/parser)，同时也支持[将这些语法树打印成Go源码](http://golang.org/pkg/go/printer)。特别是，Go输出库用官方格式输出格式化后源码（通常是gofmt工具完成的），从而 gofix可以自动修改Go源码进行而不会导致格式异常。事实上，开发gofmt 的动机之一（可能另一个是避免争论大括号应该在哪）是实现一个能够更加容易重写Go 程序的工具，就像gofix做的那样。

gofix已经让它变得不可或缺。特别是近期reflect包的修改，在没有自动转换的情况下可能相当令人不快，同时reflect包的API又迫切需要重构。gofix提供了修复错误或者完全重构包的API的能力，无需担心现有代码转换的问题。我们希望你能像我们一样，发现 gofix是一个有用并且方便的工具。