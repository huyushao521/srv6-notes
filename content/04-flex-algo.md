# 04 · 灵活算法 Flex-Algo：一张网里的多条"最短路"

> **本章定位**：原书第 4 章《Flexible Algorithms》。本版按原书 4.1–4.9 的段落顺序**逐段对照**：灰色英文块是原文摘录（保留原句与术语），紧随其后的中文是该段的完整翻译，必要时补一句工程注解。书中的 Figure 4.1–4.9 按原文描述用 ASCII 重绘（同类图合并或拆解），图注标明来源。配置与命令输出来自原书 Example 4.1–4.20，按 IOS XR 风格保留。

**本章要拿到的东西**（原书章首列表）：

| 问题 | 对应小节 |
|---|---|
| SRv6 locator 如何与 IGP 算法绑定，从而提供**不同的转发路径** | 4.2 |
| Flex-Algo 是什么，运营商怎样定义自己的路由行为 | 4.3 |
| 如何按"最小链路时延""排除某些链路"等目标优化路径 | 4.3、4.6 |
| Flex-Algo 的配置步骤，以及**定义一致性**如何保证 | 4.2.3、4.3.1、4.4 |
| TI-LFA 如何在**本算法内**提供修复路径（含 Flex-Algo 邻接段） | 4.7 |

先记住一句话：第 3 章解决了"一台节点有多少个地址"，第 4 章解决"同一台节点为什么要有多套地址"。Flex-Algo 不是新协议，而是**给 locator 贴一个算法编号，让 IGP 为这个编号单独算一棵 SPF 树**。

## 4.0 本章用到的拓扑与算例

原书的图没有标全链路度量，但文字给出的三条路径代价是明确的（Algo(0) 的 1→6→5→3 = 30、Flex-Algo(128) 的 1→2→3 = 10 ms、Flex-Algo(129) 的 1→6→5→4→3 = 40）。为让这三条结论同时成立，本章固定一张拓扑，后面所有图与算例都基于它：

{{FIG|04/fig-4-1-topology|表 4-1 · 矢量版|全章共用的 6 节点拓扑：每条链路标注 IGP 度量与时延，5-3 为 RED 亲和链路。}}

```asciifig
表 4-1：本章拓扑（6 节点，IS-IS level-2 单区域）

   链路         IGP 度量    链路时延     亲和/备注
   ──────────────────────────────────────────────────────
   1 – 6          10         1 ms
   6 – 5          10         2 ms
   5 – 3          10        12 ms        RED 亲和（易丢包链路）
   5 – 4          10        10 ms
   4 – 3          10        10 ms
   4 – 2          20         8 ms
   1 – 2          40         6 ms        代价高但时延低
   2 – 3          10         4 ms
   ──────────────────────────────────────────────────────
   三条关键路径：
   Algo(0)          1 → 6 → 5 → 3        累计代价 30
   Flex-Algo(128)   1 → 2 → 3            累计时延 10 ms
   Flex-Algo(129)   1 → 6 → 5 → 4 → 3    累计代价 40（避开 RED 链路）
```

读法：**1-2 链路 IGP 度量大（40）但时延小（6 ms）**，这就是"最低代价"与"最低时延"分道扬镳的原因。真实网络里这种"贵但快"的链路很常见：新铺的直连光纤、跨城直达波长——度量上不划算，时延上无可替代。

## 4.1 引言：算法是 locator 的属性，不是段的属性

:::en
Chapter 7 of Segment Routing: Part II provides a comprehensive description of flexible algorithms for SR-MPLS. For the most part, this description equally applies to SRv6.
:::

《Segment Routing: Part II》第 7 章已完整讲过 SR-MPLS 的灵活算法，其中绝大部分内容**原样适用于 SRv6**。本章只讲 SRv6 的不同之处。

:::en
Each SRv6 locator prefix is associated with an IGP algorithm that indicates how the shortest path to that prefix should be computed: which nodes should be considered in the topology, which metric should be minimized, and which other constraints should be factored in. This algorithm can be one of the IETF-defined IGP algorithms, with an identifier ranging from 0 to 127, or a flexible algorithm between 128 and 255.
:::

每个 SRv6 **locator 前缀都关联一个 IGP 算法**，该算法说明"到这条前缀的最短路径该怎么算"：

1. **拓扑里应该考虑哪些节点**；
2. **最小化哪个度量**；
3. **还要满足哪些约束**。

算法可以是 IETF 定义的 IGP 算法（编号 0–127），也可以是 **128–255 之间的灵活算法**。

| 算法号段 | 归属 | SRv6 现状 |
|---|---|---|
| **0** | SPF（最小化 IGP 度量） | 全网默认，必配 |
| **1** | Strict-SPF | **SRv6 尚不支持**（只对 SR-MPLS 有意义） |
| 2–127 | IANA 保留 / 其他标准算法 | 无用于 SRv6 的定义 |
| **128–255** | **Flex-Algo**，域内自定义 | 本章主角 |

:::en
Flexible algorithms, or Flex-Algos for short, are defined within the scope of an IGP domain and fully customizable by the operator. Each operator can define one or more Flex-Algos tailored to their specific needs.
:::

灵活算法（Flex-Algo）在 **IGP 域范围内**定义、由运营商**完全自定义**；一个运营商可以按需定义一到多个。

:::en
With SR-MPLS, flexible algorithms only apply to prefix segments. SRv6 extends the scope of flexible algorithms to every routable segment, thanks to the locator concept, as well as adjacency segments, routable or non-routable.
:::

这是 SRv6 相对 SR-MPLS 的第一个实质增强：SR-MPLS 里 Flex-Algo 只作用于 **prefix segment**（标签没有 locator 结构）；SRv6 借助 locator 概念，把灵活算法扩展到**所有可路由段**（邻接段、Binding SID、业务段都行），**连不可路由的邻接段也能带算法属性**。

| 维度 | SR-MPLS | SRv6 |
|---|---|---|
| Flex-Algo 作用对象 | 仅 prefix segment | **任意可路由段**（由 locator 决定） |
| 邻接段 | 无算法概念 | **有**（End.X 带 Alg 字段，见 4.5） |
| 表达"另一种路径" | 每算法一套标签块 | 每算法一个 **locator**（同一前缀块内换 nibble） |
| 备份路径 | 分算法计算 | 分算法计算，且**邻接段也有本算法的保护段** |

:::en
In this chapter, we start by describing how IGP algorithms are associated with segment locators. We then remind how flexible algorithms are defined and kept consistent within an IGP domain. We conclude by showing how the IGP algorithm is preserved along TI-LFA backup paths for all segment types.
:::

本章路线：**locator 怎么带算法**（4.2）→ **Flex-Algo 的定义与一致性**（4.3、4.3.1）→ **参与关系**（4.4）→ **段实例化**（4.5）→ **路径计算**（4.6）→ **所有段类型上都保住算法的 TI-LFA**（4.7）。

:::en
From an IETF perspective, IGP flexible algorithms are defined in RFC 9350. In the remainder of this chapter, Algo(X) refers to the standard algorithm X and Flex-Algo(Y) refers to the flexible algorithm Y.
:::

IETF 侧的标准是 **RFC 9350（IGP Flexible Algorithm）**。本章记号统一为：**Algo(X)** 指标准算法 X，**Flex-Algo(Y)** 指灵活算法 Y。

## 4.2 Locator 算法：段继承 locator 的算法

:::en
In SRv6, the traffic steered onto a routable segment is first forwarded to the segment parent node along the shortest path to the segment locator. This part of the forwarding path is common for all the segments defined under the same locator.
:::

在 SRv6 中，被引导到某个可路由段的流量，**先沿"到该段 locator 的最短路径"被送到父节点**。这段路对**同一个 locator 下的所有段是共用的**——这就是"算法绑 locator 而不是绑段"的物理原因。

:::en
Each remote router computes it as the shortest path to the node or set of nodes that advertise the segment locator, according to an IGP algorithm. The IGP algorithm is thus associated with the segment locator rather than the individual segments.
:::

每台远端路由器**按某个 IGP 算法**计算"到通告该 locator 的节点（或节点组）的最短路径"。所以**算法关联的是 locator，不是单个段**。

:::en
Each routable segment inherits the IGP algorithm of its locator. This applies to prefix segments as well as all other routable segments (e.g., adjacency, binding, or service segments).
:::

**每个可路由段都继承其 locator 的 IGP 算法**：前缀段如此，其他可路由段也一样——邻接段、Binding SID、业务段，只要挂在某个 locator 下，就自动带上那个 locator 的算法。

> 一句话记忆：**locator 是"路由域"，算法是这个域的属性；段是域里的住户，跟着域走。**

### 4.2.1 用例：低时延算法 + 第二套 locator

:::en
A typical use-case is for an operator to define a Flex-Algo, e.g., Flex-Algo(128), that minimizes the accumulated link delay to provide low-delay services across their network. This is illustrated in Figure 4.1.
:::

典型用例：定义 **Flex-Algo(128)，最小化累计链路时延**，为全网低时延业务提供路径（原书 Figure 4.1）。

{{FIG|04/fig-4-2-two-paths|图 4-1 · 矢量版|同一拓扑上 Algo(0) 走低代价路径、Flex-Algo(128) 走低时延路径，靠两个 locator 区分。}}

```asciifig
    图 4-1：原书 Figure 4.1 —— 节点 1 到节点 3 的两条路径（Algo(0) 与 Flex-Algo(128)）

   ① Algo(0)：最小化 IGP 度量的路径
        1 ──10── 6 ──10── 5 ──10── 3        累计代价 30
                             ▲
                             └ 这段时延 12 ms，整条路 = 1 + 2 + 12 = 15 ms

   ② Flex-Algo(128)：最小化链路时延的路径
        1 ──6ms── 2 ──4ms── 3               累计时延 10 ms

   两条路径同时存在，靠 locator 区分：
        fc00:0:3::/48          （Algo 0）        → 走 ①
        fc00:1:3::/48          （Flex-Algo 128） → 走 ②
   同一台节点 3，两个地址，两种"最优"。目的 SID 一变，路径就变，
   全程只有一个 SID、不需要段列表、不需要控制器。
```

*图 4-1：同一拓扑上 Algo(0) 与 Flex-Algo(128) 的最短路径（按原书 Figure 4.1 重绘，链路度量见表 4-1）*

:::en
First, the operator enables dynamic link-delay measurements to continuously measure the propagation delay on each link in the network and flood that information as a routing metric in the IGP. This allows the low-delay paths to automatically adapt to any link delay change, typically caused by a rerouting in the underlying optical network.
:::

第一步，开启**动态链路时延测量**：持续测量每条链路的传播时延，并把结果作为**路由度量**在 IGP 中泛洪。这样低时延路径能**自动跟随时延变化**——最常见的起因是底层光网络发生了重路由（光层换了一条更长或更短的路由，IP 层看到的时延会跳一下）。

:::en
Alternatively, if the propagation delays are assumed to be constant or measured by an external tool, they can also be configured statically on each link. Chapter 15 of Segment Routing: Part II offers a comprehensive description of the link delay monitoring functionality in Cisco IOS XR, including the probing strategy, IGP advertisement, telemetry reporting, and static configuration.
:::

也可以**静态配置**：若时延被假定为常数，或由外部工具（探针、NMS）测好后导入，就在每条链路上静态写死。IOS XR 的链路时延监控（探测策略、IGP 通告、telemetry 上报、静态配置）详见《Part II》第 15 章。

| 时延来源 | 优点 | 风险 |
|---|---|---|
| 动态测量（RFC 7471 扩展） | 自动跟随光层变化，真实 | 测量本身有开销；抖动会引发路径抖动 |
| 静态配置 | 稳定、无测量开销 | 光层重路由后**值是错的**，且没人知道 |
| 外部工具导入 | 可与性能平台对齐 | 依赖外部系统连通性与时效 |

:::en
Then, the operator defines Flex-Algo(128) with link delay as the optimization metric. This means that the shortest paths for this Flex-Algo must minimize the accumulated link delay instead of the link IGP metric.
:::

第二步，定义 **Flex-Algo(128)，把"链路时延"作为优化度量**。这意味着该算法的所有最短路径**最小化累计时延**，而不是累计 IGP 度量。

:::en
Finally, the operator configures an additional SRv6 locator associated with Flex-Algo(128) on each node in the IGP domain. This effectively provides two different ways to reach the node: the Algo(0) default low-cost path, computed based on link IGP metrics, and the Flex-Algo(128) low-delay path.
:::

第三步，在域内**每台节点上再配一个绑定 Flex-Algo(128) 的 locator**。于是到达该节点有了两种方式：Algo(0) 的**低代价路径**（按链路 IGP 度量算）与 Flex-Algo(128) 的**低时延路径**。

三件事的关系一句话说清：**测量供数据，定义定规则，locator 划地址**。少任何一件，第二个路径就不存在。

:::en
In the illustrations of this book, we dedicate the last nibble of the 32-bit SRv6 SID block to encode the IGP algorithm as follows. All Algo(0) locators are drawn from the block fc00:0000::/32. All Flex-Algo(K) locators are drawn from the block fc00:000(K-127)::/32.
:::

