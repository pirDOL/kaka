# [深入Linux进程](http://www.tldp.org/LDP/LG/issue23/flower/linuxproc.html)

Linux系统向管理员提供了一系列检查进程状态、调整进程优先级以及执行状态的工具。下面用Linux系统中常见的一个免费web服务器Apache httpd守护程序为例，演示其中一些工具的使用。下面屏幕输出内容省略了一些不影响功能展示的内容。

通过下面的输出可以发现http守护程序的大小是142699字节，在这个ELF文件中，代码占108786字节，初始化数据占4796字节，未初始化数据占19015字节。
```
orion-1:# ls -l httpd
-rwxr-x--- 1 root root 142699 Oct 5 1996 httpd*

orion-1:# size httpd
text    Data    bss     dec     hex     filename
108786  4796    19015   132597  205f5   httpd
```

对文件进行对象转储（objdump）可以看到代码段在文件中的起始地址为0x1ce0，只读数据段起始地址为0x16238，其他数据段起始地址为0x1a9e8，未初始化数据段起始地址为0x1bcb0。除此之外，用于调试的符号表地位为0x1bcb0 。
```
orion-1:# objdump --headers httpd
httpd: file format elf32-i386
 Sections: < Some sections excluded for clarity >
Idx Name Size VMA LMA File off Algn
0 .interp 00000013 080000d0 080000d0 000000d4 2**0
CONTENTS, ALLOC, LOAD, READONLY, DATA
8 .text 00014544 08001ce0 08001ce0 00001ce0 2**4
CONTENTS, ALLOC, LOAD, READONLY, CODE
10 .rodata 000047ac 08016238 08016238 00016238 2**2
CONTENTS, ALLOC, LOAD, READONLY, DATA
11 .data 00001050 0801b9e8 0801b9e8 0001a9e8 2**2
CONTENTS, ALLOC, LOAD, DATA
16 .bss 00004a47 0801ccb0 0801ccb0 0001bcb0 2**4
ALLOC
17 .stab 000004f8 00000000 00000000 0001bcb0 2**2
CONTENTS, READONLY, DEBUGGING
```

http守护程序使用了C标准库中的函数，以动态链接库的方式链接（so是shared library的缩写）：
```
orion-1:# ldd -r httpd
libc.so.5 => /usr/local/lib/libc.so.5 (0x4000a0)
```

守护程序在系统启动时开始运行，在下面检查它的状态时正处于睡眠状态（S），这个进程消耗很少的CPU时间。
```
orion-1:# ps -fc | grep httpd
PID TTY STAT    TIME    COMMAND
90  ?   S       0:00    httpd
```

下图展示了机器上正在执行的所有进程以及它们的关系。httpd进程的父进程是init，这是典型的Unix守护进程。httpd还有三个子进程，大概是用于监听http连接。
```
orion-1:# pstree
init-+-4*[agetty]
     |-bash--script--script--bash--script--script--bash--pstree
     |-bash
     |-crond
     |-gpm
     |-httpd--3*[httpd]
     |-inetd
     |-kflushd
     |-klogd
     |-kswapd
     |-lpd
     |-rpc.mountd
     |-rpc.nfsd
     |-rpc.portmap
     |-sendmail
     |-syslogd
     `-update
