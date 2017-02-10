## [Automatically Locate When and Where Bugs Were Introduced with git bisect](https://elliot.land/post/automatically-locate-when-and-where-bugs-were-introduced-with-git-bisect)

在软件开发的过程中，总会引入bug，可能一开始代码还是可以工作的，但一些修改会直接或者间接的导致代码不能工作。让我们面对它吧。
>Let's face it, when developing software things will break.

最好的情况是你立刻发现了代码不能工作的原因，相反是一些不明显的偶发bug，你找不到bug的原因，并且看起来最近的代码修改都和bug无关。接下来怎么办呢？
>On the other end of the scale is some obscure bug that’s only happening sometimes

首先，深呼吸，自信的按响你的指关节，打开终端并威胁的一笑，现在准备开始。
>confidently crack your knuckles and open your terminal with with a menacing grin

从我们已经了解的信息开始，我们知道在过去的某个时间点，代码是可以正常工作的，并且现在不能正常工作。因此可以推测在这之间的某次提交引入了bug。

假如现在代码库在某次提交a上，这个提交是不能正常工作的代码。确保当前的分支没有本地的修改，然后开始二分搜索过程，如果一切正常的话，下面的命令不会输出任何内容。
```
git bisect start
```

我们已知当前的版本是有bug的，因此我们把当前提交标记为bad，同样，正常不会输出任何内容。
```
git bisect bad
```

现在我们需要找到并检出没有bug的一个提交。在这个例子中，我们知道2016-08-03这个时间点，代码是没有bug的，所以我用`git rev-list`找到距离这个时间最近的一次提交。当然如果你知道tag、branch、commid的话，可以直接检出。
```
git checkout $(git rev-list --max-age=2016-06-03 --date-order --reverse HEAD | head -n 1)
```

接下来一步会很重要，首先你需要确定上面检出的版本没有bug，否则需要不断检出更早的版本，直到你能确定没有bug了为止。此时通过下面的命令把检出的提交标记为good：
```
git bisect good
```

现在你会看到输出一些有意义的信息，`git bitsec`准备施展它的魔法了：bisect字面的意思是分成两部分，git这样做了，然后找到了中间的一次提交，它和开始相隔了987次提交，然后git把这次提交检出。
```
Bisecting: 987 revisions left to test after this (roughly 10 steps)
[8fe7a35242303e8316c1d77883c0e247db6df5a8] testDefaultTotalCountIsZero
```

现在你来测试一下，在这次提交中是否还有bug。如果是则执行`git bisect bad`，否则执行`git bisect good`。每次执行都会把提交次数的数字减小一半：
```
Bisecting: 489 revisions left to test after this (roughly 9 steps)
[03c4c4e5bd1740a277a606dd208e17a855761243] Merge branch 'release/1.5' of https://github.com/elliotchance/concise into 1.4/193-set-color-scheme
```

重复执行9次`git bisect bad`或`git bisect good`，直到没有提交可以再次平分，你会看到下面的输出：
```
57a00e86622073c887be101a2e76c079245e519c is the first bad commit
```

下面是一些有用的命令用于分析引入bug的提交，从中可以看到导致bug的真正原因：
```
git show 57a00e8
git diff 57a00e8 57a00e8^
```

当完成了bug的定位时，通过下面的命令结束`git bisect`。此时git会清除所有二分查找过程，然后检出你执行`git bitsect start`时的那次提交。
```
git bisect reset
```

### Gotchas
你会发现上面重复的过程在大多数情况下都是奏效的，但是当上面的方法不好用时，可以尝试下面的一些技巧：
> rinse-and-repeat

1. 如果不能手动测试一次提交是否存在bug，例如程序不能编译（译者注：什么鬼？），你可以通过`git bisect skip`告诉git不能验证当前提交是否有bug，于是git会选择距离当前提交最近的提交并继续，而不是进行二分。
2. `git bisect`可以智能的对提交进行隔离，即使父子提交不是绝对的线性关系。如果你已知某个提交是否有bug，你可以手动的检出并确认，这个不会影响到正在进行的二分查找过程。
3. 每次`git bisect`会执行`git checkout`，因此需要保持工作目录没有未提交的修改。通常`git bisect`检出一个版本时，验证是否有bug可能需要修改当前版本的代码，因为要保证工作目录clean才能继续执行`git bisect`，如果每验证一个提交都需要打补丁然后再还原会很麻烦，推荐使用`git stash`来解决这个问题。

>git bisect will try to recover by picking a commit thats very close to this without further bisecting.
>git bisect is very clever in that it will isolate the commit even if it’s not a completely linear ancestry.

### For Lazy People
如果测试某次提交时可以通过控制台输出来验证，例如执行单测。你可以通过`git bisect run`自动化执行二分查找。它你指定的shell命令返回值来判断当前的提交是否存在bug，例如：
```
git bisect run phpunit --filter testRecordIsSavedToTheDatabase
```

感谢阅读，欢迎反馈，请在评论区留言，并考虑订阅。快乐编码。假设你熟悉git并用它来托管项目代码。

### [关于作者Elliot Chance](http://elliot.land/)
我是一个数据呆子，也是一个TDD的狂热爱好者。我居住在澳大利亚悉尼。我热衷探索新技术，并用现代的方法解决老问题。