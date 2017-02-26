## [OpenZipkin: A distributed tracing system](http://zipkin.io/)

[TOC]

### 1 Home

#### 1.1 Zipkin是什么
![](OpenZipkin A distributed tracing system/1.png)

Zipkin是一个分布式追踪系统。用于收集时序信息，从而优化微服务架构的时延。Zipkin的理论基础是[谷歌Dapper论文](http://research.google.com/pubs/pub36356.html)，实现了追踪数据的采集和查询。

应用程序通过植入追踪点的方式把时序信息汇报给Zipkin。Zipkin UI除了展现时序信息以外，还会通过依赖图展现每个应用程序接收、发送的请求数量，如果你正在解决系统时延或者定位系统中的某个错误，可以格局应用程序、trace数据长度、annotation以及时间戳等对所有被追踪的请求进行过滤或排序，从中选择一个被追踪的请求，通过观察每个span占整个请求时间的百分比，从而定位应用程序的问题。
>Applications are instrumented to report timing data to Zipkin. 

#### 1.2 接下来
1. 试用Zipkin，可以阅读[快速入门](http://zipkin.io/pages/quickstart)
2. 调研你的平台是否已经支持[追踪程序库](http://zipkin.io/pages/existing_instrumentations)
3. 加入[Zipkin的gitter讨论频道](https://gitter.im/openzipkin/zipkin)
4. Zipkin的代码托管在Github的[openzipkin/zipkin](https://github.com/openzipkin/zipkin/)
5. issue也在[Github](https://github.com/openzipkin/zipkin/issues)上讨论

### 2 Quickstart
这部分主要介绍构建并运行一个zipkin系统实例，以便于用户在本地试用Zipkin。本文提供三种构建方式：Java、Docker以及从源码构建运行。

如果熟悉Docker，这里推荐使用Docker部署Zipkin，否则可以选择Java或者直接从源码构建运行。不论以那种方式构建部署，Zipkin UI的URL都是http://your_host:9411。

#### 2.1 Docker
[Docker Zipkin]项目可以构建Zipkin的docker镜像，并提供了相关的脚本以及docker-compose.yml文件启动编译好的镜像。当然也可以直接执行镜像，这是最简单的方法：
```shell
docker run -d -p 9411:9411 openzipkin/zipkin
```

#### 2.2 Java
如果你安装了Java 8或者更高的版本，最快开始使用Zipkin的方法是获取[最新的发布版](https://search.maven.org/remote_content?g=io.zipkin.java&a=zipkin-server&v=LATEST&c=exec)作为可独立执行的jar文件：
```shell
wget -O zipkin.jar 'https://search.maven.org/remote_content?g=io.zipkin.java&a=zipkin-server&v=LATEST&c=exec'
java -jar zipkin.jar
```

#### 2.3 从源码运行
如果你需要开发新的功能，可以从源码运行Zipkin。你需要获取[Zipkin源码](https://github.com/openzipkin/zipkin)并编译：
```shell
# get the latest source
git clone https://github.com/openzipkin/zipkin
cd zipkin
# Build the server and also make its dependencies
./mvnw -DskipTests --also-make -pl zipkin-server clean install
# Run the server
java -jar ./zipkin-server/target/zipkin-server-*exec.jar
```

如果你发现了什么有趣的地方，欢迎和我们在[gitter](https://gitter.im/openzipkin/zipkin)上交流。

### 3 Architecture
#### 3.1 架构概览
使用了追踪功能的应用程序可以通过追踪器记录时序信息已经其他的一些元信息，例如：应用程序执行的操作。追踪功能通常是对应用程序使用的库进行埋点，因此追踪器对用户是透明的。例如：对web服务器程序的http通信库埋点，在接收请求和发送响应时就可以记录追踪数据，这些被追踪的数据叫做span。
>They often instrument libraries, so that their use is transparent to users.

追踪程序库需要稳定、低开销才能应用在生产中。因此，追踪程序库只会把追踪标识符放在用户真实的请求中传递，用于告诉下游的服务，这个请求是被追踪的。真正的追踪数据则异步的发给Zipkin后端服务，就如同应用程序向监控平台汇报指标信息一样。

例如：追踪某个应用程序中的一个操作，这个操作需要向后端发送一个http请求，此时追踪程序库需要在http请求头部添加一些标识符。除此之外，span中的其他信息，例如追踪请求的名字等都不会通过http请求传递给后端。

被追踪的应用程序通过汇报器（原文：Reporter）把追踪数据发送给Zipkin。汇报器和收集器之间会有多种传输通路。收集器把追踪数据持久化到存储中。最后，Web UI调用查询API服务展现追踪数据。

下图描述了数据通路：

![](OpenZipkin A distributed tracing system/2.png)

参考[Zipkin支持的追踪程序库列表](http://zipkin.io/pages/existing_instrumentations)，看看你使用的平台是否Zipkin已经支持了追踪程序库。

#### 3.2 例子
如概览中所说，追踪标识符（译者注：TraceId、SpanId）是跟随用户请求一起传输的，而span数据是单独发送到Zipkin的。不论是传输追踪标识符还是span数据，都是由追踪程序库来创建追踪数据结构，并根据当前请求的具体数据填充。例如：**a tracer ensures parity between the data it sends in-band (downstream) and out-of-band (async to Zipkin).**
>As mentioned in the overview, identifiers are sent in-band and details are sent out-of-band to Zipkin. ... 
>For example, a tracer ensures parity between the data it sends in-band (downstream) and out-of-band (async to Zipkin).

下图是追踪http请求的序列图，用户代码请求资源/foo，当用户代码接收到http响应以后，追踪程序库会创建一个span，并把它异步的发送到Zipkin。

因为追踪程序库对用户代码有侵入性，因此通过异步发送span，减少因为追踪系统给用户代码带来的额外时间开销以及发送失败时的错误处理。
```
┌─────────────┐ ┌───────────────────────┐ ┌─────────────┐ ┌──────────────────┐
│ User Code   │ │ Trace Instrumentation │ │ Http Client │ │ Zipkin Collector |
└─────────────┘ └───────────────────────┘ └─────────────┘ └──────────────────┘
       │                 │                         │                 │
           ┌─────────┐
       │ ──┤GET /foo ├─> │ ────┐                   │                 │
           └─────────┘         │ record tags
       │                 │ <───┘                   │                 │
                           ────┐
       │                 │     │ add trace headers │                 │
                           <───┘
       │                 │ ────┐                   │                 │
                               │ record timestamp
       │                 │ <───┘                   │                 │
                             ┌─────────────────┐
       │                 │ ──┤GET /foo         ├─> │                 │
                             │X-B3-TraceId: aa │     ────┐
       │                 │   │X-B3-SpanId: 6b  │   │     │           │
                             └─────────────────┘         │ invoke
       │                 │                         │     │ request   │
                                                         │
       │                 │                         │     │           │
                                 ┌────────┐          <───┘
       │                 │ <─────┤200 OK  ├─────── │                 │
                           ────┐ └────────┘
       │                 │     │ record duration   │                 │
            ┌────────┐     <───┘
       │ <──┤200 OK  ├── │                         │                 │
            └────────┘       ┌────────────────────────────────┐
       │                 │ ──┤ asynchronously report span     ├────> │
                             │                                │
                             │{                               │
                             │  "traceId": "ab",              │
                             │  "id": "6b",                   │
                             │  "name": "get",                │
                             │  "timestamp": 1483945573944000,│
                             │  "duration": 386000,           │
                             │  "annotations": [              │
                             │--snip--                        │
                             └────────────────────────────────┘
```

#### 3.3 传输
被追踪的服务通过追踪程序库把被追踪的信息以span的形式发送给Zipkin的收集器。主要的传输方式有三种：HTTP、Kafka和Scribe。更多信息参考[span接收](http://zipkin.io/pages/span_receivers)。

Zipkin由四部分组成：
1. 收集器
2. 存储
3. 查询
4. web UI

#### 3.4 收集器
当追踪数据到达Zipkin的收集器守护程序以后，数据会先进行校验，如果正确就写入存储中，同时对追踪数据会创建索引用于查询。

#### 3.5 存储
Zipkin最初使用Cassandra存储数据，因为Cassandra具有良好的可扩展性、灵活的schema，并且Cassandra在Twitter中广泛使用。但是我们也提供了存储的抽象接口，用于支持其他的存储系统。除了Casssandra，Zipkin还支持的存储系统包括：ElasticSearch以及MySQL。其他的存储系统可以通过第三方的扩展实现。

#### 3.6 查询服务
在完成追踪数据的存储和索引以后，下一步就是查询数据。Zipkin通过一个简单的JSON API服务查询追踪数据，这个服务最重要的使用者是Web UI。

#### 3.7 Web UI
我们开发了一个GUI为查看追踪信息提供了美观的使用界面。Web UI提供了按照服务、时间、annotation等维度查看追踪数据的方法。注意：UI中未实现用户权限的认证功能。

### 4 Existing instrumentations
追踪数据是通过每台机器上的追踪程序库收集并且发送到Zipkin的。当一个应用程序请求另一个应用程序时，追踪标识符会通过请求传递到另一个应用程序，这样Zipkin才能将一个请求经过的所有应用程序上的追踪数据通过追踪标识符组织成若干个span。

下面介绍一下目前Zipkin支持的不同平台上的追踪程序库，使用它们请阅读相应的文档。

#### 4.1 OpenZipkin追踪程序库
下面的追踪程序库是由OpenZipkin作者维护的，代码一同托管在[OpenZipkin的Github项目组](https://github.com/openzipkin/)、在[Zipkin gitter](https://gitter.im/openzipkin/zipkin/)可以联系到这些库的作者。

|语言|库|框架|追踪标识符传递|传输方式|采样|其他|
|----|--|----|--------------|--------|----|----|
|Go|[zipkin-go-opentracing](https://github.com/openzipkin/zipkin-go-opentracing)|[Go kit](https://gokit.io/), or roll your own with [OpenTracing](http://opentracing.io/)|Http (B3), gRPC (B3)|Http, Kafka, Scribe|Yes||
|Java|[brave](https://github.com/openzipkin/brave)|Jersey, RestEASY, JAXRS2, Apache HttpClient, Mysql|Http (B3), gRPC (B3)|Http, Kafka, Scribe|Yes|Java 6 or higher|
|JavaScript|[zipkin-js](https://github.com/openzipkin/zipkin-js)|[cujoJS](http://cujojs.com/), [express](http://expressjs.com/), [restify](http://restify.com/)|Http (B3)|Http, Kafka, Scribe|Yes|Uses continuation-local-storage under to hood, so you don’t have to pass around an explicit context|
|Ruby|[zipkin-ruby](https://github.com/openzipkin/zipkin-ruby)|[Rack](http://rack.github.io/)|Http (B3)|Http, Kafka, Scribe|Yes|lc support. Ruby 2.0 or higher|
|Scala|[zipkin-finagle](https://github.com/openzipkin/zipkin-finagle)|[Finagle](https://github.com/twitter/finagle)|Http (B3), Thrift|Http, Kafka, Scribe|Yes|Library is written in Java. Propagation is defined in Finagle itself.|

#### 4.2 社区开发的追踪程序库
如果这里缺少了哪个库，请向[本网页的Github](https://github.com/openzipkin/openzipkin.github.io)提交pull reuqest补充。

如果想要自己开发另一个框架或者平台的追踪程序库，请阅读文档[追踪程序库](http://zipkin.io/pages/instrumenting)

|语言|库|框架|追踪标识符传递|传输方式|采样|其他|
|----|--|----|--------------|--------|----|----|
|C#|[ZipkinTracerModule](https://github.com/mdsol/Medidata.ZipkinTracerModule)|OWIN, HttpHandler|Http (B3)|Http|Yes|lc support. 4.5.2 or higher
|C#|[Zipkin4net](https://github.com/criteo/zipkin4net)|Any|Http (B3)|Any|Yes| 
|Go|[go-zipkin](https://github.com/elodina/go-zipkin)|x/net Context| ||Kafka|Yes| 
|Go|[monkit-zipkin](https://github.com/spacemonkeygo/monkit-zipkin/)|[Monkit](https://github.com/spacemonkeygo/monkit/)|Http (B3), easy to add others|Scribe, UDP, easy to add others|Yes| 
|Java|[cassandra-zipkin-tracing](https://github.com/thelastpickle/cassandra-zipkin-tracing)|[Apache Cassandra](http://cassandra.apache.org/)|CQL (B3)|Http, Kafka, Scribe|Yes|Java 8+
|Java|[Dropwizard Zipkin](https://github.com/smoketurner/dropwizard-zipkin)|[Dropwizard](http://www.dropwizard.io/)|Http (B3), Thrift|Http, Scribe|Yes|Java 7 or higher
|Java|[htrace](https://github.com/apache/incubator-htrace/tree/master/htrace-zipkin)|HDFS, HBase||Http, Scribe| |Yes|Java 7 or higher
|Java|[Spring Cloud Sleuth](https://github.com/spring-cloud/spring-cloud-sleuth)|Spring, Spring Cloud (e.g. Stream, Netflix)|Http (B3), Messaging (B3)|Http, Spring Cloud Stream Compatible (e.g. RabbitMQ, Kafka, Redis or anything with a custom Binder)|Yes|Java 7 or higher
|Java|[Wingtips](https://github.com/Nike-Inc/wingtips)|[Any Servlet API framework](https://github.com/Nike-Inc/wingtips/tree/master/wingtips-servlet-api), [roll-your-own](https://github.com/Nike-Inc/wingtips#generic-application-pseudo-code), [async framework support](https://github.com/Nike-Inc/wingtips#usage-in-reactive-asynchronous-nonblocking-scenarios)|Http (B3)|Http|Yes|Java 7 or higher, [SLF4J MDC support](https://github.com/Nike-Inc/wingtips#mdc_info) for auto-tagging all log messages with tracing info
|Python|[py_zipkin](https://github.com/Yelp/py_zipkin)|Any|Http (B3)|Pluggable|Yes|Generic python tracer, used in pyramid-zipkin; py2, py3 support.
|Python|[pyramid_zipkin](https://github.com/Yelp/pyramid_zipkin)|[Pyramid](http://docs.pylonsproject.org/projects/pyramid/en/latest/)|Http (B3)|Kafka, Scribe|Yes|py2, py3 support.
|Python|[swagger_zipkin](https://github.com/Yelp/swagger_zipkin)|Swagger ([Bravado](http://bravado.readthedocs.io/en/latest/)), to be used with py_zipkin|Http (B3)|Kafka, Scribe|Yes|Uses py_zipkin; py2, py3 support.
|Python|[flask_zipkin](https://github.com/qiajigou/flask-zipkin)|[Flask](http://flask.pocoo.org/)|Http (B3)|Pluggable|Yes|Uses py_zipkin; py2, py3 support.
|Scala|[akka-tracing](https://github.com/levkhomich/akka-tracing)|[Akka](https://akka.io/), [Spray](https://spray.io/), [Play](https://www.playframework.com/)|Http (B3), Thrift|Scribe|Yes|Java 6+, Scala 2.10+, activator templates for Akka and Play

### 5 Data Model

### 6 Instrumenting a library

### 7 Transports