```

httpd和init进程的关系可以通过更多的细节来确认。init进程的PID为1，httpd进程的父进程PID也是1。

httpd进程驻留在内存中的大小是528kB（RSS，Resident Set Size），整个进程虚存地址空间大小是1012MB。httpd进程的用户ID是0，即管理员root，此时这个进程的优先级是0（-20是优先级最高的实时任务，20是最低的优先级）。kswapd进程的SW<状态表示它在睡眠，这个进程没有驻留在内存中的页，并且它的优先级小于0。
```
orion-1:# ps -cl1,2,3,90
F UID PID PPID PRI NI SIZE RSS WCHAN STAT TTY TIME COMMAND
100 0 1 0 0 0 844 328 c01115c9 S ? 0:03 init [5]
40 0 2 1 0 0 0 0 c0111a38 SW ? 0:00 (kflushd)
40 0 3 1 -12 -12 0 0 c0111a38 SW< ? 0:00 (kswapd)
140 0 90 1 0 0 1012 528 c0119272 S ? 0:00 httpd
```

下面来观察一下进程的虚存。httpd大缺页错误的次数为23，大缺页错误表示从磁盘或者page cache中加载内存页到物理内存。代码段驻留内存（Text Resident Size）大小是24kB，which suggests a code page size of 1024 bytes when viewed in association with the page fault number。数据段驻留内存（Data Resident Size）108kB，总大小合计132kB。除此之外，httpd进程和其他进程共享115kB的内存（可能是C标准库）。
```
orion-1:# ps -cmp1,2,3,90
PID MAJFLT  MINFLT  TRS DRS SIZE    SWAP    RSS SHRD    COMMAND
2   0       0       0   0   0       0       0   0       kflushd
3   0       0       0   0   0       0       0   0       kswapd
1   206     49      5   77  82      0       82  65      init 
90  23      51      24  108 132     0       132 115     httpd
```

系统管理员可以通过修改nice参数来调整httpd进程的优先级。下面将httpd进程的优先级调高10。只有管理员可以向负数范围修改优先级，这是为了阻止缺乏经验的用户造成CPU过载，另外还可以保护系统不受黑客攻击。现在可以查看修改后的优先级，尽管在当前系统中httpd进程是空闲的，它不接受web请求，所以它不会消耗太多的CPU。
```
orion-1:# renice -10 90
90: old priority 0, new priority -10
orion-1:# ps -cl
UID PID PRI PPID    NI  SIZE    RSS STAT    TIME    COMMAND
0   1   0   0       0   844     328 S       0:03    init [5]
0   2   0   1       0   0       0   SW      0:00    (kflushd)
0   3   -12 1       -12 0       0   SW<     0:00    (kswapd)
0   90  -10 1       -10 1012    528 S <     0:00    httpd
```

假设现在系统因为运行几个耗CPU的shell脚本使得负载增加。对计算机执行了5次虚拟内存统计，执行间隔为5秒。
* procs字段：有2个进程在等待CPU，在第3次执行时，有2个进程状态为不可中断睡眠。
* memory字段：因为当前系统中的进程都很小，足够驻留在内存中，所以没有swap操作。
* io字段：bi（从磁盘读取数据块）、bo（向磁盘写入数据块）都很活跃。
* system字段：每秒有很多中断（in）以及上下文切换（cs）。
* cpu字段：第1次执行结果显示了从系统启动以后开始计算的系统平均负载。接下来4次执行结果为每个周期的系统负载。其中CPU时间的35%花费在用户空间，其他的时间用于执行内核态的系统调用。这一结果和机器正在执行的操作是一致的：find命令查找文件导致磁盘IO增加。
```
orion-1:# vmstat 5 5
procs       memory          swap        io      system      cpu
r   b   w   swpd    free    buf si  so  bi  bo  in  cs      us  sy  id
2   0   0   0       0       0   0   0   10  8   133 34      6   8   86
2   0   0   0       0       0   0   0   614 11  737 1234    32  68  0
1   2   0   0       0       0   0   0   100 129 435 366     40  60  0
2   0   0   0       0       0   0   0   202 26  375 455     33  67  0
2   0   0   0       0       0   0   0   230 0   331 472     31  69  0
```

可以通过内核探针找到最耗CPU的进程，通过下面的探针结果可以发现目录缓存、文件系统以及输出到控制台是内核消耗时间最多的三个任务，系统调度进程只能排在最活跃进程的第12位。注意只有在编译时开启性能分析才能从内核中读取到相关信息。
```
orion-1:# readprofile | sort -nr | head -20
CLK_TCK Function                Normalised load
67649   total                   0.0858
7796    d_lookup                54.1389
5425    ext2_readdir            3.5319
5034    scrup                   7.8168
4573    filldir                 14.8474
4481    find_inode              86.1731
2849    ext2_check_dir_entry    15.8278
2581    getname                 7.9660
1885    getblk                  2.2440
1665    sys_newlstat            6.8238
1546    lookup_dentry           5.1533
1542    do_con_write            0.3119
1425    get_hash_table          9.6284
1422    cp_new_stat             4.5577
1323    __namei                 10.3359
1270    system_call             19.8438
1231    ext2_getblk             2.2140
1084    raw_scan_sector         1.8951
1077    sys_getdents            3.0597
973     schedule                1.2102
```

Linux的ps命令从虚拟文件系统/proc中读取信息，它是进程的内核数据结构在磁盘上的镜像，注意尽管看起来/proc好像在磁盘上，但是它实际并不保存在磁盘上。

下面是httpd进程在/proc文件系统中的内容，通过进程管理命令获得的所有信息都可以在这里找到，只不过显示方式不太友好。下面是status表的内容，其中增加了一些注释便于理解。
```
orion-1:# cat /proc/90/status
Name: httpd
State: S (sleeping)
Pid: 90 # Process ID
PPid: 1 # Parent Process (init)
Uid: 0 0 0 0 # User ID (root)
Gid: 65535 65535 65535 65535 # Group ID
VmSize: 1012 kB # Total virtual memory
VmLck: 0 kB # Total locked
VmRSS: 512 kB # Text Resident Set Size
VmData: 276 kB # Virtual Memory Data size
VmStk: 20 kB # Stack size
VmExe: 108 kB # Executable
VmLib: 576 kB # Library
SigPnd: 00000000 # Signals pending
SigBlk: 00000000 # Signals blocked
SigIgn: 80000000 # Signals ignored
SigCgt: 00006441 # Signals caught
```

最后是Linux系统识别的所有信号，它们从0开始逐个编号，例如SIGHUP是0，SIGKILL是9。
```
orion-1:# fuser -l
HUP INT QUIT ILL TRAP ABRT IOT BUS FPE KILL USR1 SEGV USR2 PIPE ALRM TERM STKFLT CHLD CONT STOP TSTP TTIN TTOU URG XCPU XFSZ VTALRM PROF WINCH IO PWR UNUSED
```