## 摘要
thrift是一个软件库以及一系列代码生成工具，Facebook开发thrift是为了加快开发和实现高效、可伸缩的后端服务。它的首要目标是实现跨编程语言高效、可靠的通信，，thrift对每种语言最需要差异化的部分进行了抽象，通过为每种语言分别实现相应的thrift程序库实现了跨语言通信。特别的，thrift只需要开发者在一个语言无关（language-neutral）的文件中定义数据类型和服务接口，thrift就可以生成构建RPC客户端和服务端所有必需的代码。

>Its primary goal is to enable efficient and reliable communication across programming languages by abstracting the portions of each language that tend to
require the most customization into a common library that is implemented
in each language.

这篇论文纤细介绍了thrift实现中的动机和设计，还有一些有趣的实现细节。不要把这篇文章作为一个研究，而是把它作为我们做了什么以及为什么这样做的阐述。

### 7.10 编译器
thrift的编译是基于C++和标准lex/yacc实现语法解析，尽管通过其他语言可以把编译器实现的更简短（例如：通过Python Lex-Yacc或者ocamlyacc），使用C++可以强制显式的定义语言结构。强类型的语法解析树元素对于编译的新开发人员更容易接触代码（有待讨论）。

>Strongly typing the parse tree elements (debatably) makes the code more approachable for new developers.

代码生成是通过两趟处理完成的：第一次只查找文件包含和类型定义，在这个阶段不检查类型定义，因为某个类型可能是在另一个文件中定义的。所有的文件在第一趟处理中顺序扫描，当解析出文件包含关系树以后开始第二趟处理，第二趟处理把类型定义插入的到解析树中，如果有未定义的类型就抛出错误。然后根据解析树生成代码。

我们显式禁止了前置声明，是因为它天生的复杂性以及潜在的循环依赖。两个thrift结构体，不能互相包含对方类型的实例，因为我们不允许生成的C++代码中出现空结构体，所以结构体相互包含的情况不会出现。

### 7.11 TFileTransport
TFileTransport用于把thrift的请求、结构体按照输入数据的长度分割为帧并写入磁盘。按照帧格式生成磁盘文件是为了更好的检查错误以及只处理一个文件中有限的几个不连续的数据。TFileWriterTransport使用操作系统的写磁盘的内存buffer保证写大量日志数据时的性能。thrift的日志文件被分割为固定长度的块，每个消息都不允许跨越块边界。如果消息的长度不是块大小的倍数，最后一个块的剩余部分不存储真正的数据。下一条消息从下一个块开始。把文件分割为块对于从文件指定的某个位置读取解析数据是友好的。

## 8 Facebook的thrift服务
thrift在Facebook中的大量服务中使用，包括：检索、日志、手机、广告和开发者平台。下面重点讨论两个使用场景

### 8.1 检索
thrift是Facebook检索服务的底层协议和网络通信层。多语言代码生成对于检索服务是很适用的，因为它允许后端服务通过高效率的服务端语言（C++）开发，同时基于PHP的web应用能够通过thrift的PHP库调用C++实现的后端服务。除此之外，检索服务还有很多统计、部署和测试功能是通过python实现的（同样，通过thrift的python库可以和检索服务通信）。另外，thrift的日志文件格式为实时索引更新时重做日志。thrift允许检索服务团队修改thrift的代码，以便于提升thrift的健壮性以及快速开发代码。

>Additionally, the Thrift log file format is used as a redo log for providing real-time search index updates. Thrift has allowed the search team to leverage each language for its strengths and to develop code at a rapid pace.

### 8.2 日志
通过thrift的`TFileTransport`功能实现结构化数据打印日志功能。每个服务函数的定义以及参数可以被认为是一个结构化的日志项，它通过函数名唯一索引。这些日志能够广泛应用：比如在线和离线处理、统计聚合或者作为流量回放。

## 9 结论
thrift通过*分治法*让Facebook的工程师可以高效率的构建可伸缩的后端服务（译者注：分就是把一个应用分割成多个RPC服务，治就是通过thrift让这些RPC按照业务逻辑调用，实现应用需求）。应用开发者只需要关注业务逻辑的代码，对于底层的socket可以不用关心。我们通过在一个地方（thrift）实现缓冲和输入输出的代码避免了重复工作，不同的应用中不需要重复实现这些内容。

>Thrift has enabled Facebook to build scalable backend services efficiently by enabling engineers to divide and conquer.

thrift已经在Facebook内部大范围的应用中使用，包括搜索、日志、手机、广告以及开发者平台。我们发现开发效率、系统可用性带来的收益完全能够弥补由thrift额外的抽象层造成的边际性能成本。

## 附录A 相似系统
下面这些软件系统和thrift类似，简要介绍一下：

* SOAP：基于XML，针对HTTP的web服务设计，XML的解析非常消耗性能
* CORBA：相对比较全面，有过度设计的嫌疑，并且很重，软件的安装很不方便
* COM：主要针对Windows客户端软件，不是一个完全开放的解决方案
* Pillar：轻量级、高性能，但是不支持版本和抽象
* Protocal Buffers：闭源，Google开发，在Sawzall的论文中介绍

## 致谢
感谢Martin Smith、Karl Voskuil、Yishan Wong对thrift的诸多反馈（以及大量的使用和测试）。

thrift是Pillar的后继者，后者是Adam D'Angelo开发的类似系统。Adam起初在Caltech工作，后来来到Facebook，如果没有Adam的洞察力就不会有thrift的诞生。

## 参考
[1] Kempf, William, "Boost.Threads", http://www.boost.org/doc/html/threads.html
[2] Henkel, Philipp, "threadpool", http://threadpool.sourceforge.net
