# 18 · SRv6 TE：没有信令的隧道

> **本章定位**：补章，取自《SRv6 Network Programming: Ushering in a New Era of IP Networks》（Zhenbin Li、Zhibo Hu、Cheng Li，2021）第 4 章《SRv6 TE》。前 17 章回答"段怎么表达路径"，这一章回答三个新问题：**路径由谁算出来、怎么交给头端、算错了或者断了怎么发现**。体例不变：英文块为该章原文摘录，紧随其后的中文是逐段翻译，原文 Figure 按描述用 ASCII 重绘，配置按 IOS XR 风格示意。

**本章要拿到的东西**：

| 问题 | 对应小节 |
|---|---|
| 为什么 SPF 不足以承载 SLA，TE 到底在优化什么 | 18.1 |
| MPLS TE 的四个组件，到 SR-TE 少掉了哪一个 | 18.1.1 / 18.1.2 |
| 控制器为什么要用 BGP-LS 而不是直接做 IGP 邻居 | 18.2.1 |
| BGP-LS 为 SRv6 加了哪些 TLV，排障先看哪几个 | 18.2.2 |
| SR Policy 的三个 Key、候选路径的三元组分别是什么 | 18.4 |
| 手工 / 头端 / 集中式三条算路各自做不到什么 | 18.5 |
| BSID、Color、DSCP 三种引流的适用边界 | 18.6 |
| 为什么"策略 up"不代表"路径通" | 18.8 |
| 控制器下发策略用 BGP 还是 PCEP，本质差别在哪 | 18.9 / 18.10 |

一句话概括本章与前 17 章的关系：**第 3 章把"路点"做进了 SID，本章把"路点"变成了可计算、可下发、可运维的对象**。MPLS TE 用信令在每一跳建隧道；SRv6 TE 把隧道状态只留在头端，省掉的是逐跳状态，代价是**再也收不到"路径断了"的信令通知**——所以本章后半段（18.8）比前半段更要紧。

## 18.0 本章拓扑

```text
图 18-1：本章拓扑（原书 Figure 4.29 / 4.30 场景重绘）

                       ┌── P1 ────── P2 ──┐       路径 A：低时延（color 100）
   PE1 ────────────────┤                  ├── PE2  locator fc00:0:2::/48
  (headend)            └── P3 ────── P4 ──┘       路径 B：绕行、带宽富余（color 123）
       │
       └────────────────────────────────────── PE3  locator fc00:0:3::/48
                                                 （PE2 的 VPN FRR 备份节点）

  SID 约定（沿用前 17 章）：
    PE1  locator fc00:0:1::/48       End SID  fc00:0:1:e000::
    P1   locator fc00:0:11::/48      End.X（P1→P2）  fc00:0:11:e002::
    P2   locator fc00:0:12::/48      End.X（P2→PE2） fc00:0:12:e001::
    P3   locator fc00:0:13::/48      End.X（P3→P4）  fc00:0:13:e004::
    P4   locator fc00:0:14::/48      End.X（P4→PE2） fc00:0:14:e001::
    PE2  End SID fc00:0:2:e000::     VPN SID（End.DT4，VRF 9）fc00:0:2:e109::
    PE1  动态 BSID 池 fc00:0:1:d000::/64
```

| 角色 | 需要配置的东西 | 不需要的东西 |
|---|---|---|
| PE1（头端） | locator、SRv6 Policy、BSID、BGP-LS、PCEP、SBFD | 逐跳隧道状态 |
| P1–P4 | locator、IGP TE 度量（delay / affinity）、TI-LFA | Policy、BSID、PCEP |
| PE2 / PE3 | locator、VPN SID、带 color 的 BGP 路由、BGP-LS 上报 | Policy（除非也做头端） |
| 控制器 | BGP-LS 收拓扑、PCEP 算路下发、算路算法 | 转发面任何配置 |

## 18.1 从 SPF 到 TE：为什么要"指定路径"

:::en
As one of the most vital network services, TE is widely used in various network scenarios. It is also one of the three major features that SRv6 has inherited from MPLS.
:::

TE（流量工程）是最重要的网络服务之一，广泛用于各类网络场景。它也是 **SRv6 从 MPLS 继承的三大特性之一**（另两个是 VPN 与可靠性）。

:::en
A conventional routing protocol selects the shortest path to route its traffic, regardless of factors such as bandwidth and latency. Traffic is not switched to another path, even if the shortest path is congested. This is not a problem with low traffic on a network. However, with the ever-increasing Internet applications, exclusive use of the SPF algorithm is likely to result in severe routing problems.
:::

常规路由协议只按最短路径转发，**不看带宽和时延**。最短路径拥塞了，流量也不会绕到别的路上去。网络轻载时这不是问题；但应用越堆越多以后，只用 SPF 会带来严重的路由问题。

:::en
TE focuses on optimizing the overall network performance. Its primary objectives are to provide efficient and reliable network services, optimize network resource utilization, and optimize network traffic forwarding paths. TE has two primary concerns. One relates to traffic, that is, how to guarantee the network SLA. The other relates to resources, that is, how to optimize their utilization.
:::

TE 关注的是**整体网络性能**的优化，目标是提供高效可靠的网络服务、优化资源利用率、优化流量转发路径。TE 有两个核心关切：一是**流量**，即怎么保证 SLA；二是**资源**，即怎么把利用率做上去。

这两件事经常互相冲突，这也是 TE 的工程难点所在：

| 关切 | 典型指标 | 优化动作 | 反作用 |
|---|---|---|---|
| 流量（SLA） | 时延、抖动、丢包 | 把业务钉到低时延路径 | 该路径被压满，反而抖动上升 |
| 资源（利用率） | 链路峰值利用率、均值 | 把流量摊到多条路径 | 摊出去的那条可能不满足时延 |

所以 TE 从来不是"算一条更好的路"，而是**在一组互相冲突的约束下分配流量**。

:::en
A traditional way to implement TE is based on MPLS, called MPLS TE. By using an overlay model, MPLS TE can easily establish a dedicated virtual path over a physical network topology, and then map data traffic to the virtual path.
:::

传统做法基于 MPLS，叫 MPLS TE。它用 **overlay 模型**在物理拓扑之上建一条专用虚路径，再把数据流量映射到这条虚路径上。

:::en
MPLS TE uses RSVP-TE as its signaling protocol. RSVP-TE needs to maintain the per-flow path states on each node along a path. As the network scale increases, so does the workload for RSVP-TE to maintain the path states, consuming excessive device resources. As a result, it is difficult to deploy RSVP-TE on large-scale networks.
:::

MPLS TE 用 **RSVP-TE** 做信令。RSVP-TE 需要在路径上的**每个节点维护 per-flow 的路径状态**。网络规模一大，维护这些状态的工作量跟着涨，吃掉大量设备资源，导致 RSVP-TE 在大网上难以部署。

:::en
This is where SR comes in, overcoming the disadvantages of RSVP-TE. SR draws on source routing and carries a sequential list of instructions (called a Segment List) in the packet header to guide packet forwarding on a network. These instructions are targeted at nodes and links instead of data flows. As such, network devices only need to maintain limited node and link states. Transit nodes only need to forward packets based on the SR path information that is explicitly carried in the packets, and do not need to maintain the per-flow path states. This solves the poor scalability issue of RSVP-TE.
:::

SR 就是来解决这个问题的。SR 借用了**源路由**思想，把一串有序指令（Segment List，段列表）放在报文头里，指导报文在网络中转发。**这些指令指向节点和链路，而不是指向数据流**。因此设备只需要维护有限的节点与链路状态：**中间节点只看报文里明确携带的 SR 路径信息转发，不需要维护 per-flow 状态**。这就是 RSVP-TE 扩展性问题的解法。

这段话里"指向节点和链路，而不是数据流"是整章的根。把它换成状态数量的账：

| 方案 | 状态存在哪 | 状态数量级 | 一条隧道挂了要通知几跳 |
|---|---|---|---|
| RSVP-TE | 路径上每一跳 | 隧道数 × 跳数 | 每一跳（Path/Resv 刷新） |
| SRv6 TE | 只有头端 | 策略数（与跳数无关） | 0 跳（没人知道，见 18.8） |

省掉的是状态，**丢掉的是"路径通不通"的知情权**——这就是 18.8 要补的洞。

:::en
Because of this, the SR-TE solution, which combines SR and TE, is future-oriented, more flexible and powerful, and well accepted in the industry.
:::

正因如此，SR 与 TE 结合的 **SR-TE** 方案被视为面向未来的、更灵活也更强的手段，业界接受度很高。

### 18.1.1 MPLS TE 的四个组件

:::en
On a traditional MPLS network, each MPLS node needs to maintain a TE architecture in order to support TE.
:::

传统 MPLS 网络上，每个节点都要维护一套 TE 架构才能支持 TE。

```text
图 18-2：MPLS TE 的四个组件（原书 Figure 4.1 重绘）

  ┌─ 1. 信息通告 ──────────────────────────────┐
  │  IGP TE 扩展（IS-IS 新 TLV / OSPF 新 LSA） │
  │  通告：最大链路带宽、最大可预留带宽、      │
  │        当前已预留带宽、链路颜色(admin group)│
  │            │                               │
  │            ▼                               │
  │        TEDB（流量工程数据库）              │
  └────────────┬───────────────────────────────┘
               │
  ┌────────────▼───────────────┐   ┌──────────────────────┐
  │ 2. 路径选择                 │   │ 3. 信令               │
  │   CSPF（带宽/跳数/策略约束）│──►│   RSVP-TE 逐跳建 CR-LSP│
  │   或离线工具批量算路        │   │   Path → Resv 回程     │
  └────────────────────────────┘   └──────────┬───────────┘
                                              │
  ┌───────────────────────────────────────────▼───────────┐
  │ 4. 报文转发：按标签交换，沿预建 LSP 走                │
  └───────────────────────────────────────────────────────┘
```

:::en
In TE, a network device needs to obtain not only network topology information but also network load information. To obtain both types of information, MPLS TE introduces the information advertisement component. Specifically, MPLS TE extends the existing IGPs to advertise TE link information, for example, introducing new TLVs to IS-IS and new LSAs to OSPF. The TE link information includes the maximum link bandwidth, maximum reservable bandwidth, currently reserved bandwidth, and link colors.
:::

TE 里设备不只要拓扑，还要**负载信息**。为此 MPLS TE 引入了信息通告组件：扩展既有 IGP 通告 TE 链路信息——例如给 IS-IS 加新 TLV、给 OSPF 加新 LSA。TE 链路信息包括**最大链路带宽、最大可预留带宽、当前已预留带宽、链路颜色**。

:::en
Through IGP TE extensions, network devices can maintain TE link and topology attributes of the network to form a Traffic Engineering Database (TEDB). Based on the TEDB, paths that satisfy various constraints can be computed.
:::

借助 IGP 的 TE 扩展，设备可以维护全网的 TE 链路与拓扑属性，形成 **TEDB**。有了 TEDB，才能算出满足各种约束的路径。

:::en
The path selection component uses the Constrained Shortest Path First (CSPF) algorithm and TEDB to compute paths that meet specified constraints. As an improved variant of the SPF algorithm, CSPF takes certain constraints (such as bandwidth requirements, maximum number of hops, and management policy requirements) into consideration when computing the shortest path on a network.
:::

路径选择组件用 **CSPF**（约束最短路径优先）加 TEDB 计算满足约束的路径。CSPF 是 SPF 的改进变体：在算最短路时把**带宽需求、最大跳数、管理策略**等约束一并考虑。

:::en
The signaling component is used to dynamically establish LSPs, avoiding the trouble of manual hop-by-hop configuration. RSVP-TE can be used to establish Constraint-based Routed Label Switched Paths (CR-LSPs).
:::

信令组件用来动态建立 LSP，免得手工逐跳配置。RSVP-TE 用来建立**基于约束的 LSP（CR-LSP）**。

:::en
The packet forwarding component refers to the label-based MPLS data forwarding plane. It switches labels and then forwards packets to a specified next hop. In this manner, packets can be forwarded along preestablished LSPs. As LSPs support forwarding along specified paths, MPLS TE overcomes the disadvantages of IGP-based forwarding only along the shortest path.
:::

报文转发组件就是基于标签的 MPLS 转发面：交换标签、把报文送到指定下一跳，于是报文能沿预建的 LSP 走。因为 LSP 支持按指定路径转发，MPLS TE 才克服了"IGP 只能走最短路"的缺陷。

四个组件里，**第 1、3 两个是"状态制造机"**：TE 度量把带宽占用扩散到全网，RSVP-TE 把隧道状态钉在每一跳。SR-TE 要动的正是这两个。

### 18.1.2 集中式 SR-TE 架构

:::en
SR-TE can also use a functional architecture similar to that used by MPLS TE. Like MPLS, SR floods SR information through IGP extensions. The ingress is responsible for establishing the SR path that meets specific constraints, without the need of RSVP-TE for establishing LSPs. Therefore, the information advertisement and signaling components of SR-TE are integrated to some extent, but they are logically independent of each other.
:::

SR-TE 可以用与 MPLS TE 类似的功能架构。和 MPLS 一样，SR 通过 IGP 扩展扩散 SR 信息。**头端负责建立满足特定约束的 SR 路径，不需要 RSVP-TE 来建 LSP**。因此 SR-TE 的信息通告与信令组件在某种程度上**融合**了，但逻辑上仍相互独立。

这段话容易被读成"省了一个组件"，实际省的是**每个中间节点的组件**：

| 组件 | MPLS TE | SR-TE | 变化本质 |
|---|---|---|---|
| 信息通告 | IGP 扩散拓扑 + 带宽占用 | IGP 只扩散 **SID 与 locator**（拓扑） | 带宽占用不再进 IGP |
| 路径选择 | CSPF（本地，域内） | CSPF（头端）或 **控制器全局算** | 从"各自最优"变成"全局最优" |
| 信令 | RSVP-TE 逐跳 Path/Resv | **没有**（PCEP/BGP 一次性把段列表交给头端） | 状态从 N 跳收敛到 1 跳 |
| 转发 | 标签交换 | IPv6 源路由（SRH / uSID 容器） | 见第 2、3 章 |

:::en
MPLS TE uses the traditional distributed architecture, in which the ingress computes paths based on relevant constraints and uses RSVP-TE to establish CR-LSPs. As services raise more and more SLA requirements on networks and the scale of networks is gradually expanding, several problems regarding distributed path computation occur.
:::

