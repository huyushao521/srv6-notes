# 05 · IS-IS 中 Locator 的泄露、重分发与汇总

> **本章定位**：原书第 5 章《IS-IS Locator Leaking, Redistribution, and Summarization》。本版按原书段落顺序**逐段对照**：灰色英文块是原文摘录（保留原句与术语），紧随其后的中文是该段完整翻译，必要时补一段工程注解。书中的 Figure 5.1–5.6 按原文描述用 ASCII 重绘，图注标明来源。配置与命令输出来自原书 Example 5.1–5.12，按 IOS XR 风格保留。

**本章要拿到的东西**（原书章首列表）：

| 问题 | 对应小节 |
|---|---|
| 为什么单区域能通、多区域就不通 | 5.1 |
| Locator 如何从 Level-2 泄露进 Level-1，环路怎么防 | 5.2 |
| 多 IGP 实例（CORE / METRO）之间怎么交换 SID 可达性 | 5.3 |
| 一个 /40 覆盖 256 台节点：汇总怎么做、代价是什么 | 5.4 |
| 汇总 + Flex-Algo + TI-LFA 三者同时存在时的坑 | 5.5 |
| 跨区"能 ping 通 PE 却不通信"的排障路径 | 5.6 |

前三章解决的是"**一台节点**怎么被寻址"（locator、End/End.X、TI-LFA、Flex-Algo）。本章解决的是"**一个域**怎么被寻址"——locator 出了本区域还能不能被路由到。这是现网跨区故障里占比最高的一类，也是最容易被"默认路由掩盖"的一类。

## 5.0 本章拓扑

原书用一个两级结构：三个 Level-1 区域挂在一个 Level-2 骨干上，每个区域内有 PE 与 P 节点。本章所有图与算例都基于这张拓扑：

```text
图 5-1：本章拓扑（原书 Figure 5.1 重绘）

      Area 49.0001            L2 骨干（全部 L1/L2 与 L2-only）           Area 49.0003
  ┌──────────────────┐                                      ┌──────────────────────┐
  │  PE-1            │                                      │             PE-3     │
  │  fc00:0:1::/48   │                                      │      fc00:0:3::/48   │
  │      │           │                                      │                │     │
  │  P-11            │                                      │             P-31     │
  └──────┼───────────┘                                      └────────────────┼─────┘
         │                                                                   │
      ABR-2 ─────────────── ABR-4 ────────────── ABR-5 ──────────────────── ABR-6
   fc00:0:2::/48        fc00:0:4::/48         fc00:0:5::/48          fc00:0:6::/48
         │                    │                     │                       │
  ┌──────┴───────────┐  ┌─────┴──────────────┐                        │
  │  P-12            │  │  P-41              │                        │
  │  PE-9  fc00:0:9::/48                    │                        │
  └──────────────────┘  └────────────────────┘                        │
      Area 49.0002（内含 PE-9）                           Area 49.0003 内的 PE-7
                                                        fc00:0:7::/48
```

关键事实先摆出来：

| 节点 | 角色 | 位置 | 默认能看到谁 |
|---|---|---|---|
| PE-1 | L1-only | Area 49.0001 | 只本区 + 指向 ABR-2 的**默认路由** |
| ABR-2 | L1/L2 | 49.0001 与骨干 | 全网的 L2 明细 |
| ABR-4、ABR-5 | L2-only | 骨干 | 全网的 L2 明细 |
| PE-7 | L1-only | Area 49.0003 | 只本区 + 默认路由 |

注意 PE-1 和 PE-7 都是 **L1-only**——它们没有任何 L2 明细。这一点决定了本章的全部问题：**PE-1 想用 SRv6 封装去 PE-7，外层目的地是 `fc00:0:7::`，而 PE-1 的路由表里根本没有这条前缀，只有一条 `::/0`。**

## 5.1 默认路由为什么救不了 SRv6

:::en
IS-IS is a two-level routing protocol. Level-1 routers exchange routing information only with the routers in their own area and use the closest Level-1/Level-2 router to reach destinations outside the area. Level-2 routers form the backbone: they know the topology of the backbone as well as all the prefixes of all areas, and they forward traffic between areas.
:::

IS-IS 是**两级**路由协议。Level-1 路由器只与本区域的节点交换路由信息，出区靠**最近的 L1/L2 路由器**；Level-2 路由器构成骨干——它们既知道骨干拓扑，也知道**所有区域的所有前缀**，并负责区域间转发。

:::en
In a classic IP network, the Level-1-only router does not need any detail about remote prefixes: it installs a default route towards its nearest Level-1/Level-2 router, indicated by the Attached bit (ATT) in the Level-1 LSP of that router, and lets the backbone handle the rest.
:::

传统 IP 网络里，L1-only 路由器**不需要远端明细**：它靠最近 L1/L2 路由器 L1 LSP 里的 **ATT 位（Attached bit）** 装一条默认路由，其余的交给骨干。

:::en
This mechanism is also sufficient to reach a remote SRv6 locator, because the locator is just an IPv6 prefix. However, it is not sufficient to reach it along the path that the operator intended: every packet leaves the area through the nearest border router, regardless of which border router provides the best path to the destination locator, and regardless of the IGP algorithm associated with that locator.
:::

这条机制**对"能不能到"是够的**——locator 就是个 IPv6 前缀，默认路由照样能把它送出区。但**对"到不到得对"不够**：

1. 所有报文都从**最近的**边界路由器出区，不管哪台 ABR 到目的 locator 的路径更优；
2. 算法属性（第 4 章的 Flex-Algo）在这一跳**完全丢失**——默认路由只有 Algo(0)。

把两种做法摆在一起看：

| 维度 | 只靠 ATT 默认路由 | 泄露 L2 明细进 L1 |
|---|---|---|
| 可达性 | 有（`::/0` → ABR） | 有（每条 locator 一个条目） |
| 出口选择 | **固定为最近 ABR** | 按目的前缀选**最优 ABR** |
| 跨区路径是否最优 | 否（次优，可能绕行整个骨干） | 是 |
| Flex-Algo locator | **不可用**（默认路由无算法属性） | 可用（明细路由带算法） |
| TI-LFA 修复 | 只能在默认路由上做 | 可对每条 locator 独立做 |
| 路由表规模 | 1 条 | = 全网 locator 数（这才是问题） |

所以本章的整个设计张力是：**明细路由带来正确性与算法能力，也带来规模；汇总与策略是唯一的解法。**

