> **本章定位**：原书第 2 章《SRv6 Fundamentals》。本版按原书 2.1–2.7 的段落顺序**逐段对照**：灰色英文块是原文摘录（保留原句与术语），紧随其后的中文是该段的完整翻译，必要时补一句工程注解。书中的 Figure 2.1–2.6 各配一张矢量图（可缩放、点击放大）。

## 2.1 Segment Routing 简述

:::en
For a comprehensive understanding of Segment Routing, refer to the SR book series parts 1 and 2. A very brief introduction to Segment Routing is provided in this section. If you are already familiar with Segment Routing, you can skip this section and go directly to section 2.2.
:::

完整的 Segment Routing 论述在本系列的第一部与第二部里。本节只提供一个极简介绍：如果你已经熟悉 SR，可以直接跳到 2.2 节。

### 2.1.1 什么是 Segment Routing

:::en
The Segment Routing (SR) architecture is based on the source routing paradigm. A node (any router, host, or a device in general) chooses a path and steers a packet through the network via that path by inserting an ordered list of segments in the packet header, instructing how nodes that receive the packet should process this packet. A segment can represent any kind of instruction. It can be fabric oriented with a topological instruction, or it can be a more advanced application executed on a server.
:::

SR 架构建立在**源路由（source routing）**范式之上。一个节点（可以是路由器、主机，或任何设备）在报文头里插入一个**有序的段列表**，用这个列表把报文引导到它所选择的路径上，同时指示收到报文的节点应该怎样处理这个报文。一个段可以代表任何类型的指令：可以是面向 fabric 的拓扑指令，也可以是运行在服务器上的更高级应用。

:::en
Because the instructions are encoded in the packet header, the nodes in the network simply have to execute these instructions when they receive the packet. The nodes on that path do not have to maintain state information for all possible flows that are traversing them ("the state is in the packet").
:::

因为指令就编码在报文头里，网络中的节点收到报文时**只需执行这些指令**。路径上的节点不必为途经它们的、所有可能存在的流维护状态信息——这就是常说的"**状态在报文中**"。

:::en
The source node can control the steering of packets at the level of individual flows by adding the proper instructions, or segments, in the packet headers. Since nodes, other than the source node, do not need to store and maintain any per-flow state, the traffic steering decisions only impact the source nodes. This way, SR offers advanced traffic steering capabilities in IP networks while improving scalability both in the data and control planes.
:::

源节点通过在报文头里加入恰当的指令（也就是段），可以做到**按流（per-flow）级别**的调度控制。由于除源节点外的其他节点不需要保存和维护任何 per-flow 状态，调度决策只影响源节点本身。这样一来，SR 在 IP 网络中提供了高级的流量引导能力，同时改善了数据面与控制面的可扩展性。

:::en
Segment Routing has two data plane instantiations. One over MPLS, typically known as SR-MPLS, and over the IPv6 data plane, typically referred to as SRv6. This book focused on the latter.
:::

Segment Routing 有两种数据面实例：一种跑在 MPLS 上，通常称为 **SR-MPLS**；另一种跑在 IPv6 数据面上，通常称为 **SRv6**。本书只讨论后者。

两种范式的差别，一张图看最直观：

```
传统逐跳状态（RSVP-TE、每流标签）        源路由（SRv6）
                                         
  源 ── 信令 ──> 每台路由器各自维护          源把程序写进报文头
         每流状态、标签、带宽、备份 LSP            沿途节点只做两件事：
                                         1) 最长匹配查 DA
   ┌────┬────┬────┬────┐                 2) 按指令处理并"移一位"
   │ R1 │ R2 │ R3 │ R4 │                 ┌────┬────┬────┬────┐
   │状态│状态│状态│状态│                 │ R1 │ R2 │ R3 │ R4 │
   └────┴────┴────┴────┘                 │ 无 per-flow 状态   │
   路径变了 → 全网重新信令                 └────┴────┴────┴────┘
                                         路径变了 → 只改源节点列表
```

*图 2-0：逐跳状态 vs 源路由（按 2.1 节文字描述绘制）*

{{FIG|02/fig-2-0-hopstate|图 2-0 · 矢量版|逐跳状态与源路由的对比：前者靠信令让全网维护每流状态，后者只把程序写进报文头。}}

### 2.1.2 Segment 与 SID

:::en
A Segment is an instruction that a node executes on the incoming packet. Examples of instructions are: forward the packet according to the shortest path to destination, forward the packet through a specific interface, deliver the packet to a given application/service instance, etc. In the context of SRv6, the instruction is defined by the "SRv6 Endpoint Behavior". As of today, there are over a hundred different behaviors defined, all kept track of by IANA. There are a few behaviors that are widely used in almost every deployment.
:::

一个**段（Segment）**是节点对入向报文执行的一条指令。指令的例子包括：按到目的地的最短路径转发报文、从指定接口转发出去、把报文投递给某个应用/业务实例，等等。在 SRv6 的语境里，这条指令由"**SRv6 Endpoint Behavior（端点行为）**"定义——也就是这条指令所执行的报文处理行为。到今天为止已定义一百多种行为，全部由 IANA 登记维护；不过真正在几乎每个部署中都会用到的行为只有少数几种。

:::en
A Segment Identifier (SID) identifies a segment. It is a specific instantiation of a segment. This book uses the terms "segment" and "SID" interchangeably.
:::

**段标识符（SID）**用来标识一个段，它是一个段的具体实例化。本书中"segment"与"SID"两个词互换使用。

容易混淆的点：**段是"指令"这个抽象概念，SID 是"哪台节点上的哪条指令"的具体地址**。同一个 End 行为在每台节点上都有一个不同的 SID，但指令语义完全相同。

### 2.1.3 网络编程（Network Programming）

:::en
The concept of Network Programming consists of combining segments to build a network program that is executed by the network. Segments are the basic building blocks or instructions that allow us to build this program. In the simplest application, these building blocks can be used individually. A single segment can steer a packet through the network, such as a segment with the instruction forward packet according to the shortest path to destination Node 1.
:::

**网络编程**的概念，就是把多个段组合起来，构成一个由网络来执行的"网络程序"。段是搭建这个程序的基本积木（指令）。最简单的用法是单独使用一块积木：单个段就能把报文引导穿过网络，例如"按最短路径转发到节点 1"这个段。

:::en
Other applications can combine these building blocks to achieve the requirements of the application data flow. By combining segments in an ordered list to form a network program, packets can be steered on any path through the network, regardless of the shortest path, domain boundaries, routing protocol, etc. Or, by combining segments, packets can be steered through a chain of services. The ordered list of segments that composes a network program is called a SID list, and in the IPv6 data plane, it is encoded in the IPv6 header, more specifically in the IPv6 Destination Address and in the Segment Routing Header.
:::

其他应用则可以把这些积木组合起来，满足应用数据流的要求：把段按有序列表组合成网络程序后，报文可以被引导到网络中的**任意路径**上——不受最短路径、域边界、路由协议的限制；或者通过组合段，把报文引导穿过一串服务（服务链）。组成网络程序的这个有序段列表称为 **SID 列表**；在 IPv6 数据面中，它编码在 IPv6 头里，更具体地说，编码在 IPv6 目的地址字段和 Segment Routing Header 中。

### 2.1.4 Segment List 操作

:::en
The SID list is encoded in the packet header. The instruction that is currently being executed on the packet is the instruction of the Active Segment. If the active segment of a packet has the instruction forward packet according to the shortest path to destination Node 1, then each node that receives that packet forwards the packet on the shortest path to Node 1. Once the segment has been processed, the next segment in the SID list becomes the active segment.
:::

SID 列表编码在报文头里。报文**当前正在执行**的那条指令，属于**活动段（Active Segment）**。如果一个报文的活动段是"按最短路径转发到节点 1"，那么每个收到该报文的节点都按到节点 1 的最短路径转发它。一个段处理完之后，SID 列表里的**下一个段成为活动段**。

:::en
In addition, certain scenarios (e.g., Traffic Engineering) may require pushing additional SIDs into the SID list. These segment list operations are mapped to the actual data plane operations applied on the packet header.
:::

此外，某些场景（例如流量工程）可能需要往 SID 列表里**压入（push）**额外的 SID。这些段列表操作，最终都映射为对报文头实际执行的数据面操作。

活动段在报文里是哪个字段？在 SRv6 里永远是 **IPv6 目的地址（DA）**：

```
   源节点封装后的 SID 栈（Segment List 倒序存放）

   SRH Segment List[]
   ┌──────────────────────────────────────┐
   │ [3] fc00:0:2:X::     ← 第一站           │
   │ [2] fc00:0:3:X::                        │
   │ [1] fc00:0:4:X::                        │
   │ [0] fc00:0:5:eeee::  ← 最后一站（业务 SID）│
   └──────────────────────────────────────┘

   IPv6 DA      = fc00:0:2:X::   ← 活动段永远在 DA 里
   Segments Left = 3             ← 还剩 3 段未走

   每跳处理：SL-- ; DA = Segment List[SL] ; 再查表转发
```

*图 2-1：SID 列表与活动段的关系（按 2.1.4 与 2.6 节描述绘制）*

{{FIG|02/fig-2-1-activeseg|图 2-1 · 矢量版|SID 列表倒序存放、活动段永远在 DA 里、SL 与 DA 必须原子更新。}}

### 2.1.5 SR 域（SR Domain）

:::en
The SR Domain is the set of nodes participating in the SR model. It is expected that all nodes in an SR domain are managed by the same administrative entity. All SRv6 SIDs within an SR Domain are allocated from a common IPv6 address. Any packet entering the SR Domain is encapsulated on ingress and decapsulated on egress. This ensures customer packet preservation and integrity.
:::

**SR 域**是参与 SR 模型的节点集合。一般预期 SR 域内所有节点由**同一个管理实体**管理。SR 域内所有 SRv6 SID 都从**统一的 IPv6 地址空间**中分配。任何进入 SR 域的报文都在**入向封装、出向解封装**，这保证了客户报文的保真与完整性。

这一条是后面所有安全讨论的地基：域内地址统一规划、域边界做封装/解封装，因此"域外地址"与"域内 SID"在转发面上天然可区分——域内设备看到来自域外的、DA 落在 SID 块内的报文，可以直接丢弃。

### 2.1.6 Global Segment 与 Local Segment

:::en
There are two types of SIDs, Global and Local.
:::

SID 分为两类：**Global（全局）** 与 **Local（本地）**。

:::en
Global Segment: All SR-enabled nodes in the SR Domain support the instruction associated with a global segment, and each node in the SR Domain installs the instruction of a global segment in its forwarding table. An example of a global segment is a segment with the instruction forward packet according to the shortest path to destination Node 1. Since it is a global segment, each node in the SR Domain knows how to forward the packet on the shortest path to Node 1.
:::

**全局段**：SR 域内所有支持 SR 的节点都支持全局段所关联的指令，域内每台节点都会把这条指令装进自己的转发表。全局段的例子是"按最短路径转发到节点 1"——因为它是全局段，域内每台节点都知道怎样把报文按最短路径送到节点 1。

:::en
Local Segment: Only the node that originates a local segment supports the instruction associated with that local segment, and only the node that originated the local segment installs the associated instruction in its forwarding table. An example of a local segment is a segment advertised by Node 1 with the instruction forward packet on the interface to Node 2. Although other nodes can have an interface to Node 2, the intention is to steer the packet on Node 1's interface to Node 2.
:::

**本地段**：只有**产生**这个本地段的节点支持它关联的指令，也只有产生它的节点会把该指令装进转发表。本地段的例子：节点 1 通告一个段，指令是"从到节点 2 的那个接口转发出去"。虽然别的节点也可能有接口连到节点 2，但这条指令的意图是**必须走节点 1 自己的那个接口**去节点 2。

