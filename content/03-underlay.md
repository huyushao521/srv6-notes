# 03 · Underlay 指令：Locator、End/End.X 与 TI-LFA

> **本章定位**：原书第 3 章《Underlay Instructions》。本版按原书 3.1–3.6 的段落顺序**逐段对照**：灰色英文块是原文摘录（保留原句与术语），紧随其后的中文是该段的完整翻译，必要时补一句工程注解。书中的 Figure 3.1–3.35 按原文描述用 ASCII 重绘（同类图合并），图注标明来源。配置与命令输出来自原书 Example 3.1–3.14，按 IOS XR 风格保留。

**本章要拿到的东西**（原书章首列表）：

| 问题 | 对应小节 |
|---|---|
| underlay 指令怎样把流量按指定路径引导 | 3.1、3.3、3.4 |
| SRv6 locator 为什么能改善路由可扩展性 | 3.2 |
| IGP prefix segment 与 adjacency segment 及其数据面行为 | 3.3、3.4 |
| uSID flavor 如何把多条指令塞进一个 128 bit SID | 3.3.1.1、3.4.1.1 |
| PSP 与 USD flavor 的目的与用法 | 3.3.1.2、3.3.1.3、3.3.1.4 |
| TI-LFA 如何提供快速重路由 | 3.5 |
| locator 与 segment 在 IS-IS / OSPF 中的通告格式 | 3.2.2、3.3.3、3.4.3 |

## 3.1 引言：underlay 指令是"路点"而不是"状态"

:::en
The underlay instructions are segments that direct the traffic onto a forwarding path by enforcing a sequence of intermediate waypoints or links along the way to the packet destination. In SRv6, like SR-MPLS, the underlay instructions are distributed by an Interior Gateway Protocol (IGP). This is why they are often called IGP Segments.
:::

underlay 指令是**段（segment）**：它通过在去往报文目的地的路上强制一串中间路点（waypoint）或链路，把流量引导到某条转发路径上。在 SRv6 中（与 SR-MPLS 一样），这些 underlay 指令由**内部网关协议（IGP）**分发——所以常被称为 **IGP Segment**。

:::en
At the time of this writing, the IETF has defined minor extensions to the IS-IS (RFC 9352) and OSPF (RFC 9513) protocols for distributing SRv6 IGP segments. Each router participating in the IGP thus learns the segments instantiated by other participating nodes and can maintain a complete view of all segments available in the IGP domain.
:::

撰写本书时，IETF 为分发 SRv6 IGP 段而对 IS-IS（RFC 9352）与 OSPF（RFC 9513）做的只是**小幅扩展**。因此每台参与该 IGP 的路由器都能学到其他节点实例化的段，并维护"IGP 域内全部可用段"的完整视图。

:::en
The (sub-)types of IGP segments in SRv6 are the same as SR-MPLS: The prefix segment, which steers the traffic along the shortest path to an IGP prefix, and the adjacency segment, which forces the traffic on a particular IGP adjacency, regardless of its metric.
:::

SRv6 中 IGP 段的（子）类型与 SR-MPLS 完全相同，只有两种：

- **Prefix Segment（前缀段）**：把流量沿到某个 IGP 前缀的**最短路径**引导；
- **Adjacency Segment（邻接段）**：把流量**强制**压到某条特定 IGP 邻接上，**不管它的度量是多少**。

:::en
The IGP segments are the base building blocks that enable the construction of topological SR paths for fast-reroute, micro-loop avoidance, and traffic engineering purposes.
:::

这两类段是基础积木，用它们可以拼出**拓扑型 SR 路径**，服务于三个目的：快速重路由（FRR）、微环避免（micro-loop avoidance）、流量工程（TE）。

:::en
The concept of IGP segments is further detailed in Chapter 2 of Segment Routing: Part I.
:::

IGP 段概念的完整推导见《Segment Routing: Part I》第 2 章；本章只关心"在 SRv6 数据面上它长什么样、怎么配、怎么通告、怎么被保护"。

## 3.2 Segment Locator：一条前缀 Sum 住所有段

### 原书侧栏：SRv6 SID 的结构

:::en
An SRv6 SID comprises a locator, a function, and an optional argument. The locator is encoded in the most significant bits of the SID, followed by the function and then the argument, if any. If the combined length of the locator, function, and argument is shorter than 128 bits, the remaining bits are set to 0.
:::

一个 SRv6 SID 由 **locator、function、可选 argument** 三部分组成。locator 编码在 SID 的最高位，其后是 function，再后面是 argument（如果有）。如果三者长度之和不足 128 bit，剩余位补 0。

:::en
The locator is an IPv6 prefix associated with the endpoint node where the segment is instantiated. The function is an opaque value used by the endpoint node, in combination with the locator, to determine the operation to be performed on the packet. Together, the locator and function uniquely identify a segment on a node. Finally, an argument may provide additional context or information for executing the segment operation. The presence and format of the argument is determined by the type of operation associated with the segment, and its value may vary across packet flows.
:::

- **locator** 是与"实例化该段的端点节点"关联的 IPv6 前缀；
- **function** 是端点节点自己用的**不透明值**，与 locator 一起决定对该报文执行什么操作；
- locator + function 合起来在同一台节点上**唯一标识一个段**；
- **argument** 为执行该段操作提供额外上下文。它是否存在、格式如何，由该段关联的操作类型决定，其值**可以随流变化**。

最后一句是 uSID 能工作的关键：argument 是"每条流可以不同"的自由区，所以才能拿它装下一条指令。

```
    图 3-1：SID 的三段结构与 locator 的两段结构

   128 bit SID
   +----------------+----------+----------------+------------------+
   |   Locator      | Function |    Argument    |   补 0（未用位）  |
   |   L bits       |  F bits  |    A bits      |   128-L-F-A      |
   +----------------+----------+----------------+------------------+
   |<---- 路由用 --->|<-- 本地执行 -->|<-- 每条流可变 -->|

   Locator 内部又分两段（IS-IS/OSPF 的 SID Structure TLV 描述）：
   +--------------------------+---------------------+
   |  Locator-Block (LB)      |  Locator-Node (LN)  |  → 合起来才是 locator
   |  全网统一，如 fc00:0::/32 |  节点编号，如 0x0004 |
   +--------------------------+---------------------+
   例：fc00:0::/32 (LB, 32 bit) + 0004 (LN, 16 bit) = fc00:0:4::/48
```

*图 3-1：SRv6 SID 的 LOC:FUNCT:ARG 结构与 locator 的 LB/LN 划分（按原书 3.2 节侧栏与 RFC 9352 §3.1 绘制）*

### 3.2 正文：locator 的本质是"汇总"

:::en
All SRv6 segments are instantiated within the context of a segment locator.
:::

**所有 SRv6 段都必须在一个 segment locator 的上下文里实例化**——没有游离于 locator 之外的 SID。

:::en
The locator is an IPv6 prefix covering all the segments of a node that share the same route to that node. For example, all the segments of Node 4 that should be routed along the shortest IGP path can be instantiated from the locator fc00:0:4::/48.
:::

locator 是一段 IPv6 前缀，它**覆盖"到该节点走同一条路由"的所有段**。例如：节点 4 上所有"应当沿 IGP 最短路径被路由到"的段，都可以从 locator `fc00:0:4::/48` 中实例化。

反过来说：如果一个段需要走**不同的**路由（不同算法、不同切片、任播组），它就必须挂在**另一个** locator 下——这就是 Flex-Algo（第 4 章）与 anycast 的地址基础。

:::en
The locators in an SRv6 domain are typically allocated from a common IPv6 prefix. This common prefix is the SRv6 SID block or locator block. The remainder of the locator, which identifies a node within the SID block, is the locator node. Chapter 10 provides guidelines for allocating SID blocks and locators.
:::

SRv6 域内的 locator 通常从一个**公共 IPv6 前缀**中分配：这个公共前缀就是 **SRv6 SID block（或 locator block）**；locator 中剩下的、用于在 SID block 内标识节点的部分，称为 **locator node**。SID block 与 locator 的分配方法见第 10 章。

> 术语提醒：`locator = SID block + locator node`。中文资料里常把 `SID block` 叫"段块"、把 `locator node` 叫"节点段"，本质就是图 3-1 下半部分的 LB/LN 划分。

:::en
Advertising the locator as an IPv6 route in the routing protocol immediately provides reachability to all the segments instantiated from that locator. From a routing protocol perspective, the segment locator is an IPv6 prefix that summarizes all its underlying segments.
:::

在路由协议中**把 locator 当作一条 IPv6 路由通告出去，就立刻为从它实例化出的所有段提供了可达性**。从路由协议的角度看，segment locator 就是一个**汇总了其下所有段**的 IPv6 前缀。

```
    图 3-2：原书 Figure 3.1 —— 到 locator fc00:0:4::/48 的路由树（默认链路度量 10）

                        ┌────┐
                        │ 1  │  ← 任意源
                        └─┬──┘
                   10 ┌───┴───┐ 10
                      ▼       ▼
                   ┌────┐   ┌────┐
                   │ 2  │   │ 3  │
                   └─┬──┘   └─┬──┘
                   10│        │10
                      └───┬───┘
                          ▼
                       ┌────┐
                       │ 4  │  locator fc00:0:4::/48
                       └────┘  End SID fc00:0:4::

    节点 1 有两条等价路径（经 2、经 3）→ 转发表里是 ECMP，两条都装
    两条路径都用同一个 /48 表达，与"节点 4 上有多少个段"无关
```

*图 3-2：到 segment locator 的最短路径树（按原书 Figure 3.1 重绘）*

:::en
The segment locator concept allows transit nodes to route traffic destined to any segment of a node (or anycast group) without knowing about each individual segment that is instantiated on that node (or set of nodes). The transit nodes only need to learn about the locators of that node via their routing protocol and install them in their routing table. This provides a significant gain in routing scalability as each node only needs to maintain one route per other node and routing policy in the domain, regardless of how many segments are instantiated at each node.
:::

segment locator 这个概念，让中转节点**不需要知道目标节点上具体实例化了哪些段**，也能把去往"该节点（或任播组）任意段"的流量路由过去。中转节点只需通过路由协议学到那个节点的 **locator** 并装表即可。这带来显著的路由可扩展性收益：**每台节点对其他每个节点/路由策略只需维护一条路由**，与该节点上实例化了多少个段完全无关。

```
    图 3-3：可扩展性账本（MPLS 标签 vs SRv6 locator）

   MPLS（按标签逐条分发）              SRv6（按 locator 汇总）
   节点 4：100 个业务标签              节点 4：1 个 locator fc00:0:4::/48
            ↓ 泛洪到全网                        ↓ 泛洪到全网
   全网 N-1 台节点各学 100 条          全网 N-1 台节点各学 1 条

   路由条数 ≈ (N-1) × 段数             路由条数 ≈ (N-1) × 1
   这就是 Bell Canada 报告的"最值钱的收益"（见 2.2 节与第 14 章）
```

*图 3-3：locator 汇总带来的路由规模差异（按 3.2 节文字与 2.2 节结论绘制）*

:::en
The locator advertisement in the IGP also indicates the IGP algorithm to be used for computing the shortest paths to this prefix. This can be the default SPF algorithm that minimizes the accumulated link IGP metric (algorithm 0) or a flexible algorithm (algorithms 128-255). The algorithm values 1-127 are reserved for other IETF-defined IGP algorithms, but none are used today for SRv6.
:::

locator 在 IGP 中的通告**同时指明了计算到该前缀最短路径所用的 IGP 算法**：

| 算法号 | 含义 | 现状 |
|---|---|---|
| **0** | 默认 SPF：最小化累计链路 IGP 度量 | 绝大多数部署 |
| **128–255** | 灵活算法（Flex-Algo），自定义约束与度量 | 第 4 章 |
| 1–127 | 保留给 IETF 定义的其他 IGP 算法 | 撰写本书时尚无用于 SRv6 的 |

:::en
Furthermore, all segment locators associated with the default SPF algorithm (algorithm 0) are also advertised as regular IPv6 prefixes in the IGP. This allows non-SRv6 nodes to install the route and serve as transit for SRv6 traffic. There is no difference between SRv6 and regular IPv6 traffic for those transit nodes.
:::

此外，**所有关联默认 SPF 算法（算法 0）的 locator 还会同时作为普通 IPv6 前缀在 IGP 中通告**。这让不支持 SRv6 的节点也能装这条路由、充当 SRv6 流量的中转。对那些中转节点而言，**SRv6 流量与普通 IPv6 流量毫无区别**。

这一句是"增量部署"的技术依据：核心里的老设备不必升级也能转发 SRv6 外层报文，只要它能装 `/48` 的 IPv6 路由。

### 3.2.1 Locator 配置

:::en
An SRv6 segment locator is configured on a Cisco IOS XR router as shown in Example 3.1.
:::

在 Cisco IOS XR 上配置一个 SRv6 segment locator，见例 3.1。

**例 3.1：SRv6 locator 配置**

```
segment-routing srv6
  locators
    locator MAIN
      prefix fc00:0:4::/48
      micro-segment behavior unode psp-usd
```

:::en
This sequence of instructions configures the prefix fc00:0:4::/48 as a new SRv6 segment locator on Node 4 for the default SPF algorithm. In this example, the locator is given the operational alias MAIN, which we can use in other parts of Node 4 configuration to refer to this locator. Additional locators can be defined on the node by replicating this configuration with a different alias and prefix. For example, to create anycast groups or associate with different IGP algorithms (e.g., flexible algorithms).
:::

