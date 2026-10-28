# 14 · 案例：Bell Canada 的 SRv6 地址规划

> **本章定位**：原书第 14 章，与 Bell Canada 技术总监 **Daniel Voyer** 合作撰写。**这是全书唯一给出完整生产级地址算账的章节**，可以直接当模板复用到自己的规划里。英文块为原文摘录，中文为完整翻译，Figure 14.1–14.4 重绘。

**本章要拿到的东西**：

| 问题 | 对应小节 |
|---|---|
| Bell 为什么从 SR-MPLS 转向 SRv6 | 14.1 |
| 19,720 个节点、81 个区域怎么切地址 | 14.2、14.3 |
| 为什么"每个算法一个 Block" | 14.3 |
| "跨 Block 保持 Set/Node ID 一致"带来什么 | 14.3.1 |
| Set 按需分配与按区域平均，差多少 | 14.4 |
| 224 个 Set 到底够不够（真实的约束是什么） | 14.6 |
| 从主机到容器，为什么不需要 MPLS 了 | 14.7 |

一句话概括：**Bell 的规划之所以能当模板，是因为它把"地址"变成了"可加总、可汇总、可预测"的工程物**——每一个决策都能算出一个数，而不是"看起来够用"。

## 14.1 背景与动机

:::en
Bell Canada is the largest communications company in Canada. It deployed one of the earliest SR-MPLS networks in 2017, and the first benefit it realized was TI-LFA protection. Because of the compelling advantages of SRv6 uSIDs, Bell then transitioned to SRv6, replacing the complexity of MPLS at the host, socket and container level, and removing the need for SR-MPLS, LDP and SRv6 gateways at the data center and network edge.
:::

Bell 是**加拿大最大的通信公司**。**2017 年它就建成了最早的一批 SR-MPLS 网络**，**第一个真正落地的收益是 TI-LFA 保护**。后来因为 **uSID 的优势太明显**，转向 SRv6：**主机 / 套接字 / 容器层面不再需要 MPLS**，**数据中心与网络边缘也不再需要 SR-MPLS / LDP / SRv6 网关**。

这条演进路径值得单独记住——**它不是"跳过 SR-MPLS 直接上 SRv6"，而是"先用 SR-MPLS 拿到保护，再用 SRv6 拿到端到端"**：

```text
图 14-1：Bell 的两步走（原书 Figure 14.1 重绘）

  2017  SR-MPLS（Segment Routing over MPLS）
        ✔ TI-LFA 保护（第一个收益）
        ✘ 主机/容器侧仍需 MPLS 栈
        ✘ DC 与边缘仍需 SR-MPLS / LDP / SRv6 网关

  之后  SRv6 + uSID
        ✔ 端到端（host → socket → container）统一为 IPv6
        ✔ 删掉边缘与 DC 的互通网关
        ✔ 获得 IGP 汇总能力（MPLS 做不到）
```

:::en
The reported benefits include a potential reduction of up to 90% in carrier network service OPEX, a 75% reduction in equipment footprint, and as much as 66% reduction in power consumption per central office when service programming is used. SRv6 uSID also removes the BGP 3107 complexity tax and enables IGP summarization, which MPLS cannot do.
:::

公开的数字：

| 指标 | 降幅 | 来源 |
|---|---|---|
| 载波业务 OPEX | **最多 90%** | 服务编程 + 自动化 |
| 设备占地（footprint） | **75%** | 网关/设备退场、局所合并 |
| 单局功耗 | **最多 66%** | 服务编程取代专用设备 |
| BGP 3107 复杂度 | **删除** | uSID 不需要 3107 承载 |
| IGP 汇总能力 | **新增** | MPLS 标签无法汇总，IPv6 前缀可以 |

最后一项是**技术上最本质的差异**：**MPLS 标签是"平的"，无法汇总；IPv6 前缀是"分层的"，可以汇总**。这一条直接决定了"核心表项随节点数增长还是随区域数增长"（14.5）。

## 14.2 网络结构：81 个区域、19,720 个节点

