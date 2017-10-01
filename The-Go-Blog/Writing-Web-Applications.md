## [Writing Web Applications](https://golang.org/doc/articles/wiki/)

### TLDR
1. 本文介绍了如何用Go语言编写web应用。
1. 体现了DRY的地方很多：把渲染模板的代码收敛到一个函数renderTemplate，通过闭包把检验URL的代码收敛到一个地方。

### 正文
#### 简介 
本教程将讨论： 

* 创建一个支持加载和保存方法的数据结构 
* 使用net/http包来构建web应用       程序 
* 使用html/template包来处理HTML模板 
* 使用regexp包来验证用户输入 
* 使用闭包

基本知识： 
* 编程经验 
* 了解基本的web技术(HTTP、HTML) 
* 一些UNIX/DOS命令行知识 

#### 开始 
现在，你需要一个能运行FreeBSD、Linux、OS X或Windows的机器。我们用`$`` 代表命令提示符。

安装Go语言环境（参考[安装说明](https://golang.org/doc/install)）。 

为本教程新建一个目录，将新建目录添加到GOPATH环境变量，然后命令行切换到新建目录:```
$ mkdir gowiki
$ cd gowiki 
```

创建一个名为wiki.go的源文件，使用你喜欢的编辑器打开，并添加以下代码：
```golang
package main
import (
    "fmt"
    "io/ioutil"
)
```

我们从标准库导入了fmt和ioutil包。后面我们将实现更多的功能，到时候我们会添加更多的包到import声明。 

#### 数据结构 
我们现在开始定义数据结构。wiki由一些列相互关联的页面组成，每个页面有一个标题和一个主体（页面的内容）。所以我们定义的Page结构体包含title和body两个成员。
```golang 
type Page struct {
    Title string
    Body []byte
}
```

`[]byte`表示元素类型为byte的slice（更多内容参考：[Slices: usage and internals](https://golang.org/doc/articles/slices_usage_and_internals.html)）。 我们将Body成员定义为`[]byte`而不是`string`是因为我们希望和io库很好的配合，在后面会看到。 

`Page`结构体描述了页面内容如何被保存在内存中。但是如何进行持久存储页面呢？ 我们可以为Page类型写一个save方法：
```golang 
func (p *Page) save() error {
    filename := p.Title + ".txt"
    return ioutil.WriteFile(filename, p.Body, 0600)
}
```

save方法的签名表示这样的含义：“这是一个方法，名字叫save，方法的接收者p是一个指向Page类型结构体的指针。 方法没有参数，但有一个error类型的返回值。” 

该方法会将Page的Body成员的值保存到一个文本文件。为了简化，我们使用Title成员的值作为文件的名字。

save方法返回类型为error的错误值，它是WriteFile函数的返回值（这个标准库函数功能是将byte切片写入文件）。应用程序可以通过save方法返回的 error值判断写文件时是否遇到错误。如果写文件一切正常，Page.save() 将返回nil（指针、接口等类型的零值）。

传递给WriteFile函数的第三个参数0600是一个八进制整数值， 表示新创建的文件只对当前用户是读写权限。（更多信息请参考Unix手册open(2)） 

除了保存页面，我们还需要加载页面：
```golang
func loadPage(title string) *Page {
    filename := title + ".txt"
    body, _ := ioutil.ReadFile(filename)
    return &Page{Title: title, Body: body}
}
```

函数loadPage通过title参数构造文件名，然后读取文件的内容到 新的变量body，最后返回一个指向由title和body值构造的Page的指针。

函数可以返回多个值。标准库函数`io.ReadFile`返回`[]byte`和`error`。loadPage函数没有处理错误信息；下划线_表示空白标识符，它用于丢掉错误返回值（本质上没有对任何变量赋值）。

但是如果ReadFile遇到错误怎么办？例如文件不存在。我们不能忽略 类似的错误。我们修改函数返回*Page和error。
```golang
func loadPage(title string) (*Page, error) {
    filename := title + ".txt"
    body, err := ioutil.ReadFile(filename)
    if err != nil {
        return nil, err
    }
    retur n&Page{Title: title, Body: body}, nil
}
```

这个函数的调用者应该检查第二个返回值；如果是nil表示成功加载页面。否则， error可以被调用者处理（更多信息请参考[语言规范](https://golang.org/ref/spec#Errors)）。 

现在我们有了一个简单的数据结构，并且可以保存到文件和从文件加载页面。让我们写一个main函数测试一下：
```golang
func main() {
    p1 := &Page{Title:"TestPage", Body: []byte("This is a sample Page.")}
    p1.save()
    p2, _ := loadPage("TestPage")
    fmt.Println(string(p2.Body))
}
```

编译并运行程序后会创建一个名为TestPage.txt的文件，内容是p1的Body成员。然后文件的内容被读取到p2，并且打印其Body成员到屏幕。

可以这样编译和运行程序： 
```
$ go build wiki.go
$ ./wiki This is a sample page. 
```

（如果是使用Windows系统则不需要在wiki前面加`./`。） 

点击[这里](https://golang.org/part1.go)浏览完整代码。 

### 了解net/http包（插曲） 

这里是一个简单的Web服务器的完整代码：
```golang 
package main

