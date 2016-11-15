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
    return int(C.get_s_cnt()) + int(C.g_cnt) // ok
}
```

$GOROOT/misc/cgo/stdio和$GOROOT/misc/cgo/gmp里面提供了一些例子. [C? Go? Cgo!](https://blog.golang.org/c-go-cgo)中介绍了cgo的使用。

通过#cgo伪指令可以定义CFLAGS、CPPFLAGS、CXXFLAGS、FFLAGS和LDFLAGS，用于调整C、C++、Fortran编译器。定义在多行中的指令会被连接起来。指令可以包含编译时的约束列表，约束可以只对特定的平台生效（[更多关于约束语法的细节](https://golang.org/pkg/go/build/#hdr-Build_Constraints )）。例如：
```go
// #cgo CFLAGS: -DPNG_DEBUG=1
// #cgo amd64 386 CFLAGS: -DX86=1
// #cgo LDFLAGS: -lpng
// #include <png.h>
import "C"
```

还有一种获取CPPFLAGS和LDFLAGS的方法是使用pkg-config工具，把包名字跟在#cgo pkg-config指令后面。
```go
// #cgo pkg-config: png cairo
// #include <png.h>
import "C"
```

当编译时会根据cgo指令生成CGO_CFLAGS、CGO_CPPFLAGS、CGO_CXXFLAGS、CGO_FFLAGS和CGO_LDFLAGS这些环境变量。如果不同的包需要不同的编译选项，应该通过cgo命令差异化配置，不要使用环境变量，这样当迁移到其他环境编译时可以不需要额外配置环境。

一个包中的所有通过cgo指令定义的CPPFLAGS和CFLAGS选项会被合并起来，作为编译包的C文件时使用；CPPFLAGS和CXXFLAGS同理也会合并起来编译C++文件；CPPFLAGS和FFLAGS合并后用于编译Fortran。所有包中的LDFLAGS会被合并起来在链接时使用。通过pkg-config指令定义的包也会合并，然后添加到相应的编译选项中。

当分析cgo命令时，所有的${SRCDIR}会被替换成当前文件所在的绝对路径，这使得预先编译好的静态库可以正确的包含以及链接。例如：如果一个包foo位于/go/src/foo目录，那么下面的代码会被解析为：
```go
// #cgo LDFLAGS: -L${SRCDIR}/libs -lfoo
// #cgo LDFLAGS: -L/go/src/foo/libs -lfoo
```

当Go工具发现包含特殊的import "C"语句的Go文件时，它会找非Go文件，然后把它们编译成这个Go包的一部分。.c .s .S文件会用C编译器编译；.cc .cpp .cxx文件会用C++编译器编译；.f .F .for .f90文件会用fortran编译器编译。.h .hh .hpp .hxx文件会不单独编译，如果这些文件发生了变化，对应的C和C++文件会被重新编译。默认的C和C++编译器可以通过CC和CXX环境变量设置，当然也可以在命令行选项中包含这些环境变量。

cgo工具默认关闭交叉编译，将CGO_ENABLED环境变量设置为1可以开启cgo的交叉编译，0则关闭。The go tool will set the build constraint "cgo" if cgo is enabled.

当交叉编译时，你必须指定一个C交叉编译器，在构建工具链时通过设置CC_FOR_TARGET变量或者在运行cgo时设置环境变量CC都可以修改cgo使用的C编译器，同理C++交叉编译器对应的环境变量是CXX_FOR_TARGET和CXX。

### Go引用C

### C引用Go
Go函数可以导出给C代码使用，对应的C代码如下：
```
//export MyFunction
func MyFunction(arg1, arg2 int, arg3 string) int64 {...}

//export MyFunction2
func MyFunction2(arg1, arg2 int, arg3 string) (int64, *C.char) {...}

