## [Defer, Panic, and Recover](https://blog.golang.org/defer-panic-and-recover)

4 August 2010 By Andrew Gerrand

Go语言支持常见的流程控制机制：if、for、switch、goto。除此之外，还支持通过go语句启动一个goroutine执行代码。这里我想讨论一些不太常见的机制：defer、panic、recover。

defer语句把对一个函数的调用暂存到列表中，在当前函数返回时列表中的函数被调用。defer通常用于简化清理工作的函数调用。

例如：下面这个函数打开了两个文件，然后从一个文件把内容拷贝到另一个文件。第一种实现尽管可以工作，但是存在缺陷，当`os.Create`调用失败，`CopyFile`不会关闭`src`文件就直接返回了。最简单的修复是在第二个return语句之前增加`src.Close()`，但是如果函数逻辑越来越复杂，可能不容易发现函数返回前没有关闭文件，并且即使发现了也不容易修复。通过使用defer语句可以确保文件总能被关闭，defer语句可以提醒我们在打开文件之后立即考虑关闭文件，不论函数中有多少return语句，文件总是能够被关闭。
```go
func CopyFile(dstName, srcName string) (written int64, err error) {
    src, err := os.Open(srcName)
    if err != nil {
        return
    }

    dst, err := os.Create(dstName)
    if err != nil {
        return
    }

    written, err = io.Copy(dst, src)
    dst.Close()
    src.Close()
    return
}

func CopyFile(dstName, srcName string) (written int64, err error) {
    src, err := os.Open(srcName)
    if err != nil {
        return
    }
    defer src.Close()

    dst, err := os.Create(dstName)
    if err != nil {
        return
    }
    defer dst.Close()

    return io.Copy(dst, src)
}
```

defer语句的行为很直接并且很容易预计，可以总结为下面三条：
1. defer语句调用的函数是在defer语句定义时计算实参值的
2. defer语句按照LIFO的顺序执行
3. defer语句调用的函数可能会修改外层函数的命名返回值（这是为了便于修改函数返回的错误码，后面我们会看到一个例子）

例：`a`函数中i是在defer语句定义的位置计算的，因此当函数返回时fmt输出0；`b`函数输出3210；`c`函数返回2，因为defer调用func时递增了命名返回值i。
```go
func a() {
    i := 0
    defer fmt.Println(i)
    i++
    return
}

func b() {
    for i := 0; i < 4; i++ {
        defer fmt.Print(i)
    }
}

func c() (i int) {
    defer func() { i++ }()
    return 1
}
```

panic是一个内置函数，调用panic时会停止当前的程序流，转而执行panic程序流。当函数F调用panic时，F的执行就停止了，然后执行F的defer语句，最后F返回给它的调用者。对于调用者，此时F返回就相当于F的调用者直接调用了panic，进程会一直这样清空调用栈，直到当前goroutine中所有的函数都返回并导致程序崩溃。panic可以通过直接调用panic函数触发，也可以在运行时错误中触发，例如：访问数组越界。
>Panic is a built-in function that stops the ordinary flow of control and begins panicking. ... To the caller, F then behaves like a call to panic. The process continues up the stack until all functions in the current goroutine have returned, at which point the program crashes.

recover是一个内置函数，它可以重新获得panic的goroutine的执行权。recover只有通过defer调用才是起到作用，在正常的程序流中调用recover会返回nil，其不到任何效果。如果当前goroutine触发了panic，调用recover能够捕捉到传递给panic函数的值，并且返回正常的控制流。
>If the current goroutine is panicking, a call to recover will capture the value given to panic and resume normal execution.

下面是一个展示panic和defer机制的程序：函数g输入参数i，如果i>3就调用panic，否则就递归调用自己，传入参数i+1。函数f通过defer语句执行一个函数，函数中调用recover，如果recover获取的panic不是nil，就输出出来。在继续往下阅读之前，请先思考一下程序的输出是什么。

如果我们把函数f中的defer执行的函数删除，panic会一直传递到当前goroutine的栈顶，这时会终止程序。
```go
package main

import "fmt"

func main() {
    f()
    fmt.Println("Returned normally from f.")
}

func f() {
    defer func() {
        if r := recover(); r != nil {
            fmt.Println("Recovered in f", r)
        }
    }()
    fmt.Println("Calling g.")
    g(0)
    fmt.Println("Returned normally from g.")
}

func g(i int) {
    if i > 3 {
        fmt.Println("Panicking!")
        panic(fmt.Sprintf("%v", i))
    }
    defer fmt.Println("Defer in g", i)
    fmt.Println("Printing in g", i)
    g(i + 1)
}

// output
Calling g.
Printing in g 0
Printing in g 1
Printing in g 2
Printing in g 3
Panicking!
Defer in g 3
Defer in g 2
Defer in g 1
Defer in g 0
Recovered in f 4
Returned normally from f.

// output
Calling g.
Printing in g 0
Printing in g 1
Printing in g 2
Printing in g 3
Panicking!
Defer in g 3
Defer in g 2
Defer in g 1
Defer in g 0
panic: 4
 
panic PC=0x2a9cd8
[stack trace omitted]
```

panic和recover的真实的例子是Go标准库中的[json包](http://golang.org/pkg/encoding/json/)。它通过一系列递归函数解析json格式的数据，当遇到非法格式的json数据，解析器会调用panic函数把异常传递到用户调用的标准库接口函数中，在这里通过recover函数捕捉异常并根据异常返回一个合适的错误值（具体请看[decode.go](http://golang.org/src/pkg/encoding/json/decode.go)中定义的`decodeState`类型以及`error`和`unmarshal`方法）。

**Go标准库最方便的一点是即使包内部使用了panic，包导出给用户使用的API仍然是返回一个显式的错误值。**

defer其他的使用例子除了前面的file.Close以外还包括：释放互斥锁、打印footer等等。
```go
mu.Lock()
defer mu.Unlock()

printHeader()
defer printFooter()
```

总而言之，defer语句以及panic和recover提供了一种不同寻常强大的机制来控制程序流。其他的程序语言中，也通过特殊的数据结构实现一系列类似defer模型的机制。尝试一下吧。
>In summary, the defer statement (with or without panic and recover) provides an unusual and powerful mechanism for control flow. It can be used to model a number of features implemented by special-purpose structures in other programming languages. Try it out.