MPLS TE 用的是传统**分布式架构**：头端按约束算路，再用 RSVP-TE 建 CR-LSP。随着业务对 SLA 的要求越来越高、网络规模越来越大，分布式算路暴露出几个问题。

:::en
Although distributed TE uses the SPF or CSPF algorithm to compute paths automatically, it does not compute paths from a global network view. Instead, each node makes its own path decision autonomously, making it impossible to obtain the globally optimal path.
:::

分布式 TE 虽然用 SPF/CSPF 自动算路，但**不是从全局视角算**。每台设备自主决策，因此**拿不到全局最优路径**。

:::en
End-to-end inter-area path computation also has a similar problem. As IGP topology information is flooded only within an IGP area, network nodes can only detect the intra-area topology and cannot compute end-to-end inter-area paths. Although BGP-LS can be used to flood topology information across areas, other problems may occur. For example, path computation on a large-scale network requires more Central Processing Unit (CPU) resources.
:::

端到端跨区算路有同样的问题。IGP 拓扑**只在本区域内扩散**，节点只能看到区域内拓扑，算不出端到端跨区路径。用 BGP-LS 跨区扩散拓扑可以缓解，但又带来新问题，比如大网算路要吃掉更多 **CPU**。

这两条合起来，就是"分布式天花板"：

```text
图 18-3：局部最优 ≠ 全局最优（原书 Figure 4.2 的论证重绘）

  业务：A 区 → B 区，要求时延 < 20 ms

  A 区内部：                 B 区内部：
    R1 ──5ms── R2               R5 ──2ms── R6
     │          │                │          │
     └─ 3ms ────┘                └─ 8ms ────┘

  每个区的头端都只看到本区：各自选"本区最短"。
  但跨区那一段（R2 ── R5）谁都没算进去，
  端到端可能 5+30+2 = 37 ms，SLA 早已破了。
```

:::en
With the emergence of SDN, controller-based centralized control has begun to show its advantages. As the brain of a centrally controlled network, the controller can collect network topology information and TE information globally on the network, compute paths in a centralized manner, and then deliver the computation results to network devices.
:::

SDN 出现后，**控制器集中控制**开始显出优势。控制器作为集中控制网络的大脑，可以**全局收集**网络拓扑与 TE 信息，集中算路，再把结果下发给设备。

:::en
In addition, the controller can collect end-to-end inter-domain topology information and compute paths centrally to obtain the optimal end-to-end inter-domain path. As such, controller-based centralized path computation provides traffic optimization that is hard to implement with distributed TE.
:::

此外，控制器能收集**端到端跨域**拓扑、集中算路，拿到最优的端到端跨域路径。所以控制器集中算路能做到分布式 TE 很难做到的流量优化。

:::en
SR-TE not only solves the scalability problem of traditional RSVP-TE but also meets the requirements of the SDN architecture, helping to further the development of TE technologies and the application of SDN.
:::

SR-TE 既解决了传统 RSVP-TE 的扩展性问题，也符合 SDN 架构的要求，推动了 TE 技术与 SDN 应用的发展。

```text
图 18-4：集中式 SR-TE 架构（原书 Figure 4.2 重绘）

  ┌──────────────── 控制器（大脑）─────────────────┐
  │ 1. 信息收集   BGP-LS 收拓扑 / TE / SR ──► TEDB │
  │ 2. 集中算路   接收算路请求 → 全局约束算出路径   │
  │ 3. 信令       把结果下发（PCEP 或 BGP SRv6 Policy）│
  └──────────┬───────────────────────▲────────────┘
             │ 下发路径              │ 上报信息
  ┌──────────▼───────────────────────┴────────────┐
  │ 网络设备（头端）                               │
  │ 1. 信息通告：IGP 扩展（拓扑 + TE + SR 信息）   │
  │ 2. 信息上报：BGP-LS 上报上述信息               │
  │ 3. 信令：向控制器请求算路 / 接收结果           │
  │ 4. 报文转发：按源路由机制走（段列表在包里）    │
  └────────────────────────────────────────────────┘
```

:::en
The controller can use protocol extensions such as BGP-LS to collect network topology, TE, and SR information in order to establish a global TEDB.
:::

控制器可以用 BGP-LS 之类的协议扩展收集网络拓扑、TE 与 SR 信息，建立**全局 TEDB**。

:::en
Typically, the controller and network devices exchange signaling messages through PCEP or BGP SRv6 Policy extensions.
:::

控制器与设备之间的信令，通常走 **PCEP** 或 **BGP 的 SRv6 Policy 扩展**。

这两个协议的取舍不是技术优劣，而是**推送/拉取模型的差异**：BGP 天然是 Push（RR 把路由推给对等体），PCEP 是 Pull（客户端请求、服务器回结果）。所以"按需建路"这类场景用 BGP 会别扭，而"控制器统一算、统一下发"用 BGP 更顺。这一点原书作者在 18.10 里有更尖锐的看法。

## 18.2 BGP-LS：控制器怎么看到全网

### 18.2.1 为什么不能用 IGP 邻居

:::en
To compute TE paths, a controller needs information regarding network-wide topology and its TE and SR attributes. A simple method is to add the controller to the IGP topology as a common routing device so that the controller can collect network topology information by listening for IGP flooding.
:::

控制器要算 TE 路径，就得有**全网拓扑及其 TE、SR 属性**。最简单的办法是把控制器当成一台普通路由设备加进 IGP，靠听 IGP 泛洪来收集拓扑。

:::en
This method requires the controller to establish an IGP neighbor relationship with at least one routing device in each IGP area and is feasible for a small-scale network with only one or a small number of IGP areas. If this method is applied to a network with a large number of IGP areas, the controller needs to maintain a large number of IGP neighbor relationships, posing challenges to scalability. In addition, an IGP does not support multi-hop connections. If an IGP is used to collect network topology information, single-hop IGP neighbor relationships need to be established and tunnels have to be established between the controller and network nodes.
:::

这个办法要求控制器**在每个 IGP 区域至少和一台设备建邻居**。只有一两个区域的小网还行；区域一多，控制器要维护大量 IGP 邻居，扩展性就成了问题。而且 **IGP 不支持多跳连接**：用 IGP 收拓扑就得建单跳邻居、在控制器与网络节点之间拉隧道，部署复杂度更高。

把这三个限制换算成工程账：

| 限制 | 后果 | 缓解手段 |
|---|---|---|
| 每区域至少一个邻居 | N 个区域 = N 个邻居（+ 备份 = 2N） | 每区域一台 BGP-LS 发言人 |
| 不支持多跳 | 需要拉隧道或用直连链路 | BGP over TCP，天然多跳 |
| 拓扑变化靠泛洪 | 控制器跟着全量 SPF，CPU 浪费 | BGP-LS 只上报增量 NLRI |

:::en
To address this issue, BGP-LS is introduced for a controller to collect network topology information efficiently. BGP-LS has inherited many advantages of BGP, such as reliable transmission over TCP, good scalability with Route Reflectors (RRs), and flexible control using policies. Therefore, BGP-LS has become the main protocol used by the SDN controller to collect network topology information.
:::

为解决这个问题，引入了 **BGP-LS** 让控制器高效收拓扑。BGP-LS 继承了 BGP 的许多优点：**TCP 可靠传输、借助 RR 的扩展性、策略灵活控制**。因此 BGP-LS 成为 SDN 控制器收集网络拓扑的主流协议。

:::en
Only one routing device in each IGP area needs to run BGP-LS and directly establish a BGP-LS peer relationship with a consumer. A routing device can also establish a BGP-LS peer relationship with a centralized BGP speaker, which then establishes a BGP-LS peer relationship with the consumer.
:::

**每个 IGP 区域只需要一台设备跑 BGP-LS**，与 consumer（控制器）建 BGP-LS 对等体。设备也可以先和一台集中 BGP 发言人建对等体，再由它与 consumer 建。

```text
图 18-5：BGP-LS 典型架构（原书 Figure 4.3 重绘）

  区域 1                      区域 2                     区域 3
  ┌──────────────┐           ┌──────────────┐          ┌──────────────┐
  │  R1 ── R2    │           │  R5 ── R6    │          │  R9 ── R10   │
  │   │          │           │   │          │          │   │          │
  │  [R3]◄─BGP-LS│           │  [R7]        │          │  [R11]       │
  └───┬──────────┘           └───┬──────────┘          └───┬──────────┘
      │  BGP-LS 单跳             │                         │
      └──────────┬───────────────┴─────────────────────────┘
                 ▼
        ┌─────────────────┐   BGP-LS   ┌──────────────┐
        │ 集中 BGP 发言人 │◄──────────►│  consumer    │
        │ （RR 角色）     │  一条连接  │  （控制器）  │
        └─────────────────┘            └──────────────┘

  [ ] 表示该区域内跑 BGP-LS 的那一台设备，其余设备只在 IGP 里扩散。
```

这张图的关键是"**一条连接收全网**"：控制器只和 RR 建一条 BGP-LS 会话，就能拿到所有区域的拓扑。**别把 BGP-LS 会话建到每台 PE 上**，那是把 IGP 邻居的复杂度原封不动搬到 BGP 上。

:::en
On the basis of BGP, BGP-LS introduces a series of new Network Layer Reachability Information (NLRI) attributes to carry information about links, nodes, and IPv4/IPv6 prefixes. Such new NLRIs are called Link-State NLRIs.
:::

BGP-LS 在 BGP 基础上引入了一组新的 **NLRI**，用来携带链路、节点、IPv4/IPv6 前缀的信息，称为 **Link-State NLRI**。

:::en
Before supporting SR, BGP-LS defines four types of Link-State NLRIs: Node NLRI, Link NLRI, IPv4 Topology Prefix NLRI, IPv6 Topology Prefix NLRI. In addition, BGP-LS defines attributes corresponding to the preceding NLRIs to carry link, node, and IPv4/IPv6 prefix parameters.
:::

在支持 SR 之前，BGP-LS 定义了四类 Link-State NLRI：**Node NLRI、Link NLRI、IPv4 拓扑前缀 NLRI、IPv6 拓扑前缀 NLRI**。另外还定义了与这些 NLRI 对应的属性，用来携带链路、节点、前缀参数。

原文 Table 4.1 把四类 NLRI 与其属性的对应关系列全了，摘成一张便于排障的表：

| NLRI | 由哪些部分唯一确定 | 携带的属性 | 排障时看什么 |
|---|---|---|---|
| Node | Protocol-ID、Identifier、Local Node Descriptor（AS / BGP-LS ID / OSPF Area-ID / IGP Router-ID） | Node Attribute：MT-ID、Node Flag Bits、Node Name、IPv6 Router-ID… | 节点是否上报、Node Name 与现网是否对得上 |
| Link | Protocol-ID、Identifier、Local/Remote Node Descriptor、Link Descriptor（Link Local/Remote ID、IPv4 接口地址） | Link Attribute：IPv6 接口/邻居地址、Admin Group(Color)、TE 度量、带宽 | **Admin Group 与 delay 度量**是算路的分水岭 |
| IPv4/IPv6 Prefix | Protocol-ID、Identifier、Local Node Descriptor、Prefix Descriptor（MT-ID、OSPF Route Type、IP Reachability） | Prefix Attribute：IGP Flags、Route Tag、Prefix Metric… | locator 前缀是否带正确 Metric |

三张"同一份数据"的东西经常被搞混，先分清：

| 概念 | 谁产生 | 谁消费 | 装的是什么 |
|---|---|---|---|
| IGP 的 TE 扩展（IS-IS TLV 22 / OSPF LSA 10） | 每台路由器 | 区域内的路由器 | 链路带宽、TE 度量、affinity |
| TEDB | 本地 SPF 结果 | 本地 CSPF 或控制器 | 上面那些 + 拓扑 |
| BGP-LS | 每区域一台发言人 | 控制器 | **把 TEDB 序列化成 BGP NLRI 发出去** |

也就是说：**BGP-LS 不是新协议，是 TEDB 的搬运工**。它不改变语义，只改变可达范围——从"区域内泛洪"变成"跨域推送"。

### 18.2.2 SRv6 的扩展：SID NLRI 与属性 TLV

:::en
To support SR, the IETF has defined a series of extensions for the Node, Link, and Prefix Attributes. One such example is the BGP-LS extensions for supporting SR-MPLS. Since the focus of this book is SRv6, in the following section, we describe the extensions added to BGP-LS for collecting SRv6 information.
:::

为支持 SR，IETF 为 Node、Link、Prefix 属性定义了一系列扩展，例如支持 SR-MPLS 的 BGP-LS 扩展。本书聚焦 SRv6，下面只讲为收集 SRv6 信息而新增的扩展。

:::en
First, BGP-LS defines SRv6 SID NLRI, which is used to advertise the network-layer reachability information of SRv6 SIDs. The NLRI contains the following information: Protocol-ID, Local Node Descriptors, and SRv6 SID Descriptors — currently defined as the SRv6 SID Information TLV.
:::

首先，BGP-LS 定义了 **SRv6 SID NLRI**，用于通告 SRv6 SID 的网络层可达信息。该 NLRI 包含：**Protocol-ID、本地节点描述符、SRv6 SID 描述符**（当前就把 SRv6 SID Information TLV 定义为描述符）。

:::en
Second, BGP-LS defines SRv6 SID NLRI attributes to carry SRv6 SID reachability information. Currently, the following three related attributes are defined: SRv6 Endpoint Function, which carries the endpoint function information (such as End.DT4) associated with a SID NLRI; SRv6 BGP Peer Node SID, which carries the BGP peer information associated with a SID NLRI; and SRv6 SID Structure, which describes the length of each part of an SRv6 SID.
:::

其次，还定义了若干 SRv6 SID NLRI 属性来携带可达信息，当前有三个：**SRv6 Endpoint Function**（携带 SID 关联的端点行为，如 `End.DT4`）、**SRv6 BGP Peer Node SID**（携带 SID 关联的 BGP 对等体信息）、**SRv6 SID Structure**（描述 SID 各部分的长度）。

:::en
Last but not least, BGP-LS extends the existing attributes by defining a series of attribute TLVs. Node Attribute extensions include SRv6 Capabilities, which advertises the SRv6 capabilities supported by a node, and SRv6 Node MSD Types, which advertises an SRv6-capable node's capabilities of processing SRv6 SID depths of different types. Link Attribute extensions include SRv6 End.X SID, which advertises the End.X SIDs associated with a P2P or P2MP link, and SRv6 LAN End.X SID, which advertises End.X SIDs associated with broadcast links. Prefix Attribute extension includes SRv6 Locator, which advertises the SRv6 locator of a node.
:::

