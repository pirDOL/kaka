## [Go Slices: usage and internals](https://blog.golang.org/go-slices-usage-and-internals)
5 January 2011

### 简介
go语言的slice类型提供了一种方便、高效的方法来管理某种类型数据的序列。slice类似于其他语言中的数组，但是slice也有许多特有的属性。这篇文章会介绍slice是什么以及如何使用它们。

### 数组
slice类型是在go语言的array类型基础上建立的抽象，所以理解slice的前提是理解array。

array的定义指定了长度和元素类型，例如[4]int表示4个整数的数组。数组的长度是固定的，换言之长度是类型的一部分（[4]int和[5]int是两个不同、不兼容的类型）。数组可以用常规的方式索引，s[n]
访问第n个元素（从0开始）。

```go
var a [4]int
a[0] = 1
i := a[0]
// i == 1
```

数组不需要显式的初始化，零值数组是随时可用的，数组元素的初值是相应类型的零值。
```go
// a[2] == 0, the zero value of the int type
```

[4]int的内存表示就是4个整数顺序的平铺。

![](Go Slices usage and internals/1.png)

go语言中的数组是值，数组类型的变量表示整个数组，而不是（像C语言那样）数组名是指向数组第一个元素的指针。这就意味着当传递数组或者对数组赋值时，会导致数组内容的拷贝。（为了避免不必要的拷贝，你可以传递一个指向数组的指针，但是指针毕竟不是数组。）一种理解数组的方式是把它看作是一种带有数字索引而不是字段名struct，并且长度固定。

数组字面值可以使用如下方式指定：
```go
b := [2]string{"Penn", "Teller"}
```
或者可以让编译器自动计算数组元素个数：
```go
b := [...]string{"Penn", "Teller"}
```
上面两种情况中，b的类型都是[2]string

### slice
数组有适合的使用场景，但它们缺少灵活性，所以在go代码中其实很少使用数组。取而代之的是随处可见的slice。slice基于array构建，并且提供了更强大的功能和便利。

slice的类型声明是[]T，T是slice元素的类型。不同于数组，slice没有指定的长度。

slice字面值的声明和array类似，但是slice不需要填写元素个数。
```go
letters := []string{"a", "b", "c", "d"}
```

slice可以通过内置函数make创建，函数签名如下：
```go
func make([]T, len, cap) []T
```
其中T是slice的元素类型。make函数接收一个类型、一个长度和一个可选的容量参数。make会创建一个array，然后返回指向这个array的slice。
```go
var s []byte
s = make([]byte, 5, 5)
// s == []byte{0, 0, 0, 0, 0}
```

当忽略容量参数时，缺省值为指定的长度参数。上面代码的更简洁的版本为：
```go
s := make([]byte,5)
```

slice的长度和容量可以通过内置的len和cap函数获得。
```go
len(s) == 5
cap(s) == 5
```

下面两个小节讨论了长度和容量的关系。

slice的零值是nil，对应的len和cap函数返回0。

slice还可以在已有的array或者slice上创建，创建的方法是通过冒号隔开的两个下标指定一个半开半闭的区间。例如表达式b[1:4]创建了一个slice，它包含b的第1个到3个元素（创建得到的slice下标范围是0-2，不是1-3）
```go
b := []byte{'g', 'o', 'l', 'a', 'n', 'g'}
// b[1:4] == []byte{'o', 'l', 'a'}, sharing the same storage as b
```

slice创建的开始和结束下标是可选的，缺省值分别为0和slice的长度：
```go
// b[:2] == []byte{'g', 'o'}
// b[2:] == []byte{'l', 'a', 'n', 'g'}
// b[:] == b
```

根据array创建slice的语法如下：
```go
x := [3]string{"Лайка", "Белка", "Стрелка"}
s := x[:] // a slice referencing the storage of x
```

### slice的内部实现
slice是一个数组片段的描述，它包含一个指向数组的指针、片段的长度以及容量（片段的最大长度）。
![](Go Slices usage and internals/2.png)

前面通过make([]byte, 5)创建的的变量s，其结构如下：
![](Go Slices usage and internals/3.png)

长度是slice引用的元素个数，容量是底层array的元素数量（从slice指针指向的第一个数组元素开始计算）。下面的例子清楚区分了二者。

当我们在s上创建一个slice，观察新slice数据结构的变化以及和底层数组的关系。
```go
s = s[2:4]
```
![](Go Slices usage and internals/4.png)

slicing操作（在slice上创建slice）并没有拷贝slice的数据，而是创建了一个新的slice结构体指向原来的array。这使得slice操作和数组索引操作一样高效。因此修改slice的元素会修改原始slice的元素。
```go
d := []byte{'r', 'o', 'a', 'd'}
e := d[2:] 
// e == []byte{'a', 'd'}
e[1] = 'm'
// e == []byte{'a', 'm'}
// d == []byte{'r', 'o', 'a', 'm'}
```

前面我们创建了一个长度日容量短的slice，我们可以重新slicing，把它的长度增长到容量：
```go
s = s[:cap(s)]
```
![](Go Slices usage and internals/5.png)

