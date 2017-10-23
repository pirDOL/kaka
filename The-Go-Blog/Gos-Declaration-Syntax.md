## [Go's Declaration Syntax](https://blog.golang.org/gos-declaration-syntax)

7 July 2010 By Rob Pike

### TLDR
1. `int *p`：`*p`的类型是int，所以`p`的类型是指向int的指针。
>Instead of describing the types with special syntax, one writes an expression involving the item being declared, and states what type that expression will have.
2. Go's declarations read left to right, we believe Go's type syntax is easier to understand than C's, especially when things get complicated.
```
int (*(*fp1)(int (*fp2)(int, int), int))(int, int)
int (*(*fp)(int (*)(int, int), int))(int, int)

f1 func(f1 func(int, int) int, b int) func(int, int) int
f func(func(int, int) int, int) func(int, int) int
```

### 简介
很多新手对于Go的声明语法不同于C系列的语言已有的传统感到奇怪，本文会比较Go 和C系列语言的两种声明语法，并解释为什么Go的声明语法长成现在的样子。

### C语法
首先来说是C语言语法，C没有采用特殊语法描述变量的类型，而是采用了一种不寻常但非常聪明的声明语法：声明语法由表达式和类型组成，表达式只要包含要声明的标识符即可（译者注：x、*p、a[3]），然后类型描述的是表达式的类型。例如：`int x;`声明了x为int类型，表达式是`x`，它的类型是int（所以，x就是int类型）。通常情况下声明一个变量的方法是：写一个包含这个变量的表达式，在表达式左侧写上这个表达式计算结果的类型（译者注：`int a[3];`，声明的变量是a，表达式是`a[3]`，它的返回值类型为int，所以a是一个元素为int的数组）。
>In general, to figure out how to write the type of a new variable, write an expression involving that variable that evaluates to a basic type, then put the basic type on the left and the expression on the right.

另外，下面这两个声明表示p是一个指向int类型的指针，因为`*p`这个表达式的类型是int，a是一个元素类型为int的数组，因为`a[3]`的类型是int。忽略特定的下标值（译者注：因为a[3]越界了），这里下标值还用来表示数组元素的个数。
```c
int *p;
int a[3];
```

那么函数的定义呢？最开始，C的函数声明是把参数类型写在参数列表的括号外面，像这样：main是一个函数，因为表达式`main(argc, argv)`的返回值是int。
```
int main(argc, argv)
    int argc;
    char *argv[];
{ /* ... */ }
```

但是，现代C语言的写法是`int main(int argc, char *argv[]) { /* ... */ }`，和原始的写法在基本语法结构上是相同的。

C的声明语法是很棒的语法思想，对于简单类型能很好的工作，但是（随着类型的复杂）很快就变得混乱，典型的例子是申明一个函数指针，按照语法规范，是这样写的：`int (*fp)(int a, int b);`，这里fp是一个指向函数的指针，因为如果你写这个表达式`(*fp)(a,b)`，你会调用一个函数，它的返回值为int。

如果fp的某个参数也是个函数指针呢？`int (*fp)(int (*ff)(int x, int y), int b)`，这个表达式开始难以理解了。（为了能够理解这个表达式，我们先看一个语法特性），在声明函数时，可以把参数的名字省略掉，所以main函数可以这样声明：`int main(int, char *[])`，argv前面是这样声明的：`char *argv[]`，把声明语句`*`和`[]`中间的变量名去掉，剩下的就是argv这个变量的类型`char *[]`，对于这个类型把变量名放在中间看起来很奇怪（译者注：简单类型是`int x;`，变量名在最后，但是复杂类型`char *argv[]`，变量名在中间）。
>so you drop the name from the middle of its declaration to construct its type. It's not obvious, though, that you declare something of type char *[] by putting its name in the middle.

那就让我们看下如果把参数的名字都省略掉以后fp的声明：`int (*fp)(int (*)(int, int), int)`，参数名的位置很难明显的看出来，甚至都没法准确、清晰的看出来这是个函数指针声明了。

如果返回值类型是一个函数指针呢？`int (*(*fp)(int (*)(int, int), int))(int, int)`，要想看出来这是个fp的声明是很困难的。

你可以在设计更多的例子，但是这些例子都说明了C的声明语法导致了一些（可读性）方面的困难。

