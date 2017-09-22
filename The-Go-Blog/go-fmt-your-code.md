## [go fmt your code](https://blog.golang.org/go-fmt-your-code)

23 January 2013 By Andrew Gerrand

### TLDR
1. mechanical source transformation：通过机械（机器、程序）转换代码
2. `gofmt -r 'bytes.Compare(a, b) == 0 -> bytes.Equal(a, b)'`，其中`a`和`b`小写单个字母表示任意的Go表达式，并且`=>`前后的`a`是指同一个表达式

### 简介
[gofmt](http://golang.org/cmd/gofmt/)是一个自动格式化go代码的工具，被它格式化的代码：

* 代码更容易编写：编码时不用再关心次要的格式化问题
* 代码更容易阅读：如果所有的代码风格都保持一致，你就不用再阅读代码时把一种风格的代码转换成你能理解的格式
* 代码更容易维护：通过程序修改代码时不会因为格式化导致不相干的diff，只会显示真正修改的地方
* 减少争论：永远不会因为空格和括号的位置导致争论

### 格式化你的代码
我们最近对第三方的Go包进行了调查，发现大约70%遵循了gofmt的格式化风格。这个数字超出预期，感谢使用gofmt的所有人，如果gofmt能把剩下30%也覆盖了就更好了。

你可以直接使用gofmt工具格式化代码，也可以通过[go fmt命令](http://golang.org/cmd/go/#hdr-Run_gofmt_on_package_sources)格式化代码：
```bash
gofmt -w yourcode.go
go fmt path/to/your/package
```

为了帮助你保证代码遵循gofmt的风格，Go的代码库对于编辑器和版本管理系统提供了钩子，可以更容易的在你的代码上执行gofmt。

对于vim用户，[vim-go插件](https://github.com/fatih/vim-go)包含了`:Fmt`命令在当前窗口执行gofmt。

对于emacs用户，[go-mode.el](https://github.com/dominikh/go-mode.el)提供了一个钩子实现在保存前执行gofmt。在你的.emacs文件中添加下面这行就饿可以安装：
```
(add-hook 'before-save-hook #'gofmt-before-save)
```

对于Eclipse和SublimeText用户，[GoClipse](https://github.com/GoClipse/goclipse)和[GoSublime](https://github.com/DisposaBoy/GoSublime)项目分别给这两个编辑器提供了gofmt的支持。

对于git的重度狂热分子，[这个git pre-commit脚本](http://tip.golang.org/misc/git/pre-commit)实现了pre-commit钩子，未正确格式化的go代码不能提交。如果你使用的是Mercurial，[hgstyle插件](https://bitbucket.org/fhs/hgstyle/overview)提供了gofmt的pre-commit钩子。

### 通过程序实现代码转换
工具格式化的代码最大的优点在于通过程序自动转换代码时不会产生格式diff的噪声。对于代码规模很大的项目，通过程序自动转换代码是很有价值的工具，因为相比于人手工逐一修改，程序不会遗漏也不容易产生错误。显然，像我们在谷歌面对的项目规模，通过人工修改代码格式，显然是不现实的。

通过程序实现代码转换最简单的例子就是gofmt的`-r`选项，这个选项指定了从pattern到replacement的替换规则。
```
gofmt -r 'pattern -> replacement'
```

pattern和replacement都是合法的go表达式，其中，单个小写字母可以匹配所有的子表达式，pattern和replacement中相同的小写字母表示相同的子表达式。

例如：Go核心代码[最近的修改](https://golang.org/cl/7038051)重写了[bytes.Compare](http://golang.org/pkg/bytes/#Compare)，替换成效率更高的[bytes.Equal](http://golang.org/pkg/bytes/#Equal)。只需要两个gofmt调用就可以完成接口调用的修改：
```
gofmt -r 'bytes.Compare(a, b) == 0 -> bytes.Equal(a, b)'
gofmt -r 'bytes.Compare(a, b) != 0 -> !bytes.Equal(a, b)'
```

gofmt也使得[gofix](http://golang.org/cmd/fix/)成为可行，gofix可以对任意复杂的代码进行转换。对于早期我们经常对Go语言和标准库进行不兼容的升级，gofix曾经是一个很有意义的工具。例如：在Go1.0之前，标准库没有error接口，当时约定俗成的做法是使用os.Error。当我们[引进了error以后](http://golang.org/doc/go1.html#errors)，我们开发了gofix的一个插件，可以把所有对os.Error的引用以及使用这种类型的函数改写为新的[errors包](http://golang.org/pkg/errors/)。如果手工完成这个工作会让然望而生畏，但是因为所有的代码都是标准格式，所以很容易准备gofix工具并执行，然后review修改，修改几乎覆盖了所有的Go代码。

更多关于gofix的内容请参考[这篇文章](https://blog.golang.org/introducing-gofix)