这几行把 `fc00:0:4::/48` 配成节点 4 上、面向**默认 SPF 算法**的一个新 SRv6 segment locator。示例给这个 locator 起了运维别名 **MAIN**，节点 4 配置的其他位置就可以用这个名字引用它。要定义更多 locator，只要换个别名和前缀重复这段配置——例如为了创建**任播组**，或关联到**不同的 IGP 算法**（如灵活算法）。

:::en
For each locator advertised in the IGP, a prefix segment is automatically instantiated. This prefix segment can be configured with a specific set of endpoint behavior flavors (see section 3.3.1). In this example, the micro-segment (uSID), penultimate segment popping (PSP), and ultimate segment decapsulation (USD) flavors are enabled for the prefix segment of locator MAIN. We will describe all three flavors in the later sections of this chapter.
:::

**每通告一个 locator，就自动实例化一个 prefix segment**。这个前缀段可以配一组特定的端点行为 **flavor**（见 3.3.1 节）。本示例对 locator `MAIN` 的前缀段启用了三种 flavor：

```text
micro-segment behavior unode psp-usd
                   ^^^^^ ^^^ ^^^^
                   |     |   └── USD：最后一段解封装
                   |     └────── PSP：倒数第二段弹出 SRH
                   └──────────── uSID（unode）：容器内可放 6 条 16 bit 微指令
```

三种 flavor 都在本章后续小节展开（3.3.1.1 / 3.3.1.2 / 3.3.1.3）。

:::en
We can ensure that the locator is properly instantiated by checking the list of locators currently configured on the node.
:::

要确认 locator 是否被正确实例化，查看节点上当前配置的 locator 列表即可。

**例 3.2：查看节点上所有 SRv6 locator**

```
RP/0/RP0/CPU0:R4# show segment-routing srv6 locator
Name             ID       Algo  Prefix                    Status   Flags
---------------  -------  ----  ------------------------  -------  --------
MAIN             1        0     fc00:0:4::/48             Up       U
```

:::en
The output shows the newly created locator MAIN with the prefix fc00:0:4::/48. This locator is associated with the default SPF algorithm (Algo 0) and has the U-flag, indicating that it is a micro-segment locator, as per the configuration. Note that an A-flag would indicate an anycast locator.
:::

输出显示新建的 locator `MAIN`，前缀 `fc00:0:4::/48`，关联默认 SPF 算法（`Algo 0`）。**Flags 里的 `U` 表示这是微段（uSID）locator**，与配置一致；如果是 **`A`** 则表示**任播（anycast）locator**。

### 3.2.2 Locator 通告

:::en
Advertising a segment locator in the IGP makes it routable within the routing domain. The following configuration instructs an Cisco IOS XR router to advertise the locator MAIN in IS-IS instance 1.
:::

在 IGP 中通告 segment locator，才能让它在路由域内**可路由**。下面的配置让路由器在 IS-IS 实例 1 中通告 locator `MAIN`。

**例 3.3：让 IS-IS 实例 1 通告 locator MAIN**

```
router isis 1
  address-family ipv6 unicast
    segment-routing srv6
      locator MAIN
```

:::en
A segment locator can be advertised in one or multiple IGP instances, like a loopback address.
:::

一个 segment locator 可以像 loopback 地址那样，在**一个或多个 IGP 实例**中通告——这决定了"哪些区域/域能看到这个节点"。

:::en
Once configured, the locator is advertised as part of an SRv6 Locator TLV in IS-IS (RFC 9352) or OSPF (RFC 9513). SRv6 locators are processed by the receiving routers similarly to IPv6 prefix reachability advertisements. Each router computes the shortest path to every SRv6 locator that it receives and installs it in its forwarding table.
:::

配置完成后，locator 会作为 **SRv6 Locator TLV** 的一部分在 IS-IS（RFC 9352）或 OSPF（RFC 9513）中通告。接收方的处理方式与普通 IPv6 前缀可达性通告**完全类似**：每台路由器对收到的每个 SRv6 locator 计算最短路径并装进转发表。

```
    图 3-4：原书 Figure 3.2 —— IS-IS 中的 SRv6 Locator TLV（Type 27）

    0                   1                   2                   3
    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |  Type = 27    |    Length     |           MT ID               |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |                        Metric (4 octets)                      |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |D|  Flags(7)   |  Algorithm    | Locator Size  |               |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+               +
   |                 Locator（只编码网络位）                         |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   | Sub-TLV Len   |           Sub-TLVs（可多个）                    |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

   同一个 TLV 可放多个 locator：每个 locator 重复"MT ID 之后"整段字段
```

*图 3-4：IS-IS SRv6 Locator TLV（按原书 Figure 3.2 与 RFC 9352 §3.1 绘制）*

:::en
The IS-IS locator advertisement, as shown in Figure 3.2, contains the following fields: Type: 27. Length: The number of octets in the TLV value, including any sub-TLV. R: Bits reserved for future use. MT ID: Multi-Topology Identifier, as defined in RFC 5120. Multiple locators with the same MT ID can be advertised together in the same SRv6 Locator TLV, repeating the series of fields after the first 4 bytes for each locator.
:::

IS-IS 的 locator 通告（图 3.2 / 图 3-4）字段如下：

| 字段 | 说明 |
|---|---|
| **Type** | `27`，标识 SRv6 Locator TLV |
| **Length** | TLV value 的字节数，**含所有 sub-TLV** |
| **R** | 保留位（未来使用） |
| **MT ID** | 多拓扑标识（RFC 5120）。**同 MT ID 的多个 locator 可放进同一个 TLV**，每个 locator 重复"前 4 字节之后"的那一串字段 |

:::en
Metric: Metric associated with the locator prefix, as defined in RFC 5305. Flags: D-flag (most significant bit): Up/down bit, as defined in RFC 5305. When set, this flag indicates that the locator was re-advertised downwards in the IS-IS level hierarchy (e.g., from level 2 to level 1). All other bits are reserved for future use.
:::

| 字段 | 说明 |
|---|---|
| **Metric** | 与该 locator 前缀关联的度量（RFC 5305） |
| **Flags → D-bit（最高位）** | Up/Down 位（RFC 5305）。**置 1 表示该 locator 在 IS-IS 层级中被"向下"再通告**（例如 level-2 → level-1）。其余位保留 |

:::en
Algorithm: IGP algorithm associated with the locator, as defined in RFC 8402. Locator Size and Locator: Respectively, the length and value of the SRv6 locator prefix. Only the network bits of the locator prefix are encoded.
:::

| 字段 | 说明 |
|---|---|
| **Algorithm** | 与该 locator 关联的 IGP 算法（RFC 8402） |
| **Locator Size / Locator** | locator 前缀的**位长**与**值**；**只编码网络位**（不做地址填充） |

:::en
Sub-TLV-length and Sub-TLVs: Respectively, the length and content of one or more sub-TLVs containing, in particular, the prefix segments that belong to this locator.
:::

| 字段 | 说明 |
|---|---|
| **Sub-TLV Length / Sub-TLVs** | 一个或多个 sub-TLV 的长度与内容，**其中最主要的就是属于该 locator 的 prefix segment**（End SID sub-TLV，见 3.3.3.1） |

:::en
In addition, it is recommended that the Prefix Attribute Flags TLV, defined in RFC 7794, be included as a sub-TLV of the locator TLV. The Prefix Attribute Flags TLV is mandatory when the locator TLV is leaked upwards in the IS-IS level hierarchy or redistributed from another protocol or instance.
:::

此外，建议把 RFC 7794 定义的 **Prefix Attribute Flags TLV** 作为 locator TLV 的 sub-TLV 带上。**当 locator TLV 被向上泄露（level-1 → level-2）或从其他协议/实例重分发时，这个 TLV 是强制的**——否则接收方无法判断该前缀的源属性（第 5 章"泄露与重分发"必须带的字段）。

```
    图 3-5：原书 Figure 3.3 —— OSPFv3 中的 SRv6 Locator TLV（Type 1）

   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |  Type = 1     |    Length     |  Route Type   |  Algorithm    |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   | Locator Length|Prefix Options |                               |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+                               +
   |                     Metric (4 octets)                         |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |                 Locator（只编码网络位）                         |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |                 Sub-TLVs（可多个）                              |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

   Prefix Options 的最高位是 AC-bit（RFC 9513 扩展）：
     AC=1 → 该 locator 属于任播组，可被多台节点同时通告
```

*图 3-5：OSPFv3 SRv6 Locator TLV（按原书 Figure 3.3 与 RFC 9513 §4.1 绘制）*

:::en
The OSPFv3 locator advertisement, as shown in Figure 3.3, contains the following fields: Type: 1. Length: The number of octets in the TLV value, including any sub-TLV. Route Type: An SRv6 locator route can only be of type Intra-Area, Inter-Area, AS External (Type 1 or 2) or NSSA External (Type 1 or 2).
:::

OSPFv3 的 locator 通告（图 3.3 / 图 3-5）字段：

| 字段 | 说明 |
|---|---|
| **Type** | `1` |
| **Length** | TLV value 字节数，含所有 sub-TLV |
| **Route Type** | SRv6 locator 路由只能是：区内、区间、AS 外部（Type 1/2）、NSSA 外部（Type 1/2） |

:::en
Algorithm: IGP algorithm associated with the locator, as defined in RFC 8402. Locator Length: Length of the locator prefix in bits. Prefix Options: OSPF prefix options, as defined in RFC 5340 and RFC 8362, and extended in RFC 9513 with the AC-bit (most significant bit). When set, the AC-bit indicates that the locator is associated with an anycast group and may thus be advertised by multiple nodes.
:::

| 字段 | 说明 |
|---|---|
| **Algorithm** | 关联的 IGP 算法（RFC 8402） |
| **Locator Length** | locator 前缀位长 |
| **Prefix Options** | OSPF 前缀选项（RFC 5340 / RFC 8362）；RFC 9513 用**最高位扩展出 AC-bit**：置 1 表示该 locator 属于**任播组**，可由多台节点同时通告 |

:::en
Metric: Metric associated with the locator prefix, as defined in RFC 5340. Locator: SRv6 locator prefix, with only the network bits being encoded. Sub-TLVs: One or more sub-TLVs containing, in particular, the prefix segments that belong to this locator.
:::

| 字段 | 说明 |
|---|---|
| **Metric** | 前缀度量（RFC 5340） |
| **Locator** | locator 前缀，仅编码网络位 |
| **Sub-TLVs** | 一个或多个 sub-TLV，其中主要是属于该 locator 的 prefix segment |

:::en
The Algorithm field indicates which IGP algorithm should be used to compute the shortest path to the locator. In the case of algorithm 0, the locator is also advertised separately as a regular IPv6 prefix, so that legacy (i.e., non-SRv6) routers can install a forwarding entry for it and seamlessly forward the SRv6 traffic destined to this locator. SRv6 locators advertised with an algorithm in the range 128-255 are flexible algorithm locators and will be further detailed in Chapter 4.
:::

**Algorithm 字段指明用哪种 IGP 算法计算到该 locator 的最短路径**。对算法 0，locator **还会单独作为普通 IPv6 前缀再通告一次**，使遗留（不支持 SRv6 的）路由器也能装上转发条目、无缝转发去往该 locator 的 SRv6 流量。算法号 128–255 的 locator 属于**灵活算法 locator**，在第 4 章展开。

:::en
In our example, all the other nodes in the IGP domain compute their shortest path to Node 4 and install an entry to the prefix fc00:0:4::/48 in their routing and forwarding tables. For example, Node 1 has two ECMP shortest paths to Node 4 via Node 2 and Node 3 and thus installs the FIB entry fc00:0:4::/48 pointing to both of them.
:::

在我们的例子里，IGP 域内其他所有节点都算出到节点 4 的最短路径，并把 `fc00:0:4::/48` 装进路由表与转发表。例如节点 1 有两条经节点 2、节点 3 的 ECMP 最短路径，因此 `fc00:0:4::/48` 的 FIB 条目同时指向这两条。

**例 3.4：节点 1 上到 locator fc00:0:4::/48 的 IPv6 路由**

```
RP/0/RP0/CPU0:R1# show route ipv6 fc00:0:4::/48
Routing entry for fc00:0:4::/48
  Known via "isis 1", distance 115, metric 21, type level-2
  Installed [...]
  Routing Descriptor Blocks
    fe80::250:56ff:feab:d750, from fc00:0:4::1, via GigabitEthernet0/0/0/0
      Route metric is 21
    fe80::250:56ff:feab:1d17, from fc00:0:4::1, via GigabitEthernet0/0/0/1
      Route metric is 21
```

读法：**一个前缀、两个 RDB（Routing Descriptor Block）**，说明这条 locator 路由是 ECMP 的；metric 21 = 两跳 × 10 + 节点 4 loopback 的 1。注意装的是**一条**路由，而不是节点 4 上每个 SID 各一条。

### 3.2.3 不可路由的 locator 与段

:::en
A segment locator not advertised in any routing protocol (or made reachable by static routes) is a non-routable locator. All the segments instantiated under such a non-routable locator are non-routable segments. These non-routable segments are not reachable from any node other than their parent node.
:::

**没有在任何路由协议中通告**（也没有用静态路由打通）的 segment locator 叫**不可路由 locator**。挂在它下面的所有段都是**不可路由段**：除了它们的**父节点**，任何节点都到不了它们。

:::en
A non-routable segment can be the first segment in a segment-list originating from its parent node or generally used as part of any segment list provided that the preceding segment steers the traffic to the parent node of the non-routable segment.
:::