工程上先记住一句话：**默认路由让 SRv6 "能通"，泄露让 SRv6 "通得对"。**

## 5.2 Locator 泄露：把 L2 的 locator 送进 L1

:::en
Locator leaking consists of advertising the locators of remote areas from Level-2 into Level-1. The border routers inject the Level-2 locator prefixes into their Level-1 area, so that the Level-1-only routers can compute a shortest path to each remote locator and select the border router that provides the best path, rather than the closest one.
:::

**Locator 泄露就是把远端区域的 locator 从 Level-2 通告进 Level-1。** 边界路由器把 L2 的 locator 前缀注入自己的 L1 区域，于是 L1-only 路由器能对**每条远端 locator**分别算最短路、选出**最优**边界路由器，而不是**最近**的那台。

:::en
Leaking is not limited to SRv6: it is a generic IS-IS mechanism. What is specific to SRv6 is the scale and the granularity: an operator typically leaks only the locator aggregate of each area, never the customer prefixes, because customer reachability is carried by BGP and must stay in BGP.
:::

泄露本身**不是 SRv6 专有**机制，它是 IS-IS 的通用能力。SRv6 的特异之处在**规模与粒度**：运营商只泄露**每个区域的 locator 聚合**，绝不泄露客户前缀——客户可达性由 BGP 承载，必须留在 BGP 里。

这条纪律是刚性的。泄漏客户路由进 IGP 的后果是：IGP 收敛被客户路由规模拖垮（IGP 是全量泛洪 + SPF 重算），而 BGP 的路由抖动会直接引发全网 SPF。

### 5.2.1 环路怎么防：up/down bit

:::en
When a prefix is leaked downwards, from Level-2 into Level-1, the router sets the up/down bit (the down bit) in the advertisement. If a router receives a leaked prefix in the up direction, that is, a prefix with the down bit set advertised from Level-1 into Level-2, it must ignore it. This rule prevents routing loops between the levels.
:::

前缀**向下泄露**（L2 → L1）时，路由器在通告中置 **up/down bit（down 位）**。如果某台路由器在**向上**方向收到带 down 位的同一条前缀（即被人又从 L1 塞回 L2），必须**忽略**。这条规则防止层级之间形成路由环路。

```text
图 5-2：down bit 的传播与"回灌即丢弃"（原书 Figure 5.2 重绘）

   ┌──────────── L2 骨干 ────────────┐
   │  ABR-2 知道 fc00:0:7::/48       │
   └───────┬─────────────────────────┘
           │ ① 泄露：L2 → L1，置 down bit
           ▼
   ┌── Area 49.0001 ─────────────────┐
   │  fc00:0:7::/48  (down bit = 1)   │  ← PE-1 学到，路由可用
   │         │                        │
   │         └─ ② 若有人把它 redistribute 回 L2 …
   └─────────────────────────────────┘
           │ ③ L1 → L2，down bit 仍为 1
           ▼
   ┌──────────── L2 骨干 ────────────┐
   │  ABR-4 收到：down bit = 1 且来自 L1
   │  → 规则要求「忽略」，否则形成
   │    L2 ↔ L1 ↔ L2 的三跳环路
   └─────────────────────────────────┘
```

反过来，**向上泄露**（L1 → L2）**不置** down 位——它表达的是"这个区域的 locator 从这里可以到达"，骨干需要这份信息。这就是为什么泄露必须**双向都要配**：

| 方向 | 目的 | down bit | 典型范围 |
|---|---|---|---|
| L2 → L1 | 区内节点能到远端 locator，且能选最优出口 | **置 1** | 全网 locator 聚合（可汇总） |
| L1 → L2 | 骨干能到**本区域**的 locator | 不置 | 仅本区域 locator |

只配一个方向的后果很具体：只配 L2→L1，区内能出去，但**别的区域回不来**（骨干没有这条明细，只有本区域自己知道）；只配 L1→L2，骨干有明细，但**区内节点仍靠默认路由出去**，路径次优、算法失效。

### 5.2.2 配置：泄露必须收窄到 locator

:::en
In Cisco IOS XR, leaking is configured with the redistribute command under the address-family: redistribute isis <instance> level-2 into level-1, optionally qualified by a route policy. The route policy is not optional in practice: without it, every Level-2 prefix, including customer prefixes redistributed into IS-IS, would be leaked into every Level-1 area.
:::

IOS XR 里泄露用 address-family 下的 `redistribute isis <instance> level-2 into level-1`，可带 route-policy。**实际部署中策略不是可选项**：不带策略，所有 L2 前缀（包括被重分发进 IS-IS 的客户前缀）都会漏进每个 L1 区域。

**例 5.1：ABR-2 上双向泄露，且只放 locator 聚合**

```text
route-policy LOC-LEAK-L2TO1
  if destination in (SRV6-LOCATOR-AGG) then
    pass
  else
    drop
  endif
end-policy
!
route-policy LOC-LEAK-L1TO2
  if destination in (SRV6-LOCATOR-LOCAL) then
    pass
  else
    drop
  endif
end-policy
!
prefix-set SRV6-LOCATOR-AGG
  fdbb:bb00::/32 le 48
end-set
!
prefix-set SRV6-LOCATOR-LOCAL
  fdbb:bb00:0001::/48,
  fdbb:bb00:0002::/48
end-set
!
router isis 1
 address-family ipv6 unicast
  metric-style wide
  redistribute isis 1 level-2 into level-1 route-policy LOC-LEAK-L2TO1
  redistribute isis 1 level-1 into level-2 route-policy LOC-LEAK-L1TO2
```

三个细节值得单独说清：

1. **`le 48` 是关键**。locator 是 /48，但汇总路由可能是 /40 或 /32。写 `fdbb:bb00::/32 le 48` 表示"这个 /32 内所有长度 ≤ /48 的前缀"，既能放明细也能放聚合；只写 `/32` 会漏掉全部明细。
2. **`redistribute isis 1 level-2 into level-1` 是同一实例内的层级间操作**，不是实例间重分发（5.3 节）。
3. **策略里不要用 `if destination in (...)` 匹配"全部 IPv6"** 这种偷懒写法。泄露范围一旦放大，路由表规模是全网的乘法，而不是加法。

### 5.2.3 验证：三条命令分清"泄露了没有"

:::en
The leaked prefixes are visible in the Level-1 link-state database of the area, with the down bit set in the extended reachability TLV. On the router, show isis route reports the leaked prefix, and show isis database verbose shows the TLV flag that identifies it as leaked.
:::

