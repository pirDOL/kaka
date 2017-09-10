## [Introduction Gofix](https://blog.golang.org/introducing-gofix)

15 April 2011 By Russ Cox

下一个Go发布版会包含重大的API修改，设计若干Go基础包。[HTTP服务端handler的代码](http://codereview.appspot.com/4239076)、[调用net.Dial的代码](http://codereview.appspot.com/4244055)、[调用os.Open的代码](http://codereview.appspot.com/4357052)、[使reflect包的代码](http://codereview.appspot.com/4281055)如果不升级到最新的API就无法编译通过。Now that our releases are more stable and less frequent, this will be a common situation. Each of these API changes happened in a different weekly snapshot and might have been manageable on its own; 然而，更新