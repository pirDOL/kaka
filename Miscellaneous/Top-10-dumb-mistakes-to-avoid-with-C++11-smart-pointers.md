## [Top 10 dumb mistakes to avoid with C++ 11 smart pointers](http://www.acodersjourney.com/2016/05/top-10-dumb-mistakes-avoid-c-11-smart-pointers/)

我喜欢新时代C++11的智能指针，从许多方面，智能指针对于不想自己管理内存的普通人来说是天赐的福音。在我看来，智能指针还让C++的新手更容易入门。

然而，在频繁使用智能指针两年多的经历中，我遇到很多不合理使用智能指针导致程序效率降低或者是崩溃的case。下面我把它们分门别类的列出来，方便后面参考。

在我们开始之前，先来看一个简单的飞行器类，我们会用这个类来说明智能指针的错误使用：
```c++
class Aircraft {
private:
    string m_model;

public:
    int m_flyCount;
    weak_ptr myWingMan;

    void Fly() {
        cout << "Aircraft type" << m_model << "is flying !" << endl;
    }

    Aircraft(string model) {
        m_model = model;
        cout << "Aircraft type " << model << " is created" << endl;
    }

    Aircraft() {
        m_model = "Generic Model";
        cout << "Generic Model Aircraft created." << endl;
    }

    ~Aircraft() {
        cout << "Aircraft type  " << m_model << " is destroyed" << endl;
    }
};
```

### 错误1：在unique_prt够用的情况下使用shared_ptr
我最近接手了一个其他人的代码，其中使用了一个shared_ptr创建和管理对象。当我分析了代码以后，我发现其中90%的地方，通过shared_ptr包装的资源都没有被共享。

在不需要共享的场合使用shared_ptr是有问题的：

1. 如果只想独占一个资源，那么使用shared_ptr会导致代码容易出现意外的资源泄漏和bug：
    * 微秒的bug：因为资源使用shared_ptr管理，所以理论上其他人可以把它赋值给新的shared_ptr，甚至通过新的shared_ptr修改资源。这个场景是你可能无法预料到的。
    * 不必须的资源使用：即使其他的指针不会修改共享的资源，当最开始的shared_ptr在离开作用域时试图释放资源，但是因为资源此时是共享的，所以资源本身不会被使用，资源的生命周期被延长了，从而导致内存非必需的上涨。
2. shared_ptr比unique_ptr更消耗资源，前者需要维护线程安全的引用计数，还需要一个控制块，这使得它比unique_ptr的开销更重。

**建议：默认情况下，使用unique_ptr，如果后续有需要改为共享资源，可以很容易的从unique_ptr修改为shared_ptr。**

### 错误2：没有保证shared_ptr管理的资源的线程安全性
shared_ptr允许你在多个线程之间，通过指针共享资源，这就导致了一个很常见的错误：认为shared_ptr可以保证对底层资源的线程安全性。通过shared_ptr管理的资源被多个线程共享时，需要由程序员自己使用同步原语保证底层资源的线程安全。

**建议：如果不打算在多个线程之间共享资源，请使用unique_ptr**

### 错误3：使用auto_ptr
auto_ptr的特性很危险，现在已经被废弃了。当auto_ptr通过值拷贝传递时会导致资源所有权的转移，此时再使用原来的auto_ptr引用资源时就会导致程序崩溃。例如：
```c++
int main() {
    auto_ptr myAutoPtr(new Aircraft("F-15"));
    SetFlightCountWithAutoPtr(myAutoPtr); // Invokes the copy constructor for the auto_ptr
    myAutoPtr->m_flyCount = 10; // CRASH !!!
}
```

**建议：unique_ptr完成了auto_ptr本来打算实现的所有功能，建议对你的代码做一下调研，把所有的auto_ptr全部替换成unique_ptr，这样做的绝对安全的，但是还是要回归测试一下修改后的代码。**

### 错误4：不使用make_shared初始化shared_ptr
make_shared比使用原始的指针有两个突出的优点：

1. 性能：用new创建一个资源，然后再创建一个shared_ptr管理资源，这包括两个动态内存分配操作。相反使用make_shared时，C++编译器只会做一次内存配分，分配足够大的内存容纳资源和shared_ptr。
2. 
~~安全性：考虑一个场景，Aircraft对象被创建出来，然后shared_ptr创建失败了，此时Aircraft对象就不会被释放了，从而导致了内存泄漏。~~ 查看了Microsoft编译器的memory头文件以后，我发现如果Aircraft分配失败了，Aircraft会被释放掉，所以make_shared和不需要考虑安全性。

