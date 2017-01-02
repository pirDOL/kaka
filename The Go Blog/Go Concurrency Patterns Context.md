## [Go Concurrency Patterns: Context](https://blog.golang.org/context)

29 July 2014 By Sameer Ajmani

### 简介
在Go语言的服务器程序中，每个接收到的请求都由一个单独的goroutine处理，处理请求时通常会再创建其他的goroutine访问后端服务，例如数据库或者RPC服务。因此，每个请求通常会有一个处理请求的goroutine集合，这些goroutine需要能够访问这个请求的参数，例如：终端用户的身份、验证令牌、请求超时时间等。当一个请求超时或者被取消时，这个请求相关的所有goroutine都需要马上退出，以便于系统能够马上回收资源。

在谷歌我们开发了context包，它简化了从请求到达的API入口向这个请求相关的所有goroutine传递当前请求的参数值、goroutine取消信号、请求超时时间等。context包目前发布在[这里](https://golang.org/pkg/context)，这篇blog会通过一个实际例子来描述如何使用它。

### Context
context包的核心是`Context`类型，下面介绍为了便于理解进行了一些简化，以[godoc](https://golang.org/pkg/context)为准。

* Done方法：返回一个channle，它作为取消Context表示的请求的goroutine的信号，当channel关闭时，goroutine需要丢弃正在执行的操作并立即返回。更多关于Done channel的编程范式请阅读[Pipelines and Cancelation](https://blog.golang.org/pipelines)。Done方法返回的channel是只读的，这是因为通常是一个goroutine向另一个goroutine发送取消信号，接收取消信号的goroutine不是发送取消信号，同理Context也没有定义Cancel方法。另外，父goroutine处理请求时创建子goroutine处理不同任务时，子goroutine也不应该取消父goroutine。除此之外，`WithCancel`函数提供了一种方法实现取消一个新的Context。
* Err方法：返回一个error，是Context表示的请求被取消的原因。
* Deadline方法：允许函数在执行前判断自己要不要执行，如果请求剩余的可用时间很短，再执行一个可能比较耗时的操作就没有意义。同样，这个方法也可以用于设置IO操作超时时间。
* Value方法：允许`Context`变量携带请求作用域的数据，这个数据需要保证多个goroutine同步访问时的安全性。

>A Context does not have a Cancel method for the same reason the Done channel is receive-only: the function receiving a cancelation signal is usually not the one that sends the signal. In particular, when a parent operation starts goroutines for sub-operations, those sub-operations should not be able to cancel the parent. Instead, the WithCancel function (described below) provides a way to cancel a new Context value.

>Value allows a Context to carry request-scoped data.

```go
// A Context carries a deadline, cancelation signal, and request-scoped values
// across API boundaries. Its methods are safe for simultaneous use by multiple
// goroutines.
type Context interface {
    // Done returns a channel that is closed when this Context is canceled
    // or times out.
    Done() <-chan struct{}

    // Err indicates why this context was canceled, after the Done channel
    // is closed.
    Err() error

    // Deadline returns the time when this Context will be canceled, if any.
    Deadline() (deadline time.Time, ok bool)

    // Value returns the value associated with key or nil if none.
    Value(key interface{}) interface{}
}
```

### Context的派生
context包提供了从已有的Context派生出一个新Context的操作，通过派生操作得到的所有Context构成了一棵树，当一个Context取消时，所有从它派生出来的Context都会取消。

* Background()：返回一个空Context作为所有Context树的根，它永远也不会取消，没有超时时间和请求作用域的值，当请求到达时，从Background()派生出这个请求的Context。
* WithCancel()：返回父Context的一个拷贝，当父Context的Done channel关闭时，或者父goroutine调用了CancelFunc，派生的Context的Done channel被关闭。取消通常使用场景：当一个请求到达时会创建一个Context，当处理这个请求的函数返回时，对应的Context被取消；除此之外，取消还用于终止多副本的冗余请求。
* WithTimeout()：返回父Context的一个拷贝，当父Context的Done channel关闭时，或者父goroutine调用了CancelFunc，或者超时时间timeout到达时，派生的Context的Done channel被关闭。在访问后端服务时通常需要超时机制。
* WithValue()：提供了访问Context的请求作用域数据。

```go
// Background returns an empty Context. It is never canceled, has no deadline,
// and has no values. Background is typically used in main, init, and tests,
// and as the top-level Context for incoming requests.
func Background() Context

// WithCancel returns a copy of parent whose Done channel is closed as soon as
// parent.Done is closed or cancel is called.
func WithCancel(parent Context) (ctx Context, cancel CancelFunc)

// A CancelFunc cancels a Context.
type CancelFunc func()

// WithTimeout returns a copy of parent whose Done channel is closed as soon as
// parent.Done is closed, cancel is called, or timeout elapses. The new
// Context's Deadline is the sooner of now+timeout and the parent's deadline, if
// any. If the timer is still running, the cancel function releases its
// resources.
func WithTimeout(parent Context, timeout time.Duration) (Context, CancelFunc)

// WithValue returns a copy of parent whose Value method returns val for key.
func WithValue(parent Context, key interface{}, val interface{}) Context
```

了解context包如何使用的最好的例子就是通过一个能够工作的例子。

### 例子：谷歌搜索
我们的例子是一个HTTP服务，它能够处理类似`/search?q=golang&timeout=1s`这样的url，通过[谷歌搜索API](https://developers.google.com/web-search/docs/)搜索query golang，并把搜索结果渲染返回，timeout参数用于指定请求的超时时间。完整的代码分为三个包：
* [server](https://blog.golang.org/context/server/server.go)：main函数和/search接口的handler
* [userip](https://blog.golang.org/context/userip/userip.go)：从请求中提取用户的ip地址，并把它关联到Context中
* [google](https://blog.golang.org/context/google/google.go)：实现了一个Search函数，到谷歌上搜索一个query

#### 服务端程序
服务端程序处理类似/search?q=golang这样的请求，返回golang在谷歌搜索的前面若干条结果。

1. 首先，`handleSearch`函数被注册为`/search`这个接口的handler，在`handleSearch`中创建了一个Context变量`ctx`，它会在handler返回时取消。除此之外，如果请求URL中包含`timeout`参数，当超时时间到达时，`ctx`也会自动取消。
1. 然后，handler从请求中提取搜索词和客户端ip（通过userip包完成）。客户端ip在请求后端时使用，所以把它作为请求作用域的参数关联到`ctx`。
1. 最后，handler把`ctx`和搜索词传递给`google.Search`，如果搜索成功，就根据返回的结果渲染html。

```go
func handleSearch(w http.ResponseWriter, req *http.Request) {
    // 1.
    // ctx is the Context for this handler. Calling cancel closes the
    // ctx.Done channel, which is the cancellation signal for requests
    // started by this handler.
    var (
        ctx    context.Context
        cancel context.CancelFunc
    )
    timeout, err := time.ParseDuration(req.FormValue("timeout"))
    if err == nil {
        // The request has a timeout, so create a context that is
        // canceled automatically when the timeout expires.
        ctx, cancel = context.WithTimeout(context.Background(), timeout)
    } else {
        ctx, cancel = context.WithCancel(context.Background())
    }
    defer cancel() // Cancel ctx as soon as handleSearch returns.

    // 2.
    // Check the search query.
    query := req.FormValue("q")
    if query == "" {
        http.Error(w, "no query", http.StatusBadRequest)
        return
    }

    // Store the user IP in ctx for use by code in other packages.
    userIP, err := userip.FromRequest(req)
    if err != nil {
        http.Error(w, err.Error(), http.StatusBadRequest)
        return
    }
    ctx = userip.NewContext(ctx, userIP)

    // 3.
    // Run the Google search and print the results.
    start := time.Now()
    results, err := google.Search(ctx, query)
    elapsed := time.Since(start)   

    if err := resultsTemplate.Execute(w, struct {
        Results          google.Results
        Timeout, Elapsed time.Duration
    }{
        Results: results,
        Timeout: timeout,
        Elapsed: elapsed,
    }); err != nil {
        log.Print(err)
        return
    }
```

#### userip包
userip包提供了从请求中提取客户端ip地址的函数，并可以把ip地址关联到Context。Context提供k-v方式访问请求作用域的参数，key和value的类型都是`interface{}`，key的实际类型需要支持相等比较，value的实际类型必须保证多个goroutine同时访问的安全性。userip包封装了Context的k-v方式，可以通过key和value的真实类型访问请求作用域的参数。

1. 首先，为了避免key冲突，userip包定义了包内部使用的类型key（译者注：key类型的实际类型是int，客户端ip这个参数的key为0），用key类型的值作为访问Context的参数的key。
2. 然后，`FromRequest`从`http.Request`中提取出客户端ip（客户端ip的实际类型为`net.IP`），`FromContext`从`Context`中提取客户端ip，客户端ip的key值为0，这个函数内部封装了`interface{}`到`net.IP`的转换
3. 最后，`NewContext`返回一个携带客户端ip的新Context
```go
// The key type is unexported to prevent collisions with context keys defined in
// other packages.
type key int

// userIPkey is the context key for the user IP address.  Its value of zero is
// arbitrary.  If this package defined other context keys, they would have
// different integer values.
const userIPKey key = 0

func FromRequest(req *http.Request) (net.IP, error) {
    ip, _, err := net.SplitHostPort(req.RemoteAddr)
    if err != nil {
        return nil, fmt.Errorf("userip: %q is not IP:port", req.RemoteAddr)
    }

func NewContext(ctx context.Context, userIP net.IP) context.Context {
    return context.WithValue(ctx, userIPKey, userIP)
}

func FromContext(ctx context.Context) (net.IP, bool) {
    // ctx.Value returns nil if ctx has no value for the key;
    // the net.IP type assertion returns ok=false for nil.
    userIP, ok := ctx.Value(userIPKey).(net.IP)
    return userIP, ok
}
```

#### google包
`google.Search`函数向[谷歌搜索API](https://developers.google.com/web-search/docs/)发送HTTP请求，然后解析返回的json格式的结果。这个函数接收一个`Context`参数ctx，当`ctx.Done`关闭时，这个函数会立即返回，即使此时谷歌搜索API还没有返回结果。

1. 谷歌搜索API请求需要检索词和客户端ip作为HTTP请求参数
2. `google.Search`调用辅助函数`httpDo`向谷歌搜索API发送HTTP请求，并且当`ctx.Done`被关闭时，不论发往谷歌搜索API的HTTP请求没有返回，还是已经返回结果然后正在处理，都立即取消。`google.Search`向`httpDo`传递一个闭包处理谷歌搜索API的HTTP响应。
3. `httpDo`函数在一个新goroutine中发送HTTP请求并处理响应，当`ctx.Done`关闭时，`httpDo`会立即取消请求，不论新的goroutine有没有返回。

>Search uses a helper function, httpDo, to issue the HTTP request and cancel it if ctx.Done is closed while the request or response is being processed

```go
func Search(ctx context.Context, query string) (Results, error) {
    // 1.
    // Prepare the Google Search API request.
    req, err := http.NewRequest("GET", "https://ajax.googleapis.com/ajax/services/search/web?v=1.0", nil)
    if err != nil {
        return nil, err
    }
    q := req.URL.Query()
    q.Set("q", query)

    // If ctx is carrying the user IP address, forward it to the server.
    // Google APIs use the user IP to distinguish server-initiated requests
    // from end-user requests.
    if userIP, ok := userip.FromContext(ctx); ok {
        q.Set("userip", userIP.String())
    }
    req.URL.RawQuery = q.Encode()

    // 2.
    var results Results
    err = httpDo(ctx, req, func(resp *http.Response, err error) error {
        if err != nil {
            return err
        }
        defer resp.Body.Close()

        // Parse the JSON search result.
        // https://developers.google.com/web-search/docs/#fonje
        var data struct {
            ResponseData struct {
                Results []struct {
                    TitleNoFormatting string
                    URL               string
                }
            }
        }
        if err := json.NewDecoder(resp.Body).Decode(&data); err != nil {
            return err
        }
        for _, res := range data.ResponseData.Results {
            results = append(results, Result{Title: res.TitleNoFormatting, URL: res.URL})
        }
        return nil
    })
    // httpDo waits for the closure we provided to return, so it's safe to
    // read results here.
    return results, err
}

// 3.
func httpDo(ctx context.Context, req *http.Request, f func(*http.Response, error) error) error {
    // Run the HTTP request in a goroutine and pass the response to f.
    tr := &http.Transport{}
    client := &http.Client{Transport: tr}
    c := make(chan error, 1)
    go func() { c <- f(client.Do(req)) }()
    select {
    case <-ctx.Done():
        tr.CancelRequest(req)
        <-c // Wait for f to return.
        return ctx.Err()
    case err := <-c:
        return err
    }
}
```

#### 代码适配Context
许多服务器框架提供了传递请求作用域参数的包和类型，我们可以定义`Context`接口的新实现来适配使用已有的服务器框架的代码和希望使用`Context`的代码。

例如，[Gorilla的context包](http://www.gorillatoolkit.org/pkg/context)通过一个map实现HTTP请求到k-v对的映射，这样就可以把handler和请求作用域的参数关联起来。为了适配Gorilla，我们实现了[新的Context](https://blog.golang.org/context/gorilla/gorilla.go)，通过`Value`方法可以获取某个特定的HTTP请求关联的数据。
>For example, Gorilla's github.com/gorilla/context package allows handlers to associate data with incoming requests by providing a mapping from HTTP requests to key-value pairs. In gorilla.go, we provide a Context implementation whose Value method returns the values associated with a specific HTTP request in the Gorilla package.

其他包提供了类似Context的取消机制的实现，例如[Tomb包](http://godoc.org/gopkg.in/tomb.v2)提供了`Kill`方法，通过关闭`Dying`channel来发送取消信号，除此之外，Tomb包还提供了类似`sync.WaitGroup`等待多个goroutine返回的方法。为了适配Tomb，我们实现了[新的Context](https://blog.golang.org/context/tomb/tomb.go)，除了支持Context已有的cancel方法以外，如果Tomb被kill，也会取消当前的Context。

### 总结
在谷歌我们要求所有Go程序员把Context参数作为从请求到达到请求返回路径上所有调用的函数的第一个参数，这样做的目的是为了让不同团队开发的代码能够相互合作，并且Context也使得请求超时、终止请求以及诸如安全认证信息等关键参数在Go程序中传递变得更容易控制。

基于Context构建的服务器框架需要实现Context接口中的方法，这样才能在服务器框架包和需要Context参数的包之间建立联系。Context通过建立一个请求作用域的数据访问以及请求终止功能的通用接口，使得开发可扩展服务变得更加容易。
>Server frameworks that want to build on Context should provide implementations of Context to bridge between their packages and those that expect a Context parameter. Their client libraries would then accept a Context from the calling code. By establishing a common interface for request-scoped data and cancelation, Context makes it easier for package developers to share code for creating scalable services.