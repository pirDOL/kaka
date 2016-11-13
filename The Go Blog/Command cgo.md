## [Command cgo](https://golang.org/cmd/cgo/)

cgo允许创建调用C代码的Go包。

### 通过go命令使用cgo
cgo最简单的使用是在编写Go代码时引用一个伪包C，这样Go代码就能引用C的类型、变量和函数，例如：C.size_t、C.stdout、C.putchar。

import "C"语句前面的注释（注释和import之间不能空行）叫做序言（preamble），它在编译这个包的C部分代码时，作为头文件。例如：
```go
// #include <stdio.h>
// #include <errno.h>
import "C"
```

序言可以包含任意的C代码，包括函数、变量的声明和定义，尽管它们定义在C包中，但是可以在Go代码中使用。序言中定义的所有符号，即使是小写字母开头的，也可以在Go代码中引用。特例：序言中的静态变量不能在Go代码中使用，静态函数则没有这个限制。

译者注：用static函数做为static变量的getter和setter
```go
//test_static.go

package test
//int g_cnt;
//static int s_cnt;
//static int get_s_cnt() { return s_cnt; }
import "C"

func foo() int {
    return int(C.s_cnt) + int(C.g_cnt) // error: undefined reference to `s_cnt'
    return int(C.get_c_cnt()) + int(C.g_cnt) // ok
}
```


### Go引用C

### C引用Go

### 传递指针

### 直接使用cgo

