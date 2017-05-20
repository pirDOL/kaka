## [Gccgo in GCC 4.7.1](https://blog.golang.org/gccgo-in-gcc-471)

Ian Lance Taylor

[参考翻译](http://studygolang.com/articles/535)

Go语言是一门以[语言规范spec](http://golang.org/ref/spec)而不是具体实现来定义的语言。Go的开发小组编写了两个不同的编译器实现Go语言的spec：gc和gccgo。拥有两种编译器实现确保了Go语言的spec的完整性和正确性：当两个编译器出现分歧时，我们会修改spec或者修改编译器实现。gc是最原始的编译器，go tool默认使用这个编译器。gccgo则是一种不同的实现，这篇文章会详细讨论gccgo实现的侧重点。

gccgo作为GNU编译工具集（GNU Compiler Collection）GCC的一部分发布。GCC支持若干种不同的前端，每个前端对应一种语言，gccgo就是Go语言的一种前端编译工具，连接到后端编译工具。Go语言的前端编译工具和GCC是解耦的，设计Go的前端编译工具时考虑了能够连接到不同的后端编译工具，目前后端编译工具只支持GCC。（译者注：我理解前端编译工具gccgo是把Go转换成C/C++，然后后端编译工具gcc、clang等再编译成二进制。）

和gc比较，gccgo编译速度更慢，但是支持更强大的编译优化。所以gccgo编译出的CPU密集型程序执行速度更快。GCC这些年实现的编译优化gccgo都能使用，例如内联、循环优化、向量化、指令调度等等。尽管gccgo没有生成更好的代码，但是在某些情况下，gccgo编译出的程序执行速度快30%。

gc编译器只支持主流的处理器：x86（32位、64位）和ARM，然后gccgo支持所有GCC支持的处理器，目前gccgo已经在x86（32位、64位）、SPARC、MIPS、PowerPC、Alpha这些处理器上完成了测试。另外，gccgo还测试了gc编译器不支持的操作系统，代表性的比如Solaris。

gccgo提供了标准、完整的Go库。gccgo和gc在Go运行时很多的核心特性上保持了一致，比如goroutine调度器、channel、内存分配器、垃圾收集器，gccgo也支持gc的goroutine动态堆栈的功能，但是目前仅限于x86（32位、64位）平台，并且必须使用gold链接器。在其它处理器上，每个goroutine还是会分配一个大的栈，如果出现深度的函数嵌套调用会导致堆栈溢出）。

>Gccgo supports splitting goroutine stacks as the gc compiler does, but currently only on x86 (32-bit or 64-bit) and only when using the gold linker (on other processors, each goroutine will have a large stack, and a deep series of function calls may run past the end of the stack and crash the program).

gccgo发布包中还没有包含go命令，如果你使用的是标准Go发布版中的go命令，它已经支持通过`-compiler`选项选择gccgo编译器：`go build -compiler gccgo myprog`。Go和C/C++之间相互调用的工具：cgo和SWIG也支持gccgo。

我们把已经将针对GCC的Go前端编译工具gofrontend采用和Go工具相同的BSD许可证发布。你可以从[这里](http://code.google.com/p/gofrontend)下载它的代码。注意当编译gccgo时，gofrontend前端的代码需要和GCC后端编译工具链接，因为GCC是GPL许可证，它的优先级比BSD许可证高。

>Note that when the Go frontend is linked with the GCC backend to make gccgo, GCC GPL license takes precedence.

最新发布的GCC 4.7.1包含了支持Go1的gccgo。如果你需要性能更好的CPU密集型的Go程序或者你需要在gc不支持的处理器和操作系统共，gccgo是你的菜。