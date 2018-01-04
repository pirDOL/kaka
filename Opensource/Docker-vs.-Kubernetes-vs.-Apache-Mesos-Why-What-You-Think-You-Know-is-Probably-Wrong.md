## [Docker vs. Kubernetes vs. Apache Mesos: Why What You Think You Know is Probably Wrong](https://mesosphere.com/blog/docker-vs-kubernetes-vs-apache-mesos/)

### TLDR
你装在裸机里的虚拟机里的DC/OS 里的 Mesos 里的 OpenStack 里的 k8s 里的 Docker 里的应用。。 ​

![](Docker-vs.-Kubernetes-vs.-Apache-Mesos-Why-What-You-Think-You-Know-is-Probably-Wrong/62ce04ffgy1fjik6d05d3j20dw0gh0w2.jpg)

1. original mission
    1. docker: managing dependencies and binaries across many applications and customers required significant effort. So they combined some of the capabilities of Linux cgroups and namespaces into a single and easy to use package so that applications can consistently run on any infrastructure.
    2. container orchestration: additional tooling was needed to coordinate these containers across multiple machines
        1. Marathon on Apache Mesos: the first container orchestrators that supported Docker images
        2. k8s: 
            1. existing internal container and distributed computing tools like Borg were directly coupled to Google's infrastructure. So, instead of using any code from their existing systems, Google designed Kubernetes from scratch to orchestrate Docker containers.
            2. Kubernetes’ core strength is providing application developers powerful tools for orchestrating stateless Docker containers.
            3. Kubernetes is also attractive because it is open source under the CNCF, in contrast to Docker Swarm(now part of Docker Engine) which, though open source, is tightly controlled by Docker, Inc.
        3. mesos：
            1. Mesos has a unique ability to individually manage a diverse set of workloads — including traditional applications such as Java, stateless Docker microservices, batch jobs, real-time analytics, and stateful distributed data services. Mesos’ broad workload coverage comes from its two-level architecture, which enables “application-aware” scheduling. 
            2. Container orchestration is one example of a workload that can run on Mesos’ modular architecture, and it’s done using a specialized orchestration “framework” built on top of Mesos called Marathon. 
2. So when people compare Docker and Kubernetes to Mesos, they are actually comparing Kubernetes and Docker Swarm to Marathon running on Mesos.

### 翻译

无数的文章、讨论和开源社区的chatter都在比较Docker、Kubernetes、Mesos。如果你听信了某些一知半解者的言论，你可能会认为这三个开源项目正在为争夺容器霸权而殊死战斗（原文：in a fight-to-the death for container supremacy）。同时，你也会相信，在这三者间的选择无异于对其所奉宗教的信仰，而且真正的信徒敢于大胆和异教徒作斗争，并且拥护自己的信仰。

那些都是扯淡。

虽然这三种技术都可以使用容器来部署、管理和扩展应用程序，但实际上它们每个都侧重解决不同的问题，并且扎根在不同的问题上下文中。事实上，这三种被广泛采用的工具链彼此完全不同。

（这篇文章不去）比较这些快速发展的技术的相似的特性，我们会回顾一下每个项目的原始任务、架构以及它们之间如何相互补充和交互。

#### 让我们从Docker开始