:::en
Bell operates a multi-level IS-IS network with a level-2 backbone and up to 80 level-1 areas, for a total of 81 areas. The network is expected to have around 19,000 nodes considering mid-term growth. Area sizes vary between 100 and 700 nodes: 48 small areas of up to 150 nodes, 25 medium areas of up to 300 nodes, and 7 large areas of up to 700 nodes.
:::

Bell 跑的是**多级 IS-IS**：**1 个 L2 骨干 + 最多 80 个 L1 区域，共 81 个区域**；考虑中期增长，全网约 **19,000+ 节点**。**区域规模从 100 到 700 不等**：

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

这个分布是规划的关键：**小区域远多于大区域**。**若给每个区域平均分配 Set，小区浪费一大片、大区又不够涨**——这是最典型的错误分配方式（第 10.1.2 节算过：按平均分 19,720 / 81 ≈ 243 个 uSID，看似可行，实践不可取）。

## 14.3 地址规划：一个 Space、三个 Block、224 个 Set

:::en
Bell designates a small portion of the ULA range, fd00::/8, as the SRv6 space: 0.0015% of this space is enough. Using ULA provides excellent addressing scale, and also network opacity and privacy, since ULAs are not routable outside the domain.
:::

Bell 从 **`fd00::/8`（ULA 私有空间）** 里取极小一段作为 SRv6 Space——**只占 0.0015%**。用 ULA 有两个好处：

1. **地址规模充裕**（`fd00::/8` 有 2^120 个地址）；
2. **ULA 在域外不可路由**，天然带来**网络不透明性与隐私性**。

| 选择 | 规模 | 风险 | Bell 的选择 |
|---|---|---|---|
| 公网 IPv6（2000::/3） | 大 | 与外部路由冲突、安全暴露 | ✘ |
| **ULA（fc00::/7，取 fd00::/8）** | 极大 | 需自管唯一性 | **✔** |
| 普通私有段（如 fdxx 小段） | 够用 | 后期扩展受限 | 部分运营商用 |

:::en
They allocate one uSID block per algorithm: fdbb:bb00::/32 for algorithm 0 (minimum cost), fdbb:bb01::/32 for Flex-Algo 128 (minimum delay), and fdbb:bb02::/32 for Flex-Algo 129 (restrict link). Each block provides about 57,000 global uSIDs, which exceeds current requirements.
:::

**每个算法一个 Block**：

| Block | 算法 | 用途 |
|---|---|---|
| `fdbb:bb00::/32` | Algo 0 | 最短路（最低成本） |
| `fdbb:bb01::/32` | Flex-Algo 128 | 最小时延 |
| `fdbb:bb02::/32` | Flex-Algo 129 | 限制链路（绕行/排除） |

单个 Block 提供约 **57,000** 个全局 uSID（224 Set × 256），对 19,720 节点的网络**绰绰有余**。

**为什么"每算法一个 Block"而不是"一个 Block 里分 Function"**：

| 方案 | 地址形态 | Flex-Algo 切流怎么做 | 排障难度 |
|---|---|---|---|
| 每算法一个 Block | `fdbb:bb00::/32`、`fdbb:bb01::/32` | **SID 前缀直接体现算法** | 看前缀即知算法 |
| 单 Block 多 Function | 同前缀，靠 Function 位区分 | 需查映射表 | 看 SID 不能直接判断 |

第一条是**运维可见性**的胜利：**trace 出来一看是 `fdbb:bb01` 就知道走了低时延平面**，不需要查任何表（第 9 章的案例 A 就是靠这个定位的）。

:::en
Sets simplify the allocation: each set holds 256 uSIDs and is represented by a /40. A block contains 224 sets, with set IDs from 0x00 to 0xdf, for global uSID allocation. One or more sets are allocated to each region, and a region gets the same set IDs from every block. A node gets the same set ID and node ID in every block, so its locators differ only in the block ID.
:::

**Set 是分配的基本单位**：一个 Set 装 **256 个 uSID**，对应一个 **`/40`**；一个 Block 有 **224 个 Set**（ID `0x00`–`0xdf`）用于全局分配。