slice不能增长超过它的容量。如果非要这么做会导致运行时panic，就和array和slice索引越界一样。同样的，如果想访问slice底层数组前面的元素，不能通过重新slicing负值的方式实现。

### slice的增长（copy和append函数）
增长slice的容量必须新建一个更大的slice，然后把原来的slice中内容拷贝进去。这个技术是其他语言中动态数组用户程序背后的实现。下一个例子展示了如何倍增一个slice的容量：
```go
t := make([]byte, len(s), (cap(s)+1)*2) // +1 in case cap(s) == 0
for i := range s {
    t[i] = s[i]
}
s = t
```

使用内置的copy函数可以代替常用的循环拷贝操作。就像函数名一样，copy从一个源slice拷贝数据到目的地slice，返回值为拷贝的元素个数：
```go
func copy(dst, src []T) int
```

copy函数支持在长度不同的slice之间拷贝（拷贝到短的那个slice为止）。另外，copy能够处理源slice和目的slice有重叠的情况。

使用copy简化上面的代码片段：
```go
t := make([]byte, len(s), (cap(s)+1)*2)
copy(t, s)
s = t
```

另一个常用的操作是向slice后面追加数据。这个函数追加byte类型的元素到[]byte类型的slice，如果需要的话会增加slice的容量，返回更新过的slice结构体。

```go
func AppendByte(slice []byte, data ...byte) []byte {
    m := len(slice)
    n := m + len(data)
    if n > cap(slice) { // if necessary, reallocate
        // allocate double what's needed, for future growth.
        newSlice := make([]byte, (n+1)*2)
        copy(newSlice, slice)
        slice = newSlice
    }
    slice = slice[0:n]
    copy(slice[m:n], data)
    return slice
}
```

AppendByte可以这样使用：
```go
p := []byte{2, 3, 5}
p = AppendByte(p, 7, 11, 13)
// p == []byte{2, 3, 5, 7, 11, 13}
```

像AppendByte这样的函数是很有用的，因为它能够在用户的代码中完整的控制slice的增长方式，取决于程序的特性，可能需要分配或大或小的内存块或者是限制重新分配的slice容量的上上限。

但是大多数程序不需要这么细粒度的控制，所以Go提供了内置的append函数适用于大多数目的，函数签名如下：
```go
func append(s []T, x ...T) []T
```

append函数添加元素x到s的最后，如果需要的话增长slice的容量。
```go
a := make([]int, 1)
// a == []int{0}
a = append(a, 1, 2, 3)
// a == []int{0, 1, 2, 3}
```

如果需要把一个slice追加到另一个slice后面，使用...运算符把第二个参数（slice）扩展为一个参数列表：
```go
a := []string{"John", "Paul"}
b := []string{"George", "Ringo", "Pete"}
a = append(a, b...) // equivalent to "append(a, b[0], b[1], b[2])"
// a == []string{"John", "Paul", "George", "Ringo", "Pete"}
```

因为零值的slice的长度为0，所以可以声明一个slice（默认是零值），然后在循环中追加数据。
```go
// Filter returns a new slice holding only
// the elements of s that satisfy f()
func Filter(s []int, fn func(int) bool) []int {
    var p []int // == nil
    for _, v := range s {
        if fn(v) {
            p = append(p, v)
        }
    }
    return p
}
```

### A possible "gotcha"
如前文所述，在一个slice上创建slice不会复制底层的数组。底层的数组在它的应用计数为0之前都会保存在内存中。有时，这会导致程序在内存中保存全部数据，但是只有其中一小部分是需要的。

例如：FindDigits函数把一个文件加载到内存中，然后搜索这个文件找第一个连续的数字串，并把它们以slice的方式返回。
```go
var digitRegexp = regexp.MustCompile("[0-9]+")

func FindDigits(filename string) []byte {
    b, _ := ioutil.ReadFile(filename)
    return digitRegexp.Find(b)
}
```

上面的代码如同做广告一样工作，但是返回的[]byte指向一个包含整个文件的array，因为返回的slice引用到了原始的array，只要这个slice不被销毁那么GC就不能释放array，文件中绝大部分没用的数据保存在内存中。

译注：[Find源码](https://github.com/golang/go/blob/master/src/regexp/regexp.go)
```go
func (re *Regexp) Find(b []byte) []byte {
    a := re.doExecute(nil, b, "", 0, 2)
    if a == nil {
        return nil
    }
    return b[a[0]:a[1]]
}
```

解决这个问题的一种方式是返回前拷贝感兴趣的数据到一个新的slice中。
```go
func CopyDigits(filename string) []byte {
    b, _ := ioutil.ReadFile(filename)
    b = digitRegexp.Find(b)
    c := make([]byte, len(b))
    copy(c, b)
    return c
}
```

这个函数更简洁的版本是通过append实现，留给读者做练习。

### 更多阅读
[Effective Go](http://golang.org/doc/effective_go.html)包含了slice和array的深入讨论，[Go语言语法](http://golang.org/doc/go_spec.html)定义了slice以及相关的helper函数。

By Andrew Gerrand