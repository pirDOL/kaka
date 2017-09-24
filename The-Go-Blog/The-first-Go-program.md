## [The first Go program](https://blog.golang.org/first-go-program)

18 July 2013 By Andrew Gerrand

### TLDR
本文介绍了第一个Go程序，实现功能是S表达式的解析。第一个Go程序在语法上和今天有很多不同，从语法的变化可以一探Go语言逐渐成长的过程。

### 正文
最近Brad Fitzpatrick和我开始重构[godoc](http://golang.org/cmd/godoc/)，我突然发现godoc是最老的Go程序之一。Robert Griesemer早在2009年编写的代码，时至今日我们还在使用。

当我在[twitter上](https://twitter.com/enneff/status/357403054632484865)发布了这件事以后，Dave Cheney回复了[一个有趣的问题](https://twitter.com/davecheney/status/357406479415914497)：第一个Go程序是什么？Rob Pike从他的邮件中翻找，在一封给Robert和Ken Thompson的很老的邮件中找到了第一个Go程序。

下面介绍一下第一个Go程序。Rob在2008年2月实现了它，当时Go team只有Rob、Robert和Ken。他们已经确定了一个固定的特征列表（具体内容在[这篇博客](http://commandcenter.blogspot.com.au/2012/06/less-is-exponentially-more.html)中）以及一个粗略的语言规范。Ken已经完成了第一个可以工作的Go编译器版本（这个版本的编译器不产生二进制程序，而是把Go代码直接翻译成C，便于快速验证早期的Go编译器原型），所以是时候尝试开发一个Go程序了。

Rob向Go team发送邮件：
下面是代码，使用了一些丑陋的hack方法绕过当时Go语言还没有实现字符串的问题。
程序输出的icounter表示执行的语句数，打印出来用于调试。

```
From: Rob 'Commander' Pike
Date: Wed, Feb 6, 2008 at 3:42 PM
To: Ken Thompson, Robert Griesemer
Subject: slist

it works now.

roro=% a.out
(defn foo (add 12 34))
return: icounter = 4440
roro=%

here's the code.
some ugly hackery to get around the lack of strings.
```

这个程序解析并打印[S表达式](https://en.wikipedia.org/wiki/S-expression)，它不接受用户输入，不导入任何包，只依赖内置的print函数打印输出。这个程序编写的背景是：只有一个[可以工作但功能很原始的编译器](http://golang.org/change/8b8615138da3)，很多语言特性都没有实现，还有一些没有指定。

当然，Go语言今天的基本风格还能从这个程序中辨认出来，类型和变量声明、程序流控制、包声明都没有改变。但是还有很多语言特性是和现在不同的或者当时没有实现，最明显的就是第一个Go程序中缺少并发和接口，Go语言在设计的第1天就考虑这两个特性，但是当时还没有实现。

`func`当时是`function`，并且函数签名中返回值位于参数前面，二者通过`<-`分隔，但是现在`<-`被用于channel的发送和接收操作。例如：`WhiteSpace`函数输入参数为整数`c`，返回值为bool。`<-`分隔返回值和参数只是个权宜之计，当找到更好的支持函数多返回值的方法以后就不再使用它了。
```
function WhiteSpace(bool <- c int)
```

方法和函数使用了不同的关键字`method`，并且方法会在结构体中预定义（后来很快就不这样做了）。
```
method (this *Slist) Car(*Slist <-) {
    return this.list.car;
}

type Slist struct {
    ...
    Car method(*Slist <-);
}
```

第一个Go程序还不支持字符串，尽管在语言手册中定义了。为了绕过这个问题，Rob用一个uint8的数组代替字符串，初始化这个数组看起来很笨拙。当时，Go语言中的数组功能还很简单，slice还没被设计和实现，当时slice的雏形叫做open array。
```
input[i] = '('; i = i + 1;
input[i] = 'd'; i = i + 1;
input[i] = 'e'; i = i + 1;
input[i] = 'f'; i = i + 1;
input[i] = 'n'; i = i + 1;
input[i] = ' '; i = i + 1;
...
```

`panic`和`print`是内置的关键字，而不是定义好的函数。
```
print "parse error: expected ", c, "\n";
panic "parse";
```

第一个Go程序和现在的Go还有很多细微的差别，看看你能不能发现一些。

在这个程序被实现不到2年以后，Go作为一个开源项目发布。回首过去，Go语言的发展和成熟让人感到吃惊。第一个Go程序和我们今天所看到的Go程序相比，最后一个变化就是去掉了分号。

更让人感到惊奇的是我们关于如何**编写**Go代码学到了很多，例如：Rob曾经把方法接收者命名为`this`，但现在我们使用简短的上下文命名方法，除此之外的例子还有很多，并且时至今日我们还在探索编写Go代码更好的方法，例如：[glog包](https://github.com/golang/glog)中[处理日志等级的聪明的技巧](https://github.com/golang/glog/blob/c6f9652c7179652e2fd8ed7002330db089f4c9db/glog.go#L893)。

我很好奇我们明天会学到什么。

附：代码
```golang
package main

// fake stuff
type char uint8;

// const char TESTSTRING[] = "(defn foo (add 'a 'b))\n";

type Atom struct {
        string  *[100]char;
        integer int;
        next    *Slist;  /* in hash bucket */
}

type List struct {
        car     *Slist;
        cdr     *Slist;
}

type Slist struct {
        isatom          bool;
        isstring        bool;
        //union {
        atom    Atom;
        list    List;
        //} u;

        Free method();
        Print method();
        PrintOne method(doparen bool);
        String method(*char <-);
        Integer method(int <-);
        Car method(*Slist <-);
        Cdr method(*Slist <-);
}

method (this *Slist) Car(*Slist <-) {
        return this.list.car;
}

method (this *Slist) Cdr(*Slist <-) {
        return this.list.cdr;
}

method (this *Slist) String(*[100]char <-) {
        return this.atom.string;
}

method (this *Slist) Integer(int <-) {
        return this.atom.integer;
}

function OpenFile();
function Parse(*Slist <-);

//Slist* atom(char *s, int i);

var token int;
var peekc int = -1;
var lineno int32 = 1;

var input [100*1000]char;
var inputindex int = 0;
var tokenbuf [100]char;

var EOF int = -1;  // BUG should be const

function main(int32 <-) {
        var list *Slist;

        OpenFile();
        for ;; {
                list = Parse();
                if list == nil {
                        break;
                }
                list.Print();
                list.Free();
                break;
        }

        return 0;
}

method (slist *Slist) Free(<-) {
        if slist == nil {
                return;
        }
        if slist.isatom {
//              free(slist.String());
        } else {
                slist.Car().Free();
                slist.Cdr().Free();
        }
//      free(slist);
}

method (slist *Slist) PrintOne(<- doparen bool) {
        if slist == nil {
                return;
        }
        if slist.isatom {
                if slist.isstring {
                        print(slist.String());
                } else {
                        print(slist.Integer());
                }
        } else {
                if doparen {
                        print("(");
                }
                slist.Car().PrintOne(true);
                if slist.Cdr() != nil {
                        print(" ");
                        slist.Cdr().PrintOne(false);
                }
                if doparen {
                        print(")");
                }
        }
}

method (slist *Slist) Print() {
        slist.PrintOne(true);
        print "\n";
}

function Get(int <-) {
        var c int;

        if peekc >= 0 {
                c = peekc;
                peekc = -1;
        } else {
                c = convert(int, input[inputindex]);
                inputindex = inputindex + 1; // BUG should be incr one expr
                if c == '\n' {
                        lineno = lineno + 1;
                }
                if c == '\0' {
                        inputindex = inputindex - 1;
                        c = EOF;
                }
        }
        return c;
}

function WhiteSpace(bool <- c int) {
        return c == ' ' || c == '\t' || c == '\r' || c == '\n';
}

function NextToken() {
        var i, c int;
        var backslash bool;

        tokenbuf[0] = '\0';     // clear previous token
        c = Get();
        while WhiteSpace(c)  {
                c = Get();
        }
        switch c {
                case EOF:
                        token = EOF;
                case '(':
                case ')':
                        token = c;
                        break;
                case:
                        for i = 0; i < 100 - 1; {  // sizeof tokenbuf - 1
                                tokenbuf[i] = convert(char, c);
                                i = i + 1;
                                c = Get();
                                if c == EOF {
                                        break;
                                }
                                if WhiteSpace(c) || c == ')' {
                                        peekc = c;
                                        break;
                                }
                        }
                        if i >= 100 - 1 {  // sizeof tokenbuf - 1
                                panic "atom too long\n";
                        }
                        tokenbuf[i] = '\0';
                        if '0' <= tokenbuf[0] && tokenbuf[0] <= '9' {
                                token = '0';
                        } else {
                                token = 'A';
                        }
        }
}

function Expect(<- c int) {
        if token != c {
                print "parse error: expected ", c, "\n";
                panic "parse";
        }
        NextToken();
}

// Parse a non-parenthesized list up to a closing paren or EOF
function ParseList(*Slist <-) {
        var slist, retval *Slist;

        slist = new(Slist);
        slist.list.car = nil;
        slist.list.cdr = nil;
        slist.isatom = false;
        slist.isstring = false;

        retval = slist;
        for ;; {
                slist.list.car = Parse();
                if token == ')' {       // empty cdr
                        break;
                }
                if token == EOF {       // empty cdr  BUG SHOULD USE ||
                        break;
                }
                slist.list.cdr = new(Slist);
                slist = slist.list.cdr;
        }
        return retval;
}

function atom(*Slist <- i int) {  // BUG: uses tokenbuf; should take argument
        var h, length int;
        var slist, tail *Slist;
        
        slist = new(Slist);
        if token == '0' {
                slist.atom.integer = i;
                slist.isstring = false;
        } else {
                slist.atom.string = new([100]char);
                var i int;
                for i = 0; ; i = i + 1 {
                        (*slist.atom.string)[i] = tokenbuf[i];
                        if tokenbuf[i] == '\0' {
                                break;
                        }
                }
                //slist.atom.string = "hello"; // BUG! s; //= strdup(s);
                slist.isstring = true;
        }
        slist.isatom = true;
        return slist;
}

function atoi(int <-) {  // BUG: uses tokenbuf; should take argument
        var v int = 0;
        for i := 0; '0' <= tokenbuf[i] && tokenbuf[i] <= '9'; i = i + 1 {
                v = 10 * v + convert(int, tokenbuf[i] - '0');
        }
        return v;
}

function Parse(*Slist <-) {
        var slist *Slist;
        
        if token == EOF || token == ')' {
                return nil;
        }
        if token == '(' {
                NextToken();
                slist = ParseList();
                Expect(')');
                return slist;
        } else {
                // Atom
                switch token {
                        case EOF:
                                return nil;
                        case '0':
                                slist = atom(atoi());
                        case '"':
                        case 'A':
                                slist = atom(0);
                        case:
                                slist = nil;
                                print "unknown token"; //, token, tokenbuf;
                }
                NextToken();
                return slist;
        }
        return nil;
}

function OpenFile() {
        //strcpy(input, TESTSTRING);
        //inputindex = 0;
        // (defn foo (add 12 34))\n
        inputindex = 0;
        peekc = -1;  // BUG
        EOF = -1;  // BUG
        i := 0;
        input[i] = '('; i = i + 1;
        input[i] = 'd'; i = i + 1;
        input[i] = 'e'; i = i + 1;
        input[i] = 'f'; i = i + 1;
        input[i] = 'n'; i = i + 1;
        input[i] = ' '; i = i + 1;
        input[i] = 'f'; i = i + 1;
        input[i] = 'o'; i = i + 1;
        input[i] = 'o'; i = i + 1;
        input[i] = ' '; i = i + 1;
        input[i] = '('; i = i + 1;
        input[i] = 'a'; i = i + 1;
        input[i] = 'd'; i = i + 1;
        input[i] = 'd'; i = i + 1;
        input[i] = ' '; i = i + 1;
        input[i] = '1'; i = i + 1;
        input[i] = '2'; i = i + 1;
        input[i] = ' '; i = i + 1;
        input[i] = '3'; i = i + 1;
        input[i] = '4'; i = i + 1;
        input[i] = ')'; i = i + 1;
        input[i] = ')'; i = i + 1;
        input[i] = '\n'; i = i + 1;
        NextToken();
}
```