最后，BGP-LS 通过定义一系列属性 TLV 扩展既有属性：

- **Node 属性扩展**：`SRv6 Capabilities`（节点支持的 SRv6 能力）、`SRv6 Node MSD Types`（节点对各类 SID 深度的处理能力）；
- **Link 属性扩展**：`SRv6 End.X SID`（P2P/P2MP 链路关联的 End.X SID）、`SRv6 LAN End.X SID`（广播网链路的 End.X SID）；
- **Prefix 属性扩展**：`SRv6 Locator`（节点 locator）。

```text
图 18-6：SRv6 的 BGP-LS 对象关系（原书 Figure 4.4–4.13 归并重绘）

  SRv6 SID NLRI（一条 SID 一条路由）
  ┌────────────────────────────────────────────┐
  │ Protocol-ID │ Local Node Descr. │ SID Descr.│
  │                    │               │        │
  │                    │        SRv6 SID Info TLV
  │                    │        ┌──────────────┐ │
  │                    │        │ SID (16 octet)│ │
  │                    │        └──────────────┘ │
  └────────────────────┴────────────────────────┘
                       │ 作为该 NLRI 的属性随车
        ┌──────────────┼──────────────┬───────────────────┐
        ▼              ▼              ▼                   ▼
  Endpoint Function  BGP Peer Node  SID Structure    （行为相关扩展）
  行为码 + Algorithm    SID TLV      LB/LN/Fun/Arg
   (End.DT4 等)      B/S/P 标志+weight

  与 Node/Link/Prefix NLRI 并列的另外三类：
    Node NLRI   + SRv6 Capabilities + Node/Link MSD
    Link NLRI   + SRv6 End.X SID + SRv6 LAN End.X SID
    Prefix NLRI + SRv6 Locator（含 D 位 / A 位 / Algorithm / Metric）
```

逐个说清楚每个 TLV 在排障时的用处，比背字段值更有价值：

| TLV | 挂在谁身上 | 携带什么 | 排障价值 |
|---|---|---|---|
| **SRv6 SID NLRI** | NLRI 本体 | 单条 SID 的可达性 | 控制器"看不到 SID 列表"，九成是这里没上来 |
| SRv6 SID Information | NLRI 子 TLV | 16 octet 的 SID 值 | SID 值与设备 `show segment-routing srv6 sid all` 对不上即异常 |
| **SRv6 Endpoint Function** | SID 属性 | 行为码 + Algorithm（0 SPF / 1 Strict SPF / 128–255 Flex-Algo） | **行为码错 → 控制器以为这台设备不能做 `End.DT4`**；Algo 错 → 算到错算法的拓扑上 |
| SRv6 BGP Peer Node SID | SID 属性 | B/S/P 标志、Weight、Peer AS、Peer BGP ID | EPE / BGP 出口工程；`P` 位置位表示重启不变，利于稳定编程 |
| **SRv6 SID Structure** | SID 属性 | LB / LN / Fun / Arg 各占多少 bit | **长度错 → 控制器按错误位长拼 SID**，最隐蔽的一类故障 |
| SRv6 Capabilities | Node 属性 | O-flag（OAM 能力） | O 位不支持 → 第 9 章的探测可能不通 |
| Node / Link MSD | Node / Link 属性 | Max Seg Left、Max End Pop、Max H.Insert、Max H.Encaps、Max End D | **MSD 小 → 控制器必须压段数**，否则头端封装失败（见 18.7） |
| SRv6 End.X SID | Link 属性 | 行为码、B/S/P 标志、Algorithm、Weight、SID | 显式路径"必须走某条链路"靠它 |
| SRv6 LAN End.X SID | Link 属性 | 上面那些 + 邻居 IS-IS System-ID 或 OSPFv3 Router-ID | 广播网（如 IXP 交换网）里区分邻居 |
| **SRv6 Locator** | Prefix 属性 | Flags（**D 位**泄漏防环、**A 位** anycast）、Algorithm、Metric | D 位在 L1↔L2 泄漏时必须置位（第 5 章）；A 位错 → 多归模型算错 |

:::en
Based on these extensions, a controller can collect networkwide SRv6 information in addition to networkwide topology and TE information. The controller can then make use of the information to compute networkwide TE paths.
:::

有了这些扩展，控制器除了全网拓扑与 TE 信息，还能收集**全网 SRv6 信息**，进而算出全网 TE 路径。

一个实操提醒：**MSD 是控制器算路的硬约束，不是参考值**。如果头端 `Max H.Encaps = 6`，控制器给一条 8 段的显式路径，头端要么拒绝、要么截断——两种结果都表现为"策略建起来了但流量不走"，属于最难查的一类故障。设计期就要把头端型号的 MSD 写进算路约束。

## 18.3 PCEP：把算好的路径送下去

### 18.3.1 有状态 PCE 与七步交互

:::en
The Path Computation Element (PCE) architecture was first proposed to solve the path computation problem on large-scale networks with multiple areas. We can use this architecture to compute inter-domain paths for TE, and it consists of the following three parts: PCE, Path Computation Client (PCC), and PCEP.
:::

**PCE**（路径计算单元）架构最初是为了解决多区域大网的算路问题提出的，可用于计算跨域 TE 路径。它由三部分组成：**PCE**、**PCC**（路径计算客户端）、**PCEP**。

:::en
PCEP: a protocol that runs over TCP using the port number 4189 and is used for communication between a PCC and PCE. A PCEP message consists of a common header and a collection of either mandatory or optional objects for carrying TE path computation requests and path computation results.
:::

PCEP 是运行在 **TCP 4189** 端口上的协议，用于 PCC 与 PCE 之间通信。一条 PCEP 消息由公共头加一组必需或可选对象组成，用来携带 TE 算路请求与算路结果。

:::en
Traditional PCEs adopt centralized path computation, and the PCEP of the initial version defines RSVP-TE-oriented stateless PCE protocol extensions and interaction processes. Stateless PCEs independently compute paths based on the TEDB, without needing to maintain any of the previously computed paths. That said, stateless PCEs do not have information about the currently active TE paths and therefore cannot perform any type of re-optimization on the active paths.
:::

传统 PCE 采用集中算路，初版 PCEP 定义的是**面向 RSVP-TE 的无状态**扩展与交互流程。无状态 PCE 只按 TEDB 独立算路，**不维护任何已算出的路径**。因此它不知道当前有哪些活跃 TE 路径，也就**无法对活跃路径做任何再优化**。

:::en
With the development of SDN and emergence of SR, PCEP now includes stateful PCE and relevant extensions for SR, which effectively support centralized SR-TE functions.
:::

随着 SDN 发展与 SR 出现，PCEP 增加了**有状态 PCE** 与 SR 相关扩展，从而有效支撑集中式 SR-TE。

:::en
Stateful PCE: A stateful PCE maintains a TEDB that is strictly synchronized with a network. The TEDB includes not only the IGP link states, TE information, and TE path information, but also reserved resources used by TE paths on the network. Comparatively speaking, stateful PCEs can compute better network paths than stateless PCEs by performing reliable state synchronization with networks.
:::

**有状态 PCE** 维护一个与网络严格同步的 TEDB，里面不只有 IGP 链路状态、TE 信息、TE 路径信息，还有 **TE 路径占用的预留资源**。靠可靠的状态同步，有状态 PCE 算出的路径比无状态更好。

:::en
PCE extensions for SR: SR has advantages over RSVP-TE in terms of scalability due to the fact that it provides the same capability of explicitly specifying paths, but without needing to maintain per-flow states on transit nodes. On the other hand, as SR does not maintain states on transit nodes, it lacks the capability of computing paths based on the bandwidth usage on the ingress. That is where PCE-based SR comes into play by being able to address this issue. To put it more precisely, as a PCE stores the topology, TE, path, and reserved resource information of the entire network, it can compute paths based on networkwide resources, ultimately optimizing resources on the entire network.
:::

**SR 的 PCE 扩展**：SR 的可扩展性优于 RSVP-TE，因为它同样能显式指定路径，却**不需要在中间节点维护 per-flow 状态**。但反过来说，SR 在中间节点不存状态，就**失去了"按带宽占用算路"的能力**——这正好是 PCE 补上的位置。更准确地说：PCE 存着全网的拓扑、TE、路径与预留资源信息，因此能**按全网资源算路**，最终做全网资源优化。

这段是整章的"结构性论证"，值得停下来想一下：

| 谁 | 强在哪 | 弱在哪 | 谁补 |
|---|---|---|---|
| RSVP-TE | 每跳知道带宽占用，能预留、能抢占 | 状态随规模爆炸 | — |
| SR / SRv6 | 只头端有状态，规模好 | **不知道带宽占用**，无法预留/抢占 | PCE（有状态） |
| PCE + SRv6 | 全局算路 + 无状态转发 | 依赖控制器可用性 | SBFD / 头端检测（18.8） |

```text
图 18-7：有状态 PCE 算路七步（原书 Figure 4.14 重绘）

  PCC（头端 PE1）                                PCE（控制器）
       │                                              │
  ① 配置 SRv6 Policy（NETCONF/CLI）                   │
       │                                              │
  ② Open ───────────────────────────────────────────►│ 协商能力
       │◄───────────────────────────────────────────  │ （含 PST=2）
       │                                              │
  ③ PCRpt（Delegate=1 + 策略约束/属性）──────────────►│ 委托控制权
       │                                              │
       │                                    ④ 按委托标志、
       │                                      约束、属性算路
       │                                              │
  ⑤ PCUpd（ERO 里带 SRv6 段列表）◄────────────────────│
       │                                              │
  ⑥ 安装目标路径                                     │
       │                                              │
  ⑦ PCRpt（RRO=实际路径，ERO=控制器算的路径）────────►│ 状态回报
       │                                              │
```

七步里最容易被忽略的是 **⑦**：PCC 回报的 RRO 是"我**实际**在用哪条路径"，ERO 是"控制器**希望**我用哪条"。两者不一致时，说明头端做了本地调整（例如某 SID 不可达被剔除）——**这个不一致就是排障的第一现场**。

:::en
Stateful PCEs work in either passive or active mode: Passive stateful PCE performs path computation and optimization based on the LSP states learned from a PCC, which it is synchronized with, and does not update the LSP states proactively. Active stateful PCE can proactively deliver path suggestions to a network to update paths. For example, a PCC can delegate its control over LSPs to an active stateful PCE through the LSP delegation mechanism.
:::

有状态 PCE 有两种工作模式：**被动模式**按从 PCC 学来的 LSP 状态算路与优化，不会主动更新路径；**主动模式**可以主动把路径建议下发给网络去更新路径——例如 PCC 通过 **LSP 委托（delegation）**机制把 LSP 控制权交给主动有状态 PCE，PCE 就能改 PCC 的 LSP 参数。

### 18.3.2 SRv6 的三个扩展

:::en
These extensions include three parts: the new type PATH-SETUP-TYPE for SRv6, the SRv6 PCE Capability sub-TLV used to advertise SRv6 capabilities, and the SRv6 ERO and SRv6 RRO subobjects used to carry SRv6 SIDs of a specific SRv6 path.
:::

这些扩展包括三部分：为 SRv6 新增的 **PATH-SETUP-TYPE**、用于通告 SRv6 能力的 **SRv6 PCE Capability 子 TLV**、以及用来携带具体 SRv6 路径上 SID 的 **SRv6-ERO 与 SRv6-RRO 子对象**。

:::en
To support SRv6, PCEP introduces a new path setup type for identifying SRv6 paths, and its type value is 2. PCEP goes a step further by also defining the SRv6 PCE Capability sub-TLV for describing SRv6 capabilities in detail.
:::

为支持 SRv6，PCEP 引入了新的**路径建立类型（PST）**来标识 SRv6 路径，**类型值为 2**。PCEP 还进一步定义了 **SRv6 PCE Capability 子 TLV**，用来细描述 SRv6 能力。

| PST 值 | 含义 | 备注 |
|---|---|---|
| 0 | RSVP-TE | 传统 |
| 1 | Segment Routing | SR-MPLS |
| **2** | **SRv6** | 本章；协商不上 = 控制器不会给 SRv6 算路 |

:::en
During capability advertisement, if the PATH-SETUP-TYPE-CAPABILITIES TLV carries a PST with the value of 2, SRv6 path setup is supported. In this case, the PATH-SETUP-TYPE-CAPABILITIES TLV must carry an SRv6 PCE Capability sub-TLV to describe the SRv6 capability in detail.
:::

能力通告时，如果 `PATH-SETUP-TYPE-CAPABILITIES` TLV 里带 **PST=2**，就表示支持 SRv6 路径建立。此时该 TLV **必须**再带一个 SRv6 PCE Capability 子 TLV，把 SRv6 能力描述清楚。

选路请求也一样：**SRP（Stateful PCE Request Parameters）对象里要带 `PATH-SETUP-TYPE` TLV 且 PST=2**，否则 PCE 会按 SR-MPLS 去算，返回的 ERO 里是 MPLS 标签而不是 128 bit SID。

:::en
An SRv6-ERO subobject can be carried in a PCRep, PCInitiate, PCUpd, or PCRpt message. With the aim of carrying an SRv6 SID and NAI, or either one of them, PCEP defines a new subobject called SRv6-ERO Subobject. An NAI is associated with an SRv6 SID, which means the NAI can be resolved into an SRv6 SID.
:::

SRv6-ERO 子对象可以出现在 **PCRep、PCInitiate、PCUpd、PCRpt** 消息里。为了携带 SRv6 SID 与/或 **NAI**（Node or Adjacency Identifier，节点或邻接标识），PCEP 定义了新子对象 **SRv6-ERO**。NAI 与 SRv6 SID 相关联，意味着 **NAI 可以被解析成 SRv6 SID**。

NAI 的价值在于"**算路算的是抽象节点，落地靠头端解析**"：

| NT 值 | NAI 是什么 | 典型用途 |
|---|---|---|
| 0 | 不含 NAI | 只给 SID |
| 2 | 节点关联的 IPv6 地址 | 控制器只给"必须经过 R7" |
| 4 | End.X SID 关联链路的全球 IPv6 地址对 | "必须走 R7→R8 这条链路" |
| 6 | 同上，但用链路本地地址对 | 节省全球地址 |

