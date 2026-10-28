# 14 · 案例：Bell Canada 的 SRv6 地址规划

> 对应原书第 14 章，与 Bell Canada 技术总监 Daniel Voyer 合作撰写。**这是全书唯一给出完整生产级地址算账的章节**，可以直接当成模板复用到你自己的规划里。

## 14.1 背景与动机

:::en
Bell Canada is the largest communications company in Canada. It deployed one of the earliest SR-MPLS networks in 2017, and the first benefit it realized was TI-LFA protection. Because of the compelling advantages of SRv6 uSIDs, Bell then transitioned to SRv6, replacing the complexity of MPLS at the host, socket and container level, and removing the need for SR-MPLS, LDP and SRv6 gateways at the data center and network edge.
:::

Bell 是加拿大最大的通信公司。2017 年它就建成了最早的一批 SR-MPLS 网络，**第一个真正落地的收益是 TI-LFA 保护**。后来因为 uSID 的优势太明显，转向 SRv6：主机/套接字/容器层面不再需要 MPLS，数据中心与网络边缘也不再需要 SR-MPLS/LDP/SRv6 网关。

:::en
The reported benefits include a potential reduction of up to 90% in carrier network service OPEX, a 75% reduction in equipment footprint, and as much as 66% reduction in power consumption per central office when service programming is used. SRv6 uSID also removes the BGP 3107 complexity tax and enables IGP summarization, which MPLS cannot do.
:::

公开的数字：载波业务 OPEX 最多降 **90%**、设备占地降 **75%**、启用服务编程后单局功耗最多降 **66%**；同时删掉 BGP 3107 那笔复杂度税，并获得 MPLS 不具备的 IGP 汇总能力。

## 14.2 网络结构：81 个区域、19,720 个节点

:::en
Bell operates a multi-level IS-IS network with a level-2 backbone and up to 80 level-1 areas, for a total of 81 areas. The network is expected to have around 19,000 nodes considering mid-term growth. Area sizes vary between 100 and 700 nodes: 48 small areas of up to 150 nodes, 25 medium areas of up to 300 nodes, and 7 large areas of up to 700 nodes.
:::

Bell 跑的是多级 IS-IS：1 个 L2 骨干 + 最多 80 个 L1 区域，共 **81 个区域**；考虑中期增长，全网约 **19,000+ 节点**。区域规模从 100 到 700 不等：

| IS-IS 层级 | 区域组 | 单区最大节点 | 区域数 | 合计节点 |
|---|---|---|---|---|
| L2 | 骨干 | 120 | 1 | 120 |
| L1 | 小 | 150 | 48 | 7,200 |
| L1 | 中 | 300 | 25 | 7,500 |
| L1 | 大 | 700 | 7 | 4,900 |
| | | | **81** | **19,720** |

:::en
The distribution matters: there are many more small areas than large ones. Allocating the same number of sets to every area would waste a large fraction of the space in the small areas and leave no room for growth in the large ones.
:::

这个分布是规划的关键：**小区域远多于大区域**。若给每个区域平均分配 Set，小区浪费一大片、大区又不够涨——这是最典型的错误分配方式（第 10.2 节算过：57,000 / 81 ≈ 700，理论可行，实践不可取）。

## 14.3 地址规划：一个 Space、三个 Block、224 个 Set

:::en
Bell designates a small portion of the ULA range, fd00::/8, as the SRv6 space: 0.0015% of this space is enough. Using ULA provides excellent addressing scale, and also network opacity and privacy, since ULAs are not routable outside the domain.
:::

Bell 从 `fd00::/8`（ULA 私有空间）里取极小一段作为 SRv6 Space——**只占 0.0015%**。用 ULA 有两个好处：地址规模充裕；且 ULA 在域外不可路由，天然带来网络不透明性与隐私性。

:::en
They allocate one uSID block per algorithm: fdbb:bb00::/32 for algorithm 0 (minimum cost), fdbb:bb01::/32 for Flex-Algo 128 (minimum delay), and fdbb:bb02::/32 for Flex-Algo 129 (restrict link). Each block provides about 57,000 global uSIDs, which exceeds current requirements.
:::

每个算法一个 Block：

| Block | 算法 | 用途 |
|---|---|---|
| `fdbb:bb00::/32` | Algo 0 | 最短路（低成本） |
| `fdbb:bb01::/32` | Flex-Algo 128 | 最小时延 |
| `fdbb:bb02::/32` | Flex-Algo 129 | 限制链路（绕行） |