:::en
To correctly execute the intended instruction of a local segment, the packet must first be steered to the node that can correctly execute this instruction. In our example, we want Node 1 to execute the instruction; therefore, a global segment with instruction forward packet according to the shortest path to destination Node 1 can precede the local segment. The packet will then be steered first to Node 1 and then on Node 1's interface to Node 2.
:::

要想正确执行本地段意图中的指令，报文必须**先被引导到那台能正确执行该指令的节点**。在我们的例子里，我们希望由节点 1 来执行，因此可以先放一个全局段"按最短路径转发到节点 1"，再放这个本地段。报文就会先被送到节点 1，再从节点 1 的接口去节点 2。

:::en
The local semantic of a local segment does not mean that nodes in the network do not know about other nodes' local segments. To be able to use local segments, other nodes need to know about their existence and meaning.
:::

"本地段"的本地语义，**不**意味着网络中的节点不知道其他节点的本地段。相反，为了能使用别的节点的本地段，其他节点必须知道它们的存在与含义——所以本地段同样要通告出去，只是"指令执行"这件事落在产生者身上。

```
   强制走 1→2 这条链路（而不是 源→3→2 的最短路径）

   SID list：< 全局段 fc00:0:1:: , 本地段 fc00:0:1:e001:: >

        ┌────┐   ①按最短路径去 1    ┌────┐
        │ 源 │────────────────────>│ 1  │
        └────┘                     └─┬──┘
                                    │ ②本地段在此被消费
                                    │   （End.X / uA 行为）
                                    │  Eth2 指定链路
                                    ▼
                                  ┌────┐
                                  │ 2  │
                                  └────┘

        若 SID list 只写"去节点 2"，报文可能走 源→3→2
```

*图 2-2：Global 段负责"送到能执行的人手上"，Local 段负责"从哪个接口出去"（按 2.1.6 节描述绘制）*

{{FIG|02/fig-2-2-global-local|图 2-2 · 矢量版|全局段把报文送到能执行指令的节点，本地段再从该节点指定的接口送出。}}

### 2.1.7 拓扑段：Prefix Segment 与 Adjacency Segment

:::en
There are two types of segments whose purpose is mainly to provide topological instructions in the underlay fabric: the Prefix Segment and the Adjacency Segment. These two segment types are the basic building blocks that allow the construction of any topological path through a network by combining or stacking them.
:::

有两类段主要用于在 underlay fabric 中提供**拓扑指令**：**Prefix Segment（前缀段）**与 **Adjacency Segment（邻接段）**。这两类段是基本积木，通过组合或堆叠它们，可以构造出穿过网络的任意拓扑路径。

:::en
Typically, these segments are distributed in the control plane by using the link-state IGP advertisements. This means that all nodes in the IGP network receive these segments. This way, the IGP provides a complete view of the network: each node in the network knows the network's topology and all the segments in the area.
:::

通常这两类段通过链路状态 IGP 通告在控制面分发，也就是说 IGP 网络里所有节点都会收到这些段。这样 IGP 就给出了网络的完整视图：每台节点都知道网络拓扑以及本区域内的所有段。

:::en
If the IGP network is organized in areas, then the nodes do not have a complete view of the remote area (i.e., the topology of nodes and links within it) since that is the principle of separating a network into areas. In SRv6, the segments of any given node are reachable via their locator, which summarizes the segments of that node. These locators may be propagated between areas such that nodes in other areas can reach remote segments by leveraging their locator reachability. This way, Segment Routing can also be used as a transport method in multi-area and multi-level networks.
:::

如果 IGP 网络划分了区域，节点就**不会**拥有远端区域的完整视图（区域内的节点与链路拓扑），这本来就是分区域的原则。在 SRv6 中，任意节点的所有段都可以通过它的 **locator** 到达，而 locator 是对该节点所有段的**汇总**。这些 locator 可以在区域之间传播，使其他区域的节点依靠 locator 的可达性访问远端段。这样一来，Segment Routing 也能作为**多区域、多层级网络**中的传输手段。

这段话点出 SRv6 相比 MPLS 的结构性优势：**locator 是可汇总的 IPv6 前缀**，所以区域/层级边界上不必像 BGP 3107 那样逐条携带客户路由，只带汇总前缀即可。

**Prefix Segment（前缀段）**

:::en
The prefix segment is a global segment, associated with an advertised prefix. The instruction of a prefix segment is to "steer traffic along the ECMP-aware shortest path to the prefix associated with this segment." From anywhere in the network, packets with a prefix segment as the active segment are forwarded on the ECMP-aware shortest path towards the node advertising the prefix associated with the segment. This path is typically a multi-hop path.
:::

前缀段是**全局段**，与一个被通告的前缀关联。它的指令是"**沿 ECMP 感知的最短路径，把流量引导到这个段所关联的前缀**"。从网络中任何位置出发，以某个前缀段为活动段的报文都会沿 ECMP 感知的最短路径转发，朝向通告该前缀的节点。这条路径通常是**多跳**的。

:::en
The prefix segment is a fundamental building block of SR because of its very interesting properties: it is global; all nodes in the SR domain know what to do with packets that have a prefix segment as the active segment. it is multi-hop; a single segment spans multiple hops in the path, reducing the number of segments needed for a path and allowing to exercise equal-cost paths that span multiple hops. it is ECMP-aware; it natively uses all equal-cost paths which are widely prevalent in typical IP.
:::

前缀段是 SR 的基础积木，原因在于它有三个很有价值的属性：

| 属性 | 含义 | 工程意义 |
|---|---|---|
| **Global（全局）** | SR 域内所有节点都知道怎么处理以该前缀段为活动段的报文 | 不需要每台节点单独配置，靠 IGP 共识 |
| **Multi-hop（多跳）** | 一个段跨越路径上的多跳，减少一条路径所需的段数，并能利用跨多跳的等价路径 | 6 条 uSID 就能走完很长的路径 |
| **ECMP-aware（等价多路径感知）** | 原生使用典型的 IP 网络中广泛存在的所有等价路径 | 不需要像 MPLS 那样额外做熵标签 |

:::en
The prefix segment follows the shortest path to the prefix associated with the segment. More generally, this should be "follows the path as computed by the applied algorithm." By default, the applied algorithm is Dijkstra's Shortest Path First (SPF) algorithm, using the IGP link metric as link cost. The outcome of that algorithm is the well-known IGP shortest path.
:::

前缀段沿"该段所关联前缀的最短路径"转发。更一般地说，应该是"**按所应用的算法计算出的路径**"转发。默认应用的算法是 Dijkstra 最短路径优先（SPF），以 IGP 链路度量作为代价，其结果就是众所周知的 IGP 最短路径。

:::en
However, the SR architecture offers the instrumentation to deviate from that by associating a specific algorithm with each Prefix-SID. The first algorithm that is specified, as well as the default algorithm, is the well-known IGP shortest path algorithm. Using flexible algorithms, a user can define their own algorithm and associate that with a Prefix-SID. The prefix segment is called the "Endpoint behavior" in SRv6, but commonly referred to as uN in SRv6 uSID terminology. The prefix associated with the Prefix-SID is the SRv6 locator prefix.
:::

不过 SR 架构提供了偏离这一默认行为的机制：为每个 Prefix-SID 关联一个**特定算法**。第一个被标准化的算法（也是默认算法）就是众所周知的 IGP 最短路径算法；借助**灵活算法（Flex-Algo）**，用户可以定义自己的算法并关联到 Prefix-SID 上。在 SRv6 中，前缀段对应的行为称为 Endpoint 行为（简称 **End**），在 uSID 术语里常写作 **uN**。与前缀段关联的前缀就是 **SRv6 locator 前缀**。

**Adjacency Segment（邻接段）**

:::en
An adjacency segment (commonly referred to as "Adjacency-SID," or even "Adj-SID") is a segment that is associated with a unidirectional adjacency or set of unidirectional adjacencies. The instruction of an adjacency segment is to "steer traffic out of the link(s) of the adjacency(ies) associated with this segment." The traffic on this adjacency segment is steered on the link regardless of shortest path routing.
:::

**邻接段**（常称 Adjacency-SID、Adj-SID）是与一条**单向邻接**（或一组单向邻接）关联的段。其指令是"**把流量从这个段关联的邻接链路送出**"。走在邻接段上的流量，**不管最短路径怎么算**，都必须走这条链路。

:::en
An adjacency segment is typically used to steer traffic to a neighbor node if the shortest path to that neighbor is not via that direct link. Otherwise, the prefix segment of that neighbor is generally preferred. The adjacency segment is called the "Endpoint with L3 cross-connect behavior" in SRv6, often referred to as uA in SRv6 uSID terminology.
:::

邻接段通常用在"到某个邻居的最短路径**不经过**这条直连链路"的场合，用来强制走那条直连；否则一般优先使用该邻居的前缀段。在 SRv6 中邻接段对应的行为是 Endpoint with L3 cross-connect（**End.X**），uSID 术语里写作 **uA**。

```
   Prefix 段 vs Adjacency 段

        ┌────┐   代价 10   ┌────┐
        │ 源 │────────────>│  B │   Prefix-SID(B)：走 IGP 最短路径
        └──┬─┘             └────┘
           │ 代价 100          ▲
           │                   │ 想走下面这条？
           ▼                   │ 用 Adj-SID(B via Eth3)
        ┌────┐  ───────────────┘
        │  C │
        └────┘

   一个段 = 一跳（Adjacency） 还是 多跳（Prefix）？
   TI-LFA 修复路径、强制绕行、跨域拼接都靠 Adjacency 段兜底
```

*图 2-3：Prefix 段与 Adjacency 段的差别（按 2.1.7 节描述绘制）*

{{FIG|02/fig-2-3-prefix-adj|图 2-3 · 矢量版|Prefix 段多跳且 ECMP 感知，Adjacency 段钉死一跳，强制绕行与 TI-LFA 靠后者。}}

### 2.1.8 业务段：L3VPN per-VRF Segment

:::en
Various segment types are related to services. In this introduction, we give one example: an L3VPN service segment.
:::

还有多类段与业务相关。本节只给一个例子：**L3VPN 业务段**。

:::en
An L3VPN per-VRF segment is associated with a specific customer or tenant VRF. The instruction of this segment type is to "decapsulate the inner packet, perform a prefix lookup in the associated FIB table, and forward the inner packet accordingly." This is equivalent to the per-VRF VPN label in MPLS (RFC 4364).
:::

**L3VPN per-VRF 段**与某个特定客户（或租户）的 VRF 关联。这类段的指令是"**解封装内层报文，在关联的 FIB 表中做前缀查找，并按结果转发内层报文**"。它等价于 MPLS 中的 per-VRF VPN 标签（RFC 4364）。

:::en
The IPv4 L3VPN per-VRF segment, as an example, is called the End.DT4 SID in SRv6—with "4" for IPv4—but it is commonly referred to as uDT4 in SRv6 uSID terminology.
:::

以 IPv4 的 L3VPN per-VRF 段为例，它在 SRv6 中称为 **End.DT4** SID（"4"代表 IPv4），在 uSID 术语里常写作 **uDT4**。

## 2.2 SRv6 让 IPv6 自足

:::en
The networking industry today is fundamentally built on IP technology. IPv4, specified in 1981 (RFC 791), is still widely used but has limited capabilities to be extended to support new applications. As a result, various additional protocols have been deployed alongside IPv4 to support these applications. Notable examples include MPLS, used for VPN and TE, and VxLAN, used to extend layer 2 networks over a layer 3 infrastructure. In addition, the industry has built hacks to overcome the existing limitations, such as the lack of entropy for ECMP load-balancing.
:::

今天的网络产业从根本上建立在 IP 技术上。1981 年标准化的 IPv4（RFC 791）仍被广泛使用，但它的可扩展能力有限，难以支撑新应用。结果是业界在 IPv4 旁边叠加了各种附加协议：MPLS 用于 VPN 与流量工程，VxLAN 用于把二层网络延伸到三层基础设施之上。此外，为了绕过既有局限（例如 ECMP 负载分担缺少熵），业界还造了不少"补丁"式做法。

