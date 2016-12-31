## [Error handling and Go](https://blog.golang.org/error-handling-and-go)

12 July 2011 By Andrew Gerrand

### 简介
如果你写过Go代码，你可能会遇到内置的`error`类型，Go代码使用这个类型的值表示一个异常的状态。例如当文件打开失败时`os.Open`函数返回一个非空的`error`值。下面的代码使用`os.Open`打开一个文件，发生错误时调用`log.Fatal`方法打印错误信息并终止执行。

如果像下面代码这样使用`error`可以满足大部分的开发场景，但是这篇文章我们会深入分析`error`类型，并且讨论Go语言中错误处理的优秀实践。
>You can get a lot done in Go knowing just this about the error type, but in this article we'll take a closer look at error and discuss some good practices for error handling in Go.

```go
func Open(name string) (file *File, err error)

f, err := os.Open("filename.ext")
if err != nil {
    log.Fatal(err)
}
// do something with the open *File f
```

### error类型
`error`类型是一个接口，`error`类型的变量可以表示任意值，只要这个值能够把自己描述为一个string即可。接口的定义如下，和很多内置类型一样，`error`类型是在[universe block](http://golang.org/doc/go_spec.html#Blocks)中[预定义](http://golang.org/doc/go_spec.html#Predeclared_identifiers)的。
>The error type, as with all built in types, is predeclared in the universe block.

[errors包](http://golang.org/pkg/errors/)定义的内部类型`errorString`是最常见也是最常用的`error`类型的实现。通过`errors.New`函数构造一个`error`类型的变量，这个函数输入一个字符串，然后把它转换成为`errors.errorString`结构体，然后返回一个`error`类型的变量（译者注：因为`errorString`实现了`Error`接口，所以`errorString`类型的变量可以赋值给`error`）。
```go
type error interface {
    Error() string
}

// errorString is a trivial implementation of error.
type errorString struct {
    s string
}

func (e *errorString) Error() string {
    return e.s
}

// New returns an error that formats as the given text.
func New(text string) error {
    return &errorString{text}
}
```

接下来通过`Sqrt`函数展示`errors.New`的使用，调用者向`Sqrt`函数传递的参数为负值时，函数会返回一个非空的`error`（`error`类型的返回值实际类型为`errors.errorString`），调用者通过`error.Error`方法访问错误信息，即`math: square root of ...`，**或者`error`类型是可以直接通过fmt包打印**，fmt包格式化`error`时会调用`error.Error`方法。

`error.Error`方法接收的string参数就是发生错误时的上下文信息，上下文信息要尽量全面，例如：`os.Open`返回的`error`应该是`open /etc/passwd: permission denied`，而不应该仅仅是`permission denied`，实例代码中`Sqrt`返回的`error`就缺少不合法的参数究竟是多少这个信息。通过`fmt.Errorf`方法可以添加这个缺少的信息，这个方法的参数和`fmt.Printf`相同，返回值为通过`errors.New`创建的`error`。
```go
func Sqrt(f float64) (float64, error) {
    if f < 0 {
        return 0, errors.New("math: square root of negative number")
    }
    // implementation
}

f, err := Sqrt(-1)
if err != nil {
    fmt.Println(err)
}

if f < 0 {
    return 0, fmt.Errorf("math: square root of negative number %g", f)
}
```

`fmt.Errorf`能够满足大多数情况的需求，但是因为`error`是个接口，所以理论上任意的数据结构都能赋值给`error`，只要这个数据结构实现了`Error`接口即可，这样就可以对数据结构返回更详细的错误信息。例如：假如`Sqrt`的调用者希望能够恢复不合法的参数，为了实现这一点，我们需要实现一个新的`error`，不能再使用`errors.errorString`。这样，有特殊需求的调用者就可以通过[类型断言](http://golang.org/doc/go_spec.html#Type_assertions)来检查`Sqrt`返回的`error`是`NegativeSqrtError`还是`errors.Error`，如果是前者就可以根据需要特殊处理。这个修改对于把`error`传递给`fmt.Println`或者`log.Fatal`是透明的。
```go
type NegativeSqrtError float64

func (f NegativeSqrtError) Error() string {
    return fmt.Sprintf("math: square root of negative number %g", float64(f))
}
```

另一个例子是[json](http://golang.org/pkg/encoding/json/)包定义了`SyntaxError`类型，`json.Decode`方法在解析json时遇到语法错误时返回它。`SyntaxError`的`Field`字段在使用`fmt.Println`或者`log.Fatal`格式化`error`时不会输出，但是调用者可以通过这个字段获得出错误的文件的行信息，然后通过`fmt.Errorf`输出这些详细信息。下面的代码是[Camlistore](http://camlistore.org/)项目[实际代码](https://github.com/camlistore/go4/blob/03efcb870d84809319ea509714dd6d19a1498483/jsonconfig/eval.go#L123-L135)的精简。
```go
type SyntaxError struct {
    msg    string // description of error
    Offset int64  // error occurred after reading Offset bytes
}

func (e *SyntaxError) Error() string { return e.msg }

if err := dec.Decode(&val); err != nil {
    if serr, ok := err.(*json.SyntaxError); ok {
        line, col := findLine(f, serr.Offset)
        return fmt.Errorf("%s:%d:%d: %v", f.Name(), line, col, err)
    }
    return err
}
```

`error`接口只定义了一个`Error`方法，还有其他的错误类型实现了更多的方法。例如：[net包](http://golang.org/pkg/net/)除了和通常的用法一样返回`error`类型以外，它还定义了`net.Error`接口，这个接口中增加了其他的方法用于判断不同的错误信息。用户代码可以通过类型断言判断是否为`net.Error`类型的错误，通过`net.Error`中的`Timeout`方法和`Temporary`方法就可以判断这个网络错误短期能否恢复，例如爬虫在遇到暂时网络问题时，可以等待一段时间然后重试，但是遇到短时间不能恢复的网络错误，就需要放弃抓取。
>Client code can test for a net.Error with a type assertion and then distinguish transient network errors from permanent ones.

```go
package net

type Error interface {
    error
    Timeout() bool   // Is the error a timeout?
    Temporary() bool // Is the error temporary?
}

if nerr, ok := err.(net.Error); ok && nerr.Temporary() {
    time.Sleep(1e9)
    continue
}
if err != nil {
    log.Fatal(err)
}
```

### 简化重复的错误处理
Go中错误处理是很重要的，Go从语言实现和使用惯例上鼓励用户在出现错误时显式的检查（其他语言的使用惯例是抛出异常，但是可以不立即捕捉）。在一定程度上，显示检查错误使得Go代码变得冗杂，但是幸运的是可以采用一些技术来简化重复的错误处理。

考虑一个[App Engine](http://code.google.com/appengine/docs/go/)上的应用程序，它提供一个HTTP接口从数据存储中获得记录，然后根据模板格式化以后返回。`viewRecord`需要处理`datastore.Get`和`viewTemplate`返回的错误，处理逻辑都是把错误信息返回给用户，同时返回HTTP 500。对于这一个接口看起来这两处错误处理代码是可以管理的，但是当HTTP接口越来越多时，你会发现有很多相同的错误处理代码。
```go
func init() {
    http.HandleFunc("/view", viewRecord)
}

func viewRecord(w http.ResponseWriter, r *http.Request) {
    c := appengine.NewContext(r)
    key := datastore.NewKey(c, "Record", r.FormValue("id"), 0, nil)
    record := new(Record)
    if err := datastore.Get(c, key, record); err != nil {
        http.Error(w, err.Error(), 500)
        return
    }
    if err := viewTemplate.Execute(w, record); err != nil {
        http.Error(w, err.Error(), 500)
    }
}
```

为了减少重复的代码，我们定义一个`appHandler`类型，它返回一个`error`类型的值，然后我们就可以修改`viewRecord`，让它直接返回`datastore.Get`和`viewTemplate`返回的错误，修改后的`ViewRecord`比前面的版本简单，但是和[http包](http://golang.org/pkg/net/http/)不兼容，因为通过`http.HandleFunc`注册的处理函数是没有返回值的，我们可以给`appHandler`类型实现`http.Handler`的`ServeHTTP`接口，这样`ServeHTTP`就可以调用注册的`appHandler`函数，如果`appHandler`函数返回错误，就把错误信息返回给用户。注意`ServeHTTP`方法的接收者`fn`的类型是一个函数类型，Go支持这个语法，通过`fn(w, r)`表达式来调用接收者函数。最后，注册`appHandler`时要使用`http.Handle`方法。
```go
type appHandler func(http.ResponseWriter, *http.Request) error

func viewRecord(w http.ResponseWriter, r *http.Request) error {
    c := appengine.NewContext(r)
    key := datastore.NewKey(c, "Record", r.FormValue("id"), 0, nil)
    record := new(Record)
    if err := datastore.Get(c, key, record); err != nil {
        return err
    }
    return viewTemplate.Execute(w, record)
}

func (fn appHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
    if err := fn(w, r); err != nil {
        http.Error(w, err.Error(), 500)
    }
}

func init() {
    http.Handle("/view", appHandler(viewRecord))
}
```

通过错误处理基础设施，我们可以进一步改进，把错误处理做的对用户更友好。我们可以对于不同的错误信息返回不同的HTTP状态码，而不是所有错误都返回HTTP 500，并且还可以把完整的错误输出到App Engine开发者的控制台中，便于调试。
>With this basic error handling infrastructure in place, we can make it more user friendly. 

首先我们创建一个`appError`结构体包含一个`error`类型字段以及其他一些字段；接着修改`appHandler`的返回值为`*appError`，注意：通常让函数直接返回`error`类型的实际类型是错误的，[Go FAQ](http://golang.org/doc/go_faq.html#nil_error)里面讨论了原因，但是这里可以这样做的原因是`appError`只被`ServeHTTP`看到和使用；然后修改`appHandler`实现的`ServeHTTP`接口，把`appError`的`Message`和`Code`字段返回给用户，并把`Error`字段完整的信息输出到开发者的控制台；最后修改`viewRecord`的函数返回值为`*appError`，当遇到错误时返回更多的上下文信息。

修改后的`viewRecord`和最开始的版本函数代码量差不多，但是现在没有重复的代码并且向用户提供了更友好的用户体验。当然，可以继续优化这个应用程序的错误处理，一些想法：

1. 错误处理可以通过HTML模板返回
2. 当用户是管理员时通过HTTP响应返回调用堆栈，便于调试
3. 为`appError`写一个构造函数，存储调用堆栈，便于调试
4. 在`appHandler`中恢复panic，把错误以“Critical”的级别记录到日志中，并向用户返回“发生了严重的错误。”。这样对于避免向用户返回他们不能理解的由程序导致的错误信息是一个较好的实践。更多细节请参考[Defer, Panic, and Recover]

>recover from panics inside the appHandler, logging the error to the console as "Critical," while telling the user "a serious error has occurred." This is a nice touch to avoid exposing the user to inscrutable error messages caused by programming errors. 

```go
type appError struct {
    Error   error
    Message string
    Code    int
}

type appHandler func(http.ResponseWriter, *http.Request) *appError

func (fn appHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
    if e := fn(w, r); e != nil { // e is *appError, not os.Error.
        c := appengine.NewContext(r)
        c.Errorf("%v", e.Error)
        http.Error(w, e.Message, e.Code)
    }
}

func (fn appHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
    if e := fn(w, r); e != nil { // e is *appError, not os.Error.
        c := appengine.NewContext(r)
        c.Errorf("%v", e.Error)
        http.Error(w, e.Message, e.Code)
    }
}

func viewRecord(w http.ResponseWriter, r *http.Request) *appError {
    c := appengine.NewContext(r)
    key := datastore.NewKey(c, "Record", r.FormValue("id"), 0, nil)
    record := new(Record)
    if err := datastore.Get(c, key, record); err != nil {
        return &appError{err, "Record not found", 404}
    }
    if err := viewTemplate.Execute(w, record); err != nil {
        return &appError{err, "Can't display record", 500}
    }
    return nil
}
```

### 总结
适当的错误处理是优秀软件的必要组成部分，通过这篇博客中介绍的错误处理技术，你可以写出简洁可靠的Go代码。