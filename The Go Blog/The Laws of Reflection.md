## [The Laws of Reflection](https://blog.golang.org/laws-of-reflection)
6 September 2011 By Rob Pike

### 简介
计算机科学中的反射是程序检查自己的数据结构的能力，特别是通过类型，它是元编程的一种形式，同样，反射也给程序员带来了很多困惑。

这篇文章中，我们尝试通过解释Go中反射的工作原理来让大家明白反射。每种语言的反射模型都是不同的，甚至有的语言根本不支持反射，但是这篇文章讨论反射的范围仅限于Go，因此下面文章中“反射”专指“Go中的反射”。

### 类型和接口
因为反射是建立在类型系统的基础上，所以先让我们复习一下Go里面的类型。

Go是静态类型语言，每个变量都必须有一个静态的类型：类型必须是是在编译时确定并且已知的，例如：int、float32、*MyType、[]byte等。下面的声明中，**i是int类型的，j是MyInt类型，i和j的静态类型是不同的**，尽管MyInt底层实际上也是int，**静态类型不同意味着如果不用类型转换，就不能相互赋值**
```go
type MyInt int

var i int
var j MyInt
```

类型中最重要的一种是interface，它表示一组方法的集合。**interface类型的变量可以存储任何类型的值，只要对应的值实现了接口类型定义的方法即可**。接口最常见的一个例子是定义在[io包](http://golang.org/pkg/io/)中的类型io.Reader和io.Writer，任何实现了Read或者Write方法（方法签名要一致，即参数和返回值）的类型我们叫做实现了io.Reader或者io.Writer接口，这就意味着io.Reader类型的变量（例如下面的变量r）可以保存任何类型值，只要值类型有一个Read方法就行。需要特别注意的是无论r保存的值是什么类型的，r的类型都是io.Reader，因为Go是静态类型，r的静态类型是io.Reader。
```go
// Reader is the interface that wraps the basic Read method.
type Reader interface {
    Read(p []byte) (n int, err error)
}

// Writer is the interface that wraps the basic Write method.
type Writer interface {
    Write(p []byte) (n int, err error)
}

var r io.Reader
r = os.Stdin
r = bufio.NewReader(r)
r = new(bytes.Buffer)
// and so on
```

接口类型中特别重要的一个例子是空接口：`interface{}`，**它表示空的方法集合，因为任何类型都能满足，所以它能保存任意类型的值**。

有些人认为Go的接口是动态类型的，这是错误的。Go的接口是静态类型的，同一个接口类型的所有变量，它们的静态类型都是相同的。尽管在运行时保存在接口变量中的值的类型可能会改变，但是无论值的类型如何变化，值都是满足接口的。
原文：They are statically typed: a variable of interface type always has the same static type, and even though at run time the value stored in the interface variable may change type, that value will always satisfy the interface.
（译者注：用上面的代码解释一下上面这段。r的静态类型是io.Reader，运行到第一行，r保存的值类型一开始是os.Stdin，然后运行到第二行，r保存的值类型变成了bufio.Reader，最后第三行，r保存的值类型变成了bytes.Buffer。但是r的类型一直是io.Reader，所以r的类型不是动态的。另外，尽管os.Stdin、bufio.Reader、bytes.Buffer是不同的类型，但是它们都能赋值给r。）

对于上面的讨论我们必须保持严谨和准确，因为反射和接口关系很紧密。

### 接口的表示
[Russ Cox的blog](http://research.swtch.com/2009/12/go-data-structures-interfaces.html)介绍了接口类型的在Go的表示。这里不完整的重复blog的内容，只是按顺序概述一下要点。

**接口类型的变量保存了一个(value
, type)对，准确来说就是：value为赋值给接口类型变量的实际值的底层实际数据，type为实际值的类型描述符**。例如：把tty赋值给r以后，r的(value, type)对为`(tty, *os.File)`。

值得注意的是`*os.File`实现了除了Read以外的方法，尽管通过接口变量r只能访问Read方法，但是r.value实际上保存了`*os.File`的所有方法。例如：`*os.File`还实现了Write，因此我们可以通过类型断言把r赋值给io.Writer。`r.(io.Writer)`表示类型断言，它断言的是r.value同样实现了io.Writer接口，所以能够赋值给变量w。这样赋值以后，w的(value, type)对为`(tty, *os.File)`，和r相同。**接口变量的静态类型决定了通过接口类型的变量能够调用什么方法，尽管接口变量保存的实际值可能实现了更多的方法。**
```go
var r io.Reader
tty, err := os.OpenFile("/dev/tty", os.O_RDWR, 0)
if err != nil {
    return nil, err
}
r = tty

var w io.Writer
w = r.(io.Writer)

var empty interface{}
empty = w
```

把w赋值给空接口empty以后，empty和w保存了相同的(value, type)对：`(tty, *os.File)`。**这是一个技巧：空接口能够保存任意类型的值以及值的类型的所有信息，便于我们之后的使用。**

把empty赋值给w不需要类型断言的原始是因为w能够满足空接口（译者注：**把接口a赋值给接口b时，只要b定义的方法是a的子集，就不需要类型断言**。因为空集是任何集合的真子集，所以把w赋值给empty不需要类型断言。），在把r赋值给w时需要类型断言，因为io.Writer定义的方法集合不是io.Reader的子集。

一个很重要的细节是接口的(value, type)对中的type只能是实际类型，不能是接口，也就是说**接口类型的变量不能保存的值类型不能是接口**。

现在关于反射需要的知识我们都准备好了。

### 反射第一定律：Reflection  goes from interface value to reflection object
（译者注：reflection object是指`reflect.Value`和`reflect.Type`）

反射的最基础层次的理解是一种机制检查接口类型的变量中保存的value和type。首先需要了解[reflect包](http://golang.org/pkg/reflect/)中的两个类型：[Type](http://golang.org/pkg/reflect/#Type)和[Value](http://golang.org/pkg/reflect/#Value)。这两个类型用于访问接口变量的type和value，`reflect.TypeOf`返回`reflect.Type`、`reflect.ValueOf`返回`reflect.Value`。后面我们可以发现，从`reflect.Value`也可以得到`reflect.Type`，目前我们先分别来看value和type。

你可能很奇怪下面的程序中没有接口，因为只把一个float64类型的变量x（而不是一个接口类型的变量）传递给了`reflect.TypeOf`函数。通过`reflect.TypeOf`的[函数签名](http://golang.org/pkg/reflect/#TypeOf)可以发现这个函数的参数为空接口（译者注：空接口可以保存任何类型的变量）。当调用`reflect.TypeOf(x)`时，先创建一个临时的空接口变量保存x，然后把它作为实参传递给`reflect.TypeOf`，`reflect.TypeOf`从空接口中还原x的类型信息。

同理，`reflect.ValueOf`函数用于提取空接口的值。从这里开始的代码中，我们省略package、import等内容，只关注可执行的部分。
```go
package main

import (
    "fmt"
    "reflect"
)

func main() {
    var x float64 = 3.4
    fmt.Println("type:", reflect.TypeOf(x))
    fmt.Println("value:", reflect.ValueOf(x))
}

// output
type: float64
value: <float64 Value>
```

`reflect.Type`和`reflect.Value`实现了很多方法用于检查和操作：

* `reflect.Value`实现了一个`Type`方法能够返回`reflect.Value`的类型
* `reflect.Type`和`reflect.Value`都实现了`Kind`方法用于返回一个常数，表示接口中value的类型，例如 Uint、Float64、Slice等
* `reflect.Value`实现了`Int`、`Float`等方法，用于以int64、float64类型的方式返回接口中的value
* `reflect.Value`还实现了`SetInt`、`SetFloat`等方法，因为涉及到`settabiliy`的概念，具体会在第三条定律中讨论。

```go
var x float64 = 3.4
v := reflect.ValueOf(x)
fmt.Println("type:", v.Type())
fmt.Println("kind is float64:", v.Kind() == reflect.Float64)
fmt.Println("value:", v.Float())

// output
type: float64
kind is float64: true
value: 3.4
```

Go的反射库有一些特性指的单独指出一下：

1. 首先，为了保持API简洁，`reflect.Value`的get和set方法对于每种数据类型，都只保持一份最大类型的实现，例如：对于所有的有符号整数的set和get方法都使用int64类型。也就说`reflect.Value`的`Int`方法的返回值以及`SetInt`方法的形参都是int64，如果`reflect.Value`保存的符号整数长度不是64位，需要显式转换。
2. 如果`reflect.Value`保存的值类型是用户自定义的，那么`Kind`方法返回的是底层类型，而不是用户自定义的静态类型。但是`Type`方法能够返回静态类型。例如：`v.Kind()`返回的是`reflect.Int`，尽管x的静态类型是MyInt，不是int，但是`Kind`方法没法区分MyInt和int；但是`Type`方法返回的是x的静态类型MyInt。
```go
var x uint8 = 'x'
v := reflect.ValueOf(x)
fmt.Println("type:", v.Type())                            // uint8.
fmt.Println("kind is uint8: ", v.Kind() == reflect.Uint8) // true.
x = uint8(v.Uint())

type MyInt int
var x MyInt = 7
v := reflect.ValueOf(x)
fmt.Println("Kind is:", v.Kind()) // int
fmt.Println("Type is:", v.Type()) // main.MyInt
```

### 反射第二定律：Reflection  goes from reflection object to interface value
和物理中的反射一样，Go的反射也同样是可逆的。

`reflect.Value`实现了`Interface`方法可以从反射对象中恢复出接口变量，实际上这个方法是根据反射对象的type和value信息创建出一个接口变量并返回。例如：反射对象v通过`Interface`方法恢复了v表示的float64变量。

下面的`fmt.Println(y)`可以简化一下，`fmt.Println`和`fmt.Printf`的参数类型都是空接口，fmt包会从空接口中解析出它所表示的值，解析的方法就和`y := v.Interface().(float64)`类似，所以我们只需要把`Interface`方法返回的空接口直接传递给`fmt.Println`就可以打印反射对象`reflect.Value`保存的值了。`fmt.Println(v)`打印的是反射对象本身，而`fmt.Println(v.Interface())`是打印的反射对象保存的实际值（译者注：实测`fmt.Println(v)`也能打印出v保存的实际值）。因为我们已知反射对象保存的值类型为float64，我们也可以通过格式化打印，同样，因为`fmt.Printf`也会对`v.Interface()`返回的空接口进行解析，拿到反射对象保存的值，所以这里也不需要类型断言。
```go
// Interface returns v's value as an interface{}.
func (v Value) Interface() interface{}

v := reflect.ValueOf(3.4)
y := v.Interface().(float64) // y will have type float64.
fmt.Println(y)

fmt.Println(v)
fmt.Println(v.Interface())
fmt.Printf("value is %7.1e\n", v.Interface())
// output
3.4e+00
3.4e+00
3.4e+00
value is 3.4e+00
```

**简而言之，`Interface`和`ValueOf`是互逆的，除了`Interface`返回的是一个空接口。**（译者注：`ValueOf`输入的可能不是一个空接口，但是对反射对象执行`Interface`返回的不一定是原来的接口，而是一个空接口）。

再次，可以从接口变量创建反射对象，也可以从反射对象得到接口变量。

### 反射第三定律：To  modify a reflection object, the value must be settable
第三条定律是最微秒、困惑的，但是我们可以从简单的原理入手理解它。首先是一小段不能实现功能的代码，但却很值得研究。输出的异常信息很神秘，它并不表示`SetFloat`的参数7.1是不可寻址的，而是反射对象v是不可设置的。
>... it will panic with the cryptic message. ... it's that v is not settable

`setability`是反射对象`reflect.Value`的一个属性，不是所有的`reflect.Value`都可以被设置。`CanSet`方法可以用于检查`reflect.Value`能不能被设置，对于不能被设置的反射对象，调用`SetXXX`方法会导致panic。
```go
var x float64 = 3.4
v := reflect.ValueOf(x)
v.SetFloat(7.1) // Error: will panic.

// output
panic: reflect.Value.SetFloat using unaddressable value

var x float64 = 3.4
v := reflect.ValueOf(x)
fmt.Println("settability of v:", v.CanSet())

// output
settability of v: false
```

什么是`settability`？`settability`类似于变量是否可以寻址，更严格来说，它表示一个反射对象能不能修改创建反射对象时使用的实际值，是否可以修改，取决于反射对象如何保存实际值。上面代码中的变量v实际上是根据x的一个副本创建的（译者注：`reflect.ValueOf`调用是传值的），如果`v.SetFloat(7.1)`能够成功执行，那么实际修改的不是x本身，而是修改的x的副本，尽管看起来v是根据x创建的。这样的修改是没有意义的，因为x并没有变，所以Go不允许这样的调用，`settability`就是用来避免这种问题的属性。

`settability`看起来很离奇，但实际并不是。这只是一个常见问题换了个马甲。考虑一个函数调用`f(x)`，显然不能期望函数能够修改x，因为我们并没有把x本身传递给函数，而是传递了x的一个值拷贝。如果想通过函数修改实参，需要向函数传递指针：`f(&x)`。
>If this seems bizarre, it's not. It's actually a familiar situation in unusual garb. 

反射对象的`settability`和这个问题类似，如果希望通过反射对象修改实际值，必须通过实际值的指针创建反射对象。下面让我们验证一下，首先和前面一样初始化x，然后通过x的指针创建一个反射对象p，通过输出我们发现反射对象p是不可设置的，但是我们需要修改的不是p，而是\*p（即p指向的内容）。`reflect.Value`实现了`Elem`方法用于获取p指向的内容，它的返回值v也是`reflect.Value`，通过输出我们发现v是可以设置的，调用`v.SetFloat()`就可以修改x的值，通过输出可以验证结果符合预期。
```go
var x float64 = 3.4
p := reflect.ValueOf(&x) // Note: take the address of x.
fmt.Println("type of p:", p.Type())
fmt.Println("settability of p:", p.CanSet())

v := p.Elem()
fmt.Println("settability of v:", v.CanSet())

v.SetFloat(7.1)
fmt.Println(v.Interface())
fmt.Println(x)

// output
type of p: *float64
settability of p: false
settability of v: true
7.1
7.1
```

反射可能很难理解，但是反射实现的就是编程语言所实现的功能，通过反射对象`Type`和`Value`就可以区分出当前执行的操作。需要记住的是：如果想通过`reflect.Value`修改它表示的实际值，那么需要实际值可以被寻址。
>Reflection can be hard to understand but it's doing exactly what the language does, albeit through reflection Types and Values that can disguise what's going on.

### 结构体
在定律三的例子中，变量v本身并不是个指针，它是从一个指针得到的。通过这一点我们可以把它应用扩展到一个更常见的场景：通过反射修改结构体成员。只要我们使用结构体的指针创建反射对象，就能通过反射体对象修改结构体字段。

下面是一个简单的例子：我们通过结构体变量t的地址创建反射对象，因为后面需要修改它，然后我们把typeOfT初始化为变量t对应的类型并按照结构体成员迭代，注意成员名字是从typeOfT中提取出来的，从s中提取出来的结构体成员的类型仍然是`reflect.Value`。因为s保存的是可设置的反射对象，因此我们可以修改结构体的成员。如果把程序修改为通过t（而不是&t）创建s，那么`SetInt`、`SetString`调用都会失败，因为创建s使用的t是不可设置的。
>Then we set typeOfT to its type and iterate over the fields using straightforward method calls (see package reflect for details). Note that we extract the names of the fields from the struct type, but the fields themselves are regular reflect.Value objects.

关于结构体的`settability`需要额外指出的一点是：只有结构体导出的成员才能设置，因此结构体T定义成员名字（首字母）都是大写的。
```go
type T struct {
    A int
    B string
}
t := T{23, "skidoo"}
s := reflect.ValueOf(&t).Elem()
typeOfT := s.Type()
for i := 0; i < s.NumField(); i++ {
    f := s.Field(i)
    fmt.Printf("%d: %s %s = %v\n", i,
        typeOfT.Field(i).Name, f.Type(), f.Interface())
}
s.Field(0).SetInt(77)
s.Field(1).SetString("Sunset Strip")
fmt.Println("t is now", t)

// output
0: A int = 23
1: B string = skidoo
t is now {77 Sunset Strip}
```

### 结论
再次总结一下反射的定律：
* Reflection goes from interface value to reflection object.
* Reflection goes from reflection object to interface value.
* To modify a reflection object, the value must be settable.

一旦你理解力这些定律，尽管Go的反射有点微秒，但是使用起来会很容易了。反射是一个很强大的工具，但是使用时需要很小心，除非特别需要，否则应该尽量避免使用。

关于反射这个话题我们还有很多没有讨论，例如：通过channel接收和发送、分配内存、使用slice和map、调用方法和函数，但是这批blog内容已经足够多了，对于这些没讨论到的话题，我们会在后面的文章中继续。