```c++
shared_ptr pAircraft(new Aircraft("F-16")); // Two Dynamic Memory allocations - SLOW !!!

shared_ptr pAircraft(new Aircraft("F-16")); // Two Dynamic Memory allocations - SLOW !!!
```

建议：使用make_shared实例化shared_ptr，不要用原始指针。

### 错误5：在创建了对象以后没有立即把指针传递给shared_ptr
资源的指针需要在获取后马上传递给shared_ptr，此后原始指针就不能被使用了。考虑下面的例子：
```c++
int main() {
    Aircraft* myAircraft = new Aircraft("F-16");

    shared_ptr pAircraft(myAircraft);
    cout << pAircraft.use_count() << endl; // ref-count is 1

    shared_ptr pAircraft2(myAircraft);
    cout << pAircraft2.use_count() << endl; // ref-count is 1

    return 0;
}
```

这个例子会因为非法访问从而导致程序崩溃，问题的原因是当第一个shared_ptr在退出作用域时，myAircraft会被析构，但是当第二个shared_ptr退出作用域时，它会再次析构myAircraft。

**建议：如果不使用make_shared创建shared_ptr，只少把分配资源和创建shared_ptr放在一行**
```c++
shared_ptr pAircraft(new Aircraft("F-16"));
```

### 错误6：释放被shared_ptr使用的原始指针
通过`shared_ptr::get()`方法可以获取shared_ptr管理的资源原始指针，然而获取这个指针是很危险的，并且应该尽量避免，考虑下面的代码：
```c++
void StartJob() {
    shared_ptr pAircraft(new Aircraft("F-16"));
    Aircraft* myAircraft = pAircraft.get(); // returns the raw pointer
    delete myAircraft;  // myAircraft is gone
}
```

当我们从shared_ptr中获取它管理的资源的原始指针myAircraft时，我们释放了这个指针。然而当StartJob函数返回时，pAircraft因为作用域结束而析构，析构时会再次释放它管理的资源，因为资源已经被释放了，所以shared_ptr析构导致了非法访问。

**建议：从shared_ptr中获取原始指针时需要仔细考虑，永远也不能假设别人不会释放原始指针，如果别人这样做了，那么shared_ptr析构就会导致非法访问**

### 错误7：shared_ptr管理对象数组没有自定义delete
考虑下面的代码片段：
```c++
void StartJob() {
    shared_ptr ppAircraft(new Aircraft[3]);
}
```

shared_ptr只会管理Aircraft[0]，Aircraft[1]和Aircraft[2]不会被shared_ptr释放，从而导致了内存泄漏。如果你使用的是Visual Studio 2015，会出现堆被写花的错误。

**建议：如果shared_ptr管理的资源是一个数组，那么需要自定义delete。**
```c++
void StartJob() {
    shared_ptr ppAircraft(new Aircraft[3], [](Aircraft* p) { delete[] p; });
}
```

### 错误8：使用shared_ptr时没有避免循环引用
在很多情况下，如果一个类包含一个shared_ptr对象，就可能导致循环引用。考虑下面的场景：你向创建两个Aircraft对象，一个被Maverick驾驶，另一个被Iceman驾驶。同时，两个Aircraft对象需要保存另一个Aircraft对象的引用。
>we want to create two Aircraft objects – one flown my Maverick and one flown by Iceman ( I could not help myself from using the TopGun reference !!! ). Both maverick and Iceman needs to hold a reference to each Other Wingman.

我们开始的设计是下面这样的：Aircraft中保存了一个shared_ptr<Aircraft>。
```c++
class Aircraft {
private:
    string m_model;
public:
    int m_flyCount;
    shared_ptr<Aircraft> myWingMan;
    ...
}
```

然后在main函数中，我们创建两个Aircraft对象Maverick和Iceman，然后把它们设置为对方的驾驶员。
```c++
int main() {
    shared_ptr pMaverick = make_shared("Maverick: F-14");
    shared_ptr pIceman = make_shared("Iceman: F-14");

    pMaverick->myWingMan = pIceman; // So far so good - no cycles yet
    pIceman->myWingMan = pMaverick; // now we got a cycle - neither maverick nor goose will ever be destroyed

    return 0;
}
```

当main返回时，我们希望看到两个Aircraft对象被析构，但是一个也没有，因为这两个Aircraft对象是循环引用的（导致两个对象的引用计数都不是0）。尽管shared_ptr对象本身从栈上面析构了，但是因为两个Aircraft对象是相互引用的，因此这两个对象无法被析构。
```
Aircraft type Maverick: F-14 is created
Aircraft type Iceman: F-14 is created
```