规则极其干净：

1. **每个区域分配一到多个 Set**；
2. **同一区域在每个 Block 里拿相同的 Set ID**；
3. **同一节点在每个 Block 里拿相同的 Set ID + Node ID**。

### 14.3.1 三条规则的价值：一个节点只有"一段"不同

```text
图 14-2：同一节点在三个 Block 里的 locator（原书 Figure 14.2 重绘）

  Algo 0     : fdbb:bb00:080e::/48
  Algo 128   : fdbb:bb01:080e::/48
  Algo 129   : fdbb:bb02:080e::/48
                └─┬──┘ └┬┘└┬┘
               Block  Set Node(=14=0x0e)

  → 三个 locator 只在第 3 个 16 bit 段不同（Block ID）
  → Set 与 Node 完全一致
```

| 带来的好处 | 具体表现 |
|---|---|
| **人眼可换算** | 看到 `080e` 就知道是 Set 0x08 的 0x0e 号节点，任意算法通用 |
| **脚本可生成** | 配置模板只需替换 Block 字段，不会错位 |
| **排障可推断** | trace 出 `fdbb:bb02:080e::` 立即知道"该节点在绕行平面" |
| **扩容可预测** | 新节点在三个 Block 里都拿同一个 Set/Node，一步完成 |

:::en
This consistency is not cosmetic: it means that the three locators of a node can be generated from a single pair of numbers, which removes an entire class of configuration errors during provisioning and makes cross-algorithm troubleshooting mechanical rather than investigative.
:::

这种一致性**不是为了好看**：它意味着**一个节点的三个 locator 可以由"一对数字"生成**，从而**消除配置下发时的一整类错误**，并让**跨算法排障从"调查"变成"机械换算"**。

## 14.4 Set 分配模型：按需，不按平均

:::en
The allocation model is not equal-sized per area. Small areas get one set (256 uSIDs for up to 150 nodes), medium areas get two, and large areas get three, with additional sets assigned on demand. Sets allocated to one region need not be contiguous: growth simply takes the next free set.
:::

分配模型**不是按区域平均**，而是按需：

| 区域规模 | 节点数 | Set 数 | uSID 容量 | 余量 |
|---|---|---|---|---|
| 骨干 | 120 | 1 | 256 | 136 |
| 小 | ≤150 | 1 | 256 | 106 |
| 中 | ≤300 | 2 | 512 | 212 |
| 大 | ≤700 | 3 | 768 | 68 |

Set **不必连续**：区域长大了，**从空闲池里再拿一个 Set** 就行，**边界路由器加一条 `/40` 汇总即可**。

```text
图 14-3：Set 池的分配（原书 Figure 14.3 重绘）

  Set ID: 00 01 02 03 04 05 06 07 08 09 ... df   （共 224 个）
          │  │  │  │  │  │  │  │  │  │
          │  │  └──┴──┘  │  │  └──┘  │       已分配（按区域，不连续）
          │  │  区域 A   │  区域 C   │
          │  │           └─ 区域 B    └─ 区 D（新开）
          │  └─ 骨干
          └─ 刻意留空（或给未来最大区域）

  区域 A 扩容：直接拿走 0x0a → 新增一条 fdbb:bb00:0a00::/40 汇总
  → 不需要移动任何已分配地址
```

:::en
The decision to allow non-contiguous sets is what makes the plan maintainable over a decade: contiguous allocation looks tidier on paper, but it forces address renumbering whenever a region grows into the wrong direction. Non-contiguous allocation trades a little tidiness for the complete elimination of renumbering.
:::

**允许 Set 不连续，是这份规划能维护十年的原因**：连续分配**在纸面上更整齐**，但它会在**区域朝错误方向增长时逼出重新编址**。不连续分配**用一点整齐度，换掉了"重新编址"这件事本身**。

## 14.5 汇总与增长：核心表项随区域数增长