:::en
But, why should IP rely on additional layers like MPLS or UDP/VxLAN? Ideally, IP should be self-sufficient. Unlike IPv4, IPv6 has all the built-in capabilities to become self-sufficient. This book explores what SRv6 adds to IPv6 to achieve this goal. Obviously, IPv6 can encapsulate upper-layer protocols such as UDP and TCP. It can also natively encapsulate IPv4, IPv6 packets, allowing it to transport service traffic across the SR domain.
:::

但 IP 为什么要依赖 MPLS、UDP/VxLAN 这类附加层？理想情况下，**IP 应当是自足的**。与 IPv4 不同，IPv6 具备成为自足协议所需要的全部内建能力。本书探讨的正是 SRv6 给 IPv6 增加了什么，从而达成这一点。IPv6 显然可以封装 UDP、TCP 等上层协议，也能原生封装 IPv4、IPv6 报文，从而在 SR 域内传输业务流量。

:::en
SRv6 leverages IPv6 as its underlying data plane. This means that SRv6 utilizes the existing IPv6 infrastructure to implement segment routing, making it inherently compatible with any IPv6-capable device.
:::

SRv6 以 IPv6 作为底层数据面。这意味着 SRv6 利用现有的 IPv6 基础设施来实现段路由，因而**天生与任何支持 IPv6 的设备兼容**。

:::en
One of the most significant advancements that SRv6 introduces is Network Programming. SRv6 allows for the definition of network instructions directly within the IPv6 packet header. These instructions dictate specific actions that must be performed on the packet as it traverses the network. This level of programmability enables more dynamic and flexible network behaviors, such as traffic engineering, service chaining, and network slicing, without the need for additional protocols or complex configurations.
:::

SRv6 带来的最重要的进步之一是**网络编程**。SRv6 允许**直接在 IPv6 报文头里定义网络指令**，这些指令规定报文穿越网络时必须执行的具体动作。这种可编程性带来了更动态、更灵活的网络行为——流量工程、服务链、网络切片都不再需要额外协议或复杂配置。

:::en
IPv6 addresses are 128 bits long. SRv6 uses this space to encode the segment identifiers. SRv6 uSID (micro-segments), allows encoding up to six 16-bit micro-instructions within a single IPv6 address. If more than six instructions are needed for a packet, the additional instructions can be encoded in the Segment Routing Header (SRH).
:::

IPv6 地址长 128 位，SRv6 就用这段空间来编码段标识符。SRv6 uSID（微段）可以在**单个 IPv6 地址内编码最多 6 条 16 位微指令**。如果一个报文需要超过 6 条指令，多出来的指令可以编码进 Segment Routing Header（SRH）。

:::en
The SRH is a type of Routing Header, an extension header defined in the IPv6 specification (RFC 8200). A typical SRv6 packet does not contain an SRH, as in most of the use-cases less than six uSIDs are required. Section 2.5 delves more into the SRH.
:::

SRH 是一种 Routing Header，属于 IPv6 规范（RFC 8200）定义的扩展头。**典型的 SRv6 报文并不包含 SRH**，因为大多数用例所需的 uSID 少于 6 条。2.5 节会深入讨论 SRH。

:::en
uSID's implementation is possible thanks to one of the most well-known building blocks in a router: the IP Longest Prefix Match. A node installs a local micro-segment in the forwarding table with a prefix length that is long enough to identify the local micro-segment. The node does not interpret the remaining part of the address; therefore it can be used to include other information such as the next instruction to be executed.
:::

uSID 之所以能实现，靠的是路由器中最广为人知的基本模块：**IP 最长前缀匹配**。节点在转发表里安装一条本地微段，其前缀长度足以标识这条微段；节点**不解释地址剩余的部分**，因此剩余位可以用来携带其他信息，比如下一条待执行的指令。

:::en
This fundamental IP forwarding block enables various interesting capabilities. If the destination address contains a sequence of local micro-segments, such as a uN (Prefix-SID) + uA (Adjacency-SID), they can be processed in one lookup by programming the forwarding entry with the prefix and length containing both micro-segments.
:::

这个基础 IP 转发模块带来了一些很有价值的特性。如果目的地址中包含一串**本地**微段（例如 uN 前缀段 + uA 邻接段），只要把转发表项的前缀与其长度设置为**同时覆盖这两条微段**，就能**一次查表处理两条指令**。

:::en
It also enables concurrent utilization of micro-segments of different sizes, such as 16-bit micro-segments for topological instructions and 32-bit micro-segments to identify L2 Pseudowires (VPWS) of a large-scale L2VPN PE.
:::

它还支持**不同长度的微段并存**：例如 16 位微段用于拓扑指令，32 位微段用于标识大规模 L2VPN PE 上的二层伪线（VPWS）。

:::en
In addition, like in classic IP networks, the IP longest prefix match allows for IP prefix summarization. This leads to significant scalability gains and allows for more nodes within each domain. This is one of the most relevant benefits compared to MPLS networks, as reported by Bell Canada.
:::

此外，与经典 IP 网络一样，最长前缀匹配允许**IP 前缀汇总**。这带来显著的扩展性收益，也让每个域内可以容纳更多节点——这是相比 MPLS 网络最有价值的优势之一（Bell Canada 也这样报告）。

:::en
IPv6 includes a Flow Label field in its base header, which serves as an entropy source. This simplifies the load-balancing of packets by not requiring deep packet inspection to find the necessary flow identifiers for proper load balancing and providing hardware friendly entropy (i.e., it is located at a shallow position with a fixed offset). This finally solves a long-standing problem in MPLS networks.
:::

IPv6 的基本头里带有 **Flow Label** 字段，可作为熵源。它简化了报文的负载分担：不必做深度报文检测（DPI）去找流的标识，而且熵值对硬件友好（位置靠前、偏移固定）。这终于解决了 MPLS 网络中一个长期存在的问题。

封装开销的对比（按书中 2.2 与 2.4 节数据整理）：

| 封装方式 | 头部字节 | 说明 |
|---|---|---|
| SRv6 + 6 条 uSID | 40（外层 IPv6，DA 内含 6 条微指令） | 不需要 SRH |
| SRv6 + 6 条非压缩 SID | 40 + 8 + 6×16 = 144 | SRH 多出 88 字节（4+4+5×16） |
| IPv6 / VxLAN | 40 + 8（UDP）+ 8（VXLAN 头）= 56 | 还带内层以太网 14 字节 |

:::en
SRv6 simplifies the network architecture by reducing the need for multiple overlay protocols. Instead of relying on MPLS, VxLAN, or other tunneling mechanisms, SRv6 can achieve superior functionalities while reducing the cost. For example, the overhead in bytes of SRv6 encapsulation is smaller than IPv6/VXLAN while offering superior capabilities (e.g., Traffic Engineering or Service Chaining across domains).
:::

SRv6 通过减少对多种 overlay 协议的需求来简化网络架构。它不必依赖 MPLS、VxLAN 或其他隧道机制，就能实现更强的功能且成本更低。例如，SRv6 封装的**字节开销比 IPv6/VXLAN 更小**，却能提供更强能力（如跨域的流量工程或服务链）。

:::en
This simplification does not come at the cost of functionality. On the contrary, SRv6 enhances the network with additional features such as improved scalability, better traffic engineering, and more efficient use of network resources. Encoding multiple SIDs within a single packet allows for complex routing decisions and service chains to be implemented with minimal overhead.
:::

这种简化并没有以牺牲功能为代价。相反，SRv6 还给网络增加了新特性：更好的扩展性、更强的流量工程、更高效的资源利用。在**单个报文中编码多个 SID**，使得复杂的路由决策与服务链可以以极小的开销实现。

:::en
Using the IP data plane brings back the inherent benefits tied to IP. All network devices have an IP implementation, making it the universally applicable transport method. This eliminates the need for per-domain-type add-on protocols. This has resulted in significant cost-savings as it allows to remove gateways at domain boundaries, which is often a cause of scaling and reliability issues.
:::

使用 IP 数据面，把 IP 与生俱来的好处重新拿了回来。所有网络设备都有 IP 实现，因此 IP 是普遍适用的传输方式；这消除了"每种域都需要附加协议"的需求。它带来的显著成本节省在于可以**移除域边界上的网关**——这些网关往往是扩展性和可靠性的问题源头。

:::en
SRv6 elevates IPv6 to a new level, meeting and often surpassing the expectations set by traditional IP networking. By integrating network programming capabilities directly into the IPv6 protocol, SRv6 delivers services with superior functionalities and flexibility. The elimination of additional layers and protocols reduces complexity and operational costs. At the same time, the inherent scalability of IPv6, combined with the programmability of SRv6, ensures that the network can grow and adapt to future demands.
:::

SRv6 把 IPv6 提升到了一个新层次，达到了、而且常常超越了传统 IP 网络的预期。通过把网络编程能力直接集成进 IPv6 协议，SRv6 以更强的功能和灵活性提供服务；消除附加层与附加协议降低了复杂度与运维成本。同时，IPv6 固有的可扩展性与 SRv6 的可编程性结合，保证网络可以增长并适应未来需求。

:::en
This positions SRv6 as a more efficient and cost-effective solution than IPv4 and its supplementary layers, making it a compelling choice for modern network architectures.
:::

这使得 SRv6 成为比"IPv4 加各种补充层"更高效、更具成本效益的方案，从而是现代网络架构的有力选择。

## 2.3 SRv6 Segment ID（SID）

### 2.3.1 定义与处理

:::en
An SRv6 Segment Identifier (SID) is defined as an IPv6 address explicitly associated with a segment, as per RFC 8402. When an SRv6 SID is placed in the Destination Address field of an IPv6 packet header, it is routed through transit nodes in an IPv6 network like any other IPv6 address.
:::

按 RFC 8402 的定义，SRv6 的 **SID 是一个与某个段显式关联的 IPv6 地址**。当 SRv6 SID 被放进 IPv6 报文头的目的地址字段时，它在 IPv6 网络中就像任何普通 IPv6 地址一样被中转节点路由。

:::en
The SRv6 segment endpoint node creates Forwarding Information Base (FIB) entries for its local SIDs. When an SRv6-capable node receives an IPv6 packet, it performs an IP longest prefix match lookup on the packet's destination address. This lookup returns the action associated with the locally instantiated SRv6 SID.
:::

SRv6 端点节点为它的**本地 SID** 创建 FIB 表项。当支持 SRv6 的节点收到 IPv6 报文时，对报文的目的地址做**最长前缀匹配**查找，这次查找返回与该本地实例化 SID 关联的动作。

注意这里存在的跨度：**中转节点只做纯 IP 转发（不看 SRH、不看 SID 语义），只有匹配到本地 SID 的节点才进入"执行指令"模式**。这也是"Transit 节点不必支持 SRv6"的原因。

### 2.3.2 SID 格式

:::en
As specified in RFC 8986, section 3.1, the format of an SRv6 SID comprises three parts: LOC:FUNCT:ARG. Here, a locator (LOC) is encoded in the L most significant bits of the SID, followed by F bits for the function (FUNCT) and A bits for arguments (ARG).
:::

按 RFC 8986 第 3.1 节，SRv6 SID 的格式由三部分组成：**LOC:FUNCT:ARG**。其中 locator（LOC）编码在 SID 的最高 L 位，其后是 F 位的 function（FUNCT），再后面是 A 位的 arguments（ARG）。

```
    RFC 8986 §3.1 的 SID 位格式

    0                   1                   2                   3
    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |                                                               |
   +                          Locator (L bits)                    +
   |                                                               |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |            Function (F bits)          |      Arguments (A)    |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |                    Arguments 续 / 补零至 128 位                 |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

   书中示例：L=48, F=16, A=0
   fc00:0:5:eeee::  →  fc00:0:5:: /48 (locator) + eeee (function)
   未用的位补 0，使整个 SID 恰好构成一个合法的 /128 地址
```

