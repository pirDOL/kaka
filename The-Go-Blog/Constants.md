## [Constants](https://blog.golang.org/constants)

25 August 2014 By Rob Pike

### TLDR
1. typed-constant vs untyped constant
```
const untyped = "hello"
const typed string = "hello"
```

>In summary, a typed constant obeys all the rules of typed values in Go. On the other hand, an untyped constant does not carry a Go type in the same way and can be mixed and matched more freely. It does, however, have a default type that is exposed when, and only when, no other type information is available.

2. const MaxUint = ^uint(0)
3. range
```go
var i8 int8 = 128 // Error: too large.
var u8 uint8 = -1 // Error: negative value.

const Huge = 1e1000       // OK
fmt.Println(Huge)         // Error: constant 1.00000e+1000 overflows float64
fmt.Println(Huge / 1e999) // OK
```

### 简介
Go是一个静态语言，不允许混合数值类型的操作，例如：你不能将float64加到int上，甚至不能把int32加到int上。但是下面这种写法却是合法的：`1e6*time.Second`、`math.Exp(1)`，甚至是`1<<(‘\t’+2.0)`。Go的常量不同于变量，它们更像是普通的数字。这篇文章解释了常量为什么这样设计以及这样设计对用户意味着什么。

### 背景：C
在构思Go的早期，我们对大量的由C语言和它的后代的混合和匹配数字类型引起的问题进行了讨论。很多难以理解的bug、崩溃和可移植性问题是因为表达式包含了不同位宽、不同符号的整数。下面的表达式对于经验丰富的C程序员会很熟悉，但对于新手程序员是难以理解它的结果（原文：it isn't a priori obvious）。计算结果的位宽是多少？值是多少？它是有符号的还是无符号的？这中表达式潜伏着让人讨厌的bug。
```
unsigned int u = 1e9;
long signed int i = -1;
..。i + u ..。
```

>C has a set of rules called "the usual arithmetic conversions" and it is an indicator of their subtlety that they have changed over the years (introducing yet more bugs, retroactively)。

我们在设计Go的时候决定避免这个雷区，所以我们规定不能混合数值类型。如果想i和u相加，你必须明确想要的结果是什么类型。例如：
```go
var u uint 
var i int
```

你可以写`uint(i)+u`或者`i+int(u)`，它们都能清晰的表示加法操作的类型，Go不像C那样可以写`i+u`，也不能混合`int`和`int32`，即使int是用32位表示。

Go数据类型的严格性消除了一般的bug和其他的问题，它是Go语言的一个关键特性。但是这个特性带来了一定的成本：需要程序员在代码中通过笨拙的类型转换来明确语意。

那么常量是如何在上面的特性中工作的？根据上面的声明，怎样使得`i = 0`或者`u = 0`是符合语法的？字面值0的究竟是什么类型？在简单上下文中常量的类型转换是很没必要的，例如：`i = int(0)`。

我们很快认识到需要让数字常量以不同于C语言的方式工作。经过大量的思考和实验，我们提出了一个我们认为各方面感觉不错的设计，使得程序员不需要做没有意义的常量转换，任何时候都能像`math.Sqrt(2)`使用常量，并且不会有编译错误。

总之，在Go的大多数场景中常量都能工作，我们来看看它怎么工作的。

### 术语
首先，简单的定义一下常量。在Go中，const是一个关键字，用于给标量值2、3.14159或"scrumptious"取一个名字。这些标量值在Go语言中叫做常量。常量也可以通过由常量组成的表达式创建，如`2+3`或`2+3i`或`math.Pi/2`或`("go"+"pher")`。

有些语言没有常量，另外一些语言中常量的定义更泛化，对const关键字的应用也比Go语言广泛。例如：在C和C++里，const是类型限定词，用来编辑更复杂的值更复杂的属性。

但是在Go里常量只是一个简单的、不能修改的值。下面我们只讨论Go语言。

### 字符串常量
数值常量有很多种：整数、浮点数、runes、有符号、无符号、虚数、复数。我们从一个形式更简单的常量开始：字符串。字符串常量容易理解，而且提供了探索Go语言中类型问题的更小的问题空间。

