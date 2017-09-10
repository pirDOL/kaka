### [如何选择使用开源软件建立监控体系](https://mp.weixin.qq.com/s?__biz=MzAwMDU1MTE1OQ==&mid=2653548961&idx=1&sn=52d7c8a4be3ab04355b22930ad5f61c2&chksm=813a6039b64de92fa30e530601d0f25733b2782d84d828b61a351fe53689e29930adcb5a2bd6&mpshare=1&scene=1&srcid=0810mlmrPtuv5PvjmcrgCZkU&key=3ca3acd7b7e79486513b675e553bd51fbdfea38e8f801b9f53108d58a98ad4b735688edb7d1a62b79b3c468efd47343dc4f0317c72bbf53c47f137c823468bb8ca3dc5ba49a7411eb6af86d1b1079cae&ascene=0&uin=MTYyMjExMzUyMw%3D%3D&devicetype=iMac+MacBookPro12%2C1+OSX+OSX+10.11.5+build(15F34)&version=12020610&nettype=WIFI&fontScale=100&pass_ticket=1gsLTeS4kmmluG4VQPh4GTHcOLNta5D0QfwLgmVgYoiN5JXD%2FVPres3m447DOrmS)

1. 基础环境监控
    * 技术范围：IaaS层，CPU、内存、磁盘使用率、网络/磁盘IO
    * 技术栈：zabbix，开源（自主发现服务器、分布式监控、可视化配置），二次开发，对接内部办公通信软件、短信和邮箱
    * 智能预警：
        * 问题：假如我们设定CPU使用率超过85%就告警，那么请问系统在凌晨没什么人使用的时候，CPU使用率超过了50%，系统是正常还是异常的？
        * 解决：将之前几周甚至几个月的指标进行聚合计算，得出当前时间的动态告警阈值，并根据时间的变化而不断调整。如果说监控是看现在，那么智能预警就是观过去，测未来。

2. 应用监控
    * 技术范围：PaaS/SaaS层，访问量、交易时长、交易占比、外部攻击等业务指标，支持管理层业务决策
    * 技术栈：ELK，日志检索