原书插图用了一个便于阅读的约定：**把 32 bit SID block 的最后一个 nibble 用来编码 IGP 算法**。

| 算法 | 地址块 | 例（节点 3） | 缩写 |
|---|---|---|---|
| Algo(0) | `fc00:0000::/32` | `fc00:0000:0003::/48` | `fc00:0:3::/48` |
| Flex-Algo(K) | `fc00:000(K-127)::/32` | K=128 → `fc00:0001:0003::/48` | `fc00:1:3::/48` |
| | | K=129 → `fc00:0002:0003::/48` | `fc00:2:3::/48` |
| | | K=130 → `fc00:0003:0003::/48` | `fc00:3:3::/48` |

{{FIG|04/fig-4-3-locator-encoding|locator 与算法 · 矢量版|算法编进 SID Block 最后一个 nibble：Algo(0) 用 fc00:0000::/32，Flex-Algo(K) 用 fc00:000(K-127)::/32。}}

注意这只是**书中插图的编号习惯**，不是协议要求：算法号在 IS-IS Locator TLV 的 `Algorithm` 字段里（图 3-4），地址怎么切完全由运营商的地址规划决定（第 10 章）。

:::en
Following this convention, Node 3 in our example advertises the locators: fc00:0000:0003::/48 (or fc00:0:3::/48 for short) associated with Algo(0) that is routed along the low-cost path. fc00:0001:0003::/48 (or fc00:1:3::/48 for short) associated with Flex-Algo(128) that is routed along the low-delay path.
:::

按此约定，节点 3 通告两个 locator：`fc00:0:3::/48`（Algo(0)，沿低代价路径路由）与 `fc00:1:3::/48`（Flex-Algo(128)，沿低时延路径路由）。

:::en
As a result, when Node 1 sends a packet to the Prefix-SID fc00:1:3:: (under the locator fc00:1:3::/48), the packet follows the low-delay shortest path 1 → 2 → 3, represented in Figure 4.1, with an accumulated delay of 10ms. Similarly, when Node 1 sends a packet to the Prefix-SID fc00:0:3:: (under the locator fc00:0:3::/48), this packet follows the low-cost path 1 → 6 → 5 → 3 with an accumulated IGP cost of 30.
:::

结果就是：节点 1 发给 Prefix-SID `fc00:1:3::` 的报文沿**低时延路径 1 → 2 → 3** 走，累计时延 10 ms；发给 `fc00:0:3::` 的报文沿**低代价路径 1 → 6 → 5 → 3** 走，累计 IGP 代价 30。**同一个目的节点，两个 SID，两条路径，一个 IGP。**

### 4.2.2 原书侧栏：段列表也能强制任意路径吗

:::en
A low-delay path can also be built with an SR-TE segment list of Algo(0) segments. For example, the SID-list <fc00:0:1:e002::, fc00:0:3::>, where fc00:0:1:e002:: is the Algo(0) Adjacency-SIDs of Node 1 towards Node 2, enforces a low-delay path from Node 1 to Node 3.
:::

低时延路径**也能**用 Algo(0) 段拼出来。例如段列表 `<fc00:0:1:e002::, fc00:0:3::>`（`fc00:0:1:e002::` 是节点 1 指向节点 2 的 Algo(0) 邻接段）同样强制出"1 → 2 → 3"。

:::en
However, the Flex-Algo functionality enforces the low-delay path with a single SID, fc00:1:3::. This Flex-Algo SID continuously follows the low-delay path to Node 3, hence there is no need to recompute a SID-list when the topology changes, and ensures a low-delay backup path when TI-LFA is enabled.
:::

但 Flex-Algo 用一个 SID 就做到了：`fc00:1:3::`。这个 SID **持续跟随**到节点 3 的低时延路径，于是带来三个差别：

| 维度 | 段列表（SR-TE，Algo 0） | Flex-Algo SID |
|---|---|---|
| 表达长度 | 2 个 SID 起，拓扑一变就得重算 | **1 个 SID** |
| 拓扑变化 | 控制器/头端要重算并重下 | IGP 收敛**自动**跟随 |
| 备份 | 备份段列表也要重算 | TI-LFA 在**本算法内**算修复路径 |
| 报文头 | 多 SID → 容易超 128 bit → 需要 SRH | 通常一个 uSID 容器就够（免 SRH） |
| 适用规模 | 少量特例（几十条策略） | 一整类流量（百万级会话） |

工程结论：**成规模的"这类流量都走低时延"用 Flex-Algo；个别流量的精确指定用 SR Policy**。两者不冲突——第 6 章的 BGP Color 正是把业务映射到 Flex-Algo SID 的常用手法。

### 4.2.3 配置与验证：四步才能出邻接段

:::en
Let us start by configuring a new SRv6 locator and prefix segment associated with Flex-Algo(128) on all four routers. In Cisco IOS XR, the IGP algorithm is specified with the algorithm keyword within the SRv6 locator configuration. The locator is associated with the standard SPF algorithm (Algo(0)) when this keyword is omitted.
:::

先在**四台路由器**上都配一个绑定 Flex-Algo(128) 的新 locator 与前缀段。IOS XR 里算法用 locator 配置中的 `algorithm` 关键字指定；**省略即 Algo(0)**。

:::en
At the time of this writing, the Strict-SPF algorithm (Algo(1)) is not supported for SRv6 in Cisco IOS XR. Aside from the algorithm value, the configuration of Flex-Algo locators is the same as the Algo(0) ones, as shown in Example 4.1.
:::

撰写本书时 IOS XR 的 SRv6 **不支持 Strict-SPF（Algo 1）**。除算法值外，Flex-Algo locator 的配置与 Algo(0) locator 完全一样。

**例 4.1：节点 3 上把 locator `fc00:1:3::/48`（命名 `DELAY`）关联到 IGP 算法 128**

```text
segment-routing
 srv6
  locators
   locator MAIN
    micro-segment behavior unode psp-usd
    prefix fc00:0:3::/48
   !
   locator DELAY
    micro-segment behavior unode psp-usd
    prefix fc00:1:3::/48
    algorithm 128
```

两套 locator、同样的 flavor、**只差一行 `algorithm`**。这是本章最重要的一条配置心法：Flex-Algo 不引入新配置体系，它只是 locator 的一个属性。

:::en
We can verify that the new locator is correctly created by running the show command in Example 4.2.
:::

用例 4.2 的命令确认新 locator 已创建。

**例 4.2：配好 `fc00:1:3::/48` 后节点 3 上的 SRv6 locator 列表**

```text
RP/0/RP0/CPU0:R3# show segment-routing srv6 locator
Name                  ID       Algo  Prefix                    Status   Flags
--------------------  -------  ----  ------------------------  -------  --------
MAIN                  1        0     fc00:0:3::/48             Up       U
DELAY                 2        128   fc00:1:3::/48             Up       U
```

读法：`Algo` 列是 128，说明这行 locator **已经绑定了 Flex-Algo(128)**；`Flags: U` 表示它是 uSID locator。但绑定不等于参与，也不等于邻接段已生成。

:::en
As we have seen in Chapter 3, configuring a locator in Cisco IOS XR triggers the instantiation of the corresponding prefix segment. We can verify this for the new DELAY locator with the show command in Example 4.3.
:::

如第 3 章所述，IOS XR 里配 locator 会**自动实例化对应的 prefix segment**。用例 4.3 验证 `DELAY` 的 prefix segment。

**例 4.3：配好 locator 后节点 3 上的 SRv6 段列表**

```text
RP/0/RP0/CPU0:R3# show segment-routing srv6 sid all
*** Locator: 'MAIN' ***
SID                Behavior      Context                      Owner      State  RW
-----------------  ------------  ---------------------------  ---------  -----  --
fc00:0:3::         uN (PSP/USD)  'default':3                  sidmgr     InUse  Y
fc00:0:3:e000::    uA (PSP/USD)  [Gi0/0/0/2, Link-Local]:0    isis-1     InUse  Y
fc00:0:3:e001::    uA (PSP/USD)  [Gi0/0/0/3, Link-Local]:0    isis-1     InUse  Y
*** Locator: 'DELAY' ***
fc00:1:3::         uN (PSP/USD)  'default':3                  sidmgr     InUse  Y
```

:::en
At this stage, there is no adjacency segment instantiated under the DELAY locator. This is expected since the adjacency segments are instantiated by the IGP (e.g., IS-IS), and no IGP process on the node currently knows about this new locator.
:::

此时 `DELAY` 下**没有邻接段**，这是正常的：邻接段由 **IGP 进程**实例化，而节点上还没有任何 IGP 进程知道这个新 locator。

**分工要记清**：`uN`（End）来自 **sidmgr**，`uA`（End.X）来自 **IGP**。Owner 列已经写明了 —— 这就是排障时"为什么只有 `fc00:1:3::` 没有 `fc00:1:3:e000::`"的答案。

:::en
Let us then assign the 'DELAY' locator to the IS-IS process 1, as shown in Example 4.4.
:::

于是把 `DELAY` 挂到 IS-IS 进程 1（例 4.4）。

**例 4.4：把 `DELAY` locator 关联到 IS-IS 进程 1**

```text
router isis 1
 address-family ipv6 unicast
  segment-routing srv6
   locator MAIN
   !
   locator DELAY
```

:::en
You might notice when running the show command in Example 4.3 again that the adjacency segments are still missing under the DELAY locator. Assigning the locator to the IGP process is all that is needed to trigger the instantiation of Algo(0) adjacency segments but, in the case of Flex-Algo, one more step is needed. The node also needs to participate in this Flex-Algo.
:::

再跑一次例 4.3 会发现**邻接段仍然缺失**。对 Algo(0)，把 locator 挂给 IGP 进程就够了；但**对 Flex-Algo 还差一步：节点必须"参与"这个算法**（4.4 节）。

四步检查清单（少一步就少一段）：

| 步骤 | 配置位置 | 少了它的症状 |
|---|---|---|
| 1. 建 locator + `algorithm` | `segment-routing srv6 / locators` | 没有 prefix segment（uN） |
| 2. 挂给 IGP 实例 | `router isis N / ... / locator X` | locator 不泛洪，别人看不见 |
| 3. **参与算法** | `router isis N / flex-algo 128` | **有 uN，没有 uA**，算法路径上不走你 |
| 4. 算法定义一致 | `flex-algo 128 / metric-type …` + `advertise-definition` | 参与被撤回，全网回落到 Algo(0) |

## 4.3 Flex-Algo 的定义（FAD）

:::en
Network operators may define flexible algorithms according to their needs in each IGP domain and assign to them any identifier in the range 128-255.
:::

运营商可以在**每个 IGP 域内**按需定义灵活算法，编号取 **128–255** 中任意值。

:::en
The definition of a flexible algorithm consists of three elements: a calculation type; an optimization metric; and a set of constraints.
:::

一个灵活算法的**定义（FAD）由三要素构成**：

| 要素 | 回答的问题 | 取值范围 | 默认 |
|---|---|---|---|
| **计算类型**（calculation type） | 用哪种算法算路径 | 目前只有 SPF | SPF（不用配） |
| **优化度量**（optimization metric） | 最小化哪个度量 | IGP metric / delay / TE metric | IGP metric |
| **约束**（constraints） | 哪些链路不许用 / 必须用 | SRLG、亲和属性四类规则 | 无 |

:::en
The calculation type indicates the method to compute the paths and is selected among the calculation types used by standard IGP algorithms. The standard IGP algorithms are those listed in the IANA-maintained IGP Algorithm Types sub-registry (IANA-IGP-ALGO) under the IGP Parameters registry with a value between 0 and 127. In practice, only two standard IGP algorithms have been defined so far (Algo 0 and Algo 1), which both share the same calculation type: Shortest Path First (SPF). This is the only calculation type currently available for flexible algorithms.
:::

**计算类型**说明"路径怎么算"，取自标准 IGP 算法所用的计算类型。标准算法就是 IANA 的 *IGP Algorithm Types* 子注册表（IANA-IGP-ALGO）里 0–127 的那些。实际上目前只定义了 **Algo 0 与 Algo 1**，两者计算类型相同，都是 **SPF**——这也是灵活算法**当前唯一可选**的计算类型。

:::en
The optimization metric indicates which link metric should be considered for the shortest path calculation. RFC 9350 specifies three possible optimization metrics: the IGP metric, the traffic engineering default metric (or TE metric for short), and the minimum unidirectional link delay (or link delay for short).
:::

**优化度量**说明最短路径计算该用哪个链路度量。RFC 9350 规定三种：

| Metric-Type | 名称 | 度量来源 | 典型用途 |
|---|---|---|---|
| **0** | IGP metric | 基础 IGP 度量（IS-IS wide metric / OSPF cost） | "避开某些链路"的普通专网 |
| **1** | 链路时延（min unidirectional link delay） | 动态测量或静态配置 | 5G 回传、金融、实时视频 |
| **2** | TE metric | TE 默认度量 | 已有 TE 规划的存量网 |

:::en
The constraints consist of zero, one, or more filtering rules that identify network resources to be included in or excluded from the paths of this Flex-Algo. The rules specified in RFC 9350 allow a Flex-Algo to exclude all links that belong to a specific Shared Risk Link Group (SRLG); exclude all links with a specific affinity color (also known as administrative group); include only links with at least one affinity color from a specific set of colors; include only links with a specific combination of affinity colors.
:::