不可路由段可以作为"从父节点发起的段列表"的**第一个段**；更一般地，它可以出现在任何段列表里，**前提是它前面那个段已经把流量引导到了它的父节点**。

这就是"不可路由段永远出现在程序末尾/紧跟其父节点 SID"的原因——它靠前一个段"送到门口"，自己只负责"进门之后的那一步"。

:::en
The non-routable nature of a segment has no impact on the packet processing at the segment parent node. For every incoming packet whose destination address matches a locally instantiated SRv6 SID, the node performs the endpoint processing dictated by the segment behavior, regardless of whether the locator is routable.
:::

段的"不可路由性"**不影响父节点对该报文的处理**。对每个入向报文，只要目的地址匹配本地实例化的 SRv6 SID，节点就按该段行为执行端点处理，**与 locator 是否可路由无关**。

:::en
Non-routable segment identifiers (SIDs) are locally significant. This means that different nodes in the network may associate a different semantics to the same non-routable SID. For example, they could bind it to a local adjacency (Adjacency-SID), SR policy (Binding-SID), or service (Service-SID), regardless of what semantics is bound to this SID on other nodes in the network. This is the same concept as the locally significant SIDs in SR-MPLS.
:::

**不可路由 SID 是"本地有效（locally significant）"的**：网络里不同节点可以给**同一个**不可路由 SID 绑定**不同语义**——某节点可以把它绑到本地邻接（Adjacency-SID）、某节点绑到 SR 策略（Binding-SID）、某节点绑到业务（Service-SID），互不干扰。这与 SR-MPLS 中"本地有效标签"是同一个概念。

```
    图 3-6：可路由段 vs 不可路由段

   ┌── 可路由（locator 在 IGP 通告） ──────────────────────────────┐
   │  fc00:0:4::/48 可路由 → fc00:0:4::  任一台节点都能把包送到这里   │
   │  fc00:0:4:e000::（uA，挂在同一 locator 下）→ 同样可路由        │
   └───────────────────────────────────────────────────────────────┘

   ┌── 不可路由（locator 未通告，例如空 locator node）─────────────┐
   │  fc00:0:e005::（LN = 0000）→ 只有节点 4 自己认，别的节点查不到  │
   │  要用它，前面必须有一个"把包送到节点 4"的段：                  │
   │      <fc00:0:4:: , fc00:0:e005::>                              │
   │       送我到 4       从 4 的某个接口出去                        │
   └───────────────────────────────────────────────────────────────┘

   本地有效：节点 4 上 fc00:0:e005:: 可以是"去 5 的邻接"
             节点 7 上同样的 fc00:0:e005:: 可以是"去 9 的邻接"
```

*图 3-6：可路由与不可路由 locator/段的可达性差别（按 3.2.3 节与 3.4 节文字绘制）*

## 3.3 IGP Prefix Segment

:::en
An IGP prefix segment steers traffic from anywhere in the IGP domain along the ECMP-aware shortest path to a node or, more generally, to an IGP prefix.
:::

IGP 前缀段把流量从 IGP 域内**任意位置**，沿 **ECMP 感知的最短路径**引导到某台节点，或者更一般地说，引导到某个 IGP 前缀。

:::en
The parent node of a prefix segment advertises the segment locator as an IPv6 prefix in the IGP. Following the normal IGP routing procedure, all other IPv6 nodes in the IGP domain compute the shortest path to the locator and install the corresponding entries in their routing and forwarding tables. Any traffic sent towards a prefix segment by nodes in the IGP domain is thus forwarded along the IGP shortest path to the prefix segment parent node. The transit routers that process the traffic to an SRv6 prefix segment do not require any SRv6 capability since the routing and forwarding on such intermediate nodes are performed based on the segment locator.
:::

前缀段的**父节点**把 segment locator 作为 IPv6 前缀在 IGP 中通告。按正常 IGP 路由流程，域内其他所有 IPv6 节点算出到该 locator 的最短路径，并把对应条目装进路由表与转发表。于是域内任何节点发往前缀段的流量，都沿 IGP 最短路径到达该前缀段的父节点。**转发这类流量的中转路由器不需要任何 SRv6 能力**，因为中间节点的路由与转发完全基于 segment locator（就是普通 IPv6 前缀）。

:::en
Prefix segments are typically routable. There is no known use for a non-routable prefix segment at the time of this writing.
:::

前缀段**通常是可路由的**。撰写本书时**还没有已知场景需要不可路由的前缀段**——因为前缀段的语义就是"按最短路径去这台节点"，不可路由的话这个语义无从谈起。

:::en
Figure 3.4 shows the forwarding path from Node 1 to the Prefix-SID fc00:0:4::, instantiated on Node 4 under the locator fc00:0:4::/48 with the function 0. The path to this Prefix-SID follows the ECMP shortest cost paths via Node 2 and Node 3.
:::

图 3.4（下方图 3-7）展示节点 1 到 Prefix-SID `fc00:0:4::` 的转发路径。该 SID 实例化在节点 4 上、挂在 locator `fc00:0:4::/48` 下、**function 号为 0**。到它的路径沿经节点 2、节点 3 的 ECMP 等价最短代价路径。

```
    图 3-7：原书 Figure 3.4 —— 节点 1 到 Prefix-SID fc00:0:4::（默认链路度量 10）

   ┌──────────────────────────────────────────────────────────────┐
   │  Prefix-SID = locator + function 0 → fc00:0:4::              │
   │  FIB（节点 1）：fc00:0:4::/48 → { Gi0/0/0/0(去2), Gi0/0/0/1(去3) } │
   └──────────────────────────────────────────────────────────────┘

   注意 function = 0：**Prefix-SID 的 SID 值就等于 locator 本身**
   → 于是"到 locator 的路由"与"到这个 SID 的处理"天然重合
   → 这也是 uSID 里 uN 能与 locator 同地址、位移后自动指向下一站的原因
```

*图 3-7：到 Prefix-SID 的 ECMP 最短路径（按原书 Figure 3.4 重绘）*

### 3.3.1 默认端点行为（End）

:::en
The IGP prefix segments are associated with the default SRv6 endpoint behavior, also called "End" behavior (RFC 8986), or one of its flavors. Upon reaching the parent node of an IGP prefix segment, the Destination Address field of the IPv6 header is updated with the next SID in the Segment List, and a lookup is performed on the updated Destination Address.
:::

IGP 前缀段关联**默认的 SRv6 端点行为**，也叫 **End 行为**（RFC 8986），或它的某个 flavor。报文到达前缀段的父节点后，IPv6 头的**目的地址字段被更新为段列表中的下一个 SID**，并对更新后的目的地址做一次查找。

:::en
When the prefix segment is associated with the base (unflavored) End behavior, the next SID is obtained by walking the IPv6 extension header chain until an SRH with a non-zero Segments Left value is found, decrementing the value in the SRH Segments Left field by 1, and reading the entry in the SRH Segment List field at the index indicated by the new Segments Left value. If the packet does not contain an SRH or its Segments Left value is already equal to zero, then the node checks the packet upper-layer header type. If this is an an allowed type (e.g., ICMP) for an SRv6 packet according to the local node configuration, the node consumes the upper-layer header as it would for a regular IPv6 packet. Otherwise (if the type is not allowed), the node produces an ICMP error message and drops the packet.
:::

当前缀段关联**基础（无 flavor）End 行为**时，获取下一个 SID 的步骤如下：

1. 沿 IPv6 扩展头链向前走，直到找到**一个 `Segments Left` 非 0 的 SRH**；
2. 把 SRH 的 `Segments Left` **减 1**；
3. 读取 SRH Segment List 中**由新的 `Segments Left` 指示的下标**处的条目（注意 SID 是倒序编码的，见脚注 1）。

如果报文**没有 SRH**，或 `Segments Left` **已经为 0**，节点就检查报文的**上层头类型**：

- 若该类型在本地配置里**被允许**作为 SRv6 报文的上层（例如 ICMP），节点像处理普通 IPv6 报文那样**消费上层头**；
- 若**不被允许**，节点**产生 ICMP 差错报文并丢弃**该报文。

这一步是"防隧道穿孔"的最后一道检查：SID 列表走完后，如果裸露出来的东西不是预期的载荷类型，就不该继续处理。

:::en
The default endpoint behavior is illustrated in Figure 3.5. Node 2 receives an IPv6 packet whose destination address matches a locally instantiated SRv6 SID, fc00:0:2::, bound to the End behavior, reads the SRH, decrements the Segments Left (SL) value from 2 to 1 (operation 1 in Figure 3.6) and copies the IPv6 address at index 1 in the Segment List into the Destination Address field of the IPv6 header (operation 2 in Figure 3.6). Node 2 then looks up the new destination address, fc00:0:3::, in its forwarding table and transmits the packet along the shortest path to Node 3.
:::

默认端点行为见图 3.5（下方图 3-8 左）。节点 2 收到一个报文，目的地址匹配本地实例化的 SID `fc00:0:2::`（绑定 End 行为）；它读取 SRH，把 `Segments Left` 从 **2 减到 1**（图 3.6 的操作①），并把 Segment List 中**下标 1** 的地址复制进 IPv6 头的目的地址字段（操作②）。随后节点 2 用新目的地址 `fc00:0:3::` 查转发表，沿到节点 3 的最短路径把报文发出。

```
    图 3-8：原书 Figure 3.5 / 3.6 —— End 行为的处理（两次操作）

   收到：DA = fc00:0:2::   SL = 2
   ┌───────────────────────────────────────────────┐
   │ SRH: SL=2  Segment List[0]=fc00:0:5::         │
   │                Segment List[1]=fc00:0:3::     │
   │                Segment List[2]=fc00:0:2::     │
   └───────────────────────────────────────────────┘
        │ ① SL--（2 → 1）
        │ ② DA = Segment List[SL=1] = fc00:0:3::
        ▼
   发出：DA = fc00:0:3::   SL = 1   → 查 FIB（命中 fc00:0:3::/48）→ 去节点 3

   两个动作必须原子完成：先减 SL 再取 DA，或用新 SL 取 DA
   （若先改 DA 后减 SL，中间态会出现"DA 与 SL 不自洽"的报文）
```

*图 3-8：End 行为的两步处理——减 `Segments Left`、换目的地址（按原书 Figure 3.5/3.6 重绘）*

:::en
In theory, multiple prefix segments could be defined for the same locator with different combinations of flavors, but this is rarely useful in practice.
:::

理论上，同一个 locator 下可以定义**多个**前缀段，分别带不同的 flavor 组合；但实践中几乎没用——通常一个 locator 一个前缀段，flavor 一次配齐。

#### 原书侧栏：端点行为 flavor（Endpoint behavior flavors）

:::en
Endpoint behavior flavors, or SID flavors, are extensions or variations that can be applied to an SRv6 endpoint behavior. Each flavor enhances the endpoint behavior with an additional capability, such as removing an exhausted SRH from the packet (see section 3.3.1.2), decapsulating a packet at its final destination (see section 3.3.1.3), or enabling SID compression (see section 3.3.1.1).
:::

端点行为 flavor（也叫 SID flavor）是可以施加到某个 SRv6 端点行为上的**扩展或变体**。每个 flavor 给该行为增加一项能力，例如：把已耗尽的 SRH 从报文中移除（3.3.1.2）、在最终目的地解封装（3.3.1.3）、启用 SID 压缩（3.3.1.1）。

:::en
Applying a flavor does not alter the semantics of the endpoint behavior. For example, a segment bound to the End.X behavior retains its adjacency segment semantics regardless of which flavor, or flavors, are applied to it.
:::

**加 flavor 不改变行为本身的语义**。例如绑定 End.X 行为的段，无论加了哪些 flavor，仍然是"邻接段"语义。

:::en
Each flavor is defined for a set of endpoint behaviors, which may grow over time as new use-cases arise and new behaviors are invented. The flavors defined today apply primarily to the topological and binding segment behaviors. Multiple flavors can be applied concurrently to an endpoint behavior, but some are mutually exclusive.
:::

每个 flavor 都只对**一组特定的端点行为**定义；随着新用例与新行为的出现，这组集合会扩大。目前定义的 flavor 主要作用于**拓扑段**与**绑定段（binding segment）**。一个端点行为可以**同时**加多个 flavor，但有些互斥（如 USP 与 PSP）。

:::en
The flavors described in this chapter apply to both the End and End.X endpoint behaviors, and can be combined without restriction.
:::

本章描述的 flavor 对 **End 与 End.X 两种行为都适用**，并且可以**无限制组合**。

:::en
The End behavior supports the micro-segment, penultimate segment popping, and ultimate segment decapsulation flavors.
:::

End 行为支持三种 flavor：**micro-segment（uSID）**、**penultimate segment popping（PSP）**、**ultimate segment decapsulation（USD）**。下面三小节依次讲。

### 3.3.1.1 Micro-Segment（uSID）flavor

:::en
In a typical deployment scenario, all SIDs in an SRv6 domain are allocated from the same locator block. This locator block is, therefore, repeated multiple times in each SID list. In addition, the combined length of a SID locator, function, and argument is often less than 128 bits. As a result, padding bits are carried along with each SID to fill up the remaining space. However, the Micro-Segment (uSID) flavor allows a headend router to optimize the packet header length by avoiding the locator block repetition and reducing the need for padding bits.
:::

在典型部署中，SRv6 域内**所有 SID 都从同一个 locator block 中分配**。因此这个 locator block 会在每个段列表里**重复出现很多次**。此外，SID 的 locator + function + argument 往往**不足 128 bit**，于是每条 SID 都拖着一段补 0 的 padding 位。**uSID flavor 就是用来消掉这两笔浪费的**：既避免 locator block 重复，又减少 padding。

