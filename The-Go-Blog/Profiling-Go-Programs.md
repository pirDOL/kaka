## [Profiling Go Programs](https://blog.golang.org/profiling-go-programs)

24 June 2011 By Russ Cox, July 2011; updated by Shenghou Ma, May 2013

在2011年的Scala Days大会上，Robert Hundt展示了名字为[Loop Recognition in C++/Java/Go/Scala](http://research.google.com/pubs/pub37122.html)的论文，这篇论文实现了一种特定的循环识别算法，这种算法可以应用在比如C++、Java、Scala等编译器分析代码的过程中，通过分析得出程序哪里存在性能问题的结论。这篇论文中的Go程序运行的很慢，这就提供了一个很好的机会展示一下如何使用Go的性能分析工具来分析一个运行很慢的程序，并优化它的运行速度。

通过使用Go的性能分析工具来分析并优化特定的瓶颈，我们让Go语言的循环识别程序的运行速度快了一个数量级，同时减少了6倍的内存使用。（更新：由于最新gcc对libstdc++的优化，内存使用实际减少了3.7倍。）

Hundt的论文没有说明他使用了哪个版本的C++、Go、Java、Scala。本文我们使用Go编译器最新的周版本6g，g++编译器的版本是Ubuntu Natty发布版中默认自带的。我们不使用Java和Scala测试，因为我们不擅长用这两种语言编写高效率的程序，所以避免了比较不公平。因为C++是论文中执行最快的语言，Go和C++比较就足够了。（更新：博客更新的内容使用了最新的amd64开发版的Go编译器，以及2013年3月发布的g++ 4.8.0）
```
$ go version
go version devel +08d20469cc20 Tue Mar 26 08:27:18 2013 +0100 linux/amd64
$ g++ --version
g++ (GCC) 4.8.0
Copyright (C) 2013 Free Software Foundation, Inc.
...
$
```

测试程序运行环境为：3.4GHz Core i7-2600 CPU，16GB内存，3.8.4-gentoo版本内核。CPU频率动态调整是关闭的：
```
$ sudo bash
# for i in /sys/devices/system/cpu/cpu[0-7]
do
    echo performance > $i/cpufreq/scaling_governor
done
#
```

我们[从这里](https://github.com/hundt98847/multi-language-bench)获取到Hundt的测试程序，C++和Go分别用一个单文件实现，只保留一行循环识别结果的输出内容。我们使用linux的`time`命令测量程序的运行时间，格式化输出user、system、real时间以及内存的最大使用量。

C++程序执行时间为17.8秒，使用700MB内存，Go程序执行25.5秒，使用1302MB内存。这些测量结果和论文中的数据很难保存绝对一致，本文的目的是展示如何使用`go tool pprof`，而不是复现论文的结果。
```
$ cat xtime
#!/bin/sh
/usr/bin/time -f '%Uu %Ss %er %MkB %C' "$@"
$

$ make havlak1cc
g++ -O3 -o havlak1cc havlak1.cc
$ ./xtime ./havlak1cc
# of loops: 76002 (total 3800100)
loop-0, nest: 0, depth: 0
17.70u 0.05s 17.80r 715472kB ./havlak1cc
$

$ make havlak1
go build havlak1.go
$ ./xtime ./havlak1
# of loops: 76000 (including 1 artificial root node)
25.05u 0.11s 25.20r 1334032kB ./havlak1
$
```

在开始调优Go程序之前，我们需要启用性能分析功能。如果代码使用了[testing包](http://golang.org/pkg/testing/)的性能测试功能，我们可以直接使用`go test`的标准命令行参数`-cpuprofile`和`-memprofile`开启性能分析功能。但是对于独立的程序，例如这个循环识别算法程序，我们需要导入`runtime/pprof`，并添加几行代码：

新的代码定义了一个命令行参数`cpuprofile`，通过[flag包](http://golang.org/pkg/flag/)解析命令行参数，如果`cpuprofile`被设置了，就通过[StartCPUProfile](http://golang.org/pkg/runtime/pprof/#StartCPUProfile)开启CPU分析功能，并把输出打印到`cpuprofile`指定的文件中。性能分析器必须在程序退出之前时调用[StopCPUProfile](http://golang.org/pkg/runtime/pprof/#StopCPUProfile)把所有分析结果都写入文件。我们使用`defer`确保当`main`函数返回时，`StopCPUProfile`一定会被调用。
```golang
var cpuprofile = flag.String("cpuprofile", "", "write cpu profile to file")

func main() {
    flag.Parse()
    if *cpuprofile != "" {
        f, err := os.Create(*cpuprofile)
        if err != nil {
            log.Fatal(err)
        }
        pprof.StartCPUProfile(f)
        defer pprof.StopCPUProfile()
    }
    ...
```

添加了上面的代码以后，我们执行程序并增加`-cpuprofile`命令，然后用`go tool pprof`命令解析生成的profile文件。`go tool pprof`是Google的C++性能分析器[pprof](https://github.com/gperftools/gperftools)的变种。
```
$ make havlak1.prof
./havlak1 -cpuprofile=havlak1.prof
# of loops: 76000 (including 1 artificial root node)

$ go tool pprof havlak1 havlak1.prof
Welcome to pprof!  For help, type 'help'.
(pprof)
```

最常用的命令是`topN`，输出前N条CPU采样结果。当CPU性能分析打开时，Go程序每秒会暂停100次，对当前执行的goroutine栈的程序计数器的组成进行采样。下面的结果中共有2525条记录，和程序运行了25秒是吻合的。

**`topN`命令输出格式：**

1. 第一列：正在执行的函数（译者注：采样时位于栈顶的函数）的采样数。`topN`命令按照这列的值排序输出。
2. 第二列：第一列函数的采样数占全部采样数的百分比。例如：`runtime.mapaccess1_fast64`函数在298次采样中都是正在执行，占全部采样次数2525的11.8%。
3. 第三列：第二列的累加。例如：11.8% + 10.6% + 9.9% = 32.4%，即前三个函数占全部采样结果的32.4%。
4. 第四、五列：采样时只要在goroutine栈中出现的函数就累计（位于栈顶的函数就是正在执行，位于其他位置的函数就是等待调用返回），`-cum`选项可以按照第四列和第五列排序。例如：`main.FindLoops`函数在10.8%的采样中是正在执行状态，但是在84.1%的采样中都出现了这个函数。
4. 第六列：`go tool pprof`输出的最后一列就是在采样中出现的函数名字。

注：理论上`main.FindLoops`和`main.main`函数按照`-cum`选项输出的百分比应该是100%。但是因为每个goroutine最多采集前100个栈帧，所以有15%的采样因为`main.DFS`递归调用超过100层，导致`main.main`因为栈帧截断没有采集到。

```
(pprof) top10
Total: 2525 samples
     298  11.8%  11.8%      345  13.7% runtime.mapaccess1_fast64
     268  10.6%  22.4%     2124  84.1% main.FindLoops
     251   9.9%  32.4%      451  17.9% scanblock
     178   7.0%  39.4%      351  13.9% hash_insert
     131   5.2%  44.6%      158   6.3% sweepspan
     119   4.7%  49.3%      350  13.9% main.DFS
      96   3.8%  53.1%       98   3.9% flushptrbuf
      95   3.8%  56.9%       95   3.8% runtime.aeshash64
      95   3.8%  60.6%      101   4.0% runtime.settype_flush
      88   3.5%  64.1%      988  39.1% runtime.mallocgc

(pprof) top5 -cum
Total: 2525 samples
       0   0.0%   0.0%     2144  84.9% gosched0
       0   0.0%   0.0%     2144  84.9% main.main
       0   0.0%   0.0%     2144  84.9% runtime.main
       0   0.0%   0.0%     2124  84.1% main.FindHavlakLoops
     268  10.6%  10.6%     2124  84.1% main.FindLoops
```

goroutine堆栈采集结果除了可以用文本的方式展现，还可以展示为调用图，`web`命令可以把性能分析采集到的数据展示为SVG格式的图片，并用浏览器打开。类似，`gv`命令是转换为PostScript格式，用Ghostview打开。这两个命令都需要安装[graphviz](http://www.graphviz.org/)，[完整图片](https://rawgit.com/rsc/benchgraffiti/master/havlak/havlak1.svg)的一部分如下；

图中的每个方框对应一个单独的函数，方框的大小和函数在采样时位于栈顶的次数成正比。从X方框到Y方框的箭头表示X调用了Y，在箭头上的数字表示函数Y在采样时出现在栈帧中的次数。如果栈帧中一个函数出现了多次，例如递归函数调用，每次出现都会计数1次。例如：`main.DFS`这个方框指向自己的箭头上的数字为21342。

```
(pprof) web
```

![](Profiling-Go-Programs/profiling-go-programs_havlak1a-75.png)

一瞥即可发现，我们的程序在哈希操作上耗费了比较多的时间，哈希操作就是使用Go语言的`map`值。我们可以告诉`web`命令只显示特定函数的采样结果，例如`runtime.mapaccess1_fast64`，这样可以从图中过滤掉噪声。

```
(pprof) web mapaccess1
```

![](Profiling-Go-Programs/profiling-go-programs_havlak1-hash_lookup-75.png)

如果我们仔细看，我们可以发现`runtime.mapaccess1_fast64`是由`main.FindLoops`和`main.DFS`调用的。现在我们能够对程序慢的原因有一个粗略的想法，是时候具体到某一个函数上，让我们先来看`main.DFS`，先看它是因为它比较简短。

`list`展示了`DFS`函数的代码（实际上它会展示所有函数名能和`DFS`正则匹配的函数），**输出格式：**

1. 第一列：采样时正在执行对应行的次数
2. 第二列：采样时这行代码正在执行或者位于栈帧中
3. 第三列：代码在文件中的行号

另外，`disasm`命令可以展示函数的汇编指令，如果采样次数足够多，可以帮助你定位哪条汇编指令是热点。`weblist`命令则能混合显示汇编指令和Go代码，默认显示的是Go代码，用鼠标点击Go代码会显示汇编指令，具体见[这里](https://rawgit.com/rsc/benchgraffiti/master/havlak/havlak1.html)。

如果对比第二列数据，就可以知道大量的时间耗费在哈希函数实现的map查找上。大量的时间耗费在247行的`DFS`递归调用，这是符合预期的。除去这个函数，看起来剩下的时间花在了访问`number`这个map上，242行、246行、250行。对于这里的查询操作，map不是最有效的选择。`BasicBlock`结构体会被编译器赋予唯一的序列号，所以我们用`[]int`代替`map[*BasicBlock]int`，通block号索引查询。因为如果数组或者切片能够满足要求的话，没有理由用map。

把`number`从map修改为slice只需要[修改7行代码](https://github.com/rsc/benchgraffiti/commit/58ac27bcac3ffb553c29d0b3fb64745c91c95948)，程序的运行时间变成了原来的一半。

```
(pprof) list DFS
Total: 2525 samples
ROUTINE ====================== main.DFS in /home/rsc/g/benchgraffiti/havlak/havlak1.go
   119    697 Total samples (flat / cumulative)
     3      3  240: func DFS(currentNode *BasicBlock, nodes []*UnionFindNode, number map[*BasicBlock]int, last []int, current int) int {
     1      1  241:     nodes[current].Init(currentNode, current)
     1     37  242:     number[currentNode] = current
     .      .  243:
     1      1  244:     lastid := current
    89     89  245:     for _, target := range currentNode.OutEdges {
     9    152  246:             if number[target] == unvisited {
     7    354  247:                     lastid = DFS(target, nodes, number, last, lastid+1)
     .      .  248:             }
     .      .  249:     }
     7     59  250:     last[number[currentNode]] = lastid
     1      1  251:     return lastid
(pprof)

$ make havlak2
go build havlak2.go
$ ./xtime ./havlak2
# of loops: 76000 (including 1 artificial root node)
16.55u 0.11s 16.69r 1321008kB ./havlak2
$
```

我们再次执行性能分析工具，确认`main.DFS`不再是执行时间中的热点，`main.DFS`也不再在分析结果中出现了，相应的程序runtime的调用也减少了。现在程序的热点是内存的分配和垃圾回收，`runtime.mallocgc`实现内存分配以及定期执行垃圾回收，它占用了54.2%的时间。

```
$ make havlak2.prof
./havlak2 -cpuprofile=havlak2.prof
# of loops: 76000 (including 1 artificial root node)
$ go tool pprof havlak2 havlak2.prof
Welcome to pprof!  For help, type 'help'.
(pprof)
(pprof) top5
Total: 1652 samples
     197  11.9%  11.9%      382  23.1% scanblock
     189  11.4%  23.4%     1549  93.8% main.FindLoops
     130   7.9%  31.2%      152   9.2% sweepspan
     104   6.3%  37.5%      896  54.2% runtime.mallocgc
      98   5.9%  43.5%      100   6.1% flushptrbuf
(pprof)
```

为了定位为什么垃圾回收执行的这么频繁，我们需要知道是哪里在分配内存。一种方法就是增加内存分析工具，我们通过`-memprofile`命令行参数开启这个功能，程序在每次循环识别算法迭代时把内存分析结果写入文件，代码修改在[这里](https://github.com/rsc/benchgraffiti/commit/b78dac106bea1eb3be6bb3ca5dba57c130268232)。然后我们在执行程序时增加`-memprofile`。
```golang
var memprofile = flag.String("memprofile", "", "write memory profile to this file")
...

    FindHavlakLoops(cfgraph, lsgraph)
    if *memprofile != "" {
        f, err := os.Create(*memprofile)
        if err != nil {
            log.Fatal(err)
        }
        pprof.WriteHeapProfile(f)
        f.Close()
        return
    }

$ make havlak3.mprof
go build havlak3.go
./havlak3 -memprofile=havlak3.mprof
$
```

我们仍然使用`go tool pprof`命令分析profile文件，现在是按照内存分配来采样，而不是按照CPU时钟。根据分析结果我们发现，`FindLoops`分配了56.3MB的内存，整个程序占用了82.4MB，`CreateNode`占用了17.6MB。**为了减小内存分配时采样对程序的开销，内存分配的精度只能精确到0.5MB（`1-in-524288`），所以上面的数据是实际分配内存的近似值。**

>To reduce overhead, the memory profiler only records information for approximately one block per half megabyte allocated (the “1-in-524288 sampling rate”), so these are approximations to the actual counts.

```
$ go tool pprof havlak3 havlak3.mprof
Adjusting heap profiles for 1-in-524288 sampling rate
Welcome to pprof!  For help, type 'help'.
(pprof) top5
Total: 82.4 MB
    56.3  68.4%  68.4%     56.3  68.4% main.FindLoops
    17.6  21.3%  89.7%     17.6  21.3% main.(*CFG).CreateNode
     8.0   9.7%  99.4%     25.6  31.0% main.NewBasicBlockEdge
     0.5   0.6% 100.0%      0.5   0.6% itab
     0.0   0.0% 100.0%      0.5   0.6% fmt.init
(pprof)
```

为了定位是哪里分配了较多的内存，我们通过`list`命令显示`FindLoops`函数每一行分配内存的结果。看起来目前的瓶颈和CPU一样：在简单的数据结构能够满足要求的时误用了map。`FindLoops`函数中有29.5MB内存是map。
```
(pprof) list FindLoops
Total: 82.4 MB
ROUTINE ====================== main.FindLoops in /home/rsc/g/benchgraffiti/havlak/havlak3.go
  56.3   56.3 Total MB (flat / cumulative)
...
   1.9    1.9  268:     nonBackPreds := make([]map[int]bool, size)
   5.8    5.8  269:     backPreds := make([][]int, size)
     .      .  270:
   1.9    1.9  271:     number := make([]int, size)
   1.9    1.9  272:     header := make([]int, size, size)
   1.9    1.9  273:     types := make([]int, size, size)
   1.9    1.9  274:     last := make([]int, size, size)
   1.9    1.9  275:     nodes := make([]*UnionFindNode, size, size)
     .      .  276:
     .      .  277:     for i := 0; i < size; i++ {
   9.5    9.5  278:             nodes[i] = new(UnionFindNode)
     .      .  279:     }
...
     .      .  286:     for i, bb := range cfgraph.Blocks {
     .      .  287:             number[bb.Name] = unvisited
  29.5   29.5  288:             nonBackPreds[i] = make(map[int]bool)
     .      .  289:     }
...
```

另外，执行`go tool pprof`时增加`--inuse_objects`参数，按照“分配的采样次数”显示，不再按照内存大小显示。下图中288行被采样409600次，大约200000个map（译者注：为什么采样了4096000次表示分配了200000个map）占用了29.5MB，也就是说初始化map会消耗150字节的内存。如果map用于保存k-v对，这150字节的内存还是可以接受的，但是这里把map当作set使用，所以150字节的内存就显得有些多了（译者注：因为管理value相关的数据结构对应的内存浪费了）。
```
$ go tool pprof --inuse_objects havlak3 havlak3.mprof
Adjusting heap profiles for 1-in-524288 sampling rate
Welcome to pprof!  For help, type 'help'.
(pprof) list FindLoops
Total: 1763108 objects
ROUTINE ====================== main.FindLoops in /home/rsc/g/benchgraffiti/havlak/havlak3.go
720903 720903 Total objects (flat / cumulative)
...
     .      .  277:     for i := 0; i < size; i++ {
311296 311296  278:             nodes[i] = new(UnionFindNode)
     .      .  279:     }
     .      .  280:
     .      .  281:     // Step a:
     .      .  282:     //   - initialize all nodes as unvisited.
     .      .  283:     //   - depth-first traversal and numbering.
     .      .  284:     //   - unreached BB's are marked as dead.
     .      .  285:     //
     .      .  286:     for i, bb := range cfgraph.Blocks {
     .      .  287:             number[bb.Name] = unvisited
409600 409600  288:             nonBackPreds[i] = make(map[int]bool)
     .      .  289:     }
...
(pprof)
```

我们使用一个slice代替map，因为map可以实现不插入相同的元素，所以我们需要实现一个`append`函数的变体，来模拟map的这个功能：
```golang
func appendUnique(a []int, x int) []int {
    for _, y := range a {
        if x == y {
            return a
        }
    }
    return append(a, x)
}
```

实现了上面的函数以后，就可以把map替换为slice，只需要[修改几行代码](https://github.com/rsc/benchgraffiti/commit/245d899f7b1a33b0c8148a4cd147cb3de5228c8a)。现在程序比原来执行速度快了2.11倍。让我们再看一下CPU性能分析，现在内存分配和对应的垃圾回收`runtime.mallocgc`只占用的执行时间从54.2%降低到50.9%。
```
$ make havlak4
go build havlak4.go
$ ./xtime ./havlak4
# of loops: 76000 (including 1 artificial root node)
11.84u 0.08s 11.94r 810416kB ./havlak4
$

$ make havlak4.prof
./havlak4 -cpuprofile=havlak4.prof
# of loops: 76000 (including 1 artificial root node)
$ go tool pprof havlak4 havlak4.prof
Welcome to pprof!  For help, type 'help'.
(pprof) top10
Total: 1173 samples
     205  17.5%  17.5%     1083  92.3% main.FindLoops
     138  11.8%  29.2%      215  18.3% scanblock
      88   7.5%  36.7%       96   8.2% sweepspan
      76   6.5%  43.2%      597  50.9% runtime.mallocgc
      75   6.4%  49.6%       78   6.6% runtime.settype_flush
      74   6.3%  55.9%       75   6.4% flushptrbuf
      64   5.5%  61.4%       64   5.5% runtime.memmove
      63   5.4%  66.8%      524  44.7% runtime.growslice
      51   4.3%  71.1%       51   4.3% main.DFS
      50   4.3%  75.4%      146  12.4% runtime.MCache_Alloc
(pprof)
```

另一种分析“为什么系统在执行垃圾回收”的方法是查看哪里分配了内存，因为内存分配是导致垃圾回收的原因。通过`web mallocgc`查看相关的函数调用。

从下面的图中很难知道发生啥，因为很多方框中的采样值很小，从而干扰了较大方框的观察。我们通过下面的命令忽略小于10%采样值的方框，然后我们就可以很容易跟踪比较粗的箭头找到哪里分配了内存（译者注：其实是从`runtime.mallogc`倒着找，找到应用层的函数），`FindLoops`函数触发的垃圾回收次数最多，如果我们用`list`命令查看`FindLoops`，我们发觉这个函数还没啥很大的内存分配，每次调用时根据`size`参数动态分配一些用于记录状态的数据结构。但是如果考虑到这个函数被调用了50次，所以每次分配的内存累计起来就触发了比较多的垃圾回收。
```
$ go tool pprof --nodefraction=0.1 havlak4 havlak4.prof
Welcome to pprof!  For help, type 'help'.
(pprof) web mallocgc

(pprof) list FindLoops
...
     .      .  270: func FindLoops(cfgraph *CFG, lsgraph *LSG) {
     .      .  271:     if cfgraph.Start == nil {
     .      .  272:             return
     .      .  273:     }
     .      .  274:
     .      .  275:     size := cfgraph.NumNodes()
     .      .  276:
     .    145  277:     nonBackPreds := make([][]int, size)
     .      9  278:     backPreds := make([][]int, size)
     .      .  279:
     .      1  280:     number := make([]int, size)
     .     17  281:     header := make([]int, size, size)
     .      .  282:     types := make([]int, size, size)
     .      .  283:     last := make([]int, size, size)
     .      .  284:     nodes := make([]*UnionFindNode, size, size)
     .      .  285:
     .      .  286:     for i := 0; i < size; i++ {
     2     79  287:             nodes[i] = new(UnionFindNode)
     .      .  288:     }
...
(pprof)
```

![](Profiling-Go-Programs/profiling-go-programs_havlak4a-mallocgc.png)

![](Profiling-Go-Programs/profiling-go-programs_havlak4a-mallocgc-trim.png)

支持垃圾回收的语言并不意味着你可以忽略内存分配的问题。在这个例子中，最简单的解决方法是使用cache，每次调用`FindLoops`时会复用前一次调用时用于记录状态的数据结构。事实上，在Hundt的论文中，他解释了Java也需要类似的修改用于提高程序的性能，但是对于其他的垃圾回收语言，他没有做相同的实现。

我们实现一个全局的`cache`结构体，然后在`FindLoops`中查询它，如果`cache`的大小足够就使用它，否则重新分配。尽管全局变量是不好的工程实践，比如：并发调用`FindLoops`是不安全的。但是我们这里只是用最小的修改来印证程序性能瓶颈的分析结论，使用全局变量这种方法是比较简单，并且和Hundt的论文中Jave的实现能够类比。当然，也有其他的实现方式，比如把全局变量`cache`中的内容放到`LoopFinder`数据结构中，这样就能支持并发使用了。
```
var cache struct {
    size int
    nonBackPreds [][]int
    backPreds [][]int
    number []int
    header []int
    types []int
    last []int
    nodes []*UnionFindNode
}

if cache.size < size {
    cache.size = size
    cache.nonBackPreds = make([][]int, size)
    cache.backPreds = make([][]int, size)
    cache.number = make([]int, size)
    cache.header = make([]int, size)
    cache.types = make([]int, size)
    cache.last = make([]int, size)
    cache.nodes = make([]*UnionFindNode, size)
    for i := range cache.nodes {
        cache.nodes[i] = new(UnionFindNode)
    }
}

nonBackPreds := cache.nonBackPreds[:size]
for i := range nonBackPreds {
    nonBackPreds[i] = nonBackPreds[i][:0]
}
backPreds := cache.backPreds[:size]
for i := range nonBackPreds {
    backPreds[i] = backPreds[i][:0]
}
number := cache.number[:size]
header := cache.header[:size]
types := cache.types[:size]
last := cache.last[:size]
nodes := cache.nodes[:size]
```

代码修改在[这里](https://github.com/rsc/benchgraffiti/commit/2d41d6d16286b8146a3f697dd4074deac60d12a4)
```
$ make havlak5
go build havlak5.go
$ ./xtime ./havlak5
# of loops: 76000 (including 1 artificial root node)
8.03u 0.06s 8.11r 770352kB ./havlak5
$
```

还有一些其他的优化点可以提高程序的运行速度，因为它们都不需要性能分析工具，所以这里我们就展示了。例如：内部循环使用的work list可以在循环迭代之间以及`FindLoops`调用之间复用，and it can be combined with the separate “node pool” generated during that pass. 类似的，loop graph结构可以在每次迭代之间复用，而不用重复分配。实现这些优化以后，得到了最终版本的Go代码，使用了符合Go风格的数据结构和方法，这个修改对程序的运行时性能影响很小，核心的算法和约束都没有变化。

[最终版本](https://github.com/rsc/benchgraffiti/blob/master/havlak/havlak6.go)执行时间为2.29秒，使用351MB内存。比最开始的版本快了11倍，即使我们关闭loop graph复用策略，只保留一个循环查找记录作为cache，仍然是比最开始的版本快6.7倍，内存减少1.5倍。当然，把最终版本的Go程序和C++的未优化版本对比是不公平的，因为C++中也使用了一些不合理的数据结构，例如在vector能满足要求的地方使用了set。为了公平对比，我们把最终版本的Go程序翻译成[C++代码](https://github.com/rsc/benchgraffiti/blob/master/havlak/havlak6.cc)，执行时间和Go程序相似，只比Go略快一点。另外，C++版本自动分配和释放内存，而没有显式使用cache，所以C++程序比Go版本简短一些，也更容易实现（译者注：少了cache管理的代码），但是实际上从代码函数和字符数统计来看，并没有显著的差别。

>As the C++ program is using automatic deletes and allocation instead of an explicit cache, the C++ program a bit shorter and easier to write, but not dramatically so:

```
$ make havlak6
go build havlak6.go
$ ./xtime ./havlak6
# of loops: 76000 (including 1 artificial root node)
2.26u 0.02s 2.29r 360224kB ./havlak6
$

$ ./xtime ./havlak6 -reuseloopgraph=false
# of loops: 76000 (including 1 artificial root node)
3.69u 0.06s 3.76r 797120kB ./havlak6 -reuseloopgraph=false
$

$ make havlak6cc
g++ -O3 -o havlak6cc havlak6.cc
$ ./xtime ./havlak6cc
# of loops: 76000 (including 1 artificial root node)
1.99u 0.19s 2.19r 387936kB ./havlak6cc

$ wc havlak6.cc; wc havlak6.go
 401 1220 9040 havlak6.cc
 461 1441 9467 havlak6.go
$
```

Benchmarks are only as good as the programs they measure. 我们使用`go tool pprof`分析了一个效率不高的Go程序，最终把它的处理性能提高了一个数量级，并且减少了3.7倍的内存使用。和同等优化的C++程序对比，Go程序几乎不落下风，当然前提是程序员能够仔细处理内层循环生成的垃圾。

>A subsequent comparison with an equivalently optimized C++ program shows that Go can be competitive with C++ when programmers are careful about how much garbage is generated by inner loops.

程序源码、Linux x86-64的二进制、本文使用的profile文件都在Github的[ benchgraffiti项目中](https://github.com/rsc/benchgraffiti/)

如前文所述，[go test](http://golang.org/cmd/go/#Test_packages)命令已经包含了这些性能分析的命令行参数，只需要定义一个[benchmark函数](http://golang.org/pkg/testing/)就可以通过命令行参数获取benchmark函数执行过程中的性能分析结果了。

通过HTTP接口也可以拿到性能分析数据，只需要导入下面的包，会自动向这个URL`/debug/pprof`注册一些handler，然后通过`go tool pprof`命令加上一个URL参数就可以实时获取程序的profile文件。
```
import _ "net/http/pprof"

go tool pprof http://localhost:6060/debug/pprof/profile   # 30-second CPU profile
go tool pprof http://localhost:6060/debug/pprof/heap      # heap profile
go tool pprof http://localhost:6060/debug/pprof/block     # goroutine blocking profile
```

goroutine blocking profile会在未来的博客中单独介绍。Stay tuned.