*图 2-4：SRv6 SID 的 LOC:FUNCT:ARG 结构（按 RFC 8986 §3.1 与 2.3.2 节绘制）*

{{FIG|02/fig-2-4-loc-funct-arg|图 2-4 · 矢量版|SRv6 SID 的 LOC:FUNCT:ARG 位布局，以及 48/16/0 的示例切分。}}

:::en
The locator encodes the parent node instantiating the SID. The function is an opaque identifier of the local behavior bound to the SID. The arguments, only used in some particular cases, provide information required for processing that specific Endpoint behavior.
:::

**locator** 编码的是实例化该 SID 的父节点；**function** 是绑定到这个 SID 的本地行为的**不透明标识**（路由器不必知道外部怎么解释它）；**arguments** 只在某些特定场景使用，提供处理该特定端点行为所需的信息。

:::en
L, F, and A values are flexible, provided their total length (L+F+A) does not exceed 128 bits. If L+F+A is less than 128 bits, the ARG is followed by enough zero bits to fill the 128-bit SID. Such an SRv6 SID is assigned to a node within a prefix defined as a locator of length L.
:::

L、F、A 的取值是灵活的，只要总长度（L+F+A）不超过 128 位。如果小于 128 位，则 ARG 之后补足够多的 0 位填满 128 位 SID。这样的 SRv6 SID 被分配给"长度为 L 的 locator 前缀"所定义的那台节点。

:::en
Typically, the locator is routed throughout the entire network. This allows any transit node to forward the packet destined for an SRv6 SID to the node identified by the SID's locator (RFC 7608).
:::

通常 locator 会在**整个网络**中路由（IGP 通告）。这使得任何中转节点都能把"目的地址为某个 SRv6 SID"的报文，转发到该 SID 的 locator 所标识的节点（RFC 7608）。

## 2.4 微段（uSID）

:::en
A computer program generally comprises several instructions. An instruction, in turn, can itself be a micro-program composed of several micro-instructions. Similarly, in SRv6, any network instruction (in the destination address (DA) or the SRH) can "contain" a micro-program of up to six micro-instructions. A micro-program is contained in an SRv6 SID. A micro-instruction is referred to as a uSID.
:::

一段计算机程序通常由若干条指令组成；而一条指令本身，又可以是由多条**微指令**组成的微程序。类似地，在 SRv6 中，任何一条网络指令（位于目的地址 DA 或 SRH 中）都可以"容纳"一个最多含 **6 条微指令**的微程序。微程序包含在一个 SRv6 SID 中，其中的一条微指令称为 **uSID**。

:::en
A 128-bit SRv6 instruction that contains a micro-program is called a container instruction or container SID and has the structure shown in Figure 2.1.
:::

包含微程序的 128 位 SRv6 指令称为**容器指令（container instruction）**或**容器 SID**，结构如图 2.1 所示。

:::en
Within the SR domain, the operator allocates a prefix, the uSID block, represented in the figure as BBBB:BBBB, where each B is a nibble (4 bits). The prefix can be allocated from a public or private range. Today, this block is 32 bits long. A uSID container always starts by a uSID block. Multiple uSID blocks can be used across the network, however all the uSIDs in the same uSID container must share the same uSID block.
:::

在 SR 域内，运营商会分配一个前缀，称为 **uSID block**（图中记为 `BBBB:BBBB`，每个 B 是一个 nibble 即 4 位）。这个前缀可以从公网或私有地址段分配。目前该 block 长 **32 位**。一个 uSID 容器**总是以 uSID block 开头**。网络中可以使用多个 uSID block，但**同一个 uSID 容器内的所有 uSID 必须共享同一个 uSID block**。

:::en
The uSID container contains up to six 16-bit uSIDs, represented in the figure as 000N. If the micro-program contains less than six uSIDs, any unused micro-instruction is set to the value 0000, known as "End-of-Container".
:::

容器里最多包含 **6 个 16 位 uSID**（图中记为 `000N`）。如果微程序不足 6 条，未使用的微指令位置填 `0000`，称为 **End-of-Container（容器结束）**。

```
    Figure 2.1 重绘：128 位 uSID 容器内的 6 条微指令

   bit 0                                                          127
        +------------+--------+--------+--------+--------+--------+--------+
        | uSID Block | uSID 1 | uSID 2 | uSID 3 | uSID 4 | uSID 5 | uSID 6 |
        |   32 bit   | 16 bit | 16 bit | 16 bit | 16 bit | 16 bit | 16 bit |
        +------------+--------+--------+--------+--------+--------+--------+
        | BBBB:BBBB  |  0002  |  0003  |  0004  |  0000  |  0000  |  0000  |
        |            |   uN   |   uA   |  uDT4  |  EoC   |  EoC   |  EoC   |
        +------------+--------+--------+--------+--------+--------+--------+

        文本写法：fc00:0000:0002:0003:0004:0000:0000:0000
        （IPv6 每 16 位一组，正好 8 组 = 32 位 block + 6 组 uSID）
```

*图 2-5：网络程序在 128 位 uSID 容器中的编码（按原书 Figure 2.1 重绘）*

{{FIG|02/fig-2-5-usid-container|图 2-5 · 矢量版|128 位 uSID 容器：32 位 block 加 6 条 16 位微指令，未用槽位填 End-of-Container（0000）。}}

### 2.4.1 Shift and Forward（位移转发）

:::en
The key packet processing operation for uSIDs at each of the SR Endpoints is shift and forward. This operation has been designed with hardware efficiency in mind since bit shifting is a basic operation.
:::

uSID 在每个 SR 端点上的关键处理动作是 **shift and forward（位移转发）**。这个操作在设计时就考虑到了硬件效率——**位移是芯片最基本的能力**。

:::en
Figure 2.2 illustrates this operation. The uSID fc00:0000:0002:: is instantiated as a uN on Node 2. A source node sends a packet with the uSID container fc00:0000:0002:0003:0004::, containing three uSIDs. The 4th, 5th, and 6th uSID positions in the container are unused and set to the End-of-Container value 0000. All routers forward this packet along the shortest path to prefix fc00:0000:0002::/48, Node 2's locator prefix.
:::

图 2.2 说明了这个操作。uSID `fc00:0000:0002::` 在节点 2 上被实例化为一个 uN。源节点发出的报文携带 uSID 容器 `fc00:0000:0002:0003:0004::`，其中包含 3 条 uSID；第 4、5、6 个位置未使用，填 End-of-Container 值 `0000`。所有路由器都把这个报文按到前缀 `fc00:0000:0002::/48`（节点 2 的 locator）的最短路径转发。

:::en
When the packet arrives at Node 2, this node performs an IP longest prefix match on the destination address, and finds that it matches the local uN SID fc00:0000:0002::. Node 2 then performs the shift-and-forward operation on the packet, as illustrated in Figure 2.2.
:::

报文到达节点 2 后，节点 2 对目的地址做最长前缀匹配，发现匹配本地 uN SID `fc00:0000:0002::`，于是执行 shift-and-forward 操作。

:::en
The shift-and-forward operation first shifts the part of the IPv6 destination address after the block by 16 bits to the left, transforming the destination address into fc00:0000:0003:0004::. The 16 bits that are shifted out to the left, 0002 in this example, are lost. The 16 bits that are shifted in from the right are filled with the End-of-Container value 0000.
:::

位移转发操作把 IPv6 目的地址中 **block 之后的部分整体左移 16 位**，将目的地址变成 `fc00:0000:0003:0004::`。从左侧挤出的 16 位（本例中的 `0002`）被丢弃；从右侧补进来的 16 位填 End-of-Container 值 `0000`。

:::en
Node 2 then looks up the updated destination address in its forwarding table. It matches fc00:0000:0003::/48, the locator advertised by Node 3. Node 2 forwards the packet accordingly.
:::

节点 2 随后用更新后的目的地址查转发表，匹配到 `fc00:0000:0003::/48`（节点 3 通告的 locator），据此把报文转发出去。

| 步骤 | IPv6 DA（8 组 16 位） | 谁在处理 |
|---|---|---|
| 源节点发出 | `fc00:0000:0002:0003:0004:0000:0000:0000` | 源封装 |
| 途中转发 | 不变（按 /48 查表） | Transit（纯 IP） |
| 节点 2 命中 uN 后位移 | `fc00:0000:0003:0004:0000:0000:0000:0000` | Node 2（End/uN） |
| 节点 3 命中 uN 后位移 | `fc00:0000:0004:0000:0000:0000:0000:0000` | Node 3（End/uN） |
| 节点 4 交付业务 SID | 已在 DA 中，执行 End.DT4 解封装 | Node 4/5 |

*图 2-6：原书 Figure 2.2 重绘——每跳只左移 16 位，指针自然指向下一条指令*

{{FIG|02/fig-2-6-usid|图 2-6 · 矢量版|uSID 容器的逐跳左移：Block 全程不变，容器每跳左移 16 bit，右侧补 0000。}}


这个设计最妙的地方：**没有任何"读指针"需要维护**。MPLS 靠标签栈顶指针（栈操作），SRH 靠 Segments Left（需要读写 SRH），而 uSID 的"当前位置"就是**DA 里 block 之后的第一条非零 uSID**——位移一次，指针自动前进一格。

### 2.4.2 一次查多个 uSID

:::en
In this example, Node 2 matched on a single local uSID (fc00:0000:0002::/48), but in other scenarios it could match multiple uSIDs in a single lookup, leveraging the power of the IP longest prefix match functionality. Typical examples include a uN followed by uA (Adjacency-SID), or a uN followed by a uDT* (VPN Per-VRF uSID). This is a significant advantage over MPLS, which can only look up a single label at a time.
:::

在这个例子里，节点 2 只匹配了一条本地 uSID（`fc00:0000:0002::/48`）；但在其他场景下，它可以借助最长前缀匹配**一次匹配多条 uSID**。典型例子是 uN 后面紧跟 uA（邻接段），或者 uN 后面紧跟 uDT*（VPN per-VRF uSID）。这是相对 MPLS 的显著优势——MPLS 一次只能查一个标签。

:::en
By leveraging the IP longest prefix match functionality, the node cannot only match two local uSIDs in one lookup, it also allows combinations of different uSID sizes. Large-scale L2VPN VPWS deployments can benefit from this by combining 32-bit uSIDs to identify VPWS service, with 16-bit uSID for topological instructions.
:::

借助最长前缀匹配，节点不仅能**一次查两条本地 uSID**，还允许**不同长度的 uSID 混用**。大规模 L2VPN VPWS 部署正受益于此：用 32 位 uSID 标识 VPWS 业务，用 16 位 uSID 表达拓扑指令。

```
   两次语义、一次查表：uN + uA 的组合项

   转发表里直接装：fc00:0000:0002:0003::/64  →  "从 Eth3 出去，并位移 32 位"
                  （前缀长度覆盖两条 uSID，一次命中，省一次流水线）

   对比 MPLS：交换芯片一次只能看栈顶一个标签
              → "pop 一个再看下一个" 需要两轮查表
```

*图 2-7：uN+uA 单次查表（按 2.4.2 节描述绘制）*

{{FIG|02/fig-2-7-un-ua-lookup|图 2-7 · 矢量版|一条 /64 表项同时覆盖 uN 与 uA，对比 MPLS 一次只能看栈顶一个标签。}}

### 2.4.3 压缩与未压缩的头部开销

:::en
By now, you may see the huge benefits that uSID provides. It allows encoding a network program of six instructions into a single uSID container within the IPv6 destination address. Figure 2.3 compares the header sizes using uncompressed SIDs versus using uSIDs, showing substantial packet size savings. Encoding six uncompressed SIDs in the packet header adds 88 bytes (= 4 + 4 + 5 × 16) more header overhead compared to using six uSIDs.
:::