被泄露的前缀在**本区域的 L1 链路状态库**里可见，扩展可达性 TLV 中 down 位为 1。在路由器上，`show isis route` 能看到该前缀，`show isis database verbose` 能看到标识"这是泄露来的"的 TLV 标志。

**例 5.2：PE-1 上确认远端 locator 已泄露进来**

```text
RP/0/RP0/CPU0:PE-1# show isis route fc00:0:7::/48
IS-IS 1 IPv6 Unicast Route Table
Prefix               Metric  Interface   Nexthop        Source  Stall
fc00:0:7::/48        30      Gi0/0/0/0   fe80::2 (ABR-2)  L1      No
```

**例 5.3：ABR-2 的 L1 LSP 里这条前缀的 down 位**

```text
RP/0/RP0/CPU0:ABR-2# show isis database verbose level-1 ABR-2.00-00
<...>
  Extended Reachability: 2001:db8:: (Metric: 30)
    IPv6 Interface Address: fdbb:bb00:0002::
    Prefix Attribute Flags: X:1 R:0 N:0
  <...>
```

`X:1` 就是 **down bit**（X 位在 RFC 5305 的 IPv6 扩展可达性 TLV 中承载 up/down 语义）。排障时这三个证据构成闭环：

| 现象 | 查什么 | 判据 |
|---|---|---|
| L1 节点没有远端 locator | `show isis route <locator>` | 无条目 → 泄露没配或策略 drop |
| 有路由但没 down 位 | `show isis database verbose level-1` | `X:0` → 这不是泄露来的，是本地产生的 |
| 路由在两个区域之间反复消失 | L2 侧是否又学到了带 X 位的同一前缀 | 学到且**未被忽略** → 违反 5.2.1，需查实现版本与策略 |

### 5.2.4 泄露粒度：明细、聚合，还是只靠默认路由

同样叫"泄露"，粒度可以差三个数量级。三种做法在一个 200 节点区域里的对比：

| 做法 | 区内路由表 | 出口选择 | 配置 |
|---|---|---|---|
| 只靠 ATT 默认路由 | 1 条 | 最近 ABR，固定 | 无 |
| 泄露**远端聚合**（L2 的 /40） | = 远端区域数（几十条） | 按区域选 ABR | `destination in (fdbb:bb00::/32 le 48)` 但远端只通告 /40 时自然聚合 |
| 泄露**全网明细**（每个 /48） | = 全网节点数（上千条） | 按节点选 ABR，最精确 | 同上，远端未汇总时即明细 |

原书推荐的是**中间那种**，理由是三笔账：

1. **出口精度**：聚合泄露已经能区分"去哪个区域走哪台 ABR"，这对绝大多数业务够用；只有"同一区域内选不同 ABR"才需要明细，而那件事该由区域内的 L1 拓扑解决，不该靠跨区明细。
2. **稳定性**：明细泄露意味着**远端任意一台节点增删都会引发本区 SPF 重算**；聚合泄露则只在区域级变化时才动。
3. **与汇总的配合**：如果远端已经在边界做了汇总，本区拿到的天然就是聚合，不需要额外配置——**汇总做得好，泄露自动变轻**。

规模公式可以直接拿来算账：

```text
区内 L1 路由表 ≈ 远端区域数 × 每区域聚合条数（通常 1–2，按算法分）
                （若泄露明细）= 全网节点数 × 每节点 locator 数

180 台节点 × 2 个 locator（Algo 0 + Flex-Algo） = 360 条/区域
若 60 个区域互相明细泄露 → 每个区 21,600 条 → 全网泛洪量爆炸
若按区域聚合 → 每个区 120 条 → 可控
```

最后一个常被忽略的问题：**泄露进来的路由，其 metric 是"到泄露点"的 metric，不是"端到端"的 metric**。所以区内节点选 ABR 时用的是"到 ABR 的距离"，而各 ABR 到目的地的距离差**不在比较范围内**。这是聚合泄露的本质妥协：**它按区域选出口，不按目的地选出口**。要按目的地选，就得回到明细泄露，或者用 SR Policy 显式指定。

## 5.3 多实例重分发：实例之间只换 locator

:::en
Large networks are frequently decomposed into multiple IGP instances rather than into multiple areas of a single instance. A common example is a core instance that spans the whole backbone and a set of metro instances, one per region, each with its own IGP process and its own flooding domain.
:::

大型网络经常**按实例拆分**，而不是在单个实例内按区域拆分。常见形态是：一个覆盖全骨干的 **CORE 实例**，加上每个区域一个 **METRO 实例**，各自有独立的 IGP 进程与泛洪域。

:::en
The instances are independent: they do not exchange link-state information, and the topology of one instance is invisible to the other. Reachability between instances is established by redistributing prefixes from one instance into the other, filtered by a route policy that selects only the SRv6 locators.
:::

实例之间**互相独立**：不交换链路状态，一个实例的拓扑对另一个完全不可见。跨实例可达性靠**前缀重分发**建立，用 route-policy **只挑选 SRv6 locator**。

:::en
Contrary to SR-MPLS, SRv6 does not require the distribution of any label or SID binding between the instances: the locator prefix itself is the reachability information. The node that owns the locator performs the End behavior locally, and any router that can route a packet to that prefix can use the locator's SIDs.
:::

与 SR-MPLS 的关键差别：**SRv6 不需要在实例之间分发任何标签或 SID 绑定**——**locator 前缀本身就是可达性信息**。locator 的拥有者在本地执行 End 行为，任何能把报文路由到这个前缀的路由器都能使用该 locator 下的 SID。

这一条把跨域设计简化了一大截：

| 维度 | SR-MPLS | SRv6 |
|---|---|---|
| 跨实例要分发什么 | **前缀 + 标签绑定**（SRGB 必须一致或有映射） | **只有前缀** |
| 标签/SID 冲突 | 需全局规划 SRGB，实例间易撞 | 无（SID 就是 IPv6 地址，天然唯一） |
| 重分发漏配标签 | 业务不通，且难定位 | 前缀可达即可转发 |
| 跨实例保护 | 需额外设计 | **同样丢失**（见下文） |

:::en
What is not preserved across instances is the IGP algorithm: a locator that belongs to Flex-Algo(128) is redistributed as a plain IPv6 prefix, and the receiving instance computes its shortest path with Algo(0). The destination is still reachable, but along a path that does not respect the Flex-Algo constraints.
:::