:::en
The set structure leads naturally to summarization: 256 /48 prefixes collapse into one /40, a 256-to-1 gain. Border routers of each region advertise one summary per assigned set into the core. When a region outgrows its sets, the operator assigns another set and adds one more summary prefix.
:::

Set 结构天然带来汇总：**256 个 `/48` → 1 个 `/40`，256:1**。**每个区域的边界路由器按"已分配的 Set"向核心通告汇总，一个 Set 一条**。区域扩容时，**加一个 Set、加一条汇总**——**核心表项随区域数增长，不随节点数增长**。

| 汇总粒度 | 核心表项数（本案例） | 故障域 | 评价 |
|---|---|---|---|
| 不汇总（每节点 /48） | 19,720 | 单节点 | 不可接受 |
| **按 Set 汇总（/40）** | **约 224** | 单 Set（≤256 节点） | **Bell 的选择** |
| 按区域汇总（多 Set 合一） | 约 81 | 单区域（≤700 节点） | 精度下降 |
| 按 Block 汇总 | 3 | 全网 | 仅极端场景 |

```text
图 14-4：核心视角的差别（原书 Figure 14.4 重绘）

  无汇总：核心装 19,720 条 /48        → SPF/LSP 规模大，收敛慢
  按 Set 汇总：核心装 ~224 条 /40      → 规模降两个数量级
  按区域汇总：核心装 ~81 条 /36~38     → 更小，但定位精度差

  Bell 选"按 Set"：在"规模"与"故障定位精度"之间取平衡点
```

:::en
Summarization at the set level also bounds the blast radius of a change: a new node in a region only modifies the set summary if the set is new, and a failure inside a set is contained to that set's 256 nodes. This is the operational reason to summarize at /40 rather than at the block level.
:::

**按 Set 汇总还限定了变更的爆炸半径**：**区域内新增节点，只有在"新开 Set"时才会改动汇总**；而**一个 Set 内部的故障被限制在该 Set 的 256 个节点里**。这就是**在 `/40` 而不是 Block 级做汇总的运维理由**。

## 14.6 容量实算：真正的约束不是节点数

这是本章最值得抄的一段——**224 个 Set 听起来很多，实际不一定够**。

```text
例 14.1：224 个 Set 到底够不够

需求 = 区域数 × 每区 Set 数（含预留）

按 Bell 的实际情况（按需分配，不预留太多）:
  骨干 1×1 + 小 48×1 + 中 25×2 + 大 7×3
  = 1 + 48 + 50 + 21 = 120 个 Set         → 224 够，余 104

按"每区预留 1 个"的保守策略:
  1×2 + 48×2 + 25×3 + 7×4
  = 2 + 96 + 75 + 28 = 201 个 Set         → 224 勉强够，余 23

按"三算法各自独立规划 + 每区预留 1 个":
  = 201 × 1（因为 Set ID 跨 Block 复用）   → 仍 201，够
  但若三算法各用独立 Set 池（不复用）:
  = 603 个 Set                            → 224 远远不够！

② 关键洞察：
   Bell 的"跨 Block 复用相同 Set ID"不是省事，而是【直接把需求除以 3】
   没有这条规则，224 个 Set 只够 1/3 的规模
```

| 规划方式 | Set 需求 | 224 够吗 | 说明 |
|---|---|---|---|
| 跨 Block 复用 Set ID，按需分配 | 120 | ✔ 充裕 | **Bell 的做法** |
| 跨 Block 复用 Set ID，每区预留 1 | 201 | ✔ 勉强 | 留 23 给新开区 |
| 每算法独立 Set 池 | 603 | ✘ | 必须加宽 Block |
| 每区平均分（224/81 ≈ 2.7） | 224 | ✘ 局部 | 大区不够，小区浪费 |

:::en
The capacity constraint is therefore a product of two numbers that are easy to overlook: the number of regions and the reserve factor per region. Node count enters only indirectly, through the number of sets needed to hold the largest area. A plan that is sized on node count alone will look sufficient and fail on the first region split.
:::