对应两个标志位也很关键：**F 位置位 = 不含 NAI 值；S 位置位 = 不含 SID 值**。两者都置位就只剩"行为码 + 空对象"，实际部署中几乎不出现。

:::en
An RRO is used by a PCC to report the actual path of an LSP when reporting LSP states. In SRv6, this object indicates the SID list of the actual SRv6 path that a PCC uses. To carry SRv6 SID information, PCEP defines the SRv6-RRO subobject. Note that the SRv6-RRO and SRv6-ERO subobjects share the same format, but the former does not include the L field.
:::

RRO 用于 PCC 回报 LSP 状态时描述 **LSP 的实际路径**。在 SRv6 里，它表示 PCC 实际使用的 SRv6 路径的 SID 列表。为此 PCEP 定义了 **SRv6-RRO 子对象**。注意 SRv6-RRO 与 SRv6-ERO 格式相同，**只是前者没有 L（loose）字段**。

顺带说清 ERO 里 `Function Code` 字段的定位：**它不影响压给报文的 SRH，只用于可维护性**。所以看到 ERO 里 Function Code 与实际行为码不一致时，先别急着排业务——它可能只是控制器的展示字段。

:::en
Put briefly, based on the PCEP extensions, a PCE can receive an SRv6 TE path computation request from a PCC, compute the target path, and return the computation result to the PCC. The combination of the PCE's centralized path computation capability and SRv6 ingress's explicit path programming capability enables TE with flexible controllability, global optimization, and enhanced scalability.
:::

一句话：有了这些 PCEP 扩展，PCE 能收到 PCC 的 SRv6 TE 算路请求、算出目标路径、把结果回给 PCC。**PCE 的集中算路能力 + SRv6 头端的显式路径编程能力**，合起来实现了可控性强、全局优化、扩展性好的 TE。

## 18.4 SRv6 Policy 模型：Key、候选路径、段列表

:::en
SRv6 Policy leverages the source routing mechanism of SR to instruct packet forwarding based on an ordered list of segments encapsulated by the source node. SRv6 uses programmable 128-bit IPv6 addresses to provide diverse network functions, which are expressed using SRv6 instructions that can identify not only forwarding paths but also Value-Added Services (VASs) such as firewalls, application acceleration, and user gateways.
:::

SRv6 Policy 利用 SR 的源路由机制，由源节点封装一个**有序段列表**来指导转发。SRv6 用可编程的 128 bit IPv6 地址提供多样化网络功能，这些功能由 SRv6 指令表达——**既能标识转发路径，也能标识增值服务（VAS）**，如防火墙、应用加速、用户网关。

:::en
Another stand-out feature of SRv6 is its excellent extensibility. This is clearly reflected in the fact that, to support a new network function, all that is needed is to define a new instruction, without changing the protocol mechanism or deployment. This advantage significantly shortens the delivery period of innovative network services.
:::

SRv6 另一个突出特性是**极好的可扩展性**：要支持一个新网络功能，**只需定义一条新指令**，不用改协议机制、也不用改部署，这大幅缩短了创新业务的交付周期。

这两句话把 TE 与第 11 章（服务编程）连起来了：**同一条段列表里可以既有"路点"又有"服务"**。所以 SRv6 TE 的段列表不是单纯路径，而是"路径 + 途经处理"的混合程序——Bell SP 的生产案例（第 16 章）就是把 DDoS 清洗 SID 与 VRF 9 的 VPN SID 串在两条 uSID 里。

:::en
To implement SR-TE, the industry put forward SR Policy, a framework that supports both SR-MPLS and SRv6. Focusing on how to use SR Policies to implement SRv6 TE, this section includes the following: SR Policy model definition, control-plane path computation, data-plane forwarding, and protection measures in failure scenarios. The SR Policies used to implement SRv6 TE are called SRv6 Policies in this book.
:::

为实现 SR-TE，业界提出了 **SR Policy** 框架，同时支持 SR-MPLS 与 SRv6。聚焦如何用 SR Policy 实现 SRv6 TE，本节包括：**模型定义、控制面算路、数据面转发、故障场景保护**。书中把用于实现 SRv6 TE 的 SR Policy 称为 **SRv6 Policy**。

:::en
The SRv6 Policy model uses the following three tuple as the keys to uniquely identify an SRv6 Policy: Headend, Color, Endpoint. Headend is the ingress node of an SRv6 Policy, which can steer traffic into the corresponding SRv6 Policy. Color is an attribute used to identify different SRv6 Policies with specified headends and endpoints. Endpoint is the destination of an SRv6 Policy.
:::

模型用**三元组做 Key** 唯一标识一条策略：**Headend（头端）、Color（颜色）、Endpoint（端点）**。Headend 是策略的入节点，负责把流量引进去；Color 在"同头端、同端点"的多条策略间做区分；Endpoint 是策略目的地。

:::en
It can be associated with a series of service attributes, such as low latency and high bandwidth, and as such can be considered a service requirement template ID. Because no unified coding rule is defined, color values need to be allocated by administrators. For example, an administrator can allocate a color value of 100 to an SRv6 Policy whose end-to-end latency requirement is less than 10 ms. The color attribute enables the association between services and SRv6 Policies.
:::

Color 可关联一系列业务属性（低时延、大带宽等），因此**可看作"业务需求模板"的编号**。由于**没有统一定义编码规则，Color 取值必须由管理员规划**。例如把"端到端时延小于 10 ms"的策略 color 定为 100。Color 属性正是**业务与策略之间的挂钩**。

这里有个必须提前做的规划动作，否则后面全是坑：

| Color 值 | 语义 | 谁打这个标 | 谁消费 |
|---|---|---|---|
| 100 | 低时延（< 10 ms） | 尾端 PE 在 BGP 路由上打 `extcommunity color 100` | 头端 PE 递归到 color 100 的策略 |
| 123 | 通用 / 大带宽 | 同上 | 同上 |
| 200 | 视频类（可绕行） | 同上 | 同上 |

**Color 没有标准编码**，所以它天然是"跨部门约定"：规划文档不写清楚，两个团队各定一套 100，就会在割接当天出现"业务走错隧道但没人报错"。

:::en
All the SRv6 Policies delivered to a specific headend have the same headend value. For this reason, the specific headend can use the <Color, Endpoint> tuple to uniquely identify an SRv6 Policy, thereby steering traffic into the SRv6 Policy.
:::

下发到某个头端的策略 Headend 值都相同。因此**头端只需用 `<Color, Endpoint>` 二元组**就能唯一确定一条策略，把流量引进去。

```text
图 18-8：SRv6 Policy 三层模型（原书 Figure 4.20 重绘）

  Key: <Headend = PE1, Color = 100, Endpoint = fc00:0:2::1>
  ┌────────────────────────────────────────────────────────────┐
  │  SRv6 Policy                                               │
  │   ├── 候选路径 A   pref 200  <Protocol-origin=BGP,         │
  │   │   │                      Originator=RR-1, Discr=1>     │
  │   │   ├── 段列表 A1  weight 2  路径 A（低时延）            │
  │   │   └── 段列表 A2  weight 1  路径 A'（同算法另一条）      │
  │   │                                                        │
  │   └── 候选路径 B   pref 100  <PCEP, 控制器, 7>              │
  │       └── 段列表 B1  weight 1  路径 B（绕行）              │
  │                                                            │
  │  BSID: fc00:0:1:d000::100  ←── 指向"这条策略"的接口        │
  └────────────────────────────────────────────────────────────┘
        ▲ 选中的是 pref 最高的候选路径 A（200 > 100）
        ▲ 候选路径 A 内两条段列表按 2:1 做 UCMP
```

:::en
A candidate path is the basic unit for delivering an SRv6 Policy path to the headend through protocols such as BGP SRv6 Policy and PCEP. Different candidate paths can be delivered using different protocols. An SRv6 Policy may be associated with multiple candidate paths, each of which has a preference. If this is the case, the SRv6 Policy makes the candidate path with the highest preference the primary one.
:::

**候选路径**是通过 BGP SRv6 Policy、PCEP 等把路径下发给头端的**基本单元**。不同候选路径可用不同协议下发。一条策略可关联多条候选路径，各带 preference，**策略选 preference 最高的做主**。

:::en
Each candidate path of an SRv6 Policy is uniquely identified using the tuple <Protocol-origin, Originator, Discriminator>, where Protocol-origin indicates the protocol or component through which the candidate path is generated, Originator indicates the node that generates the candidate path, and Discriminator helps distinguish candidate paths with the same <Protocol-origin, Originator> tuple.
:::

每条候选路径用 **`<Protocol-origin, Originator, Discriminator>`** 唯一标识：前者表示由哪个协议或组件产生，Originator 表示哪台设备产生，Discriminator 区分**同协议同产生者**的多条候选路径。

:::en
A segment list identifies a source-routed path through which traffic is sent to the endpoint of the involved SRv6 Policy. One candidate path can be associated with multiple segment lists, each of which is allocated a weight to implement weighted load balancing using Equal-Cost Multiple Path (ECMP) or Unequal-Cost Multiple Path (UCMP).
:::

**段列表**标识一条源路由路径，流量沿它送到策略端点。一条候选路径可关联**多条段列表**，每条分配 weight，用 **ECMP 或 UCMP** 做加权负载分担。

三层模型对应三件不同的事，混淆是排障最常见的误区：

| 层 | 变更频率 | 谁能改 | 改错的后果 |
|---|---|---|---|
| Key（Headend/Color/Endpoint） | 极低 | 规划部门 | 等于新建一条策略，旧策略残留 |
| 候选路径（含 preference） | 中（控制器算路会动） | 控制器 / 人工 | preference 写反 → 主备颠倒 |
| 段列表（含 weight） | 高（拓扑一变就变） | 控制器自动 | weight 全相同 → 退化成等价 ECMP |

:::en
Furthermore, binding SIDs can be allocated to SRv6 Policies. As basic SR instructions, binding SIDs are used to identify SRv6 Policies and provide diverse functions including traffic steering and tunnel stitching. Packets carrying a binding SID will be steered into the corresponding SRv6 Policy. From this perspective, binding SIDs can be regarded as interfaces that are invoked for SRv6 Policy selection.
:::

此外策略可分配 **BSID**。作为基础 SR 指令，BSID 用于标识策略并提供**引流、隧道拼接**等功能。**目的地址为 BSID 的报文会被引进对应策略**。从这个角度看，**BSID 就是"选择策略"时被调用的接口**。

:::en
Simply put, if we consider SRv6 Policy as a network service, then the binding SID is the interface used to access the service. The SRv6 Policy model is designed to work in publish-subscribe mode, which means that network services are subscribed to as needed and then the network provides service interfaces accordingly. Since the binding SID is considered as the interface, it must meet interface requirements, which include: independence, reliability, and stability.
:::

简单说：把策略看成一项网络服务，**BSID 就是访问该服务的接口**。模型按**发布-订阅**方式设计：有需求才订阅，网络按需提供服务接口。既然 BSID 是接口，就必须满足三条要求：**独立性、可靠性、稳定性**。

:::en
Independence: Any service can invoke such an interface without considering implementation details. Because all implementation details are encapsulated inside SRv6 Policies, services only need to be aware of the interfaces when using SRv6 Policies.
:::

**独立性**：任何业务都能调用这个接口，不必关心实现细节——因为细节全封装在策略内部，业务**只需知道接口**。

:::en
Reliability: Once released, the interface must be responsible for the contract between the application and network service. This means that SRv6 Policy must guarantee the promised service in the contract no matter how many applications invoke it. This requires SRv6 Policies to support auto scaling of network resources.
:::

**可靠性**：接口一旦发布，就要对"应用与网络服务之间的契约"负责。即**无论多少应用调用，策略都必须兑现契约承诺的服务**，这要求策略支持资源自动伸缩。

:::en
Stability: Interfaces must be stable. To achieve this, the binding SID of an SRv6 Policy must be kept unchanged throughout the lifecycle of the SRv6 Policy, regardless of network topology, service, and path changes.
:::

**稳定性**：接口必须稳定。为此 **BSID 必须在策略整个生命周期内保持不变**，不管拓扑、业务、路径怎么变。

"三性"落到配置上就一句话：**BSID 用静态池，不要用动态池**。

```text
! PE1：为需要长期被引用的策略预留静态 BSID 段
segment-routing
 srv6
  locators
   locator Locator0
    micro-segment behavior unode psp-usd
    prefix fc00:0:1::/48
    static-sid fc00:0:1:d000::/64     ! 静态：可规划、重启不变
    dynamic-sid fc00:0:1:e000::/64    ! 动态：控制器临时分配/上报用
```

:::en
An SRv6 Policy delivered by a controller to a forwarder does not carry a binding SID. After receiving an SRv6 Policy, the forwarder randomly allocates a binding SID in the dynamic range of locators and then runs BGP-LS to report the state of the SRv6 Policy carrying the binding SID. In this way, the controller learns the binding SID of the SRv6 Policy and uses this information for SRv6 path programming.
:::

控制器下发给转发器的策略**不携带 BSID**。转发器收到后在 **locator 的动态范围内随机分配**一个 BSID，再通过 **BGP-LS 上报**带 BSID 的策略状态。这样控制器**反过来学到**这个 BSID，用于后续路径编程。

这条回路（下策略 → 头端分 BSID → BGP-LS 回报 → 控制器拿 BSID 拼路径）是"**隧道拼接**"的基础，也是 BSID 池必须留足的原因：每次重建都可能吃掉一个动态 BSID，池子不够就会出现"策略建不起来但没报错"。

## 18.5 三条算路的路子：手工 / 头端 / 集中式

:::en
The candidate paths of an SRv6 Policy can be generated using different methods, including manual configuration, headend computation, and centralized computation. The Protocol-origin and Originator fields can be used to distinguish the generation method of a candidate path.
:::

候选路径有三种生成方式：**手工配置、头端计算、集中式计算**。用 Protocol-origin 与 Originator 字段就能区分候选路径的来源。

### 18.5.1 手工配置

:::en
In manual configuration, a candidate path is manually planned and configured for an SRv6 Policy through the CLI or NETCONF. In manual configuration mode, the endpoint and color of the SRv6 Policy as well as the preference value and segment list of the candidate path must all be configured. Additionally, the preference value must be unique, and binding SIDs must be allocated within the static range of locators.
:::