**跨实例会丢的是算法属性**：属于 Flex-Algo(128) 的 locator 被当作普通 IPv6 前缀重分发出去，接收方按 **Algo(0)** 算最短路。目的地**仍然可达**，但走的路径**不再遵守 Flex-Algo 约束**。

这是 Flex-Algo 跨域部署的硬边界，值得单独记住：

| 跨越什么 | 算法属性 | 结果 |
|---|---|---|
| 同一实例的不同 level（泄露） | 保留 | 区内可走算法路径（代价是明细规模） |
| 不同实例（重分发） | **丢失** | 退化为 Algo(0) 路径 |
| 不同 AS（BGP 承载 locator） | **丢失** | 退化为 Algo(0) 路径 |

**例 5.4：ABR-2 上把 CORE 实例的 locator 重分发进 METRO 实例（双向）**

```text
route-policy LOC-ONLY
  if destination in (SRV6-LOCATOR-AGG) then
    pass
  else
    drop
  endif
end-policy
!
router isis METRO
 address-family ipv6 unicast
  metric-style wide
  redistribute isis CORE level-2 into level-2 route-policy LOC-ONLY
!
router isis CORE
 address-family ipv6 unicast
  metric-style wide
  redistribute isis METRO level-2 into level-2 route-policy LOC-ONLY
```

两个实例**都要配**，方向各一。这里没有 down bit 兜底——**实例之间没有层级语义，就没有 up/down 保护**，防环只能靠"只重分发 locator + 精确前缀集"。

:::en
Redistribution between instances is a more dangerous operation than leaking between levels, because there is no implicit loop prevention mechanism. A policy that redistributes prefixes in both directions without a precise filter can create a feedback loop between the instances, with prefixes oscillating and the SPF recomputation rate climbing until the network becomes unstable.
:::

**实例间重分发比层级间泄露更危险，因为它没有隐式防环机制。** 双向重分发若策略不够精确，会造成实例间的前缀"反馈循环"：前缀互相注入、反复撤销，SPF 重算频率飙升，最终全网震荡。

三重防护是标准做法：

1. **前缀集精确到 locator 块**（`fdbb:bb00::/32 le 48`），绝不使用 `::/0` 或宽泛的 `le 64`；
2. **两个方向用同一个 prefix-set**，避免一侧宽一侧窄导致单向回路；
3. **监测重分发计数**：`show isis statistics` 的重分发计数若持续增长，就是反馈环的第一信号。

**例 5.5：确认重分发生效且只有 locator**

```text
RP/0/RP0/CPU0:PE-1# show isis route
IS-IS METRO IPv6 Unicast Route Table
Prefix               Metric  Interface   Nexthop        Source  Stall
fdbb:bb00:0002::/48  20      Gi0/0/0/0   fe80::2 (ABR-2) redist  No
fdbb:bb00:0007::/48  30      Gi0/0/0/0   fe80::2 (ABR-2) redist  No
fdbb:bb00:0009::/48  30      Gi0/0/0/0   fe80::2 (ABR-2) redist  No
```

`Source` 列是 `redist`，说明这几条不是本实例的链路状态算出来的，而是重分发来的。**如果这一列里出现客户前缀（如 `2001:db8:100::/48`），说明策略写错了，必须立刻收窄。**

## 5.4 汇总：SRv6 相对 MPLS 的结构性红利

:::en
Summarization is where SRv6 pays off compared to MPLS. Because SIDs are IPv6 prefixes, the locators of an area can be summarized into a single aggregate: 256 /48 locators fit into a single /40, a 256-to-1 reduction, and 65,536 /48 locators fit into a single /32.
:::

汇总正是 SRv6 相对 MPLS 的**结构性红利**。因为 SID 本质是 IPv6 前缀，一个区域的所有 locator 可以汇总成一条聚合路由：**256 个 /48 装进一个 /40，压缩比 256:1**；65,536 个 /48 装进一个 /32。

:::en
MPLS has no equivalent capability: a label space cannot be summarized, because labels are locally significant identifiers without hierarchical structure. This is one of the main reasons why the routing table of a large MPLS network grows linearly with the number of nodes, while an SRv6 network can keep it flat.
:::

MPLS **没有对应能力**：标签空间不可汇总——标签是本地有效标识，**没有层级结构**。这正是大型 MPLS 网路由表随节点数**线性增长**，而 SRv6 网可以做到**平坦**的主要原因之一。

数字摆出来更直观：

| 网络规模 | MPLS 核心路由表 | SRv6 汇总后 | 差 |
|---|---|---|---|
| 1,000 台节点，每台 1 个 locator | 1,000 条 | 4 条 /40（每 /40 装 256） | 250:1 |
| 19,000 台节点（Bell 案例，第 14 章） | 19,000 条 | 75 条 /40 | 253:1 |
| 65,536 台节点 | 65,536 条 | 1 条 /32 | 65,536:1 |

### 5.4.1 汇总的代价：Null0 与静默黑洞

:::en
When a router originates a summary, it also installs a discard route for the summary prefix pointing to Null0. This guarantees that packets for components that are not actually present are dropped at the summarizing router rather than looping in the core.
:::

产生汇总的路由器会同时装一条指向 **Null0** 的丢弃路由。这保证"**汇总里有、实际不存在**"的报文在汇总点被丢弃，而不是在核心兜圈子。

:::en
But it also creates a well-known failure mode: when the summarizing router loses reachability to a specific component, the discard route still attracts the traffic and silently black-holes it. The packet is delivered to the summarizing router, which has no more specific route, and the Null0 route drops it without any ICMP message.
:::

但它也埋下一个著名故障模式：**当汇总路由器丢失到某个具体分量的可达性时，Null0 路由仍在吸引流量，形成静默黑洞**。报文被送到汇总路由器，它没有更明细的路由，Null0 把它丢掉，**且不产生任何 ICMP 消息**。

这就是第 8 章 **UPA（Unreachable Prefix Announcement）** 要解决的问题。本章只需记住因果链：

```text
图 5-3：汇总 + 明细丢失 = 静默黑洞（原书 Figure 5.3 重绘）

   核心只看到：fdbb:bb00::/40  →  ABR-2
                                    │
   报文到达 ABR-2 ──────────────────┤
                                    ├─ 有 fc00:0:9::/48 明细？ 否
                                    │  （PE-9 所在区域已断）
                                    └─ 命中 Null0 → 丢弃，无 ICMP
                                    
   业务侧看到的现象：ping 客户地址超时，traceroute 停在 ABR-2。
   运维侧看到的现象：核心路由表里 /40 一直在，一切"正常"。
```