到这里应该能看出 uSID 的巨大好处：它能把 6 条指令组成的网络程序编码进 IPv6 目的地址中的**一个容器**里。图 2.3 对比了未压缩 SID 与 uSID 的头部大小，显示报文体积有可观的节省。在报文头中编码 6 条未压缩 SID，会比用 6 条 uSID **多出 88 字节**（= 4 + 4 + 5 × 16）的头部开销。

```
    Figure 2.3 重绘：6 条 uSID vs 6 条非压缩 SID

   ── uSID（压缩）────────────────────────────────────────
   | IPv6 头 40B | DA 里塞 6×16bit |           载荷          |
   ↑ 无 SRH，总开销 40 字节

   ── 非压缩 SID ────────────────────────────────────────
   | IPv6 头 40B | SRH 头 | SID[0..5] 6×16B |    载荷       |
                          ↑ 96 字节 SID 列表 + 8 字节 SRH 固定头

   差额 = 96 + 8 - 16（DA 本来就有）= 88 字节
   按 1280 字节 MTU 算，单包头部占比从 ~3% 抬到 ~10%
```

*图 2-8：压缩 SID 列表与未压缩 SID 列表的头部对比（按原书 Figure 2.3 与 2.4.3 节数据重绘）*

{{FIG|02/fig-2-8-header-overhead|图 2-8 · 矢量版|6 条 uSID 与 6 条非压缩 SID 的头部开销：相差 88 字节，MTU 1280 时占比 3% 对 10%。}}

## 2.5 Segment Routing Header（SRH）

:::en
When introducing SRv6, the Segment Routing Header (SRH) is often one of the first topics discussed. However, in practice, the SRH is rarely used. Most use cases do not require an SRH in the packet header because six uSIDs that can be inserted in the IPv6 Destination Address field is sufficient for most of the use cases. Nonetheless, you may encounter the SRH in specific situations, such as when using TI-LFA.
:::

讲 SRv6 的时候，SRH 往往是第一批被讨论的话题。但**在实践中 SRH 很少用到**：大多数用例不需要报文头里出现 SRH，因为 6 条 uSID 塞进 IPv6 目的地址字段已经够用。不过在特定场景——例如 TI-LFA——你确实会遇到 SRH。

:::en
Since the SRH is an integral part of the SRv6 architecture, it is important to understand its functionalities and how it is processed.
:::

由于 SRH 是 SRv6 架构不可分割的一部分，理解它的功能与处理方式仍然重要。

:::en
The SRH is a type of Routing Header as defined in the IPv6 specification (RFC 8200). An IPv6 source uses the Routing Header to list one or more intermediate "segments" to be "visited" on the way to a packet's destination. The Routing Header is identified by a Next Header field value of 43 in the immediately preceding header.
:::

SRH 是 IPv6 规范（RFC 8200）定义的一种 **Routing Header**。IPv6 源节点用 Routing Header 列出报文在去往目的地途中需要"访问"的一个或多个中间"段"。Routing Header 由**紧邻其前一个头部的 Next Header 字段值为 43** 来标识。

### 2.5.1 Routing Header 通用格式

```
    Figure 2.4 重绘：RFC 8200 的 Routing Header 通用格式

    0                   1                   2                   3
    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |  Next Header  | Hdr Ext Len   |  Routing Type | Segments Left |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |                                                               |
   .                     Type-specific Data                       .
   |                                                               |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

*图 2-9：IPv6 Routing Header 通用格式（按原书 Figure 2.4 重绘，RFC 8200 §4.4）*

{{FIG|02/fig-2-9-rh-generic|图 2-9 · 矢量版|Routing Header 通用格式：前 32 位的四个字段被 SRH 完全复用。}}

| 字段 | 长度 | 含义 |
|---|---|---|
| Next Header | 8 bit | 标识紧跟 Routing Header 之后的头部类型 |
| Hdr Ext Len | 8 bit | Routing Header 的长度，以 8 字节为单位 |
| Routing Type | 8 bit | Routing Header 变体的标识（IANA 登记）；**SRH 的值为 4** |
| Segments Left | 8 bit | 到达最终目的地前**还剩多少个段**要访问 |
| Type-specific Data | 可变 | 由 Routing Type 决定大小与格式 |

### 2.5.2 SRH 格式

:::en
The Segment Routing Header format is specified in RFC 8754. Since it is a type of Routing Header, it adheres to the Routing Header format, with the first 32 bits of the SRH matching those in the Routing Header format.
:::

SRH 的格式在 RFC 8754 中规定。由于它属于 Routing Header，因此遵循 Routing Header 的格式——SRH 的**前 32 位与通用 Routing Header 完全一致**。

```
    Figure 2.5 重绘：RFC 8754 的 SRH 格式

    0                   1                   2                   3
    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   | Next Header   | Hdr Ext Len   | Routing Type=4| Segments Left |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   | Last Entry    |    Flags      |              Tag              |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |                                                               |
   |              Segment List[0]  (128-bit IPv6 address)          |
   |                                                               |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |                            ......                             |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |              Segment List[n]  (128-bit IPv6 address)          |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |                  Optional TLVs (variable)                     |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

   注意：Segment List 是倒序存放的
        [0] = 最后一站，[n-1] = 第一站
```

*图 2-10：SRH 格式（按原书 Figure 2.5 重绘，RFC 8754 §2）*

{{FIG|02/fig-2-10-srh|图 2-10 · 矢量版|SRH 头部字段与位宽：四个对字段、Last Entry/Flags/Tag，其下是 128 位的 Segment List。}}


:::en
The first four fields are common to all Routing Headers and are specified in RFC 8200, section 4.4: Next Header identifies the type of header that immediately follows the SRH in the packet; Hdr Ext Len indicates the length of the SRH header in 8-octet units; Routing Type is set to 4, indicating the Routing Type for SRH; Segments Left represents the number of segments that remain in the Segment List.
:::

前四个字段是所有 Routing Header 共有的，在 RFC 8200 第 4.4 节规定：**Next Header** 标识紧跟在 SRH 之后的头部类型；**Hdr Ext Len** 以 8 字节为单位表示 SRH 长度；**Routing Type** 置为 4，标识这是 SRH；**Segments Left** 表示 Segment List 中还剩多少个段。

:::en
The remaining fields are specific to the SRH and are specified in RFC 8754: Last Entry contains the index (zero-based) of the last element of the Segment List. Note that the Segment List is encoded in reverse order. Therefore, this field represents the index of the first segment of the policy's segment list.
:::

其余字段是 SRH 专有的，定义在 RFC 8754 中。**Last Entry** 包含 Segment List 最后一个元素的索引（从 0 开始）。注意 Segment List 是**倒序编码**的，因此这个字段实际表示的是策略段列表里**第一个段**的索引。

:::en
Flags: One flag has been defined for SRH as of the time of writing: the OAM flag (O-flag) in bit position 2, as specified in RFC 9259, Operations, Administration, and Maintenance (OAM) in Segment Routing over IPv6 (SRv6).
:::

**Flags**：撰写本书时 SRH 只定义了一个标志——第 2 位的 **OAM flag（O-flag）**，由 RFC 9259（SRv6 的 OAM）规定。

:::en
Tag: Allows packets to be tagged as part of a specific class or group based on shared properties. Note that Tag is not used in the processing of SID behaviors defined in RFC 8986.
:::

**Tag**：允许按共享属性把报文标记为某个特定类别或组。注意 Tag 在 RFC 8986 定义的 SID 行为处理中**并不使用**。

:::en
Segment List[0...n – 1]: Consists of a series of 128-bit IPv6 addresses that represent the segments in the segment list. The segment list is encoded in reverse order, starting from the last segment of the policy's segment list. For example, Segment List[0] contains the last segment of the policy, Segment List[1] contains the penultimate segment, and so on.
:::

**Segment List[0...n-1]**：由一系列 128 位 IPv6 地址组成，代表段列表中的各个段。段列表按**倒序**编码，从策略段列表的**最后一个段**开始。例如 Segment List[0] 是策略的最后一个段，Segment List[1] 是倒数第二个段，依此类推。

:::en
Type Length Value (TLV): Provides metadata shared across functions. TLVs are ignored during SID processing unless specified by local configuration. When writing this book, only two TLVs have been defined: the HMAC TLV and padding TLV, which are defined in RFC 8754. Additionally, it is worth noting that there are no known implementations or deployments of these two TLVs at the time of writing.
:::

**TLV（Type-Length-Value）**：提供跨功能共享的元数据。除非本地配置明确要求，TLV 在 SID 处理过程中会被忽略。撰写本书时只定义了两个 TLV——HMAC TLV 与 padding TLV（RFC 8754），并且值得注意的是，**这两个 TLV 在当时没有任何已知的实现或部署**。

## 2.6 带 SRH 的报文处理

:::en
Nodes can assume different roles in SRv6 networks: SR Source node — Any node that originates an IPv6 packet with an SRv6 SID as destination address of the IPv6 header. Note that this packet may or may not contain an SRH. Transit node — Any node forwarding an IPv6 packet whose destination address does not match a locally configured segment. A transit node does not need to be SRv6-capable. SR Segment Endpoint node — Any node receiving an IPv6 packet whose destination address matches a locally configured segment. The node processes the local segment.
:::

节点在 SRv6 网络中承担不同角色：

| 角色 | 定义 | 是否需要支持 SRv6 |
|---|---|---|
| **SR Source node** | 任何以 SRv6 SID 作为 IPv6 头目的地址、发起 IPv6 报文的节点。该报文**可以带、也可以不带 SRH** | 需要 |
| **Transit node** | 任何转发的报文中，目的地址**不匹配**本地配置段的节点 | **不需要** |
| **SR Segment Endpoint node** | 任何收到报文且目的地址**匹配**本地配置段的节点，由它处理这个本地段 | 需要 |

:::en
Nodes can assume different roles, even multiple ones, simultaneously. For example, it can be the SR Source node on one path and a Transit or SR Segment Endpoint node on another.
:::

节点可以同时承担不同角色，甚至多种角色：例如在一条路径上是 SR Source，在另一条路径上是 Transit 或 SR Segment Endpoint。

:::en
This section describes the packet processing at the SR Source, Transit, and SR Segment Endpoint nodes for SRv6 packets with an SRH. For illustration purposes, the example in this chapter is unrealistic in three aspects: It uses SRH while not required. It uses a non-reduced SRH. No Penultimate Segment Popping (PSP) is applied on the packet.
:::

本节讲述带 SRH 的 SRv6 报文在 SR Source、Transit、SR Segment Endpoint 三类节点上的处理。为了讲清楚，本书的示例在三个方面是"不现实"的：**第一**，明明不需要 SRH 却用了 SRH；**第二**，用的是非 reduced 的 SRH；**第三**，没有对报文做倒数第二跳弹出（PSP）。

:::en
The network in Figure 2.6 contains five SRv6-enabled nodes (1, 2, 3, 4, and 5) and two classic non-SRv6 IPv6 nodes (12 and 34). The IPv6 address block fc00:0::/32 has been designated as the SID block. All the nodes within the domain will allocate SIDs within that range. The SRv6-enabled nodes each advertise in the IGP an SRv6 locator prefix fc00:0:N::/48, with N as the node number, and an End SID fc00:0:N:X::, with X as the function ID.
:::

图 2.6 的网络包含 **5 台支持 SRv6 的节点（1、2、3、4、5）**和**两台经典的非 SRv6 IPv6 节点（12、34）**。IPv6 地址块 `fc00:0::/32` 被指定为 SID block，域内所有节点都在这个范围内分配 SID。每台支持 SRv6 的节点在 IGP 中通告一个 SRv6 locator 前缀 `fc00:0:N::/48`（N 为节点编号），以及一个 End SID `fc00:0:N:X::`（X 为功能号）。

:::en
An IPv4 L3VPN service is established between nodes 1 and 5, and the service packets need to follow the path 1 → 2 → 3 → 4 → 5. Node 5 instantiates an L3VPN service SID fc00:0:5:eeee:: for this purpose.
:::

节点 1 与节点 5 之间建立了一条 IPv4 L3VPN 业务，业务报文需要走 **1 → 2 → 3 → 4 → 5** 这条路径。为此节点 5 实例化了一个 L3VPN 业务 SID `fc00:0:5:eeee::`。

```
    Figure 2.6 重绘（拓扑部分）

      ┌────┐   ┌────┐   ┌────┐   ┌────┐   ┌────┐
      │ 1  │───│ 2  │───│ 3  │───│ 4  │───│ 5  │
      │Source│  │End │   │End │   │End │   │End.DT4│
      └────┘   └────┘   └────┘   └────┘   └────┘
         │        │                  │        │
       ┌─┴─┐    ┌─┴─┐              ┌─┴─┐    ┌─┴─┐
       │10 │    │11 │              │12 │    │34 │   ← Transit（经典 IPv6，非 SRv6）
       └───┘    └───┘              └───┘    └───┘

    SID block : fc00:0::/32
    locator   : fc00:0:<N>::/48   （N = 节点号）
    End SID   : fc00:0:<N>:X::
    业务 SID  : fc00:0:5:eeee::   （End.DT4，仅节点 5 实例化）