:::en
With the uSID flavor, a headend router can encode multiple segment routing instructions in each 128-bit SID. These instructions, also called micro-instructions, are represented by Micro-SIDs (uSIDs), and a 128-bit SID containing a series of uSIDs is called a uSID container. Each uSID container carries the locator block followed by a series of uSIDs. The first uSID in the series is the active uSID and makes up the uSID container locator node and function, while the remaining uSIDs and potential padding bits make up the uSID container argument.
:::

有了 uSID flavor，headend 可以在**每个 128 bit SID 中编码多条 SR 指令**。这些指令称为**微指令**，用 **uSID** 表示；一个装着若干 uSID 的 128 bit SID 称为 **uSID 容器**。每个 uSID 容器 = **locator block** + **一串 uSID**。其中：

- **第一个 uSID 是活动 uSID**，它构成容器的 **locator node 与 function**；
- **其余 uSID 以及可能的 padding 位，构成容器的 argument**。

这一句是理解 uSID 的钥匙：**"剩下的指令"在协议上就是"argument"**。所以 3.2 节侧栏说 argument 的值可以随流变化——因为每条流要走的路径本来就可以不同。

:::en
A uSID is typically 16-bit long and allocated from a 32-bit block of the IPv6 Unique Local Address (ULA) space (RFC 4193), such as fc00:0::/32. This allows up to six micro-instructions to be encoded in each uSID container.
:::

uSID 通常 **16 bit** 长，从 IPv6 **ULA 空间（RFC 4193）**的一个 **32 bit 块**中分配，例如 `fc00:0::/32`。这样每个 uSID 容器最多能编码 **6 条微指令**（128 − 32 = 96 = 6 × 16）。

:::en
When a segment list requires six micro-instructions or less, the headend router can steer packets onto it with plain IPv6 encapsulation. The entire segment list is encoded in a single uSID container written into the Destination Address field of the IPv6 header. No SRH is needed. In the occasional event that seven or more segments are required, the headend node appends an SRH carrying the additional uSID containers.
:::

当段列表只需要 **6 条或更少**微指令时，headend 用**纯 IPv6 封装**就能把报文引上去：整个段列表编码进**一个 uSID 容器**，写进 IPv6 头的目的地址字段，**不需要 SRH**。偶尔需要 **7 条及以上**时，headend 才追加一个 SRH 来携带多出来的 uSID 容器。

:::en
When processing a uSID container at the parent node of the active uSID, if the argument value is non-zero, the next SID is constructed by shifting the SID argument value to the left by the length of the active uSID, overwriting the active uSID, and filling the least significant bits of the argument with zeros. If the argument value is 0, the processing follows the regular End behavior (section 3.3.1).
:::

在活动 uSID 的父节点处理容器时：

- 若 **argument 值非 0**：把 argument **整体左移"活动 uSID 的长度"（16 bit）**，覆盖掉活动 uSID，并在最低位补 0，得到下一个 SID；
- 若 **argument 值为 0**：说明容器已到末尾，转为执行**常规 End 行为**（3.3.1 节），即回到 SRH 取下一个 SID。

:::en
A Node-SID with the uSID flavor is called a uNode (or uN) SID. It is the micro-instruction identifier of a node segment.
:::

带 uSID flavor 的 Node-SID 称为 **uNode（uN）SID**，它是"节点段"这条微指令的标识。

:::en
The uNode segment processing is illustrated in Figure 3.7. Node 2 instantiates the SID fc00:0:2:: bound to the End behavior with the uSID flavor. This SID is allocated off the locator block fc00:0::/32 with a 16-bit locator node 0x0002, an empty function, and an 80-bit argument. Node 2 installs the FIB entry fc00:0:2::/48, with a prefix length matching the SID locator and (empty) function, but not the argument. This is to trigger the segment processing regardless of the SID argument value. Indeed, the argument value is unknown when the segment is instantiated: it is constructed by the headend node and may differ for each traffic flow.
:::

uNode 段的处理见图 3.7（下方图 3-9）。节点 2 实例化的 SID `fc00:0:2::` 绑定 End 行为 + uSID flavor。这个 SID 从 locator block `fc00:0::/32` 分配：**16 bit locator node = 0x0002**、**function 为空**、**argument 长 80 bit**。

节点 2 安装的 FIB 条目是 **`fc00:0:2::/48`**——前缀长度只覆盖 locator + （空）function，**不覆盖 argument**。目的就是"**不管 argument 是什么值，都要触发这个段的处理**"。因为实例化这个段的时候，argument 值是未知的：它由 headend 构造，而且**每条流可能都不一样**。

```
    图 3-9：原书 Figure 3.7 / 3.8 —— uN（End + uSID）的位移处理

   SID 位结构（节点 2 的 uN = fc00:0:2::）
   +------------------+------------+----------------------------------+
   | LB = fc00:0::/32 | LN = 0x0002| function = 空 | argument 80 bit   |
   +------------------+------------+----------------------------------+
   |<---- /48，FIB 只装到这里 ---->|<---- 不解析，装的是下一条指令 --->|

   收到：DA = fc00:0:2:3:4::   （3:4 就是 argument）
   ┌──────────────────────────────────────────────────────┐
   │ fc00:0:   2   : 3 : 4 : 0 : 0 : 0                    │
   │ └─block─┘  ↑     └── argument ──┘                    │
   │           uN 命中（/48）                              │
   └──────────────────────────────────────────────────────┘
         │ ① argument 左移 16 bit（覆盖掉 0002）
         │ ② 最低 16 bit 补 0
         ▼
   发出：DA = fc00:0:3:4:0:0:0:0   → 查 FIB 命中 fc00:0:3::/48 → 去节点 3

   整个过程没有 SRH，也不需要"指针"：位移一次，指针自动前进一格
```

*图 3-9：uSID flavor 下的容器位移（按原书 Figure 3.7/3.8 重绘）*

:::en
Upon receiving the packet shown in Figure 3.8, Node 2 determines that the destination address fc00:0:2:3:4:: matches the local SID fc00:0:2:: and carries the argument value 3:4:0:0:0 (boxed). Since the argument value is not 0, Node 2 shifts this value by 16 bits to the left (operation 1 in Figure 3.8) and fills the 16 least significant bits of the destination address with zeros (operation 2 in Figure 3.8). In this case, the endpoint node constructs the new destination address without involving the SRH. The packet in Figure 3.8 does not even contain an SRH. Node 2 then looks up the new destination address, fc00:0:3:4::, in its forwarding table and transmits the packet along the shortest path to Node 3.
:::

收到图 3.8 所示报文后，节点 2 判断目的地址 `fc00:0:2:3:4::` 匹配本地 SID `fc00:0:2::`，且携带的 argument 值为 `3:4:0:0:0`（图中方框）。argument 非 0，于是节点 2 把这个值**左移 16 bit**（操作①），并把目的地址**最低 16 bit 补 0**（操作②）。这个场景里，端点节点**完全不涉及 SRH** 就构造出了新目的地址——图 3.8 的报文**根本不含 SRH**。节点 2 用新目的地址 `fc00:0:3:4::` 查表，沿到节点 3 的最短路径发出。

:::en
In Figure 3.9 we show a scenario where a long segment list requires the presence of an SRH. When Node 4 receives the packet, the SID in the destination address has the argument value 0. Node 4 therefore applies the regular End operation described in section 3.3.1: it decrements the SL value in the SRH from 1 to 0 and copies the SID at index 0 in the Segment List to the Destination Address field of the IPv6 header. Node 4 then looks up the new destination address, fc00:0:5:6:7::, and forwards the packet accordingly.
:::

图 3.9（下方图 3-10）展示"段列表太长、必须带 SRH"的场景。节点 4 收到的报文里，目的地址中的 SID 其 **argument 为 0**——意味着"本容器里的指令用完了"。于是节点 4 执行**常规 End 操作**（3.3.1 节）：把 SRH 的 `SL` 从 **1 减到 0**，把 Segment List[0] 的 SID 复制进目的地址。节点 4 再用新目的地址 `fc00:0:5:6:7::` 查表转发。

```
    图 3-10：原书 Figure 3.9 —— uSID 容器用尽，回到 SRH 取下一容器

   DA = fc00:0:4:2:3::   ← argument 还有 2:3
        │ 节点 4 位移 16 bit
        ▼
   DA = fc00:0:2:3:0::   （继续在同一个容器内走动）
        … 直到 argument 变成 0 …
        ▼
   DA = fc00:0:4::       ← argument = 0 → 容器结束
        │ 常规 End：SL-- ，DA = Segment List[SL]
        ▼
   DA = fc00:0:5:6:7::   ← SRH 里的下一个 uSID 容器（又能走 6 拍）

   规律：容器内靠"位移"前进，容器之间靠"SL/DA"前进
```

*图 3-10：uSID 容器结束时切回 SRH（按原书 Figure 3.9 重绘）*

:::en
The uSID flavor is standardized at the IETF as the NEXT-C-SID flavor in draft-ietf-spring-srv6-srh-compression.
:::

uSID flavor 在 IETF 标准化为 **NEXT-C-SID flavor**，见 `draft-ietf-spring-srv6-srh-compression`（现已成 RFC 9800）。注意：读 IANA 码点时看到 `End with NEXT-CSID`，说的就是这个 flavor，不要与 `NEXT-ONLY-CSID` 混。

### 3.3.1.2 Penultimate Segment Pop（PSP）flavor

:::en
The Penultimate Segment Pop flavor allows the node processing the penultimate SID in a segment list to remove the SRH from the packet. As a result, the ultimate segment router receives a plain IPv6 packet without an SRH, which simplifies the processing of SRH at the destination node and reduces the packet size for the last hop.
:::

**PSP** flavor 让"处理段列表中**倒数第二个 SID** 的节点"把 **SRH 从报文中移除**。结果是：**最后一段（ultimate segment）的路由器收到的是一张不带 SRH 的普通 IPv6 报文**，从而简化目的节点的 SRH 处理，并减小最后一跳的报文体积。

:::en
The behavior of the penultimate segment router is illustrated in Figures 3.10, 3.11 and 3.12. The packet contains an SRH with Segments Left equal to 1 and a Segment List with two segments: fc00:0:5::, which is the last segment in the path, bound to the End behavior, and fc00:0:4::, which is the penultimate segment, bound to the End behavior with the PSP flavor.
:::

倒数第二段路由器的行为见图 3.10–3.12（下方图 3-11）。报文含一个 SRH：`Segments Left = 1`，Segment List 有两项：

| 下标 | SID | 行为 |
|---|---|---|
| 0 | `fc00:0:5::` | End（**最后一段**，路径终点） |
| 1 | `fc00:0:4::` | **End + PSP**（倒数第二段） |

:::en
When Node 4 receives the packet (Figure 3.10), the destination address matches the penultimate SID fc00:0:4::. Then, instead of following the regular End operation described in section 3.3.1, Node 4: Copies the last SID in the Segment List, fc00:0:5::, to the Destination Address field of the IPv6 header (operation 1). Sets the Segments Left value to 0 (operation 2). Removes the SRH from the packet (operation 3).
:::

节点 4 收到报文（图 3.10）时，目的地址匹配倒数第二个 SID `fc00:0:4::`。此时**不执行** 3.3.1 的常规 End 操作，而是：

1. 把 Segment List 中**最后一个 SID** `fc00:0:5::` 复制到 IPv6 头的**目的地址**字段（操作①）；
2. 把 `Segments Left` **置 0**（操作②）；
3. 把 **SRH 从报文中移除**（操作③）。

```
    图 3-11：原书 Figure 3.10 / 3.11 / 3.12 —— PSP 的三步与逐跳变化

   入方向（节点 4 收到）：
      外层 IPv6  DA = fc00:0:4::   NH = 43(SRH)
      └─ SRH:  SL = 1
               Segment List[0] = fc00:0:5::   ← 最后一段
               Segment List[1] = fc00:0:4::   ← 就是当前 DA（PSP）
      └─ 上层：L4 载荷

   节点 4 动作（红色三步）：
      ① DA = Segment List[SL] = fc00:0:5::
      ② SL = 0
      ③ 删除 SRH → 外层 IPv6 的 Next Header 改为上层协议号

   出方向（去节点 5）：
      外层 IPv6  DA = fc00:0:5::   NH = L4（不再是 43）
      无 SRH，报文变短 8 + 8×N 字节

   对末节点（节点 5）而言：这就是一张普通 IPv6 报文，它连 SRH 都不用解析
```

*图 3-11：PSP flavor 的三步处理（按原书 Figure 3.10/3.11/3.12 合并重绘）*

:::en
Note that copying the last SID in the Segment List to the Destination Address field of the IPv6 header is equivalent to decrementing the Segments Left value and reading the Segment List entry at the corresponding index. The operation is described differently for clarity.
:::

注意：**"把 Segment List 最后一个 SID 复制到目的地址"与"把 `Segments Left` 减 1 后按下标读 Segment List"是等价的**——这里只是换了个说法便于理解（因为 SL 已经等于 1，减 1 后就是下标 0，正好是最后一项）。

:::en
Upon receiving the packet from Node 4 (Figure 3.12), Node 5 finds out that the Destination Address field matches its local SID fc00:0:5::, bound to the End behavior. However, the packet does not contain any SRH. The default endpoint processing (section 3.3.1) would then check the upper-layer header type and consume the packet accordingly.
:::