extern int64 MyFunction(int arg1, int arg2, GoString arg3);
extern struct MyFunction2_return MyFunction2(int arg1, int arg2, GoString arg3);
```

cgo把所有的输入文件从前言（import "C"前的注释）拷贝进来以后，会把C代码生成到\_cgo_export.h这个文件中。有多个返回值的Go函数被映射为一个返回struct的函数。有的Go类型不能优雅的映射到C类型。

如果前言包含的文件中有export会带来一些约束：因为前言的文件会被拷贝到两个不同的C语言输出文件中，所以前言中的文件不能包含任何定义，只能包含声明。如果一个文件包含定义和声明，那么生成的两个输出文件中会因为重复的符号导致链接失败。为了避免这一点，*definitions must be placed in preambles in other files*，或者把定义放在C源码文件中

### 传递指针
Go是一个垃圾回收语言，垃圾回收器需要保存所有指向Go内存的指针的地址。因此，在Go和C之间传递指针会有很多限制。

这里Go指针指的是指向通过Go分配的内存的指针（例如使用&操作符或者使用new函数），C指针指的是C分配的内存的指针（例如通过C.malloc）。一个指针是Go指针还是C指针取决于内存如何分配，和指针的类型无关。

Go代码向C传递Go指针时需要保证Go指针指向的内存中不包含Go指针。C代码也需要遵守这个约束：不能向传入的Go指针对应的内存中存Go指针，即使是暂时的也不行。当传给C的Go指针指向结构体的字段时，对应的Go内存是这个字段的内存，而不是整个结构体。当传递的Go指针指向的是数组或者切片时，Go内存是整个数组或者切片背后的数组。

C代码在返回以后可能不会再保存Go指针的拷贝。

C代码调用Go函数时不能返回Go指针。C代码调用Go函数时，如果Go函数接受C指针作为参数，可以向C指针指向的内存中存储非指针和C指针类型的数据，不能存内容是Go指针的C指针；如果Go函数接受Go指针参数，必须保证这个Go指针指向的内存中不能包含其他的Go指针。

Go代码不能向C内存中存Go指针，C代码可以在C内存中存Go指针，但是当C函数返回以后就不能再向C内存中存储Go指针了。

>Go code may pass a Go pointer to C provided the Go memory to which it points does not contain any Go pointers. The C code must preserve this property: it must not store any Go pointers in Go memory, even temporarily. When passing a pointer to a field in a struct, the Go memory in question is the memory occupied by the field, not the entire struct. When passing a pointer to an element in an array or slice, the Go memory in question is the entire array or the entire backing array of the slice.

>C code may not keep a copy of a Go pointer after the call returns.

>A Go function called by C code may not return a Go pointer. A Go function called by C code may take C pointers as arguments, and it may store non-pointer or C pointer data through those pointers, but it may not store a Go pointer in memory pointed to by a C pointer. A Go function called by C code may take a Go pointer as an argument, but it must preserve the property that the Go memory to which it points does not contain any Go pointers.

>Go code may not store a Go pointer in C memory. C code may store Go pointers in C memory, subject to the rule above: it must stop storing the Go pointer when the C function returns.

上面这些规则是在运行时动态检查的，通过设置GODEBUG环境变量来控制cgocheck的检查。默认设置是GODEBUG=cgocheck=1，它的行为是进行简单廉价的动态检查；GODEBUG=cgocheck=0则关闭所有检查；GODEBUG=cgochec=2是开启全部的指针检查，这回造成运行时间的开销。

对于上面的种种限制，都可以使用unsafe包来打破，因为对于C语言来说，没法阻止它做任何事情。显然，不遵守上面的这些规则会导致程序异常终止或者以非预期的方式执行。

### 直接使用cgo
使用：
```
go tool cgo [cgo options] [-- compiler options] gofiles...
```

cgo把输入指定的Go文件转换成多个Go和C文件输出。当调用C编译器编译Go包的C语言部分时，通过uninterpreted来传递编译器选项（原文：The compiler options are passed *through uninterpreted* when invoking the C compiler to compile the C parts of the package.）。

下面是可以使用的cgo选项：
```
-dynimport file
    Write list of symbols imported by file. Write to
    -dynout argument or to standard output. Used by go
    build when building a cgo package.
-dynout file
    Write -dynimport output to file.
-dynpackage package
    Set Go package for -dynimport output.
-dynlinker
    Write dynamic linker as part of -dynimport output.
-godefs
    Write out input file in Go syntax replacing C package
    names with real values. Used to generate files in the
    syscall package when bootstrapping a new target.
-objdir directory
    Put all generated files in directory.
-importpath string
    The import path for the Go package. Optional; used for
    nicer comments in the generated files.
-exportheader file
    If there are any exported functions, write the
    generated export declarations to file.
    C code can #include this to see the declarations.
-gccgo
    Generate output for the gccgo compiler rather than the
    gc compiler.
-gccgoprefix prefix
    The -fgo-prefix option to be used with gccgo.
-gccgopkgpath path
    The -fgo-pkgpath option to be used with gccgo.
-import_runtime_cgo
    If set (which it is by default) import runtime/cgo in
    generated output.
-import_syscall
    If set (which it is by default) import syscall in
    generated output.
-debug-define
    Debugging option. Print #defines.
-debug-gcc
    Debugging option. Trace C compiler execution and output.
```