所以真正的容量约束是**两个容易被忽略的数的乘积**：**区域数 × 每区预留系数**。**节点数只是间接进入**（通过"最大区域需要几个 Set"）。**只按节点数做容量的规划，看起来够用，却会在第一次"区域拆分"时失败。**

## 14.7 从主机到容器：为什么不再需要 MPLS

:::en
With SRv6 uSIDs, the same addressing hierarchy extends from the provider edge into the data center and into the host networking stack. A container can be assigned a SID from the same space as a router, which means the first hop of a service chain is not a gateway but the workload itself.
:::

用 SRv6 uSID 时，**同一套编址层级从 PE 一直延伸到数据中心、延伸到主机网络栈**。**一个容器可以从"和路由器相同的空间"里分配到一个 SID**，这意味着**服务链的第一跳不再是网关，而是工作负载本身**。

| 层次 | MPLS 时代 | SRv6 uSID 时代 |
|---|---|---|
| 骨干路由器 | MPLS 标签 | IPv6 + uSID |
| PE / 边缘 | SR-MPLS 或 SRv6 网关 | 直接 SRv6 |
| DC 网关 | 需要封装转换 | **不需要**（同一封装） |
| 主机 / socket | 需要 MPLS 栈（几乎没人做） | **原生 IPv6** |
| 容器 | 需 sidecar / CNI 转换 | **可直接持有 SID** |

:::en
This is the real reason the equipment footprint drops: every boundary that used to require a translation device is now just a router, because there is nothing to translate. The 75% footprint reduction is not primarily a hardware shrink; it is the removal of encapsulation conversion points.
:::

这才是**设备占地下降的真实原因**：**过去每一个需要"转换设备"的边界，现在只是一台路由器**，因为**没有东西需要转换**。**75% 的占地下降主要不是硬件变小，而是"封装转换点"消失了**。

## 14.8 本章小结

:::en
Bell's plan is a template because every choice is arithmetic: one space from ULA, one block per algorithm, 224 sets per block, sets allocated per region on demand with no contiguity requirement, and identical set and node IDs across blocks. The result is a network that summarizes 256:1, grows by adding a set, and stays readable to a human.
:::

Bell 的规划能当模板，是因为**每个选择都是算术**：**ULA 里取一个 Space、每算法一个 Block、每 Block 224 个 Set、Set 按区域按需分配且不要求连续、跨 Block 保持相同 Set/Node ID**。结果是：**现状 256:1 汇总、增长时加一个 Set、对人类可读**。

| 决策 | Bell 的选择 | 一句话理由 |
|---|---|---|
| Space | ULA `fd00::/8` 的 0.0015% | 规模够、域外不可路由 |
| Block | **每算法一个 `/32`** | 前缀即体现算法，排障可见 |
| Set 容量 | 256 个 uSID（`/40`） | 汇总单位 = 分配单位 |
| Set 分配 | **按需、可非连续** | 永不重新编址 |
| 跨 Block 一致性 | **同 Set ID + 同 Node ID** | 需求除以 3、配置可生成 |
| 汇总 | 每 Set 一条 `/40` | 核心表项随区域数增长 |
| 真实约束 | **区域数 × 预留系数** | 不是节点数 |

一句话收束：**地址规划的水平，体现在"能不能用两个数把全网算出来"**。Bell 的答案是：**区域数** 与 **每区 Set 数**。

## 实战案例

### 案例 A：把 Bell 的模型套到一张 2 万节点的网上（原书练习）

**输入**：80 个区域，最大 700 节点，3 个算法。

```text
算账:
① 每区 Set 数 = ⌈节点数 / 256⌉ + 1（预留增长）
   → 小 2、中 3、大 4
② 总 Set 需求 ≈ 48×2 + 25×3 + 7×4 + 1×1 ≈ 200
   → 224 个 Set 几乎用尽
③ 结论：按"预留一个"的保守策略，单个 Block 不够
   → 要么减少预留，要么再开一个 Block
     （地址空间完全允许：256 个 Block 只占 /24）
```