节点 5 从节点 4 收到报文（图 3.12）后，发现目的地址匹配本地 SID `fc00:0:5::`（绑定 End 行为）。但**报文不含任何 SRH**。此时默认端点处理（3.3.1 节）会去检查**上层头类型**，并据此消费报文。

于是 End 行为在没有 SRH 时的处理逻辑（"检查上层类型，允许则消费，否则 ICMP 差错并丢弃"）就成了 PSP 能工作的**配套前提**——PSP 负责"把 SRH 拿掉"，End 负责"没有 SRH 也能收场"。

#### 原书侧栏：PHP 与 PSP —— MPLS 与 SRv6 的类比

:::en
The penultimate segment pop flavor is the exact analog of the penultimate hop popping (PHP) behavior in MPLS. In MPLS, the penultimate node pops the last label and forwards a plain IPv4 or IPv6 packet to the egress node. This relieves the egress node from performing two lookups. Similarly, in SRv6, the PSP flavor relieves the egress node from processing the SRH.
:::

PSP flavor 是 MPLS 中 **PHP（倒数第二跳弹出）**行为的精确类比：MPLS 里倒数第二台节点弹掉最后一个标签，把裸 IPv4/IPv6 报文交给出口节点，从而让出口节点**省掉一次查表**；SRv6 里 PSP flavor 做的是同一件事——让出口节点**省掉 SRH 处理**。

:::en
Note that, as opposed to MPLS PHP, the PSP flavor is not mandatory and is not enabled by default. In MPLS, PHP has been traditionally enabled by default for many years, but this is no longer the case in modern deployments.
:::

与 MPLS PHP 的重要差别：**PSP flavor 不是强制的，也不是默认开启的**。MPLS 里 PHP 传统上默认开启了很多年，但现代部署已不再如此（因为 PHP 会破坏出口节点的"末跳信息"，给 telemetry 与排障带来麻烦）。

实践建议：如果出口节点需要从 SRH 里读信息（例如**带 argument 的业务 SID、SID 列表用于回溯路径、按 SL 做末跳计量**），就**不要**开 PSP；纯转发场景开 PSP 能省带宽和省末跳开销。

### 3.3.1.3 Ultimate Segment Decapsulation（USD）flavor

:::en
The Ultimate Segment Decapsulation flavor allows the endpoint node of a segment list to remove the outer IPv6 header from the packet and forward the inner packet to its final destination. In this context, the SRv6 segment list is used as a traffic-engineered tunnel between the segment list source and the segment list destination.
:::

**USD** flavor 让段列表的**端点节点**把**外层 IPv6 头摘掉**，把内层报文转发到最终目的地。在这个语境下，SRv6 段列表被当作"从段列表源到段列表目的"的 **TE 隧道**使用。

:::en
The behavior of the ultimate segment router is illustrated in Figures 3.13 and 3.14. The packet contains an SRH with Segments Left equal to 0 and a Segment List with two segments.
:::

最后一段路由器的行为见图 3.13、3.14（下方图 3-12）。报文含一个 SRH：`Segments Left = 0`，Segment List 有两项。

:::en
When Node 5 receives the packet (Figure 3.13), the destination address matches the last SID fc00:0:5::, bound to the End behavior with the USD flavor. As depicted in Figure 3.14, Node 5 then removes the outer IPv6 header (operation 1). The resulting inner IPv6 packet includes the SRH, whose Segments Left value is already 0. The node then forwards the inner packet to its final destination.
:::

节点 5 收到报文（图 3.13）时，目的地址匹配最后一个 SID `fc00:0:5::`（End + USD）。如图 3.14 所示，节点 5 随后**摘掉外层 IPv6 头**（操作①）。得到的**内层 IPv6 报文仍然包含 SRH**，其 `Segments Left` 已经为 0。然后节点把内层报文转发到最终目的地。

```
    图 3-12：原书 Figure 3.13 / 3.14 —— USD 解封装

   入方向（节点 5 收到，自己就是最后一段）：
      ┌─────────────────────────────────────────────┐
      │ 外层 IPv6  DA = fc00:0:5::  NH = 43         │  ← 隧道头
      │   SRH: SL = 0, Segment List = [.., ..]      │
      │   ┌───────────────────────────────────────┐ │
      │   │ 内层 IPv6  DA = 2001:db8::1  用户报文  │ │  ← 被隧道的东西
      │   └───────────────────────────────────────┘ │
      └─────────────────────────────────────────────┘
               │ ① 剥掉外层 IPv6 头（含外层扩展头）
               ▼
   出方向：内层 IPv6 报文（SRH 仍在，SL=0）→ 按内层 DA 转发给最终目的地

   与 PSP 的区别：PSP 只摘 SRH，报文还是个 SRv6 报文；USD 摘的是"整个外层头"
```

*图 3-12：USD flavor 摘除外层 IPv6 头（按原书 Figure 3.13/3.14 重绘）*

:::en
Note that the inner packet still contains the SRH: this is a fundamental difference between the PSP and USD flavors. The PSP flavor only removes the SRH, while the USD flavor removes the entire outer IPv6 header, this is, the IPv6 header and its extension headers, including the SRH.
:::

**内层报文仍带着 SRH**——这是 PSP 与 USD 的**根本区别**：

| flavor | 摘掉什么 | 出口节点看到什么 | 典型用途 |
|---|---|---|---|
| **PSP** | 只摘 **SRH** | 普通 IPv6 报文，DA = 最后一段 SID | 省最后一跳处理，仍在自己的地址空间内转 |
| **USD** | 摘掉**整个外层 IPv6 头**（含扩展头、SRH） | **内层用户报文**（可能还封着 SRH） | 隧道出口，把用户流量"落地" |

#### 原书侧栏：USD 与 "Next Header" 字段

:::en
When the USD flavor removes the outer IPv6 header, the inner IPv6 packet must be identified. This is achieved by the Next Header field of the outer IPv6 header pointing to the inner IPv6 header. Unlike the "IPv4-in-IPv6" case where the protocol number 4 is used, there is no dedicated protocol number for "IPv6-in-IPv6": the value 41 is used.
:::

USD 摘掉外层头之后，怎么知道"里面是 IPv6"？靠**外层 IPv6 头的 Next Header 字段指向内层 IPv6 头**。IPv4-in-IPv6 用协议号 **4**；IPv6-in-IPv6 **没有专用号**，用的是 **41**（IPv6 encapsulation）。

:::en
Note that when an SRH is present, the Next Header field of the outer IPv6 header points to the SRH (value 43), and the SRH's Next Header field points to the inner IPv6 header (value 41).
:::

有 SRH 时，指针是两级的：**外层 IPv6 的 Next Header = 43（指向 SRH）**；**SRH 的 Next Header = 41（指向内层 IPv6）**。所以 USD 节点判断"里面是不是 IPv6"实际是读 **SRH 的 Next Header**。

### 3.3.1.4 组合 PSP 与 USD flavor

:::en
The PSP and USD flavors may be combined, as illustrated in Figures 3.15 and 3.16. In this case, the penultimate segment router pops the SRH and forwards a plain IPv6 packet to the ultimate segment router, which then decapsulates the packet.
:::

PSP 与 USD 可以**组合**使用，见图 3.15、3.16（下方图 3-13）。此时：**倒数第二段路由器弹掉 SRH**，把一张**裸 IPv6 报文**交给最后一段路由器，后者再执行**解封装**。

```
    图 3-13：原书 Figure 3.15 / 3.16 —— PSP + USD 组合

   节点 4（End + PSP，SL=1）              节点 5（End + USD，SL=0）
   ┌──────────────────────────┐          ┌──────────────────────────┐
   │ 外层 DA=fc00:0:4::       │          │ 外层 DA=fc00:0:5::       │
   │ SRH: SL=1                │  裸报文   │ NH=41（无 SRH，已被摘）    │
   │ 内层 用户报文             │ ───────▶ │ 内层 用户报文             │
   └──────────────────────────┘  已摘SRH  └──────────────────────────┘
        ① DA=最后一段 ② SL=0                  ① 摘外层 IPv6 头
        ③ 摘 SRH                               ② 转发内层报文到目的地

   好处：最后一跳既不携带 SRH（省字节），也不需要解析 SRH（省处理）
   典型场景：核心到 PE 的 TE 隧道，PE 上要把用户流量交给业务 VRF
```

*图 3-13：PSP 与 USD 组合时的逐跳效果（按原书 Figure 3.15/3.16 重绘）*

:::en
The combination of these two flavors is very useful in practice: it removes the SRH from the last hop, reducing the packet size, and it also removes the outer IPv6 header at the destination, so that the destination node can forward the inner packet to its final destination without any SRv6-specific processing.
:::

这两种 flavor 的组合**在实践中非常有用**：既在最后一跳去掉了 SRH（减小报文），又在目的节点去掉了外层 IPv6 头，于是目的节点**不需要任何 SRv6 特定处理**就能把内层报文转发到最终目的地——PE 上"隧道到此结束、进入业务处理"是最典型的用法。

### 3.3.2 配置

:::en
There is nothing to configure for the unflavored End behavior: any locator advertised in the IGP automatically instantiates a prefix segment bound to the End behavior, as discussed in section 3.2.1.
:::

**无 flavor 的 End 行为不需要任何配置**：任何在 IGP 中通告的 locator 都会自动实例化一个绑定 End 行为的前缀段（见 3.2.1 节）。

:::en
A prefix segment bound to the End behavior with the desired flavors is configured under the locator, as shown in Example 3.5. In this example, the locator MAIN is configured with the uSID and PSP flavors. Note that End.X segments can also be configured with flavors, as we will see in section 3.4.2.
:::

带 flavor 的前缀段则在 locator 下配置，见例 3.5。本示例给 locator `MAIN` 配了 **uSID 与 PSP** 两种 flavor。注意 End.X 段同样可以配 flavor（见 3.4.2 节）。

**例 3.5：给 locator MAIN 的前缀段配 uSID + PSP flavor**

```
segment-routing srv6
  locators
    locator MAIN
      prefix fc00:0:4::/48
      micro-segment behavior unode psp
```

读法：`unode` = End + uSID；`psp` = 加 PSP。**写在这个 locator 块下，作用于该 locator 自动生成的前缀段**；同一节点上的其他 locator 各自独立配置 flavor。

### 3.3.3 通告

:::en
Prefix segments are advertised in the IGP as sub-TLVs of the SRv6 Locator TLV, described in section 3.2.2. The sub-TLV used to advertise a prefix segment instantiated with the End behavior is the SRv6 End SID sub-TLV.
:::

前缀段作为 **SRv6 Locator TLV 的 sub-TLV** 在 IGP 中通告（Locator TLV 见 3.2.2 节）。用来通告"以 End 行为实例化的前缀段"的 sub-TLV，就是 **SRv6 End SID sub-TLV**。

#### 3.3.3.1 SRv6 End SID sub-TLV

:::en
Figure 3.17 shows the SRv6 End SID sub-TLV in IS-IS (OSPF uses the same structure with a different sub-TLV number).
:::

图 3.17（下方图 3-14）是 IS-IS 中的 SRv6 End SID sub-TLV。**OSPFv3 用完全相同的结构，只是 sub-TLV 编号不同**。

```
    图 3-14：原书 Figure 3.17 —— IS-IS SRv6 End SID sub-TLV

   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |   Type = 5    |    Length     |     Flags     |  Algorithm    |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |                        SID（16 octets，完整 128 bit）           |
   +                                                               +
   |                                                               |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   | Sub-sub-TLV Len|        Sub-sub-TLVs（如 SID Structure）        |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

   IS-IS：sub-TLV Type = 5（End SID）、11（End.X SID）
   OSPFv3：sub-TLV Type = 2（End SID）、3（End.X SID）——结构相同
   SID 字段总是 16 字节，不做变长压缩（与 Locator 字段不同）
```

*图 3-14：IS-IS SRv6 End SID sub-TLV（按原书 Figure 3.17 与 RFC 9352 §3.2 绘制）*

:::en
Table 3.1 describes the fields of the SRv6 End SID sub-TLV.
:::

表 3.1 说明 SRv6 End SID sub-TLV 的字段。

**表 3.1：SRv6 End SID sub-TLV 字段**

| 字段 | 说明 |
|---|---|
| **Type** | IS-IS `5` / OSPFv3 `2`，标识 SRv6 End SID sub-TLV |
| **Length** | sub-TLV value 的字节数，含 sub-sub-TLV |
| **Flags** | 目前全部保留（置 0），未来用于定义新的属性 |
| **Algorithm** | 与该 SID 关联的 IGP 算法（RFC 8402）。**必须与承载它的 Locator TLV 中的 Algorithm 一致**，否则接收方应忽略该 sub-TLV |
| **SID** | 完整的 128 bit SID 值（**定长 16 字节**） |
| **Sub-sub-TLV Length / Sub-sub-TLVs** | 一个或多个 sub-sub-TLV，例如 **SRv6 SID Structure**（见 3.3.3.2） |

#### 3.3.3.2 SRv6 SID Structure sub-sub-TLV

:::en
The SRv6 SID Structure sub-sub-TLV carries the length of the locator, function, and argument fields of an SRv6 SID, as well as the length of the locator block and locator node sub-fields within the locator. Its structure is shown in Figure 3.19.
:::

**SRv6 SID Structure sub-sub-TLV** 携带该 SID 的 **locator、function、argument 三个字段的长度**，以及 locator 内部 **locator block 与 locator node 两个子字段的长度**。结构见图 3.19（下方图 3-15）。