那么如何修复呢？我们把Aircraft中的shared_ptr改为weak_ptr，下面是修改后的main函数输出：注意两个Aircraft对象都被析构了。
```
Aircraft type Maverick: F-14 is created
Aircraft type Iceman: F-14 is created
Aircraft type  Iceman: F-14 is destroyed
Aircraft type  Maverick: F-14 is destroyed
```

**建议：在类的设计中，当资源的所有权不是必需或者不想影响资源的生命周期，考虑使用weak_ptr。

### 错误9：没有删除unique_ptr.release()返回的原始指针
`unique_ptr.release()`方法不会释放它管理的资源，并且unique_ptr不再继续管理这个资源。你必须手动释放release返回的原始指针。

下面的代码会导致内存泄漏，因为main函数退出时，Aircraft对象还没有被释放
```c++
int main() {
    unique_ptr myAircraft = make_unique("F-22");
    Aircraft* rawPtr = myAircraft.release();
    return 0;
}
```

**建议：任何时候调用unique_ptr.release()，记得释放它返回的原始指针，如果你想要释放unique_ptr管理的资源，调用unique_ptr.reset()。**

### 错误10：调用weak_ptr.lock()之前没有检查weak_ptr是否过期
在使用weak_ptr之前，你需要通过weak_ptr.lock()获取weak_ptr，这个方法会把weak_ptr升级为shared_ptr。然而，如果weak_ptr弱引用的资源已经被释放，那么lock返回的weak_ptr就是空，此时weak_ptr也可以叫做是过期的，在过期的waek_ptr上调用任何方法都会导致非法访问。

例如：下面的代码中，通过pIceman.reset()释放pIceMan管理的Aircraft对象，此时pMaverick->myWingMan弱引用的是pIceman就无效了。如果通过pMaverick->myWingMan执行任何操作，都会导致非法访问。
```c++
int main() {
    shared_ptr pMaverick = make_shared("F-22");
    shared_ptr pIceman = make_shared("F-14");

    pMaverick->myWingMan = pIceman;
    pIceman->m_flyCount = 17;

    pIceman.reset(); // destroy the object managed by pIceman

    cout << pMaverick->myWingMan.lock()->m_flyCount << endl; // ACCESS VIOLATION

    return 0;
}
```

修复方法很容易，就是在使用myWingMan之前增加一个判断。
```c++
if (!pMaverick->myWingMan.expired()) {
    cout << pMaverick->myWingMan.lock()->m_flyCount << endl;
}
```

编辑：正如很多读者指出的那样，上面的代码不能在多线程的环境中使用，然而现在99%的程序都是多线程的。可能在expired和lock之间，weak_ptr过期了。很感谢指出这个问题的读者。我采用了[Manuel Freiholz](https://disqus.com/by/manuel_freiholz/)的方法解决这个问题：在lock以后判断shared_ptr是否为空：
```c++
shared_ptr<aircraft> wingMan = pMaverick->myWingMan.lock();
if (wingMan) {
    cout << wingMan->m_flyCount << endl;
}
```

注：shared_ptr重载了operator bool
```c++
explicit operator bool() const;
Checks if *this stores a non-null pointer, i.e. whether get() != nullptr.
true if *this stores a pointer, false otherwise.

#include <iostream>
#include <memory>
 
typedef std::shared_ptr<int> IntPtr;
 
void report(IntPtr ptr) {
    if (ptr) {
        std::cout << "*ptr=" << *ptr << "\n";
    } else {
        std::cout << "ptr is not a valid pointer.\n";
    }
}
 
int main() {
    IntPtr ptr;
    report(ptr);
 
    ptr = IntPtr(new int(7));
    report(ptr);
}
```

**建议：使用weak_ptr之前记得检查它是否合法，线程安全的检查方法是判断lock返回值是否为空。**

### 接下来
如果你想了解更多关于C++11的智能指针以及其他特性，我推荐你下面两本书：

1. [C++ Primer (5th Edition) by Stanley Lippman](http://www.amazon.com/Primer-5th-Stanley-B-Lippman/dp/0321714113/ref=sr_1_13?ie=UTF8&qid=1463183650&sr=8-13&keywords=C%2B%2B+11)
2. [Effective Modern C++: 42 Specific Ways to Improve Your Use of C++11 and C++14 by Scott Meyers](http://www.amazon.com/Effective-Modern-Specific-Ways-Improve/dp/1491903996/ref=sr_1_1?ie=UTF8&qid=1463183650&sr=8-1&keywords=C%2B%2B+11)

祝各位朋友在C++11探索的道路杀那个一切顺利，如果喜欢这篇文章请分享。