**约束**是零到多条**过滤规则**，用来指定哪些资源**进**、哪些**出**该算法的路径。RFC 9350 定义四类：

1. **排除 SRLG**：属于指定共享风险链路组的链路全部排除；
2. **排除亲和色**（exclude-any admin group）：带某亲和色（= 管理组）的链路全部排除；
3. **包含任一**（include-any admin group）：只保留**至少带一个**指定色的链路；
4. **全部包含**（include-all admin group）：只保留**同时带齐**指定色组合的链路。

:::en
For a link to be eligible for use in a particular Flex-Algo, it must advertise a value for the selected optimization metric, match all of the include constraints and none of the exclude constraints in the Flex-Algo definition.
:::

一条链路要能被某 Flex-Algo 使用，必须同时满足：**通告了所选优化度量的值**、**满足全部 include 约束**、**不满足任何 exclude 约束**。三条是"与"关系——任何一个不满足，这条链路就从该算法的拓扑里消失（4.6 节的剪枝）。

:::en
For example, the low-delay Flex-Algo(128) described in the previous section is defined with the SPF calculation type, link delay optimization, and an empty set of constraints. The corresponding router configuration is shown in Example 4.5.
:::

例如前面那个低时延 **Flex-Algo(128)**：SPF 计算类型、时延优化、**空约束集**。配置见例 4.5 —— 全部内容只有两行。

**例 4.5：定义低时延 Flex-Algo(128)**

```text
router isis 1
 flex-algo 128
  metric-type delay
  advertise-definition
```

:::en
The metric-type configuration specifies the Flex-Algo optimization metric and advertise-definition instructs the IGP to advertise this Flex-Algo definition as part of its Router Capability TLV for IS-IS (see Figure 4.2) or Router Information LSA for OSPF (see Figure 4.3) to the other nodes of the IGP domain. The SPF calculation type does not need to be configured since it is the only available type.
:::

`metric-type` 指定优化度量；`advertise-definition` 指示 IGP **把这份定义泛洪出去**——在 IS-IS 里装进 **Router Capability TLV**（图 4.2），在 OSPF 里装进 **Router Information LSA**（图 4.3）。计算类型不用配，因为没有第二个选项。

**注意这条命令是"泛洪开关"**：不写 `advertise-definition` 的节点，定义只在本地有效，永远不可能被选中（4.3.1 的规则），而且它自己也**不会参与**。

:::en
The Flex-Algo definition is configured on a node within the scope of an IGP instance (IS-IS instance 1 in Example 4.5) and the node advertises that definition in all levels or areas that it is part of within this instance. For example, an IS-IS level-2-only node advertises the Flex-Algo definition only in the level 2 backbone, while a level-1-2 node advertises it in both level 1 and level 2. Flex-Algo definitions are not shared across IGP instances, meaning that if a node needs to advertise the same Flex-Algo definition in multiple IGP instances, the definition must be configured separately for each instance.
:::

Flex-Algo 定义配在**某个 IGP 实例内**（例 4.5 是 IS-IS 实例 1），节点会在它所属的**所有 level / area** 通告这份定义：

| 节点类型 | 通告范围 |
|---|---|
| level-2-only | 只在 level 2 骨干 |
| level-1-2 | **level 1 和 level 2 都通告** |
| 多实例节点 | **每个实例要单独配一份**（定义不跨实例共享） |

这条对多区域设计很关键：第 5 章讲的泄露（leaking）之所以必要，一部分原因就是**Flex-Algo 参与者与定义都按 level 算**，level-1 里的算法路径可能需要 locator 被泄露到 level-2 才能跨区贯通。

{{FIG|04/fig-4-4-fad-tlv|图 4-2 · 矢量版|Flex-Algo 定义 TLV：三要素分别落在 Flex-Algorithm、Calc-Type、Metric-Type 与约束 Sub-TLV 上。}}