:::en
This sub-sub-TLV is essential for the correct operation of the network: without it, a node receiving an SRv6 SID from the IGP would not know where the locator ends and the function begins, and thus would not be able to determine the locator of the SID (which is needed, for example, to compute the shortest path to the SID), nor to perform any operation on the argument field.
:::

这个 sub-sub-TLV **对网络正确运行至关重要**：没有它，从 IGP 收到 SRv6 SID 的节点就**不知道 locator 在哪里结束、function 从哪里开始**，于是既算不出该 SID 的 locator（而"算到 SID 的最短路径"正需要 locator），也无法对 argument 字段做任何操作。

:::en
Nodes are required to advertise the SRv6 SID Structure sub-sub-TLV for all the SIDs they advertise, and to interpret it correctly when received. If a node receives a SID without the SID Structure sub-sub-TLV, it should assume that the SID has an empty argument field and a locator length equal to ... the locator length advertised in the parent Locator TLV.
:::

节点**必须**为它通告的所有 SID 都带 SID Structure sub-sub-TLV，并**正确地解释**收到的这个字段。如果收到的 SID **没带** SID Structure，接收方应假定：**argument 字段为空**，**locator 长度等于父 Locator TLV 里通告的 locator 长度**。

```
    图 3-15：原书 Figure 3.19 —— SRv6 SID Structure sub-sub-TLV

   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |  Type = 1     |    Length     |  Locator Block Len (1 octet)  |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   | Locator Node Len| Function Len |  Argument Len|               |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+               +
   |              Sub-sub-sub-TLVs（保留，未来扩展）                  |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

   四个长度字段相加必须 ≤ 128，不足部分即 padding（补 0 位）
   例：LB=32, LN=16, Fun=0, Arg=80 → 32+16+0+80 = 128，无 padding（uN）
   例：LB=32, LN=16, Fun=32, Arg=0 → 共 80，剩 48 bit padding（普通 SID）
```

*图 3-15：SRv6 SID Structure sub-sub-TLV（按原书 Figure 3.19 与 RFC 9352 §3.3 绘制）*

为什么这个 TLV 决定成败：**uSID 的位移是"按活动 uSID 长度左移"**。接收方如果不知道 `LN` 长度是 16 bit，就无从计算位移量，整个压缩方案无法互操作——这就是它被列为**强制**的原因。

:::en
The SRv6 SID Structure sub-sub-TLV is also used to verify the consistency of the SID allocations across the network and to detect misconfigurations: for example, a node can check that all the SIDs received from a peer share the same locator block and locator node lengths.
:::

这个 sub-sub-TLV 还被用来**校验全网 SID 分配的一致性、发现配置错误**：例如节点可以检查"从某个邻居收到的所有 SID 是否共享同一个 locator block 长度与 locator node 长度"——不一致就是规划出了问题。

## 3.4 IGP Adjacency Segment

:::en
An IGP adjacency segment forces the traffic into a particular IGP adjacency, regardless of the IGP metric of that adjacency. Like the prefix segment, the adjacency segment is a topological segment.
:::

IGP 邻接段把流量**强制压到某条特定的 IGP 邻接**上，**不管这条邻接的 IGP 度量是多少**。与前缀段一样，邻接段也是**拓扑段**。

:::en
The parent node of the adjacency segment advertises the segment in the IGP, but the segment locator of an adjacency segment is typically not advertised as an IPv6 prefix. As a result, adjacency segments are non-routable segments: they can only be used in a segment list if the preceding segment in the list steers the traffic to the parent node of the adjacency segment (see section 3.2.3).
:::

邻接段的父节点在 IGP 中通告这个段，但**邻接段的 segment locator 通常不作为 IPv6 前缀通告**。因此邻接段是**不可路由段**：只有当段列表中**前一个段把流量引导到邻接段的父节点**时，它才能被使用（见 3.2.3 节）。

:::en
The parent node of an adjacency segment instantiates the segment as an SRv6 SID bound to the End.X endpoint behavior (RFC 8986). The End.X behavior forces the packet out of a specific interface, or set of interfaces, regardless of the shortest path to the packet destination.
:::

邻接段的父节点把该段实例化为一个绑定 **End.X** 端点行为（RFC 8986）的 SRv6 SID。**End.X 行为强制报文从某个特定接口（或一组接口）发出**，而不看目的地址的最短路径。

:::en
The SID of an adjacency segment is locally significant: any node in the network may use the same SID value for a different adjacency segment. This is in contrast with the prefix segment, whose SID is unique across the IGP domain.
:::

邻接段的 SID 是**本地有效**的：网络里任何节点都可以用**同一个 SID 值**表示**不同的**邻接段。这与前缀段形成对照——前缀段的 SID 在 IGP 域内**全局唯一**。

```
    图 3-16：原书 Figure 3.21 / 3.22 —— 可路由前缀段 vs 不可路由邻接段

   前缀段（可路由）                        邻接段（不可路由）
   fc00:0:4::/48 在 IS-IS 里通告           fc00:0:e005:: 不进入任何 LSP
        │                                        │
        ▼                                        ▼
   任何节点都能算路并送包到节点 4          只有知道"节点 4 上有这个 SID"的
    （中转节点无需 SRv6 能力）             headend 才会用，且必须前置一个
                                          把包送到节点 4 的段：
                                          <fc00:0:4::, fc00:0:e005::>
                                              送我到 4   从 4 的 Eth2 出去

   节点 4：fc00:0:e005:: → Eth2（去节点 5）
   节点 7：fc00:0:e005:: → Eth1（去节点 9）   ← 同一个值，不同语义，互不影响
```

*图 3-16：邻接段的本地有效性与不可路由性（按原书 Figure 3.21/3.22 重绘）*

:::en
Figure 3.21 illustrates the use of the adjacency segment fc00:0:e005::, instantiated on Node 4 to force the traffic out of the interface connected to Node 5. Note that the SID value of the adjacency segment is allocated from a different locator (fc00:0:e000::/48), which is not advertised in the IGP.
:::

图 3.21（图 3-16 右侧）演示邻接段 `fc00:0:e005::` 的用法：它实例化在节点 4 上，强制流量从**连节点 5 的那个接口**出去。注意这个邻接段的 SID 值是从**另一个 locator（`fc00:0:e000::/48`）**分配的，而**这个 locator 并不在 IGP 中通告**。

用"空 locator node"来集中放不可路由 SID 是一种常见规划：`e000`/`e001`… 这类节点号不对应任何真实节点，天然不可路由，一眼就能从地址看出"这是本地段"。

### 3.4.1 End.X 端点行为

:::en
The End.X endpoint behavior is the adjacency segment behavior: it forces the packet out of a specific interface or set of interfaces. The destination address of the packet is updated with the next SID in the segment list, as in the End behavior, and the packet is then transmitted out of the interface (or interfaces) associated with the segment.
:::

**End.X 就是邻接段的行为**：强制报文从**特定接口（或一组接口）**发出。目的地址按段列表**更新为下一个 SID**（与 End 行为一样），然后报文从与该段关联的接口（们）发出。

:::en
The End.X behavior supports the same three flavors as the End behavior: micro-segment, penultimate segment popping, and ultimate segment decapsulation. In addition, the End.X behavior supports the NEXT-ONLY-CSID flavor, which is used for the compression of adjacency segments only.
:::

End.X 支持与 End **相同的三种 flavor**（uSID / PSP / USD）。此外 End.X 还支持 **NEXT-ONLY-CSID** flavor，用于"只压缩邻接段"的场景（区别于 NEXT-C-SID 的"压缩整个列表"）。

```
    图 3-17：原书 Figure 3.23 —— End.X 的处理

   收到：DA = fc00:0:e005::（End.X，绑定 Eth2）
          SRH: SL = 1
        │
        │ ① SL--（1 → 0）
        │ ② DA = Segment List[0]
        ▼
   发出接口：**Eth2**（不看 DA 的最短路径！）
   发出报文：DA = fc00:0:5::  →  节点 5 收到后按普通 End/或按 SID 处理

   与 End 的唯一差别：决定出接口时，End 查 FIB（按 DA 最短路径），
                        End.X 直接绑死接口（可 ECMP 到一组链路）
```

*图 3-17：End.X 的"绑定出接口"特性（按原书 Figure 3.23 重绘）*

#### 3.4.1.1 Micro-Segment（uSID）flavor

:::en
When the End.X behavior is associated with the uSID flavor, the SID is called a uA SID (where "A" stands for adjacency). Like the uN SID, the uA SID is typically 16 bits long and is encoded in the same uSID container as the uN SID of the parent node.
:::

End.X 行为关联 uSID flavor 时，该 SID 称为 **uA SID**（A = adjacency）。与 uN 一样，uA 通常 **16 bit** 长，并且**与父节点的 uN 编码在同一个 uSID 容器里**。

:::en
A uA SID is instantiated under a non-routable locator, since it must be preceded by the uN SID of its parent node in the segment list. The uN SID and the uA SID are allocated from the same locator block, so that the shift operation described in section 3.3.1.1 transitions from the uN SID to the uA SID seamlessly.
:::

uA SID 实例化在**不可路由 locator**下，因为段列表里它**必须**紧跟其父节点的 uN SID。uN 与 uA **从同一个 locator block 分配**，这样 3.3.1.1 节的位移操作才能**无缝**从 uN 转到 uA。

#### 原书侧栏：uN 与 uA 在 FIB 中的分工（GIB 与 LIB）

在 uSID 节点上，转发表被拆成两半：

- **GIB（Global IPv6 Index Block）**：装**可路由**的 uN（`fc00:0:2::/48` 这类），查找时按"locator + locator node"命中，执行**位移**；
- **LIB（Local IPv6 Index Block）**：装**不可路由**的 uA（`fc00:0:e005::` 这类），只有把包送到本节点之后才会命中，执行**绑接口转发**。

为什么必须拆开：uN 的处理是"改 DA 再查表"，uA 的处理是"按绑定的出接口发出去"。两类条目的**前缀长度、命中顺序、动作**都不同；把 16 bit 的 uA 混进全局 IPv6 表里会导致前缀冲突和查找深度爆炸。

```
    图 3-18：GIB 与 LIB 的划分

   ┌──────────── 节点 4 的转发表 ────────────────────────────────┐
   │ GIB（全局，来自 IGP 的 locator）                             │
   │   fc00:0:2::/48  → Eth1  （邻居 2 的 locator）              │
   │   fc00:0:3::/48  → Eth3  （邻居 3 的 locator）              │
   │   fc00:0:4::/48  → local  → 执行 uN：位移 DA                 │
   ├──────────── LIB（本地，只在本节点有意义）───────────────────┤
   │   fc00:0:e002::  → Eth1  （uA：去邻居 2 的邻接）             │
   │   fc00:0:e005::  → Eth2  （uA：去邻居 5 的邻接）             │
   └─────────────────────────────────────────────────────────────┘

   命中顺序：DA 先查 GIB（可路由部分）；只有"DA 的 locator==本节点"
             才会进入 LIB 做 uA 匹配 → 避免本地段泄漏到全局转发
```

*图 3-18：uSID 节点的 GIB/LIB 分工（按 RFC 8986bis 与 IOS XR 实现描述绘制）*

:::en
Figure 3.25 illustrates the combined forwarding entry for the uN SID fc00:0:2:: and the uA SID fc00:0:e005:: on Node 2. Both SIDs are 16 bits long: the uN SID is allocated off the locator fc00:0:2::/48, while the uA SID is allocated off the non-routable locator fc00:0:e000::/48.
:::

图 3.25（下方图 3-19）展示节点 2 上 **uN `fc00:0:2::` 与 uA `fc00:0:e005::` 的合并转发表项**。两个 SID 都是 16 bit：uN 从 locator `fc00:0:2::/48` 分配，uA 从**不可路由** locator `fc00:0:e000::/48` 分配。

:::en
The combined forwarding entry is a single FIB entry covering the locator block fc00:0::/32 and 16 bits of the uSID, i.e., a /48 prefix. This entry is used to match both the uN SID and the uA SID, since they are both encoded in the same position of the destination address.
:::

合并转发表项是**一条 FIB 条目**：覆盖 locator block `fc00:0::/32` 加 **16 bit uSID**，即一个 **/48 前缀**。这条条目同时用于匹配 **uN 与 uA**——因为二者都编码在目的地址的**同一位置**。

:::en
When the packet arrives, the node performs a lookup on the destination address and finds the matching /48 entry. If the 16 bits following the locator block match the uN SID value, the node performs the uN processing (shift). If they match a uA SID value, the node performs the uA processing (forward out of the bound interface).
:::

报文到达后，节点对目的地址查表，命中那条 **/48** 条目。然后看**紧随 locator block 之后的那 16 bit**：

- 若等于 **uN** 值 → 执行 **uN 处理（位移）**；
- 若等于某个 **uA** 值 → 执行 **uA 处理（从绑定接口发出）**。

:::en
This is a key scalability property of uSID: a single FIB entry covers both the uN and all the uA SIDs of a node, regardless of the number of adjacencies.
:::

这是 uSID 的一项关键可扩展性优势：**一条 FIB 条目同时覆盖一个节点的 uN 及其所有 uA SID**，与该节点有多少条邻接**无关**。

```
    图 3-19：原书 Figure 3.25 —— uN 与 uA 共用一条 /48 条目

   目的地址：  fc00:0 : XXXX : ....
               └ /32 ┘  └16bit┘
     FIB 条目： fc00:0::/48  → 命中本节点，转交"uSID 引擎"

     uSID 引擎按接下来的 16 bit 分派：
       XXXX == 0002（uN） → 动作：DA <<= 16bit，最低 16 bit 补 0，再查表
       XXXX == e002（uA） → 动作：从 Eth1 发出（去邻居 2）
       XXXX == e005（uA） → 动作：从 Eth2 发出（去邻居 5）
       XXXX == 其他      → 无匹配，按普通 IPv6 处理/丢弃

   → N 条邻接不需要 N 条全局路由，只需 1 条 /48 + LIB 内 N 条本地条目
```