```

*图 2-11：原书 Figure 2.6 的拓扑（按原文节点编号与 SID 规划重绘，23 号线路上有 ECMP 与 Transit 混跑）*

{{FIG|02/fig-2-11-topology|图 2-11 · 矢量版|原书 Figure 2.6 的拓扑：5 台 SRv6 节点加 4 台 Transit，标注 SID block、locator 与业务 SID。}}

:::en
It is important to mention that the SRH can contain a combination of compressed and non-compressed segments. It could very well be that the first element is a uSID container with six uSIDs, and the second element is a single SID used, for example, in the context of a public cloud.
:::

需要强调：**SRH 里可以混合压缩段与非压缩段**。完全可以是第一个元素为含 6 条 uSID 的容器，第二个元素为单个非压缩 SID（例如公有云场景中需要携带一个外部 SID）。

### 2.6.1 SR Source 节点

:::en
An SR Source node steers a packet into a policy. If the policy's segment list contains a single segment, and there is no need to add information to the SRH flag or add a TLV; the destination address is set to the single segment list entry, and the SRH may be omitted.
:::

SR Source 节点把报文引入一条策略。如果策略的段列表**只有一个段**，且不需要设置 SRH 标志位或添加 TLV，那么把目的地址设为这唯一的段即可，**SRH 可以省略**。

:::en
When needed, the SRH is created as follows (RFC 8754, section 4.1): The Next Header and Hdr Ext Len fields are set as specified in RFC 8200. The Routing Type field is set to 4. The first element of the SRH Segment List is the ultimate segment. The second element is the penultimate segment, and so on. The Last Entry field is set to n – 1, where n is the number of elements in the policy. The Segments Left field is set to n – 1. The destination address of the packet is set with the value of the first segment. The packet is forwarded toward the packet's destination address (the first segment).
:::

需要 SRH 时，按 RFC 8754 第 4.1 节创建：

1. `Next Header` 与 `Hdr Ext Len` 按 RFC 8200 的规定设置
2. `Routing Type` 设为 **4**
3. SRH Segment List 的**第一个元素是最后一个段**，第二个元素是倒数第二个段，依此类推（倒序）
4. `Last Entry` 设为 **n − 1**（n 为策略中段的个数）
5. `Segments Left` 设为 **n − 1**
6. 报文的**目的地址设为第一个段**
7. 报文朝着目的地址（也就是第一个段）转发出去

:::en
In our example, Node 1 is the SR Source node. The SID list to be applied on the packet is, in traversal order, < fc00:0:2:X::, fc00:0:3:X::, fc00:0:4:X::, fc00:0:5:eeee:: >. This SID list steers the packet from Node 1 to Node 2, then to Node 3, then to Node 4, and finally to the packet's destination Node 5. While the first three SIDs are End SIDs, the last SID is an End.DT4 SID. This is an L3VPN service SID that instructs Node 5 how to process this service packet.
:::

在我们的示例里，节点 1 是 SR Source。施加到报文上的 SID 列表按**遍历顺序**是 `< fc00:0:2:X::, fc00:0:3:X::, fc00:0:4:X::, fc00:0:5:eeee:: >`。这个列表把报文从节点 1 引到节点 2，再到节点 3，再到节点 4，最后到目的地节点 5。前三个 SID 都是 End SID，最后一个 SID 是 **End.DT4**——这是一个 L3VPN 业务 SID，指示节点 5 如何处理这个业务报文（详见第 6 章）。眼下只需知道：节点 5 必须**以该 SID 作为活动段**收到这个报文。

:::en
Node 1 follows the abovementioned procedure and sets the IPv6 header's Next Header field to 43 (Routing Header). The SRH Next Header field is set to 4 (IPv4), and the SRH Hdr Ext Len field to the appropriate value. The Routing Type field is set to 4 (SRH). The entries in the SRH Segment List are in the reverse traversal order. The first element (index 0) in the SRH Segment List is the ultimate segment fc00:0:5:eeee::. The second element (index 1) is the penultimate segment fc00:0:4:X::. The element after that (index 2) is fc00:0:3:X::, and the last element (index 3) is the first segment fc00:0:2:X::. The Last Entry and Segments Left fields are set to 4 – 1 = 3 since the policy's SID list has four elements (n = 4).
:::

节点 1 按上述流程操作：IPv6 头的 `Next Header` 设为 **43**（Routing Header）；SRH 的 `Next Header` 设为 **4**（表示内层是 IPv4），`Hdr Ext Len` 设为相应值；`Routing Type` 设为 4。Segment List 按倒序存放：索引 0 是最后一个段 `fc00:0:5:eeee::`，索引 1 是倒数第二段 `fc00:0:4:X::`，索引 2 是 `fc00:0:3:X::`，索引 3 是第一个段 `fc00:0:2:X::`。因为策略有 4 个段（n = 4），`Last Entry` 与 `Segments Left` 都设为 **3**。

:::en
Node 1 sets the IPv6 Destination Address field to the first segment fc00:0:2:X::. The node performs a FIB lookup for this destination address and finds that it matches fc00:0:2::/48 advertised by Node 2. Node 1 sets the IPv6 Source Address field to the loopback address fc00:0:1::1 allocated from the SRv6 locator prefix and forwards the packet towards Node 2.
:::

节点 1 把 IPv6 目的地址设为第一个段 `fc00:0:2:X::`，对该目的地址做 FIB 查找，命中节点 2 通告的 `fc00:0:2::/48`。同时把 IPv6 源地址设为从 SRv6 locator 前缀中分配的 loopback 地址 `fc00:0:1::1`，然后把报文转发向节点 2。

节点 1 发出的报文长这样：

```
   ┌──────────────────────── IPv6 头（40B）────────────────────────┐
   │ Version/TClass/FlowLabel │ Payload Len │ NH=43 │ Hop Limit=64  │
   │ SA = fc00:0:1::1                                              │
   │ DA = fc00:0:2:X::      ← 活动段（DA 里）              ★       │
   ├──────────────────────── SRH ──────────────────────────────────┤
   │ NH=4 │ Len │ Type=4 │ Segments Left = 3                        │
   │ Last Entry = 3 │ Flags = 0 │ Tag = 0                          │
   │ Segment List[0] = fc00:0:5:eeee::   （最后一站）               │
   │ Segment List[1] = fc00:0:4:X::                                 │
   │ Segment List[2] = fc00:0:3:X::                                 │
   │ Segment List[3] = fc00:0:2:X::      （第一站，与 DA 冗余）      │
   ├───────────────────────────────────────────────────────────────┤
   │ 内层 IPv4 业务报文                                             │
   └───────────────────────────────────────────────────────────────┘
```

*图 2-12：SR Source 封装结果（按 2.6.1 节示例与图 2.6 第一只报文描述重绘，★ 表示活动段）*

{{FIG|02/fig-2-12-sr-source-encap|图 2-12 · 矢量版|节点 1 封装出的报文：IPv6 头（NH=43、★ 活动段 DA）、SRH 四个 SID、内层 IPv4。}}

### 2.6.2 Transit 节点

:::en
A Transit node is any node that forwards an IPv6 packet whose destination address does not match a locally configured segment or a local interface. A transit node does not need to be SRv6-capable.
:::

**Transit 节点**是转发的报文中、目的地址既不匹配本地配置段、也不匹配本地接口的节点。Transit 节点**不需要支持 SRv6**。

:::en
As specified in RFC 8200, the only node allowed to inspect the Routing Header (and therefore the SRH) is the node identified in the Destination Address field of the IPv6 header. Any other transited node must not inspect the Routing Header and must forward the packet toward the destination address according to its classic IPv6 routing table.
:::

按 RFC 8200 规定，**唯一被允许检查 Routing Header（因而也就是 SRH）的节点，是 IPv6 头目的地址字段所标识的那个节点**。任何其他中转节点都**不得**检查 Routing Header，必须按经典 IPv6 路由表朝目的地址转发报文。

:::en
When a SID is in the destination address of an IPv6 header of a packet, it's routed through an IPv6 network as an IPv6 address. The network devices will route and forward the packet based on RFC 7608. The routers implement longest-match-first on prefixes of any valid length and ignore the part of the address that extends beyond the longest-match prefix.
:::

当 SID 位于报文的 IPv6 目的地址字段时，它就像普通 IPv6 地址一样在 IPv6 网络中被路由。网络设备按 RFC 7608 进行路由转发：路由器对**任意合法长度**的前缀做最长匹配优先，并**忽略超出最长匹配前缀的那部分地址**。

:::en
In Figure 2.6, the Transit nodes are represented using smaller circles, such as nodes 10, 11, and 12.
:::

在图 2.6 中，Transit 节点用更小的圆圈表示，例如节点 10、11、12。

"忽略超出最长匹配前缀的部分"这句话，正是 SRv6 转发面能如此简单的根源：Transit 只看 `/48`，后面 80 位是 uSID 还是垃圾，它**完全不关心**。

#### 2.6.2.1 高效负载分担

:::en
Several paths might have equal cost along the packet's journey from ingress PE to the egress PE. The transit nodes performs per-flow load-balancing between the ECMP paths leveraging the IPv6 Flow Label to do this optimally and efficiently.
:::

从入向 PE 到出向 PE 的途中，可能存在多条等价路径。Transit 节点在 ECMP 路径之间做 **per-flow 负载分担**，并利用 IPv6 Flow Label 以最优、最高效的方式完成。

:::en
The IPv6 Flow Label is a 20-bit field in the IPv6 header that provides entropy. The ingress PE, as part of the encapsulation of the customer packet, always computes a hash of the received packet, regardless of whether it is an IPv4 or IPv6 packet, or an Ethernet frame. The output of the customer packet hash is encoded within the IPv6 outer header Flow Label field.
:::

IPv6 Flow Label 是 IPv6 头中 **20 位**的字段，用来提供熵。入向 PE 在封装客户报文时，**总是**对收到的报文计算哈希——不管收到的是 IPv4 报文、IPv6 报文还是以太网帧。哈希结果被写入外层 IPv6 头的 Flow Label 字段。

:::en
The hash of the received customer packet header typically uses the 5-tuple consisting of the source and destination IP addresses, the transport layer protocol identifier and source and destination ports. However, in some specific scenarios, this hash also includes other fields, such as the GTP-U TEID in the case of mobility networks. In either case, all the packets belonging to the same flow will always have the same Flow Label value.
:::

对客户报文头的哈希通常使用**五元组**：源/目的 IP 地址、传输层协议号、源/目的端口。某些特定场景还会把其他字段纳入哈希，例如移动网络中的 **GTP-U TEID**。无论哪种情况，**同一条流的所有报文都具有相同的 Flow Label 值**。

:::en
Once the hash of the received customer packet is encoded into the IPv6 Flow Label field, any intermediate transit router can use this ASIC-friendly entropy information to perform load-balancing. Therefore, when there are multiple ECMP paths, the transit routers perform a hash computation leveraging a 3-tuple composed of the IPv6 Source Address, IPv6 Destination Address, and IPv6 Flow Label fields, combined with additional elements (e.g., router-id, ingress interface) to prevent polarization. The hash output determines which of the links the packet will be forwarded to.
:::

客户报文哈希一旦写入 Flow Label，任何中间 Transit 路由器都能直接使用这份**对 ASIC 友好**的熵信息做负载分担。因此当存在多条 ECMP 路径时，Transit 路由器用**三元组**（IPv6 SA、IPv6 DA、IPv6 Flow Label）再加一些附加元素（如 router-id、入接口，用于**防止极化**）计算哈希，哈希结果决定报文走哪条链路。

:::en
The IPv6 Flow Label is very important in applying correct load-balancing in the core without imposing a tax on the forwarding ASIC to inspect deep into packet headers to find the customer packet and use it to compute a load-balancing hash. The IPv6 Flow Label provides pre-computed hardware-friendly entropy information.
:::

Flow Label 对于在核心正确做负载分担非常重要：它让转发 ASIC **不必付出代价去深挖报文头**、找出客户报文再算哈希。Flow Label 提供的是**预先算好的、硬件友好的熵**。

为什么必须是 3 元组 + router-id 而不是 2 元组？因为 SRv6 隧道里 **DA 常常是同一个 SID**（同一段路径上所有流共用），SA 也可能相同，只有 Flow Label 携带熵。再加上 router-id/入接口，是为了让不同路由器对同一 Flow Label 的选路结果**不同**，避免所有节点的哈希都指向同一条链路——那就是"极化"。

```
   入向 PE 计算一次哈希，核心只做枚举

   客户 5 元组 ──哈希──> Flow Label = 0x3a7f1
                              │
                              ▼
   ┌──────────── 核心 Transit（只读三元组） ────────────┐
   │ hash(SA, DA, FlowLabel, router-id, in-if) = 2      │
   │   ├── 链路 A                                        │
   │   └── 链路 B  ← 选中                                 │
   └────────────────────────────────────────────────────┘

   全程无需 DPI，无需解析内层任何字段 → 可线速