import (
    "fmt"
    "net/http"
)

func handler(w http.ResponseWriter, r *http.Request) {
    fmt.Fprintf(w,"Hi there, I love %s!", r.URL.Path[1:])
}

func main() {
    http.HandleFunc("/", handler)
    http.ListenAndServe(":8080", nil)
}
```

main函数首先调用http.HandleFunc，告诉http包用handler函数处理所有跟目录的访问请求（“/“）。

然后调用http.ListenAndServe，指定监听所有网卡上的8080端口（目前先忽略第二个参数nil）。这个函数会阻塞直到程序终止。

函数handler的类型是http.HandlerFunc。它的参数是一个http.ResponseWriter和一个http.Request。

参数http.ResponseWriter是描述HTTP响应的结构体，向它写入的数据会发送 到HTTP客服端。

参数http.Request是客户端请求数据对应的数据结构。`r.URL.Path`表示客户端请求的URL地址。后面的`[1:]`含义是从Path的第一个字符到 末尾创建一个子切片。这样可以忽略URL路径中的开始的`/`字符。 

如果你运行这个程序并这个URL地址`http://localhost:8080/monkeys`，程序会返回一个包含这个内容的页面`Hi there, I love monkeys!`。

### 使用net/http包提供wiki页面服务
使用前需要导入net/http包：
```golang
import (
    "fmt"
    "net/http"
    "io/ioutil"
)
```

然后我们创建用于处理浏览wiki页面的HTTP handler——viewHandler函数。它会处理所有以/view/为前缀的URL。
```golang 
func viewHandler(w http.ResponseWriter, r *http.Request) {
    title := r.URL.Path[len("/view/"):]
    p, _ := loadPage(title)
    fmt.Fprintf(w, "<h1>%s</h1><div>%s</div>", p.Title, p.Body)
}
```

首先，该函数从保存请求URL的r.URL.Path变量中取出要浏览页面的标题。然后对Path创建切片`[lenPath:]`忽略前缀/view/，因为用户请求的URL格式始终为/view/xxx，前缀/view/不是页面标题的组成部分。 

接着该函数从文件中读取页面数据，格式化为一个简单的HTML格式的字符串，写入到http.ResponseWriter类型的w中。

这里又一次使用下划线来忽略loadPage返回值error。这里只是为了简化代码，它并不是好的编程实践。稍后我们会继续完善这个部分。 

要使用这个函数，我们需要修改main函数中的http初始化代码，使用viewHandler函数处理URL前缀为/view/的请求。
```golang 
func main() {
    http.HandleFunc("/view/", viewHandler)
    http.ListenAndServe(":8080", nil)
}
```

