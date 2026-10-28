# 04 · 灵活算法 Flex-Algo

> 对应原书第 4 章 *Flexible Algorithms*。一句话：**让同一张物理网同时表达多种"最短路径"**——一条按 IGP 度量最短，一条按时延最短，一条避开某些链路。

## 4.1 为什么需要它

:::en
An IGP normally computes a single shortest path tree, based on a single metric. But operators need several different notions of "best": lowest IGP cost for general traffic, lowest latency for latency-sensitive services, and a path that avoids certain links or planes for others. Flex-Algo lets the IGP compute multiple constrained SPF trees, each associated with an algorithm identifier, over the same physical topology.
:::

IGP 默认只算一棵最短路径树，只认一个度量。但运营商需要好几种"最优"：普通流量要最低 IGP 开销，时延敏感业务要最低时延，还有业务要绕开某些链路或平面。Flex-Algo 让 IGP 在同一张物理拓扑上算出**多棵带约束的 SPF 树**，每棵树对应一个 algorithm 编号。

| Algorithm | 含义 | 常见用途 |
|---|---|---|
| 0 | 常规最短路径（IGP metric） | 普通业务 |
| 128 | 最小**时延**（min-delay） | 5G 回传、金融、视频 |
| 129+ | 自定义（排除链路、限制亲和、另一套度量） | 切片、专网、绕行 |

## 4.2 三个组成部分

:::en
Flex-Algo is built from three pieces: a definition, which states how the algorithm is computed; a set of participating routers, which must all agree on the same definition; and a set of prefixes, each of which must be associated with a locator that is bound to that algorithm. If a router's definition differs from the one used by the rest of the domain, that router does not participate, and the algorithm falls back to algorithm zero.
:::

Flex-Algo 由三部分组成：

1. **定义（FAD，Flex-Algo Definition）**：说明这个算法怎么算——用哪个度量、排除哪些链路、用哪些亲和属性。
2. **参与者（participation）**：只有**声明参与且 FAD 完全一致**的节点才进入该算法的 SPF 计算。
3. **前缀（prefix）**：前缀必须关联一个**绑定该算法**的 locator，才会生成该算法的 SID。

**最容易踩的坑**：FAD 不一致的节点会被静默排除。结果是"这个算法算出的路径少了一段"，业务看着通但绕行或缺省回落到 algo 0。排查要看 `show isis flex-algo` 的参与者列表。

## 4.3 配置

```text
router isis 1
 flex-algo 128
  metric-type delay
  advertise-definition
 !
 interface HundredGigE0/0/0/1
  address-family ipv6 unicast
   flex-algo 128
   !
  !
 !
!
segment-routing
 srv6
  locator LOWLAT
   micro-segment behavior unode psp-usd
   prefix fc00:1:7::/48
   algorithm 128
```

:::en
Each algorithm needs its own locator, because the algorithm is encoded in the prefix advertisement: a locator bound to algorithm 128 produces a SID that is reachable only over the algorithm-128 tree. In practice an operator configures one locator per algorithm on every node, so a node has one address per algorithm.
:::

每个算法要有自己的 locator，因为算法信息随前缀一起通告：绑定 128 的 locator 产生的 SID，只能沿 128 那棵树到达。实践中每台节点**每个算法配一个 locator**，于是一台节点有多个地址，每个地址代表"在某种度量下的最优到达方式"。

```text
Node7:
  fc00:0:7::/48   algorithm 0    → 最短路
  fc00:1:7::/48   algorithm 128  → 最小时延
```

## 4.4 与 SR Policy / TI-LFA 的关系

:::en
Flex-Algo is a distributed, IGP-driven mechanism: it gives you a constrained shortest path without any controller. SR Policy is centralized and explicit: it gives you an arbitrary path. They are complementary — Flex-Algo covers the "one metric for a whole class of traffic" case, SR Policy covers the "this particular flow must go exactly here" case. TI-LFA computes its repair paths inside each algorithm, so a low-latency path is also protected by a low-latency repair path.
:::

Flex-Algo 是**分布式、IGP 驱动**的：不需要控制器，就能得到一条带约束的最短路径。SR Policy 是**集中式、显式**的：能得到任意路径。两者互补——Flex-Algo 解决"某一类流量统一走某个度量"，SR Policy 解决"这条特定流必须精确走这里"。

重要细节：**TI-LFA 在每个算法内部各自计算修复路径**，所以低时延路径的备份也是低时延路径，不会故障后突然绕远。

## 4.5 典型约束清单

| 约束 | FAD 字段 | 说明 |
|---|---|---|
| 度量类型 | metric-type | IGP / 时延 / TE metric |
| 亲和包含 | affinities include-any/all | 只走打了某标记的链路 |
| 亲和排除 | exclude-any | 绕开某类链路（如跨洋、微波） |
| 排除链路 | exclude | 显式排除指定链路/节点 |
| 优先级 | priority | 决定哪条路径更"优" |

## 实战案例：5G 回传的双算法双 Block 规划

**需求**：同一张回传网，普通业务走最短路，uRLLC/视频类走最小时延；两类流量在故障时都不能绕远。

**方案**：

1. 全网红绿两条 locator：`fdbb:bb00::/32`（algo 0）、`fdbb:bb01::/32`（algo 128）。
2. 所有链路启时延度量（`metric-type delay`），用 `advertise-definition` 统一 FAD；亲和属性标记微波/跨海链路。
3. 业务侧通过 BGP Color + Automated Steering 把低时延 VPN 路由引到 algo 128 的 SID。
4. 每台节点两个 locator 都参与 TI-LFA，保证故障后仍在本算法内恢复。

**验证**：

- `show isis flex-algo 128` 参与者必须是全网节点；少一个就会导致该区域路径不一致。
- `traceroute` 对比两个 locator 的路径，确认 algo 128 走的是低时延链路。
- 注入链路故障，确认 algo 128 的备份路径仍在低时延集合内。

**常见坑**：

| 现象 | 根因 |
|---|---|
| algo 128 路径等于 algo 0 | 部分节点没配 `flex-algo 128` 的接口参与，SPF 被剪枝后回落到最短路 |
| 只有本区域能到时延 locator | locator 绑定了算法，但跨区没有泄露/汇总该 locator（见第 5 章） |
| 业务偶发绕远 | 某些前缀只有 algo 0 的 locator，Color 引导失败后走默认路径 |
| 时延抖动大 | 时延度量是静态配置而非动态测量，需配合性能测量工具校准 |

## 本章小结

1. Flex-Algo = IGP 内的多棵受限 SPF 树，用 algorithm ID 标识。
2. 三要素：FAD、参与者、绑定算法的 locator；FAD 不一致会静默退化。
3. 一节点一算法一 locator，地址规划必须同步（见第 10 章）。
4. TI-LFA 按算法分别计算，保证故障后不跨算法绕行。