### 5.4.2 汇总的三条铁律

**铁律一：只汇总"自己区域里真实存在"的 locator。**

:::en
A summary must only cover components that are reachable through the summarizing router. If a summary covers prefixes that the router does not have detailed reachability for, it will black-hole traffic that another border router could have delivered.
:::

汇总**只能覆盖"经由本路由器可达"的分量**。如果汇总覆盖了自己并不掌握明细的前缀，它会把**本来能由别的边界路由器送达**的流量打成黑洞。

判断方法很机械：对汇总前缀下的每一条明细，检查它的出接口/下一跳是否都在本路由器上。不在的，就不该被这条汇总覆盖（或者本路由器不该做这个汇总）。

**铁律二：一个算法一个可汇总块。**

Flex-Algo 的 locator 与 Algo(0) 的 locator 在地址上是**分开的块**（第 4 章：`fc00:0:x::/48` vs `fc00:1:x::/48`）。汇总时**绝不能跨算法块做**：

| 做法 | 结果 |
|---|---|
| Algo(0) 块汇总成 /40，Flex-Algo 块单独汇总 | 正确，两套算法路径都保持 |
| 把两个算法的 locator 汇总进同一条 /32 | **算法属性丢失**，走 Algo(0)，低时延业务静默降级 |

原因在 5.3 节已给：汇总/重分发都是"退化为 Algo(0)"的操作。所以地址规划（第 10 章）必须**按算法分块**，这也解释了第 4 章为什么坚持"每个算法一个 locator 块"。

**铁律三：汇总路由器要保留明细。**

汇总的目的是**让核心不认识明细**，不是让**汇总路由器**忘记明细。汇总路由器必须继续持有本区域的全部 locator 明细，否则：

- 它无法判断某个分量是否还存在（没法触发 UPA）；
- 它无法做明细转发，所有区内流量都要靠更具体的 L1 路由——而那条路由若来自泄露，会与汇总形成"同一路由器上两条不同来源"的复杂局面。

**例 5.6：ABR-2 上汇总本区域 locator 并通告进 L2**

```text
router isis 1
 address-family ipv6 unicast
  summary-prefix fdbb:bb00:0000::/40 level-2
  summary-prefix fdbb:bb01:0000::/40 level-2
```

一条 `/40` 覆盖 256 个 `/48`；`fdbb:bb01::/40` 是 Flex-Algo(128) 的块，**单独汇总**。两条汇总，两套算法，互不干扰。

**例 5.7：验证汇总与 Null0 同时存在**

```text
RP/0/RP0/CPU0:ABR-2# show route fdbb:bb00:0000::/40
Routing entry for fdbb:bb00::/40
  Known via "isis 1", distance 115, metric 20, type level-2
  Installed Oct 28 09:12:44.331 for 03:41:07
  Routing Descriptor Blocks
    directly connected, via Null0
      Route metric is 20, traffic share count is 1
```

`via Null0` 是**预期**的——它就是为了吃掉"汇总里有、实际没有"的报文。真正要警惕的是：**`via Null0` 存在，但明细已经一批一批消失**。这时 Null0 就从"兜底"变成了"黑洞"。

### 5.4.3 双 ABR 同时汇总：ECMP 下的半丢包

现网几乎不会只有一台 ABR。当两台 ABR 同时为同一区域做同一个 `summary-prefix` 时，核心看到的是"两条等价的汇总路由"，走 ECMP。这里有一个**只在故障时才暴露**的坑：

```text
图 5-5：双 ABR 汇总 + 单边明细丢失（原书 Figure 5.5 重绘）

              核心 ──┬── ECMP ──► ABR-2  /40，明细完整 → 正常送达
                     │
                     └── ECMP ──► ABR-6  /40，明细已丢 → Null0 丢弃

   业务侧观感：约 50% 丢包，时通时不通；且每次路径变化丢包比例会跳变。
   核心侧观测：两条 /40 都 Up，metric 相同，看不出任何异常。
   ABR-6 侧观测：/40 依然通告，Null0 依然存在，也看不出异常。
```

这个故障的恶劣之处在于**三方各自看都正常**：

| 视角 | 看到的事实 | 结论 |
|---|---|---|
| 核心 | 两条 /40 等价，ECMP | 一切正常 |
| ABR-6 | 汇总路由在、Null0 在 | 一切正常 |
| 业务 | 50% 丢包 | 网络有问题 |

三个防护手段，按代价从低到高：

1. **一致的通告条件**：两台 ABR 上的 `summary-prefix` 必须**对同一组明细生效**。若一台的明细来自 L1 泄露、另一台来自直连，明细集合天然不同，就会单边悬空。
2. **汇总前先确认明细完整**：把"该 /40 下的明细条数"做成巡检项（区内节点数 × 每节点 locator 数），任一台 ABR 上数量对不上就告警。
3. **上 UPA（第 8 章）**：这才是根治——明细丢失时由 ABR 主动通告"该前缀不可达"，上游 BGP PIC 直接切换，不再依赖 ECMP 抽签。

**一句话**：**汇总的单点不是"一台路由器"，而是"一份明细"。** 只要有一台 ABR 的明细不全，你就有了一台隐形黑洞。

## 5.5 三件事同时存在时：泄露 × Flex-Algo × TI-LFA

前三章与本章各自都能讲通，真正出事的是**三者叠加**。这一节把交叉点挑明。

### 5.5.1 算法 locator 的路由只存在于该算法的路由表里

:::en
In an SRv6 network with flexible algorithms, the IGP does not compute a single shortest path tree: it computes one tree per algorithm that the node participates in, and installs the corresponding locator prefixes in separate routing tables.
:::

在启用灵活算法的 SRv6 网络里，IGP **不再只算一棵最短路树**：它为节点参与的**每个算法**各算一棵树，并把对应的 locator 前缀装进**各自独立的路由表**。

:::en
As a consequence, a router that does not participate in Flex-Algo(128) has no route to the locators of Flex-Algo(128) at all: the prefix is not present in its Algo(0) table. A packet whose outer destination is such a locator is dropped by that router, even though the same destination node is perfectly reachable through its Algo(0) locator.
:::

