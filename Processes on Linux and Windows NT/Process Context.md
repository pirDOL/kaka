# [进程上下文](http://www.tldp.org/LDP/LG/issue23/flower/context.html)

每当一个进程放弃CPU使用权时，它当前的执行状态必须被保存起来以便于进程重新被调度运行时能够从相同的位置恢复执行。这个执行状态数据就是上下文，把进程的线程从处理器上剥夺（并替换成另一个进程的线程）的过程就叫做进程切换或者上下文切换。

进程切换和上下文切换是有区别的，进程切换是指把CPU上的进程替换成另一个，上下文切换是进程在执行中被中断，进程切换时执行的操作是上下文切换的超集。上下文切换的典型场景是响应外部中断或者系统调度需要从用户态切换成内核态，但是此时进程仍然拥有CPU使用权，只是线程的执行被中断，然而进程切换要比上下文切换保存更多的信息以便于将来重新调度这个进程时使用。

进程的上下文信息包括：地址空间、堆栈空间、虚地址空间、寄存器镜像（程序计数器PC、堆栈指针SP、指令寄存器IR、程序状态字PSW、其他通用寄存器）、帐号信息、进程相关的内核数据结构的镜像、进程当前的状态（等待、就绪等）。（译者注：原文中的updating是啥意思？）

>The context of a process includes its address space ... and other general processor registers), updating profiling or accounting information, making a snapshot image of its associated kernel data structures and updating the current state of the process (waiting, ready, etc).

状态信息保存在进程的PCB中，进程PCB保存在不同的调度队列中。当新的进程调度到CPU运行时，它的PCB会被拷贝到适当的位置，例如：PC指针会被加载为PCB中下一条执行的指令的地址。

### Linux

每个进程的上下文以task_struct结构体描述，它保存诸如调度策略、调度优先级、实时优先级、处理器允许的时间片、进程相关的寄存器、文件句柄（file_struct）、虚存（mm_struct）。

当进程切换时，调度器保存进程的task_struct，将处理器当前执行进程的task_struct指针替换为新进程的task_struct，然后恢复新进程的内存地址和寄存器上下文。进程切换需要硬件的支持。

### Windows NT

内核维护所有进程和线程的状态，分别保存在内核进程对象和内核线程对象中。这些对象中保存了内核所需的切换进程和线程的信息。

内核通过将上下文信息添加到当前内核模式的堆栈中实现上下文切换，对进程来说还需要保存段表的地址也就是进程的地址空间。