*图 3-19：uN 与 uA 共享同一 /48 FIB 条目（按原书 Figure 3.25 重绘）*

#### 3.4.1.2 PSP 与 USD flavor

:::en
The End.X behavior supports the PSP and USD flavors with exactly the same semantics as the End behavior. Figures 3.26 and 3.27 illustrate the PSP flavor applied to an End.X segment.
:::

End.X 支持 **PSP 与 USD** flavor，语义与 End **完全相同**。图 3.26、3.27（下方图 3-20）演示 PSP 施加在 End.X 段上的情形。

:::en
In the example, the segment list contains the adjacency segment fc00:0:e005:: (End.X with PSP) and the prefix segment fc00:0:5:: (End). When Node 4 receives the packet with the destination address fc00:0:e005::, it copies the last SID in the segment list to the destination address, sets the Segments Left to 0, pops the SRH, and forwards the packet out of the interface associated with the adjacency segment.
:::

例中段列表包含邻接段 `fc00:0:e005::`（End.X + PSP）与前缀段 `fc00:0:5::`（End）。节点 4 收到目的地址为 `fc00:0:e005::` 的报文后：把段列表中**最后一个 SID** 复制到目的地址、把 `Segments Left` **置 0**、**弹出 SRH**，然后**从该邻接段关联的接口把报文发出**。

```
    图 3-20：原书 Figure 3.26 / 3.27 —— End.X + PSP

   SL=1，Segment List = [ fc00:0:5:: , fc00:0:e005:: ]
                                    ▲ 末段      ▲ 当前 DA（End.X+PSP）
   节点 4：
     ① DA ← fc00:0:5::      ② SL ← 0      ③ 弹 SRH
     ④ **从 Eth2 发出**（邻接绑定），不是按 DA 查表！
   → 节点 5 收到一张普通 IPv6 报文，DA = fc00:0:5::

   用途：用邻接段精确控制"从哪条链路出"，同时让末节点省掉 SRH 处理
        典型于 TI-LFA 修复路径的最后一跳（见 3.5 节）
```

*图 3-20：End.X 与 PSP flavor 组合（按原书 Figure 3.26/3.27 重绘）*

### 3.4.2 配置

:::en
An adjacency segment bound to the End.X behavior is configured on an interface, under the IS-IS or OSPF instance that enables SRv6, as shown in Example 3.6.
:::

绑定 End.X 行为的邻接段**在接口上配置**，位置在"启用了 SRv6 的 IS-IS 或 OSPF 实例"之下，见例 3.6。

**例 3.6：在节点 4 的 Gi0/0/0/2 接口上配置邻接段**

```
interface GigabitEthernet0/0/0/2
  address-family ipv6 unicast
    router isis 1
      segment-routing srv6
        adjacency
          index 5
          micro-segment behavior unode psp-usd
```

:::en
This configuration instantiates an adjacency segment bound to the End.X behavior with the uSID, PSP, and USD flavors on the interface GigabitEthernet0/0/0/2 of Node 4, with an index value of 5.
:::

这段配置在节点 4 的 `GigabitEthernet0/0/0/2` 上实例化一个绑定 **End.X**、带 **uSID + PSP + USD** flavor 的邻接段，**index 值为 5**。

:::en
The index is a 16-bit value that identifies the adjacency segment within the locator. The SID value is formed by the concatenation of the locator, the index, and the flavor-specific bits.
:::

**index 是 16 bit 值**，用于在该 locator 内**标识这个邻接段**。SID 值由"**locator + index + flavor 相关位**"拼成。

于是 `index 5` + 不可路由 locator `fc00:0:e000::/48` 就得到 `fc00:0:e005::` —— 这就是前文那个 SID 的来源。**index 是运维的抓手**：改 index 就改 SID，规划时按"接口 → index"做一张表，比直接写死 128 bit 地址好维护得多。

:::en
The uSID flavor of the adjacency segment is configured with the micro-segment behavior command, exactly like the prefix segment. It can be combined with the PSP and USD flavors.
:::

邻接段的 uSID flavor 用 `micro-segment behavior` 命令配置，**与前缀段完全一样**，并且可以与 PSP、USD 组合。

:::en
If the End.X segment is configured without the uSID flavor, the SID is a regular 128-bit SID allocated from the locator, as shown in Example 3.7.
:::

如果 End.X 段**不带 uSID flavor**，SID 就是一个从 locator 分配的**普通 128 bit SID**，见例 3.7。

**例 3.7：不带 uSID flavor 的邻接段（显式 128 bit SID）**

```
interface GigabitEthernet0/0/0/2
  address-family ipv6 unicast
    router isis 1
      segment-routing srv6
        adjacency
          sid fc00:0:4:e005::
          behavior end-x psp-usd
```

读法：`sid` 直接给完整地址（这里挂在**可路由** locator `fc00:0:4::/48` 下，只是用不常规的 function 值），`behavior end-x` 声明这是邻接段。**两种写法不能混用**：配了 uSID flavor 就用 `index`，配普通 SID 就用显式 `sid`。

### 3.4.3 通告

:::en
Adjacency segments are advertised in the IGP as SRv6 End.X SID sub-TLVs of the SRv6 Locator TLV, exactly like the prefix segments are advertised as SRv6 End SID sub-TLVs.
:::

邻接段在 IGP 中作为 **SRv6 End.X SID sub-TLV**（同样挂在 Locator TLV 之下）通告——与前缀段用 SRv6 End SID sub-TLV 的方式**完全对称**。

#### 3.4.3.1 SRv6 End.X SID sub-TLV

:::en
The SRv6 End.X SID sub-TLV carries the SID value, the flags, the algorithm, and the identifier of the neighbor or the adjacency associated with the segment.
:::

SRv6 End.X SID sub-TLV 携带 **SID 值、flags、algorithm**，以及**与该段关联的邻居/邻接的标识**。

```
    图 3-21：原书 Figure 3.28 —— IS-IS SRv6 End.X SID sub-TLV

   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |  Type = 11    |    Length     |     Flags     |  Algorithm    |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |                        Weight (1 octet)                       |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |                    SID（16 octets，完整 128 bit）               |
   +                                                               +
   |                                                               |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |                     Neighbor System-ID (6 octets)             |
   +                               +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |                               |Neighbor Media Type (1 octet)  |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   | Sub-sub-TLV Len|        Sub-sub-TLVs（如 SID Structure）        |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

*图 3-21：IS-IS SRv6 End.X SID sub-TLV（按原书 Figure 3.28 与 RFC 9352 §4.2 绘制）*

**表 3.2：SRv6 End.X SID sub-TLV 字段**

| 字段 | 说明 |
|---|---|
| **Type** | IS-IS `11` / OSPFv3 `3` |
| **Length** | sub-TLV value 字节数，含 sub-sub-TLV |
| **Flags** | 目前全部保留（置 0） |
| **Algorithm** | 关联的 IGP 算法，**必须与父 Locator TLV 一致** |
| **Weight** | 该邻接的权重。**同一邻居存在多条并行链路时，用权重做加权 ECMP**；权重可在同一个段上叠加 |
| **SID** | 完整的 128 bit SID |
| **Neighbor System-ID** | 该邻接**对端邻居的 IS-IS System-ID**（6 字节），用于把段与实际邻接**绑定**，防错连 |
| **Neighbor Media Type** | 邻居链路类型（如 1 = P2P、2 = 广播），供接收方校验拓扑一致性 |
| **Sub-sub-TLVs** | 例如 SRv6 SID Structure（见 3.3.3.2） |

:::en
Note that the End.X SID sub-TLV does not carry the local interface identifier: the segment is identified by the pair (parent node, neighbor system ID), which is sufficient to unambiguously identify an adjacency in a point-to-point network.
:::

注意：End.X SID sub-TLV **不携带本端接口标识**。这个段由 **(父节点, 邻居 System-ID)** 这对信息来标识——在点到点网络里，这足以**唯一**确定一条邻接。

#### 3.4.3.2 广播网络上的 LAN End.X SID

:::en
In a broadcast network (e.g., an Ethernet LAN), multiple nodes share the same adjacency, and the neighbor system ID is not sufficient to identify the adjacency. In this case, the SRv6 LAN End.X SID sub-TLV is used, which carries in addition the system ID of the node that advertises the pseudo-node (the DIS in IS-IS).
:::

在**广播网络**（如以太网 LAN）里，多台节点共享同一条邻接，**光靠邻居 System-ID 不足以定位邻接**。此时改用 **SRv6 LAN End.X SID sub-TLV**：它额外携带"**通告伪节点的那个节点的 System-ID**"（IS-IS 里就是 **DIS**）。

:::en
The structure of the SRv6 LAN End.X SID sub-TLV is identical to the SRv6 End.X SID sub-TLV, except that it carries an additional Neighbor System-ID field, which identifies the DIS.
:::

**SRv6 LAN End.X SID sub-TLV 的结构与 SRv6 End.X SID sub-TLV 相同**，只是**多一个 Neighbor System-ID 字段**，用来标识 DIS。

```
    图 3-22：原书 Figure 3.31 / 3.32 —— LAN End.X SID 多出的那一个 System-ID

   End.X SID（P2P）：                  LAN End.X SID（广播网）：
   ┌───────────────┐                   ┌───────────────┐
   │ SID           │                   │ SID           │
   │ Neighbor ID   │ ← 就够定位邻接     │ Neighbor ID   │ ← 对端（可能是 DIS 本身）
   └───────────────┘                   │ DIS System-ID │ ← 多这一个，定位伪节点
                                       └───────────────┘

   为什么需要：共享 LAN 上，R1 到 R2 的"邻接"实际是 R1→伪节点→R2，
              段必须表达"经过该伪节点"，否则无法与别的共享链路区分
```

*图 3-22：P2P 与广播网下 End.X 通告的差别（按原书 Figure 3.31/3.32 重绘）*

#### 3.4.3.3 SRv6 SID Structure

:::en
Like the End SID sub-TLV, the End.X SID and LAN End.X SID sub-TLVs must carry the SRv6 SID Structure sub-sub-TLV, so that the receivers know the boundaries of the locator, function, and argument fields of the advertised SID.
:::

与 End SID sub-TLV 一样，**End.X SID 与 LAN End.X SID 也必须携带 SRv6 SID Structure sub-sub-TLV**，以便接收方知道该 SID 的 locator / function / argument 边界。

对 uA 而言这一点尤其关键：接收方需要知道 **LN 长度 = 16 bit、function 为空、argument 80 bit**，才能正确解析"位移之后落到哪个 uA"。

## 3.5 TI-LFA：用邻接段补齐修复路径

:::en
Topology-Independent Loop-Free Alternate (TI-LFA) is a fast-reroute mechanism that provides sub-50ms protection against link and node failures, without any assumption on the topology. It relies on the combination of the IGP prefix and adjacency segments to construct a repair path that is guaranteed to be loop-free.
:::

**TI-LFA（拓扑无关无环备份）**是一种快速重路由机制，能在**不对拓扑作任何假设**的前提下，对链路与节点故障提供 **sub-50ms** 保护。它依靠**前缀段 + 邻接段的组合**构造一条**保证无环**的修复路径。

:::en
The repair path is computed by the Point of Local Repair (PLR) using the post-convergence shortest path tree: the PLR computes the shortest path to the destination as it will be after the failure, then encodes the nodes and links of that path that are not on the shortest path of the neighbor (the backup next-hop) as a segment list.
:::

修复路径由 **PLR（本地修复点）**用**收敛后的最短路径树**计算：PLR 先算出"故障发生后"到目的地的**新最短路径**，然后把这条路径上**不在备份下一跳邻居的最短路径上**的节点与链路，编码成一个**段列表**。

:::en
In an SRv6 network, TI-LFA is implemented by pushing a segment list onto the packet at the PLR. The segment list is typically made of the prefix segments of the intermediate nodes and the adjacency segments of the links that need to be traversed explicitly.
:::

在 SRv6 网络里，TI-LFA 的实现方式是**在 PLR 上给报文压一个段列表**。段列表通常由**中间节点的前缀段**与**需要显式经过的链路的邻接段**组成。

### 3.5.1 保护前缀段

:::en
Figure 3.33 illustrates the protection of the prefix segment fc00:0:5:: (the Prefix-SID of Node 5) against the failure of the link between Node 1 and Node 3.
:::

图 3.33（下方图 3-23）演示对前缀段 `fc00:0:5::`（节点 5 的 Prefix-SID）的保护，故障场景是**节点 1 与节点 3 之间那条链路**断开。

```
    图 3-23：原书 Figure 3.33 —— 链路保护（PLR = 节点 1，故障 = 1-3 链路）

   拓扑（默认度量 10，4-5 链路度量 100）：

        ┌────┐  10   ┌────┐
        │ 1  │───────│ 2  │
        └─┬──┘       └──┬─┘
       10 │  ✗故障      │10
          │             │
        ┌─┴──┐  10   ┌──┴─┐
        │ 3  │───────│ 4  │
        └─┬──┘       └──┬─┘
       10 │             │100
          └────► ┌────┐ ◄┘
                 │ 5  │  目的：fc00:0:5::
                 └────┘

   收敛前：1 → 3 → 5 （metric 20）
   收敛后：1 → 2 → 4 → 3 → 5 （metric 40）
   修复路径 = 1 → 2 → 4 → 3 → 5，用段列表把"必须经过的节点"钉死：
        < fc00:0:2:: , fc00:0:3:: , fc00:0:5:: >
          经 2（隐式）  经 3（隐式）   到 5
   注意：2、4 只需前缀段就能沿最短路径串起来，无需邻接段