由此推出一条**极容易踩的坑**：**不参与 Flex-Algo(128) 的路由器，压根没有 Flex-Algo(128) locator 的路由**——这条前缀不在它的 Algo(0) 路由表里。外层目的地是这类 locator 的报文会被它**直接丢弃**，尽管**同一个目的节点的 Algo(0) locator 完全可达**。

这解释了一类经典现象：

```text
现象：跨区低时延业务不通，但普通业务全通。
      在中间某台 P 节点上 traceroute 断掉，
      而 ping 该节点的 Algo(0) locator 一切正常。

原因：PE-1 用 fc00:1:3:: 作外层 DA，
      区域内的 P 节点没参与 Flex-Algo(128)，
      它的路由表里没有 fc00:1:3::/48 → 无路由 → 丢弃。
```

同一区域的两种部署方式，结果完全不同：

| 区内节点是否参与算法 | 低时延业务的跨区转发 | 代价 |
|---|---|---|
| **全参与**（`flex-algo 128` 一行） | 区内按算法路径走，全程一致 | 每台节点都要支持该度量类型 |
| **不参与** | **不通**（无路由，静默丢弃） | —— |
| 边界处换 SID（段列表 `<fc00:0:2::, fc00:1:3::>`） | 区内 Algo(0) 到 ABR，ABR 之后按算法走 | 需要头端编程或 BSID，规模不友好 |

工程结论：**Flex-Algo 要跨区，就整个转发域一起参与。** "只在核心开算法、接入区不开"是行不通的，因为转发路径上的每一跳都要有该算法的路由。

**例 5.8：确认某节点是否参与算法、是否有该算法路由**

```text
RP/0/RP0/CPU0:P-11# show isis flex-algo 128
IS-IS 1 Flex-Algo 128
  Metric-Type: 1  Priority: 128  Calc-Type: 0
  Participating: Yes
  Locators:
    fc00:1:3::/48    via Gi0/0/0/1  metric 20
!
RP/0/RP0/CPU0:P-11# show isis route flex-algo 128
IS-IS 1 IPv6 Unicast Route Table (Flex-Algo 128)
Prefix               Metric  Interface   Nexthop
fc00:1:2::/48        20      Gi0/0/0/1   fe80::2 (ABR-2)
fc00:1:3::/48        40      Gi0/0/0/1   fe80::2 (ABR-2)
```

`Participating: Yes` 与 `show isis route flex-algo 128` 里能看到远端 locator，这两条同时成立才算"这台节点能转发该算法的流量"。只看到 uN 段（`show segment-routing srv6 sid all`）**不代表**它会把别人的算法流量转发出去——那只是本地 SID。

### 5.5.2 汇总之后，TI-LFA 的保护范围也跟着缩小

:::en
TI-LFA computes a repair path to a post-convergence next hop. Its scope is therefore limited by the scope of the routing information: a router can only protect the destinations for which it has a route, and can only compute a repair path within the topology it knows.
:::

TI-LFA 计算的是"到**收敛后下一跳**"的修复路径。它的作用范围因此**被路由信息的范围限制**：路由器只能保护**自己有路由的**目的地，也只能在**自己掌握的拓扑内**算修复路径。

:::en
When locators are summarized at the area border, the routers inside the area no longer have detailed routes to remote locators: they have a summary route. Protection for the individual remote locators is then provided by the border router, which does have the details, and not by the routers inside the area.
:::

当 locator 在区域边界被汇总后，**区内路由器不再持有远端 locator 的明细**，只有一条汇总路由。此时对**单个远端 locator** 的保护由**边界路由器**（持有明细的那台）提供，而不是区内路由器。

于是保护被**分层**了：

```text
图 5-4：汇总后的分层保护（原书 Figure 5.4 重绘）

   PE-1 ──► P-11 ──► ABR-2 ══════► ABR-4 ──► P-31 ──► PE-3
    │        │         │              │        │        │
    └────────┴─────────┘              └────────┴────────┘
      保护「到汇总前缀」                保护「到明细 locator」
      （区内拓扑内修复）                （骨干拓扑内修复）

   第 1 段：PE-1 到 fdbb:bb00::/40 的下一跳（ABR-2）
            若 P-11 故障，TI-LFA 在区内算修复路径 → 仍到 ABR-2
   第 2 段：ABR-2 到 fc00:0:7::/48 的下一跳（ABR-4）
            若骨干链路故障，TI-LFA 在骨干算修复路径 → 仍到 ABR-4
   两段各自独立收敛，任一段故障都不影响另一段的保护范围。
```

这张图给出了一个**设计原则**：**汇总点就是保护责任的转移点**。汇总做在哪一层，那一层就必须承担该层以下的全部明细保护能力（PQ 空间、备份带宽、算法内的修复路径）。

反过来，如果汇总做得过粗（例如把整个大区汇总成一条 /32 交给骨干），那台汇总路由器就成了**全区的单点**：它一挂，骨干只知道 /32 没了，几十台 PE 的业务一起断。

### 5.5.3 泄露还是汇总：一张决策表

| 你的目标 | 该做的事 | 不该做的事 |
|---|---|---|
| 区内节点能到远端 locator | L2 → L1 泄露（**只放 locator 聚合**） | 把客户前缀一起泄露 |
| 骨干能到各区域 locator | L1 → L2 泄露（仅本区域 locator） | 双向无策略重分发 |
| 核心路由表要平坦 | 在 ABR 上 `summary-prefix` | 汇总后又把明细泄露进骨干 |
| 低时延业务跨区 | **整个转发域参与同一个 Flex-Algo** | 只核心开算法、接入区不开 |
| 保护范围要覆盖端到端 | 汇总点下沉到"该层能保护"的位置 | 一条 /32 汇总全大区 |
| 汇总后不出静默黑洞 | 上 UPA（第 8 章） | 只靠 Null0 兜底 |

## 5.6 排障：跨区不通的五步定位法

跨区故障的现象高度雷同（"内层通、外层不通"），但根因分布在五个层次。按下面的顺序查，每一步都有明确的"是/否"判据，**不要跳步**：