手工配置模式下，通过 CLI 或 NETCONF **人工规划并配置**候选路径。此时必须把策略的 **endpoint、color** 与候选路径的 **preference、段列表**全配齐。此外 **preference 必须唯一**，**BSID 必须在 locator 静态范围内分配**。

```text
! PE1：手工显式路径 + 静态 BSID（IOS XR 风格，字段名以平台版本为准）
segment-routing
 traffic-eng
  srv6
   locator Locator0
  segment-lists
   segment-list SL-lowlat
    index 10 sid fc00:0:11:e002::       ! P1 的 End.X（P1→P2）
    index 20 sid fc00:0:12:e001::       ! P2 的 End.X（P2→PE2）
    index 30 sid fc00:0:2:e000::        ! PE2 的 End
  policies
   policy PE2-LOWLAT
    color 100 end-point ipv6 fc00:0:2::1
    binding-sid fc00:0:1:d000::100      ! 静态池内，写进文档
    candidate-paths
     preference 200
      explicit segment-list SL-lowlat
```

:::en
Manually configured paths cannot automatically adapt to network topology changes. That is, if a specified link or node fails, SRv6 Policy rerouting cannot be triggered, which leads to continuous traffic interruption. As such, generally, two disjoint paths need to be planned for a manually configured SRv6 Policy, with connectivity detection mechanisms employed to check path connectivity.
:::

手工路径**不能自动适应拓扑变化**。指定链路或节点一旦故障，**策略不会重路由**，业务持续中断。因此通常要为手工策略规划**两条互不相关的路径**，并配合连通性检测机制。

这段话要读出严重性：手工策略不是"少了个自动化"，而是**故障时完全不切**。段列表里只要有一个 SID 不可达，报文就在那一跳被丢——头端不会知道，因为没有信令。所以手工模式**必须配 SBFD**（18.8.1），这是硬要求。

### 18.5.2 头端计算

:::en
Headend computation is similar to RSVP-TE path computation. Specifically, the headend uses IGP link-state and TE information to form a TEDB; runs the CSPF algorithm to compute a qualified path according to constraints such as bandwidth, latency, Shared Risk Link Group (SRLG), and disjoint paths; and then installs the corresponding SRv6 Policy to guide traffic forwarding.
:::

头端计算类似 RSVP-TE 算路：头端用 IGP 链路状态与 TE 信息形成 TEDB，跑 CSPF 按**带宽、时延、SRLG、不相交路径**等约束算出合格路径，再安装对应策略指导转发。

:::en
Headend computation has the following restrictions: Due to the lack of cross-domain topology information, the headend can compute only paths within a single IGP domain, not those that span multiple IGP domains. Because SR transit nodes do not maintain the per-flow state, resource preemption and bandwidth reservation are not supported.
:::

头端计算有两条限制：**① 缺少跨域拓扑，只能算单个 IGP 域内的路径**；**② 因为 SR 中间节点不维护 per-flow 状态，不支持资源抢占与带宽预留**。

第 ② 条常被误读成"SRv6 不支持带宽"。准确说法是：**头端算路可以参考带宽余量，但不能"扣减"它**——没有预留就没有准入控制，多个头端各自按"当前余量"算路，会同时选中同一条链路。这正是集中式算路存在的根本理由（全网只有一个算路者，可以统一扣减）。

### 18.5.3 集中式计算

:::en
In centralized computation, a controller collects network topology, TE, and SRv6 information through BGP-LS or other protocols; computes a qualified path according to service requirements; and then delivers the corresponding SRv6 Policy to the headend through protocols such as BGP and PCEP. Centralized computation supports global traffic optimization, resource reservation, and cross-domain scenarios.
:::

集中式计算中，控制器通过 BGP-LS 等收集拓扑、TE 与 SRv6 信息，按业务需求算出合格路径，再通过 BGP、PCEP 等把策略下发给头端。**集中式支持全局流量优化、资源预留、跨域场景**。

原文 Table 4.19 逐项对比了三种方式，这张表值得整张记住——它是选型的唯一依据：

| 能力 | 手工配置 | 头端计算 | 集中式计算 |
|---|---|---|---|
| 人工规划路径 | 支持 | 支持 | 支持 |
| 按最小时延算路 | 支持 | 支持 | 支持 |
| **带宽预留** | 不支持 | 不支持 | **支持** |
| affinity 属性算路 | 支持 | 支持 | 支持 |
| 跳数限制 | 支持 | 支持 | 支持 |
| **全局流量优化** | 不支持 | 不支持 | **支持** |
| **优先级抢占** | 不支持 | 不支持 | **支持** |
| **跨域场景** | 支持（人肉规划） | **不支持** | **支持** |
| SRLG | 不支持 | 支持 | 支持 |

:::en
In general, because a controller can obtain global topology, TE, and other relevant information using BGP-LS, it is possible to achieve global traffic optimization through centralized computation. In contrast, headend computation can only compute the optimal path within an IGP domain. Centralized computation also supports bandwidth reservation and priority preemption, which facilitates TE deployment.
:::

总体而言，控制器能通过 BGP-LS 拿到全局拓扑与 TE 等信息，因此**集中式可实现全局流量优化**；**头端计算只能在 IGP 域内算最优**。集中式还支持带宽预留与优先级抢占，便于 TE 落地。

```text
图 18-9：三条算路的选型决策（按约束逐层排除）

  有带宽预留/抢占要求？
    ├─ 是 ──► 只能集中式（上表唯一"支持"的一列）
    └─ 否 ──► 需要跨 IGP 域？
              ├─ 是 ──► 集中式；或"手工规划跨域 + 每域内集中"
              └─ 否 ──► 拓扑稳定、路径变化少？
                        ├─ 是 ──► 手工 + SBFD（最省，但故障不自动切）
                        └─ 否 ──► 头端 CSPF（域内自动，无需控制器）
```

工程上更常见的是**混合**：域内用头端 CSPF 跟拓扑，跨域骨干用集中式算路，个别硬 SLA 专线用"手工 + SBFD + 双路径"。三种并存不冲突——候选路径的 preference 会把它们排出主备。

## 18.6 三种引流方式：BSID、Color、DSCP

:::en
After an SRv6 Policy is deployed on the headend, traffic needs to be steered into the SRv6 Policy. This can be done based on either binding SIDs or color values.
:::

策略在头端部署好之后，还要把流量**引进去**。可以基于 **BSID**，也可以基于 **Color**。

### 18.6.1 基于 BSID 引流

:::en
As shown in Figure 4.24, an SRv6 Policy with the binding SID B1::100 and segment list <B3::4, B4::6, B5::55> is deployed on node A to which a packet with the destination address of B1::100 is sent from an upstream node.
:::

如图，节点 A 上部署了一条 BSID 为 `B1::100`、段列表为 `<B3::4, B4::6, B5::55>` 的策略。上游节点把一个**目的地址为 `B1::100`** 的报文送给了 A。

:::en
As the destination address is the binding SID of node A's local SRv6 Policy, node A processes the packet as follows: 1. Decrements the SL value in the SRH of the original packet by 1 to point to the next SID. 2. Encapsulates a new IPv6 header for the packet, with the destination address as the first SID (B3::4) of the corresponding SRv6 Policy and the source address as a local interface address. 3. Encapsulates a new SRH carrying the segment list of the corresponding SRv6 Policy. 4. Updates other fields in the packet, searches the forwarding table, and forwards the packet accordingly.
:::

因为目的地址就是 A 本地策略的 BSID，A 这样处理：**① 把原报文 SRH 的 SL 减 1**，指向下一个 SID；**② 给报文封一个新 IPv6 头**，目的地址为策略第一个 SID（`B3::4`），源地址为本地接口地址；**③ 封装新 SRH**，携带策略段列表；**④ 更新其他字段、查转发表、转发**。

第 ① 步是这套机制的精髓，也是最容易看漏的一步：

```text
图 18-10：BSID 引流是"压栈"而不是"替换"

  上游发来（已有段列表，正在执行）：
  ┌─────────┬──────────────────────────────┬──────┐
  │ IPv6 头 │ SRH: [B1::100, X::1, Y::1]   │ 载荷 │  SL=1
  │ DA=B1::100                              │      │
  └─────────┴──────────────────────────────┴──────┘
        │ ① 原 SRH 的 SL 减 1（1 → 0），保留"剩余程序"
        ▼
  ┌─────────┬──────────────────────────────┬──────┐
  │ IPv6 头 │ SRH: [B1::100, X::1, Y::1]   │ 载荷 │  SL=0
  └─────────┴──────────────────────────────┴──────┘
        │ ②③ 外面再包一层
        ▼
  ┌─────────┬────────────────────────────────┬──────────┬──────┐
  │ 新 IPv6 │ 新 SRH: [B3::4, B4::6, B5::55] │ 原报文   │ 载荷 │
  │ DA=B3::4│ SL=2                           │(含旧SRH) │      │
  └─────────┴────────────────────────────────┴──────────┴──────┘
            执行完新段列表后，旧的 SRH 继续（SL=0 → X::1 → Y::1）
```

:::en
Using this method, traffic can be steered into the SRv6 Policy based on its binding SID. This method is usually used in scenarios such as tunnel stitching and inter-domain path stitching to effectively reduce the SRv6 SID stack depth. It also significantly reduces the inter-domain coupling degree, so that the changes to forwarding paths in one domain do not need to be propagated to others.
:::

用这种方式，流量可按 BSID 引进策略。它常用于**隧道拼接、跨域路径拼接**，可**有效降低 SID 栈深度**，也**显著降低域间耦合**——一个域内路径变化不需要扩散到别的域。

"降低栈深度"要配合 MSD 理解：拼接是**把一条长路径拆成两段短路径**，每段各自不超过本域 MSD。**拼接不减少端到端总跳数，但把"一次压满"变成"分段压"**，从而绕开 MSD 限制。代价是每段多一层 IPv6 头（40 B）。

### 18.6.2 基于 Color 引流

:::en
The color attribute introduced to SRv6 Policies is used as an extended community of BGP routes. Because of this, the traffic transmitted over a specific route can be steered into the SRv6 Policy configured with the same color value.
:::

引入策略的 color 属性被用作 **BGP 路由的扩展团体**。因此**走某条特定路由的流量，会被引进 color 值相同的策略**。

:::en
Color is an important SRv6 Policy attribute; it is an anchor point for services and tunnels. As shown in Figure 4.25, a color template can be used to define one or more service requirements, including low latency, bandwidth, and affinity attributes. SRv6 Policy paths can then be computed based on the color template.
:::

Color 是策略的重要属性，是**业务与隧道的锚点**。color 模板可以定义一个或多个业务要求（低时延、带宽、affinity），策略路径再按这个模板算出来。

:::en
As well as this, services can use the color attribute to define the requirements of network connections. This enables the color attribute of services to be matched with the color of a specific SRv6 Policy, ultimately achieving automatic traffic steering. Hence, during service deployment, only service requirements, not tunnels, need to be defined. The result is the decoupling between service deployment and tunnel deployment.
:::

同时，业务用 color 属性表达自己对网络连接的要求。这样**业务的 color 与某条策略的 color 匹配**，实现自动引流。于是**部署业务时只需定义业务需求，不需要定义隧道**——结果就是**业务部署与隧道部署解耦**。

"解耦"这三个字是本章最该抄进设计文档的一条，实际差别是：

| 场景 | 耦合（指向 BSID） | 解耦（Color） |
|---|---|---|
| 新增一条低时延专线 | 头端加策略 + 改静态路由指向 BSID | 尾端路由打 `color 100`，策略早已存在 |
| 骨干扩容换路径 | 改每个业务指向的 BSID | 只改策略段列表，业务侧零变更 |
| 跨团队协作 | 业务团队要懂隧道规划 | 业务只说"我要 <10 ms" |

:::en
Figure 4.26 shows the detailed process of color-based traffic steering: 1. A controller delivers an SRv6 Policy with the color value 123 to node A using BGP or another protocol. 2. After a route policy is configured on node E to set the color extended community attribute to 123 for routes, node E advertises a BGP route carrying this attribute to node A. 3. After receiving the route, node A recurses it to the SRv6 Policy whose endpoint and color values match the original next hop and color attribute of the BGP route.
:::

基于 color 的引流过程：**① 控制器用 BGP 等把 color=123 的策略下发给 A**；**② 节点 E 配路由策略把路由的 color 扩展团体设为 123，向 A 通告携带该属性的 BGP 路由**；**③ A 收到路由后，按路由的原始下一跳与 color 属性，把它递归到 endpoint 与 color 都匹配的策略上**。

```text
图 18-11：Color 引流三步（原书 Figure 4.26 重绘）

  ① 控制器 ──BGP/PCEP 下发策略──► PE1
       policy: color=123, endpoint=fc00:0:2::1, 段列表 <...>

  ② PE2 上：route-policy 给路由打 color（详见第 16 章 Bell SP 配置）
       route-policy SET_COLOR
         set extcommunity color 123
       end-policy
       → BGP 通告 10.2.2.2/32（next-hop fc00:0:2::1, color=123）

  ③ PE1 收到路由，做"递归（recursion）"：
       next-hop fc00:0:2::1 ──┐
                              ├─► 匹配 <color=123, endpoint=fc00:0:2::1>
       color 123          ────┘        └─► 命中策略 → 写入 FIB
                                           出接口 = 策略
```

:::en
In the preceding method, after receiving a packet, node A searches the forwarding table based on the packet's destination address and finds that the outbound interface is an SRv6 Policy-specific interface. Then, node A encapsulates the packet with an SRv6 header and forwards it over the SRv6 Policy.
:::

在上面的方式里，A 收到报文后按目的地址查转发表，发现**出接口是策略专属接口**，于是给报文加 SRv6 头，从策略转发出去。

:::en
In this traffic steering mode, route policies are usually used to determine the color values carried by BGP routes. By leveraging flexible coloring policies, color values can be modified as needed on individual nodes, such as the tailend, headend, and even RRs.
:::

这种引流模式通常用**路由策略决定 BGP 路由携带的 color 值**。借助灵活的打色策略，可以在**尾端、头端、甚至 RR** 上按需修改 color。

这点在现网极实用，也最容易出事故：**同一前缀在不同节点被打不同 color**，会出现"同一目的、不同 PE 走不同隧道"。有时是刻意设计（源端就近选路），有时是割接漏改。

### 18.6.3 基于 DSCP 引流

:::en
In addition to binding SIDs and color values, traffic steering can also be performed based on the Differentiated Services Code Point (DSCP) values encapsulated in IP headers. This helps further classify services that match the same route but different origins.
:::