点击[这里](https://golang.org//part2.go)浏览完整代码。

我们创建一些测试页面（如test.txt），然后尝试通过我们的程序展示这个wiki页面：

使用编辑器打开test.txt文件，输入"Hello world"并保存（文件内容不包括双引号）。 
```
$ go build wiki.go
$ ./wiki
```

如果是使用Windows系统则不需要"wiki"前面的"./"。

启动web服务器后，浏览[http://localhost:8080/view/test](http://localhost:8080/view/test)将显示一个标题为"test"内容为"Hello world"的页面。 

### 编辑页面
没有编辑功能的wiki不是真正的wiki。让我们创建两个新函数：editHandler用于显示编辑页面的界面，saveHandler用于保存编辑后的页面内容。

我们先将它们加入到main()函数：
```golang
func main() {
    http.HandleFunc("/view/", viewHandler)
    http.HandleFunc("/edit/", editHandler)
    http.HandleFunc("/save/", saveHandler)
    http.ListenAndServe(":8080", nil)
}
```

函数editHandler加载页面（如果页面不存在就返回一个空的Page结构体），然后显示一个HTML编辑页面。
```golang
func editHandler(w http.ResponseWriter, r *http.Request) {
    title := r.URL.Path[len("/edit/"):]
    p, err := loadPage(title)
    if err != nil {
        p = &Page{Title: title}
    }
    fmt.Fprintf(w, "<h1>Editing %s</h1>"+
        "<form action=\"/save/%s\" method=\"POST\">"+
        "<textarea name=\"body\">%s</textarea><br>"+
        "<input type=\"submit\" value=\"Save\">"+
        "</form>",
        p.Title, p.Title, p.Body)
}
```

这个函数只是实现了基本功能，但是那些HTML的硬编码代码比较丑陋。当然，还有更好的实现方式。

### 使用html/template包 
html/template是标准库中的包。它可以实现将HTML代码分离到一个文件，然后我们可以在不改变底层代码前提下调整和完善编辑页面。 

首先，我们导入html/template包。现在我们已经不再使用fmt包了，因此需要删除它。
```golang
import (
    "html/template"
    "http"
    "io/ioutil"
    "os"
)
```

让我们为编辑页面创建一个模板文件。新建一个edit.html文件，并输入以下内容：
```html 
<h1>Editing {{.Title}}</h1>

<form action="/save/{{.Title}}" method="POST">
<div><textarea name="body" rows="20" cols="80">{{printf "%s" .Body}}</textarea></div>
<div><input type="submit" value="Save"></div>
</form>
```

修改editHandler函数，使用模板代替硬编码HTML：
```golang
func editHandler(w http.ResponseWriter, r *http.Request) {
    title := r.URL.Path[len("/edit/"):]
    p, err := loadPage(title)
    if err != nil {
        p = &Page{Title: title}
    }
    t, _ := template.ParseFiles("edit.html")
    t.Execute(w, p)
}
```

函数template.ParseFiles读取edit.html目标文件，返回一个template.Template类型的指针。

函数t.Execute处理模板，将生成的HTML写入到http.ResponseWriter。模板中中以点开头的.Title和.Body标识符将被p.Title和p.Body替换。

模板语法中的指令是被双花括号包括的部分。`printf "%s" .Body`指令表示一次函数调用，将.Body作为字符串 
而不是字节串输出，类似fmt.Printf函数的效果。html/template可以保证输出正确、安全的HTML字符串，例如：大于号特殊符号会自动转义为`&gt;`, 保证渲染使用的数据不会破坏模板的HTML结构。
 
现在我们已经使用了模板，所以给viewHandler函数创建一个名为view.html的模板文件：
```html 
<h1>{{.Title}}</h1>
<p>[<a href="/edit/{{.Title}}">edit</a>]</p>
<div>{{printf "%s" .Body}}</div>
```

同时也要调整viewHandler函数：
```golang
func viewHandler(w http.ResponseWriter, r *http.Request) {
    title := r.URL.Path[len("/view/"):]
    p, _ := loadPage(title)
    t, _ := template.ParseFiles("view.html")
    t.Execute(w, p)
}
```

通过观察可以发现两个handler使用模板的代码非常相似。因此我们将重复的代码挪到一个独立的函数中，并修改是调用它的函数：
```golang
func renderTemplate(w http.ResponseWriter, tmpl string, p *Page) {
    t, _ := template.ParseFiles(tmpl + ".html")
    t.Execute(w, p)
}
func viewHandler(w http.ResponseWriter, r *http.Request) {
    title := r.URL.Path[len("/view/"):]
    p, _ := loadPage(title)
    renderTemplate(w, "view", p)
}
func editHandler(w http.ResponseWriter, r *http.Request) {
    title := r.URL.Path[len("/edit/"):]
    p, err := loadPage(title)
    if err != nil {
        p = &Page{Title: title}
    }
    renderTemplate(w, "edit", p)
}
```

如果我们想把main函数中未实现的save函数注释掉，我们可以重新构建和测试程序。点击[这里](https://golang.org/part3.go)浏览完整代码。

#### 处理不存在的页面
如果访问/view/APageThatDoesntExist会发生什么情况？你会看到模板HTML的网页，
这是因为程序忽略了loadPage返回的错误信息，并尝试用空Page填充view模板。为了处理请求的页面不存在的情况，应该程序重定向到一个新页面的编辑页面，http.Redirect函数向HTTP响应报文添加http.StatusFound(302)状态码，以及重定位的目的URL。
```golang
func viewHandler(w http.ResponseWriter, r *http.Request) {
    title := r.URL.Path[len("/view/"):]
    p, err := loadPage(title)
    if err != nil {
        http.Redirect(w, r, "/edit/"+title, http.StatusFound)
        return
    }
    renderTemplate(w, "view", p)
}
```

#### 保存页面
saveHandler函数用于处理编辑页面提交的表单。把main函数中的saveHandler注释去掉以后，我们来实现这个handler：
```golang
func saveHandler(w http.ResponseWriter, r *http.Request) {
    title := r.URL.Path[len("/save/"):]
    body := r.FormValue("body")
    p := &Page{Title: title, Body: []byte(body)}
    p.save()
    http.Redirect(w, r, "/view/"+title, http.StatusFound)
}
```

从URL中获取页面标题，从表单唯一的字段Body提取内容，创建一个新的Page结构体保存它们。然后save方法将页面写到文件, 最后重定向到/view/页面。

FormValue方法的返回值是字符串类型，我们需要先转换为[]byte，然后才能用于初始化Page结构体。我们通过`[]byte(body)`实现强制转换。

#### 错误处理
前面代码中的很多处地方都忽略了错误处理。这不是好的编程实践，因为发生错误的话会导致程序行为语法预计。更好的处理方式是捕捉错误并向用户显示相关的错误信息。这样即使发生错误, 服务器也可以按照我们预期的方式运行, 用户也可以收到错误提示信息。

首先, 我们先处理renderTemplate中的错误，http.Error函数返回一个具体的错误码（对于renderTemplate就是服务器错误）和错误信息.
看来刚才决定将模板处理独立到一个函数是一个正确的决定：
```golang
func renderTemplate(w http.ResponseWriter, tmpl string, p *Page) {
    t, err := template.ParseFiles(tmpl + ".html")
    if err != nil {
        http.Error(w, err.Error(), http.StatusInternalServerError)
        return
    }
    err = t.Execute(w, p)
    if err != nil {
        http.Error(w, err.Error(), http.StatusInternalServerError)
    }
}
```

接下来修复saveHandler，p.save()时发生的错误信息也将报告给用户：
```golang
func saveHandler(w http.ResponseWriter, r *http.Request) {
    title, err := getTitle(w, r)
    if err != nil {
        return
    }
    body := r.FormValue("body")
    p := &Page{Title: title, Body: []byte(body)}
    err = p.save()
    if err != nil {
        http.Error(w, err.Error(), http.StatusInternalServerError)
        return
    }
    http.Redirect(w, r, "/view/"+title, http.StatusFound)
}
```

#### 缓存模板
前面的实现有一个性能缺陷：renderTemplate每次渲染页面时都会调用ParseFiles函数。更好的方法是只在初始化的使用调用一次，将全部要处理的模板
保存到一个Template类型的指针中，然后可以使用[ExecuteTemplate](https://golang.org/pkg/html/template/#Template.ExecuteTemplate)渲染指定的模板。

首先创建一个名位templates全局变量，然后用ParseFiles进行初始化：
```golang
var templates = template.Must(template.ParseFiles("edit.html", "view.html"))
```

template.Must只是一个helper函数，当传入非nil时抛出panic异常，否则原封不动的返回`*Template`。
在这里抛出异常是合适的：如果模板不能正常加载，唯一合理的处理方式就是退出程序。

ParseFiles接收任意个数的字符串参数，每个字符串唯一表示一个模板文件，这个函数会解析这些文件，并用模板文件的basename（译者注：模板文件绝对路径为/path/to/template.html，basename是template.html）索引模板对应的`*Template`。如果我们需要更多的模板，只要将模板文件名添加到ParseFiles参数中。

然后是修改renderTemplate函数, 调用templates.ExecuteTemplate渲染指定的模板：
```golang
func renderTemplate(w http.ResponseWriter, tmpl string, p *Page) {
    err := templates.ExecuteTemplate(w, tmpl+".html", p)
    if err != nil {
        http.Error(w, err.Error(), http.StatusInternalServerError)
    }
}
```

需要注意的是指定模板的方式是通过模板文件名, 因此这里添加了".html"后缀。

#### 安全验证
你可能已经发现了这个程序有严重的安全缺陷：用户可以通过构造URL读写服务器上的任意路径（译者注：viewHandler读取的文件路径为/view/path/to/wiki，/path/to/wiki没有限制）。为了降低这种风险，我们编写一个函数用正则表达式验证标题的合法性。

首先，要导入"regexp"包。然后创建一个全局变量保存用于验证的正则表达式：
```golang
var validPath = regexp.MustCompile("^/(edit|save|view)/([a-zA-Z0-9]+)$")
```

函数regexp.MustCompile将分析和编译正则表达式，返回regexp.Regexp。MustCompile和Compile有些不同，它在遇到错误时会抛出panic异常，而Compile在遇到错误时通过第二个返回值返回错误。

现在, 让我们写一个函数从请求的URL提取标题, 用validPath测试是否是合法的路径，并提取标题：
```golang
func getTitle(w http.ResponseWriter, r *http.Request) (string, error) {
    m := validPath.FindStringSubmatch(r.URL.Path)
    if m == nil {
        http.NotFound(w, r)
        return "", errors.New("Invalid Page Title")
    }
    return m[2], nil // The title is the second subexpression.
}
```

如果标题有效返回nil，如果标题无效, 函数会向客户端返回"404 Not Found"错误，并向函数的调用者返回非nil的错误，我们需要导入errors包创建一个非nil的错误值。让我们将getTitle应用到每个处理程序：
```golang
func viewHandler(w http.ResponseWriter, r *http.Request) {
    title, err := getTitle(w, r)
    if err != nil {
        return
    }
    p, err := loadPage(title)
    if err != nil {
        http.Redirect(w, r, "/edit/"+title, http.StatusFound)
        return
    }
    renderTemplate(w, "view", p)
}
func editHandler(w http.ResponseWriter, r *http.Request) {
    title, err := getTitle(w, r)
    if err != nil {
        return
    }
    p, err := loadPage(title)
    if err != nil {
        p = &Page{Title: title}
    }
    renderTemplate(w, "edit", p)
}
func saveHandler(w http.ResponseWriter, r *http.Request) {
    title, err := getTitle(w, r)
    if err != nil {
        return
    }
    body := r.FormValue("body")
    p := &Page{Title: title, Body: []byte(body)}
    err = p.save()
    if err != nil {
        http.Error(w, err.Error(), http.StatusInternalServerError)
        return
    }
    http.Redirect(w, r, "/view/"+title, http.StatusFound)
}
```

#### 函数字面值和闭包
在每个处理函数中捕捉错误引入了很多重复的代码。是否可以将每个处理函数的
错误处理和安全验证包装到一个函数？Go语言的[函数类型](https://golang.org/ref/spec#Function_literals)提供了功能强大的抽象函数方法，刚好可以用在这里。

第一步，我们重写每个处理函数，增加一个标题字符串参数：
```golang
func viewHandler(w http.ResponseWriter, r *http.Request, title string)
func editHandler(w http.ResponseWriter, r *http.Request, title string)
func saveHandler(w http.ResponseWriter, r *http.Request, title string)
```

然后，我们定义一个包装函数，函数接收另一个函数类型，签名和上面定义的处理函数相同，返回值同样为一个函数类型http.HandlerFunc（用于适配http.HandleFunc的参数类型）:
```golang
func makeHandler(fn func (http.ResponseWriter, *http.Request, string)) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        // Here we will extract the page title from the Request,
        // and call the provided handler 'fn'
    }
}
```

这里返回的函数就是一个闭包，因为它引用了在它外部定义的局部变量的值。在这里，变量fn（makeHandler函数的唯一参数）就是被闭包引用的变量。

现在我们可以将getTitle的代码移到这里（还有一些细节的改动）：
```golang
func makeHandler(fn func(http.ResponseWriter, *http.Request, string)) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        m := validPath.FindStringSubmatch(r.URL.Path)
        if m == nil {
            http.NotFound(w, r)
            return
        }
        fn(w, r, m[2])
    }
}
```

makeHandler返回的是一个函数，函数接收的参数为http.ResponseWriter和http.Request（其实就是http.HandlerFunc类型）。 闭包函数中从URL提取页面的标题，并用validPath验证
标题是否符合正则表达式。如果是无效的标题，就用http.NotFound函数向ResponseWriter返回错误。如果是有效的标题，就调用fn处理请求，传入的参数为ResponseWriter、Request和title。

现在我们可以在main函数注册的时候使用makeHandler包装具体的处理函数：
```golang
func main() {
    http.HandleFunc("/view/", makeHandler(viewHandler))
    http.HandleFunc("/edit/", makeHandler(editHandler))
    http.HandleFunc("/save/", makeHandler(saveHandler))
    http.ListenAndServe(":8080", nil)
}
```

最后我们删除处理函数中对getTitle的调用，这样处理代码变得更加简单：
```golang
func viewHandler(w http.ResponseWriter, r *http.Request, title string) {
    p, err := loadPage(title)
    if err != nil {
        http.Redirect(w, r, "/edit/"+title, http.StatusFound)
        return
    }
    renderTemplate(w, "view", p)
}
func editHandler(w http.ResponseWriter, r *http.Request, title string) {
    p, err := loadPage(title)
    if err != nil {
        p = &Page{Title: title}
    }
    renderTemplate(w, "edit", p)
}
func saveHandler(w http.ResponseWriter, r *http.Request, title string) {
    body := r.FormValue("body")
    p := &Page{Title: title, Body: []byte(body)}
    err := p.save()
    if err != nil {
        http.Error(w, err.Error(), http.StatusInternalServerError)
        return
    }
    http.Redirect(w, r, "/view/"+title, http.StatusFound)
}
```

#### 试一下页面效果!
点击[这里](https://golang.org/final.go)查看最终版本的代码.

重新编译代码, 并且运行:
```
$ go build wiki.go
$ ./wiki
```

浏览[http://localhost:8080/view/ANewPage](http://localhost:8080/view/ANewPage)将会看到编辑页面，你可以输入一些文字, 点击"save"就能重新定向到新创建的页面。

#### 其他任务
下面是一些根据自己的兴趣选择一些简单的任务：

* 保存模板到tmpl/目录，保存数据到data/目录
* 增加一个处理函数，将首页重定向到/view/FrontPage
* 优化页面模板：让它们是合法的HTML，并添加一些CSS
* 实现页面之间的链接：将[PageName]替换为`<a href="/view/PageName">PageName</a>`。（提示: 可以使用regexp.ReplaceAllFunc实现该功能）

编译版本 go1.9。