```text
第 1 步：外层 locator 在源端有没有路由？
  show isis route <远端 locator>
  ├─ 无条目 ──────────────► 泄露/重分发没配，或策略 drop 了（5.2、5.3）
  └─ 有条目 ──► 第 2 步

第 2 步：这条路由是不是"泄露来的"，down bit 对不对？
  show isis database verbose level-1 | include -A3 "Extended Reachability"
  ├─ X:0 而链路确实是跨区的 ──► 不是泄露，是本地产生的（可能误配 redistribute）
  └─ X:1 ──► 第 3 步

第 3 步：下一跳是不是"最近 ABR"而不是"最优 ABR"？
  traceroute <远端 locator>  /  show isis route <locator> detail
  ├─ 出口是最近 ABR，绕行骨干 ──► 只靠 ATT 默认路由，明细没泄露（5.1）
  └─ 出口符合设计 ──► 第 4 步

第 4 步：算法 locator 在中间节点有没有路由？
  show isis route flex-algo 128 <远端 locator>
  ├─ 无条目 ──────────────► 该节点未参与算法（5.5.1）
  └─ 有条目 ──► 第 5 步

第 5 步：报文在哪一跳被丢？
  traceroute 分段 + 逐跳 show segment-routing srv6 sid all
  ├─ 停在汇总路由器 ──────► 命中 Null0，明细丢失（5.4.1，上 UPA）
  └─ 停在某台 P 节点 ─────► 该节点无该 locator 路由（回到第 1/4 步）
```

配套的巡检矩阵（建议做成日常脚本）：

| 检查项 | 命令 | 期望 |
|---|---|---|
| 每台 L1 节点有几个远端 locator | `show isis route \| count` | = 全网 locator 数（泄露生效） |
| 泄露前缀是否都带 down 位 | `show isis database verbose level-1` | `X:1` |
| 骨干是否有全部区域聚合 | `show isis route level-2` | 每个区域一条聚合 |
| 汇总是否有 Null0 | `show route <summary>` | `via Null0`，且明细**同时存在** |
| 重分发计数是否稳定 | `show isis statistics` | 计数不持续增长 |
| 算法路由是否齐 | `show isis route flex-algo K` | 全网 locator 都在 |
| 算法参与是否齐 | `show isis flex-algo K` | `Participating: Yes` |

## 5.7 本章小结

:::en
In this chapter, we reviewed the mechanisms that make SRv6 locators reachable across an IS-IS domain: leaking between levels, redistribution between instances, and summarization.
:::

本章讲了让 SRv6 locator **跨 IS-IS 域可达**的三套机制：**层级间泄露、实例间重分发、前缀汇总**。

:::en
We first observed that a Level-1-only router reaches remote locators through a default route, which is sufficient for connectivity but not for optimality nor for flexible algorithms, and that leaking the locator prefixes from Level-2 into Level-1 solves both problems at the cost of scale.
:::

先说清了一个事实：L1-only 路由器靠**默认路由**就能到远端 locator，这对**连通性**够用，但**对最优路径不够、对灵活算法完全无效**；把 locator 从 L2 泄露进 L1 能同时解决这两个问题，**代价是路由表规模**。

:::en
We then showed that redistribution between instances only needs to carry the locator prefixes, since SRv6 requires no label or SID binding distribution, but that the IGP algorithm is not preserved across instance boundaries.
:::

然后是实例间重分发：**只需携带 locator 前缀**——SRv6 不需要分发标签或 SID 绑定——但**算法属性跨实例边界不保留**。

:::en
Finally, we described summarization, the capability that lets an SRv6 network keep a flat routing table where an MPLS network would grow linearly, and the discard route that comes with it, which protects the core from looping packets but silently black-holes traffic when a component disappears.
:::

最后是汇总：它让 SRv6 网保持**平坦路由表**，而 MPLS 网只能**线性增长**；随之而来的 Null0 丢弃路由既保护核心不兜圈子，也在分量消失时**静默黑洞**。

把本章压成一张表：

| 机制 | 作用范围 | 保留算法？ | 主要风险 |
|---|---|---|---|
| ATT 默认路由 | L1-only | **否** | 次优路径、算法失效 |
| L2 → L1 泄露 | 单实例跨 level | 是 | 路由表规模；down 位配置错误 |
| L1 → L2 泄露 | 单实例跨 level | 是 | 只泄露本区域 locator 才安全 |
| 实例间重分发 | 跨进程 | **否** | 双向无策略 → 前缀反馈震荡 |
| 汇总 `summary-prefix` | 区域边界 | 按块区分 | Null0 静默黑洞（→ 第 8 章 UPA） |

一句话收束：**locator 的可达性靠泄露与重分发建立，规模靠汇总控制，正确性靠"只放 locator"这条纪律守住。** 三者缺一，网络要么不通、要么绕行、要么被黑洞吃掉。

## 实战案例

### 案例 A：19,000 节点网络的分层泄露与汇总规划

**场景**：一个省级+地市两级网络，核心 4 个区域（每区约 200 台 P/PE），地市 60 个 METRO 实例。目标是核心路由表不随节点数增长，同时保证跨区低时延业务可用。

**地址与泄露规划**：

```text
SID block：fdbb:bb00::/32（Algo 0）   fdbb:bb01::/32（Flex-Algo 128）

  fdbb:bb00:0000::/40   ← 区域 1（256 个 /48）
  fdbb:bb00:0100::/40   ← 区域 2
  fdbb:bb00:0200::/40   ← 区域 3
  fdbb:bb00:0300::/40   ← 区域 4
  fdbb:bb00:0400::/40 … ← 地市 METRO 各实例一段
  fdbb:bb01:0000::/40   ← Flex-Algo 128，按区域再切

泄露范围（三个方向，三套策略）：
  ① L2 → L1（区内）：只放 fdbb:bb00::/32 le 48 + fdbb:bb01::/32 le 48
  ② L1 → L2（出区）：只放本区域的两条 /40（Algo 0 与 Algo 128 各一条）
  ③ 实例间：只放对端实例的 /40 聚合
```

**关键配置（核心 ABR）**：

```text
prefix-set LOC-REMOTE
  fdbb:bb00::/32 le 48,
  fdbb:bb01::/32 le 48
end-set
!
prefix-set LOC-LOCAL-AGG
  fdbb:bb00:0000::/40,
  fdbb:bb01:0000::/40
end-set
!
route-policy LOC-L2TO1
  if destination in (LOC-REMOTE) then
    pass
  else
    drop
  endif
end-policy
!
route-policy LOC-L1TO2
  if destination in (LOC-LOCAL-AGG) then
    pass
  else
    drop
  endif
end-policy
!
router isis 1
 address-family ipv6 unicast
  metric-style wide
  summary-prefix fdbb:bb00:0000::/40 level-2
  summary-prefix fdbb:bb01:0000::/40 level-2
  redistribute isis 1 level-2 into level-1 route-policy LOC-L2TO1
  redistribute isis 1 level-1 into level-2 route-policy LOC-L1TO2
```