除了 BSID 与 color，还可以按 IP 头里的 **DSCP** 值引流。这有助于进一步区分**命中同一条路由但来源不同**的业务。

:::en
For example, an operator can configure multiple SRv6 Policies as a group on the headend, specify the mapping between each SRv6 Policy and DSCP value in the group, and bind services to the group. In this way, after receiving the service traffic, the headend searches for the corresponding SRv6 Policy in the group according to the DSCP value carried in the IP header, and then completes traffic steering accordingly.
:::

例如运营商可以在头端把多条策略配成一个**组**，组内指定每条策略与 DSCP 值的映射，并把业务绑定到这个组。这样头端收到业务流量后，按 IP 头里的 DSCP 值在**组内**找到对应策略，完成引流。

:::en
It is important to note that, in this traffic steering mode, services must be differentiated at the origin and have different DSCP values specified.
:::

需要强调的是，这种模式下**业务必须在源端就被区分开、并打上不同的 DSCP 值**。

:::en
Certain scenarios may require both color-based and DSCP-based traffic steering. If this is the case, the color attribute can be configured for the involved group, so that the group is also identified using the <Color, Endpoint> tuple. With a traffic steering policy, based on the next hop and color attribute, a service route is first matched with a group, not an individual SRv6 Policy. The headend then resolves the corresponding SRv6 Policy in the group based on the DSCP value carried in the packet.
:::

有些场景需要 **color 与 DSCP 并用**。此时给**组**配上 color 属性，让组也用 `<Color, Endpoint>` 标识。引流策略按下一跳与 color **先把业务路由匹配到"组"而不是单条策略**，头端再按报文携带的 DSCP 在组内解析出具体策略。

```text
图 18-12：两段式引流（color 选组，DSCP 选组内策略）

  路由：10.2.2.2/32  next-hop=fc00:0:2::1  color=123
        │
        ▼  第一段：按 <Color, Endpoint> 命中"组"
  ┌─────────────────────── 组 GROUP-A（color 123）───────────────────────┐
  │  DSCP AF11 ──► 策略 P1（低时延段列表）                               │
  │  DSCP AF21 ──► 策略 P2（大带宽段列表）                               │
  │  DSCP default ► 策略 P3（默认段列表）                                │
  └──────────────────────────────────────────────────────────────────────┘
        │
        ▼  第二段：按报文的 DSCP 在组内选一条
     报文出队
```

三种引流方式的适用边界，一句话版本：

| 方式 | 靠什么识别流量 | 强在哪 | 弱在哪 | 典型场景 |
|---|---|---|---|---|
| BSID | 目的地址 = BSID | 精确、可拼接、降栈深 | 业务侧要指向一个 SID，耦合 | 跨域拼接、SRv6 域互联 |
| Color | BGP 扩展团体 + 下一跳 | **业务与隧道解耦**、可跨节点打标 | 粒度只能到"前缀" | 云专线、按 SLA 分隧道 |
| DSCP | IP 头 6 bit | 同一前缀内再细分 | 要求源端打标、全程不重写 | 同一 VRF 内多等级业务 |
| Color + DSCP | 先选组再选策略 | 前缀级 + 业务级两级 | 规划复杂度最高 | 大型城域/骨干 |

## 18.7 报文怎么走：L3VPN over SRv6 Policy 七步

:::en
In previous sections, we outlined the methods of computing SRv6 Policies and steering traffic into an SRv6 Policy. This section uses L3VPNv4 services as an example to describe how data is forwarded over an SRv6 Policy.
:::

前面讲完了"怎么算策略"和"怎么把流量引进来"。本节以 **L3VPNv4 业务**为例，讲报文如何沿策略转发。

:::en
1. A controller delivers an SRv6 Policy (color: 123; endpoint: PE2 address 2001:DB8::1) to the ingress PE1. The SRv6 Policy is associated with only one candidate path that contains only one segment list <2::1, 3::1, 4::1>.
:::

**① 控制器向头端 PE1 下发策略**：color 123，endpoint 为 PE2 地址 `2001:DB8::1`。策略只关联一个候选路径，候选路径只含一个段列表 `<2::1, 3::1, 4::1>`。

:::en
2. The egress PE2 advertises the BGP VPNv4 route 10.2.2.2/32 (color: 123; next hop: PE2 address 2001:DB8::1/128; VPN SID: 4::100) to PE1.
:::

**② 尾端 PE2 向 PE1 通告 BGP VPNv4 路由** `10.2.2.2/32`：color 123，下一跳 `2001:DB8::1/128`，**VPN SID `4::100`**。

:::en
3. After receiving the BGP route, PE1 recurses it to the corresponding SRv6 Policy based on its color and next hop.
:::

**③ PE1 收到路由后，按 color 与下一跳把它递归到对应策略**上。

:::en
4. After receiving a common unicast packet from CE1, PE1 searches the routing table of the corresponding VPN instance and finds that the corresponding VPN route has been recursed to an SRv6 Policy. Hence, PE1 inserts an SRH carrying the segment list of the SRv6 Policy, encapsulates an IPv6 header into the packet, searches the corresponding routing table, and then forwards the packet accordingly.
:::

**④ PE1 从 CE1 收到普通单播报文**，查对应 VPN 实例路由表，发现该 VPN 路由已递归到一条策略上。于是 PE1 **插入携带策略段列表的 SRH、封装 IPv6 头**，再查表转发。

:::en
5. P1 and P2 forward the packet according to the SIDs encapsulated in the SRH, implementing packet forwarding along the path defined in the SRv6 Policy.
:::

**⑤ P1、P2 按 SRH 里封装的 SID 转发**，实现沿策略定义的路径转发。

:::en
6. After the packet arrives at PE2, PE2 searches the Local SID Table based on the IPv6 destination address 4::1 in the packet and finds a matching End SID. According to the instruction bound to the SID, PE2 decrements the SL value of the packet by 1 and updates the IPv6 DA field to the VPN SID 4::100.
:::

**⑥ 报文到达 PE2**，PE2 按包内 IPv6 目的地址 `4::1` 查**本地 SID 表**，命中 End SID。按该 SID 绑定的指令，PE2 **把 SL 减 1，并把 IPv6 DA 更新为 VPN SID `4::100`**。

:::en
7. Based on the VPN SID 4::100, PE2 searches the Local SID Table and finds a matching End.DT4 SID. According to the instruction bound to the SID, PE2 decapsulates the packet by removing the SRH and IPv6 header, searches the routing table of the VPN instance corresponding to the VPN SID 4::100 based on the destination address in the inner packet, and then forwards the packet to CE2.
:::

**⑦ 按 VPN SID `4::100` 再查本地 SID 表**，命中 `End.DT4`。按指令 PE2 **剥掉 SRH 与 IPv6 头**（解封装），用内层报文的目的地址查 `4::100` 对应 VPN 实例的路由表，再转发给 CE2。

```text
图 18-13：L3VPNv4 over SRv6 Policy 的报文形态变化（原书 Figure 4.27/4.30 重绘）

  CE1 ──PE1──P1──P2──PE2── CE2
        │  ①③ 策略+路由      │
        │  ④ 封装             │ ⑥⑦ 解封装

  ④ 封装后（在 PE1 出口）：
  ┌────────────┬───────────────────────────────┬───────────────┬──────┐
  │ IPv6 头    │ SRH                           │ 内层 IPv6 头  │ 载荷 │
  │ SA=PE1     │ SL=2                          │ SA/DA=CE1/CE2 │      │
  │ DA=2::1    │ [2::1, 3::1, 4::1, 4::100]    │               │      │
  └────────────┴───────────────────────────────┴───────────────┴──────┘
        │ P1：DA=2::1 是本机 End.X → 换成 3::1
        ▼
  ┌────────────┬───────────────────────────────┬───────────────┬──────┐
  │ DA=3::1    │ SL=1  [2::1, 3::1, 4::1, 4::100]              │      │
  └────────────┴───────────────────────────────┴───────────────┴──────┘
        │ PE2：DA=4::1 命中 End → SL-1，DA 改成 4::100
        ▼
  ┌────────────┬───────────────────────────────┬───────────────┬──────┐
  │ DA=4::100  │ SL=0 ...                      │               │      │
  └────────────┴───────────────────────────────┴───────────────┴──────┘
        │ PE2：DA=4::100 命中 End.DT4 → 剥外层，查 VRF 9 转 CE2
        ▼
                       内层 IPv6 报文去往 CE2
```

注意第 ⑥ 步：**End SID 把 DA 换成 VPN SID，而不是直接解封装**。这是"路径终点"与"业务终点"分离的标准写法——段列表的最后一个 SID 是**节点的 End SID**，VPN SID 不放进段列表（它不在 SRH 里，省一个 16 B 槽位）。用 uSID 时同理：`uN` 之后 DA 直接指向下一段的容器。

工程含义：**如果段列表末尾直接写 VPN SID，报文会跳过"更新 DA"这一步，但在多归/anycast 场景下会失去"先到节点、再由节点选 VRF"的能力**。第 7 章的多归 EVPN 就是靠这个分离做的。

## 18.8 没有信令，就没有"down"：故障检测与切换

### 18.8.1 SBFD for SRv6 Policy

:::en
Unlike RSVP-TE, SR does not require connections to be established between routers through signaling. So, as long as an SRv6 Policy is delivered to the headend, it can be successfully established. Note that the SRv6 Policy will not go down unless it is withdrawn. As such, some technologies need to be used to quickly detect SRv6 Policy faults and trigger a traffic switchover to the backup path.
:::

与 RSVP-TE 不同，SR **不需要靠信令在路由器之间建立连接**。所以只要策略被下发到头端，它就能"成功建立"。注意：**除非策略被撤销，否则它永远不会 down**。因此必须借助其他技术快速发现策略故障，并触发向备份路径的切换。

这段话是整章最重要的一段，值得单独钉住：**"建起来了" ≠ "通了"**。

| 现象 | 在 RSVP-TE 里意味着 | 在 SRv6 TE 里意味着 |
|---|---|---|
| 策略/隧道 up | 逐跳 Path/Resv 都成功 | **只说明本地接受了段列表** |
| 路径中间断了 | PathErr 上报，隧道 down | **什么都不会发生** |
| 业务影响 | 收不到通知就不知道 | 收到通知才奇怪 |

:::en
For example, Seamless Bidirectional Forwarding Detection (SBFD), which is a simplified detection mechanism, can be deployed to achieve flexible path detection. SBFD for SRv6 Policy, specifically, is an E2E fast detection mechanism that can quickly detect faults of the path through which an SRv6 Policy passes.
:::

例如 **SBFD**（无缝双向转发检测）这种简化检测机制，可以部署来实现灵活的路径检测。**SBFD for SRv6 Policy** 是一种**端到端快速检测**机制，能快速发现策略所经路径的故障。

:::en
1. BFD for SRv6 Policy is enabled on the ingress PE1, and the SBFD destination address and discriminator are configured.
2. PE1 sends an SBFD packet encapsulated with a SID stack corresponding to the SRv6 Policy.
3. After the egress PE2 receives the SBFD packet, it returns an SBFD reply over the IPv6 shortest path.
4. If PE1 receives the SBFD reply, it considers that the segment list in the SRv6 Policy is normal; otherwise, it considers that the segment list fails. If all the segment lists of a candidate path fail, SBFD triggers a switchover to the backup candidate path.
:::

四步是：**① 头端 PE1 使能 BFD for SRv6 Policy，配置 SBFD 目的地址与 discriminator**；**② PE1 发出携带对应策略 SID 栈的 SBFD 报文**；**③ 尾端 PE2 收到后，沿 IPv6 最短路回一个 SBFD 应答**；**④ PE1 收到应答就认为该段列表正常，收不到就认为段列表故障**；若某候选路径的所有段列表都故障，SBFD 触发切换到备份候选路径。

```text
图 18-14：SBFD for SRv6 Policy 的"去程走策略、回程走最短路"

  PE1 ═══ 去程：SID 栈 = 策略段列表（被检测的路径）═══► PE2
   │   ┌──────────────────────────────────────┐        │
   │   │ DA=首 SID，SRH=段列表，UDP/discriminator │     │
   │   └──────────────────────────────────────┘        │
   │                                                   │
   ◄═══ 回程：普通 IPv6 最短路（不沿策略反向）══════════┘

  关键：只有"去程"证明策略通；回程能回来不代表策略通。
  因此 SBFD 检测的是"单向可用性 + 回程可达性"的组合。
```

这一点决定了 SBFD 的部署位置：**必须在每一条需要保护的段列表上各跑一个 SBFD 会话**，而不是"每条策略一个"。否则候选路径内两条段列表做 UCMP 时，一条断了无法单独摘除。

```text
! PE1：对策略内的段列表做 SBFD 检测（IOS XR 风格示意）
bfd
 multihop
  destination fc00:0:2:e000::
   discriminator local 1001
   discriminator remote 2002
   min-interval 100
   multiplier 3

segment-routing
 traffic-eng
  policies
   policy PE2-LOWLAT
    color 100 end-point ipv6 fc00:0:2::1
    candidate-paths
     preference 200
      explicit segment-list SL-lowlat
       bfd enable                    ! 该段列表启用 SBFD 触发切换
```

### 18.8.2 头端检测的三条规则

:::en
If SBFD is not supported by the headend or is not allowed in some scenarios, the headend is unable to quickly detect the failure of a candidate path in an SRv6 Policy. So, the only way to update the SRv6 Policy is by using a controller to detect topology changes and then perform rerouting. If the controller is faulty or fails to manage the network, the SRv6 Policy cannot converge, which may lead to traffic loss.
:::

如果头端不支持 SBFD、或某些场景不允许用 SBFD，头端就无法快速发现候选路径故障。这时**唯一办法是靠控制器检测拓扑变化再重路由**。若控制器自身故障或失管，**策略就无法收敛，会丢流量**。

:::en
To speed up the traffic switchover when a fault occurs, headend-based fault detection is introduced. With this function enabled, once a segment list fails, the headend sets the segment list to down, triggering a path switchover in the SRv6 Policy or a service switchover.
:::

为加快故障时的切换，引入了**头端检测**。使能后，**段列表一失效，头端就把它置为 down**，从而触发策略内的路径切换或业务切换。

:::en
To detect faults, the headend must be able to collect network topology information and determine the validity of a segment list based on whether the SRv6 SIDs in the segment list exist in the topology and whether routes are reachable.
:::

