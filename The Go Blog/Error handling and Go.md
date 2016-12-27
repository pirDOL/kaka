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

### 简化重复的错误处理

### 总结
适当的错误处理是优秀软件的必要组成部分，通过这篇博客中介绍的错误处理技术，你可以写出简洁可靠的Go代码。