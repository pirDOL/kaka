## [Go maps in action](https://blog.golang.org/go-maps-in-action)
6 February 2013 By Andrew Gerrand

### 简介
计算机科学中最常用的数据结构是哈希表。很多哈希表的实现有很多不同的特性，但是通常来说，所有的哈希表提供了快速的查找、添加和删除。Go提供了一个内置的map类型实现了哈希表。

### 定义和初始化
Go的map类型长成下面这个样子：KeyType可以是任何[可比较](http://golang.org/ref/spec#Comparison_operators)的类型（后续再详细讨论可比较）；ValueType可以是任意类型，包括map。例如：m变量是是一个key是string，value是int的map。

**map类型是引用类型**，和指针以及slice一样，**所以map的空值是nil**，空map不指向任何的初始化的map结构。读取nil的map和读取已初始化的空map相同，都是不返回任何结果，但是**写nil的map会导致panic**，因此不要这样做。使用内置的make函数初始化map，make函数会分配并初始化map内部的哈希数据结构，然后返回一个指向这个map的引用。map内部的数据结构的实现细节不是go语言本身实现，而是取决于具体运行的系统。这篇文章我们会侧重于map的使用，而不是map的实现。
```go
map[KeyType]ValueType

var m map[string]int

m = make(map[string]int)
```

### 使用map
Go提供了的map使用接口和通常map的语法很相像，例如：

1. 设置kv为route=>66
2. 读取key为route的value并赋值给一个新变量i
3. 如果读取的key不存在，会**返回value类型的零值**，key为root的不存在，value类型为int，对应的零值为int(0)
4. 内置的len函数返回map中kv对的数量
5. 内置delete函数从map中删除key，这个函数无返回值，如果key不存在就什么也不干
6. 测试某个key是否存在可以使用两个返回值的赋值语句，第一个值是key为route对应的value，如果key不存在，这个值就是value类型的零值，第二个值是bool类型，如果key存在，这个值为true，否则为false
7. 如果只想判断key是否存在，可以用下划线省略第一个值
8. 通过range迭代map
9. 初始化map字面常量，初始化空map只需要写一对空大括号，它的作用和make相同
```go
m["route"] = 66

i := m["route"]

j := m["root"] // j == 0

n := len(m)

delete(m, "route")

i, ok := m["route"]

_, ok := m["route"]

for key, value := range m {
    fmt.Println("Key:", key, "Value:", value)
}

commits := map[string]int{
    "rsc": 3711,
    "r":   2138,
    "gri": 1908,
    "adg": 912,
}

m = map[string]int{}
```

### 零值问题
**当key不存在时返回value类型的零值是为了使map使用更方便**

例1：bool的零值是false，map[key_type]bool就可以当作set来使用。遍历一个Nodes类型的链表并打印它的值，通过map[Node*]bool来判断链表中是否有环。
```go
type Node struct {
    Next  *Node
    Value interface{}
}
var first *Node

visited := make(map[*Node]bool)
for n := first; n != nil; n = n.Next {
    if visited[n] {
        fmt.Println("cycle detected")
        break
    }
    visited[n] = true
    fmt.Println(n.Value)
}
```

例2：slice的零值是nil，append一个nil的slice会创建一个新slice，所以向value_type为slice的map添加操作只需要一行代码，不需要判断key是否存在。下面的例子中，people是一个slice，元素的类型是Person。Person包含Name和Likes两个成员，创建一个map，key为喜好，value是有这个喜好的Person列表。打印喜欢cheese的人、打印喜欢bacon的人数，因为range和len会把nil的slice看作长度为0，因此这两个操作即使没人喜欢cheese或者bacon（生活中这当然不太可能），自然不会打印任何内容。
```go
type Person struct {
    Name  string
    Likes []string
}
var people []*Person

likes := make(map[string][]*Person)
for _, p := range people {
    for _, l := range p.Likes {
        likes[l] = append(likes[l], p)
    }
} 

for _, p := range likes["cheese"] {
    fmt.Println(p.Name, "likes cheese.")
}
fmt.Println(len(likes["bacon"]), "people like bacon.")
```

### key类型
前面提到过，map的key类型必须是可以比较的，[语言规范](http://golang.org/ref/spec#Comparison_operators)准确定义了这一点，简而言之，**可比较的类型包括：bool、数值、string、pointer、channel、interface以及只包含上述类型的数组和结构体**。很明显，slice、map、function都不能用==比较，因此不能作为key。

显然string、int以及其他的基本类型可以作为map的key，但是结构体可以作为key可能让人感觉有点意外，它的使用场景是**多维度的查询数据**。

例如想要统计网页按照国家的访问次数。hits是一个map，key是string，value是一个map（key是string，value是int）。外层map的key是网页链接，内层map的key是两个字母缩写的国家编码，表达式1获取澳大利亚人访问/doc页面的次数。

这种数据结构对于添加操作不友好，输入一个网页链接，需要先判断内层的map是否是nil，如果是nil，那么要先初始化内层map，然后才能统计。一种改进方式是使用一个map，key是一个struct类型，从而减少了复杂性。例如一个越南人访问了主页，增加统计次数只需要表达式2一行代码，同样，查询瑞士人访问spec页面的次数也是一行代码。
```go
hits := make(map[string]map[string]int)
n := hits["/doc/"]["au"] // 表达式1
func add(m map[string]map[string]int, path, country string) {
    mm, ok := m[path]
    if !ok {
        mm = make(map[string]int)
        m[path] = mm
    }
    mm[country]++
}
add(hits, "/doc/", "au")

type Key struct {
    Path, Country string
}
hits := make(map[Key]int)
hits[Key{"/", "vn"}]++ // 表达式2
n := hits[Key{"/ref/spec", "ch"}]
```

### 并发
[map是非线程安全的](http://golang.org/doc/faq#atomic_maps)，如果同时读写一个map，结果是未定义的。如果多个goroutine并发操作map，需要通过某些同步机制对map的访问操作进行协调。一种常用的保护方式是[sync.RWMutex](http://golang.org/pkg/sync/#RWMutex)。

下面的代码声明了一个counter变量，它是一个匿名的结构体，包含一个map和一个sync.RWMutex。读counter时需要获取读锁，写counter需要获取写锁：
```go
var counter = struct{
    sync.RWMutex
    m map[string]int
}{m: make(map[string]int)}

counter.RLock()
n := counter.m["some_key"]
counter.RUnlock()
fmt.Println("some_key:", n)

counter.Lock()
counter.m["some_key"]++
counter.Unlock()
```

### 迭代顺序
使用range循环迭代map的顺序是未定义的，不能确保两次迭代的顺序是相同的。从Go1.0开runtime会随机初始化map的迭代顺序，。如果需要稳定的迭代顺序，必须通过一个独立的数据结构维护迭代顺序。下面的例子通过一个存储了key的有序slice实现按照key顺序打印map[int]string。
```go
import "sort"

var m map[int]string
var keys []int
for k := range m {
    keys = append(keys, k)
}
sort.Ints(keys)
for _, k := range keys {
    fmt.Println("Key:", k, "Value:", m[k])
}
```