要检测故障，头端必须能收集网络拓扑信息，并依据**段列表中的 SID 是否存在于拓扑中、路由是否可达**这两点判断段列表是否有效。

:::en
When a segment list fails, the headend performs operations according to the following rules: 1. If the preferred candidate path of an SRv6 Policy has multiple segment lists for load balancing and one of them fails, the segment list is deleted and then removed from the load balancing list. In this case, traffic is load-balanced among the remaining segment lists. 2. If all segment lists in the preferred candidate path of an SRv6 Policy fail and there is a backup candidate path in the SRv6 Policy, traffic is switched to the backup. 3. If both the primary and backup candidate paths of an SRv6 Policy fail, the headend is notified that the SRv6 Policy is in the down state, triggering a service switchover.
:::

段列表故障时，头端按三条规则处理：

1. **首选候选路径内有多条段列表做负载分担，其中一条故障** → 删除该段列表、从分担列表中摘除，流量在其余段列表间分担；
2. **首选候选路径的所有段列表都故障，且存在备份候选路径** → 流量切到备份；
3. **主备候选路径都故障** → 头端把该策略置为 down，触发**业务级切换**（VPN FRR）。

这三条规则其实定义了一个**三级漏斗**，每一级的"覆盖面"不同：

| 级 | 触发源 | 影响范围 | 收敛时间量级 |
|---|---|---|---|
| 段列表 | 单条路径不可用 | 一条段列表 | 依赖检测周期（100 ms–3 s） |
| 候选路径 | 该 preference 下全部段列表不可用 | 一条策略的路径 | 同上 + 切换动作 |
| 业务 | 策略 down | 一整个 VRF / 一批路由 | 秒级（VPN FRR） |

:::en
To detect the states of SRv6 SIDs and routes, the headend must first obtain SRv6 SID and routing information in the IGP domain. Therefore, headend-based fault detection can be used only for SRv6 Policies in IGP single-domain scenarios.
:::

要判断 SID 与路由状态，头端必须先拿到 **IGP 域内**的 SRv6 SID 与路由信息。因此**头端检测只适用于 IGP 单域场景**的策略。

这一条限制很重要：**跨域策略不能用头端检测，只能靠 SBFD 或控制器**。设计中如果一个策略跨了两个 IGP 域又没配 SBFD，那么它**在整个生命周期内不会有任何故障感知**——这是最常见的隐患组合。

### 18.8.3 切换：三层保护各管一段

:::en
In a VPN dual-homing scenario, if a VPN node fails, so too will all SRv6 Policies destined for that node. To prevent service interruptions, traffic needs to be switched to an SRv6 Policy destined for another VPN node.
:::

VPN 双归场景里，**VPN 节点一旦故障，所有以它为端点的策略都会失效**。为避免业务中断，流量要切到以另一台 VPN 节点为端点的策略上。

:::en
Hot Standby (HSB) protection is enabled for SRv6 Policy 1. In addition, segment list 1 contains the End SIDs of P1, P2, and PE2, and protection mechanisms such as TI-LFA are deployed on network nodes.
:::

为策略 1 使能**热 standby（HSB）**保护；段列表 1 包含 P1、P2、PE2 的 End SID；同时在网络节点上部署 **TI-LFA** 之类的保护机制。

:::en
When the link between P1 and P2 fails, TI-LFA local protection takes effect on both P1 and P2. If SBFD for segment list 1 on PE1 detects the failure before TI-LFA local protection takes effect, SBFD sets segment list 1 to down, which triggers a traffic switchover to segment list 2 of SRv6 Policy 1.
:::

当 **P1–P2 链路故障**，TI-LFA 在 P1、P2 上做本地保护。**如果 PE1 上的 SBFD 在 TI-LFA 生效之前就检测到故障**，它会把段列表 1 置 down，触发流量切到策略 1 的**段列表 2**。

:::en
If P2 fails and does not have TI-LFA configured, SBFD on PE1 detects the failure of P2 and sets segment list 1 to down, which triggers the traffic of SRv6 Policy 1 to be switched to segment list 2.
:::

若 **P2 故障且未配 TI-LFA**，PE1 的 SBFD 检测到 P2 故障，把段列表 1 置 down，把策略 1 的流量切到段列表 2。

:::en
If PE2 fails, SBFD can detect that all candidate paths of SRv6 Policy 1 are unavailable. SRv6 Policy 1 is then set to down, which triggers a service switching to SRv6 Policy 2 through VPN FRR.
:::

若 **PE2 故障**，SBFD 能检出策略 1 的**所有候选路径都不可用**，策略 1 被置 down，通过 **VPN FRR** 触发业务切换到策略 2。

```text
图 18-15：三层保护的分工（原书 Figure 4.29/4.30 重绘）

  故障位置        第一层：TI-LFA        第二层：SBFD/头端检测      第三层：VPN FRR
  ─────────────────────────────────────────────────────────────────────────────
  P1–P2 链路   →   本地修复 <50 ms       （若快于 TI-LFA 则切段列表）
  P2 节点      →   无 TI-LFA 则失效   →   段列表 1 down → 段列表 2
  PE2 节点     →   无本地修复         →   所有候选路径 down   →   策略 down
                                                              →   业务切到 PE3

  体会这三层的关系：
    下层快但天花板低（只能保一跳）；
    上层的"覆盖面"更大，但依赖检测周期，速度慢一个量级。
    因此正确做法是"三层都配"，而不是"选一层最好的"。
```

| 层 | 保护对象 | 恢复时间 | 失效前提 | 不配的后果 |
|---|---|---|---|---|
| TI-LFA | 单条链路 / 单节点 | < 50 ms | 需 IGP 收敛完成 | 单点故障即丢包 |
| SBFD / 头端检测 | 段列表 → 候选路径 | 100 ms – 3 s | 需在头端配会话 | 故障无感知，业务一直断 |
| VPN FRR | 端点节点 | 秒级 | 需双归 + 两条策略 | 尾端宕机业务全断 |

一句话记法：**TI-LFA 保"路"，SBFD 保"策略"，VPN FRR 保"业务"**。三者不是替代关系，缺一层就有一个尺度的故障无人负责。

## 18.9 BGP SRv6 Policy：控制器用什么协议下发

:::en
One way to advertise SRv6 Policies is by using BGP. To achieve this, BGP extensions such as Subsequent Address Family Identifier (SAFI), NLRI, and Tunnel Encaps Attribute are defined.
:::

通告策略的一种方式是用 **BGP**。为此定义了 **SAFI、NLRI、Tunnel Encaps Attribute** 等扩展。

:::en
As a newly defined BGP address family, the SAFI is used to identify SR Policy and supports both IPv4 and IPv6 Address Family Identifiers (AFIs). If the AFI is set to IPv6 and the SAFI is set to SR Policy, it indicates that an SRv6 Policy is delivered.
:::

作为新定义的 BGP 地址族，SAFI 用于标识 SR Policy，支持 IPv4 与 IPv6 两种 **AFI**。**AFI 设为 IPv6、SAFI 设为 SR Policy，就表示下发的是 SRv6 Policy**。

:::en
In the Update messages of the IPv6 address family, the NLRI identifies an SR Policy, and the Tunnel Encaps Attribute is used to carry detailed information about the candidate path, including the associated binding SID, preference, and segment list.
:::

在 IPv6 地址族的 Update 消息里，**NLRI 标识一条策略**，**Tunnel Encaps Attribute 携带候选路径的详细信息**，包括关联的 BSID、preference、段列表。

:::en
After computing an SRv6 Policy, a controller uses a BGP peer relationship to advertise the SRv6 Policy candidate path as a route to the headend on the SRv6 network. If multiple identical candidate path routes are received, the headend performs BGP route selection and delivers the selection result to the SRv6 Policy management module, which then installs the selected route in the data plane.
:::

控制器算出策略后，用 BGP 对等体关系把**候选路径当作一条路由**通告给头端。如果收到多条相同的候选路径路由，**头端先做 BGP 选路**，把结果交给策略管理模块，再安装到数据面。

"候选路径当路由"这个设计带来一个非常实用的性质：**BGP 的选路与策略优选是两套机制串联**。先 BGP 选路（比 AS_PATH、MED 等），再策略内比 preference。排障时如果发现"候选路径没被选中"，要看**两个地方**：

```text
图 18-16：BGP SRv6 Policy 的三层报文结构（原书 Figure 4.31 / Table 4.21-4.26 归并）

  NLRI（AFI=2 IPv6, SAFI=73）：<Distinguisher, Policy-Color, Endpoint>
     |            4 octets      4 octets    16 octets   （IPv6 时长度值 24）
     └─ 标识"某策略的一条候选路径"

  Path Attribute：Tunnel Encaps Attribute(23)
     Tunnel Type = 15（SR Policy）
       ├── sub-TLV: Binding SID
       ├── sub-TLV: Preference      （缺省 100）
       ├── sub-TLV: Priority
       ├── sub-TLV: Policy Name
       ├── sub-TLV: ENLP            （显式空标签策略）
       └── sub-TLV: Segment List
             ├── sub-TLV: Weight  （缺省 1）
             ├── sub-TLV: Segment
             └── sub-TLV: Segment ...
```

| 项 | 取值 | 缺省 | 排障要点 |
|---|---|---|---|
| SAFI | 73 | — | **AFI 必须是 2**，否则下发的是 IPv4 版策略 |
| NLRI | Distinguisher + Color + Endpoint | — | Endpoint 写成 loopback 之外的地址即不生效 |
| Tunnel Type | 15 | — | 与 MPLS 的 SR Policy 区分 |
| Attribute | 23 | — | 老版本不认，表现为"路由收到但没策略" |
| Preference | 子 TLV | **100** | 与本地配置的 preference 混用会主备颠倒 |
| Weight | 子 TLV | **1** | 全相同 = 等价分担，想 UCMP 必须显式给权重 |
| ENLP | 子 TLV | — | SRv6 域内一般不用；跨域接 MPLS 时才关心 |

:::en
The Binding SID sub-TLV is used to specify the binding SID associated with a candidate path.
:::

**Binding SID 子 TLV** 用于指定候选路径关联的 BSID。

:::en
The Preference sub-TLV is an optional sub-TLV that is used to specify the preference of an SRv6 Policy candidate path.
:::

**Preference 子 TLV** 是可选子 TLV，用于指定候选路径的 preference。

控制器下发时通常**不带 BSID**（转发器在动态池里自己分，再靠 BGP-LS 回报，见 18.4）；而带 BSID 下发时，头端就要用这个值——这也是为什么**静态 BSID 段必须是全网规划表里的一行**，不能两个策略撞同一个值。

```text
! PE1：接收 BGP SRv6 Policy 并查看状态（IOS XR 风格示意）
router bgp 65000
 address-family ipv6 unicast
  segment-routing srv6
   locator Locator0
  !
  neighbor 2001:DB8:9::1       ! 控制器 / RR
   address-family sr-policy-ipv6
    route-policy PASS in
    route-policy PASS out
```

```text
show bgp ipv6 sr-policy                                  ! 收到的策略路由
show segment-routing traffic-eng policy color 100 endpoint ipv6 fc00:0:2::1
show segment-routing traffic-eng policy all detail        ! 候选路径/段列表/BSID
show segment-routing traffic-eng forwarding policy        ! 是否已装 FIB
```

**把这三条 show 按顺序看**，就对应"路由收到 → 策略生成 → 装进 FIB"三个阶段。很多"策略不生效"的问题卡在第三阶段：路由有了、策略也有了，但**没有装 FIB**，因为递归没成功。

## 18.10 设计者的一段异议：SR Policy 该不该耦合

原书这一节（4.6 Stories behind SRv6 Design）是全书少见的"作者表态"，价值在于它把协议设计背后的取舍讲透了。

:::en
During SDN transition, BGP and PCEP become two primary southbound protocols for SDN controllers. Which of these two protocols should be used has long been the subject of debate.
:::

SDN 转型期间，**BGP 与 PCEP 成为控制器的两大南向协议**，该用哪个争论了很久。

:::en
IP professionals are familiar with BGP, which therefore becomes their natural choice. Having been around for 30 years, BGP has had time to develop distinct advantages, which can be seen in its diverse functions and excellent interoperability.
:::

IP 从业者熟悉 BGP，所以它天然成为首选。BGP 已有 30 年历史，发展出明显优势：功能丰富、互操作性极好。

:::en
PCEP was first developed by experts from the optical transport field, and there were few deployments for the first 10 years after its conception. But in recent years, the development of SDN is giving PCEP a new lease of life. In particular, due to the fact that most IP-based mobile transport networks are originated from Synchronous Digital Hierarchy (SDH), many network O&M personnel with a lot of optical transport experience consider BGP complex, and so tend to opt for PCEP instead. However, the downside of PCEP is that it is a relatively new protocol that has not been thoroughly verified on live networks. It therefore falls short of BGP in many aspects, such as interoperability and performance.
:::

PCEP 最初由**光传输领域**的专家开发，诞生后十年间部署很少。近年 SDN 的发展让 PCEP 重获生机。特别地，由于多数基于 IP 的移动承载网源自 **SDH**，许多有光传输经验的运维人员觉得 BGP 太复杂，反而倾向 PCEP。但 PCEP 的短板是它相对较新、**未在现网充分验证**，在互操作性与性能等方面不如 BGP。

:::en
In addition to the impact of historical factors and user habits, BGP and PCEP have essential technical differences which affect the final choice. Specifically, BGP always adopts the Push mode, which enables a BGP RR to push a BGP route received from a peer to other peers; on the contrary, PCEP uses the Pull mode, in which a PCE client requests a PCE server to compute a path, with the PCE server then returning the path computation result to the client.
:::

除了历史因素与用户习惯，两者还有**本质的技术差异**：**BGP 始终是 Push 模式**，RR 能把从某个对等体收到的路由推给其他对等体；**PCEP 是 Pull 模式**，客户端请求服务器算路，服务器再把结果回给客户端。

:::en
For BGP, this limits its usage in scenarios where it is used for features that need SR Policies to be established on demand.
:::

对 BGP 而言，这个特性**限制了它用于"按需建立 SR Policy"的场景**。

这就是 18.3 那个表格的收尾：**BGP 适合"统一算、统一下发"，PCEP 适合"你要什么、我给什么"**。选型时先问"策略是提前规划好的，还是业务来了才建的"，答案就出来了。

:::en
I always think that Huawei's tunnel policy design in MPLS is very successful. Tunnel policies can be used for VPN instances to select tunnels.
:::

