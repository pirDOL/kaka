## [Running MongoDB Queries Concurrently With Go](https://www.mongodb.com/blog/post/running-mongodb-queries-concurrently-with-go)

March 24, 2014

### TLDR
1.  If we are using a single host address to connect to a replica set, the mgo driver will learn about any remaining hosts from the replica set member we connect to.
2. One thing to note is that the database we authenticate against may not necessarily be the database our application needs to access. Some applications authenticate against the admin database and then use other databases depending on their configuration. The mgo driver supports these types of configurations very well.
3. There are three modes that can be set, Strong, Monotonic and Eventual. 
2. Next we make a copy of the session we created in the main goroutine. Each goroutine needs to create a copy of the session so they each obtain their own socket without serializing their calls with the other goroutines.
3. Be aware that the All method will load all the data in memory at once. For large collections it is better to use the Iter method instead.

### 翻译
这是一篇特邀博客，作者是William Kennedy和Bill。前者是[Ardan Studios](http://www.ardanstudios.com/)的合伙人，Ardan Studios位于弗罗里达州迈阿密，是一家移动和web应用开发公司。后者是[GoingGo.Net](http://www.goinggo.net/)的作者，也是[Go-Miami](http://www.meetup.com/Go-Miami)和[Miami MongoDB](http://www.meetup.com/Miami-MongoDB-Meetup)的组织者。2013年Bill寻找一种新的语言用户开发Linux上的服务端，他找到了Go语言，然后就一发而不可收。

如果你打算参加2014年的GopherCon或者打算观看他们发布的视频，这篇博客可以作为Gustavo Niemeyer和Steve Francia的会议分享的前奏，因为这篇博客为初学者提供了通过[mgo驱动](http://labix.org/mgo)操作MongoDB数据库的方法。

#### 简介
MongoDB通过一些列[数据库驱动](http://docs.mongodb.org/ecosystem/drivers/?_ga=2.247640263.1773994815.1513433240-1229094571.1513433240)支持很多不同的编程语言，Go语言驱动mgo是其中之一，它是由[Gustavo Niemeyer](http://gophercon.com/speakers/#gustavo_niemeyer)主要开发，MongoDB Inc.提供了一些技术支持。Gustavo和[Steve Francia](http://gophercon.com/speakers/#steve_francia)是mgo开发小组的负责人，他们会在4月的[GopherCon 2014](http://gophercon.com/)上做题为[“Painless Data Storage With MongoDB and Go”](http://gophercon.com/schedule/#gustavo_niemeyer)分享，其中主要介绍了mgo驱动以及在构建高扩展性、高并发的软件中，MongoDB和Go语言是如何密切配合。

MongoDB和Go语言允许你在不同的操作系统和硬件架构上构建高扩展性的软件，不需要按照框架或者运行时环境。Go程序是一个静态编译的二进制，Go工具链持续的改进使得编译出的二进制和C语言一样快。如果编写Go程序和C语言一样复杂和冗长，那么Go语言就没啥意义了。相反（Go语言比C简洁），这恰恰是Go语言的闪光点，因为你一旦上了道，编写Go程序会很快速，也充满乐趣。

这批博客中我会向你展示如何用mgo驱动写一个Go语言程序，连接到MongoDB数据库并执行并发查询。我会把整个程序拆分开，并向那些第一次使用Go语言和MongoDB的同学详细解释他们可能不理解的细节。

#### 例子程序
```golang
// This program provides a sample application for using MongoDB with
// the mgo driver.
package main

import (
    "labix.org/v2/mgo"
    "labix.org/v2/mgo/bson"
    "log"
    "sync"
    "time"
)

const (
    MongoDBHosts = "ds035428.mongolab.com:35428"
    AuthDatabase = "goinggo"
    AuthUserName = "guest"
    AuthPassword = "welcome"
    TestDatabase = "goinggo"
)

type (
    // BuoyCondition contains information for an individual station.
    BuoyCondition struct {
        WindSpeed     float64 `bson:"wind_speed_milehour"`
        WindDirection int     `bson:"wind_direction_degnorth"`
        WindGust      float64 `bson:"gust_wind_speed_milehour"`
    }

    // BuoyLocation contains the buoy's location.
    BuoyLocation struct {
        Type        string    `bson:"type"`
        Coordinates []float64 `bson:"coordinates"`
    }

    // BuoyStation contains information for an individual station.
    BuoyStation struct {
        ID        bson.ObjectId `bson:"_id,omitempty"`
        StationId string        `bson:"station_id"`
        Name      string        `bson:"name"`
        LocDesc   string        `bson:"location_desc"`
        Condition BuoyCondition `bson:"condition"`
        Location  BuoyLocation  `bson:"location"`
    }
)

// main is the entry point for the application.
func main() {
    // We need this object to establish a session to our MongoDB.
    mongoDBDialInfo := &mgo.DialInfo{
        Addrs:    []string{MongoDBHosts},
        Timeout:  60 * time.Second,
        Database: AuthDatabase,
        Username: AuthUserName,
        Password: AuthPassword,
    }

    // Create a session which maintains a pool of socket connections
    // to our MongoDB.
    mongoSession, err := mgo.DialWithInfo(mongoDBDialInfo)
    if err != nil {
        log.Fatalf("CreateSession: %s\n", err)
    }

    // Reads may not be entirely up-to-date, but they will always see the
    // history of changes moving forward, the data read will be consistent
    // across sequential queries in the same session, and modifications made
    // within the session will be observed in following queries (read-your-writes).
    // http://godoc.org/labix.org/v2/mgo#Session.SetMode
    mongoSession.SetMode(mgo.Monotonic, true)

    // Create a wait group to manage the goroutines.
    var waitGroup sync.WaitGroup

    // Perform 10 concurrent queries against the database.
    waitGroup.Add(10)
    for query := 0; query < 10; query++ {
        go RunQuery(query, &waitGroup, mongoSession)
    }

    // Wait for all the queries to complete.
    waitGroup.Wait()
    log.Println("All Queries Completed")
}

// RunQuery is a function that is launched as a goroutine to perform
// the MongoDB work.
func RunQuery(query int, waitGroup *sync.WaitGroup, mongoSession *mgo.Session) {
    // Decrement the wait group count so the program knows this
    // has been completed once the goroutine exits.
    defer waitGroup.Done()

    // Request a socket connection from the session to process our query.
    // Close the session when the goroutine exits and put the connection back
    // into the pool.
    sessionCopy := mongoSession.Copy()
    defer sessionCopy.Close()

    // Get a collection to execute the query against.
    collection := sessionCopy.DB(TestDatabase).C("buoy_stations")

    log.Printf("RunQuery : %d : Executing\n", query)

    // Retrieve the list of stations.
    var buoyStations []BuoyStation
    err := collection.Find(nil).All(&buoyStations)
    if err != nil {
        log.Printf("RunQuery : ERROR : %s\n", err)
        return
    }

    log.Printf("RunQuery : %d : Count[%d]\n", query, len(buoyStations))
}
```

现在你看到了完整的程序，我们把它分开，首先从开头的类型定义结构体开始分析。

下面的数据结构表示了我们将要通过查询获取和反序列化的数据。BuoyStation是主文档，BuoyCondition和BuoyLocation是嵌入式文档，mgo驱动通过使用tag很容易将存储在MongoDB集合中的文档转换为Go语言中的类型。我们可以通过tag控制mgo驱动如何把查询返回的文档反序列化到Go语言的结构体。
```golang
type (
    // BuoyCondition contains information for an individual station.
    BuoyCondition struct {
        WindSpeed     float64 `bson:"wind_speed_milehour"`
        WindDirection int     `bson:"wind_direction_degnorth"`
        WindGust      float64 `bson:"gust_wind_speed_milehour"`
    }
 
    // BuoyLocation contains the buoy's location.
    BuoyLocation struct {
        Type        string    `bson:"type"`
        Coordinates []float64 `bson:"coordinates"`
    }
 
    // BuoyStation contains information for an individual station.
    BuoyStation struct {
        ID        bson.ObjectId `bson:"_id,omitempty"`
        StationId string        `bson:"station_id"`
        Name      string        `bson:"name"`
        LocDesc   string        `bson:"location_desc"`
        Condition BuoyCondition `bson:"condition"`
        Location  BuoyLocation  `bson:"location"`
    }
)
```

现在让我们看看如何使用mgo连接到MongoDB：我们从创建一个`mgo.DialInfo`对象开始，如果想连接到一个副本集，既可以向Addrs字段提供多个MongoDB服务实例的地址，也可以提供一个地址，当我们使用一个地址连接到一个副本集时，mgo驱动会自己获取副本集里面其他的MongoDB服务实例的地址。在这个例子里面我们选择单地址连接方式。提供完地址以后，我们指定要连接数据库以及用于验证的用户名和密码。需要注意的一点是我们验证的数据库和我们的应用需要访问的数据库可能不是一个MongoDB服务实例。有些应用通过admin数据库进行验证，验证通过后，根据配置访问其他的数据库。mgo驱动能够很好的支持这种场景。接下来我们用`mgo.DialWithInfo`方法创建一个`mgo.Session`对象，每个session都需要指定数据一致性模式：强一致、最终一致或者其他例如的写优先或者读优先配置。`mgo.Session`对象维护了一个到MongoDB实例的连接池。我们可以创建多个不同一致性模式的session用于支持不同的应用场景。
```golang
// We need this object to establish a session to our MongoDB.
mongoDBDialInfo := &mgo.DialInfo{
    Addrs:    []string{MongoDBHosts},
    Timeout:  60 * time.Second,
    Database: AuthDatabase,
    Username: AuthUserName,
    Password: AuthPassword,
}

// Create a session which maintains a pool of socket connections
// to our MongoDB.
mongoSession, err := mgo.DialWithInfo(mongoDBDialInfo)
if err != nil {
    log.Fatalf("CreateSession: %s\n", err)
}
```

下面这行代码设置了session的模式，总共有三种模式：强一致、单调、最终一致。每种模式指定了读写操作时的一致性。关于模式的更多信息可以参考mgo驱动的[这篇文档](http://godoc.org/labix.org/v2/mgo#Session.SetMode)。我们使用单调模式，它的特点是读不一定在时间上和写实时同步，但是读能够跟随写操作的单调变化（指的是按照写的时间单调）。在这个模式中，只要session上没有进行过写操作，都是读副本集的从节点，如果session上发生了写操作，会转而连接副本集的主节点。这样做的好处是可以尽可能的把读压力分担到从节点。
```golang
// Reads may not be entirely up-to-date, but they will always see the
// history of changes moving forward, the data read will be consistent
// across sequential queries in the same session, and modifications made
// within the session will be observed in following queries (read-your-writes).
// http://godoc.org/labix.org/v2/mgo#Session.SetMode.
mongoSession.SetMode(mgo.Monotonic, true)
```

当设置了session以后就准备开始查询了，下面我们并发执行多个查询：代码是Go并发的标准写法。首先我们创建一个`sync.WaitGroup`用于跟踪我们启动的goroutine是否完成了查询操作。然后我们把`sync.WaitGroup`的计数值设置为10，通过循环 启动10个goroutine执行`RunQuery`函数。`go`关键字用于并发执行一个函数或者方法。最后一行代码调用`sync.WaitGroup.Wait`方法它会将主goroutine阻塞，直到10个goroutine都完成了处理。想要了解更多关于Go并发的内容，以及更好的理解这段代码是如何工作的，可以看[这篇博客](http://www.goinggo.net/2014/01/concurrency-goroutines-and-gomaxprocs.html)和[这篇博客](http://www.goinggo.net/2014/02/the-nature-of-channels-in-go.html)。
```golang
// Create a wait group to manage the goroutines.
var waitGroup sync.WaitGroup

// Perform 10 concurrent queries against the database.
waitGroup.Add(10)
for query := 0; query < 10; query++ {
    go RunQuery(query, &waitGroup, mongoSession)
}

// Wait for all the queries to complete.
waitGroup.Wait()
log.Println("All Queries Completed")
```

现在让我们看下`RunQuery`函数是怎么合理的使用`mgo.Session`对象获取一个连接并执行查询的：`RunQuery`函数中做的第一件事是通过defer关键字调用`sync.WaitGroup.Done`方法，它会把方法的执行延期，一旦`RunQuery`函数返回就执行。这样可以确保`sync.WaitGroup`的计数值减一，即使是发生了未处理的异常。接下来我们获取主goroutine创建的session对象的拷贝，每个goroutine需要拷贝session对象，这样每个goroutine可以获得自己独占的一个socket，如果所有goroutine使用一个socket会导致并发查询变成顺序执行的。同样，我们使用defer关键字把session对象的Close操作推迟到`RunQuery`函数退出时执行，关闭session会把socket放回到连接池中，这个很重要。
```golang
// Decrement the wait group count so the program knows this
// has been completed once the goroutine exits.
defer waitGroup.Done()

// Request a socket connection from the session to process our query.
// Close the session when the goroutine exits and put the connection back
// into the pool.
sessionCopy := mongoSession.Copy()
defer sessionCopy.Close()
```

我们通过`mgo.Collection`来执行查询，通过指定数据库名和集合名，从`mgo.Session`对象获取`mgo.Collection`对象，使用`mgo.Collection`，我们可以执行Find操作返回集合中的所有文档。`mgo.Collection.All`方法会把返回值反序列化到`[]BuoyStation`对象中。slice是Go语言中的动态数据，注意`All`方法会把所有的数据加载到内存中，对于很大的集合，最好使用`Iter`方法代替。最后我们在`RunQuery`返回前把BuoyStation对象的数量打印到日志中。
```golang
// Get a collection to execute the query against.
collection := sessionCopy.DB(TestDatabase).C("buoy_stations")

log.Printf("RunQuery : %d : Executing\n", query)

// Retrieve the list of stations.
var buoyStations []BuoyStation
err := collection.Find(nil).All(&buoyStations)
if err != nil {
    log.Printf("RunQuery : ERROR : %s\n", err)
    return
}

log.Printf("RunQuery : %d : Count[%d]\n", query, len(buoyStations))
```

#### 结论
这个例子展示了如何使用Go并发启动多个goroutine执行MongoDB查询。一旦创建了一个session，mgo驱动会把MongoDB的所有方法暴露出来给用户使用，mgo驱动还能实现把BSON格式的文档反序列化到Go语言的类型中。

如果你仔细设置MongoDB的数据库和集合架构，MongoDB能够执行高并发的查询。Go和mgo驱动能够充分的把MongoDB的性能发挥到极致，这样你构建的软件能够充分利用计算性能。

mgo驱动提供了安全使用Go并发机制的支持，你可以很灵活的并发或并行执行查询。最好花一点时间学习MongoDB的副本集和负载均衡配置，然后确保负载均衡器在你的生产环境中能够按照预期工作。

现在是一个伟大的时间可以看到MongoDB和Go语言可以为的软件应用、web服务和平台做什么。这两个技术每天都在不同类型的公司中经受考验，解决各种类型的业务和计算问题。