今天的Docker公司脱胎于一个PaaS的初创公司dotCloud。dotCloud团队发现为了满足在许多应用程序和客户不同的依赖关系管理和二进制需要做大量的工作。因此他们将Linux的[cgroups](https://en.wikipedia.org/wiki/Cgroups)和namespaces的一些功能组合成一个简单易用的包，这样应用程序就可以在任何基础设施上持续运行。这个包就是[Docker镜像](https://docs.docker.com/engine/docker-overview/)，它提供以下功能:

* 将应用程序和库打包在单个包中（Docker镜像），因此应用程序可以跨多环境一致部署
* 提供类似于git的语义，例如“docker push”，“docker commit”，这样可以让应用程序开发者快速使用新技术，并将其融入到现有的工作流中
* 将Docker镜像定义为不可变层，提供不可变的基础设施。提交的更改被存储为一个单独的只读层，这让镜像复用和跟踪更改变得更加容易。通过传输镜像更新的部分而不是整个镜像节省看磁盘空间和网络流量（原文：Layers also save disk space and network traffic by only transporting the updates instead of entire images）
* 通过实例化不可变镜像来运行docker容器，同时使用可以临时存储运行时状态的可写层来，从而方便快速部署和扩展应用程序的多个实例

随着Docker的风靡，开发人员开始把容器从笔记本电脑转移到生产环境中运行。这就需要借助工具来协调这些容器，我们称为容器编排。有趣的是，Apache Mesos的[Marathon](https://mesosphere.github.io/marathon/)成为当时（2014年6月）第一个支持Docker镜像的容器编排工具（我们将在下面详细描述它）。就连Docker创始人、首席技术官Solomon Hykes也推荐Mesos为“[生产集群的黄金标准](https://www.google.com/url?q=https://www.youtube.com/watch?v=sGWQ8WiGN8Y&feature=youtu.be&t=35m10s&sa=D&ust=1500923856666000&usg=AFQjCNFLtW96ZWnOUGFPX_XUuVOPdWrd_w)”。不久之后，除了Marathon之外，许多容器编排技术出现了，这其中包括：[Nomad](https://www.nomadproject.io/)、[Kubernetes](http://kubernetes.io/)以及毫不意外的Docker Swarm（[现在是Docker引擎的一部分](https://blog.docker.com/2016/06/docker-1-12-built-in-orchestration/)）。

随着Docker开始商业化开源文件格式，该公司也开始引入工具来补充核心Docker文件格式和运行时引擎，包括:

* Docker hub：发布和存储Docker镜像
* Docker registry：私有化存储Docker镜像
* Docker cloud：构建和运行容器的管理服务
* Docker datacenter：商业化提供很多Docker技术
​
![](Docker-vs.-Kubernetes-vs.-Apache-Mesos-Why-What-You-Think-You-Know-is-Probably-Wrong/docker-host.png)

Docker让开发者可以把应用及其依赖打包到一个包里面使其成为软件行业的游戏规则改变者，这有点类似mp3格式帮助重塑了音乐产业。Docker文件格式成为行业标准，并且领导容器技术供应商（包括Docker、Pivotal, Mesosphere以及其他许多）成立[CNCF](https://www.cncf.io/)和[OCI](https://www.opencontainers.org/)。今天，CNCF和OCI的目标就是确保跨容器技术的互操作性和标准化接口，并确保使用任何工具构建的Docker容器都可以在任何运行时环境或基础设施上运行。

#### 进入Kubernetes

谷歌很早就认识到Docker镜像的潜力，并尝试在谷歌云平台上提供“容器编排即服务”。谷歌在容器方面有丰富的经验（他们在Linux中引入了cgroups），但是现有的内部容器和像Borg这样的分布式计算工具与谷歌的基础设施直接耦合。因此，谷歌没有使用现有系统中的任何代码，而是从头开始设计了Kubernetes，以编排Docker容器。Kubernetes于2015年2月发布，并提出以下目标和考虑:

* 通过一个强大的工具为应用程序开发者赋能，不必与底层基础设施交互就可以实现Docker容器编排
* 为云计算环境中的持续应用程序部署体验和API接口提供标准部署接口和原语
* 构建一个模块化的API核心，允许供应商围绕核心Kubernetes技术集成系统。

2016年3月谷歌向CNCF[捐赠了Kubernetes](https://www.linuxfoundation.org/news-media/announcements/2016/03/cloud-native-computing-foundation-accepts-kubernetes-first-hosted-0)，至今谷歌仍是该项目的主要贡献者（其次是Redhat、CoreOS等）。

![](Docker-vs.-Kubernetes-vs.-Apache-Mesos-Why-What-You-Think-You-Know-is-Probably-Wrong/kubernetes-architecture.png)

Kubernetes对应用程序开发人员非常有吸引力，因为它减少了对基础设施和运维团队的依赖。供应商也非常喜欢Kubernetes，因为它提供了一种简单的方式来让他们拥抱容器迁移，自己部署的Kubernetes是运维上的一项挑战，Kubernetes为此提供一个商业化解决方案（原文：provide a commercial solution to the operational challenges of running your own Kubernetes deployment (which remains a non-trivial exercise). ）。除此之外，Kubernetes的吸引力还源自于它是CNCF下的开源项目，与Docker Swarm相比，后者虽然是开源的，但却受到Docker Inc.的严格控制。

Kubernetes的核心优势是为应用程序开发人员提供强大的工具来编排无状态的Docker容器。虽然有多个创新项目将Kubernetes的范围扩展到更多的工作场景（如数据分析和有状态的数据服务），但这些计划仍然处于非常早期的阶段，还有待观察。

#### Apache Mesos
Apache Mesos最初是UC Berkeley为创建下一代集群管理器而诞生的项目，并从如[谷歌的Borg](https://research.google.com/pubs/pub43438.html)和[Facebook的Tupperware](https://www.youtube.com/watch?v=C_WuUgTqgOc)中吸取经验教训。但是Borg和Tupperware是单体架构，并且是和物理基础设施绑定的不开源专有技术。Mesos引入了模块化架构，采用开源的方法，且设计完全独立于底层基础架构。Mesos很快被[Twitter](https://youtu.be/F1-UEIG7u5g)、[Apple(Siri)](http://www.businessinsider.com/apple-siri-uses-apache-mesos-2015-8)、[Yelp](https://engineeringblog.yelp.com/2015/11/introducing-paasta-an-open-platform-as-a-service.html)、[Uber](http://highscalability.com/blog/2016/9/28/how-uber-manages-a-million-writes-per-second-using-mesos-and.html)、[Netflix](https://medium.com/netflix-techblog/distributed-resource-scheduling-with-apache-mesos-32bd9eb4ca38)以及许多领先的科技公司所采用，以支持他们在微服务、大数据和实时分析到弹性伸缩的一切实践。

作为一个集群管理器，Mesos的架构是为了解决一系列非常不同的挑战:

* 将数据中心资源整合成一个单一池，以简化资源配置，同时在私有或公共云之间提供一致的应用程序和操作体验
* 在相同的基础设施上实现不同的工作负载服务部署，比如分析、无状态微服务、分布式数据服务和传统应用程序，以提高利用率，降低成本和空间
* 应用程序定制运维操作的自动化（automate day-two operations），如部署、自修复、扩容和升级通过自动化的day-two 操作实现，提供高可用的容错基础设施
* 提供可持续的扩展性，在不修改集群管理器或现有应用程序的情况下，提供可扩展性来运行新的应用程序和技术
* 将应用程序和底层基础设施弹性从几个节点扩展到数万个节点

Mesos的独特之处还在于可以单独管理各种不同的工作负载：包括传统的应用程序，如Java、无状态Docker微服务、批处理任务、实时分析和有状态的分布式数据服务。Mesos广泛的工作负载覆盖来自于它的[两级架构，这个架构实现了“应用感知”的调度](https://mesosphere.com/blog/application-aware-scheduling-mesos/)。应用感知调度是通过将应用程序特定操作逻辑封装到“Mesos框架”（类似于运行中的runbook）来完成的。Mesos Master是资源管理器，它向应用程序特定的Mesos框架提供底层基础设施，同时保持资源隔离。这种方法使得每个工作负载有自己专用的应用程序调度器，它了解其对部署、缩放和升级的具体操作需求。应用程序调度程序也独立地被开发、管理和更新，这让Mesos保持高度可扩展性，支持新的工作负载，或者随着时间的推移增加更多的操作能力。

![](Docker-vs.-Kubernetes-vs.-Apache-Mesos-Why-What-You-Think-You-Know-is-Probably-Wrong/mesos-two-level-scheduler.png)

以一个团队如何管理升级为例：无状态应用程序可以从“[蓝/绿](https://martinfowler.com/bliki/BlueGreenDeployment.html)”部署方法中获益：当旧的应用程序还在使用的时候，就可以启动（原文：another complete version of the app is spun up）另一个完整版本的程序，当准备好以后把流量切换到新的应用程序，再销毁旧的应用程序。但是，升级像HDFS或Cassandra这样的数据工作负载需要把存储节点设置为离线状态，把本地数据持久化以避免数据丢失，执行特定操作序列进行升级，并在升级之前和之后根据每个节点类型执行特殊检查和命令。这些步骤中的所有环节针对特定的应用程序或服务，甚至是特定版本进行的。这使得用常规容器编排调度器管理数据服务变得非常困难。

Mesos具备按需管理每个工作负载的能力，使得许多公司将Mesos作为一个统一的平台，并通过其将微服务和数据服务结合运行。运行数据密集型应用程序的一个通用参考架构是[SMACK stack](https://mesosphere.com/blog/2017/06/21/smack-stack-new-lamp-stack/)。

#### 清晰时刻
我们在描述Apache Mesos的过程中，没有提及任何关于容器编排的内容。那么，为什么人们总是会将Mesos与容器编排联系起来呢？容器编排是一个可以在Mesos模块化架构上运行的工作负载的例子，它使用的是构建在Mesos上的一个专门的编排框架——Marathon。Marathon最初是为了在cgroup容器中编排应用程序（如JARs、tarball、ZIP文件）而开发的，并且在2014年成为第一批支持Docker容器的容器编排工具之一。

因此，当人们拿Docker、Kubernetes和Mesos比较时，他们实际上是在对比Kubernetes、Docker Swarm和Mesos上运行的Marathon。

为什么这很重要？因为Mesos根本不关心上面跑的是什么。Mesos可以为Java应用服务器、Docker容器编排、Jenkins持续集成任务、Apache Spark分析、Apache Kafka消息流以及更多的共享基础设施提供集群服务。Mesos甚至可以运行Kubernetes或其他容器编排，尽管还没有对外提供可用的版本。

![](Docker-vs.-Kubernetes-vs.-Apache-Mesos-Why-What-You-Think-You-Know-is-Probably-Wrong/mesos-workloads.png)

Mesos的另一个考虑（以及为什么它对许多企业架构师有吸引力）是它在运行任务关键工作负载时的成熟度。Mesos已经在大规模生产环境下运行（数万台服务器）超过7年，这就是为什么它比市场上其他容器技术更成熟，更可靠的原因。

#### 这一切意味着什么?
总之，这三种技术都与Docker容器有关，提供了容器编排能力，以获得应用程序的可移植性和伸缩性。那么在这三者间要如何选择呢？这就要视不同的工作环境需求而定，工作需求不同，所适用的工具自然也是各不相同。如果您是一名应用程序开发人员，并且正在寻找一种现代的方法来构建和打包应用程序，或者加快微服务启动，那么Docker容器格式和开发工具是你最好的选择。

如果你是一个dev/devops团队，想要构建一个专用的Docker容器编排系统，并愿意亲自动手让你的解决方案和底层基础设施集成（或依赖于公有云基础设施如谷歌容器引擎或Azure容器服务），Kubernetes将是你一个很好的选项。

如果您想构建一个可靠的平台，用以运行多任务关键工作负载，包括Docker容器、传统应用程序（例如Java）和分布式数据服务（例如Spark、Kafka、Cassandra、Elastic），并希望所有这些都可以在云或数据中心上可移植，那么，Mesos（或者Mesos官方的发行版Mesosphere DC/OS）是最适合你的。

无论你作何选择，你所拥抱的一系列工具都将提升你的服务器资源利用率，同时简化应用程序移植，并提高开发人员的敏捷性。你真的值得拥有！

### 参考翻译

* [1](http://www.techug.com/post/docker-vs-kubernetes-vs-apache-mesos.html)
* [2](https://mp.weixin.qq.com/s?__biz=MzA5OTAyNzQ2OA==&mid=2649694746&idx=1&sn=64e3c9f6ad80262104d49ef5b1cd4f98&chksm=88931d79bfe4946f89ad0d618db46c2d1d210e9973f1b24355403c13a1df9be457b5367f6bb5&scene=0&key=4b95006583a3cb389a242738c0831080643909110af79ce3d0a01b479bd0d306fd3f273ce16c0f307697c83be527e3cd6cc548a09bc7fe2764f56a7769edfd1aab470450eb910c702d4b2182ee4f4995)