我一直认为华为在 MPLS 里的**隧道策略（tunnel policy）**设计很成功——VPN 实例可以用隧道策略来选择隧道。

:::en
Personally speaking, I am not in favor of the SR Policy design. Huawei's tunnel policy design is very clear, in that tunnel establishment and tunnel selection are decoupled and do not affect each other. That is, tunnel attributes are configured under tunnels, and tunnel selection policies for VPN instances are configured under tunnel policies. In contrast, the SR Policy design combines tunnel (SR path) establishment, binding SID allocation to tunnels, and tunnel selection, which may lead to the following problems:
:::

就我个人而言，**我并不赞成 SR Policy 的设计**。华为的隧道策略设计非常清晰：**隧道建立与隧道选择是解耦的、互不影响**——隧道属性配在隧道下，VPN 实例的选隧道策略配在隧道策略下。而 **SR Policy 把"隧道（SR 路径）建立""给隧道分配 BSID""隧道选择"三者合在了一起**，可能带来这些问题：

:::en
• The name "SR Policy" is somewhat misleading. SR Policies involve the setup of SR paths and are quite different from the conventional definition of a policy.
• Due to the coupling design, the data of the tunnel policy that is not changed also needs to be delivered during the update of some tunnel (SR path) attributes (and vice versa), resulting in network resources being wasted.
• Based on prior experience in MPLS TE design, network deployment requires many tunnel attributes and flexible tunnel policies. The current SR Policy mechanism seems simple, but it may become complex as more SR features emerge.
:::

- **"SR Policy"这个名字有点误导**：它讲的是 SR 路径的建立，与传统意义上的"策略"相当不同；
- **耦合设计导致重复下发**：更新某些隧道路径属性时，连没变的隧道策略数据也要一起送（反之亦然），浪费网络资源；
- **可扩展性存疑**：按 MPLS TE 的历史经验，现网部署需要**很多隧道属性 + 灵活的隧道策略**。当前 SR Policy 机制看着简单，但随着 SR 特性增多可能变复杂。

这段异议不必当作结论接受，但**它指出的耦合是真实存在的**，而且已经体现在现网的两个具体后果上：

| 耦合点 | 现实后果 | 缓解做法 |
|---|---|---|
| BSID 绑在候选路径上 | 换路径要留心 BSID 是否跟着变，变了就得改引用方 | BSID 用静态池，规划表固定 |
| 选路（color）与建路（策略）同一对象 | 改隧道会触发路由重下发 | 用 color 做锚点，隧道变更不通知业务 |
| 策略、隧道、服务三层语义混在一起 | 排障时要同时看 BGP 路由、策略、FIB 三处 | 按 18.9 的三条 show 顺序排查 |

一个可以直接迁移的判断标准：**凡是"业务侧需要引用"的东西，就必须稳定；凡是"拓扑变了要跟着变"的东西，就必须可替换**。SR Policy 把这两类塞进了一个对象，所以工程上只能靠"静态 BSID + color"人为把它们分开——这也正是第 16 章 Bell SP 那个三行配置的由来。

## 18.11 排障：策略不生效的六个分支

按"路由 → 策略 → FIB → 报文"四段切，每段都有明确的期望值：

```text
图 18-17：SRv6 Policy 不生效的分支树

  业务不通
    │
    ├─ ① 头端有没有这条策略？
    │     show segment-routing traffic-eng policy color X endpoint ipv6 Y
    │     无 ──► 控制器/PCEP 会话？SAFI 73 收到没？BSID 池够不够？
    │
    ├─ ② 策略 up，但候选路径不是你以为的那条？
    │     比 preference：本地配置 vs 控制器下发（协议优先级谁高）
    │     典型：控制器下发 pref=100，本地手工写了 200 → 手工赢
    │
    ├─ ③ 段列表里的 SID 都可达吗？
    │     show segment-routing srv6 sid all | include <SID>
    │     缺 ──► 那个节点没上报 BGP-LS / locator 没起 / Algo 不匹配
    │
    ├─ ④ 递归成功了吗？（路由真的指到策略了吗）
    │     show bgp ipv6 unicast <prefix> detail   → 看 color 与 next-hop
    │     颜色不匹配 ──► 尾端没打 extcommunity，或 RR 改了 color
    │
    ├─ ⑤ 装进 FIB 了吗？
    │     show segment-routing traffic-eng forwarding policy
    │     无 ──► MSD 不够 / BSID 冲突 / 下一跳不可达
    │
    └─ ⑥ 报文真的带 SRH 了吗？
          show segment-routing srv6 counters / 抓包
          没带 ──► 引流没命中（③④ 的问题），不是转发问题
```

| 分支 | 期望值 | 常见实际值 | 根因 |
|---|---|---|---|
| ① 策略存在 | 1 条策略，候选路径数 ≥1 | 空 | PCEP 会话 down / PST≠2 / BSID 池耗尽 |
| ② 主用候选路径 | preference 最大者 | 意外的那条 | 本地静态覆盖了控制器下发 |
| ③ SID 可达 | 段列表每个 SID 都能查到 | 缺 1–2 个 | BGP-LS 未上报 / locator 未发布 |
| ④ 递归命中 | 路由 detail 里出接口 = 策略 | 出接口 = IGP 下一跳 | color 未打 / 下一跳与 Endpoint 不一致 |
| ⑤ 装 FIB | 有对应条目 | 无 | MSD 不足 / 拼接层数超限 |
| ⑥ 报文带 SRH | DA = 首 SID | DA = 业务地址 | 引流未命中（回到 ④） |

三个最费时间的坑，单独列出来：

| 坑 | 现象 | 判断方法 |
|---|---|---|
| **MSD 不足** | 策略 up、FIB 没装、无告警 | 段数 > 头端 `Max H.Encaps`；减段或改拼接 |
| **BSID 冲突** | 后建的那条策略静默失败 | 两条策略配了同一静态 BSID；查 `sid all` 有无重复 |
| **Algo 不匹配** | SID 在，但控制器算的路径绕过它 | 策略算在 Algo 128，SID 却发布在 Algo 0 |

## 18.12 本章小结

回到 18 章开头那三个问题，答案可以压成一张表：

| 问题 | 答案 | 关键机制 | 失败模式 |
|---|---|---|---|
| 路径由谁算 | 手工 / 头端 CSPF / 控制器全局 | 表 18-5 的九项能力对比 | 选了不支持所需能力的路子 |
| 怎么交给头端 | PCEP（Pull）或 BGP（Push） | PST=2、SAFI 73 | 协商不上，静默不生效 |
| 断了怎么发现 | SBFD / 头端检测 / 控制器重算 | 三层保护（图 18-15） | **什么都不配 = 永远不知道** |

前 17 章与本章的分工，用一句话说清：

| 层 | 谁负责 | 本章是否涉及 |
|---|---|---|
| SID 怎么编、locator 怎么规划 | 第 5、14、15 章 | 否 |
| 段列表怎么表达路径 | 第 3、6 章 | 只作为输入 |
| **段列表怎么被算出来、下发、监控** | **本章** | 是 |
| 服务怎么串进段列表 | 第 11、16 章 | 相邻（18.4 提及） |
| 路径断了链路级怎么救 | 第 9 章 TI-LFA | 相邻（18.8.3） |

三句话记住本章：

1. **SRv6 TE 省掉的是逐跳状态，不是省掉了运维**——状态从 N 跳搬到 1 跳，监控责任也从 N 跳搬到 1 跳。
2. **Color 是业务与隧道之间唯一的解耦点**——没有 color，所有隧道变更都要通知业务侧。
3. **"策略 up" 只是一个本地状态**——它证明"头端接受了这段程序"，不证明"这段程序能跑通"。

## 实战案例

### 案例 A：低时延专线走了普通隧道

**背景**：PE1→PE2 之间建了两条策略，`color 100`（低时延，4 跳）与 `color 123`（默认，绕行）。新开的视频会议专线要求 < 10 ms，尾端 PE2 上已经打了 `set extcommunity color 100`。割接后发现时延 23 ms。

**排查**：

```text
PE1# show bgp ipv6 unicast 10.2.2.2/32 detail
  ...
  Extended Community: Color:0:100          ← ① color 打上了
  Next Hop: fc00:0:2:e000::                ← ② 下一跳是 End SID
PE1# show segment-routing traffic-eng policy color 100 endpoint ipv6 fc00:0:2::1
  % No policy found                       ← ③ 策略根本没建
PE1# show segment-routing traffic-eng policy all
  Policy: color 100  endpoint fc00:0:2::/48   ← ④ endpoint 是 /48 前缀
```

**根因**：策略的 Endpoint 配成了 `fc00:0:2::/48`（locator 前缀），而路由的下一跳是 `fc00:0:2:e000::`（End SID）。递归要求**下一跳与 Endpoint 完全一致**，前缀匹配不算。于是路由只能回落到 IGP 最短路，正好落在绕行路径上。

**修复**：把策略 Endpoint 改成 `fc00:0:2:e000::`。规范做法是**规划阶段就规定"策略 Endpoint 一律用对端 End SID"**，并写进模板。

**教训**：color 对了不代表引流成功——**引流是 `<Color, Endpoint>` 双条件匹配**，两个都要对。

### 案例 B：跨域拼接把 MSD 撑爆了

**背景**：城域 A（8 段）与骨干 B（7 段）分属两个 IGP 域。控制器为跨域业务做**隧道拼接**：A 域内一条策略（8 段），末端指向 B 域头端的 BSID，再由 B 域策略（7 段）接续。业务不通，头端无告警。

**排查**：

```text
PE1# show segment-routing traffic-eng policy color 200 endpoint ipv6 fc00:0:9::1 detail
  Candidate path: preference 100
    Segment list: SL-A   State: up        ← 段列表自己说 up
  Forwarding: not installed               ← 但 FIB 没装
PE1# show segment-routing srv6 locators detail
  Locator0  MSD: Max-Seg-Left 10  Max-H-Encaps 8   ← 头端能力
```

**根因**：拼接后第一段是 8 段，但**第一段的末 SID 指向第二段的 BSID，报文在 B 域头端还要再压 7 段**。B 域头端 `Max-H-Encaps = 8` 够用，问题出在 A 域头端：它压了 8 段，**其中最后一段本身就是"另一条策略"**，部分实现会按"8 段 + 内层还有程序"来算净荷长度与 SL 校验，封装被拒。

**修复**：把 A 域段列表压到 6 段（保留 2 段余量给拼接层）。原则是：

```text
可用段数 = min(头端 Max-H-Encaps, 沿途最小 MSD) - 拼接层数
```

**教训**：**拼接不是免费的"段数折叠"**，它是"用额外的 40 B 外层换段数预算"。设计跨域策略时必须先查两端的 MSD，并把结果写进容量表。

### 案例 C：控制器重启，45 秒黑洞

**背景**：策略全部由控制器通过 PCEP 下发（PST=2，主动模式 + 委托）。某次控制器升级重启，业务中断约 45 秒。事后查设备日志：策略并未消失，但流量全部丢弃。

**排查**：

```text
PE1# show segment-routing traffic-eng policy color 100 endpoint ipv6 fc00:0:2::1
  BSID: fc00:0:1:e017::                    ← 动态池，编号与升级前不同
PE1# show running-config | include binding-sid
  （空：策略由控制器下发，本地无静态 BSID 配置）
```

**根因**：控制器重启后**重新下发了同一批策略**，但头端为每一条**重新分配了动态 BSID**（编号从 `e017::` 变成 `e031::`）。上游那些"把流量指向旧 BSID"的引用（另一台设备上的段列表、以及跨域拼接配置）全部指向了**已经不存在的 SID**，报文在头端被丢——因为 DA 不匹配任何本地 SID。

**修复（两步）**：

1. 被引用的策略改用**静态 BSID**（`static-sid` 段内分配），并在规划表中登记；
2. 头端补配 **SBFD**，让"路径不可用"这件事至少有 100 ms 级的可见性。

```text
! 事后加固：静态 BSID + SBFD
segment-routing
 traffic-eng
  policies
   policy PE2-LOWLAT
    color 100 end-point ipv6 fc00:0:2::1
    binding-sid fc00:0:1:d000::100       ! 静态，重启不变
    candidate-paths
     preference 200
      explicit segment-list SL-lowlat
       bfd enable
```

**教训**：BSID 的"稳定性"（18.4.3）不是文档修辞。**凡是会被别人引用的 SID，就不能是动态的**——动态 BSID 只适合"没有外部引用、只做 BGP-LS 上报"的场景。

## 延伸阅读

| 主题 | 文档 | 读它的理由 |
|---|---|---|
| SR 架构 | RFC 8402 | 第 2 章的基础；TE 的"源路由"前提 |
| SRv6 网络编程 | RFC 8986 | SID 行为（`End`、`End.X`、`End.DT4`）的定义源头 |
| BGP-LS 基础 | RFC 7752 | NLRI 四类的原始定义 |
| BGP-LS SR 扩展 | RFC 9085 | Node/Link/Prefix 的 SR 属性 |
| **BGP-LS SRv6 扩展** | **RFC 9514** | 18.2.2 那张表的权威出处 |
| PCEP SR 扩展 | RFC 8664 | PST=1（SR-MPLS）的写法，对照 PST=2 |
| **PCEP SR Policy 扩展** | **RFC 9256** | 18.3 七步交互与 SRv6-ERO/RRO 的完整定义 |
| BGP SR Policy | draft-ietf-idr-segment-routing-te-policy | SAFI 73、Tunnel Type 15、Attr 23 |
| BFD | RFC 5880 | SBFD 的基础 |
| S-BFD | RFC 7880 | 18.8.1 的简化检测机制 |

**与本书前 17 章的交叉参考**：

| 想深入了解 | 去看 |
|---|---|
| 段列表怎么写、uSID 怎么压 | 第 3 章、第 6 章 |
| locator 与 SID 规划（本章所有 SID 的来源） | 第 5 章、第 14 章 |
| BGP-LS 在 IGP 侧的对应物（IS-IS/OSPF 扩展） | 第 5 章 |
| SRH 与扩展头的报文细节 | 第 17 章 |
| 探测与 OAM（SBFD 的邻居话题） | 第 9 章 |
| 服务 SID 与 BSID 的关系 | 第 11 章 |
| color 引流的真实生产配置 | 第 16 章 |
| MTU 预算（每层封装 40 B 怎么算） | 第 10 章、第 17 章 |
