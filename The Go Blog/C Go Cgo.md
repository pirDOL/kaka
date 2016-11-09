## [C? Go? CGo!](https://blog.Golang.org/c-go-cgo)
17 March 2011

### 简介
go支持Go调用c代码。用特定的规范编写Go的文件，go生成的Go文件和c文件可以被其他的Go包使用。

下面是一个简单的例子，编写一个Go包提供两个函数：Random和Seed，这两个函数是对C标准库的random和seed的封装。
```go
package rand

/*
#include <stdlib.h>
*/
import "C"

func Random() int {
    return int(C.random())
}

func Seed(i int) {
    C.srandom(C.uint(i))
}
```

让我们分析一下这里发生了什么，首先从import语句开始。

rand包导入了一个C包，但是你在Go标准库中找不到这个包，因为他是个伪包，它被go解析为对C命名空间的引用。

rand包包含对“C包”的四个引用：C.random和C.srandom的调用、C.uint(i)数据类型转换以及import "C"语句。

Random函数调用C标准库的random函数返回结果。C标准库中random返回C类型long，go中用C.long表示，C类型必须转换为Go类型然后才能被rand包以外的Go代码使用。类型转换示例，下面还给出了一个等效的函数实现，其中使用率一个临时变量来显式表示类型转换：
```go
func Random() int {
    return int(C.random())
}

func Random() int {
    var r C.long = C.random()
    return int(r)
}
```

Seed函数则正好相反：它接收Go的int类型参数，转换成C的unsigned int，然后传递给C标准库的srandom函数。
```go
func Seed(i int) {
    C.srandom(C.uint(i))
}
```
注意：cgo中把C的unsigned int表示为C.uint，完整的C类型在cgo类型中的对应关系请参考[cgo文档](https://golang.org/cmd/cgo/)。

这个例子的一个细节我们还没有解释是import语句前的注释：
```go
/*
#include <stdlib.h>
*/
import "C"
```
注释部分由cgo识别和处理：行首为\#cgo+空格的行会被删除，这些行作为cgo的指令，用于编译和链接时的选项。剩下的行作为编译这个包C代码部分的头文件。在上面的例子中，只有一个#include语句，当然也可以是任何的C代码。

这里有一个限制：如果你的程序使用了//export指令，那么注释中的C代码可能只包含函数声明，不包含函数实现，这样你可以在Go函数中使用这些export的C代码。

\#cgo和//export语句请参考[cgo文档](https://golang.org/cmd/cgo/)。

### 字符串
不同于Go，C没有标准的字符串类型，C标准字符串约定为一个以\0结尾的字符数组。

Go和C的字符串类型转换是通过C.CString、C.GoString和C.GoStringN函数来完成。这些转换函数都会复制字符串。

下一个例子实现了一个Print函数，通过C标准库stdio的fputs函数把一个Go字符串通过stdout输出。
```go
package print

// #include <stdio.h>
// #include <stdlib.h>
import "C"
import "unsafe"

func Print(s string) {
    cs := C.CString(s)
    C.fputs(cs, (*C.FILE)(C.stdout))
    C.free(unsafe.Pointer(cs))
}
```

Go的内存管理器是不知道C代码进行的内存分配的，如果你用C.CString创建了一个C字符串（或者其他的C内存分配），你必须记得在用完以后调用C.free释放内存。

C.CString返回一个指向字符数组起始地址的指针，所以在函数返回之前，我们把它转换成unsafe.Pointer并调用C.free释放。Go语言的地道做法是用defer，在分配完以后马上释放，特别是当分配和释放之间的代码很复杂、不止一个函数时。重写以后的Print：
```go
func Print(s string) {
    cs := C.CString(s)
    defer C.free(unsafe.Pointer(cs))
    C.fputs(cs, (*C.FILE)(C.stdout))
}
```

### 编译go包
编译cgo包和Go包的编译是相同的，也是使用go build和go install。go工具会识别import "C"语句，然后由cgo来处理这些文件。

### 更多go资源
[cgo文档](https://golang.org/cmd/cgo/)包含更多C伪包以及构建过程的细节。[cgo例程](https://golang.org/misc/cgo/)展示了更高级的概念。

一个简单的、常用的基于cgo的包例子是Russ Cox的[gosqlite](https://code.google.com/archive/p/gosqlite/source)。另外，Go项目仪表盘上也列出了[几个其他cgo包](https://godashboard.appspot.com/project?tag=cgo)。

最后，如果你想了解所有这些内部是如何工作的，请阅读一下runtime包的[cgocall.go](https://golang.org/src/runtime/cgocall.go)代码开头的注释。

By Andrew Gerrand