**这正是 Bell 规划里最容易被忽略的一条**：**224 个 Set 听起来很多，但在 80 个区域 × 3 个算法的场景下，真正的约束不是节点数，而是"区域数 × 预留系数"。**

**落地检查表**：

| 项 | 判据 |
|---|---|
| Space 是否与其他业务重叠 | `fdbb:bb00::/24` 与现网无交集 |
| 每区 Set 余量 | ≥ 25% |
| Node ID 唯一性 | 同区内不重复，跨算法保持一致 |
| 汇总覆盖 | 每条 `/40` 完整覆盖内部 `/48` |
| 增长路径 | 剩余 Set 数 ≥ 区域数（应对新开区） |

### 案例 B：照抄 Bell 到省级网，栽在"跨 Block 复用"这一条

**背景**：某省级网（38 个区域，6,800 节点，3 个算法）照抄 Bell 模型，但**每算法独立分配 Set**（"更清晰"），半年后无法扩容。

```text
① 规划：每区 2 个 Set × 3 个算法 × 38 区 = 228 个 Set
   → 单 Block 只有 224 个 Set → 一开始就不够
② 现场做法：把部分区域压到 1 个 Set，勉强塞进去
③ 结果：
   - 大区（600 节点）只有 1 个 Set = 256 个 uSID → 不够，无法加节点
   - 被迫在区内做"二级拆分"，汇总层级乱掉
   - 三个算法的 Set ID 对不上，配置模板全部要写三份
④ 修复（耗时 4 个月）：
   a. 改为"跨 Block 同 Set ID/Node ID"（Bell 的做法）
   b. 需求从 228 降到 76，一个 Block 余量充足
   c. 配置模板恢复单份
```

**教训**：

| 看似"更清晰"的做法 | 实际代价 |
|---|---|
| 每算法独立 Set 池 | 需求 ×3，很快撞墙 |
| Set 连续分配 | 扩容方向受限，易逼出重编址 |
| 每区平均分 | 小区浪费、大区不够 |
| 不给预留 | 新开区无处安放 |

### 案例 C：用 Bell 的"两数模型"做一次招标应答

**场景**：投标要求回答"如何支撑未来 5 年从 15,000 节点增长到 30,000 节点，区域数从 60 增至 85"。

```text
按 Bell 的两数模型：
① 最大区按 800 节点 → 每区 Set = ⌈800/256⌉ = 4（不留预留则 3）
② 总需求 = 85 区 × (3 + 1 预留) = 340 个 Set
③ 224 个 Set 不够 → Block 从 /32 扩到 /30（Set 字段 10 bit = 1,024 个）
④ 结论：地址空间不是瓶颈（/30 只占 ULA 的极小部分），
   真正的瓶颈是【IGP 汇总后的核心表项】= 340 条 /40，
   仍在现代路由器承受范围内（万级前缀）
⑤ 应答要点：
   - 给出 224 → 1,024 的扩容路径，且"不改已分配地址"
   - 给出核心表项测算（340 条），证明可扩展
   - 给出"新开区只需 1 个 Set + 1 条汇总"的操作模型
```

**启示**：**招标应答里"地址够不够"不是重点，"扩容时要不要动存量"才是重点**。Bell 模型的杀伤力就在"**不重新编址**"。

## 延伸阅读

- **RFC 4193**：Unique Local IPv6 Unicast Addresses（ULA），`fd00::/8` 的使用依据。
- **RFC 3849**：IPv6 地址前缀保留示例（文档用）。
- **RFC 8200 / RFC 4291**：IPv6 编址与前缀长度语义，理解 `/40`、`/48` 的分层。
- **draft-ietf-spring-srv6-srh-compression**：uSID 容器与 `pfx-16` 的规范（第 3 章）。
- **RFC 9352 / Flex-Algo 相关**：Algo 128（min-delay）、Algo 129（restrict）的定义。
- 交叉参考：第 10 章（通用部署规划，本章的抽象版）、第 15 章（阿里的双 Block 与 WLIB，另一种解法）、第 5 章（泄露与汇总的 IGP 细节）、第 16 章（Bell SP 的生产服务链）。
