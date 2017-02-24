## [JSON and Go](https://blog.golang.org/json-and-go)
25 January 2011 By Andrew Gerrand

### 简介
JSON（JavaScript Object Notation）是一种简单的数据交换格式。从语法上它和JavaScript的对象和列表很相似，它通常用在浏览器的JavaScript程序和web后端服务之间通信，除此之外还有其他很多的应用场景。[JSON的官方网页](http://json.org/)提供了清晰、准确的JSON标准定义。[json包](http://golang.org/pkg/encoding/json/)使得Go程序读写JSON数据十分简单。

### 编码
使用[Marshal](http://golang.org/pkg/encoding/json/#Marshal)函数编码JSON数据，输入一个Go的结构体，例如Message，m是一个Message的实例，可以用json.Marshal来生成m对应的JSON格式。如果编码成功，返回nil的error，以及一个包含JSON数据的[]byte。

只有能够被JSON合法格式表示的数据结构才能被编码：

1. JSON Object只支持key为string，如果对Go的map进行JSON编码，map只支持map[string]T类型，其中T的类型是json包支持的Go类型。
2. channel、complex、function不能编码
3. 循环的数据结构不能编码（译者注：例如链表），这会导致Marshal函数无限循环
4. 指针会被编码为它指向的值，nil指针会编码为null
5. 结构体中未导出的字段（首字母小写）会在编码时忽略，只有导出字段才会出现在编码后的JSON输出中

```go
func Marshal(v interface{}) ([]byte, error)

type Message struct {
    Name string
    Body string
    Time int64
}

m := Message{"Alice", "Hello", 1294706395881547000}
b, err := json.Marshal(m)
b == []byte(`{"Name":"Alice","Body":"Hello","Time":1294706395881547000}`)
```

### 解码
使用[Unmarshal](http://golang.org/pkg/encoding/json/#Unmarshal)函数解码JSON，首先必须创建一个存储解码后对象的变量m，然后调用json.Unmarshal，传递一个[]byte类型的JSON字符串以及m的地址，如果JSON字符串是合法的并且能和m的类型兼容，返回nil的error，m中存储了JSON字符串对应的数据结构，就如同直接初始化m一样。

Unmarshal怎么知道JSON字符串中的key和结构体中成员是如何对应的？例如JSON字符串中有一个key为Foo，Unmarshal会按照下面的顺序查看结构体的成员

1. 导出成员 && 指定了tag为Foo
2. 导出成员 && 名字为Foo
3. 导出成员 && 名字为FOO或者foo以及其他任何忽略大小写的匹配

如果JSON字符串中的key在结构体中找不到对应的成员，Unmarshal只会初始化结构体中能够找到的成员，下面的例子中只有Name字段会被填充，JSON字符串中的Food字段会被忽略。这种行为对于从一个很大的JSON字符串中提取一部分字段是很有用的。另外，结构体中的未导出字段不会被Unmarshal修改。

```go
func Unmarshal(data []byte, v interface{}) error

var m Message
err := json.Unmarshal(b, &m)
m = Message{
    Name: "Alice",
    Body: "Hello",
    Time: 1294706395881547000,
}

b := []byte(`{"Name":"Bob","Food":"Pickle"}`)
var m Message
err := json.Unmarshal(b, &m)
```

### 空接口实现泛型JSON
如果不知道JSON字符串的格式怎么办？空接口中没有任何方法，因此**所有的Go类型都实现了空接口，因此空接口可以作为任何类型的容器**。通过类型断言可以获取空接口底层真实的类型，如果不知道类型，可以通过type switch判断。json包使用map[string]interface{}来支持泛型JSON object，[]interface{}支持泛型JSON array。任意的类型JSON值在Unmarshal时都可以存储到interface{}中，Go和JSON的类型对应关系为：

|Go|JSON|
|--|--|
|bool|布尔值|
|float64|数值|
|string|字符串|
|nil|null|

```go
var i interface{}
i = "a string"
i = 2011
i = 2.777

r := i.(float64)
fmt.Println("the circle's area", math.Pi*r*r)

switch v := i.(type) {
case int:
    fmt.Println("twice i is", v*2)
case float64:
    fmt.Println("the reciprocal of i is", 1/v)
case string:
    h := len(v) / 2
    fmt.Println("i swapped by halves is", v[h:]+v[:h])
default:
    // i isn't one of the types above
}
```

### 解码任意的数据
考虑如下存储在变量b中的JSON字符串，如果不知道JSON字符串的格式，需要使用interface{}解码，解码后变量f的类型是一个map[string]interface{}，key为string，value是interface{}。我们可以通过类型断言把f转换为map[string]interface{}，然后遍历这个map，对value的interface{}通过type-switch获取真正的value类型。这样可以在类型安全的前提下，实现解析未知格式的JSON字符串。
```go
b := []byte(`{"Name":"Wednesday","Age":6,"Parents":["Gomez","Morticia"]}`)
var f interface{}
err := json.Unmarshal(b, &f)
f = map[string]interface{}{
    "Name": "Wednesday",
    "Age":  6,
    "Parents": []interface{}{
        "Gomez",
        "Morticia",
    },
}
m := f.(map[string]interface{})
for k, v := range m {
    switch vv := v.(type) {
    case string:
        fmt.Println(k, "is string", vv)
    case int:
        fmt.Println(k, "is int", vv)
    case []interface{}:
        fmt.Println(k, "is an array:")
        for i, u := range vv {
            fmt.Println(i, u)
        }
    default:
        fmt.Println(k, "is of a type I don't know how to handle")
    }
}
```

### 引用类型
下面定义一个前面例子中JSON字符串对应的Go结构体FamilyMember，反序列化到FamilyMember结果符合预期。但是如果我们仔细观察一下会发现一个值得注意的要点。通过var声明FamilyMember类型的变量m，把m的指针传递给Unmarshal，此时m的Parents成员还是零值的slice。Unmarshal会分配一个新slice，赋值给Parents，并用JSON字符串中的内容填充。**Unmarshal对于引用类型（指针、slice、map）都会分配内存**。

接着我们考虑Foo这个结构体，如果JSON字符串中有一个Bar对象，那么Unmarshal会分配一个新的Bar结构体，并根据JSON字符串中的内容填充，并把Bar结构体的指针赋值为Foo.Bar，如果JSON字符串中没有Bar对象，Foo.Bar就是nil。

这种特性对于下面的场景很有用：如果一个应用程序需要接收不同的消息类型，例如你定义了一个接收消息的结构体IncomingMessage，发送方发送的JSON字符串中可以有Cmd或Msg字段，也可以两个都有，取决于消息的类型。当Unmarshal解析JSON字符串时，有哪个字段，就会填充IncomingMessage中相应的字段。接收方根据结构体中非空的指针，就可以知道接收到了那种信息。
```go
type FamilyMember struct {
    Name    string
    Age     int
    Parents []string
}
var m FamilyMember
err := json.Unmarshal(b, &m)

type Foo struct {
    Bar *Bar
}
type IncomingMessage struct {
    Cmd *Command
    Msg *Message
}
```

### 流式编解码
json包提供了Decoder和Encoder类型支持流式JSON数据读写。NewDecoder和NewEncoder分别包装了io.Reader和io.Write接口类型。下面是一个例子从标准输入中读取一系列JSON字符串，解析JSON字符串，删除除了Name以外的所有kv，然后重新编码为JSON字符串，写入到标准输出。因为Reader和Writer无处不在，所以Decoder和Encoder类型可以应用在广泛的场景中，例如从HTTP连接、WebSocket或者文件中读写。

```go
func NewDecoder(r io.Reader) *Decoder
func NewEncoder(w io.Writer) *Encoder

package main

import (
    "encoding/json"
    "log"
    "os"
)

func main() {
    dec := json.NewDecoder(os.Stdin)
    enc := json.NewEncoder(os.Stdout)
    for {
        var v map[string]interface{}
        if err := dec.Decode(&v); err != nil {
            log.Println(err)
            return
        }
        for k := range v {
            if k != "Name" {
                delete(v, k)
            }
        }
        if err := enc.Encode(&v); err != nil {
            log.Println(err)
        }
    }
}
```

### 参考
更多的内容请阅读[json包文档](http://golang.org/pkg/encoding/json/)，json使用的例子可以参考[jsonrpc包](http://golang.org/pkg/net/rpc/jsonrpc/)的代码。