单个 Block 提供约 **57,000** 个全局 uSID，对 19,720 节点的网络绰绰有余。

:::en
Sets simplify the allocation: each set holds 256 uSIDs and is represented by a /40. A block contains 224 sets, with set IDs from 0x00 to 0xdf, for global uSID allocation. One or more sets are allocated to each region, and a region gets the same set IDs from every block. A node gets the same set ID and node ID in every block, so its locators differ only in the block ID.
:::

**Set 是分配的基本单位**：一个 Set 装 256 个 uSID，对应一个 /40；一个 Block 有 **224 个 Set**（ID `0x00`–`0xdf`）用于全局分配。

规则极其干净：

1. 每个区域分配一到多个 Set。
2. **同一区域在每个 Block 里拿相同的 Set ID**。
3. **同一节点在每个 Block 里拿相同的 Set ID + Node ID**。

于是同一节点的三个 locator 只差 Block ID 那一段：

```text
Algo 0     : fdbb:bb00:080e::/48
Algo 128   : fdbb:bb01:080e::/48
Algo 129   : fdbb:bb02:080e::/48
              └─┬──┘ └┬┘└┬┘
             Block  Set Node(=14=0x0e)
```

:::en
The allocation model is not equal-sized per area. Small areas get one set (256 uSIDs for up to 150 nodes), medium areas get two, and large areas get three, with additional sets assigned on demand. Sets allocated to one region need not be contiguous: growth simply takes the next free set.
:::

分配模型**不是按区域平均**，而是按需：

| 区域规模 | 节点数 | Set 数 | uSID 余量 |
|---|---|---|---|
| 小 | ≤150 | 1 | 106 |
| 中 | ≤300 | 2 | 212 |
| 大 | ≤700 | 3 | 68 |
| 骨干 | 120 | 1 | 136 |

Set **不必连续**：区域长大了，从空闲池里再拿一个 Set 就行，边界路由器加一条 /40 汇总即可。

## 14.4 汇总与增长

:::en
The set structure leads naturally to summarization: 256 /48 prefixes collapse into one /40, a 256-to-1 gain. Border routers of each region advertise one summary per assigned set into the core. When a region outgrows its sets, the operator assigns another set and adds one more summary prefix.
:::

Set 结构天然带来汇总：**256 个 /48 → 1 个 /40，256:1**。每个区域的边界路由器按"已分配的 Set"向核心通告汇总，一个 Set 一条。区域扩容时，加一个 Set、加一条汇总——**核心表项随区域数增长，不随节点数增长**。

## 实战案例：把 Bell 的模型套到一张 2 万节点的网上

**输入**：80 个区域，最大 700 节点，3 个算法。

**算账**：

1. 每区 Set 数 = ⌈节点数 / 256⌉ + 1（预留增长）→ 小 2、中 3、大 4。
2. 总 Set 需求 ≈ 48×2 + 25×3 + 7×4 + 1×1 ≈ 200，**224 个 Set 几乎用尽**。
3. 结论：如果按"预留一个"的保守策略，单个 Block 不够——此时要么减少预留，要么**再开一个 Block**（地址空间完全允许：256 个 Block 只占 /24）。

**这正是 Bell 规划里最容易被忽略的一条**：224 个 Set 听起来很多，但在 80 个区域 × 3 个算法的场景下，真正的约束不是节点数，而是**区域数 × 预留系数**。

**落地检查表**：

| 项 | 判据 |
|---|---|
| Space 是否与其他业务重叠 | `fdbb:bb00::/24` 与现网无交集 |
| 每区 Set 余量 | ≥ 25% |
| Node ID 唯一性 | 同区内不重复，跨算法保持一致 |
| 汇总覆盖 | 每条 /40 完整覆盖内部 /48 |
| 增长路径 | 剩余 Set 数 ≥ 区域数（应对新开区） |

## 本章小结

1. Bell 用 ULA 的 0.0015% 承载 19,720 节点、3 个算法。
2. Space → Block（按算法）→ Set（按区域，/40）→ Node（/48）四层结构。
3. 跨 Block 保持 Set ID 与 Node ID 一致，locator 只差 Block，运维友好。
4. Set 按需分配、可不连续；汇总是 256:1。
5. 真正的容量约束是"区域数 × 预留"，不是节点数。
