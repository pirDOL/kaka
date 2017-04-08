## ["First Class Functions in Go"](https://blog.golang.org/first-class-functions-in-go-and-new-go)

30 June 2011 By Andrew Gerrand

Go语言的新手通常会对函数类型、函数作为值、闭包感到奇怪。[First Class Functions in Go](http://golang.org/doc/codewalk/functions/)这个codewalk通过一个骰子游戏[Pig](http://en.wikipedia.org/wiki/Pig_(dice))展示了这些特性。这个美丽的程序把充分的使用了这门语言，对于Go的新手和老手都可以一读。

更多资源请参考[golang.org](http://golang.org/doc/docs.html)

译者注：关于[First Class Functions](https://zh.wikipedia.org/wiki/%E5%A4%B4%E7%AD%89%E5%87%BD%E6%95%B0)：
>头等函数（first-class function）是指在程序设计语言中，函数被当作头等公民。这意味着，函数可以作为别的函数的参数、函数的返回值，赋值给变量或存储在数据结构中。有人主张应包括支持匿名函数（函数字面量，function literals）。在这样的语言中，函数的名字没有特殊含义，它们被当作具有函数类型的普通的变量对待。[3]1960年代中期，克里斯托弗·斯特雷奇在“functions as first-class citizens”中提出这一概念。

### [coldwalk](https://golang.org/doc/codewalk/functions/)

#### 简介
doc/codewalk/pig.go

Go语言支持头等函数、高阶函数、用户自定义的函数类型、函数字面量、闭包以及多返回值。这些丰富的特性使得Go这门强类型语言支持函数式编程风格。

在这个codewalk中，我们会阅读一个简单的模拟骰子游戏Pig的程序，程序实现了基本的策略。

#### 游戏规则
doc/codewalk/pig.go:17,21

Pig游戏有两个玩家，使用一个6面的骰子，每一轮玩家可以选择掷骰子或者停留：

* 如果骰子点数为1，则本轮获得的点数都会清零，然后由另一个玩家继续。
* 如果骰子点数不为1，那么把掷得的点数累计作为本轮的点数。
* 如果选择停留，那么本轮获得的点数会累加到总点数中，然后由另一个玩家继续。
* 第一个到达100点的玩家获胜。

`score`类型存储当前玩家、对方玩家的总点数，以及当前玩家本轮累计的点数。

#### 用户自定义函数类型
doc/codewalk/pig.go:26,41

**Go语言中函数可以像其他任何值类型一样传递。函数的类型由函数的签名决定，后者描述了函数参数和返回值。**

`action`类型是一个函数，输入参数是`score`。返回值是`(score, bool)`，`result`表示玩家本次行动的结果，`turnIsOver`表示玩家是否结束本轮。如果本轮结束，`result`中的`player`和`opponent`会被交换，表示轮到对方玩家行动。

#### 多返回值
doc/codewalk/pig.go:26,41

**Go函数可以返回多个值**

`roll`和`stay`函数的返回值为`(score, bool)`，这两个函数和`action`的函数签名是匹配的，它们实现了Pig游戏的规则。

#### 高阶函数
doc/codewalk/pig.go:43,44

**使用其他函数作为参数或者返回值的函数叫做高阶函数。**

`strategy`函数接收一个`score`类型参数的输入，返回一个`action`类型的输出。因为后者是一个函数，所以`strategy`是一个高阶函数。

#### 函数字面量和闭包
doc/codewalk/pig.go:48,53

**Go可以声明匿名函数，函数字面量就是闭包，闭包的函数继承它的定义所在的外层函数的作用域。**

Pig中最基础的策略是一轮累计的点数小于k就继续掷骰子，当累计点数超过k时停留。`stayAtK`函数中，内部的函数字面量和k构成了闭包，另外，函数字面量和`strategy`的函数签名是匹配的。

#### 变长参数函数声明
doc/codewalk/pig.go:91,94

`rationString`是一个变长参数的函数，在函数中，所有的参数会存放在一个切片中。

#### 模拟游戏
doc/codewalk/pig.go:56,70

模拟Pig游戏是通过不断调用`action`函数更新`score`，直到一个玩家总点数达到100。调用`strategy`函数选择一个`action`。

#### 模拟锦标赛
doc/codewalk/pig.go:72,89

`roundRobin`函数模拟一个锦标赛。每个策略和其他策略两两pk，每次pk重复`gamesPerSeries`次，并记录其中本策略赢的次数。

#### 模拟结果
doc/codewalk/pig.go:110,121

`main`函数定义了100个策略，模拟一个轮询的锦标赛，然后打印出每个策略输赢的结果。

在这些策略中，每轮累计点数25时选择停留是在100个策略中最优的，实际上[Pig最优策略](http://www.google.com/search?q=optimal+play+pig)是很复杂的。

```go
// Copyright 2011 The Go Authors. All rights reserved.
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file.

package main

import (
    "fmt"
    "math/rand"
)

const (
    win            = 100 // The winning score in a game of Pig
    gamesPerSeries = 10  // The number of games per series to simulate
)

// A score includes scores accumulated in previous turns for each player,
// as well as the points scored by the current player in this turn.
type score struct {
    player, opponent, thisTurn int
}

// An action transitions stochastically to a resulting score.
type action func(current score) (result score, turnIsOver bool)

// roll returns the (result, turnIsOver) outcome of simulating a die roll.
// If the roll value is 1, then thisTurn score is abandoned, and the players'
// roles swap.  Otherwise, the roll value is added to thisTurn.
func roll(s score) (score, bool) {
    outcome := rand.Intn(6) + 1 // A random int in [1, 6]
    if outcome == 1 {
        return score{s.opponent, s.player, 0}, true
    }
    return score{s.player, s.opponent, outcome + s.thisTurn}, false
}

// stay returns the (result, turnIsOver) outcome of staying.
// thisTurn score is added to the player's score, and the players' roles swap.
func stay(s score) (score, bool) {
    return score{s.opponent, s.player + s.thisTurn, 0}, true
}

// A strategy chooses an action for any given score.
type strategy func(score) action

// stayAtK returns a strategy that rolls until thisTurn is at least k, then stays.
func stayAtK(k int) strategy {
    return func(s score) action {
        if s.thisTurn >= k {
            return stay
        }
        return roll
    }
}

// play simulates a Pig game and returns the winner (0 or 1).
func play(strategy0, strategy1 strategy) int {
    strategies := []strategy{strategy0, strategy1}
    var s score
    var turnIsOver bool
    currentPlayer := rand.Intn(2) // Randomly decide who plays first
    for s.player+s.thisTurn < win {
        action := strategies[currentPlayer](s)
        s, turnIsOver = action(s)
        if turnIsOver {
            currentPlayer = (currentPlayer + 1) % 2
        }
    }
    return currentPlayer
}

// roundRobin simulates a series of games between every pair of strategies.
func roundRobin(strategies []strategy) ([]int, int) {
    wins := make([]int, len(strategies))
    for i := 0; i < len(strategies); i++ {
        for j := i + 1; j < len(strategies); j++ {
            for k := 0; k < gamesPerSeries; k++ {
                winner := play(strategies[i], strategies[j])
                if winner == 0 {
                    wins[i]++
                } else {
                    wins[j]++
                }
            }
        }
    }
    gamesPerStrategy := gamesPerSeries * (len(strategies) - 1) // no self play
    return wins, gamesPerStrategy
}

// ratioString takes a list of integer values and returns a string that lists
// each value and its percentage of the sum of all values.
// e.g., ratios(1, 2, 3) = "1/6 (16.7%), 2/6 (33.3%), 3/6 (50.0%)"
func ratioString(vals ...int) string {
    total := 0
    for _, val := range vals {
        total += val
    }
    s := ""
    for _, val := range vals {
        if s != "" {
            s += ", "
        }
        pct := 100 * float64(val) / float64(total)
        s += fmt.Sprintf("%d/%d (%0.1f%%)", val, total, pct)
    }
    return s
}

func main() {
    strategies := make([]strategy, win)
    for k := range strategies {
        strategies[k] = stayAtK(k + 1)
    }
    wins, games := roundRobin(strategies)

    for k := range strategies {
        fmt.Printf("Wins, losses staying at k =% 4d: %s\n",
            k+1, ratioString(wins[k], games-wins[k]))
    }
}
```