```

*图 2-13：Flow Label 作为预计算熵，让核心不必解封装（按 2.6.2.1 节描述绘制）*

{{FIG|02/fig-2-13-flowlabel|图 2-13 · 矢量版|Flow Label 作为预计算熵：入口算一次，核心每跳只读三元组并叠加 router-id 防极化。}}

### 2.6.3 SR Segment Endpoint 节点

:::en
An SR Segment Endpoint node is any node receiving an IPv6 packet whose destination address matches a locally instantiated segment. As its name indicates, this node is the endpoint of the segment. It performs the segment's instruction and activates the next segment in the packet's header if there is one. In the example of Figure 2.6, nodes 2, 3, 4, and 5 are SR Segment Endpoint nodes.
:::

**SR Segment Endpoint 节点**是收到报文且目的地址匹配**本地实例化段**的节点。顾名思义，它是这个段的**终点**：执行该段的指令，并激活报文头中的下一个段（如果还有的话）。在图 2.6 的例子里，节点 2、3、4、5 都是 SR Segment Endpoint。

:::en
The SR Segment Endpoint node processes the IPv6 header chain as defined in section 4 of RFC 8200. For SRv6 SIDs associated with an Endpoint behavior defined in RFC 8986, the SRH and upper-layer header are processed as described in this RFC.
:::

SR Segment Endpoint 节点按 RFC 8200 第 4 节处理 IPv6 头部链。对于关联 RFC 8986 所定义端点行为的 SRv6 SID，SRH 与上层头部的处理按该 RFC 描述进行。

:::en
The SRv6 RFCs, such as RFC 8754, RFC 8986, and draft-ietf-spring-srv6-srh-compression, specify the behavior of SIDs of a given type using pseudocode. The pseudocode details local processing at a node to provide a precise description of the specified functionality. An implementation of the pseudocode is compliant if the externally observable wire protocol is as described by the pseudocode. In practice, anyone can define his own behavior. IANA keeps track of all the SRv6 Endpoint behaviors. At the time of writing this book there are over a hundred different behaviors defined for different purposes.
:::

SRv6 的 RFC（如 RFC 8754、RFC 8986 与 draft-ietf-spring-srv6-srh-compression）用**伪代码**规定某类 SID 的行为。伪代码详述节点本地的处理过程，以精确描述所定义的功能。判断一个实现是否合规的标准是：**外部可观测的线上协议行为**与伪代码描述一致即可。实践中任何人都可以定义自己的行为，IANA 负责登记所有 SRv6 端点行为；撰写本书时已定义一百多种行为，用于不同目的。

:::en
The segments used in the example of Figure 2.6 use the Endpoint behavior ("End" for short), which is the most basic behavior. It is the instantiation of a Prefix-SID (RFC 8402). The pseudocode of the End behavior is specified in RFC 8986, section 4.1.
:::

图 2.6 示例中使用的段采用 Endpoint 行为（简称 **End**），它是最基本的行为，也是 Prefix-SID（RFC 8402）的实例化。End 行为的伪代码在 RFC 8986 第 4.1 节规定。

```
    Example 2.1：End SID 伪代码（RFC 8986 §4.1，去掉错误处理后）

    S01. When an SRH is processed {
    S02.     If (Segments Left == 0) {
    S03.         Stop processing the SRH, and proceed to process the next
                 header in the packet, whose type is identified by
                 the Next Header field in the routing header.
    S04.     }
    S05..S11  <省略：错误处理与长度校验>
    S12.     Decrement IPv6 Hop Limit by 1
    S13.     Decrement Segments Left by 1
    S14.     Update IPv6 DA with Segment List[Segments Left]
    S15.     Submit the packet to the egress IPv6 FIB lookup for
                 transmission to the new destination
    S16. }
```

*图 2-14：原书 Example 2.1——End 行为的伪代码（注意 SL==0 的分支直接交回上层）*


:::en
Let us examine this pseudocode and apply it to the example of Figure 2.6 where Node 2 receives the packet transmitted by Node 1. Node 2 receives the packet whose IPv6 destination address is fc00:0:2:X::, which is a local End SID of Node 2. Since the SID is an End SID, Node 2 performs the operations in Example 2.1, starting at line S01.
:::

我们把这个伪代码套到图 2.6：节点 2 收到节点 1 发来的报文，IPv6 目的地址是 `fc00:0:2:X::`，正是节点 2 的本地 End SID。由于是 End SID，节点 2 从 S01 行开始执行。

:::en
Since the Segments Left field value is three, not zero—i.e., the active SID is not the last SID in the list, processing jumps to line S12. Node 2 decrements the Hop Limit value (line S12), as in classic routing, and it decrements the Segments Left value to two (line S13). Node 2 updates the IPv6 destination address with Segment List[Segments Left = 2] (line S14), which is fc00:0:3:X::. The node performs a FIB lookup for this new destination address (line S15) and finds that it matches fc00:0:3::/48 advertised by Node 3. It forwards the updated packet to Node 3.
:::

因为 `Segments Left` 值为 3 而不是 0（即活动段不是列表里的最后一个段），处理跳到 S12 行。节点 2 像经典路由那样把 **Hop Limit 减 1**（S12），并把 **Segments Left 减到 2**（S13）。节点 2 用 `Segment List[Segments Left = 2]` 更新 IPv6 目的地址（S14），得到 `fc00:0:3:X::`；对该新目的地址做 FIB 查找（S15），命中节点 3 通告的 `fc00:0:3::/48`，于是把更新后的报文转发给节点 3。

:::en
The packet now reaches Node 3, possibly after traversing one or multiple Transit nodes. Node 3 receives the packet whose IPv6 destination address is fc00:0:3:X::, which is a local End SID of Node 3. Since the Segments Left field value is two, processing jumps to line S12. Node 3 decrements the Hop Limit value, and decrements the Segments Left value to one. Node 3 updates the IPv6 destination address with Segment List[Segments Left = 1], which is fc00:0:4:X::, and forwards the updated packet to Node 4.
:::

报文（可能经过一台或多台 Transit 节点）到达节点 3。节点 3 收到的报文目的地址是 `fc00:0:3:X::`，是它的本地 End SID。因为 `Segments Left` 为 2，处理跳到 S12：Hop Limit 减 1，`Segments Left` 减到 1；用 `Segment List[1]`（即 `fc00:0:4:X::`）更新目的地址，然后把更新后的报文转发给节点 4。

:::en
Node 4 receives the packet whose IPv6 destination address is fc00:0:4:X::, which is a local End SID of Node 4. Since the Segments Left field value is one, processing jumps to line S12. Node 4 decrements the Hop Limit value, and decrements the Segments Left value to zero. Node 4 updates the IPv6 destination address with Segment List[Segments Left = 0], which is fc00:0:5:eeee::, and forwards the updated packet to Node 5.
:::

节点 4 收到的报文目的地址是 `fc00:0:4:X::`，是它的本地 End SID。`Segments Left` 为 1，跳到 S12：Hop Limit 减 1，`Segments Left` 减到 **0**；用 `Segment List[0]`（即 `fc00:0:5:eeee::`）更新目的地址，然后把报文转发给节点 5。

逐跳的报文状态，一张表看完：

| 处理节点 | 收到的 DA | Segments Left（收到 → 发出） | 发出的 DA | 下一跳依据 |
|---|---|---|---|---|
| 节点 1（Source） | — | 3（新封） | `fc00:0:2:X::` | 命中 `fc00:0:2::/48` |
| 节点 2（End） | `fc00:0:2:X::` | 3 → 2 | `fc00:0:3:X::` | 命中 `fc00:0:3::/48` |
| 节点 3（End） | `fc00:0:3:X::` | 2 → 1 | `fc00:0:4:X::` | 命中 `fc00:0:4::/48` |
| 节点 4（End） | `fc00:0:4:X::` | 1 → 0 | `fc00:0:5:eeee::` | 命中 `fc00:0:5::/48` |
| 节点 5（End.DT4） | `fc00:0:5:eeee::` | 0 | 内层 IPv4 查 VRF 表 | 业务转发 |

*图 2-15：原书 Figure 2.6 的逐跳报文演进（按 2.6.3 节文字重绘）*

{{FIG|02/fig-2-15-hop-evolution|图 2-15 · 矢量版|逐跳报文演进表：收到的 DA、Segments Left 的前后值与发出的 DA 三列对照。}}

注意 `Segments Left` 与 `DA` 的配合关系：**DA 永远是"SID 列表里第 SL 个元素"**。SL 减 1、DA 换成 `Segment List[SL]`，这两步必须原子完成，否则会短暂出现"DA 与 SL 不自洽"的报文——某些实现里这是排障时看到 SID 跳过站的原因。

#### 2.6.3.1 倒数第二段弹出（PSP）

:::en
We did not do it for illustration purposes, but in most, if not all, practical use cases, Node 4 would remove the SRH from the packet. The Segments Left field is zero, which indicates that all segments in the list have been processed and the active segment is in the IPv6 destination address. Unless the final destination needs to receive the packet with its SRH, the SRH has become dead weight and can be removed. This is called "Penultimate Segment Popping".
:::

为了讲清楚流程，我们在示例里没有这么做；但在**绝大多数（甚至全部）实际用例**中，节点 4 会把这个 SRH 从报文中**移除**。此时 `Segments Left` 为 0，说明列表里的所有段都处理完了，活动段已经在 IPv6 目的地址里。除非最终目的地需要带着 SRH 收到报文，否则 SRH 已经成了**累赘**，可以去掉。这个动作称为 **Penultimate Segment Popping（PSP，倒数第二段弹出）**。

:::en
Despite its similar name, this behavior differs from the MPLS Penultimate Hop Popping (PHP), as documented in section 3.3.1.2.
:::

尽管名字相似，这个行为与 MPLS 的**倒数第二跳弹出（PHP）**并不相同（本书 3.3.1.2 节有对比）：PHP 弹出的是标签栈，PSP 移除的是扩展头，二者发生在不同的协议层，动机也不同。

:::en
We stop the example here. Refer to section 6.4.1 to find out how Node 5 handles the packet.
:::

示例到这里结束。节点 5 如何处理这个报文，见 6.4.1 节。

### 2.6.4 Reduced SRH

:::en
When looking closely at the packet that Node 1 sends out in Figure 2.6, you can see that the IPv6 header chain contains redundant information. The first SID (fc00:0:2:X::) is both in the IPv6 destination address and the Segment List[3].
:::

仔细看图 2.6 中节点 1 发出的报文，能看到 IPv6 头部链里有**冗余信息**：第一个 SID（`fc00:0:2:X::`）同时出现在 IPv6 目的地址和 `Segment List[3]` 里。

:::en
When the use case does not require the entire SID list to be preserved in the SRH, a reduced SRH may be used. All implementations use the reduced SRH by default.
:::

当用例**不需要**在 SRH 中保留完整 SID 列表时，可以使用 **reduced SRH**。**所有实现默认都使用 reduced SRH**。

:::en
A reduced SRH does not contain the first segment of the related SR Policy (the first segment is the one already in the destination address of the IPv6 header), and the Last Entry field is set to n – 2, where n is the number of elements in the SR Policy.
:::

reduced SRH **不包含**相关 SR 策略的第一个段（第一个段本来就在 IPv6 头的目的地址里），且 `Last Entry` 字段设为 **n − 2**（n 为 SR 策略中段的个数）。

```
   Reduced SRH（n=4 的策略，SRH 里只剩 3 个元素）

   ┌──────────────────────────────────────────────┐
   │ SA = fc00:0:1::1                             │
   │ DA = fc00:0:2:X::        ← 第一站只在这里     │
   ├──────────────────────────────────────────────┤
   │ SRH: Type=4, SL=3, Last Entry = 2  ← n-2     │
   │ Segment List[0] = fc00:0:5:eeee::            │
   │ Segment List[1] = fc00:0:4:X::               │
   │ Segment List[2] = fc00:0:3:X::   ← 不再重复第一站│
   ├──────────────────────────────────────────────┤
   │ 内层 IPv4 业务报文                            │
   └──────────────────────────────────────────────┘

   省下 16 字节/包；若第一站在 SRH 里重复，纯属浪费
