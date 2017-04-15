## [Debugging Go Code with GDB](https://golang.org/doc/gdb)

### 译者注
加载runtime-gdb.py需要gdb支持python，具体方法参考[我的另一篇博客](https://github.com/pirDOL/100k-line-coding-project/tree/master/cpp/gdb-pretty-print)

go1.3编译的二进制用gdb调试时加载runtime-gdb.py，[Go扩展](https://golang.org/doc/gdb#Go_Extensions)中pretty print和info goroutines都不能正常使用。参考[github.com/golang/go issue-7796]升级为go1.6.3以后功能正常。

go1.3输出：
```
(gdb) source /home/work/learn/go/goroot/go1.3/src/pkg/runtime/runtime-gdb.py
Loading Go Runtime support.
(gdb) l main.main
16
17      package main
18
19      import "fmt"
20
21      func main() {
22              s := []int{1, 2}
23              fmt.Println(len(s))
24              fmt.Println(s)
25      }
(gdb) b 24
Breakpoint 1 at 0x400cc7: file /home/work/learn/go/gopath/src/hello/main.go, line 24.
(gdb) r
Starting program: /home/work/learn/go/gopath/src/hello/main 
2

Breakpoint 1, main.main () at /home/work/learn/go/gopath/src/hello/main.go:24
24              fmt.Println(s)
(gdb) p s
$1 =  []int = {4804096}
(gdb) info goroutines
Python Exception <class 'gdb.error'> Attempt to extract a component of a value that is not a (null).: 
Error occurred in Python command: Attempt to extract a component of a value that is not a (null).
```

go1.6.3输出：
```
(gdb) source /home/work/learn/go/goroot/go1.6.3/src/runtime/runtime-gdb.py    
Loading Go Runtime support.
(gdb) l main.main
16
17      package main
18
19      import "fmt"
20
21      func main() {
22              s := []int{1, 2}
23              fmt.Println(len(s))
24              fmt.Println(s)
25      }
(gdb) b 24
Breakpoint 1 at 0x401121: file /home/work/learn/go/gopath/src/hello/main.go, line 24.
(gdb) r
Starting program: /home/work/learn/go/gopath/src/hello/main 
2

Breakpoint 1, main.main () at /home/work/learn/go/gopath/src/hello/main.go:24
24              fmt.Println(s)
(gdb) p s
$1 =  []int = {1, 2}
(gdb) info goroutines
* 1 running  syscall.Syscall
  2 waiting  runtime.gopark
  3 waiting  runtime.gopark
  4 runnable runtime.runfinq
```

### 简介
当使用Linux、Mac OS X、FreeBSD、NetBSD平台上的gc工具链编译和链接Go程序时，生成的二进制包含了DWARFv3调试信息，这些调试信息可以被7.1版本以上的GDB用于调试执行中的进程或者core dump。

**链接时通过-w选项可以省略掉调试信息**，例如：`go build -ldflags "-w" prog.go`

gc编译器生成的代码包含了内联函数调用和寄存器优化的变量，这两个优化有时会增加gdb调试的难度。**go build通过选项`-gdflags "-N -l"`禁用这些优化**，生成可调试的二进制。

如果你想用gdb调试core dump，对于支持设置环境变量`GOTRACEBACK=crash`的平台，设置它触发程序的崩溃并dump，更多内容参考[runtime包文档](https://golang.org/pkg/runtime/#hdr-Environment_Variables)。

#### 常规操作
* 显示源码文件、行号，设置断点和反汇编：
```
(gdb) list
(gdb) list line
(gdb) list file.go:line
(gdb) break line
(gdb) break file.go:line
(gdb) disas
```

* 显示调用栈并跳转到某个帧

>Show backtraces and unwind stack frames

```
(gdb) bt
(gdb) frame n
```

* 显示当前栈上局部变量的名字、类型、函数参数和返回值
```
(gdb) info locals
(gdb) info args
(gdb) p variable
(gdb) whatis variable
```

* 显示全局变量的名字、类型和地址
```
(gdb) info variables regexp
```

#### Go扩展
gdb新版本提供了一个扩展机制，在调试一个二进制时加载扩展脚本，从而提供了很多gdb本身不支持的调试命令，从而实现对gdb功能的扩展。例如：打印goroutine、优雅打印Go内置的map、slice和channel。

如果你想知道扩展脚本的工作原理，或者想扩展其他的功能，请看Go源码发布包中的[src/runtime/runtime-gdb.py](https://golang.org/src/runtime/runtime-gdb.py)。这个脚本依赖于一些特殊的魔法类型`hash<T,U>`，[链接器src/cmd/link/internal/ld/dwarf.go](https://golang.org/src/cmd/link/internal/ld/dwarf.go)保证了变量`runtime.m`和`runtime.g`为DWARF码。如果你对调试信息究竟长成什么样子感兴趣，请看`objdump -W a.out`命令运行输出中`.debug_*`部分。

* 优雅打印string、map、channel、interface
```
(gdb) p var
```

* string、slice和map支持`$len()`和`$cap()`函数
```
(gdb) info variables regexp
```

* `$dtype()`把接口转换成运行时的动态类型
```
(gdb) p $dtype(var)
(gdb) iface var
```

    已知问题：如果长名字和短名字不同，gdb就无法显示接口类型的值的动态类型。令人烦恼的是，打印堆栈时短类型名字和指针不能被优雅打印。

* 调查goroutine
```
(gdb) info goroutines
(gdb) goroutine n cmd
(gdb) help goroutine

(gdb) goroutine 12 bt
```

#### 已知问题
1. string的优雅打印只能对string类型有效，通过`type T string`定义的类型T不行
2. runtime包的C部分代码的类型信息被省略了
3. gdb不支持Go的名字限定规则，例如：`fmt.Print`会被认为一个非结构化的字面值，字面值中的点会被引用。特别是对于`pkg.(*MyType).Meth`这种格式的方法名，gdb更不支持。
3. 所有的全局变量都会被集中到main包中

>1. String pretty printing only triggers for type string, not for types derived from it.
2. Type information is missing for the C parts of the runtime library.
3. GDB does not understand Go’s name qualifications and treats "fmt.Print" as an unstructured literal with a "." that needs to be quoted. It objects even more strongly to method names of the form pkg.(*MyType).Meth.
4. All global variables are lumped into package "main".

### 教程
这个教程我们会调查[regexp包](https://golang.org/pkg/regexp/)的二进制单测，编译方法：`cd $GOROOT/src/regexp && go test -c`，成功的话会生成名字为regexp.test的可执行文件。

#### 开始
启动gdb调试regexp.test：
```
$ gdb regexp.test
GNU gdb (GDB) 7.2-gg8
Copyright (C) 2010 Free Software Foundation, Inc.
License GPLv  3+: GNU GPL version 3 or later <http://gnu.org/licenses/gpl.html>
Type "show copying" and "show warranty" for licensing/warranty details.
This GDB was configured as "x86_64-linux".

Reading symbols from  /home/user/go/src/regexp/regexp.test...
done.
Loading Go Runtime support.
(gdb) 
```

`Loading Go Runtime support`信息表示gdb成功加载了扩展`$GOROOT/src/runtime/runtime-gdb.py`。

帮助gdb找到Go的运行时代码以及相关的脚本，在启动gdb时用-d选项指定$GOROOT：
```
$ gdb regexp.test -d $GOROOT
```

如果因为一些原因gdb不能找到GOROOT目录或者runtime-gdb.py脚本，**你可以通过source命令手动加载**，假如Go的源码位于~/go/：
```
(gdb) source ~/go/src/runtime/runtime-gdb.py
Loading Go Runtime support.
```

#### 查看源码
用`l`或者`list`命令查看源码：
```
(gdb) l
```

查看指定部分的源码可以在`list`命令后面加上函数名字，函数名前面必须加包名：
```
(gdb) l main.main
```

查看指定文件或者行号：
```
(gdb) l regexp.go:1
(gdb) # Hit enter to repeat last command. Here, this lists next 10 lines.
```

#### 命名
**变量和函数名前面必须加它们所属的包名**，`regexp`包中的`Compile`函数在gdb中的名字是`regexp.Compile`。

**方法名字前面必须就加上它的接收者类型**，例如`*Regexp`类型的`String`方法在gdb中的名字是`regexp.(*Regexp).String`。

当变量名因为同名和作用域发生隐藏时，调试信息中的变量名后面会带一个数字后缀。闭包引用的变量名会作为指针出现，变量名前面会增加一个&前缀。

#### 设置断点
在`TestFind`函数设置断点：
```
(gdb) b 'regexp.TestFind'
Breakpoint 1 at 0x424908: file /home/user/go/src/regexp/find_test.go, line 148.
```

运行程序：
```
(gdb) run
Starting program: /home/user/go/src/regexp/regexp.test

Breakpoint 1, regexp.TestFind (t=0xf8404a89c0) at /home/user/go/src/regexp/find_test.go:148
148 func TestFind(t *testing.T) {
```

程序执行在断点位置停止，查看哪个goroutine在执行（前面标记了*的goroutine）以及它调用的函数：
```
(gdb) info goroutines
  1  waiting runtime.gosched
* 13  running runtime.goexit
```

#### 查看堆栈
查看我们设置的断点时的堆栈信息：
```
(gdb) bt  # backtrace
#0  regexp.TestFind (t=0xf8404a89c0) at /home/user/go/src/regexp/find_test.go:148
#1  0x000000000042f60b in testing.tRunner (t=0xf8404a89c0, test=0x573720) at /home/user/go/src/testing/testing.go:156
#2  0x000000000040df64 in runtime.initdone () at /home/user/go/src/runtime/proc.c:242
#3  0x000000f8404a89c0 in ?? ()
#4  0x0000000000573720 in ?? ()
#5  0x0000000000000000 in ?? ()
```

另一个编号为1的goroutine阻塞在`runtime.gosched`上，等待从channel接收：
```
(gdb) goroutine 1 bt
#0  0x000000000040facb in runtime.gosched () at /home/user/go/src/runtime/proc.c:873
#1  0x00000000004031c9 in runtime.chanrecv (c=void, ep=void, selected=void, received=void)
 at  /home/user/go/src/runtime/chan.c:342
#2  0x0000000000403299 in runtime.chanrecv1 (t=void, c=void) at/home/user/go/src/runtime/chan.c:423
#3  0x000000000043075b in testing.RunTests (matchString={void (struct string, struct string, bool *, error *)}
 0x7ffff7f9ef60, tests=  []testing.InternalTest = {...}) at /home/user/go/src/testing/testing.go:201
#4  0x00000000004302b1 in testing.Main (matchString={void (struct string, struct string, bool *, error *)} 
 0x7ffff7f9ef80, tests= []testing.InternalTest = {...}, benchmarks= []testing.InternalBenchmark = {...})
at /home/user/go/src/testing/testing.go:168
#5  0x0000000000400dc1 in main.main () at /home/user/go/src/regexp/_testmain.go:98
#6  0x00000000004022e7 in runtime.mainstart () at /home/user/go/src/runtime/amd64/asm.s:78
#7  0x000000000040ea6f in runtime.initdone () at /home/user/go/src/runtime/proc.c:243
#8  0x0000000000000000 in ?? ()
```

栈帧显示了我们正在执行`regexp.TestFind`函数，和实际情况一致：
```
(gdb) info frame
Stack level 0, frame at 0x7ffff7f9ff88:
 rip = 0x425530 in regexp.TestFind (/home/user/go/src/regexp/find_test.go:148); 
    saved rip 0x430233
 called by frame at 0x7ffff7f9ffa8
 source language minimal.
 Arglist at 0x7ffff7f9ff78, args: t=0xf840688b60
 Locals at 0x7ffff7f9ff78, Previous frame's sp is 0x7ffff7f9ff88
 Saved registers:
  rip at 0x7ffff7f9ff80
```

`info locals`命令列出当前函数的所有局部变量和它们的值，但是使用时会有些危险，因为这个命令会尝试打印未初始化的变量，未初始化的slice可能会导致gdb打印任意长度的数组。

打印函数参数：
```
(gdb) info args
t = 0xf840688b60
```

当打印函数参数时，注意它是一个指向`testing.T`类型的指针（译者注：原文这里是指向`Regexp`类型的指针，根据上下文`regexp.TestFind`函数的参数是`testing.T`类型的指针）。注意：gdb使用C风格的指针类型顺序，也就是把*放在类型名的右边，还带有一个struct关键字。
```
(gdb) p re
(gdb) p t
$1 = (struct testing.T *) 0xf840688b60
(gdb) p t
$1 = (struct testing.T *) 0xf840688b60
(gdb) p *t
$2 = {errors = "", failed = false, ch = 0xf8406f5690}
(gdb) p *t->ch
$3 = struct hchan<*testing.T>
```

`struct hchan<*testing.T>`是channel运行时的内部数据结构，当前它的值为空，否则gdb会打印它的内容。

继续：
```
(gdb) n  # execute next line
149             for _, test := range findTests {
(gdb)    # enter is repeat
150                     re := MustCompile(test.pat)
(gdb) p test.pat
$4 = ""
(gdb) p re
$5 = (struct regexp.Regexp *) 0xf84068d070
(gdb) p *re
$6 = {expr = "", prog = 0xf840688b80, prefix = "", prefixBytes =  []uint8, prefixComplete = true, 
  prefixRune = 0, cond = 0 '\000', numSubexp = 0, longest = false, mu = {state = 0, sema = 0}, 
  machine =  []*regexp.machine}
(gdb) p *re->prog
$7 = {Inst =  []regexp/syntax.Inst = {{Op = 5 '\005', Out = 0, Arg = 0, Rune =  []int}, {Op = 
    6 '\006', Out = 2, Arg = 0, Rune =  []int}, {Op = 4 '\004', Out = 0, Arg = 0, Rune =  []int}}, 
  Start = 1, NumCap = 2}
```

`s`命令我们step info到`String`函数：
```
(gdb) s
regexp.(*Regexp).String (re=0xf84068d070, noname=void) at /home/user/go/src/regexp/regexp.go:97
97      func (re *Regexp) String() string {
```

通过打印堆栈看到程序当前的位置：
```
(gdb) bt
#0  regexp.(*Regexp).String (re=0xf84068d070, noname=void)
    at /home/user/go/src/regexp/regexp.go:97
#1  0x0000000000425615 in regexp.TestFind (t=0xf840688b60)
    at /home/user/go/src/regexp/find_test.go:151
#2  0x0000000000430233 in testing.tRunner (t=0xf840688b60, test=0x5747b8)
    at /home/user/go/src/testing/testing.go:156
#3  0x000000000040ea6f in runtime.initdone () at /home/user/go/src/runtime/proc.c:243
....
```

查看当前运行位置的源码：
```
(gdb) l
92              mu      sync.Mutex
93              machine []*machine
94      }
95
96      // String returns the source text used to compile the regular expression.
97      func (re *Regexp) String() string {
98              return re.expr
99      }
100
101     // Compile parses a regular expression and returns, if successful,
```

#### 优雅打印
gdb的优雅打印是由类型名的正则匹配触发的，例如：slice
```
(gdb) p utf
$22 =  []uint8 = {0 '\000', 0 '\000', 0 '\000', 0 '\000'}
```

**因为slice、array、string都不是C指针，gdb不能解析这些类型的下标操作命令，但是你可以通过tab查看它们运行时的内部成员array来实现下标操作**：
```
(gdb) p slc
$11 =  []int = {0, 0}
(gdb) p slc-><TAB>
array  slc    len    
(gdb) p slc->array
$12 = (int *) 0xf84057af00
(gdb) p slc->array[1]
$13 = 0
```

扩展函数`$len`和`$cap`支持string、array、slice：
```
(gdb) p $len(utf)
$23 = 4
(gdb) p $cap(utf)
$24 = 4
```

channel和map是引用类型，gdb会以类C++指针`hash<int,string>*`的类型打印它们，**对channel和map解引用会触发优雅打印**。
```
(gdb) b 24
Breakpoint 1 at 0x40101f: file /home/work/learn/go/gopath/src/gdb/main.go, line 24.
(gdb) r
Starting program: /home/work/learn/go/gopath/src/gdb/main 

Breakpoint 1, main.main () at /home/work/learn/go/gopath/src/gdb/main.go:24
24              ch := make(chan int)
(gdb) n
25              m := make(map[string]int)
(gdb) n
26              m["1"] = 1
(gdb) p m
$1 = (map[string]int) 0xc820000180
(gdb) p *m
$2 = {count = 859530600448, flags = 192 'B = 63 '?', hash0 = 200, buckets = 0xc8200422d0, oldbuckets = 0xffffffffffffffff, nevacuate = 0, overflow = 0xc820014100}
(gdb) p ch
$3 = (chan int) 0xc82005e060
(gdb) p *ch
$4 = {qcount = 0, dataqsiz = 0, buf = 0xc82005e060, elemsize = 8, closed = 0, elemtype = 0x4b8480, sendx = 0, recvx = 0, recvq = {first = 0x0, last = 0x0}, sendq = {first = 0x0, 
    last = 0x0}, lock = {key = 0}}
```

interface在运行时的表示是一个指向类型描述符的指针和一个指向值的指针。Go的gdb运行时扩展会自动解析这两个指针并优雅打印它们的内容。`$dtype`扩展函数可以对动态类型解码，下面的例子来自于regexp.go的293行。
```
(gdb) p i
$4 = {str = "cbb"}
(gdb) whatis i
type = regexp.input
(gdb) p $dtype(i)
$26 = (struct regexp.inputBytes *) 0xf8400b4930
(gdb) iface i
regexp.input: struct regexp.inputBytes *
```