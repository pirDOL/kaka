## [6 Tips to supercharge C++11 vector performance](http://www.acodersjourney.com/2016/11/6-tips-supercharge-cpp-11-vector-performance/)

vector就像C++ STL容器中的瑞士军刀，用Bjarne Stroutsoup的话说就是：当你需要使用容器时，通常首选是vector。对于像我们这样的普通程序员，我们把Bjarne Stroutsoup的话当作真理并在编程实践中奉行它。然而，vector和其他的工具一样，可以高效的使用，也可以低效率的使用。

在这篇文章中，我们介绍了6个优化vector使用的方法。对于最常见的使用vector的编程任务，我们会对高效和低效的实现方法进行比较，得到性能的差异，并且分析性能提高的原因。

性能测试的硬件环境和方法：

* 所有的测试都在我的Surface Book上完成，处理器为i7 2.6GHz，内存8GB，编译器为VS2015，系统为Win10
* 我们使用了[Kjell开发的计时器程序](https://github.com/KjellKod/Stopwatch)
* 对于每个测试我们会运行100次，取平均时间用于比较。完整的测试代码在[这里](http://www.acodersjourney.com/boost-c11-vector-performance/)。欢迎下载这些代码，并在你的系统中测试vector的性能。文章中的代码片段仅仅是为了说明问题而简化出来的。
* 我们使用一个TestStruct结构体和一个FillVector()方法产生测试用的vector，它们的定义如下：
```C++
// Test struct to be inserted/removed from vector
struct BigTestStruct
{
  int iValue = 1;
  float fValue;
  long lValue;
  double dValue;
  char cNameArr[10];
  int iValArr[100];
};

// Helper function to populate the test vectors
void FillVector(vector<BigTestStruct>& testVector)
{
  for (int i = 0; i < 10000; i++)
  {
    BigTestStruct bt;
    testVector.push_back(bt);
  }
}
```

下面进入正题：6个快速的方法优化C++11中的vector使用

#### 1 提前reserve，避免不必要的重新分配和拷贝
程序员喜欢使用vector的原因是在添加元素到容器中时不需要考虑容器的容量。然而，如果向一个空容器逐渐添加元素会导致运行时很高的性能开销。如果能够在使用vector之前知道它的大小，提前分配大小是很必要的。

下面是一个简单的测试：我们向一个vector中添加10k个TestStruct实例，比较不reserve和reserve的时间，前者在我的机器上花了5145us，而后者只花了1279us，性能提高75.14%。

```C++
vector<BigTestStruct> testVector1;
vector<BigTestStruct> testVector2;
sw.Restart();
FillVector(testVector1);
cout << "Time to Fill Vector Without Reservation:" << sw.ElapsedUs() << endl;
sw.Restart();
testVector2.reserve(10000);
FillVector(testVector2);
cout << "Time to Fill Vector With Reservation:" << sw.ElapsedUs() << endl;
```

这个差异的原因在Scott Meyers的《Effective STL-50 Specific Ways to Improve Your Use of the Standard Template Library》中有过解释：
>对于vector和string，当它们的空间增长时，实际发生的事情在本质上类似于realloc，具体包括四个部分：

>1. 分配一个新的内存块，大小是容器目前容量的倍数，在大多数vector和string的实现中，每次分配增长的倍数是1.5或者2.
>1. 从容器的老的内存中把所有元素拷贝到新内存中
>1. 析构老内存中的所有元素对象
>1. 释放老的内存

>考虑到分配、拷贝、析构、释放的开销，显然这些操作会造成很高的开销。你自然不会希望它们在非必要的场合下发生。有一点不太自然的问题是，当这些操作发生时，vector或者string的所有迭代器、指针、引用都会失效。这意味者向vector或者string中插入元素这个最简单的操作需要更新使用vector或者string中元素迭代器、指针或者引用的其他数据结构同步更新。

#### 2 通过shrink_to_fit()释放vector的内存，clear() 和erase()不会释放内存
不同于通常的想法，从vector中通过clear()和erase()方法删除元素不会释放vector的内存。下面是一个简单的实验证明这一点：我们向一个vector中添加100个元素，然后对这个vector执行clear()和erase()，接着我们通过capacity()函数检查容器能够容纳的元素数量。

如输出内容，clear()和erase()不会影响vector占用的内存大小，所以如果你想在代码中释放不再使用的vector内存，使用std::vector::shrink_to_fit()。

```C++
FillVector(testVector1);
size_t capacity = testVector1.capacity();
cout << "Capacity Before Erasing Elements:" << capacity << endl;

testVector1.erase(testVector1.begin(), testVector1.begin() + 3); //
capacity = testVector1.capacity();
cout << "Capacity After Erasing 3 elements Elements:" << capacity << endl;
testVector1.clear();
capacity = testVector1.capacity();
cout << "Capacity After clearing all emements:" << capacity << endl;
testVector1.shrink_to_fit();
capacity = testVector1.capacity();
cout << "Capacity After shrinking the Vector:" << capacity << endl;

// output
Capacity Before Erasing Elements:12138
Capacity After Erasing 3 elements Elements:12138
Capacity After clearing all emements:12138
Capacity After shrinking the Vector:0  
```

注意shrink_to_fit()函数可能不会被所有的编译器实现，此时可以通过swap方法实现清空vector的内存。更多关于swap方法的内容可以参考《C++ Coding Standards: 101 Rules, Guidelines, and Best Practices》的条款82。
```
container<T>( c ).swap( c ); // the shrink-to-fit idiom to shed excess capacity
container<T>().swap( c );    // the idiom to shed all contents and capacity
```

#### 3 整个填充vector时，赋值比push_back()和insert()效率更高
用一个vector填充另外一个vector通常有三种方法：赋值、std::vector::insert()+迭代器、std::vector::push_back()+循环，代码和性能如下：
```C++
vector<BigTestStruct> sourceVector, destinationVector;
FillVector(sourceVector);

// Assign sourceVector to destination vector
sw.Restart();
destinationVector = sourceVector;
cout << "Assigning Vector :" << sw.ElapsedUs() << endl;

//Using std::vector::insert()
vector<BigTestStruct> sourceVector1, destinationVector1;
FillVector(sourceVector1);
sw.Restart();
destinationVector1.insert(destinationVector1.end(), sourceVector1.begin(), sourceVector1.end());
cout << "Using insert() :" << sw.ElapsedUs() << endl;

//Using push_back()
vector<BigTestStruct> sourceVector2, destinationVector2;
FillVector(sourceVector2);
sw.Restart();
for (unsigned i = 0; i < sourceVector2.size(); ++i) {
  destinationVector2.push_back(sourceVector2[i]);
}
cout << "Using push_back :" << sw.ElapsedUs() << endl;

// output
Assignment: 589.54 us
Insert(): 1321.27 us
Push_back(): 5354.70 us
```

赋值比insert()快了55.38%，比push_back()快了89%，这是为什么？因为赋值知道源vector的大小，只需要调用一次内存分配就可以创建目标vector的内存。

因此对于高效率的填充vector，三种方法建议首选赋值，然后是insert()+迭代器和push_back()+循环，当然，从其他容器向vector拷贝，赋值就没法使用了，这时应该insert()+迭代器。

#### 4 按元素迭代vector时，避免使用at函数
迭代vector有三种方法，代码和输出如下，正如你所见，at函数是三种方法中访问vector元素最慢的（因为at有越界检查，见[sgi源码](http://www.sgi.com/tech/stl/stl_vector.h)）。

1. 迭代器
2. vector::at()
3. 下标

```C++
//Using an iterator
vector<BigTestStruct> testVectorSum;
FillVector(testVectorSum);
sw.Restart();
int sum = 0;
for (auto it = testVectorSum.begin(); it != testVectorSum.end(); ++it)
{
  sum = sum + it->iValue;
}
cout << "Using Iterator:" << sw.ElapsedUs() << endl;

//Using the at() member function
sw.Restart();
sum = 0;
for (unsigned i = 0; i < testVectorSum.size(); ++i)
{
  sum = sum + testVectorSum.at(i).iValue;
}
cout << "Using at() :" << sw.ElapsedUs() << endl;

// Using the subscript notation
sw.Restart();
sum = 0;
for (unsigned i = 0; i < testVectorSum.size(); ++i)
{
  sum = sum + testVectorSum[i].iValue;
}
cout << "Using subscripting:" << sw.ElapsedUs() << endl;

// output
Using Iterator:0
Using at() :3.73
Using subscripting:0
```

#### 5 避免在vector前面插入元素

任何在vector头部插入的操作都是O(n)的，它效率低的原因是为了给新元素腾地方，所有已有的元素都要拷贝一次。如果需要连续的向vector头部插入，你需要重新评估一下你的设计方案。下面是对vector和list在头部插入的比较，运行了测试10次，容器的长度为1000，list比vector的头部插入新能高58836%。原因是显而易见的，因为在list头部插入是O(1)，并且vector越大，性能越糟糕。

```C++
vector<BigTestStruct> sourceVector3, pushFrontTestVector;
FillVector(sourceVector3);
list<BigTestStruct> pushFrontTestList;
//Push 100k elements in front of the new vector -- this is horrible code !!! 
sw.Restart();
for (unsigned i = 1; i < sourceVector3.size(); ++i)
{
  pushFrontTestVector.insert(pushFrontTestVector.begin(), sourceVector3[i]);
}
cout << "Pushing in front of Vector :" << sw.ElapsedUs() << endl;
// push in front of a list
sw.Restart();
for (unsigned i = 0; i < sourceVector3.size(); ++i)
{
  pushFrontTestList.push_front(sourceVector3[i]);
}
cout << "Pushing in front of list :" << sw.ElapsedUs() << endl;

// output
Average of Pushing in front of Vector :11999.4
Average of Pushing in front of list :20.36
```

#### 6 当向vector中添加元素时，使用emplace_back() 替代push_back()

几乎所有上了C+11列车的程序员都会认同emplace对于STL容器插入是一个更理想的方案。理论上，emplace至少保证效率不会比insert低，然而对于大多数的实践中，二者的差异有时几乎可以忽略不计。

对于下面的代码片段，运行100次，我们通过输出发现emplace比insert还是胜出一点，仅仅177微秒。二者几乎可以认为没有啥性能上的差别。

emplace在下面两个场景中会有显著的性能提升（实际上就是节省一次构造和析构）：

1. 添加到容器的元素有构造函数，而不是直接赋值的。
2. 传入emplace的参数类型和vector实际的元素类型不一致，例如：vector<string>调用emplace("string literal")

尽管上面的两个条件在上面的测试中都不满足，使用emplace不会比insert差很多。（原文：Even if the above two conditions don’t hold true, you’ll not *loose* much by using emplacement over insertion as demonstrated in this example.）

更多关于emplace和insert的内容请参考Scott Meyer的《Effective Modern C++: 42 Specific Ways to Improve Your Use of C++11 and C++14》条款42。

```C++
vector<BigTestStruct> sourceVector4, pushBackTestVector, emplaceBackTestVector;
FillVector(sourceVector4);
//Test push back performance
sw.Restart();
for (unsigned i = 0; i < sourceVector4.size(); ++i)
{
  pushBackTestVector.push_back(sourceVector4[i]);
}
cout << "Using push_back :" << sw.ElapsedUs() << endl;
//Test emplace_back()
sw.Restart();
for (unsigned i = 0; i < sourceVector4.size(); ++i)
{
  emplaceBackTestVector.emplace_back(sourceVector4[i]);
}
cout << "Using emplace_back :" << sw.ElapsedUs() << endl;
// output
Average Using push_back :5431.58
Average Using emplace_back :5254.64
```

#### 最后
就像很多第三方的数据，你不能盲目的依赖本文的结果和建议。在不同的操作系统、处理器架构以及编译器上测试时会有很大差异。从这篇文章开始，根据你自己的情况来测试、优化。

如果你喜欢这篇文章请分享。

附：gcc4.8.2 centos4u3 linux2.6.32 2.1GHz E5-2620*2 4G RAM
测试结果
Average Time to Fill Vector Without Reservation:5378.53
Average Time to Fill Vector With Reservation:649.25
Capacity Before Erasing Elements:16384
Capacity After Erasing 3 elements Elements:16384
Capacity After clearing all emements:16384
Capacity After shrinking the Vector:0
Begining Test for Vector element enumeration 
Using Iterator:207.63
Using at() :187.29
Using subscripting:89.55
Average of Assigning Vector :918.55
Average of Using insert() :694.86
Average of Using push_back :4102.78
Average of Pushing in front of Vector :4.58529e+06
Average of Pushing in front of list :1609.5
Average Using push_back :6667.95
Average Using emplace_back :6460.58
