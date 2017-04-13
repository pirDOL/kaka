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