```

*图 2-16：非 reduced SRH 与 reduced SRH 的差别（按 2.6.4 节描述绘制）*

{{FIG|02/fig-2-16-reduced-srh|图 2-16 · 矢量版|完整 SRH 与 reduced SRH：后者去掉与 DA 重复的第一站，Last Entry = n−2。}}

## 2.7 本章小结

:::en
This chapter briefly reviewed Segment Routing (SR) and its architecture, including the components and operations involved. Further, the chapter delves into SRv6 and its enhancements to IPv6, the definition and processing of SRv6 SIDs, the format and processing of the Segment Routing Header (SRH), and the roles of nodes in SRv6 networks (SR Source node, Transit node, SR Segment Endpoint node). An example of packet processing with SRH is provided, along with the concept of Reduced SRH.
:::

本章简要回顾了 Segment Routing 及其架构，包括涉及的组件与操作；进而深入 SRv6 及其对 IPv6 的增强、SRv6 SID 的定义与处理、SRH 的格式与处理、SRv6 网络中节点的角色（SR Source、Transit、SR Segment Endpoint），并给出了一个带 SRH 的报文处理示例以及 reduced SRH 的概念。

用三句话浓缩这一章：

1. **SRv6 的转发面只有两个动作**：Transit 做最长匹配转发（不看 SRH），Endpoint 执行本地 SID 的指令并把 DA 换成下一段
2. **uSID 用位移替代指针**，把 6 条指令塞进 128 位 DA，省掉 SRH 的 88 字节，也让"当前指令"的维护变成纯硬件左移
3. **SRH 与 Reduced SRH 是"必要时才用"的机制**：超过 6 段、需要 TLV、或要跨域携带非压缩 SID 时才需要它

## 实战案例

以下三个案例把本章的概念落到设备上。配置为 IOS XR 风格示例（需按自己的 locator/接口名替换），输出是**格式示意**，重点在"看哪几个字段、怎么判断"。

### 案例一：用 uSID 位移核对"一跳到不到位"

**场景**：某运营商 POP 内 4 台 ASR 9902 组成 SRv6 核心，SID block 为 `fc00:0::/32`，每台一个 `/48` locator。运维需要验证"从 R1 到 R4 的一条显式路径确实按 `R1→R2→R3→R4` 走，而不是 IGP 自己算的路径。

**配置（R1）**：

```
segment-routing
 srv6
  locators
   locator MAIN
    micro-segment behavior unode pfx-msb-first
    prefix fc00:0:1::/48
   !
  !
 !
!
router isis CORE
 address-family ipv6 unicast
  metric-style wide
  segment-routing srv6
   locator MAIN
  !
 !
!
```

**验证点一：locator 与 End/uN SID 是否真的装上了**

```
RP/0/RSP0/CPU0:R1# show segment-routing srv6 locator MAIN
Locator                     Behavior      Alloc            State
-------------------------- ------------ --------------- -----------
fc00:0:1::/48               unode        1                Active

RP/0/RSP0/CPU0:R1# show segment-routing srv6 sid
SID                         Behavior       Context
--------------------------- -------------- ----------------
fc00:0:1::                  End            0
fc00:0:1:e000::             End.X          GigabitEthernet0/0/0/2
```

`End` 与 locator 同地址是对的——**End/uN 的 SID 就是 locator 本身**，这是 uSID 能让"位移后自然指向下一站"的前提。

**验证点二：位移在转发表里的表现**

```
RP/0/RSP0/CPU0:R1# show cef ipv6 fc00:0:2:0003:0004::/128 detail
  fc00:0:2:0003:0004::/128, version 1482, internal 0x...
   nexthop GigabitEthernet0/0/0/1
   ...
```

要点：R1 只按 `/48` 命中，后面 `0003:0004` 对 R1 而言是**不解析的载荷**。若你想让 R1 直接把两条指令一起执行（uN+uA 单次查表），则要在 R1 上存在 `fc00:0:1:0002::/64` 这样的**组合项**——这是 uSID 相对 MPLS"一次只看一个标签"的关键差别（见 2.4.2 节）。

**验证点三：路径是否真按显式列表走**

用第 9 章的 SRv6 traceroute 手段（`ping ipv6 fc00:0:5:eeee:: sr-path <...>`）可以逐站打印；若只有 ping/traceroute 基础命令，则观察**每站的 End SID 是否被命中**（`show segment-routing srv6 sid` 的命中计数、或 CEF 计数），以及核心设备上 `show cef ipv6 <SID>` 的下一跳是否与设计一致。

### 案例二：TI-LFA 触发的 SRH，Segments Left 卡住不动

**现象**：链路 R2–R3 故障后，业务恢复很快（TI-LFA 生效），但同一时刻部分长流丢包，`show sr policies` 没有异常，抓包（镜像口）显示**修复路径报文带 SRH，且 Segments Left 在连续多跳中保持同一数值**。

**分析路径**：

1. 正常流量是 uSID 压缩（无 SRH），只有保护路径才带 SRH——因为修复路径需要"指定节点 + 指定链路"的组合，通常超过 6 条 uSID 的位置预算，或需要非压缩 SID 混合
2. 修复路径的 SRH 中，`Segments Left` 应该每命中一个 End/End.X 就减 1。**卡住不动 = 没有节点命中本地 SID**
3. 逐跳核对 DA 与本地 SID：若 DA 落在某台节点上但该 SID 未实例化（例如保护链路对应的 `End.X` 没配、或 locator 未在 IGP 中通告到达），该节点会把这个报文当**普通 IPv6 转发**处理——不消费 SID，SL 自然不减

**排查命令**：

```
RP/0/RSP0/CPU0:R2# show segment-routing srv6 sid | include End.X
RP/0/RSP0/CPU0:R2# show isis database verbose | include fc00:0:3::
RP/0/RSP0/CPU0:R2# show mpls forwarding   ! 若混跑 MPLS，确认没有走错数据面
```

**结论与修复**：补齐保护路径所需的 `End.X` 实例化（接口名要与拓扑一致），并确认 locator 的 `/48` 在 IGP 里可达。这个案例的教训是：**SRH 里的 SID 不可达时，网络不会报错，只会静默降级为普通 IP 转发**——所以 SRv6 的 OAM（第 9 章）必须能区分"按 SID 走"和"按 IP 走"。

### 案例三：核心链路利用率偏斜——Flow Label 被置 0

**现象**：两台 PE 之间的 SRv6 隧道扩容到 3 条等价 400G 链路，容量应该够，但监控显示 **A 链路 95%、B 和 C 各 30%**，且偏斜在多个 PE 对之间同时出现，说明不是单条流的偶发。

**分析**：

1. SRv6 隧道里，同一 PE 对之间的所有流**共享同一个 DA**（同一个远端 SID），SA 也相同
2. 核心 Transit 的三元组哈希只有 Flow Label 能提供区分度（见 2.6.2.1 节）
3. 若入向 PE 封装时 **Flow Label 被置 0**（老版本默认不解封装内层哈希，或 entropy 配置被关掉），则同一 PE 对的所有流哈希值恒定 → 全部压在同一条链路

**验证方法**：

```
! 1) 在核心设备确认 ECMP 的哈希输入与桶分布
RP/0/RSP0/CPU0:P1# show cef ipv6 fc00:0:5:eeee::/128 detail
   ... loadinfo ...
   Load distribution: 0 1 2 ... （检查是否只有少数桶被使用）

! 2) 在 PE 侧确认封装行为（不同版本命令不同，关键是看 entropy/flow-label 开关）
RP/0/RSP0/CPU0:PE1# show running-config | include "flow-label|entropy"
```

抓包旁证：在 PE 出口镜像几条不同业务的报文，比对 **Flow Label 是否随流变化**。若所有报文的 Flow Label 都是 0，问题确认。

**修复**：在入向 PE 上启用基于内层报文的 entropy 计算（不同平台命令不同，部分版本默认开启、部分需显式配置），升级到已修复该行为的版本，然后复测桶分布。修复后应能看到三条链路利用率趋于均衡，且同一流始终走同一条路径（per-flow 保序不受影响）。

**这类问题的通用判据**：SRv6 只是把熵搬到了 Flow Label，**它不会自动产生熵**。任何"核心偏斜但业务侧正常"的 SRv6 故障，先查 Flow Label 是否为 0，再查哈希是否引入了 router-id/入接口（防极化）。

## 延伸阅读

- RFC 8200：IPv6 规范，Routing Header 定义（图 2-9 的出处）
- RFC 8754：SRH 格式与处理（图 2-10）
- RFC 8986：SRv6 网络编程，End / End.X / End.DT4 等行为的伪代码（图 2-14）
- RFC 8402：Segment Routing 架构，Prefix-SID 与 Adjacency-SID
- RFC 9259：SRv6 OAM，O-flag 的出处
- draft-ietf-spring-srv6-srh-compression：uSID 容器、shift-and-forward 的规范定义（图 2-5、2-6）