```asciifig
    图 4-2：原书 Figure 4.2 / 4.3 —— Flex-Algo 定义（FAD）TLV 格式

   0                   1                   2                   3
   0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
  |  Type (26 IS-IS / 16 OSPF / 1039 BGP-LS)      |    Length     |
  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
  |  Flex-Algorithm (128-255)     |  Metric-Type  |   Calc-Type   |
  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
  |   Priority    |                                               |
  +-+-+-+-+-+-+-+-+            Sub-TLVs（约束集）                 +
  |  Exclude SRLG / Exclude Admin / Include-Any / Include-All / Flags
  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

*图 4-2：Flex-Algo 定义 TLV（按原书 Figure 4.2 / 4.3 合并重绘，RFC 9350 §5.1）*

| 字段 | 说明 |
|---|---|
| **Type** | IS-IS `26`；OSPF `16`；BGP-LS `1039` |
| **Length** | TLV 总长（含全部 sub-TLV） |
| **Flex-Algorithm** | 算法编号，128–255 |
| **Metric-Type** | 优化度量：`0`=IGP metric，`1`=link delay，`2`=TE metric |
| **Calc-Type** | 借用的标准算法编号。RFC 9350 规定：SPF 时**此字段填 0** |
| **Priority** | 定义选择时的优先级（4.3.1 的选主依据） |
| **Sub-TLVs** | 承载 flags 与四类约束 |

| Sub-TLV | 含义 |
|---|---|
| **Exclude SRLG** | 要排除的 SRLG 列表 |
| **Exclude Admin Group** | 要排除的亲和色位图 |
| **Include-Any Admin Group** | 允许的**单个**亲和色位图（命中任一即可） |
| **Include-All Admin Group** | 必须**同时满足**的亲和色组合位图 |
| **Flags** | 撰写本书时 SRv6 场景**未使用** |

:::en
IGP nodes advertise their Flex-Algo definitions for two reasons. First, it simplifies the network configuration by allowing nodes to register their participation in a Flex-Algo and then learn its definition from the network. The Flex-Algo definition does not need to be configured on every node in the network. Second, and most importantly, it allows all participating nodes to agree on a single definition of each Flex-Algo, thus ensuring consistent routing decisions and avoiding routing loops.
:::

为什么要泛洪定义？两个原因：

1. **简化配置**：节点只要"报名参与"，定义从网上学。定义不必逐台配置。
2. **（更重要）保证一致**：所有参与者必须用**同一份**定义，否则各自算出的路径不一样，会**产生环路**。

第 2 点是 Flex-Algo 最容易被忽略的失效模式：定义不一致不是"性能差一点"，而是**转发环路或黑洞**。这与"两套 SPF 树各自为政"完全不同。

:::en
Let us now configure the low-delay Flex-Algo(128) definition on Node 1 as shown in Example 4.5. We can then verify that Node 1 properly advertises this definition in its IS-IS Router Capability TLV by looking at the IS-IS database. The command output is reported in Example 4.6.
:::

在节点 1 上按例 4.5 配好定义后，查 IS-IS 数据库确认它确实在 **Router Capability TLV** 里通告了这份定义（例 4.6）。

**例 4.6：节点 1 在 IS-IS Router Capability TLV 中通告的 Flex-Algo(128) 定义**

```text
RP/0/RP0/CPU0:R1# show isis database verbose R1
IS-IS 1 (Level-2) Link State Database
LSPID                 LSP Seq Num  LSP Checksum  LSP Holdtime/Rcvd  ATT/P/OL
R1.00-00            * 0x00000010   0x3b5a        1030 /*            0/0/0
<...>
  Hostname:       R1
  Router Cap:     0.0.0.0 D:0 S:0
    IPv6 Router ID: fc00:0:1::1
    Flex-Algo Definition:
      Algorithm: 128 Metric-Type: 1 Alg-type: 0 Priority: 128
<...>
```

:::en
In this output, Metric-Type indicates the optimization metric, with the value 1 mapping to link delay in the Metric-Type IANA registry, and Alg-type indicates the Flex-Algo calculation type (Calc-Type), with 0 being SPF in the Algorithm Types registry. The Priority value 128 is the default in Cisco IOS XR.
:::

读法：`Metric-Type: 1` = **链路时延**（IANA Metric-Type 注册表值 1）；`Alg-type: 0` = **SPF**；`Priority: 128` 是 IOS XR 的**默认优先级**。

排障提示：这条输出是**"定义是否被泛洪"**的唯一判据。若某台节点 `show isis database verbose` 里看不到 `Flex-Algo Definition`，就说明它没配 `advertise-definition`，或者只配在别的实例里。

:::en
As another example, let us define a reliable-path Flex-Algo(129) with SPF calculation type, IGP metric, and a constraint to exclude red affinity links, assuming that the affinity color red is set on every link with a significant packet drop rate. This definition is configured as shown in Example 4.7.
:::

第二个例子：定义一个"可靠路径" **Flex-Algo(129)** —— SPF 计算类型、**IGP 度量**、并**排除 RED 亲和链路**（假设每条丢包率明显的链路都打了 RED 色）。

**例 4.7：定义可靠路径 Flex-Algo(129)**

```text
router isis 1
 affinity-map RED bit-position 1
 !
 flex-algo 129
  priority 50
  advertise-definition
  affinity exclude-any RED
```

:::en
In this instance, the optimization metric is not explicitly configured since the IGP metric is the default. The affinity name RED is a locally significant user-defined name that indicates the bit position 1, or second least significant bit (LSB), in the affinity bitmap. Network links are colored by setting this affinity in the IGP configuration for the corresponding interface (see Example 4.9). We give this definition a priority of 50.
:::

本例**没有显式配优化度量**，因为 IGP 度量就是默认值。`RED` 是**本地有效**的别名，指向亲和位图的**第 1 位（次低位）**。链路染色在接口的 IGP 配置里做（例 4.9）。这里刻意给了 `priority 50`。

| 配置项 | 本例取值 | 为什么这样填 |
|---|---|---|
| `metric-type` | 未配 → IGP metric | 目标是"避开坏链路"，不是换度量 |
| `affinity-map RED` | bit-position 1 | 别名只在本机有意义，**各节点必须位值一致** |
| `exclude-any RED` | 排除 RED 链路 | 四类约束里最常用的一种 |
| `priority 50` | 低于默认 128 | 为 4.3.1 的选主留下确定性 |

:::en
The definition of this Flex-Algo(129) is advertised in the IS-IS Router Capability TLV of Node 1 alongside the definition Flex-Algo(128), as shown in Example 4.8.
:::

Flex-Algo(129) 的定义与 Flex-Algo(128) **并列**通告在节点 1 的 Router Capability TLV 里（例 4.8）。

**例 4.8：节点 1 同时通告 Flex-Algo(128) 与 Flex-Algo(129) 的定义**

```text
RP/0/RP0/CPU0:R1# show isis database verbose R1
IS-IS 1 (Level-2) Link State Database
LSPID                 LSP Seq Num  LSP Checksum  LSP Holdtime/Rcvd  ATT/P/OL
R1.00-00            * 0x00000010   0x3b5a        1030 /*            0/0/0
<...>
  Hostname:       R1
  Router Cap:     0.0.0.0 D:0 S:0
    IPv6 Router ID: fc00:0:1::1
    Flex-Algo Definition:
      Algorithm: 128 Metric-Type: 1 Alg-type: 0 Priority: 128
    Flex-Algo Definition:
      Algorithm: 129 Metric-Type: 0 Alg-type: 0 Priority: 50
      Flex-Algo Exclude-Any Ext Admin Group:
        0x00000002
<...>
```

:::en
The value 0x00000002 under Flex-Algo Exclude-Any Ext Admin Group is the hexadecimal representation of the affinity bitmap with one bit set a position 1, matching the configuration in Example 4.7.
:::

`Flex-Algo Exclude-Any Ext Admin Group: 0x00000002` 是亲和位图的十六进制表示 —— **位 1 被置 1**（`0x2`），与例 4.7 的 `bit-position 1` 对得上。位图是**最右位为位 0**，所以"位 1"落在倒数第二位上，写出来就是 `0x00000002`。

:::en
In the network of Figure 4.4, we color the link between Node 3 and Node 5 with the red affinity to indicate that it has a large drop rate and have it excluded from our reliable path Flex-Algo(129). The configuration of Node 3 is shown in Example 4.9 and a similar one is applied on Node 5 for the reverse direction.
:::

在图 4.4 的网络里，把**节点 3 与节点 5 之间的链路**染成 RED（表示丢包率高），让可靠路径 Flex-Algo(129) 排除它。节点 3 的配置见例 4.9，节点 5 上要配一条对称的（反向）。**染色必须两端都打**，否则只有单向避开。

**例 4.9：节点 3 在指向节点 5 的接口上打 RED 亲和**

```text
router isis 1
 affinity-map RED bit-position 1
 interface GigabitEthernet0/0/0/2
  !! towards Node 5
  affinity flex-algo RED
```

:::en
Other practical applications for tagging and excluding links using Flex-Algo include avoiding unsecure or private use links, low-capacity links, or generally any link deemed inappropriate for a certain traffic type.
:::

用 Flex-Algo 染色排除链路的其他实用场景：

| 染色语义 | 排除原因 |
|---|---|
| `INSECURE` | 走公网/第三方、未加密的链路 |
| `PRIVATE` | 私有用途（科研专线、租赁给客户的波长） |
| `LOWCAP` | 低容量链路（微波、卫星备份），大流量走上去会拥塞 |
| `RED` / `BAD` | 高丢包、高误码、老化了的光模块 |
| `OVERSEA` | 跨洋链路（时延抖动大、故障修复周期长） |

:::en
With this configuration, the Flex-Algo(129) shortest path from Node 1 to Node 3 is then 1 → 6 → 5 → 4 → 3, as represented in Figure 4.4.
:::

配上之后，**Flex-Algo(129) 从节点 1 到节点 3 的最短路径变成 1 → 6 → 5 → 4 → 3**（原书 Figure 4.4）。

```text
    图 4-3：原书 Figure 4.4 —— 节点 1 到节点 3 的 Algo(0) 与 Flex-Algo(129) 路径

   Algo(0)（不排除任何链路）：
       1 ──10── 6 ──10── 5 ──10── 3                代价 30

   Flex-Algo(129)（排除 RED 链路 5-3）：
       1 ──10── 6 ──10── 5          ✗ 5-3 是 RED，不可用
                            │
                            └─10── 4 ──10── 3        代价 40
                                           ▲
       备选 1 ──40── 2 ──10── 3  = 50，比 40 贵，不选

   注意：算法 129 的度量仍是 IGP 度量（Metric-Type 0），
   变的只是"哪些链路可用"——约束改变拓扑，度量决定最短路。
```

*图 4-3：排除 RED 链路后最优路径改走 4（按原书 Figure 4.4 重绘，度量见表 4-1）*

:::en
Without using Flex-Algo, the same path could be encoded with the SR-TE SID-list <fc00:0:4:0::, fc00:0:3:0::>, where fc00:0:4:0:: and fc00:0:3:0:: are respectively the Algo(0) Prefix-SIDs of Node 4 and Node 3.
:::

不用 Flex-Algo 也能达到同样效果：用 SR-TE 段列表 `<fc00:0:4:0::, fc00:0:3:0::>`，其中 `fc00:0:4:0::`、`fc00:0:3:0::` 分别是节点 4 与节点 3 的 **Algo(0) Prefix-SID**。

对比一下就明白差别：段列表是**"这一次这么走"**，Flex-Algo 是**"这类流量永远这么走"**。前者要控制器逐条下发、拓扑变了要重算；后者由 IGP 自动维护。

### 4.3.1 定义的一致性：谁能当"权威版本"

:::en
The routing consistency is achieved through a deterministic procedure ensuring that all nodes in an IGP domain participating in a particular Flex-Algo select the same definition. Section 5.3 of RFC 9350 specifies the Flex-Algo definition selection procedure as the below ordered list of rules.
:::

路由一致性靠一套**确定性选择流程**保证：域内参与同一 Flex-Algo 的所有节点，**必须选出同一份定义**。RFC 9350 §5.3 规定的有序规则如下。

:::en
1. From the advertisements of the Flex-Algo definition in the area (including both locally generated and received advertisements), select the one(s) with the highest priority value. 2. If multiple advertisements of the Flex-Algo definition have the same highest priority, select the one that originated from the router with the highest System-ID in the case of IS-IS or Router-ID in the case of OSPF.
:::

1. 在**本区域**收到的所有定义通告（含本地生成的）中，选 **Priority 最大**的那份；
2. 若优先级并列最高，选**发起者 System-ID（IS-IS）/ Router-ID（OSPF）最大**的那份。

:::en
Furthermore, a Flex-Algo definition is only considered a candidate for selection if it is advertised. A local definition on a node that is not advertised can never become the selected definition.
:::

补充一条：**只有被通告的定义才有资格参与选举**。本地配置但没 `advertise-definition` 的定义，永远不会被选中。

:::en
These rules show that at least one node in each IGP area must advertise the Flex-Algo definition. In practice, two or more advertisers in each area are recommended for redundancy. If no node advertises the Flex-Algo definition, all participating nodes withdraw their participation and the Flex-Algo becomes non-functional.
:::

由此可得：**每个 IGP 区域至少有一台节点必须通告该定义**；生产中建议**两台以上**（冗余）。如果**没有任何节点通告**，所有参与者都会**撤回参与**，这个 Flex-Algo 直接**失效**。

{{FIG|04/fig-4-5-election|图 4-4 · 矢量版|定义选举：先取 Priority 最大，并列比 System-ID，再判断本机是否支持该定义。}}

```asciifig
    图 4-4：定义选举的判定流程（RFC 9350 §5.3）

   收到本区内该算法的所有定义通告（含本地）
                    │
                    ▼
        ┌───────────────────────────┐
        │ 通告集合为空？            │──是──► 撤回参与，算法失效
        └───────────────────────────┘        （前缀从转发表移除）
                    │否
                    ▼
        ┌───────────────────────────┐
        │ 取 Priority 最大的一组    │
        └───────────────────────────┘
                    │
                    ▼
        ┌───────────────────────────┐
        │ 仍有并列？                │──是──► 取 System-ID/Router-ID 最大者
        └───────────────────────────┘
                    │否
                    ▼
        ┌───────────────────────────┐
        │ 本机支持该定义？          │──否──► 不参与（撤回 SR-Algorithm 里的算法号）
        │ （计算类型/度量/约束）    │
        └───────────────────────────┘
                    │是
                    ▼
        参与该算法：SR-Algorithm TLV 带上算法号
                    + 计算该算法的 SPF 树 + 生成/接收该算法的段
```

*图 4-4：Flex-Algo 定义的选择与参与判定（按 RFC 9350 §5.3 与 4.3.1/4.4 文字绘制）*

**工程推论（血泪版）**：

| 现象 | 原因 | 处理 |
|---|---|---|
| 全网只有一台节点在通告定义 | 它重启/维护期间算法整体失效 | **至少两台**通告，最好分散在不同机框 |
| 两台节点通告的定义 Priority 相同但内容不同 | 靠 System-ID 比大小决出，**结果不可控** | 用 `priority` 显式指定权威，内容靠配置模板统一 |
| 某节点老配置残留了同 priority 的旧定义 | 旧定义内容不同（比如 metric-type 变了） | 巡检 `show isis database verbose` 对比 Metric-Type/Alg-type |
| 定义一致但部分节点不支持某约束 | 该节点撤回参与，拓扑缺块 | 升级版本或去掉该约束 |

## 4.4 算法参与（Participation）

:::en
When a routing node supports a particular IGP algorithm, standard or Flex-Algo, we say that it participates in this algorithm. Participating in an algorithm allows the node to be considered as part of the topology for that algorithm.
:::

一台路由节点**支持**某个 IGP 算法（标准算法或 Flex-Algo），就说它**参与（participate）**了这个算法。参与意味着该节点**被算进这个算法的拓扑**里。

:::en
In other words, a node that does not participate in a given algorithm cannot be a source, destination, or even transit of any routing path for that algorithm. This is to avoid blackholing traffic by sending it to a node that does not have forwarding entries for the locators of that algorithm.
:::

换句话说，**不参与某算法的节点，不能是该算法任何路径的源、目的，甚至中转**。原因是避免**黑洞**：把报文送给一个**没有该算法 locator 转发表项**的节点，报文到那里就没了。

> 这句是本章最"硬"的一句。它解释了为什么"不参与"不是"少一条链路"那么简单——**它是从拓扑里整台消失**，连"顺路经过"都不行。

:::en
Each node advertises the list of IGP algorithms that it supports in the Algorithm TLV, which is part of the Router Capability TLV (IS-IS), the Router Information LSA (OSPF), or the Node NLRI (BGP-LS).
:::

每台节点在 **Algorithm TLV（SR-Algorithm TLV）** 里通告自己支持的算法列表。该 TLV 在 IS-IS 中属于 Router Capability TLV，在 OSPF 中属于 Router Information LSA，在 BGP-LS 中属于 Node NLRI。

{{FIG|04/fig-4-6-sr-algo|图 4-5 · 矢量版|SR-Algorithm TLV：通告即参与，Algo(0) 默认参与。}}

```asciifig
    图 4-5：原书 Figure 4.5 / 4.6 —— SR-Algorithm TLV 格式

   0                   1                   2                   3
   0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
  |  Type (19 IS-IS / 8 OSPF / 1035 BGP-LS)       |    Length     |
  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
  |  Algorithm 1  |  Algorithm 2  |  ...  |  Algorithm n          |
  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

  每个 Algorithm 一个 octet：0、1、128、129 ……
  Algo(0) 强制出现（即使不显式配）。
```

*图 4-5：SR-Algorithm TLV（按原书 Figure 4.5 / 4.6 合并重绘，RFC 8667 / RFC 8665 / RFC 9085）*

| 字段 | 说明 |
|---|---|
| **Type** | IS-IS `19`；OSPF `8`；BGP-LS `1035` |
| **Length** | TLV 长度 |
| **Algorithm 1..n** | 支持的 IGP 算法列表，**至少包含 Algo(0)** |

:::en
A node participates in an algorithm when it advertises the support of that algorithm. As an exception, all nodes are assumed to participate in Algo(0) even without an explicit advertisement. This is because Algo(0) is the default shortest path algorithm supported in all implementations of IS-IS and OSPF.
:::

**通告即参与**。唯一的例外是 **Algo(0)**：即使不显式通告，所有节点也被**默认视为参与**，因为它是 IS-IS / OSPF 所有实现的默认最短路径算法。

:::en
SR-enabled nodes running Cisco IOS XR always advertise the participation in Algo(0) and Algo(1), although the latter is only applicable to SR-MPLS at this time.
:::

IOS XR 的 SR 节点**总是同时通告 Algo(0) 与 Algo(1)**，尽管后者目前只对 SR-MPLS 有意义。所以看到输出里有 `Algorithm: 1` 不必奇怪，它不代表 SRv6 用了 Strict-SPF。

:::en
In Cisco IOS XR, participation in a Flex-Algo is configured for an IGP process with the flex-algo keyword. This is the same keyword that starts the configuration of a Flex-Algo definition (see Example 4.5 and Example 4.7).
:::

IOS XR 里用 **`flex-algo`** 关键字在 IGP 进程下配置参与 —— 与配置定义**是同一个关键字**。这带来一个重要副作用：**只要本机有该算法的本地定义，路由器就会自动尝试参与**。

:::en
Hence, an Cisco IOS XR router always attempts to participate in a Flex-Algo for which it has a local definition. A node may also participate in a Flex-Algo without a local definition. In this case, the Flex-Algo participation is configured as shown in Example 4.10.
:::

因此，IOS XR 路由器**对本机有定义的算法一定会尝试参与**；也**可以只参与、不带本地定义**，写法见例 4.10。

**例 4.10：只参与 Flex-Algo(128) 与 Flex-Algo(129)（不带定义）**

```text
router isis 1
 flex-algo 128
 !
 flex-algo 129
```

配置里只有算法号、没有 `metric-type` / `affinity` / `advertise-definition` —— 这就是"**空定义 + 参与**"的写法：定义从网上学，参与是本地的。

:::en
Regardless of whether a local definition is configured or not, the node listens to the other definitions advertised in the IGP domain and selects one using the procedure in section 4.3.1. If the node supports the selected definition, it advertises its participation in the Flex-Algo in the SR-Algorithm TLV, as shown in Example 4.11 for Node 3.
:::

无论有没有本地定义，节点都会**监听**域内通告的定义，按 4.3.1 的流程选出一份。**若本机支持被选中的定义**（计算类型、度量、约束都支持），就在 SR-Algorithm TLV 里通告参与（例 4.11）。

**例 4.11：节点 3 在 IS-IS Router Capability TLV 中通告的算法支持列表**

```text
RP/0/RP0/CPU0:R3# show isis database verbose R3
IS-IS 1 (Level-2) Link State Database
LSPID                 LSP Seq Num  LSP Checksum  LSP Holdtime/Rcvd  ATT/P/OL
R3.00-00            * 0x00000010   0x040f        891  /*            0/0/0
<...>
  Hostname:       R3
  Router Cap:     0.0.0.0 D:0 S:0
    IPv6 Router ID: fc00:0:3::1
    SR Algorithm:
      Algorithm: 0
      Algorithm: 1
      Algorithm: 128
      Algorithm: 129
<...>
```

读法：`Algorithm: 0/1` 是 IOS XR 的常规输出，`128/129` 才是本章关心的 —— **节点 3 参与了两个 Flex-Algo**。这一行是"参与者名单"的来源，也是排障第一个要看的地方。

:::en
A node that neither advertises nor receives any definition for a Flex-Algo, or does not support the calculation type, optimization metric, or any of the constraints in the selected Flex-Algo definition, withdraws from participating in this Flex-Algo. This means that the node removes the Flex-Algo identifier from its SR-Algorithm TLV and all prefixes associated with the Flex-Algo from its forwarding table.
:::

节点在以下情况**退出**该 Flex-Algo：

1. 既不通告也收不到该算法的任何定义；
2. 或者**不支持**选中定义中的计算类型、优化度量、或任何一条约束。

退出动作很干净：**从 SR-Algorithm TLV 里删掉算法号**，并把**所有关联该算法的前缀从转发表里移除**。

> 注意第 2 条的杀伤力：升级时某台设备不支持 `metric-type delay`，它不会"降级使用 IGP 度量"，而是**直接退出**该算法。表现是"这台节点在该算法下不可达"，而不是"路径变差"。

:::en
In some cases, a node may advertise a Flex-Algo definition without participating in that Flex-Algo. This may occur, for instance, if the node does not support the selected Flex-Algo definition.
:::

也存在"**通告定义但不参与**"的节点，例如它通告了一个自己也不支持的定义（多出现在过渡期或配置错误时）。

:::en
In theory, the participation in a Flex-Algo is independent from the advertisement of a locator or any segment for that Flex-Algo. A node could be configured to participate in a Flex-Algo without advertising any associated locator, or it could have a locator associated with a Flex-Algo that it does not participate in.
:::

理论上，**参与**与**通告 locator 或段**是彼此独立的：可以只参与不通告 locator，也可以有 locator 却不参与。

:::en
However, neither of these combinations makes sense in practice. A node that does not advertise a locator for a Flex-Algo that it supports cannot be a midpoint nor the destination of any SR path for that Flex-Algo. This includes TE paths as well as TI-LFA backup paths. Similarly, a Flex-Algo locator on a node that does not participate in this Flex-Algo is not reachable from any other node in the domain, even if that locator was advertised in the IGP. This is because non-participating nodes are excluded from the Flex-Algo topology.
:::

但**两种组合在实践中都没有意义**：

- 参与算法却**不通告 locator**：它不能做该算法任何 SR 路径的**中转或终点**，**包括 TE 路径与 TI-LFA 备份路径** —— 换句话说它在算法里是"死胡同"，只能当纯中转的普通节点，却不能当 PLR 的修复目标。
- 有算法 locator 却**不参与**：该 locator 从域内**任何节点都不可达**，即使它在 IGP 中被通告了 —— 因为**不参与 = 被排除在该算法拓扑之外**。

:::en
For these reasons, we assume throughout this book that when a node participates in a Flex-Algo, it also advertises an associated locator and prefix segment, as well as an adjacency segment for every interface connected to other participating nodes.
:::

所以本书假设：**一台节点参与某 Flex-Algo，就同时通告关联的 locator、前缀段，以及每条"连到其他参与者"的接口上的邻接段。**

| 参与 | 有该算法 locator | 结果 | 说明 |
|---|---|---|---|
| ✅ | ✅ | **正常**（本书假设的配置） | 可中转、可作终点、可被 TI-LFA 修复 |
| ✅ | ❌ | 无意义 | 不能当中转/终点，TE 与备份路径都用不上它 |
| ❌ | ✅ | **不可达** | locator 泛洪了但没人算得出路径（拓扑里没它） |
| ❌ | ❌ | 完全没有该算法 | 回落到 Algo(0) |

{{FIG|04/fig-4-7-participation|参与与可达 · 矢量版|参与 × locator 通告的四种组合：只有“既参与又通告”才能当中转、终点与被修复目标。}}


## 4.5 Flex-Algo 段的实例化：一个 uN，一组 uA

:::en
When a Flex-Algo locator is configured in Cisco IOS XR (see Example 4.1), the SID manager process instantiates the corresponding Flex-Algo prefix segment. Then, when this locator and the Flex-Algo participation are configured in an IGP instance (see Example 4.10 and Example 4.4), the IGP process dynamically instantiates a Flex-Algo adjacency segment for each interface in this IGP instance.
:::

在 IOS XR 里配好 Flex-Algo locator（例 4.1）后，**SID manager 进程**实例化对应的 **Flex-Algo 前缀段**；当该 locator 与**算法参与**同时配进某个 IGP 实例（例 4.4 + 例 4.10），**IGP 进程**再为这个实例下的**每个接口**动态实例化 **Flex-Algo 邻接段**。

```text
   两个进程、两次触发、两类段：

   sidmgr ──(配 locator + algorithm)──► uN：fc00:1:3::        （每个 locator 1 个）
   isis-1 ──(配 locator + 参与算法) ──► uA：fc00:1:3:e000::   （每个接口 1 个）
                                          fc00:1:3:e001:: ...
   ── 只做第一步：有 uN 没 uA（例 4.3 的现象）
   ── 两步都做：uN + 全套 uA（例 4.12 的现象）
```

**例 4.12：启用 Flex-Algo(128) 与 Flex-Algo(129) 后节点 3 上的段列表**

```text
RP/0/RP0/CPU0:R3# show segment-routing srv6 sid all
*** Locator: 'MAIN' ***
SID                Behavior      Context                      Owner      State  RW
-----------------  ------------  ---------------------------  ---------  -----  --
fc00:0:3::         uN (PSP/USD)  'default':3                  sidmgr     InUse  Y
fc00:0:3:e000::    uA (PSP/USD)  [Gi0/0/0/1, Link-Local]:0    isis-1     InUse  Y
fc00:0:3:e001::    uA (PSP/USD)  [Gi0/0/0/2, Link-Local]:0    isis-1     InUse  Y
fc00:0:3:e002::    uA (PSP/USD)  [Gi0/0/0/0, Link-Local]:0    isis-1     InUse  Y
*** Locator: 'DELAY' ***
fc00:1:3::         uN (PSP/USD)  'default':3                  sidmgr     InUse  Y
fc00:1:3:e000::    uA (PSP/USD)  [Gi0/0/0/1, Link-Local]:128  isis-1     InUse  Y
fc00:1:3:e001::    uA (PSP/USD)  [Gi0/0/0/2, Link-Local]:128  isis-1     InUse  Y
fc00:1:3:e002::    uA (PSP/USD)  [Gi0/0/0/0, Link-Local]:128  isis-1     InUse  Y
*** Locator: 'RELIABLE' ***
fc00:2:3::         uN (PSP/USD)  'default':3                  sidmgr     InUse  Y
fc00:2:3:e000::    uA (PSP/USD)  [Gi0/0/0/1, Link-Local]:129  isis-1     InUse  Y
fc00:2:3:e001::    uA (PSP/USD)  [Gi0/0/0/2, Link-Local]:129  isis-1     InUse  Y
fc00:2:3:e002::    uA (PSP/USD)  [Gi0/0/0/0, Link-Local]:129  isis-1     InUse  Y
```

**这张表要逐字读**，它把"算法"这个抽象概念落到了每一行：

| 观察点 | 含义 |
|---|---|
| 三套 locator（MAIN / DELAY / RELIABLE） | 同一台节点、三个地址块，对应 Algo(0)/128/129 |
| 每套内有 **1 个 uN** + **N 个 uA** | uN 由 sidmgr 生成；uA 数量 = 该算法下参与接口数 |
| `Context` 尾部 `:0` / `:128` / `:129` | **该邻接段所属的算法**，这就是"算法进了 SID 本身" |
| 三段的后缀完全一样（`e000`/`e001`/`e002`） | 同一物理接口在三套 locator 下**各得一个 SID**，可并存 |

由此得到一个重要事实：**一台 4 接口的节点参与 3 个算法，就有 3 个 uN + 12 个 uA = 15 个段，却只占 3 条 IGP 路由**。这就是 locator 汇总（3.2 节）与 Flex-Algo 叠加后的规模账本。

:::en
The node also starts advertising the Flex-Algo locator, prefix segment, and adjacency segments to the other nodes in the IGP domain.
:::

节点开始向域内其他节点**通告** Flex-Algo 的 locator、前缀段与邻接段。

**例 4.13：节点 3 通过 IS-IS 通告的 SRv6 locator 与段（链路信息已截断，只保留到节点 2 的接口）**

```text
RP/0/RP0/CPU0:R3# show isis database verbose R3
IS-IS 1 (Level-2) Link State Database
LSPID                 LSP Seq Num  LSP Checksum  LSP Holdtime/Rcvd  ATT/P/OL
R3.00-00            * 0x00000010   0x040f        891  /*            0/0/0
<...>
  Hostname:       R3
  Metric: 1          MT (IPv6 Unicast) IPv6 fc00:0:3::/48
    Prefix Attribute Flags: X:0 R:0 N:0 E:0 A:0
  SRv6 Locator:   MT (IPv6 Unicast) fc00:0:3::/48 D:0 Metric: 0 Algorithm: 0
    Prefix Attribute Flags: X:0 R:0 N:0 E:0 A:0
    END SID: fc00:0:3:: uN (PSP/USD)
      SID Structure:
        Block Length: 32, Node-ID Length: 16, Func-Length: 0, Args-Length: 80
  SRv6 Locator:   MT (IPv6 Unicast) fc00:1:3::/48 D:0 Metric: 0 Algorithm: 128
    Prefix Attribute Flags: X:0 R:0 N:0 E:0 A:0
    END SID: fc00:1:3:: uN (PSP/USD)
      SID Structure:
        Block Length: 32, Node-ID Length: 16, Func-Length: 0, Args-Length: 80
  SRv6 Locator:   MT (IPv6 Unicast) fc00:2:3::/48 D:0 Metric: 0 Algorithm: 129
    Prefix Attribute Flags: X:0 R:0 N:0 E:0 A:0
    END SID: fc00:2:3:: uN (PSP/USD)
      SID Structure:
        Block Length: 32, Node-ID Length: 16, Func-Length: 0, Args-Length: 80
  Metric: 10         MT (IPv6 Unicast) IS-Extended R2.00
    Local Interface ID: 7, Remote Interface ID: 7
    Interface IPv6 Address: 2001:0:0:23::3
    Neighbor IPv6 Address: 2001:0:0:23::2
    Physical BW: 1000000 kbits/sec
    Link Average Delay: 4000 us
    Link Min/Max Delay: 4000/4000 us
    Link Delay Variation: 0 us
    Application Specific Link Attributes:
      L flag: 0, SA-Length: 1, UDA-Length: 1
      Standard Applications: 0x10 FLEX-ALGO
      User Defined Applications: 0x10
      Link Min/Max Delay: 4000/4000 us
    END.X SID: fc00:0:3:e000:: B:0 S:0 P:0 uA (PSP/USD) Alg:0
      SID Structure:
        Block Length: 32, Node-ID Length: 16, Func-Length: 16, Args-Length: 64
    END.X SID: fc00:1:3:e000:: B:0 S:0 P:0 uA (PSP/USD) Alg:128
      SID Structure:
        Block Length: 32, Node-ID Length: 16, Func-Length: 16, Args-Length: 64
    END.X SID: fc00:2:3:e000:: B:0 S:0 P:0 uA (PSP/USD) Alg:129
      SID Structure:
        Block Length: 32, Node-ID Length: 16, Func-Length: 16, Args-Length: 64
<...>
```

这段输出是**本章信息密度最高的一段**，四个看点：

1. **三个 `SRv6 Locator` 各带自己的 `Algorithm:`** —— Algo(0)/128/129。这就是 4.2 节"算法绑 locator"的报文级证据；它写在 Locator TLV 的 Algorithm 字段里（图 3-4）。
2. **三个 `END SID` 的 SID Structure 完全相同**（32/16/0/80）—— 算法不改变 SID 结构，只改变路由方式。这句话对 uSID 互操作至关重要。
3. **同一条 IS-Extended 邻居下挂了三个 `END.X SID`**，各自 `Alg:0` / `Alg:128` / `Alg:129` —— **一个物理接口、三个算法、三个邻接段**。这是 SR-MPLS 做不到的。
4. **`Application Specific Link Attributes` 里 `Standard Applications: 0x10 FLEX-ALGO`**，并带 `Link Min/Max Delay: 4000/4000 us` —— 时延作为"只给 Flex-Algo 应用看"的属性被通告（4.6 节展开）。

{{FIG|04/fig-4-8-sid-planes|图 4-6 · 矢量版|同一节点上并行的三套 SID 平面：每算法一个 uN、一组 uA，段数 ×3 但只占 3 条前缀路由。}}

```asciifig
    图 4-6：一台节点上的三套 SID 平面（节点 3，三个算法并行）

   ┌──────────────────────────────────────────────────────────────┐
   │  Algo(0) 平面       fc00:0:3::/48   代价最优    alg 0        │
   │    uN  fc00:0:3::          uA fc00:0:3:e00x::               │
   ├──────────────────────────────────────────────────────────────┤
   │  Flex-Algo(128)     fc00:1:3::/48   时延最优    alg 128      │
   │    uN  fc00:1:3::          uA fc00:1:3:e00x::               │
   ├──────────────────────────────────────────────────────────────┤
   │  Flex-Algo(129)     fc00:2:3::/48   排除 RED    alg 129      │
   │    uN  fc00:2:3::          uA fc00:2:3:e00x::               │
   └──────────────────────────────────────────────────────────────┘
     三套平面共用一张物理拓扑、一份 IGP 数据库、一个 SID 结构；
     区别只在：走哪棵树（SPF/128/129）、哪些链路可用（约束）。
     代价：每套 locator 一条 /48 路由，段数 ×3，转发表项 ×3。
```

*图 4-6：同一节点上并行的多套 SID 平面（按 4.5 节文字与例 4.12/4.13 绘制）*

## 4.6 路径计算：先剪枝，再跑 SPF

:::en
On each node, the IGP process calculates the shortest paths independently for every Flex-Algo in which it participates. This path calculation takes into consideration both the selected definition of the Flex-Algo and the set of participating nodes.
:::

每台节点的 IGP 进程**对每个自己参与的 Flex-Algo 独立算一遍最短路径**。计算同时考虑两件事：**选中的定义**与**参与者集合**。

:::en
For a Flex-Algo(K), the path calculation occurs as follows. 1. Build a topology Topo(K) for Flex-Algo(K), starting from the IGP topology of the domain and then pruning any node that does not advertise participation in Flex-Algo(K); any link that does not have a value for the optimization metric of Flex-Algo(K); any link that fails to meet any of the constraints of Flex-Algo(K). 2. Compute the paths from the local node to every reachable destination in Topo(K) using the calculation type and the optimization metric of Flex-Algo(K).
:::

Flex-Algo(K) 的路径计算分两步：

**第一步：构建 Topo(K)** —— 从域的基础 IGP 拓扑出发，剪掉三类东西：

| 剪枝对象 | 判据 | 典型现象 |
|---|---|---|
| **节点** | 没通告参与 Flex-Algo(K) | 该节点从算法里整体消失（连中转都不行） |
| **链路** | 不携带所选优化度量的值 | 优化度量选时延，但该链路没通告时延 → 剪掉 |
| **链路** | 不满足任何一条约束 | RED 链路、SRLG 成员、不满足 include 条件 |

**第二步：在 Topo(K) 上算最短路** —— 用 Flex-Algo(K) 的**计算类型**（SPF）与**优化度量**（IGP / delay / TE）从本机算到每个可达目的地。**不在 Topo(K) 里的东西不参与计算，也无法到达。**

{{FIG|04/fig-4-9-topo-prune|图 4-7 · 矢量版|基础拓扑剪掉不参与的节点 6 与 RED 链路 5-3，得到 Topo(130)，最短路随之改变。}}

```asciifig
    图 4-7：原书 Figure 4.7 —— 基础拓扑（左）与 Topo(130)（右）

   左：基础 IGP 拓扑，各节点支持的算法
   ┌──────────────────────────────────────────────────────────┐
   │   R1: algo 0,128,129,130        R3: algo 0,128,129,130   │
   │   R2: algo 0,128,129,130        R4: algo 0,128,129,130   │
   │   R5: algo 0,128,129,130        R6: algo 0  ← 不参与 130 │
   │   链路 5-3：RED 亲和（两条算法 129/130 都排除它）        │
   └──────────────────────────────────────────────────────────┘

   右：Flex-Algo(130) 的 Topo(130)（定义 = "IGP 度量 + 排除 RED"）
   ┌──────────────────────────────────────────────────────────┐
   │   剪枝 1：节点 6 不参与 130  → 1-6、6-5 两条链路一并消失 │
   │   剪枝 2：5-3 是 RED         → 这条链路消失              │
   │                                                          │
   │   剩下的路径 1 → 3：                                     │
   │       1 ──40── 2 ──10── 3      = 50   ← 用这条           │
   │       1 ──40── 2 ──20── 4 ──10── 3 = 70                  │
   │                                                          │
   │   对比 Flex-Algo(129)（节点 6 参与）：                   │
   │       1 ──10── 6 ──10── 5 ──10── 4 ──10── 3 = 40  ← 更优 │
   └──────────────────────────────────────────────────────────┘
```

*图 4-7：基础拓扑与剪枝后的 Topo(130)（按原书 Figure 4.7 重绘，度量见表 4-1）*

:::en
Following the path calculation, the node installs an IPv6 forwarding entry for all the locators of Flex-Algo(K) that are reachable in Topo(K).
:::

算完后，节点为 **Topo(K) 中可达的所有 Flex-Algo(K) locator** 装 IPv6 转发条目。**只在 Topo(K) 里可达的才装** —— 这就是"locator 通告了但装不了表"的机制解释。

:::en
When multiple paths offer the same shortest accumulated metric to a Flex-Algo destination, all of them are installed concurrently according to the Equal-Cost Multi-Path (ECMP) strategy. The shortest path calculation and the decision to install multiple best paths for a Flex-Algo destination are based solely on the Flex-Algo topology and optimization metric. For example, the IGP metric does not impact the paths installed for a Flex-Algo optimizing the link delay.
:::

当多条路径到某个 Flex-Algo 目的地的**累计度量并列最小**时，全部按 **ECMP** 同时装入。**选路与是否多路径，只看该算法的拓扑与优化度量**：

> 例如：**优化时延的算法，IGP 度量完全不参与选路**。一条 IGP 度量 1000、时延 1 ms 的链路，在 Flex-Algo(128) 下是"最好的"，在 Algo(0) 下可能是"最差的"。**同一张物理网，两套完全不同的代价观。**

这一点会带来一个反直觉的运维现象：**Flex-Algo(128) 的流量可能全部压在你以为的"备用链路"上**，因为那些链路平时 IGP 度量高、没人走，但时延低。容量规划必须按算法分别做。

:::en
The Flex-Algo topology construction and path calculation leverage the Application-Specific Link Attributes (ASLA) advertisements for all link attributes except the base IGP metric — namely the TE metric, link delay, affinity colors, and SRLGs.
:::

Topo(K) 的构建与路径计算，使用 **ASLA（应用专用链路属性）** 通告的**除基础 IGP 度量之外**的所有链路属性：**TE 度量、链路时延、亲和色、SRLG**。

这一句要拆开理解：**基础 IGP 度量仍然走普通链路 TLV**（所有算法共享），而**时延/亲和/SRLG 只走 ASLA 且明确标注 `FLEX-ALGO` 应用** —— 原因是同一份属性，SR-MPLS、RSVP-TE、Flex-Algo 可能各要一套值。

**例 4.14：节点 3 在 IS-IS 中为"到节点 5"的链路通告的 ASLA**

```text
Metric: 10         MT (IPv6 Unicast) IS-Extended R5.00
    Local Interface ID: 8, Remote Interface ID: 8
    Interface IPv6 Address: 2001:0:0:35::3
    Neighbor IPv6 Address: 2001:0:0:35::5
    Physical BW: 1000000 kbits/sec
    Link Average Delay: 12000 us
    Link Min/Max Delay: 12000/12000 us
    Link Delay Variation: 0 us
    Application Specific Link Attributes:
      L flag: 0, SA-Length: 1, UDA-Length: 1
      Standard Applications: 0x10 FLEX-ALGO
      User Defined Applications: 0x10
      Ext Admin Group: 0x00000002
      Affinity: 0x00000002
      Link Min/Max Delay: 12000/12000 us
```

:::en
Link attributes advertised as generic attributes but not as an ASLA for the Flex-Algo application are ignored during Flex-Algo calculation.
:::

关键一句：**只通告为"通用属性"但没有标注 `FLEX-ALGO` 应用的链路属性，在 Flex-Algo 计算中被忽略。**

于是排障时有一条硬规则：

| 现象 | 检查点 |
|---|---|
| 链路有亲和色，但算法 129 没排除它 | 亲和是否打在 **ASLA for FLEX-ALGO** 里（而不是只打通用 affinity） |
| 链路有时延，但算法 128 不选它 | 时延是否作为 **ASLA + `FLEX-ALGO`** 通告；`Standard Applications` 位图是否含 `0x10` |
| 部分链路时延为 0 / 缺失 | 时延测量未使能或静态值未配 → 该链路被**剪掉**（不携带优化度量） |

> **原书侧栏：Application-Specific Link Attributes（ASLA）**
>
> 像 SR 与 RSVP-TE 这样的路由应用，都依赖 IGP 通告的链路属性算路径。当它们**同时**跑在同一张网里时，可能对同一属性需要**不同的值**（例如 SR 与 RSVP-TE 的 TE 度量可能代表不同目标），或者需要**完全不同的属性集**（例如未预留带宽只对 RSVP-TE 有意义）。
>
> ASLA 允许 IGP **为应用 A 独立于应用 B 通告链路属性**，也可以把某些属性声明为**多应用共享**。ASLA 的概念与通告格式见 **RFC 8919（IS-IS）** 与 **RFC 8920（OSPF）**；IANA 的 *Link Attribute Application Identifiers* 子注册表（IANA-IGP-ASLA）维护支持的应用列表。撰写本书时支持的应用包括 **RSVP-TE、SR Policy、LFA、Flex-Algo**。
>
> 工程含义：**"这条链路有什么属性"和"这条链路对哪个应用有什么属性"是两个问题。** Flex-Algo 只认后者。

:::en
To illustrate the Flex-Algo path calculation, let us consider the example in Figure 4.7 with Flex-Algo(130) defined as "optimize IGP metric and exclude RED links" enabled on all nodes except Node 6. All nodes participating in Flex-Algo(130) construct the topology Topo(130) from the base IGP topology by pruning Node 6, which does not participate in the Flex-Algo, and the red link between Node 3 and Node 5, which is excluded as per the Flex-Algo definition. Those nodes then compute the shortest paths minimizing the IGP metric on Topo(130).
:::

用图 4.7 的例子说明计算过程：定义 **Flex-Algo(130) = "优化 IGP 度量 + 排除 RED 链路"**，除节点 6 外全部启用。所有参与者从基础拓扑出发构建 Topo(130)：**剪掉不参与的节点 6**、**剪掉定义排除的 RED 链路 3-5**，然后在 Topo(130) 上最小化 IGP 度量算最短路。

:::en
The base IGP topology and the Flex-Algo(130) definition are the same as Flex-Algo(129) in section 4.3. However, the non-participation of Node 6 in Flex-Algo(130) results in a different set of shortest paths. For example, the path from Node 1 to the Flex-Algo (129) locator of Node 3 is 1 → 6 → 5 → 4 → 3, as shown in Figure 4.4, while the path to the Flex-Algo(130) locator of Node 3 is 1 → 2 → 3.
:::

基础拓扑与定义都跟 4.3 节的 Flex-Algo(129) 一样，**唯一差别是节点 6 不参与 130** —— 结果最短路完全不同：到节点 3 的 **Flex-Algo(129)** locator 走 `1 → 6 → 5 → 4 → 3`（图 4-3），到 **Flex-Algo(130)** locator 走 `1 → 2 → 3`。

**这就是 Flex-Algo 最反直觉的地方**：两份定义一模一样，只因为"谁参与"不同，路径就变了。所以排查"路径不符合预期"时，**先看参与者名单，再看定义内容**。

:::en
A common use-case for restricting a Flex-Algo to a subset of the nodes in the network is to enforce disjoint paths in a dual-plane topology. This use-case is detailed in Chapter 7 of Segment Routing: Part II.
:::

把算法限制在**节点子集**上，最常见的用法是在**双平面拓扑**里做**路径分离**：

```text
   A 平面（参与 Flex-Algo 140）：R1 R2 R3 R4 R5
   B 平面（参与 Flex-Algo 141）：R1 R6 R7 R8 R5
   ── 两条 locator：fc00:4:x::/48（140）、fc00:5:x::/48（141）
   ── 业务分流：普通流走 A 平面 SID，另一类走 B 平面 SID
   ── 天然分离：两个算法的拓扑里根本没有对方平面的节点
```

这类设计比"用段列表强制绕开"稳定得多：**平面故障时，另一平面的路径不受影响，因为它们的 SPF 树本来就不重叠**。详见《Part II》第 7 章。

## 4.7 TI-LFA：备份路径也不能跨算法

:::en
The TI-LFA backup paths to Flex-Algo locators are computed according to the same rules as the primary shortest paths to the locator. That is, they minimize the optimization metric of the Flex-Algo definition, satisfy all of its constraints, and exclude any non-participating node. Furthermore, the TI-LFA backup paths to a Flex-Algo locator only include prefix segments and unprotected adjacency segments of that Flex-Algo.
:::

到 Flex-Algo locator 的 **TI-LFA 备份路径，用与主路径完全相同的规则计算**：最小化该定义的优化度量、满足全部约束、排除任何非参与节点。此外，备份路径**只能使用该算法自己的前缀段与"未受保护"的邻接段**。

这四句话把"备份路径也必须守规矩"讲透了。逐条拆：

| 规则 | 违反时的后果 |
|---|---|
| 同样最小化该算法的优化度量 | 低时延业务的备份变成高时延路径（故障后体验断崖） |
| 满足全部约束（如排除 RED） | 备份路径走上已知会丢包的链路 |
| 排除非参与节点 | 报文被送到没有该算法表项的节点 → 黑洞 |
| 段列表只用**本算法**的段 | 备份路径的段在别的算法里语义不同 → 走错树 |

> 最后一条解释了第 3 章为什么要在 End.X 上带 `Alg:` 字段（图 3-21）：**同一个物理接口，每个算法有自己的邻接段**，备份路径要引用"本算法的那一个"。

:::en
Similar to how the primary paths to different locators of the same node vary based on the algorithm, the backup paths also differ with each algorithm. Figure 4.8 shows the primary and TI-LFA backup paths from Node 5 to Algo(0) and Flex-Algo(129) locators of Node 2.
:::

正如同一节点不同 locator 的主路径因算法而异，**备份路径也随算法不同**。图 4.8（下方图 4-8）给出节点 5 到节点 2 的 Algo(0) 与 Flex-Algo(129) locator 的主/备路径。

{{FIG|04/fig-4-10-primary-backup|图 4-8 · 矢量版|两套算法下节点 5 到节点 2 的主/备路径，修复列表只用本算法的 P/Q 段。}}

```asciifig
    图 4-8：原书 Figure 4.8 —— 节点 5 到节点 2：两套算法、两条主路径、两条备份路径

   ① 到 Algo(0) locator  fc00:0:2::/48
        主： 5 ──10── 3 ──10── 2                代价 20
        备： 5 ──10── 4 ──20── 2                代价 30   ← LFA（邻居 4 自己就能到 2）

   ② 到 Flex-Algo(129) locator  fc00:2:2::/48（排除 RED 链路 5-3）
        主： 5 ──10── 4 ──20── 2                代价 30   ← 主路径必须绕开 RED
        备： 5 ──10── 6 ──10── 1 ──40── 2       ← TI-LFA，首跳 R6
                     │
                     └ 备份路径里的段必须是 alg 129 的：
                       P 节点 R1 的 uN   fc00:2:1::
                       Q 节点 R1→R2 邻接 fc00:2:1:e000::

   要点：同一个"去节点 2"，Algo(0) 的主是 129 的备的邻居，
        两条算法各算各的，互不复用——因为约束不同。
```

*图 4-8：两套算法下节点 5 到节点 2 的主/备路径（按原书 Figure 4.8 重绘，度量见表 4-1）*

:::en
In Cisco IOS XR, when SRv6 TI-LFA is configured on an IS-IS adjacency (see Chapter 3), the capability is automatically enabled for all Flex-Algos. As a result, the node computes and installs a backup path for all Flex-Algo locators routed through this adjacency like it does for the Algo(0) locators.
:::

IOS XR 里只要在 IS-IS 邻接上配了 SRv6 TI-LFA（第 3 章），该能力就**自动对所有 Flex-Algo 生效**。于是节点会为所有经过该邻接的算法 locator **都算并装备份路径**，与 Algo(0) 一样。

**这意味着"开 TI-LFA"是一个算法无关的全局动作**：不对某算法单独配置，它就有备份；想没有，得显式关（4.7.1）。

**例 4.15：节点 5 上 Algo(0) locator 的 IS-IS 备份路径**

```text
RP/0/RP0/CPU0:R5# show isis ipv6 fast-reroute fc00:0:2::/48
L1 fc00:0:2::/48 [21/115]
     via fe80::5054:ff:fe1f:84ae, GigabitEthernet0/0/0/2, R3, Weight: 0
       Backup path: LFA, via fe80::5054:ff:fe11:efc4, GigabitEthernet0/0/0/1, R4, Weight: 0, Metric: 31
```

**例 4.16：节点 5 上 Flex-Algo(129) locator 的 IS-IS 备份路径**

```text
RP/0/RP0/CPU0:R5# show isis ipv6 fast-reroute flex-algo 129 fc00:2:2::/48
L1 fc00:2:2::/48 [30/115]
     via fe80::5054:ff:fe11:efc4, GigabitEthernet0/0/0/1, R4, Weight: 0
       Backup path: TI-LFA (link), via fe80::5054:ff:fe07:bb74, GigabitEthernet0/0/0/0 R6, Weight: 0, Metric: 120
         P node: R1.00 [fc00:0:1::1], SRv6 SID: fc00:2:1:: uN (PSP/USD)
         Q node: R2.00 [fc00:0:2::1], SRv6 SID: fc00:2:1:e000:: uA (PSP/USD)
         Backup-src: R2.00
```

两条输出对照着看，信息量很大：

| 观察点 | 例 4.15（Algo 0） | 例 4.16（Flex-Algo 129） |
|---|---|---|
| 命令 | `show isis ipv6 fast-reroute <prefix>` | **必须加 `flex-algo 129`**，否则查的是 Algo(0) |
| 主路径下一跳 | 经 **R3**（5→3→2） | 经 **R4**（5→4→2）：避开了 RED 链路 |
| 备份类型 | **LFA**（邻居自己就有最短路径） | **TI-LFA (link)**（邻居的最短路径不满足约束，要补段列表） |
| 备份首跳 | R4 | **R6** |
| 备份代价 | 31 | 120（绕行代价显著） |
| P/Q 节点 | 无 | **P=R1（uN `fc00:2:1::`）、Q=R2（uA `fc00:2:1:e000::`）**，全是 **alg 129** 的 SID |

最后一行是本章的技术制高点：**备份路径里的 P 节点用 `fc00:2:1::`（alg 128 的邻居也有类似 SID，但这里必须是 129 的）**，Q 节点用 **R1 到 R2 的 129 邻接段**。这就是"SR-MPLS 做不到、SRv6 因为邻接段带算法才做到"的地方。

`Backup-src: R2.00` 是 IOS XR 的输出习惯：指出该备份路径对应的**收敛后上游节点**，方便核对"我算的修复路径和邻居收敛后的路径是否一致"。

:::en
The IS-IS process also automatically instantiates a protected counterpart for each local Flex-Algo adjacency segment. In the show command output of Example 4.17, the protected adjacency segments are indicated with the decorator P at the end of the Context column.
:::

IS-IS 进程还会为**每个本地 Flex-Algo 邻接段**自动实例化一个**受保护（protected）的对偶**。在例 4.17 的输出里，受保护的邻接段在 `Context` 列末尾带 **`P`** 标记。

**例 4.17：节点 5 上的段列表，含受保护的 Flex-Algo 邻接段**

```text
RP/0/RP0/CPU0:R5# show segment-routing srv6 sid
*** Locator: 'MAIN' ***
SID                Behavior      Context                        Owner    State  RW
-----------------  ------------  -----------------------------  -------  -----  --
fc00:0:5::         uN (PSP/USD)  'default':5                    sidmgr   InUse  Y
fc00:0:5:e000::    uA (PSP/USD)  [Gi0/0/0/1, Link-Local]:0:P    isis-1   InUse  Y
fc00:0:5:e001::    uA (PSP/USD)  [Gi0/0/0/1, Link-Local]:0      isis-1   InUse  Y
fc00:0:5:e002::    uA (PSP/USD)  [Gi0/0/0/2, Link-Local]:0:P    isis-1   InUse  Y
fc00:0:5:e003::    uA (PSP/USD)  [Gi0/0/0/2, Link-Local]:0      isis-1   InUse  Y
fc00:0:5:e004::    uA (PSP/USD)  [Gi0/0/0/0, Link-Local]:0:P    isis-1   InUse  Y
fc00:0:5:e005::    uA (PSP/USD)  [Gi0/0/0/0, Link-Local]:0      isis-1   InUse  Y
*** Locator: 'DELAY' ***
fc00:1:5::         uN (PSP/USD)  'default':5                    sidmgr   InUse  Y
fc00:1:5:e000::    uA (PSP/USD)  [Gi0/0/0/1, Link-Local]:128:P  isis-1   InUse  Y
fc00:1:5:e001::    uA (PSP/USD)  [Gi0/0/0/1, Link-Local]:128    isis-1   InUse  Y
fc00:1:5:e002::    uA (PSP/USD)  [Gi0/0/0/2, Link-Local]:128:P  isis-1   InUse  Y
fc00:1:5:e003::    uA (PSP/USD)  [Gi0/0/0/2, Link-Local]:128    isis-1   InUse  Y
fc00:1:5:e004::    uA (PSP/USD)  [Gi0/0/0/0, Link-Local]:128:P  isis-1   InUse  Y
fc00:1:5:e005::    uA (PSP/USD)  [Gi0/0/0/0, Link-Local]:128    isis-1   InUse  Y
*** Locator: 'RELIABLE' ***
fc00:2:5::         uN (PSP/USD)  'default':5                    sidmgr   InUse  Y
fc00:2:5:e000::    uA (PSP/USD)  [Gi0/0/0/1, Link-Local]:129:P  isis-1   InUse  Y
fc00:2:5:e001::    uA (PSP/USD)  [Gi0/0/0/1, Link-Local]:129    isis-1   InUse  Y
fc00:2:5:e002::    uA (PSP/USD)  [Gi0/0/0/2, Link-Local]:129:P  isis-1   InUse  Y
fc00:2:5:e003::    uA (PSP/USD)  [Gi0/0/0/2, Link-Local]:129    isis-1   InUse  Y
fc00:2:5:e004::    uA (PSP/USD)  [Gi0/0/0/0, Link-Local]:129:P  isis-1   InUse  Y
fc00:2:5:e005::    uA (PSP/USD)  [Gi0/0/0/0, Link-Local]:129    isis-1   InUse  Y
```

**每个接口成对出现**：带 `P` 的是**受保护版**（走它意味着"我已经准备好，一旦链路故障立即改用修复路径"），不带 `P` 的是**普通版**。段数因此翻倍 —— 这是 Flex-Algo + TI-LFA 的**转发表代价**，规划时不能忽略。

:::en
Similar to the Flex-Algo locators, the repair path of each Flex-Algo adjacency segment complies with the corresponding Flex-Algo definition. For example, the repair path for the Flex-Algo(129) Adjacency-SID fc00:2:5:e000:: associated with the link from Node 5 to Node 4 avoids the RED link between Node 3 and Node 5 by going via Node 2, as shown in Example 4.18. Figure 4.9 compares the primary and backup paths of Flex-Algo(129) Adjacency-SID fc00:2:5:e000:: with those of its Algo(0) counterpart fc00:0:5:e000::.
:::

与 locator 一样，**Flex-Algo 邻接段的修复路径也遵守该算法的定义**。例如 Flex-Algo(129) 邻接段 `fc00:2:5:e000::`（对应节点 5 → 节点 4 的链路），其修复路径**避开节点 3 与节点 5 之间的 RED 链路，改经节点 2**（例 4.18）。图 4.9 对比该段与 Algo(0) 版本 `fc00:0:5:e000::` 的主/备路径。

```text
    图 4-9：原书 Figure 4.9 —— 邻接段"5→4"在 Algo(0) 与 Flex-Algo(129) 下的主/备

   ① Algo(0) 邻接段 fc00:0:5:e000::（硬绑 5-4 链路）
        主： 5 ══► 4                            直接出接口
        备： 5 ── 3 ── 4                        经 3 绕到 4（3-5 是 RED，但 algo 0 不在乎）

   ② Flex-Algo(129) 邻接段 fc00:2:5:e000::（同样硬绑 5-4 链路）
        主： 5 ══► 4
        备： 5 ── 6 ── 1 ── 2 ── 4              ✗ 不能走 3：5-3 是 RED
             Repair Node(s): fc00:0:2::1, fc00:0:4::1（R2、R4）

   注意"段的语义不变、修复路径不同"：
        两个段都是"从 5 的某个口出去到 4"，但 algo 129 的备份要绕得远得多。
```

*图 4-9：同一邻接段在两套算法下的主/备路径（按原书 Figure 4.9 重绘，修复节点见例 4.18）*

**例 4.18：Flex-Algo(129) 邻接段 `fc00:2:5:e000::` 的主/备路由**

```text
RP/0/RP0/CPU0:R5# show route ipv6 fc00:2:5:e000::
Routing entry for fc00:2:5:e000::/80
  Known via "local-srv6 isis-1", distance 0, metric 0, SRv6 Endpoint uA (PSP/USD), SRv6 Format f3216
  Installed Oct 23 09:29:31.197 for 00:02:47
  Routing Descriptor Blocks
    fe80::5054:ff:fe14:3546 directly connected, via GigabitEthernet0/0/0/0, Backup (TI-LFA)
      Repair Node(s): fc00:0:2::1, fc00:0:4::1
      Route metric is 0
    fe80::5054:ff:fe10:e002 directly connected, via GigabitEthernet0/0/0/1, Protected
      Route metric is 0
  No advertising protos.
```

读法：**一个 /80 条目、两个 RDB** —— `Protected` 是主用（直连出接口），`Backup (TI-LFA)` 是修复。`Repair Node(s)` 列出修复列表里的中继节点（R2、R4），`SRv6 Format f3216` 说明它是 **uSID 压缩格式**（32/16/16/64，见第 2 章）。

注意 `/80`：邻接段按 **locator(48) + function(16) + 32 = 80** 的粒度装表（uA 的 Func-Length 是 16，见例 4.13），这是 uSID 下邻接段的常见前缀长度。

{{FIG|04/fig-4-11-adj-protect|邻接段保护 · 矢量版|每个 Flex-Algo 邻接段都有一个带 P 标记的受保护对偶，供 TI-LFA 修复路径引用。}}

### 4.7.1 关掉某个算法的 TI-LFA

:::en
Cisco IOS XR supports disabling TI-LFA fast reroute for a specific flexible algorithm with the CLI shown in Example 4.19.
:::

IOS XR 支持**按算法**关闭 TI-LFA 快速重路由（例 4.19）。

**例 4.19：关闭 Flex-Algo(129) 的快速重路由**

```text
router isis 1
 flex-algo 129
  fast-reroute disable
```

:::en
In this example, we are disabling fast reroute capabilities for Flex-Algo(129). This instructs the IS-IS process to stop computing fast reroute backup paths for the Flex-Algo(129) locators and allocating protected adjacency segments for this algorithm. We can confirm that fast reroute is correctly disabled by inspecting the protection of one of the Flex-Algo(129) locators, as shown in Example 4.20.
:::

这会指示 IS-IS **停止为 Flex-Algo(129) 的 locator 计算备份路径**，也**不再为该算法分配受保护的邻接段**。可用例 4.20 确认已关闭。

**例 4.20：关闭后节点 5 上 Flex-Algo(129) locator 的 IS-IS 备份状态**

```text
RP/0/RP0/CPU0:R5# show isis ipv6 fast-reroute flex-algo 129 fc00:2:2::/48
L2 fc00:2:2::/48 [31/115]
     via fe80::5054:ff:fe17:6d75, GigabitEthernet0/0/0/1, R4, Weight: 0
       No FRR backup
```

:::en
"No FRR backup" in this output shows that fast reroute is inactive for the Flex-Algo(129) locator of Node 2.
:::

输出里的 **`No FRR backup`** 说明 Flex-Algo(129) 到节点 2 的 locator 已经**没有快速重路由**了。

| 场景 | 是否该关某个算法的 FRR |
|---|---|
| 算法承载的是**尽力而为**流量（可接受秒级中断） | 可关，省一半邻接段与 CPU |
| 算法承载 **uRLLC / 金融** | **绝不关**，恰恰要靠它保住时延与可用性 |
| 平台转发表容量吃紧（邻接段翻倍后装不下） | 可对**最不关键**的算法关，并写进变更评审 |
| 双平面设计（另一平面天然备份） | 可关，跨平面已是备份 |

## 4.8 小结

:::en
In this chapter, we explored how SRv6 locators are associated with IGP algorithms, enabling different forwarding paths across the network. We presented the concept of Flex-Algos, which allow operators to define custom routing behaviors tailored to specific network needs.
:::

本章讲了 **SRv6 locator 如何与 IGP 算法绑定**，从而在全网提供不同的转发路径；并给出了 **Flex-Algo** 的概念 —— 让运营商按需定义自己的路由行为。

:::en
Flex-Algos can optimize paths by minimizing alternative metrics such as link delay or by avoiding certain links, offering more control and flexibility than the default IGP algorithm.
:::

Flex-Algo 能通过**最小化链路时延等替代度量**、或**避开特定链路**来优化路径，比默认 IGP 算法提供更多控制与灵活性。

:::en
We discussed the configuration of Flex-Algos within an SRv6 network and emphasized the importance of Flex-Algo definition consistency within the IGP domain.
:::

也讨论了 SRv6 网内 Flex-Algo 的配置，并强调**域内定义一致性**的重要性。

:::en
Finally, we examined how SRv6 TI-LFA enhances resiliency for Flex-Algo paths by providing repair paths that fully respect Flex-Algo constraints. A key innovation in SRv6 is the introduction of Flex-Algo adjacency segments, enabling Flex-Algo-specific protection for both prefix and adjacency segments, which was not possible with SR-MPLS.
:::

最后讲了 **SRv6 TI-LFA 如何增强 Flex-Algo 路径的韧性**：提供的修复路径**完全遵守 Flex-Algo 约束**。SRv6 的一个关键创新是引入了 **Flex-Algo 邻接段**，使**前缀段与邻接段都能获得"算法专属"的保护** —— 这在 SR-MPLS 里做不到。

把本章压成一张对照表：

| 维度 | Algo(0) | Flex-Algo(K) |
|---|---|---|
| 算法号 | 0（默认，永远参与） | 128–255，域内自定义 |
| 计算类型 | SPF | SPF（唯一可选） |
| 优化度量 | IGP metric | IGP metric / link delay / TE metric |
| 约束 | 无 | SRLG、亲和色的四类规则 |
| locator | 一个（如 `fc00:0:3::/48`） | **每算法再一个**（如 `fc00:1:3::/48`） |
| 邻接段 | End.X，无算法属性 | End.X 带 `Alg:K`，**每算法一套** |
| 定义 | 不存在 | FAD TLV，需泛洪，需选主一致 |
| 参与 | 强制 | 显式通告，不同版本/能力节点会被排除 |
| TI-LFA | 有 | 有，且**在本算法内**算，邻接段也有保护版 |
| 故障失效模式 | 常规收敛 | **定义不一致 → 环路**；参与缺失 → 该节点退出算法 |

一句话收束：**Flex-Algo 把"路径"从一个标量（最短路）变成一族向量（每种算法一个最短路），而 locator 就是这族向量的地址化表达。**

## 实战案例

### 案例 A：双算法双 locator 上线的完整核对清单

**场景**：某省干网 18 台核心，5G 回传业务要求端到端时延 ≤ 12 ms，普通上网流量沿用最短路。方案：Algo(0) 走 `fdbb:bb00::/32`，Flex-Algo(128)（min-delay）走 `fdbb:bb01::/32`。

**地址与配置规划表**：

```text
SID block：fdbb:bb00::/32（Algo 0）  fdbb:bb01::/32（Flex-Algo 128）
LN 长度：16 bit，Function 长度：16 bit（按需），Arg：64 bit（uSID）
每台节点：2 个 locator、2 个 uN、2×接口数个 uA

节点  R1   fc00 风格     locator            uN
─────────────────────────────────────────────────────────────
 R1         0          fdbb:bb00:1::/48   fdbb:bb00:1::
 R1         128        fdbb:bb01:1::/48   fdbb:bb01:1::
 ...（每台节点同理，Node-ID 递增）
─────────────────────────────────────────────────────────────
度量：全链路开动态时延测量；微波/卫星链路打 MICRO 亲和，
      在 algo 128 中用 include-any FIBER 排除
```

**节点侧配置**（每台一致，仅编号变）：

```text
segment-routing
 srv6
  locators
   locator MAIN
    micro-segment behavior unode psp-usd
    prefix fdbb:bb00:1::/48
   !
   locator DELAY
    micro-segment behavior unode psp-usd
    prefix fdbb:bb01:1::/48
    algorithm 128
!
router isis 1
 affinity-map FIBER bit-position 0
 affinity-map MICRO bit-position 1
 flex-algo 128
  metric-type delay
  priority 200
  advertise-definition
  affinity include-any FIBER
 !
 address-family ipv6 unicast
  metric-style wide
  segment-routing srv6
   locator MAIN
   locator DELAY
```

**上线核对五步**（按顺序做，每步都有明确通过标准）：

| 步骤 | 命令 | 通过标准 |
|---|---|---|
| 1. locator 建好 | `show segment-routing srv6 locator` | 两个 locator 都 `Up`，`Algo` 分别为 0 / 128 |
| 2. 段实例化完整 | `show segment-routing srv6 sid all` | `DELAY` 下有 **uN + 每个接口一个 uA**；缺 uA 就是没参与 |
| 3. 定义已泛洪 | `show isis database verbose \| include -A3 "Flex-Algo Definition"` | 全区域**至少两台**通告，`Metric-Type: 1`、`Priority` 一致 |
| 4. 参与名单完整 | `show isis database verbose <每台>` | `SR Algorithm` 里都有 **128**；少一台就是拓扑缺块 |
| 5. 路径真低时延 | `show isis route flex-algo 128 fdbb:bb01:<peer>::/48` + `traceroute` | 主路径与你设计的低时延拓扑一致；`ping` 测出时延达标 |

**踩坑记录（真实类型）**：

| 现象 | 根因 | 证据 |
|---|---|---|
| 时延业务某些方向绕远 | 只在一个方向打了 `affinity include-any FIBER`，反方向链路没打 → 被剪 | `show isis database verbose` 对比两端接口的 ASLA |
| 某台节点在 algo 128 下完全不可达 | 该节点版本不支持 `metric-type delay`，**退出参与** | 该节点 `SR Algorithm` 里没有 128 |
| 全网 algo 128 时通时不通 | 两台节点 `Priority` 相同、定义内容不同（一台 `metric-type delay`，一台默认 IGP） | `show isis database verbose` 里两条 FAD 的 Priority 都是 200，内容不同 |
| 上线后核心某些链路打满 | 低时延路径集中到"平时备用的直达链路"，容量没扩容 | 各算法独立做容量规划；`show interface` 按 algo 128 路径逐跳看 |

### 案例 B：定义不一致引起的转发环路——一次 40 分钟的排障

**现象**：新增 Flex-Algo(129)（"排除 RED 链路"）后，某两个区域之间的业务出现**间歇性环路**（TTL 快速耗尽、`traceroute` 看到两跳互指），普通 Algo(0) 业务完全正常。

**排查顺序**（照着做，10 分钟内定位）：

```text
① 看定义通告：谁在通告、内容是否一致
   show isis database verbose | include -A4 "Flex-Algo Definition"
   → 发现 R7 通告的两份 129 定义 Priority 都是 50，
     一份 Metric-Type 0（IGP），一份 Metric-Type 1（delay）

② 看选举结果：各节点选中的是哪份
   show isis flex-algo 129
   → R1–R6 选了 delay 版，R7 自己选 IGP 版（本地定义优先于学来的同优先级）

③ 看参与是否仍成立
   show isis database verbose R7 | include -A6 "SR Algorithm"
   → R7 仍通告 129（它支持自己那份），于是它在两套树的交界处

④ 结论：R7 用 IGP 度量算 129 的 SPF，其他节点用时延算 →
   对同一目的地的"下一跳"判断相反 → 环路
```

**根因**：`Priority` 相同、定义内容不同。选主规则靠 **System-ID 比大小**，而**本地定义在选举中同等对待** —— 结果 R7 保留了自己的版本，形成两套树。

**修复**：

```text
! 在两台权威节点上显式给高优先级，其余节点只参与不定义
router isis 1
 flex-algo 129
  priority 250
  metric-type delay      ! 内容必须完全相同
  exclude-any RED
  advertise-definition
```

```text
! 其余节点删除本地定义，只留参与
router isis 1
 flex-algo 129
```

**经验三条**：

1. **定义只配在 1–2 台"权威节点"上，其余节点只写空参与**（`flex-algo 129` 一行）。这比"全网配同一份"更不容易出错。
2. **`priority` 必须显式指定且全局唯一**，不要依赖默认值 128 靠 System-ID 决出。
3. **定义一致性巡检要进日常**：定期 diff 全网 `Flex-Algo Definition` 的 `Metric-Type`/`Alg-type`/约束位图，三处一致才算健康。

### 案例 C：Flex-Algo 备份路径把带宽吃掉了

**场景**：Flex-Algo(129) 上线后，故障演练时发现：链路 5-4 断开后，129 的备份路径走 5→6→1→2→4，绕行后**在 1-2 链路上与时延业务叠加，出现拥塞**。

**原因**：备份路径的代价（例 4.16 里的 `Metric: 120`）远高于主路径（30），且**没有任何带宽约束** —— Flex-Algo 的约束是**拓扑约束**（哪些链路可用），不是**容量约束**（还剩多少带宽）。

| 想做的事 | Flex-Algo 能做吗 | 该用什么 |
|---|---|---|
| 只走某些链路 | ✅ 亲和 / SRLG | Flex-Algo |
| 最小化某度量 | ✅ IGP / delay / TE metric | Flex-Algo |
| 保证带宽、限制占用率 | ❌ | **SR Policy + 带宽约束/局部拥塞感知** |
| 指定精确路径 | ❌（只能"改度量/改拓扑"） | **SR Policy + 显式段列表** |
| 故障后自动跟随 | ✅ IGP 收敛 + TI-LFA | Flex-Algo |

**做法**：

1. 备份路径经过的链路（1-2、2-4）按"主 + 备 + 时延业务"三重流量做容量预留；
2. 对时延业务的关键平面做**双平面分离**（4.6 节末），避免主备同沟；
3. 若必须保证带宽，叠加 **SR Policy**，让控制器在算法路径之上做容量约束。

**一句话**：**Flex-Algo 解决"走哪条路"，不解决"这条路还剩多少带宽"。** 前者是 IGP 的事，后者是 TE 的事。

## 延伸阅读

- **RFC 9350（IGP Flexible Algorithm）**：本章的规范本体 —— FAD TLV、四种约束、定义选举流程、参与规则。
- **RFC 8919 / RFC 8920**：IS-IS / OSPF 的 ASLA。第 4.6 节"哪些属性参与计算"的出处，排障时最常翻。
- **RFC 8667 / RFC 8665 / RFC 9085**：IS-IS / OSPF / BGP-LS 的 SR 扩展 —— SR-Algorithm TLV（图 4-5）与 Router Capability 的字节格式。
- **RFC 9352 / RFC 9513**：第 3 章已用到的 SRv6 Locator TLV 与 End.X 的 `Algorithm` 字段，本章的"载体"。
- **RFC 7471 / RFC 8570**：IS-IS / OSPF 的 TE 度量扩展（含链路时延），`metric-type delay` 的数据来源。
- **《Segment Routing: Part II》第 7 章**：Flex-Algo 的完整推导（含 SR-MPLS 视角、双平面设计、微环避免）。
- 交叉参考：第 3 章（locator 与 End/End.X）、第 5 章（多区域下算法 locator 的泄露与汇总）、第 6 章（用 BGP Color 把业务映射到算法 SID）、第 10 章（多算法 locator 的地址规划）。

