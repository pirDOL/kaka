## [Using Subtests and Sub-benchmarks](https://blog.golang.org/subtests)

3 October 2016 By Marcel van Lohuizen

### 简介
Go 1.7中，testing包通过对[T类型](https://golang.org/pkg/testing/#T.Run)和[B类型](https://golang.org/pkg/testing/#B.Run)增加`Run`方法支持了子测试和子性能测试。这个特性的引入使得测试执行失败能够更好的处理，通过命令行参数可以细粒度的控制执行哪个测试，最终的结果是编写更简单和更容易维护的代码。

### 表格驱动测试（Table-driven  test）基础
在深入子测试和子性能测试之前，让我们先讨论一下Go语言中测试的通常写法。通过遍历一个测试用例的slice可以实现一系列的结果检查。这个方法通常被叫做“表哥驱动测试”，它能够减少重复的代码（检查每个测试用例执行结果的代码）。同时对于增加行的测试用例也更直接。
```golang
func TestTime(t *testing.T) {
    testCases := []struct {
        gmt  string
        loc  string
        want string
    }{
        {"12:31", "Europe/Zuri", "13:31"},     // incorrect location name
        {"12:31", "America/New_York", "7:31"}, // should be 07:31
        {"08:08", "Australia/Sydney", "18:08"},
    }
    for _, tc := range testCases {
        loc, err := time.LoadLocation(tc.loc)
        if err != nil {
            t.Fatalf("could not load location %q", tc.loc)
        }
        gmt, _ := time.Parse("15:04", tc.gmt)
        if got := gmt.In(loc).Format("15:04"); got != tc.want {
            t.Errorf("In(%s, %s) = %s; want %s", tc.gmt, tc.loc, got, tc.want)
        }
    }
}
```

### 表格驱动性能测试
在Go 1.7之前是不能用相同的表格驱动测试的方法实现性能测试，因为一次性能测试是计算一个被测试函数的执行时间，所以如果像单测那样多个测试用例遍历，执行时间计算的是左右测试用例的执行时间。

这个问题常见的一个解决方式是对不同的测试用例参数，定义不同的顶层性能测试（译者注：顶层性能测试指的是_test.go文件中以`Benchmark`开头的函数），这些性能测试之间就是隔离的，除了调用相同的被测试函数以外。例如，在1.7之前，strconv包的AppendFloat函数的性能测试看起来是这样的：
```golang
func benchmarkAppendFloat(b *testing.B, f float64, fmt byte, prec, bitSize int) {
    dst := make([]byte, 30)
    b.ResetTimer() // Overkill here, but for illustrative purposes.
    for i := 0; i < b.N; i++ {
        AppendFloat(dst[:0], f, fmt, prec, bitSize)
    }
}

func BenchmarkAppendFloatDecimal(b *testing.B) { benchmarkAppendFloat(b, 33909, 'g', -1, 64) }
func BenchmarkAppendFloat(b *testing.B)        { benchmarkAppendFloat(b, 339.7784, 'g', -1, 64) }
func BenchmarkAppendFloatExp(b *testing.B)     { benchmarkAppendFloat(b, -5.09e75, 'g', -1, 64) }
func BenchmarkAppendFloatNegExp(b *testing.B)  { benchmarkAppendFloat(b, -5.11e-95, 'g', -1, 64) }
func BenchmarkAppendFloatBig(b *testing.B)     { benchmarkAppendFloat(b, 123456789123456789123456789, 'g', -1, 64) }
...
```

使用Go 1.7引入的`testing.B.Run`方法，相同的性能测试集合可以用一个顶层的性能测试实现，每次调用`Run`方法时都会创建一个单独的性能测试，调用`Run`方法的外围顶层性能测试只会执行一次，它的执行过程不会被计时。

使用子性能测试的代码行数增加了一些，但是更容易维护、可读性更强、和“表格驱动测试”的测试常规方法一致性更好。另外，子性能测试之间可以共享相同的准备测试环境的代码，同时子性能测试执行之间也不需要测试代码显式的复位计时器。
```golang
func BenchmarkAppendFloat(b *testing.B) {
    benchmarks := []struct{
        name    string
        float   float64
        fmt     byte
        prec    int
        bitSize int
    }{
        {"Decimal", 33909, 'g', -1, 64},
        {"Float", 339.7784, 'g', -1, 64},
        {"Exp", -5.09e75, 'g', -1, 64},
        {"NegExp", -5.11e-95, 'g', -1, 64},
        {"Big", 123456789123456789123456789, 'g', -1, 64},
        ...
    }
    dst := make([]byte, 30)
    for _, bm := range benchmarks {
        b.Run(bm.name, func(b *testing.B) {
            for i := 0; i < b.N; i++ {
                AppendFloat(dst[:0], bm.float, bm.fmt, bm.prec, bm.bitSize)
            }
        })
    }
}
```

### 使用子测试的表格驱动测试
Go 1.7通过`Run`方法可以实现表格驱动子测试，“表格驱动测试基础”一节中的例子用`Run`方法重写如下：
```golang
func TestTime(t *testing.T) {
    testCases := []struct {
        gmt  string
        loc  string
        want string
    }{
        {"12:31", "Europe/Zuri", "13:31"},
        {"12:31", "America/New_York", "7:31"},
        {"08:08", "Australia/Sydney", "18:08"},
    }
    for _, tc := range testCases {
        t.Run(fmt.Sprintf("%s in %s", tc.gmt, tc.loc), func(t *testing.T) {
            loc, err := time.LoadLocation(tc.loc)
            if err != nil {
                t.Fatal("could not load location")
            }
            gmt, _ := time.Parse("15:04", tc.gmt)
            if got := gmt.In(loc).Format("15:04"); got != tc.want {
                t.Errorf("got %s; want %s", got, tc.want)
            }
        })
    }
}
```

**首先需要注意的是两种实现方式在输出格式上的差别：**

* 第一种实现方式尽管有两个测试用例会执行失败，但是当执行到第一个测试用例时，因为调用了`Fatalf`导致整个顶层测试执行结束，第二个测试用例根本不会被执行。
* 使用`Run`方法输出会把两个测试用例都执行，`Fatal`系列的方法会导致一个子测试被跳过，这个子测试所属的顶层测试以及其他的子测试都不会受影响。除此之外，子测试输出的信息更简短，因为通过子测试的名字可以唯一确定一个子测试，所以在测试错误信息中没必要再加入子测试的上下文信息。

下面会继续说明使用子测试和子性能测试的其他好处。

```
--- FAIL: TestTime (0.00s)
    time_test.go:62: could not load location "Europe/Zuri"

--- FAIL: TestTime (0.00s)
    --- FAIL: TestTime/12:31_in_Europe/Zuri (0.00s)
        time_test.go:84: could not load location
    --- FAIL: TestTime/12:31_in_America/New_York (0.00s)
        time_test.go:88: got 07:31; want 7:31
```

### 执行指定的单测和性能测试
子测试和子性能测试可以通过命令行参数[-run/-bench](https://golang.org/cmd/go/#hdr-Description_of_testing_flags)单独选出，这两个选项的参数是用`/`隔开的正则表达式，用于匹配子测试和子性能测试的名字中相应的部分。（译者注：子测试完整的名字包含多个部分，这些部分之间也是用`/`隔开的。）

子测试和子性能测试的完整的名字为：顶层测试的名字/子测试（子性能测试）的名字。顶层测试的名字就是`Test`或`Benchmark`开头的函数名，子测试（子性能测试）的名字是`Run`方法的第一个参数。为了避免显示和解析的问题，名字会做如下处理：空格用下划线替代，不能打印的字符会做转义。`-run/-bench`选项输入的正则表达式会由`go test`工具自动进行相同的处理。

>To avoid display and parsing issues, a name is sanitized by replacing spaces with underscores and escaping non-printable characters. The same sanitizing is applied to the regular expressions passed to the -run or -bench flags.

一些例子：
```
# 执行欧洲时区的单测
# 译者注：第二个正则表达式用双引号括起来，其中可以包含空格，然后go test会把空格转换为下划线
$ go test -run=TestTime/"in Europe"
--- FAIL: TestTime (0.00s)
    --- FAIL: TestTime/12:31_in_Europe/Zuri (0.00s)
        time_test.go:85: could not load location

# 执行时间为下午的单测
$ go test -run=Time/12:[0-9] -v
=== RUN   TestTime
=== RUN   TestTime/12:31_in_Europe/Zuri
=== RUN   TestTime/12:31_in_America/New_York
--- FAIL: TestTime (0.00s)
    --- FAIL: TestTime/12:31_in_Europe/Zuri (0.00s)
        time_test.go:85: could not load location
    --- FAIL: TestTime/12:31_in_America/New_York (0.00s)
        time_test.go:89: got 07:31; want 7:31

# 单测名字中包含/
$ go test -run=Time//New_York
--- FAIL: TestTime (0.00s)
    --- FAIL: TestTime/12:31_in_America/New_York (0.00s)
        time_test.go:88: got 07:31; want 7:31
```

子测试`TestTime/12:31_in_America/New_York`不能被`-run=TestTime/New_York`匹配。因为子测试名字中包含了`/`，它是`-run/-bench`选项正则表达式的分隔符，导致`New_York`和`12:31_in_America`进行了匹配，匹配显然是失败的。预期的匹配是`/New_York`和`12:31_in_America/New_York`。

子测试`TestTime/12:31_in_America/New_York`能被`-run=TestTime//New_York`匹配：首先第一部分`TestTime`匹配，其次`-run`的第二个正则表达式为空字符串，那么它的语意是匹配所有的字符串，所以`12:31_in_America`匹配，最后第三部分`New_York`匹配。

**子测试名字被`/`分割为多个组成部分，和`-run`选项中的`/`分隔的部分对应匹配。**子测试名字中顶层测试和`Run`方法的第一个参数之间的`/`是testing包自动生成的，为什么`Run`方法的第一个参数的字符串中会有`/`呢？这样做是为了能够在不修改测试命名规则的前提下允许用户重构测试的层级。另外，这样做还简化了转义规则，当然用户可以显式的通过`\/`来实现转义。

>Treating slashes in names as separators allows the user to refactor hierarchies of tests without the need to change the naming. It also simplifies the escaping rules. The user should escape slashes in names, for instance by replacing them with backslashes, if this poses a problem.

如果子测试的名字不是唯一的，那么会在子测试名字的后面追加一个唯一的序列号。如果子测试没有明显的命名格式，那么`Run`方法的第一个参数可以传入空字符串，通过唯一的序号可以定位相应的子测试。

```golang
$ go test .
--- FAIL: TestTime (0.00s)
    --- FAIL: TestTime/#00 (0.00s)
        main_test.go:24: could not load location
    --- FAIL: TestTime/#01 (0.00s)
        main_test.go:28: got 07:34; want 7:31
    --- FAIL: TestTime/#02 (0.00s)
        main_test.go:28: got 18:12; want 18:08
FAIL
FAIL    subtest 0.042s
```

### 测试环境的准备和清理
子测试和子性能测试可以实现对公共的测试环境准备和清理代码的共享，这些代码会在所有子测试执行之前和之后执行最多一次，即使有子测试调用了`Skip`、`Fail`、`Fatal`这些方法。
```golang
func TestFoo(t *testing.T) {
    // <setup code>
    t.Run("A=1", func(t *testing.T) { ... })
    t.Run("A=2", func(t *testing.T) { ... })
    t.Run("B=1", func(t *testing.T) {
        if !test(foo{B:1}) {
            t.Fail()
        }
    })
    // <tear-down code>
}
```

### 并发控制
子测试提供了细粒度的并发控制。在理解如何控制并发之前，需要理解并发测试的语意。

每个测试都关联到一个测试函数，如果测试函数调用了这个测试的`testing.T`实例的`Parallel`方法，那么它就是并发测试（译者注：没调用这个方法的都是顺序测试，`testing.T`可以看作一个测试的元信息，调用）。并发测试和顺序测试不会同时执行，`-parallel`选项用于指定可以并发执行的最大并发测试数量。

当一个测试的所有子测试完成以后它的测试函数才返回，在测试函数返回之前，这个测试会阻塞其他的测试。这就意味着多个测试（每个测试有多个子测试，子测试都是并发的），那么这多个测试之间是顺序执行的。

对于通过`Run`方法创建的子测试和顶层的测试，都遵循上面的规则。事实上，顶层测试的实现是一个隐藏测试的子测试。

>Subtests allow fine-grained control over parallelism. To understand how to use subtests in the way it is important to understand the semantics of parallel tests.

>Each test is associated with a test function. A test is called a parallel test if its test function calls the Parallel method on its instance of testing.T. A parallel test never runs concurrently with a sequential test and its execution is suspended until its calling test function, that of the parent test, has returned. The -parallel flag defines the maximum number of parallel tests that can run in parallel.

>A test blocks until its test function returns and all of its subtests have completed. This means that the parallel tests that are run by a sequential test will complete before any other consecutive sequential test is run.

>This behavior is identical for tests created by Run and top-level tests. In fact, under the hood top-level tests are implemented as subtests of a hidden master test.

### 并行执行一组测试
上面的语意支持并行执行一组测试，**只能有一个顶层测试中的子测试并发执行，在一个顶层测试中所有通过`Run`方法创建的所有子测试完成之前，这个顶层测试都不会完成。其他的顶层测试此时都不能被执行。**注意，我们需要捕捉循环变量，保证Run方法的第二个参数中的闭包绑定到正确的变量。**
```golang
func TestGroupedParallel(t *testing.T) {
    for _, tc := range testCases {
        tc := tc // capture range variable
        t.Run(tc.Name, func(t *testing.T) {
            t.Parallel()
            if got := foo(tc.in); got != tc.out {
                t.Errorf("got %v; want %v", got, tc.out)
            }
            ...
        })
    }
}
```

### 并发测试完成后清理环境
在前面的例子中我们并发执行一个顶层测试下的子测试，等待所有子测试执行完成再继续下一个顶层测试。因为`Run`方法会阻塞等待所有子测试，所以可以在`Run`返回之后清理环境。等待一组子测试并发执行完成的行为和前面一个例子是相同的。
```golang
func TestTeardownParallel(t *testing.T) {
    // <setup code>
    // This Run will not return until its parallel subtests complete.
    t.Run("group", func(t *testing.T) {
        t.Run("Test1", parallelTest1)
        t.Run("Test2", parallelTest2)
        t.Run("Test3", parallelTest3)
    })
    // <tear-down code>
}
```

### 结论
Go 1.7增加的子测试和子性能测试允许你很自然的编写结构化单测和性能测试，并且可以很平滑的和现有的工具融合。

测试能够定义成这种结构使得能够细粒度的控制执行指定的测试用例、共享测试环境准备和清理、更好的控制并发测试。我们很乐于看到人们还能发现Go的测试框架的哪些好处。享受它吧。