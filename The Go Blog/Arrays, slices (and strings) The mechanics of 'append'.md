## [Arrays, slices (and strings): The mechanics of 'append'](https://blog.golang.org/slices)

26 September 2013 By Rob Pike

### 简介
面向过程的编程语言中最常见的特性是数组的概念。数组看起来是很简单的东西，但是在编程语言实现数组时会遇到很多问题，例如：

* 固定长度还是可变长度
* 长度包含在类型中吗
* 多维数组如何实现
* 空数组的语意是什么

这些问题的答案决定了数组究竟是语言的特征还是语言设计中的核心部分。（原文：The answers to these questions affect whether arrays are just a feature of the language or a core part of its design.）

Go早期的开发中，花了一年的时间才上面的问题进行了考虑，并实现了正确的设计。其中最关键的是引入了slice，它建立在固定大小的数组上，提供灵活、可扩展的数据结构。直至今天，Go的初学者经常会因为其他语言的使用经历，导致对slice的工作原理感到疑惑。

这批blog中我们会通过不同的片段来解释append函数是如何工作的，以及背后的原因，最终尝试解释Go初学者的疑惑。

### 数组
数组是Go中重要的组成部分，如同楼房的地基一般，它通常隐藏在其他更常见的结构背后。我们必须先简短的介绍一下数组，然后才能继续有趣的、强大的、想法杰出的slice。

数组在Go程序中并不常见，因为数组的长度是数组的一部分，限制了使用场景。（原文：which limits its expressive power.）。s

例如：`var buffer [256]byte`声明了一个变量buffer，保存256字节。buffer的类型为[256]byte，数组的长度是类型的一部分。512字节的数组对应的类型`[512]byte`是另一种类型。

数组中的数据就是一系列的元素，buffer变量在内存中长成这样：`buffer: byte byte byte ... 256 times ... byte byte byte`。简而言之，buffer变量保存了256字节的数组，仅此而异。我们可以通过索引语法来访问元素：`buffer[0], buffer[1], ... buffer[255]`，越界访问会导致程序崩溃。

内置函数`len`返回数组、切片以及其他一些数据类型的元素个数。对于数组返回结果显而易见，`len(buffer)`返回固定值256。

数组在Go语言中可疑很好的表示矩阵，除此之外，更常见的应用是slice的底层存储。

### slice头
slice是本文的主题（原文：Slices are where the action is）。如果想使用好slice，必须准确理解它是什么以及它能干什么。

slice是用于描述一个数组中一个连续的片段的数据结构，数组本身并不保存在slice中。slice也不是个数组，它只*描述*数组的一个片段。

我们可以在前一节中的数组变量buffer上创建一个slice，描述[100,150)这段范围的元素：`var slice []byte = buffer[100:150]`。这里为了说明问题我们使用了变量的完整定义方式，slice是变量名，它的类型是[]byte（读作：slice of bytes）。slice变量初始化为数组buffer的100-150范围的元素。更惯用的语法是省略掉类型，直接写初始化表达式：`var slice = buffer[100:150]`。在函数中，我们可以使用更简短的声明方式：`slice := buffer[100:150]`。

这个slice变量的准确内容是什么？就目前来说，可以把slice认为是一个简单的数据结构，包含两个元素：长度和一个指向数组元素的指针，slice简化的Go实现如下面的代码所示：
```go
type sliceHeader struct {
    Length        int
    ZerothElement *byte
}


slice := sliceHeader{
    Length:        50,
    ZerothElement: &buffer[100],
}
```

当然，上面的代码只是一个简化的说明，实际上sliceHeader结构体是用户不可见的，并且指向数组元素的指针也取决于元素的实际类型，但是这个代码给出了slice实现的基本思想。

除了可以对array创建slice以外，还可以用slice创建slice：`slice2 := slice[5:10]`。这个操作创建了一个新的slice，slice2包括slice的第5-9个元素，也就是原始数组buffer的第105-109个元素，slice2的底层sliceHeader结构体大致长成这个样子，注意这个sliceHeader任然指向同一个底层数组，即buffer变量保存的数组。
```go
slice2 := sliceHeader{
    Length:        5,
    ZerothElement: &buffer[105],
}
```