```

*图 3-23：TI-LFA 链路保护——纯前缀段即可表达修复路径（按原书 Figure 3.33 重绘）*

:::en
In this example, the repair path from Node 1 to Node 5 after the failure of the link Node 1-Node 3 is Node 1-Node 2-Node 4-Node 3-Node 5. The repair segment list is <fc00:0:2::, fc00:0:3::, fc00:0:5::>: the packet is first sent to Node 2, which forwards it along its shortest path to Node 3, which in turn forwards it along its shortest path to Node 5.
:::

本例中，1-3 链路故障后节点 1 到节点 5 的修复路径是 **1 → 2 → 4 → 3 → 5**。修复段列表为 `<fc00:0:2::, fc00:0:3::, fc00:0:5::>`：报文先送到节点 2，节点 2 沿**它自己的最短路径**转发到节点 3，节点 3 再沿**它自己的最短路径**转发到节点 5。

:::en
Note that only the prefix segments are needed in this case: the shortest path from Node 2 to Node 3 and the shortest path from Node 3 to Node 5 do not traverse the failed link, so the repair path is correctly followed without any adjacency segment.
:::

注意：本例**只用前缀段就够了**。因为"节点 2 到节点 3"与"节点 3 到节点 5"的最短路径都**不经过故障链路**，所以不加任何邻接段也能正确走修复路径。

这正是 TI-LFA 段列表"最小化"的原则：**能靠前缀段走的就不写邻接段**，段列表越短越好（尤其对 uSID 压缩与硬件解析深度友好）。

### 3.5.2 保护邻接段

:::en
Figure 3.34 illustrates the protection of the adjacency segment fc00:0:e005:: instantiated on Node 4 for the adjacency to Node 5, against the failure of the link Node 4-Node 5.
:::

图 3.34（下方图 3-24）演示对邻接段 `fc00:0:e005::`（实例化在节点 4 上，指向节点 5）的保护，故障场景是**节点 4 与节点 5 之间那条链路**断开。

```
    图 3-24：原书 Figure 3.34 —— 节点保护（PLR = 节点 1，故障 = 节点 3）

   收敛后路径：1 → 2 → 4 → 5（metric 120，4-5 是高代价链路）
   但 4 → 5 需要走"平时不用的"链路，最短路径上根本不会选它
   → 必须用邻接段强制：

   段列表：< fc00:0:4:: , fc00:0:e005:: , fc00:0:5:: >
             到节点 4     从 4 的 Eth2 出去   落到节点 5

           ┌─ 不可路由段，必须紧跟其父节点 4 的 SID（见 3.2.3 节）
           │
   若目的就是邻接段本身（如"经 4 到 5 的链路"是关键业务路径）：
   段列表退化成一个邻接段，前一个前缀段常常就是本节点自己的 locator

   PLR 只有在"备份下一跳的最短路径不覆盖该链路"时才用邻接段
```

*图 3-24：TI-LFA 用邻接段强制经过非最短路径链路（按原书 Figure 3.34 重绘）*

:::en
In this case, the repair path requires the adjacency segment fc00:0:e005::, because the shortest path from Node 4 to Node 5 does not use the link Node 4-Node 5 (its metric is too high). The repair segment list is therefore <fc00:0:4::, fc00:0:e005::, fc00:0:5::>.
:::

这时修复路径**必须**用邻接段 `fc00:0:e005::`，因为"节点 4 到节点 5 的最短路径"**不会**走 4-5 这条链路（它的度量太高）。因此修复段列表是 `<fc00:0:4::, fc00:0:e005::, fc00:0:5::>`。

:::en
The same repair path can also be used to protect the adjacency segment itself, in which case the segment list is just <fc00:0:e005::> and the PLR is the parent node of the adjacency segment (Node 4), which forwards the packet out of the backup interface.
:::

同一条修复路径也可以用来**保护邻接段本身**：此时段列表只有一个 `<fc00:0:e005::>`，PLR 就是该邻接段的父节点（节点 4），它把报文从**备份接口**发出。

:::en
TI-LFA is further detailed in Chapter 8, where the SRv6 implementation of the repair paths, the interaction with the IGP, and the uSID compression of the repair segment lists are described.
:::

TI-LFA 的完整细节在第 8 章：包括修复路径的 SRv6 实现、与 IGP 的交互，以及**修复段列表的 uSID 压缩**（压缩后一条修复路径常常能塞进一个 128 bit 容器，连 SRH 都不需要）。

## 3.6 小结

:::en
This chapter described the underlay instructions of SRv6: the IGP prefix segments and the IGP adjacency segments, and their endpoint behaviors End and End.X with their flavors.
:::

本章讲清了 SRv6 的 underlay 指令：**IGP 前缀段**与 **IGP 邻接段**，以及它们的端点行为 **End / End.X** 与各自的 flavor。

把本章的结论压缩成一张表：

| 维度 | Prefix Segment（End） | Adjacency Segment（End.X） |
|---|---|---|
| 语义 | 沿最短路径去某个 IGP 前缀 | 强制走某条邻接，忽略度量 |
| SID 作用域 | IGP 域内**全局唯一** | **本地有效**（同值不同义） |
| 可路由性 | 通常**可路由**（locator 在 IGP 通告） | 通常**不可路由**（必须紧跟父节点 SID） |
| uSID 名称 | **uN**（16 bit） | **uA**（16 bit） |
| FIB 位置 | GIB（全局表） | LIB（本地表） |
| 支持的 flavor | uSID / PSP / USD | uSID / PSP / USD / **NEXT-ONLY-CSID** |
| 主要用途 | 端到端路径、TI-LFA 骨架 | 显式指定链路、TI-LFA 补链、跨域拼接 |

:::en
The locator is the key concept that makes SRv6 scale: it summarizes all the segments of a node into a single IPv6 prefix, so that the transit nodes only need to know one route per node, regardless of the number of segments.
:::

**locator 是 SRv6 可扩展的关键**：它把一台节点的所有段汇总成**一条 IPv6 前缀**，于是中转节点对每台节点只需知道**一条路由**，与段的数量无关。

:::en
The uSID flavor provides a significant reduction of the packet header size, by encoding up to six micro-instructions in a single 128-bit SID, and often eliminating the need for the SRH.
:::

**uSID flavor 显著压缩报文头**：一个 128 bit SID 里最多放 6 条微指令，常常**连 SRH 都不需要**。

:::en
The PSP and USD flavors optimize the packet processing at the last hop and at the destination node, respectively.
:::

**PSP 优化最后一跳**（摘 SRH），**USD 优化目的节点**（摘整层外层头）。

:::en
In the next chapter, we will describe how the IGP segments are used to build SR policies with flexible algorithms.
:::

下一章讲如何用这些 IGP 段、结合**灵活算法**去构建 SR 策略。

## 实战案例

### 案例 A：单区域 5 节点最小可用域——先跑通 uN

**目标**：在一个 IS-IS level-2 单区域里，让 R1 能 ping 通 R5 的 loopback，并且**报文路径由 uSID 决定**，中途不产生 SRH。

```text
规划表（这张表是整个域的地基，先定死再上配置）
┌──────┬───────────────┬──────────────────┬──────────────┐
│ 节点 │ loopback      │ locator (MAIN)   │ uN SID       │
├──────┼───────────────┼──────────────────┼──────────────┤
│ R1   │ 2001:db8::1/128│ fc00:0:1::/48   │ fc00:0:1::   │
│ R2   │ 2001:db8::2/128│ fc00:0:2::/48   │ fc00:0:2::   │
│ R3   │ 2001:db8::3/128│ fc00:0:3::/48   │ fc00:0:3::   │
│ R4   │ 2001:db8::4/128│ fc00:0:4::/48   │ fc00:0:4::   │
│ R5   │ 2001:db8::5/128│ fc00:0:5::/48   │ fc00:0:5::   │
└──────┴───────────────┴──────────────────┴──────────────┘
SID block = fc00:0::/32（ULA，RFC 4193）  LN 长度 = 16 bit  function 为空
```

R1 上的配置（其余节点同理，只改编号）：

```text
segment-routing srv6
  locators
    locator MAIN
      prefix fc00:0:1::/48
      micro-segment behavior unode psp-usd
!
router isis 1
  net 49.0001.0000.0000.0001.00
  is-type level-2-only
  address-family ipv6 unicast
    metric-style wide
    segment-routing srv6
      locator MAIN
```

**验证 1：locator 是否被正确实例化**

```text
RP/0/RP0/CPU0:R1# show segment-routing srv6 locator
Name   ID  Algo  Prefix          Status  Flags
-----  --- ----  --------------  ------  -----
MAIN   1   0     fc00:0:1::/48   Up      U        ← U = uSID locator
```

**验证 2：是否学到了别人的 locator（这是 90% 的故障点）**

```text
RP/0/RP0/CPU0:R1# show isis database verbose | include fc00:0
  Prefix             : fc00:0:4::/48       ← locator 以普通 IPv6 前缀出现
  SRv6 Locator       : fc00:0:4::/48  Algo: 0
    End SID          : fc00:0:4::      ← End SID sub-TLV
```

**验证 3：带 uSID 的转发实测（R1 → R5 走 1-3-5）**

```text
RP/0/RP0/CPU0:R1# ping 2001:db8::5 source 2001:db8::1
!!!!!   ← 正常收敛

# 打入一个"显式经过 R3"的 uSID 容器，观察不产生 SRH：
RP/0/RP0/CPU0:R1# traceroute 2001:db8::5 source fc00:0:3:: numeric
 1  fc00:0:3:: ...
```

排障口诀：**ping 得通但 traceroute 看不到中间跳**，通常是中间节点在 GIB 里命中了 uN、执行位移后**继续按 DA 转发**，不带 TTL 递减的期望行为——这不是故障，是 uSID 的常态。

### 案例 B：TI-LFA 修复列表的 uSID 压缩——为什么 6 条以内免 SRH

**场景**：沿用图 3-23 的拓扑，1-3 链路故障，R1 需要 <fc00:0:2::, fc00:0:3::, fc00:0:5::>。

**压缩前（普通 128 bit SID 列表）**：

```text
SRH 开销 = 8（固定）+ 8（TLV）+ 16×3（3 个 SID）= 64 字节
报文头 = 40（外层 IPv6）+ 64 = 104 字节 + 用户载荷
```

**压缩后（一个 uSID 容器）**：

```text
容器 = fc00:0: | 0002 | 0003 | 0005 | 0 | 0 | 0 | 0
         /32      uN(2)  uN(3)  uN(5)   ← 3 条指令，剩余 3 格补 0
报文头 = 40（仅外层 IPv6，无 SRH）
省下 64 字节 → 对小包（语音、游戏、DNS）是 40% 以上的开销差别
```

**关键校验**：压缩后 **R1 必须仍然知道"位移一次 = 16 bit"**。如果对端把 LN 配成 24 bit 而没同步，R1 会位移 24 bit，DA 直接错位，报文被丢或打到错误节点——这就是 3.3.3.2 节强调 SID Structure 必须一致的实际后果。

**验证命令**：

```text
RP/0/RP0/CPU0:R1# show isis segment-routing srv6 sid-structure
SID                    LB  LN  Fun  Arg
--------------------  ---  --  ---  ---
fc00:0:1::            32   16   0   80     ← 全网必须一致
fc00:0:e005:: (local) 32   16   0   80
```

### 案例 C：PSP 该不该开——一次真实取舍

| 判据 | 开 PSP | 不开 PSP |
|---|---|---|
| 末跳带宽敏感（大量小包） | ✅ 省 8 + 8×N 字节 | ❌ |
| 出口节点需要 SRH 做路径回溯/染色 | ❌ SRH 已被摘 | ✅ |
| 出口节点要对 SL 做末跳计量 | ❌ SL 已被置 0 | ✅ |
| 出口节点是第三方设备、不支持 SRH | ✅ 收到普通 IPv6 报文 | ❌ 可能丢弃 |
| 与 USD 组合做隧道出口 | ✅ 推荐 | 视情况 |

经验：**域内纯转发场景开 PSP+USD**；**出口是业务 PE、要用 SID 做标识或 telemetry 的场景不开 PSP**。两者可以在同一域内按 locator 分别配置（不同 locator 不同 flavor），不必全网一致。

## 延伸阅读

- **RFC 8986**：SRv6 Network Programming——End / End.X / PSP / USD 的规范定义，本章 3.3、3.4 的权威出处。
- **RFC 9352 / RFC 9513**：IS-IS / OSPFv3 的 SRv6 扩展——Locator TLV、End SID、End.X SID、LAN End.X SID、SID Structure 的字节级格式。
- **RFC 9800（原 draft-ietf-spring-srv6-srh-compression）**：uSID / NEXT-C-SID / NEXT-ONLY-CSID 的压缩规范，本章 3.3.1.1、3.4.1.1 的出处。
- **RFC 9350（IGP Flexible Algorithm）**：第 4 章的前置；locator 的 Algorithm 字段在此定义。
- 交叉参考：第 5 章（泄露与重分发，Prefix Attribute Flags 的用处）、第 8 章（TI-LFA 完整实现）、第 10 章（SID block 与 locator 规划）。