还有一点需要指出，因为类型名和声明语法是相同的，如果表达式中间有类型名就很难解析，这就是为什么C的类型转换需要给类型名加括号。例如：`(int)M_PI`。

### Go语法
C语言家族以外的语言通常使用不同的声明语法。Although it's a separate point, 变量名在前面，然后紧接着是一个冒号。所以前面的例子就变成了下面这样（我们这里虚构了一种声明语法，只是为了说明和C语言不同的声明语法）：
```
x: int
p: pointer to int
a: array[3] of int
```

这些声明阅读起来很清晰，也就是说你只要从左向右阅读。Go语言参考了这种声明语法，并省略了冒号以及一些关键字，目的是为了让声明语法更简洁：
```go
x int
p *int
a [3]int
```

需要指出的是，`[3]int`的声明语法和如何在表达式中引用数组是没有直接的联系的，我们会在下一节指针中详细讨论它。仅仅以一个分隔符语法的代码获得了声明语法的可读性。

现在来考虑函数，我们先把main函数的声明转换为Go语言的声明语法（Go语言中的main函数是不接受参数的）：`func main(argc int, argv []string) int`。表面上看，和C语言的声明语法没什么特别大的区别，只是把`char *`换成了`string`，但是Go的定义只需要从左往右阅读：main函数接收一个int参数和一个string slice参数，返回一个int。去掉参数名以后函数声明依然是清晰的：`func main(int, []string) int`，因为参数名在参数定义的最开始，所以去掉以后从左往右阅读不会导致混乱（译者注：C语言中函数指针作为参数时，参数名不在函数指针声明的最开头，例如TLDR中的例子）。

Go语言声明语法的从左往右阅读风格的好处之一就是对于复杂的类型仍然能保持清晰的可读性。下面是一个函数变量的声明（类比于C语言的函数指针）：`f func(func(int,int) int, int) int`、`f func(func(int,int) int, int) func(int, int) int`，其中第二个声明中的函数变量，它的返回值也是个函数，从左向右阅读，仍然很清晰。并且最前面的标识符永远是被声明的变量。

### 指针
Go语言中声明和表达式采用不同的语法：

1. 使编写和调用闭包更容易：`sum := func(a, b int) int { return a+b } (3, 4)`
2. 数组和slice中，Go的声明语法是把括号放在类型的左边，但是表达式中则把括号放在右边：`var a []int; x = a[1]`

Go语言中的指针是“声明和表达式拥有不同的语法”的例外。和C语言类似，Go使用*表示指针，但是我们没有下决心像数组、slice和函数那样让声明和表达式有相反的顺序。通过下面的例子我们可以发现这样做的原因：后缀的*会和乘法混淆。
>Pointers are the exception that proves the rule. ... but we could not bring ourselves to make a similar reversal for pointer types.

当然我们本可以像Pascal那样使用`^`表示指针来解决混淆的问题（然后再选择另一个运算符表示异或），但是我们没有这样。这就导致了当星号作为前缀时会把声明语法和表达式语法搞的很复杂。例如：对于非指针类型的转换这样写是合法的`[]int("hi")`（译者注：类型`[]int`不用加括号），但是对于指针类型的转换，就必须要对指针类型加括号`(*int)(nil)`。如果我们不用*作为指针语法，就不用加括号了。

所以Go的指针语法是和C语言绑定的，这就意味着Go不能打破C的语法：必须加括号才能区分“类型转换时的指针类型”和“表达式中对指针解引用”（译者注：因为Go只有指针类型是和C相同的，对于非指针类型声明语法和表达式语法是不同的，所以不用加括号）。
>We could have used the Pascal ^, and perhaps we should have, because the prefix asterisk on both types and expressions complicates things in a number of ways. Had we been willing to give up * as pointer syntax, those parentheses would be unnecessary.

```
var p *int
x = *p

var p *int
x = p*

var p ^int
x = p^
```

总之，我们相信Go的声明语法比C的更容易理解，特别是当类型变得复杂时。

### 注意
Go的声明是从左到右阅读的，这里已经指出C语言（的声明语法）需要螺旋式阅读（译者注：例如`int (*(*fp)(int (*)(int, int), int))(int, int)`），请看David Anderson写的文章[The "Clockwise/Spiral Rule"](http://c-faq.com/decl/spiral.anderson.html)。