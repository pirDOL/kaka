## [Understanding HBase and BigTable](https://dzone.com/articles/understanding-hbase-and-bigtab)

学习Hbase（Google BigTable的开源实现）最难的部分，就是准确的说出来你脑海里的Hbase是什么。
>wrapping your mind around the concept of what it actually is.

非常不幸的是，这两个伟大的系统的名字中都包含了表（table）和库（base）的字眼，这对于常年使用关系数据库的用户来说是一个非常大的困扰（像我自己）。
>which tend to cause confusion among RDBMS indoctrinated individuals (like myself).

这篇文章主要想从概念上描述清楚这些分布式数据存储系统，读完它以后，你应该能够从“当你想用Hbase”和“当你用传统数据库更好”的情况之间做出更加明智的决定。
>you should be better able to make an educated decision regarding when you might want to use Hbase vs when you'd be better off with a "traditional" database.

### 所有的东西都在术语里边
幸运的是，[Google的Bigtable论文](http://labs.google.com/papers/bigtable.html)清楚的解释了Bigtable实际上是什么。下面是“数据模型”章节的第一句话：
>A Bigtable is a sparse, distributed, persistent multidimensional sorted map.

注意：这里我想提醒读者，收起他们想直接跳到最后一行的想法。
>Note: At this juncture I like to give readers the opportunity to collect any brain matter which may have left their skulls upon reading that last line.

Bigtable论文接着解释：
>The map is indexed by a row key, column key, and a timestamp; each value in the map is an uninterpreted array of bytes.

沿着上面的这些内容，Hadoop的wiki里的[Hbase架构论文](http://wiki.apache.org/hadoop/Hbase/HbaseArchitecture)指出：
>Hbase使用的数据模型与Google的Bigtable非常相似，用户将数据行存在有标签的（labelled）表中，一个数据行有一个用于排序的键和任意数量的列。表是稀疏存储的，所以只要用户喜欢，同一张表的数据行能够有惊人数量的列。

虽然上面的这些内容看起来十分神秘，但是当你一个单词一个单词的来看的话，它们就变的十分的有意义。接下来，我将会与你们来按照以下这种顺序来讨论它们：map、持久化、分布式、有序、多维度和稀疏。

与其尝试通过画图来描述整个系统，我发现在心中一点一点建立起框架更能很好的理解它。
　　
### map
Hbase和Bigtable本质上是一个[map](http://en.wikipedia.org/wiki/Associative_array)。根据读者不同的编程语言背景，map在PHP中叫做associative array，在python中叫做Dictionary，在Ruby中叫做Hash，在JavaScript中叫做Object。

维基百科对map的定义是：一个抽象的数据类型，由一个key的集合和一个value的集合组成，每一个key对应一个value。

用[JSON](http://en.wikipedia.org/wiki/JSON)举个例子，下边的是一个简单的map，所有的value都是字符串：
```json
{
    "zzzzz" : "woot",
    "xyz" : "hello",
    "aaaab" : "world",
    "1" : "x",
    "aaaaa" : "y"
}
```

### 持久化
持久化单纯的意味着当创建和访问map的程序结束以后，保存到一个指定的map中的数据不会丢失，这里与其他的持久化存储没有任何不同，比如文件存储系统。

### 分布式
Hbase和Bigtable是建立在分布式文件系统上的，所以底层的文件存储能够分布在一系列的独立的机器上。

Hbase建立在[Hadoop的分布式文件系统（HDFS）](http://hadoop.apache.org/core/docs/r0.16.4/hdfs_design.html)或者[亚马逊的简单存储服务（S3）](http://en.wikipedia.org/wiki/Amazon_S3)，而Bigtable是利用[GOOGLE的文件系统（GFS）](http://labs.google.com/papers/gfs.html)。

数据通过复制分布到各个机器节点上实现[冗余](http://en.wikipedia.org/wiki/Replication_%28computer_science%29)，这和数据通过[磁盘冗余阵列（RAID)](http://en.wikipedia.org/wiki/RAID)分布的方式有点逻辑上的相似。

由于此文章的目标是从概念上了解Hbase，我们并不关心那种分布式文件系统的实现被使用，最重要的事情是明白它是分布的，分布提供了一层保障，比如防止一个集群内的节点挂掉

### 有序的
不同于大部分的map的实现，在Hbase/Bigtable中键值严格按照字母表排序，就是说key为`aaaaa`的数据行的下一个行的key应该是`aaaab`，并且离key为`zzzzz`的数据行很远

继续我们的JSON例子，排序的版本像这样：
```json
{
　　"1" : "x",
　　"aaaaa" : "y",
　　"aaaab" : "world",
　　"xyz" : "hello",
　　"zzzzz" : "woot"
}
```

由于这些系统规模可能很庞大，并且是分布式的，因此排序这一特性是十分重要的，当你需要扫描全表的时候，因为key相似的数据行存储上是临近的，因此你感兴趣的内容也是临近的。

选择key的规范需要考虑有序性。举个例子，如果一个表的行 key是域名，将域名反过来写是非常有必要的（此时行key为`com.jinbojw.www` 而不是`wwww.jimbojw.com`），这样子域名的数据行会比较临近父域名。

继续考虑域名这个例子，key为`mail.jimbojw.com`的数据行将会紧挨着`com.jimbojw.www`的数据行。如果用正常的域名顺序作为行key，key为`mail.jimbojw.com`的数据行会临近key为`mail.xyz.com`的数据行。

值得说明的是，Hbase/Bigtable中的“有序”不是value有序而是key有序。除了key，没有其他的任何索引，因此可以简单的把它看做普通的map实现。

### 多维度
目前我们还没有提到“列”的概念，我们用常规的hashmap概念来理解Bigtable，这样做是有目的，因为“列”这个词像“表”和“库”一样是另一个沉重的单词，承担了多年的关系型数据库经验的感情包袱。

然而，我发现它可以非常简单的将它（译者注：指的是“列”）看做一个多维度的map（如果愿意的话你可以看成嵌套的map）。添加一个维度到我们的JSON例子中的话，就成了下边这个样子：
```json
{
　　"1" : {
　　"A" : "x",
　　"B" : "z"
　　},
　　"aaaaa" : {
　　"A" : "y",
　　"B" : "w"
　　},
　　"aaaab" : {
　　"A" : "world",
　　"B" : "ocean"
　　},
　　"xyz" : {
　　"A" : "hello",
　　"B" : "there"
　　},
　　"zzzzz" : {
　　"A" : "woot",
　　"B" : "1337"
　　}
}
```

在上边的例子中，你会注意到，现在每个行key都指向一个的map，map中有`A`和`B`两个key。从现在开始，我们将会把最顶层的键值对看做是一行数据，在Bigtable和Hbase的命名中，`A`和`B`两个map则被称为“列族”。

表的列族在创建表的时候指定，并且以后难以或者说不可能被修改。另外，添加一个列族也是开销很大的操作。所以如果你需要多少列簇，在一开始就一次性指定是一个很好的主意。

幸运的是，一个列族可能有任意个数量的列，在Hbase中被称为`qualifier`或者`label`。下边又是一个JSON例子，这次增加了列标记维度：
```json
{
  // ...
  "aaaaa" : {
    "A" : {
      "foo" : "y",
      "bar" : "d"
    },
    "B" : {
      "" : "w"
    }
  },
  "aaaab" : {
    "A" : {
      "foo" : "world",
      "bar" : "domination"
    },
    "B" : {
      "" : "ocean"
    }
  },
  // ...
}
```

注意这里仅有的两行数据，`A`列族有两个列`foo`和`bar`，`B`列族仅有一列，列标识符为空字符串。

当从Hbase/Bigtable查询数据时，必须提供完整的列名，格式为`<family>:<qualifier>`，举个例子，上边的例子中完整的列名为：`A:foo`、`A:bar`、`B:`。

注意，虽然列族是不变的，但是列是可变的。考虑以下扩展的数据行：
```json
{
  // ...
  "zzzzz" : {
    "A" : {
      "catch_phrase" : "woot",
    }
  }
}
```

在这个例子中，数据行`zzzzz`有一列：`A:catch_phrase`。因为每行可能有任意多的不同的列，因此没有内置的方法来查询所有行中的所有列。如果真的需要这些信息，需要去做一个全表扫描。但是可以查询所有的列族，因为列族是不可变的。

最后一个维度是时间。所有的数据都是有版本的，不管是整数的时间戳，还是你自己选择的其他整数。客户端会在插入数据的时候指定时间戳。考虑以下的例子，使用任意的整数时间戳：
```json
{
  // ...
  "aaaaa" : {
    "A" : {
      "foo" : {
        15 : "y",
        4 : "m"
      },
      "bar" : {
        15 : "d",
      }
    },
    "B" : {
      "" : {
        6 : "w"
        3 : "o"
        1 : "w"
      }
    }
  },
  // ...
}
```

任何一个列族可以根据自己的规则去决定有多少个版本的数据单元（rowkey+column_family+qualifier决定一个数据单元）。大多数应用只会简单的获取数据单元，不需要通过指定时间戳。一般情况下，Hbase/Bigtable将会返回最新的版本（最大的时间戳）因为它是按时间从新到旧排序的。

如果一个应用程序要获取一个给定的行给定的时间戳的数据单元，Hbase将会返回里边时间戳**小于或等于**给定时间戳的数据单元。

对于上面的例子：查询`aaaaa:A:foo`的数据单元将会返回`y`，查询`aaaaa:A:foo@10`的数据单元将会返回`m`，查询`aaaaa:A:foo@2`将会返回空结果。

### 稀疏
最后的关键词是稀疏。像上边提到的，一个给定的数据行的每个列族能有任意多的列，或者没有任何列。另一种类型的稀疏是指数据行的gap，即数据行的key之间可能有许多的空白（因为key按照字符顺序排列）。

如果你能够按照本文提出的map术语去理解Hbase/Bigtable，而不是用关系型数据库的概念去理解，那么这篇文章就很有意义了。

我希望这篇文章能够帮你从概念上理解Hbase的数据模型是怎么样的。和往常一样，我期待你的观点、评论和建议。

### 参考

1. [理解HBase和BigTable](http://mt.sohu.com/20161115/n473177706.shtml)
2. [大数据那些事(10):李逵麻子，李鬼坑人--BigTable的数据模型](https://zhuanlan.zhihu.com/p/24721857?refer=feizong)