字符串常量把一些文本包在两个引号中间（Go语言也支持用反引号定义原始字符串，但在这次讨论的范畴中它们都是等价的）。这是一个字符串常量：`"Hello, 世界"`（更多有关字符串表示和解释的详细内容请看这篇[博客](https://blog.golang.org/strings)）

这个字符串常量是什么类型？一个显而易见的答案是字符串，但是不对。

这是一个**无类型的字符串常量**，也就是说它是一个没有固定类型的常量文本值。是的它是一个字符串，但是不是一个Go语言类型的字符串值。即使给它一个名字，它仍然是一个无类型的字符串常量。

`const hello = "Hello, 世界"`这样声明之后，hello还是一个无类型的字符串常量。一个无类型常量只是一个值，没有已定义类型，所以它就不需要遵守“不同类型的值不能混合”的规则。无类型常量的概念使得我们可以更自由的使用Go语言的常量。

那么什么是有类型的字符串常量？像这样给定类型的就是：`const typedHello string = "Hello, 世界"`，注意`typedHello`的声明在等号的前面有明确的`string`类型。这表示 `typedHello`具有Go语言类型`string`，不能赋值给不同类型的Go变量。这说明下面代码块A是正确的，代码块B是错误的。
```go
// A
var s string 
s = typedHello
fmt.Println(s)

// B
type MyString string 
var m MyString 
m = typedHello // Type error 
fmt.Println(m)
```

变量`m`的类型是`MyString`，不同的类型不能对它赋值，只能被`MyString`类型赋值，或者强制进行类型转换
```go
const myStringHello MyString = "Hello, 世界" 
m = myStringHello // OK 
fmt.Println(m)

m = MyString(typedHello) 
fmt.Println(m)
```

回到我们的无类型字符串常量，它有个有用的性质：因为没有类型，所以把它赋值给有类型的变量不会引起类型错误。那么就能这么写：

```
m = "Hello, 世界"
m = hello
```

因为不像有类型的常量`typedHello`和`myStringHello`, `"Hello, 世界"`和`hello`都是无类型的常量，把它们赋值给任何能兼容`string`类型的变量都没有错误。

这些无类型字符串常量显然是字符串，所以能用在任何允许字符串使用的地方，但是它们不是`string`类型。

### 默认类型
Go程序员肯定看见过很多这样的声明：`str := "Hello, 世界"`，那么你可能有疑问既然常量是无类型的，那么`str`如何在这个变量声明中得到类型？答案是无类型常量有默认类型，如果需要类型却没有提供时，会使用无类型常量的默认类型。字符串常量的默认类型显然是`string`，所以下面三种写法都是等价的：
```go
str := "Hello, 世界"
var str = "Hello, 世界"

var str string = "Hello, 世界"
```

一种理解无类型常量的方法是认为它们存在于一个理想的值空间，这个空间的限制比Go的完整类型系统要小。然而用它们做任何事都需要赋值给变量，这时被赋值的变量需要一个类型（常量本身不需要类型），常量会告诉变量你应该是什么类型。在这个例子中，`str`变成一个`string`类型的值是因为无类型字符串常量的默认类型是`string`。

上面的声明中变量以类型和初始值来声明。然而有时候我们使用常量的时候不那么清楚它的目的值。例如`fmt.Printf("%s"，"Hello, 世界")`，`fmt.Printf`的函数签名是`func Printf(format string, a ...interface{}) (n int, err error)`，它的参数（除了格式化字符串以外）是空接口。当使用无类型变量作为`fmt.Printf`的参数时会创建一个空接口类型的值来传参，参数的类型就是常量的默认类型。这个过程类似于我们刚才说的用无类型字符串来声明并初始化变量的情况。

下面的例子用格式化字符`%v`来打印传给`fmt.Printf`的值，用`%T`来打印值的类型：
```go
fmt.Printf("%T： %v\n"，"Hello, 世界"，"Hello, 世界") 
fmt.Printf("%T： %v\n"，hello, hello)
```

如果常量声明了类型，会把类型交给interface，例如下面这个例子：
```go
fmt.Printf("%T： %v\n"，myStringHello, myStringHello)
```

（更多有关interface类型的值的工作原理，请看[这篇帖子](https://blog.golang.org/laws-of-reflection)的第一节）

简而言之，有类型的常量遵循所有Go语言类型的规则，相反，无类型常量没有Go类型，可以自由的混合和匹配，而只有当没有其他的类型信息可用时，才会使用无类型变量的默认类型。

### 语法决定默认类型
无类型常量的默认类型是由它的语法决定的。对字符串常量来说，唯一可能的隐式类型是 string；对[数值常量](http://golang.org/ref/spec#Numeric_types)来说，隐式类型有许多种，整型常量的默认类型是int, 浮点型是float64，rune常量的默认类型为rune（rune是int32的别名），虚数常量的默认类型是complex28。这里我们使用典型的打印语句来展示默认类型：
```go
fmt.Printf("%T %v\n"，0，0) 
fmt.Printf("%T %v\n"，0.0，0.0) 
fmt.Printf("%T %v\n"，'x'，'x') 
fmt.Printf("%T %v\n"，0i, 0i)
```
练习： 解释'x'的打印结果。

### 布尔值
我们讨论的所有无类型字符串常量的事情都能用在无类型布尔常量上。`true`和`false`是无类型的布尔值常量，可以赋值给任何布尔型变量，如果布尔常量一旦有了类型，就不能混合类型了：
```go
type MyBool bool 
const True = true 
const TypedTrue bool = true 
var mb MyBool 
mb = true // OK 
mb = True // OK 
mb = TypedTrue // Bad 
fmt.Println(mb)
```

运行这个例子看看发生啥，然后注释掉"Bad"那一行再运行一次。布尔常量遵循了字符串常量的类型规则。

### 浮点型
浮点型常量在大多数方面和布尔型常量一样。我们的标准范例从布尔值修改为浮点值之后，能够如预期一样工作：
```go
type MyFloat64 float64 
const Zero = 0.0 
const TypedZero float64 = 0.0 
var mf MyFloat64 
mf = 0.0 // OK 
mf = Zero // OK 
mf = TypedZero // Bad 
fmt.Println(mf)
```

Go语言有两个浮点类型： `float32`和`float64`。浮点型常量的默认类型是`float64`，但是无类型浮点型常量也可以赋值给一个`float32`的值：
```go
var f32 float32 
f32 = 0.0 
f32 = Zero // OK： Zero is untyped 
f32 = TypedZero // Bad: TypedZero is float64 not float32。
fmt.Println(f32)
```

浮点值是引入溢出概念或者值域的好地方。

数值常量存在于一个任意精度的数值空间，它们只是普通的数字，但是当它们赋值给一个变量，值必须能适配目的变量。我们可以用一个超大的值声明一个常量`const Huge = 1e1000`，它只是个数字而已。但是我们不能用它赋值也不能打印它，这个语句甚至不能编译：`fmt.Println(Huge)`，错误是"constant 1.00000e+1000 overflows float64"，确实如此（1e1000超过了float64的范围）。但是`Huge`也有它的使用场景：我们在表达式中使用它和其他的常量，只要表达式的计算结果能够用`float64`范围内表示就可以，这个语句`fmt.Println(Huge / 1e999)`打印10，和期望的一样。

相对来说浮点型常量可以有很高的精度，使得使用它们进行计算会更精确。[math包](https://golang.org/pkg/math)里定义的常量比`float64`的有效数字更多。这是`math.Pi`的定义：`Pi = 3.14159265358979323846264338327950288419716939937510582097494459`，当这个值赋值给一个变量会丢失一部分精度，被赋值的变量会用最高精度的`float64`或`float32`类型的值，确保丢失的精度最少。下面的代码打印3.141592653589793。
```go
pi := math.Pi 
fmt.Println(pi)
```

更多的有效数字意味着像`Pi/2`这样的计算或者其他更复杂的求值可以保持更精确的结果，直到把结果用于赋值时再截断，从而涉及常量的计算代码更容易写，并且不会损失精度。它还意味着在常量表达式里不会发生像无穷大、软溢出、NaN这些边界情况。（除以常量0是一个编译时错误，并且只要所有参与运算的都是数字，就不会出现"not a number"错误）。

### 复数
复数常量表现的非常像浮点数常量。把我们熟悉的一连串例子代码翻译成复数：
```go
type MyComplex128 complex128 
const I = (0.0 + 1.0i) 
const TypedI complex128 = (0.0 + 1.0i) 
var mc MyComplex128 
mc = (0.0 + 1.0i) // OK 
mc = I // OK 
mc = TypedI // Bad 
fmt.Println(mc)
```

复数常量的默认类型是`complex128`，它是由两个`float64`值组成的更高精度的版本。

为了使我们的例子表达清楚，我们写了完整的表达式`(0.0+1.0i)`，其实它可以更短，像 `1.0i`甚至`1i`。

我们来玩个把戏。我们知道在Go语言里，数值常量只是一个数字。那么如果一个复数数字没有虚部的话会怎么样，是实数吗？看这个`const Two = 2.0 + 0i`，
它是一个无类型复数常量。尽管它没有虚部，表达式的语法还是定义它的默认类型是`complex128`。因此如果我们用它来声明一个变量，默认类型将是`complex128`。下面的代码片段打印`complex128: (2+0i)`。
```go
s := Two 
fmt.Printf("%T： %v\n"，s, s)
```

在数值上，`Two`可以保存在一个标量浮点数里，`float64`或者 `float32`，并且不会损失精度。所以我们可以把`Two`给一个`float64`变量赋值或者初始化都没有问题：
```go
var f float64 
var g float64 = Two 
f = Two 
fmt.Println(f, "and"，g)
```

程序输出`2 and 2`。尽管`Two`是一个复数常量，它还是可以赋值给浮点型变量（原文：scalar floating-point variables，我的理解是复数类型是向量，浮点类型就是标量）。常量的像这样的跨类型的能力是有用的。

### 整数
最后我们来说整数。它们有很多变化的地方：[多种位宽、有符号和无符号等等](http://golang.org/ref/spec#Numeric_types)，但是它们遵循的规则是一样。最后一次用我们熟悉的例子修改为`int`版本：
```go
type MyInt int 
const Three = 3 
const TypedThree int = 3 
var mi MyInt 
mi = 3 // OK 
mi = Three // OK 
mi = TypedThree // Bad 
fmt.Println(mi)
```

上面的例子可以用任何整数类型来修改，包括下面这些。具体的类型很多，但是现在你应该熟悉了常量工作的模式以及内部是如何工作的。
```
int int8 int16 int32 int64 
uint uint8 uint16 uint32 uint64 
uintptr
byte // uint8的别名
rune // uint32的别名
```

像上面提到的，整数有多种不同的形式，每个形式都有自己的默认类型：简单整数常量123、0xFF、-14的默认类型是int，引号字符'a'、'世'、'\r'的默认类型是rune。尽管简单整数的默认类型是`int`不是`uint`（原文：No constant form has as its default type an unsigned integer type），无类型常量的适应性使得我们可以简单整数常量初始化无符号整型变量，只要我们明确的表示类型即可。这类似于我们用没有虚部的复数来初始化 float64。下面是几种不同的初始化`uint`的方法，它们都是等价的，但是都必须明确地表示出结果类型是无符号的。

```go
var u uint = 17  // 译者注：只要初始化的值17在uint的范围内可以隐式转换
var u = uint(17) // 译者注：17的默认类型是int，如果需要u是uint，需要显式转换
u := uint(17)    // 译者注：同上
```

类似于上面浮点数那节提到的值域问题，不是所有的整数值都能装进所有的整数类型。具体有两个可能出现的问题：值太大了或者负值赋值给一个无符号整数类型。例如：`int8`的值域是-128~127，所以值域之外的常量不能赋值给一个`int8`类型的变量：`var i8 int8 = 128 // Error: too large`

类似的，`uint8`或者说`byte`，值域是0~255，所以一个大数或者负数常量不能赋值给`uint8`：`var u8 uint8 = -1 // Error: negative value`。

基于值域的类型检查可以捕捉到下面这样的错误，如果编译器对你的常量使用发出抱怨，可能真的是像这样的bug。
```go
type Char byte 
var c Char = '世' // Error: '世' has value 0x4e16，too large。
```

### 一个练习： unsigned int的最大值
下面是个有启发性的小练习：怎么表示一个常量来描述uint的最大值？

如果我们讨论的是`uint32`, 我们可以这样写`const MaxUint32 = 1<<32 - 1`

但是我们讨论的是uint，它和`int`类型的位数是相同的，可能是32位或者64位。因为有效位数依赖于CPU架构，我们不能只考虑一种情况。

Go语言的整数定义使用的[二进制补码运算](http://en.wikipedia.org/wiki/Two's_complement)，了解二进制补码的粉丝知道-1的所有bit为1，所以-1的二进制表示和最大的无符号整数是相同的。因此我们可能会想这么写：
```go
const MaxUint uint = -1 // Error: negative value`
```

可是这是不合法的，因为-1不能用无符号变量来表示，-1 不在无符号类型的值域内。

类型转换也没用，原因是一样的：
```go
const MaxUint uint = uint(-1) // Error: negative value
```

虽然在运行时-1能被转换为无符号整数，但是[常量转换规则](http://golang.org/ref/spec#Conversions)禁止在编译时进行这种强制转换。这说明这样是有效的：
```go
var u uint 
var v = -1 
u = uint(v) // 运行时转换
```

上面的代码能通过编译只是因为v是一个变量，如果我们把v改成 常量，即使是无类型常量，我们又回到了编译器禁止的范围：
```go
var u uint 
const v = -1 
u = uint(v) // Error: negative value 编译时转换
```

我们回到之前的方法，但是尝试以^0替代 -1，对任意bit长度的0值按位取反。但这还是失败的，原因是类似的： 在数值空间中，^0的位宽也是无限长，所以我们给固定位宽的整型赋值时会丢失信息：`const MaxUint uint = ^0 // Error: overflow`

那我们怎么用常量来表示最大的无符号整数?

关键是约束操作的位宽在`uint`之内，并且避免像负值这种`uint`无法表示的值。最简单的`uint`值是有类型的常量`unit(0)`。如果uint 是32或64位，`uint(0)`相应也有32或64个位。如果我们对`uint(0)`的按位取反，得到的结果的位宽能够正确容纳在`uint`中，也就是最大的`uint`值。

因此我们不对无类型常量0按位取反，我们翻转有类型常量`unit(0)`的比特位。是这样：
```go
const MaxUint = ^uint(0) 
fmt.Printf("%x\n"，MaxUint)
```

无论当前的执行环境中表示`uint`有多少位（在[playground](http://blog.golang.org/playground)里是32位），这个常量都能正确地表示一个`uint`变量能容纳的最大值。

如果你理解我们得到这个结果的分析过程，你就理解了Go语言常量的所有重点。

### 数字
Go语言中无类型常量的概念意味着所有的数字常量存在于一个统一的空间，无论是整型，浮点型，复数，甚至字符值。当把它们带进变量的计算和赋值时才需要真实的类型。但是如果只限定在数字常量空间中，我们可以任意混合和匹配值。下面这些常量都是值1：
```go
1 
1.000 
1e3-99.0*10-9 
'\x01' 
'\u0001' 
'b' - 'a' 
1.0+3i-3.0i
```

因此，尽管它们有不同的隐式默认类型，但是作为无类型常量还是能赋值给任何整数类型的变量：
```go
var f float32 = 1 
var i int = 1.000 
var u uint32 = 1e3 - 99.0*10.0 - 9 
var c float64 = '\x01' 
var p uintptr = '\u0001' 
var r complex64 = 'b' - 'a' 
var b byte = 1.0 + 3i - 3.0i 
 
fmt.Println(f, i, u, c, p, r, b)
```

这片段的输出是：1 1 1 1 1 (1+0i) 1。

甚至能写这样古怪的东西：
```go
var f = 'a' * 1.5 
fmt.Println(f)
```

将产生145.5，除了证明“数字常量可以任意混合类型”这一点外没啥意义。

常量类型的规则本质是适应性。适应性意味着尽管Go语言中在同一个表达式里混合浮点型变量和整型变量是不合法的，甚至混合`int`和`int32`也不行，但是可以这么写`sqrt2 := math.Sqrt(2)`、`const millisecond = time.Second/1e3`、`bigBufferWithHeader := make([]byte, 512+1e6)`，它们都能得到想要的结果。

因为在Go语言中，数字常量就如同你期待的那样：像数字一样工作。