我们还可以*reslice*，也就是根据一个slice创建一个新slice，然后把新slice保存到原来的slice变量中：`slice := slice[5:10]`，这样操作以后，slice变量的sliceHeader结构体会和slice2变量的一样。*reslice*使用很广泛，例如截断一个slice，`slice = slice[1:len(slice)-1]`丢弃slice的头尾两个元素。

\[练习：写出*reslice*以后的sliceHeader结构体\]
```
slice := sliceHeader{
    Length:        3,
    ZerothElement: &buffer[106],
}
```


我们经常听到Go程序员讨论slice header，这是因为slice header是真正保存在slice类型的变量中的东西。当你调用一个函数接收一个slice类型参数，例如[bytes.IndexRune](http://golang.org/pkg/bytes/#IndexRune)，slice header是真正传递给函数的。例如：调用`slashPos := bytes.IndexRune(slice, '/')`函数时，slice参数实际上传入的是slice header。

slice header中还有一个成员，我们下面会讨论到，但是先让我们看下当你的程序使用slice时slice header的存在情况。（原文：but first let's see what the existence of the slice header means when you program with slices.）

### 向函数传递slice
需要理解的很重要的一点是尽管slice包含了一个指针，但是它仍然是一个值。换言之，slice是一个包含一个指针和一个长度的结构体值，而不是一个指向结构体的指针。这一点很重要。

在前面的例子中我们调用了IndexRune，slice header是以传值的方式传递的，这一点在不同的场景下会有不同的表现。（原文：That behavior has important ramifications.）

看下面这个简单的函数，通过函数名就知道它的功能，使用`for range`按索引迭代slice，递增每个元素值。尽管slice header是以传值的方式传递的，但是header中包含了指向数组元素的指针，因此原始的slice header和传值拷贝后的header描述的是同一个数组。因此，当函数返回以后，通过原始的slice变量可以看到修改后的元素。
```
func AddOneToEachElement(slice []byte) {
    for i := range slice {
        slice[i]++
    }
}

func main() {
    slice := buffer[10:20]
    for i := 0; i < len(slice); i++ {
        slice[i] = byte(i)
    }
    fmt.Println("before", slice)
    AddOneToEachElement(slice)
    fmt.Println("after", slice)
}

// output
before [0 1 2 3 4 5 6 7 8 9]
after [1 2 3 4 5 6 7 8 9 10]
```

再看下面的例子，slice header指向的*数组内容*可以通过函数修改，但*header本身内容*不能。slice变量中保存的长度在调用函数SubtractOneFromLength以后并没有被修改，因为这个函数的实参是不是传入的slice变量，而是它的拷贝。如果想写一个函数修改slice header，需要把修改后的header以返回值的方式传递，就像下面的例子那样。这里传入的slice变量在调用函数以后没有被改变，但是返回值newSlice的长度是修改过的。
```
func SubtractOneFromLength(slice []byte) []byte {
    slice = slice[0 : len(slice)-1]
    return slice
}

func main() {
    fmt.Println("Before: len(slice) =", len(slice))
    newSlice := SubtractOneFromLength(slice)
    fmt.Println("After:  len(slice) =", len(slice))
    fmt.Println("After:  len(newSlice) =", len(newSlice))
}

//output
Before: len(slice) = 50
After:  len(slice) = 50
After:  len(newSlice) = 49
```

### slice指针：方法接收者
另一种通过函数修改slice header是传递slice header的指针，用这种方法再次实现前面的例子如下。这个例子看起来很笨拙，特别是需要增加一个临时变量处理指针访问的间接性。但是通过这个例子可以总结出slice指针最常见的使用场景，如果一个方法需要修改slice，那么方法的接收者需要使用指针。
```go
func PtrSubtractOneFromLength(slicePtr *[]byte) {
    slice := *slicePtr
    *slicePtr = slice[0 : len(slice)-1]
}

func main() {
    fmt.Println("Before: len(slice) =", len(slice))
    PtrSubtractOneFromLength(&slice)
    fmt.Println("After:  len(slice) =", len(slice))
}
```

例如我们想实现一个slice的方法，对slice在最后一个`/`的位置截断，我们可以这样实现：如果你运行这个例子，你会发现它能正常工作，更新slice。
```go
type path []byte

func (p *path) TruncateAtFinalSlash() {
    i := bytes.LastIndex(*p, []byte("/"))
    if i >= 0 {
        *p = (*p)[0:i]
    }
}

func main() {
    pathName := path("/usr/bin/tso") // Conversion from string to path.
    pathName.TruncateAtFinalSlash()
    fmt.Printf("%s\n", pathName)
}

// output
/usr/bin
```

\[练习：把方法接收者的类型从指针类型改为值类型，再次运行程序，解释发生了什么。\]
（译者注：方法接收者实际上可以看作普通函数的一个参数，从指针类型修改为值类型，只能对值传递时拷贝的slice实现截断，但是原来的slice没有截断。）

另一方面，如果需要实现一个方法把path中的小写字母转换成大写（忽略非英文字符），方法接收者可以是值类型，因为值传递的拷贝和原始slice都指向的是同一个底层数组。这里ToUpper方法使用了`for range`的第二个返回值，这样可以避免在循环体内写两次p[i]。
```
type path []byte

func (p path) ToUpper() {
    for i, b := range p {
        if 'a' <= b && b <= 'z' {
            p[i] = b + 'A' - 'a'
        }
    }
}

func main() {
    pathName := path("/usr/bin/tso")
    pathName.ToUpper()
    fmt.Printf("%s\n", pathName)
}
```

\[练习：把ToUpper的方法接收者改为指针类型，观察是否结果上有差异。\]
（译者注：显然没有差异。）
\[练习2：包ToUpper方法扩展为能够处理Unicode字符，不仅仅是ASCII。\]

### cap
让我们看一下面的例子：向一个slice增加一个元素。通过前一节的讨论，这里应该理解为什么需要返回修改后的slice。观察运行结果发现slice增加到一定长度就不能增加了。
```
func Extend(slice []int, element int) []int {
    n := len(slice)
    slice = slice[0 : n+1]
    slice[n] = element
    return slice
}

func main() {
    var iBuffer [10]int
    slice := iBuffer[0:0]
    for i := 0; i < 20; i++ {
        slice = Extend(slice, i)
        fmt.Println(slice)
    }
}

// output
[0]
[0 1]
[0 1 2]
[0 1 2 3]
[0 1 2 3 4]
[0 1 2 3 4 5]
[0 1 2 3 4 5 6]
[0 1 2 3 4 5 6 7]
[0 1 2 3 4 5 6 7 8]
[0 1 2 3 4 5 6 7 8 9]
panic: runtime error: slice bounds out of range

goroutine 1 [running]:
panic(0x1022c0, 0x1040a018)
    /usr/local/go/src/runtime/panic.go:500 +0x720
main.main()
    /tmp/sandbox197038436/main.go:27 +0x1e0
```

现在是时候讨论slice header中的第三个成员了：slice的容量。除了数组指针、长度以外，slice header还需要保存它的容量。`Capacity`字段记录了slice底层的数组中的空间，它表示`Length`能够增长到的最大长度。当slice尝试增长超过它的容量时，会导致底层数组访问越界，从而触发panic。
```go
type sliceHeader struct {
    Length        int
    Capacity      int
    ZerothElement *byte
}
```

在我们例子中，当通过`slice := iBuffer[0:0]`创建slice以后，它的slice header如下，`Capacity`字段等于底层数组的长度减去slice首元素在数组中的索引（在这个例子中slice首元素在数组中的索引是0）。如果想获取slice的容量，可以使用内置的`cap`函数。
```go
slice := sliceHeader{
    Length:        0,
    Capacity:      10,
    ZerothElement: &iBuffer[0],
}

if cap(slice) == len(slice) {
    fmt.Println("slice is full!")
}
```

### Make
如果我们向增长一个slice超过它的容量怎么办？答案是不能。根据定义，容量就是slice可以增长的上限。但是可以通过重新分配一个新的数组，把原来数组拷贝过来，然后修改slice header来等效的实现。

首先我们看一下分配。我们可以用内置的`new`函数分配一个更大的数组，然后用这个数组创建新的slice。更简单的方法是用内置的`make`方法，它分配一个新的数组并且创建一个slice header。`make`函数接收三个参数：slice的类型、初始长度和容量，容量就是分配的新数组的长度。例如：`slice := make([]int, 10, 15)`创建了一个slice，初始有10个元素，还能再增加5个元素。

下面的代码把一个[]int的容量翻倍，但是已有的元素个数（即长度）不变，运行下面的代码，新slice会有更多的空间增加新元素，直到下一次重新分配数组。
```go
slice := make([]int, 10, 15)
fmt.Printf("len: %d, cap: %d\n", len(slice), cap(slice))
newSlice := make([]int, len(slice), 2*cap(slice))
for i := range slice {
    newSlice[i] = slice[i]
}
slice = newSlice
fmt.Printf("len: %d, cap: %d\n", len(slice), cap(slice))
```

当（通过`slice := []int{1, 2, 3}`）创建slice时，长度和容量是相等的。`make`函数为这种常见的使用方式提供了一个快捷方式，如果调用`make`时不传递第三个参数，那么长度和容量就是相等的。例如：`gophers := make([]Gopher, 10)`创建的gophers slice的长度和容量都是10。

### Copy
当我们把一个slice的容量翻倍时，在上一节我们是写了一个循环从老的数组总把数据拷贝到新的数组。Go提供了一个内置函数`copy`来简化这个操作，它接收两个slice，把第二个参数的slice拷贝到第一个参数的slice。因此，上一节的循环可以简化为：`copy(newSlice, slice)`。

`copy`函数是智能的，它只会拷贝它能拷贝的内容，换言之，它拷贝的元素数量是两个slice长度的最小值。This can save a little bookkeeping. 另外，`copy`返回整数，表示它拷贝的元素数量，尽管通常不需要检查这个值。

`copy`函数还能够处理两个slice重叠的情况，因此可以使用它来移动一个slice中的元素。下面这个例子展示了如何用`copy`实现向slice中间插入一个元素：
```go
// Insert inserts the value into the slice at the specified index,
// which must be in range.
// The slice must have room for the new element.
func Insert(slice []int, index, value int) []int {
    // Grow the slice by one element.
    slice = slice[0 : len(slice)+1]
    // Use copy to move the upper part of the slice out of the way and open a hole.
    copy(slice[index+1:], slice[index:])
    // Store the new value.
    slice[index] = value
    // Return the result.
    return slice
}

func main() {
    slice := make([]int, 10, 20) // Note capacity > length: room to add element.
    for i := range slice {
        slice[i] = i
    }
    fmt.Println(slice)
    slice = Insert(slice, 5, 99)
    fmt.Println(slice)
}

// output
[0 1 2 3 4 5 6 7 8 9]
[0 1 2 3 4 99 5 6 7 8 9]
```

上面的函数中有一些值得说明的地方：首先，这个函数修改了slice header，因此需要返回新的slice；其次，创建slice时使用了简写，例如：`slice[i:]`表示`slice[i:len(slice)]`，再比如：尽管我们目前还没这么写过，但是我们可以把创建slice时冒号前后的两个值都省略，此时`slice[:]`表示这个slice本身，当根据一个数组创建slice时，如果创建的slice描述这个数组的所有元素，那么可以这样写`slice := array[:]`。

### Append: An example
在前面我们实现了一个Extend函数实现向slice增加一个元素。当时的实现是有bug的，如果slice的容量太小会导致函数崩溃。同理，Insert函数有同样的问题。现在我们尝试去修复这个问题，为[]int实现一个鲁棒性的Extend。
```go
func Extend(slice []int, element int) []int {
    n := len(slice)
    if n == cap(slice) {
        // Slice is full; must grow.
        // We double its size and add 1, so if the size is zero we still grow.
        newSlice := make([]int, len(slice), 2*len(slice)+1)
        copy(newSlice, slice)
        slice = newSlice
    }
    slice = slice[0 : n+1]
    slice[n] = element
    return slice
}
```

在这个例子中，因为slice header可能被修改（重新分配时新slice描述的是一个不同的底层数组），所有需要返回新slice。下面是一小段代码用于展现当slice容量用满以后发生了什么：注意到起初slice的底层数组容量是5，当它填满以后，会分配一个新数组，对应的新slice的容量和数组元素地址都发生了改变。
```
slice := make([]int, 0, 5)
for i := 0; i < 10; i++ {
    slice = Extend(slice, i)
    fmt.Printf("len=%d cap=%d slice=%v\n", len(slice), cap(slice), slice)
    fmt.Println("address of 0th element:", &slice[0])
}

// output
len=1 cap=5 slice=[0]
address of 0th element: 0x10432200
len=2 cap=5 slice=[0 1]
address of 0th element: 0x10432200
len=3 cap=5 slice=[0 1 2]
address of 0th element: 0x10432200
len=4 cap=5 slice=[0 1 2 3]
address of 0th element: 0x10432200
len=5 cap=5 slice=[0 1 2 3 4]
address of 0th element: 0x10432200
len=6 cap=11 slice=[0 1 2 3 4 5]
address of 0th element: 0x10436120
len=7 cap=11 slice=[0 1 2 3 4 5 6]
address of 0th element: 0x10436120
len=8 cap=11 slice=[0 1 2 3 4 5 6 7]
address of 0th element: 0x10436120
len=9 cap=11 slice=[0 1 2 3 4 5 6 7 8]
address of 0th element: 0x10436120
len=10 cap=11 slice=[0 1 2 3 4 5 6 7 8 9]
address of 0th element: 0x10436120
```

有了实现鲁棒的Extend函数的经验，我们可以实现一个更强大的函数，可以向一个slice增加多个元素。为了实现这一点，我们使用Go的可变函数参数特性：在函数调用时把参数列表转换成slice。我们把这个函数命名为Append，第一版我们只是循环的调用Extend函数。

通过第一版的实现，可以很清楚的了解可变函数参数特性：Append函数接收的第一个参数是一个slice，后面跟随若干个int参数。这些参数对于Append函数会被保存在一个[]int中，即`for range`迭代的items。我们用`_`符号省略了迭代时的索引，因为这里不需要使用它。

另外，这个例子中我们用常量初始化了一个slice：`slice := []int{0, 1, 2, 3, 4}`，首先是slice的类型，然后是大括号中定义的元素值。

我们实现的Append函数有一个很有意思的地方是不仅支持增加元素，还可以在调用函数时把一个slice通过`...`符号按元素展开传给Append。

最后，我们可以改进Append的实现，通过把Extend的内部实现挪到Append中，避免多次内存分配提高效率。我们用了两次`copy`，一次是把旧slice中的元素拷贝到新分配的数组中，另一次是把要添加的元素拷贝到slice的最后。

```go
// Append appends the items to the slice.
// First version: just loop calling Extend.
func Append(slice []int, items ...int) []int {
    for _, item := range items {
        slice = Extend(slice, item)
    }
    return slice
}

slice := []int{0, 1, 2, 3, 4}
fmt.Println(slice)
slice = Append(slice, 5, 6, 7, 8)
fmt.Println(slice)

// output
[0 1 2 3 4]
[0 1 2 3 4 5 6 7 8]

slice1 := []int{0, 1, 2, 3, 4}
slice2 := []int{55, 66, 77}
fmt.Println(slice1)
slice1 = Append(slice1, slice2...) // The '...' is essential!
fmt.Println(slice1)

// output
[0 1 2 3 4]
[0 1 2 3 4 55 66 77]

// Append appends the elements to the slice.
// Efficient version.
func Append(slice []int, elements ...int) []int {
    n := len(slice)
    total := len(slice) + len(elements)
    if total > cap(slice) {
        // Reallocate. Grow to 1.5 times the new size, so we can still grow.
        newSize := total*3/2 + 1
        newSlice := make([]int, total, newSize)
        copy(newSlice, slice)
        slice = newSlice
    }
    slice = slice[:total]
    copy(slice[n:], elements)
    return slice
}
```

### Append: The built-in function
现在我们有了足够的动力来设计内置的`append`函数，它和我们的Append函数做的事情是一样的，效率也是一样的，但是支持任意的slice类型。

Go语言的弱点是任何泛型操作都需要运行时系统的支持，未来可能会有一天修改这个机制，但是目前为了slice更容易使用，Go提供了一个内置的泛型`append`函数，它和我们为[]int实现的版本做的事情是相同的，只不过支持任意的slice类型。

需要记住，因为slice header总是会在调用`append`以后被修改（长度肯定会变化），需要保存函数返回的slice，实际上，编译器会在你调用`append`但是不保存返回值时会报错。

对于最后一行结果，值得仔细思考一下，如何设计slice可以让这种调用方式正确工作。（原文：It's worth taking a moment to think about the final one-liner of that example in detail to understand how the design of slices makes it possible for this simple call to work correctly.）

关于`append`和`copy`还有很多的例子，其他slice的使用方法可以阅读社区的wiki[Slice Tricks](https://golang.org/wiki/SliceTricks)
```go
// Create a couple of starter slices.
slice := []int{1, 2, 3}
slice2 := []int{55, 66, 77}
fmt.Println("Start slice: ", slice)
fmt.Println("Start slice2:", slice2)

// Add an item to a slice.
slice = append(slice, 4)
fmt.Println("Add one item:", slice)

// Add one slice to another.
slice = append(slice, slice2...)
fmt.Println("Add one slice:", slice)

// Make a copy of a slice (of int).
slice3 := append([]int(nil), slice...)
fmt.Println("Copy a slice:", slice3)

// Copy a slice to the end of itself.
fmt.Println("Before append to self:", slice)
slice = append(slice, slice...)
fmt.Println("After append to self:", slice)

// output
Start slice:  [1 2 3]
Start slice2: [55 66 77]
Add one item: [1 2 3 4]
Add one slice: [1 2 3 4 55 66 77]
Copy a slice: [1 2 3 4 55 66 77]
Before append to self: [1 2 3 4 55 66 77]
After append to self: [1 2 3 4 55 66 77 1 2 3 4 55 66 77]
```

### Nil
需要额外指出的是，根据我们对于slice的了解可以很自然的推断出slice的零值应该是slice header的零值，当然也可以简写为`sliceHeader{}`。
```go
sliceHeader{
    Length:        0,
    Capacity:      0,
    ZerothElement: nil,
}
```

关键之处在于指向底层数组元素的指针也是nil。**通过`array[0:0]`创建的slice并不是零值，即使它的长度甚至是容量都是0，但是它的指针不是nil。**

**值得明确的是，空slice可以增长（假设它的容量不是0），但是零值slice因为没有底层的数组，所以不能存放任何元素。**

零值slice从功能上等效于一个长度为0的slice，尽管零值slice没有底层的数组。如果给零值slice分配了数组，就可以向它增加元素，在前面的例子中通过向一个零值slice append实现拷贝slice。（原文：As an example, look at the one-liner above that copies a slice by appending to a nil slice.）

### Strings
说到slice就不能不说string，这节简要的讨论一下string。

string实际上非常简单：它是只读的[]byte，除此之外，Go语言对string增加了一点额外的语法支持。

因为是只读的，所以不需要容量（不能向string添加元素），大多数情况下你可以把string认为是只读的[]byte。对于初学者：索引string返回字节，可以对一个string创建slice得到子串。通过前面的讨论，现在应该很清楚对一个string创建slice发生了什么。
```
slash := "/usr/ken"[0] // yields the byte value '/'.
usr := "/usr/ken"[0:4] // yields the string "/usr"
```

我们可以根据普通的[]byte创建string：`str := string(slice)`，当然也可以反过来：`slice := []byte(usr)`。

string底层的数组是不能被用户访问的，除了通过string本身以外。这就意味着当我们进行上面的转换时，必须要对底层的数组进行拷贝。Go在转换[]byte和string时完成这个操作，你不需要关心。因为底层的数组发生了拷贝，因此在[]byte和string转换以后，[]byte和string底层的数组不会互相影响。

使用类似slice的方式设计string对于创建子串效率很高：创建string的子串只需要创建一个有两个元素的string header。因为string是只读的，原始的string和子串可以共享同一个底层数组。

string起初的实现中是每个string都分配一个底层数组。但是当slice增加到Go以后，它提供了一个高效率处理string的模型，通过benchmark可以看到性能提高很大。

当然还有更过关于string的阅读材料，[这篇blog](http://blog.golang.org/strings)深入的讨论了string。

### 结论
为了理解slice如何工作，需要理解它是如何实现的。slice header是一个小体积的数据结构，每个slice变量关联到一个slice header，它描述了一个已经分配的数组中的一个片段。当我们以传值的方式传递slice时，slice header会拷贝，但是指向的底层数组是共享的。

当你理解了slice的工作原理，slice就变得容易使用并且功能强大，特别是结合内置函数例如：`copy`和`append`。

### 延伸阅读
互联网上可以找到很多关于Go的slice的材料，如前文提到的，["Slice Tricks" Wiki page](https://golang.org/wiki/SliceTricks)包含了很多例子，[Go Slices](http://blog.golang.org/go-slices-usage-and-internals)博客用清晰的图描述了slice的内存布局。Russ Cox的文章[Go Data Structures](http://research.swtch.com/godata)包含了很多有关slice以及Go的其他数据结构的讨论。

还有很多可供参考的材料，最好的学习slice的方法是使用它。