**规模账本**（这是本章最该记住的收益）：

| 项目 | 不汇总 | 汇总后 |
|---|---|---|
| 核心 L2 路由表条目 | 19,000（每节点一条 /48） | 4 条区域 /40 + 60 条地市 /40 = 64 条 |
| 区内 L1 路由表条目 | 默认路由 1 条（次优） | 64 条聚合（最优） |
| 单台节点 SPF 计算量 | 全网拓扑 | 本区拓扑 + 聚合前缀 |
| 收敛影响面 | 全网 | 本区 |

**上线核对六步**：

| 步骤 | 命令 | 通过标准 |
|---|---|---|
| 1. 泄露策略只命中 locator | `show route-policy LOC-L2TO1` + 匹配计数 | 无客户前缀命中 |
| 2. 区内有聚合 | `show isis route` | 每个远端区域一条，`X:1` |
| 3. 骨干只有聚合 | `show isis route level-2` | 条数 ≈ 区域数，不是节点数 |
| 4. Null0 与明细并存 | `show route <summary>` 与 `show isis route <某明细>` | 两者都在 |
| 5. 算法路由独立 | `show isis route flex-algo 128` | 全区域 locator 都在 |
| 6. 重分发计数稳定 | `show isis statistics` 连续两次采样 | 无增长 |

### 案例 B：双向无策略重分发导致的前缀震荡

**现象**：CORE 与两个 METRO 实例做双向重分发后，每 3–5 分钟出现一次全网 SPF 抖动，BGP 邻居不掉，但业务出现亚秒级丢包。`show isis statistics` 的 `redistributed` 计数持续增长。

**排查**：

```text
① 看策略范围
   show route-policy LOC-ONLY
   → 策略里写的是 "if destination in (fdbb:bb00::/32 le 64)"，
     le 64 把客户前缀（/56、/64）也放进来了

② 看谁在重分发
   show isis interface / show run router isis
   → METRO-1 与 METRO-2 各有一条指向 CORE 的重分发，
     且两个 METRO 之间还有一条直连重分发（设计里没有）

③ 看反馈路径
   METRO-1 → CORE → METRO-2 → METRO-1
   前缀在两实例间往返，每次往返 metric 变化触发 SPF

④ 结论：三重问题叠加
   - le 64 放进了客户路由（规模爆炸）
   - 三向重分发形成闭环（无 down 位保护）
   - 策略两边不一致（一侧 le 64，一侧 le 48）
```

**修复**：

```text
! 1. 前缀集收窄到 locator，双向共用同一个 set
prefix-set LOC-ONLY
  fdbb:bb00::/32 le 48
end-set
!
! 2. 只保留 CORE ↔ 各 METRO 的星型重分发，删除 METRO 之间的重分发
! 3. 两个方向引用同一个 route-policy
router isis CORE
 address-family ipv6 unicast
  redistribute isis METRO-1 level-2 into level-2 route-policy LOC-ONLY
  redistribute isis METRO-2 level-2 into level-2 route-policy LOC-ONLY
```

**经验三条**：

1. **实例间重分发必须星型**（所有 METRO 只对 CORE），任何"METRO 直连重分发"都会形成环；
2. **两个方向共用同一个 prefix-set**，避免一侧宽一侧窄；
3. **把 `show isis statistics` 的重分发计数做成告警指标**——它是这类问题唯一稳定的早期信号。

### 案例 C：低时延业务跨区不通，根因是"参与"不是"路由"

**现象**：Flex-Algo(128) 的低时延业务在核心区内部完全正常；一旦跨到另一个区域（区内有 12 台 L1-only 老节点），业务静默丢包，`traceroute` 停在第一台老节点。

**排查**：

```text
① 源端有算法路由
   show isis route flex-algo 128 <目的 locator>   → 有，metric 40

② 老节点上没有
   show isis route flex-algo 128 <目的 locator>   → 无条目
   show isis flex-algo 128                        → Participating: No

③ 老节点上有 Algo(0) 的 locator 吗
   show isis route fc00:0:7::/48                  → 有（泄露来的）

④ 结论：老节点没参与 128，其路由表里没有 fc00:1:7::/48，
   外层 DA 是该地址的报文在此被丢弃（不是路由环路，是直接丢）
```

**三种修复方案对比**：

| 方案 | 做法 | 适用 | 代价 |
|---|---|---|---|
| **A. 全网参与** | 老节点升级/开启 `flex-algo 128` | 设备支持 `metric-type delay` | 需版本确认；不支持则该节点退出算法，问题依旧 |
| **B. 边界换 SID** | 头端用段列表 `<fc00:0:2::, fc00:1:7::>`，在 ABR 处切到算法 SID | 只有少数老节点区域 | 需 SR Policy/BSID 与容量规划，规模不友好 |
| **C. 双 locator 分区** | 老节点区域只用 Algo(0) locator，算法路径在核心区终止 | 老节点无法升级 | 低时延只覆盖核心，不满足端到端 SLA |

**结论**：**Flex-Algo 的边界不是"策略边界"，而是"转发域边界"。** 参与不了算法的节点，就是这个算法路径上的断点，且断得很安静——没有环路、没有告警，只有丢包。

## 延伸阅读

- **RFC 1195 / ISO 10589**：IS-IS 两级的原始定义，L1/L2、ATT 位的来源。
- **RFC 5305 / RFC 5302**：IPv6 扩展可达性 TLV 与 up/down bit 的规则，5.2.1 的相对规范。
- **RFC 5308**：IPv6 prefix 的 `summary-prefix` 与 discard 行为语义。
- **RFC 9352**：IS-IS 的 SRv6 扩展（Locator TLV、End SID、End.X SID），泄露的内容载体。
- **RFC 9350**：Flex-Algo 定义与参与——5.5.1 的"路由只存在于本算法表"的规范依据。
- **RFC 8986**：SRv6 网络编程，locator 与 End 行为的定义。
- 交叉参考：第 3 章（locator 与 End/End.X）、第 4 章（Flex-Algo 参与关系）、第 8 章（UPA 解决汇总黑洞）、第 10 章（按算法分块的地址规划）、第 14 章（Bell 的 81 个区域与 19,000 节点实网数据）。



