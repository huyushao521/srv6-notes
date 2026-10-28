# 10 · SRv6 部署：地址、MTU、安全与演进

> **本章定位**：原书第 10 章《SRv6 Deployment》。这是全书**最能直接抄进设计文档**的一章：地址怎么分层、Set 怎么汇总、MTU 怎么算、安全边界怎么划、怎么从 MPLS 平滑演进。英文块为原文摘录，中文为完整翻译，Figure 10.1–10.5 重绘，Example 10.1–10.4 保留。

**本章要拿到的东西**：

| 问题 | 对应小节 |
|---|---|
| Space / Block / Set / Node 各多长，谁汇总谁 | 10.1 |
| 为什么 Set ID 从 `0x01` 开始，不用 0 | 10.1.1 |
| 一个 Set 能装多少节点，全网要多少个 Set | 10.1.2 |
| 核心表项为什么是"百级"而不是"万级" | 10.2 |
| Loopback 为什么要两套 | 10.3 |
| MTU 到底预留多少（40 / 64 / 80） | 10.4 |
| 安全边界在哪，PSP 解决什么 | 10.5 |
| 怎么"孤岛式"演进，最后删什么 | 10.6 |

这一章没有新协议，全是**决策**。而决策一旦写进设计文档就很难改——**地址规划错了要重编全网，MTU 错了要逐链路返工**。所以本章的重点是**算清楚再落笔**。

## 10.1 地址分层：Space → Block → Set → Node

:::en
A scalable SRv6 addressing plan is hierarchical: an SRv6 Space, then one uSID block per algorithm, then sets of 256 uSIDs inside each block, then node IDs inside each set. Every level is a prefix, so every level can be summarized. The hierarchy is what makes an SRv6 network scale to tens of thousands of nodes without an explosion of IGP state.
:::

可扩展的 SRv6 地址规划是**分层**的：先有 **SRv6 Space**，其下**每个算法一个 uSID Block**，Block 内再切**每 256 个 uSID 一组（Set）**，Set 内是**节点 ID**。**每一层都是前缀，所以每一层都能汇总**——正是这个层级让 SRv6 网络能扩到几万节点而**不炸 IGP 表**。

```text
图 10-1：四层结构与位宽（原书 Figure 10.1 重绘）

  fcbb : bb00 : 01 : 00 ::
  ├──────┴──────┴────┴─┤
  │      │      │   └── Function / Argument（uA、uDT、uDX…）
  │      │      └────── Node（/48，一个 uN，一台设备）
  │      └───────────── Set（/40，256 个 Node）
  └──────────────────── Block（/32，一个算法一个）

  层级         长度      数量级                可汇总为
  ─────────────────────────────────────────────────────
  SRv6 Space   /24–/20  1 个运营商              —
  Block        /32      每算法 1 个            /32
  Set          /40      每 Block 256 个        /40  ← 汇总点
  Node         /48      每 Set 256 个          /48
  Function     /64+     每 Node 65,536 个      —
```

:::en
In the example operator of the book, the space is fcbb:bb00::/24, one block per algorithm (fcbb:bb00::/32 for algorithm 0 and fcbb:bb01::/32 for Flex-Algo 128), set 0x01 for the core region, three sets for region 1 and two sets for region 2. Only six sets out of 224 are used, leaving 218 for growth.
:::

书中示例运营商的规划：

| 层级 | 取值 | 说明 |
|---|---|---|
| Space | `fcbb:bb00::/24` | 运营商独占的一段 |
| Block（Algo 0） | `fcbb:bb00::/32` | 默认算法 |
| Block（Algo 128） | `fcbb:bb01::/32` | 低时延 Flex-Algo |
| Set 核心区 | `0x01` | 核心骨干节点 |
| Set 区域 1 | `0x02 / 0x03 / 0x04` | 600 节点（3 个 Set） |
| Set 区域 2 | `0x05 / 0x06` | 400 节点（2 个 Set） |

**224 个 Set 只用了 6 个，剩下 218 个留给增长。**

:::en
The operator deliberately avoids set ID zero, so that the set prefix is not merely a longer version of the block prefix and remains visually distinguishable in show commands and configurations.
:::

一个很实用的细节：**故意不用 Set ID 0**。否则 Set 前缀与 Block 前缀**只差长度**（`fcbb:bb00::/40` 与 `fcbb:bb00::/32`），在命令行和配置里**极易混淆**；从 `0x01` 起，前缀一眼可分。

### 10.1.1 为什么这些"小规矩"值钱

| 规矩 | 不遵守的后果 |
|---|---|
| 每算法一个 Block | Flex-Algo 无法用"前缀"区分，只能靠元数据/策略，排障困难 |
| Set 从 `0x01` 起 | `show` 输出里 `fcbb:bb00::/32` 与 `/40` 混淆，误删误配 |
| Set 全局唯一、允许不连续 | 扩容时必须找连续空闲段，规划被"绑死" |
| Node 用 16 bit（`pfx-16`） | 容器深度变化，uSID 编码与硬件行为不匹配 |
| Function 层留出 Argument | 转置（第 6 章）与 Wide uSID（第 7 章）无空间可用 |

### 10.1.2 容量实算：需要几个 Set

```text
全网节点数 N = 19,720，单区最大 700
每 Set = 256 个 Node

① 按"全局平均"算下限：  19,720 / 256 ≈ 78 个 Set
② 按"单区最大"算：      700 / 256 ≈ 2.7 → 每区至少 3 个 Set
③ 按"每区预留 ≥1 个"：   81 区 × (2.7 + 1) ≈ 300 个 Set  ← 这才是真实需求
④ 检查 Block 容量：       /32 Block 有 256 个 Set（8 bit）

结论：256 个 Set 的 Block 刚好够 81 个区域用（含预留），
      余量不足 → 应扩到 /31 或 /30 的 Block，或用第二个 Block
```

:::en
The arithmetic matters because a block with an 8-bit set field provides only 256 sets. An operator with 81 regions, each needing three sets plus one for growth, consumes more than 300 sets, which does not fit. The fix is to widen the block (for example to a /30) so that the set field grows, rather than to squeeze regions into fewer sets.
:::

这个账必须算，因为 **8 bit 的 Set 字段只有 256 个 Set**。有 81 个区域、每区 3 个 Set 再加 1 个预留，就**超过 300 个**，**装不下**。正确的解法是**加宽 Block**（例如 `/30`）让 Set 字段变长，而**不是把区域硬塞进更少的 Set**。

| Block 长度 | Set 字段位数 | Set 总数 | 适用规模 |
|---|---|---|---|
| `/32` | 8 | 256 | ≤ 60 个区域 |
| `/30` | 10 | 1,024 | ≤ 250 个区域 |
| `/28` | 12 | 4,096 | 大型全国网 |

## 10.2 Set 与汇总

:::en
Because each set is a /40, border routers can advertise one /40 summary per set into the core, instead of 256 individual /48 locators. That is a 256-to-1 reduction, and it is the reason the core can stay small while the number of nodes grows.
:::

每个 Set 就是一个 `/40`，边界路由器**每个 Set 只向核心通告一条 `/40`**，而不是 256 个 `/48`。**压缩比 256:1**，核心表项**不随节点数线性增长**——这是"核心能保持小、节点数却能长"的根本原因。

```text
图 10-2：汇总边界（原书 Figure 10.2 重绘）

        核心（只装 /40）
        ┌──────────────────────────────────┐
        │  fdbb:bb00:0200::/40  ← Set 0x02 │
        │  fdbb:bb00:0300::/40  ← Set 0x03 │
        │  fdbb:bb00:0400::/40  ← Set 0x04 │
        └───────────────┬──────────────────┘
                        │ ABR（汇总点）
        ┌───────────────┴──────────────────┐
        │ 区域 1（600 节点，只装 /48）      │
        │  fdbb:bb00:0201::/48 … 256 条     │
        │  fdbb:bb00:0301::/48 … 256 条     │
        │  fdbb:bb00:0401::/48 …  88 条     │
        └──────────────────────────────────┘

  核心表项：3 条（而非 600 条）
```

```text
例 10.1：区域 1 的 Set 规划与增长
Region 1 (600 节点):
  fdbb:bb00:0200::/40  ← Set 0x02 汇总
  fdbb:bb00:0300::/40  ← Set 0x03 汇总
  fdbb:bb00:0400::/40  ← Set 0x04 汇总
增长后追加:
  fdbb:bb00:0700::/40  ← Set 0x07 汇总（不要求与 0x04 连续）
```

Set 之间**不必连续**，扩容时随便挑一个空闲 Set 即可——这正是分层规划相对"等分地址"的优势（第 14 章 Bell 的算账把这点算到了极致）。

| 汇总方式 | 核心表项 | 故障域 | 备注 |
|---|---|---|---|
| 不汇总 | 节点数（万级） | 全网 | 不可接受 |
| 按 Set 汇总（/40） | Set 数（百级） | 单 Set | **推荐** |
| 按区域汇总（多 Set 合一） | 区域数（十级） | 单区域 | 精度下降，慎用 |
| 按 Block 汇总 | 1 | 全网 | 仅极端场景 |

## 10.3 Loopback 与 Locator

:::en
Two kinds of loopback addresses coexist: the locator loopback, used as the source of SRv6 encapsulated traffic and as the node identifier in the IGP, and independent loopback addresses used by other protocols. Keeping them separate simplifies troubleshooting and avoids changing the locator when the IGP topology changes.
:::

**两类 Loopback 并存**：

| 类型 | 用途 | 注意 |
|---|---|---|
| **Locator loopback** | SRv6 封装源地址、IGP 节点标识 | 必须稳定；变更**影响全网** |
| **独立 loopback** | BGP router-id、管理面、其他协议 | 与 SRv6 解耦，便于排障 |

:::en
Note that the locator loopback address is itself a SID with the End behavior, and the last SID of an encapsulated packet is often the uN of the egress node. This means the source address of SRv6 traffic and the destination of the segment list share the same addressing hierarchy, which is what allows a single IGP advertisement to serve both purposes.
:::

注意 **locator loopback 本身就是一个 `End` 行为的 SID**，而封装报文的**最后一段往往就是出口节点的 uN**。这意味着 **SRv6 流量的源地址与段列表的目的地址共享同一套编址层级**——一次 IGP 通告就能同时满足两个用途。

**例 10.2：两套 loopback 的配置**

```text
interface Loopback0
 description MGMT / BGP router-id
 ipv4 address 192.0.2.1 255.255.255.255
 ipv6 address 2001:db8:100::1/128
!
interface Loopback100
 description SRv6 LOCATOR loopback
 ipv6 address fdbb:bb00:0201::1/128
!
segment-routing
 srv6
  locators
   locator MAIN
    micro-segment behavior unode pfx-16
    prefix fdbb:bb00:0201::/48
   !
  !
 !
!
router isis 1
 interface Loopback0
  passive
  address-family ipv6 unicast
  !
 !
 interface Loopback100
  passive
  address-family ipv6 unicast
  !
 !
!
```

**排障价值**：把两套地址分开后，"ping 不通"能立刻分成两类——**ping `2001:db8:100::1` 不通 = 控制面/路由问题**；**ping `fdbb:bb00:0201::` 不通 = locator 泄露/汇总/SRv6 问题**。混用一套地址时，这两类故障无法区分。

## 10.4 MTU：最容易低估的一项

:::en
SRv6 adds an outer IPv6 header of 40 bytes, plus an SRH when more than six uSIDs are required. The SRH size depends on the number of container SIDs: 8 bytes of fixed header plus 16 bytes per container. In the common case of no SRH, the overhead is exactly 40 bytes; with one SRH carrying one container SID, it is 64 bytes.
:::

SRv6 封装**加 40 字节外层 IPv6 头**，当**超过 6 条 uSID** 时需要再加 **SRH**。SRH 的大小取决于容器 SID 个数：**固定头 8 字节 + 每个容器 SID 16 字节**。常见情形下**无 SRH，开销恰好 40 字节**；**带一个容器 SID 的 SRH 则是 64 字节**。

```text
图 10-3：MTU 开销（原书 Figure 10.3 重绘）

  无 SRH（≤6 条 uSID）:       40 字节
  1 个容器 SID 的 SRH:        40 + 8 + 16 = 64 字节
  2 个容器 SID 的 SRH:        40 + 8 + 32 = 80 字节
  3 个容器 SID 的 SRH:        40 + 8 + 48 = 96 字节

  客户报文 1500 → 核心链路需求：
    无 SRH      1540
    SRH×1       1564
    SRH×2       1580
  → 统一取 1600（留 20–60 字节余量给未来 flavor/扩展头）
```

:::en
Operators therefore raise the underlay MTU, typically to 1600 bytes or more, so that customer packets of 1500 bytes never need fragmentation. Relying on path MTU discovery is fragile in an SRv6 domain: ICMPv6 messages may be filtered, and a lost PMTUD message turns into a silent black hole for large packets only.
:::

因此运营商通常把 **Underlay MTU 提到 1600 字节以上**，让 1500 字节的客户报文**永远不需要分片**。依赖 PMTUD 在 SRv6 域内很脆弱：**ICMPv6 可能被过滤**，一条丢失的 PMTUD 消息就变成"**只有大包不通**"的静默黑洞——比全不通更难查。

| MTU 方案 | 取值 | 优点 | 缺点 |
|---|---|---|---|
| 保守 | 1540 | 改动最小 | 无余量，加 SRH 就超 |
| **推荐** | **1600** | 覆盖 SRH×1~2，留余量 | 需要逐链路核查 |
| 激进 | 9000 | 一劳永逸，覆盖 jumbo 存储 | 老设备/微波不支持 |
| 依赖 PMTUD | 1500 | 不改配置 | **不可靠，不推荐** |

**例 10.3：MTU 全域核查（割接前必做）**

```text
! ① 列出所有链路 MTU（人工核对，或用脚本采集）
show interfaces | include "MTU|line protocol"

! ② 二分法探测实际路径 MTU（1472 是 1500 环境下 ICMP 的经典值）
ping fdbb:bb00:0202:: size 1400 repeat 3
ping fdbb:bb00:0202:: size 1472 repeat 3

! ③ 带 SRv6 封装的真实业务探测
ping vrf CUSTOMER-100 10.1.2.1 size 1472 repeat 3
```

判据：**步骤 ② 通、③ 不通 = MTU；② 不通 = 路由/locator**。这个二分能在一分钟内把两类问题分开。

## 10.5 安全边界

:::en
The SR domain boundary must be explicit. On edge interfaces, ACLs drop packets whose outer source address is not part of the SRv6 space, and uRPF is enabled where the topology allows it. Interior interfaces accept SRv6 traffic only from interior neighbors. Without this, the walled garden is a claim rather than a fact.
:::

**SR 域边界必须显式加固**：边缘接口上用 **ACL 丢弃"外层源地址不属于 SRv6 Space"的报文**，拓扑允许时开 **uRPF**；域内接口**只接受来自域内邻居的 SRv6 流量**。不这么做，"walled garden"就只是**说法**，不是事实。

| 位置 | 措施 | 防什么 |
|---|---|---|
| 域外入向接口 | ACL 丢弃外层源 ≠ SRv6 Space 的报文 | 伪造源地址注入 |
| 客户侧接口 | 不接受任何带 SRv6 封装的报文 | 客户伪造 SID 穿透核心 |
| 域内接口 | 只接受域内邻居的 SRv6 流量；可行时开 uRPF | 域内横向渗透 |
| 管理面 | 只允许域内地址访问 SID 相关控制面 | 未授权配置 |
| 控制面 | 保护 IGP/BGP 会话（MD5/keychain、TTL 安全） | 会话劫持 |

:::en
A second, less obvious exposure is the SID list itself: an SRH delivered to an untrusted endpoint reveals the internal topology. This is exactly what the PSP flavor is for — the penultimate endpoint removes the SRH before the packet reaches a node that should not see the path.
:::

第二个不那么显眼的暴露面是 **SID 列表本身**：带 SRH 的报文送到**不可信末端**，就把**内部拓扑泄露**出去了。这正是 **PSP flavor** 的用途——**倒数第二个端点先把 SRH 删掉**，末端看不到路径。

```text
图 10-4：安全边界与 PSP（原书 Figure 10.4 重绘）

  域外                     SR 域                     客户侧
  ──►[ACL: src ∉ Space ✘]──►[P]──►[P]──►[PE]──►[CE]
                                  │        │
                                  │        └─ PSP: 到达 CE 前 SRH 已删
                                  └─ uRPF + 只信域内邻居

  没有 ACL：任何伪造 src = fdbb:bb00:: 的报文都能进核心
  没有 PSP：客户侧抓包即可还原内部 SID 列表与拓扑
```

| flavor | 全称 | 作用 | 是否解决"拓扑泄露" |
|---|---|---|---|
| PSP | Penultimate Segment Pop | 倒数第二跳弹出 SRH | **是**（主要用途） |
| USP | Ultimate Segment Pop | 最后一跳弹出 | 部分 |
| USD | Ultimate Segment Decapsulation | 最后一跳解封装 | 否 |

## 10.6 无缝演进路径

:::en
MPLS and SRv6 can coexist for a long time. A PE that supports both can advertise the same VPN route with both an MPLS label and an SRv6 SID; the ingress chooses the encapsulation based on the next hop's capability. This allows the migration to proceed island by island, with gateways only at the boundaries between islands.
:::

MPLS 与 SRv6 **可以长期共存**：双栈 PE 对**同一条 VPN 路由同时携带 MPLS 标签与 SRv6 SID**，入口**按下一跳能力选择封装**。于是迁移可以**一个区域一个区域地做**，只在"孤岛"边界放互通网关，**最终网关全部下线**。

```text
图 10-5：四阶段演进（原书 Figure 10.5 重绘）

  阶段 1: 核心 SRv6，边缘 MPLS     → 边界放互通网关
  阶段 2: 区域 A 全 SRv6           → 网关下沉到区域边界
  阶段 3: 全网 SRv6，MPLS 仅回退   → 网关删除（保留配置回退）
  阶段 4: 删 LDP / BGP 3107 / 熵标签 → 纯 IPv6 数据面
```

| 阶段 | 判据（可以进下一阶段的条件） | 风险 |
|---|---|---|
| 1 → 2 | 核心 SRv6 稳定运行 ≥ 1 个月，无 P1 故障 | 网关成为单点，需双网关 |
| 2 → 3 | 至少 2 个区域全 SRv6，业务指标无劣化 | 区域间策略需重新验证 |
| 3 → 4 | 全网无 MPLS-only 设备，回退窗口已过 | **不可逆操作，需变更评审** |
| 4 完成后 | 标签池、LDP、3107 全部清理，配置基线归档 | 遗留标签残留导致隐性依赖 |

:::en
The last step is the one operators most often postpone: removing LDP and label allocation from a network that no longer needs them. Leaving them in place is not free — it keeps label-space planning, protocol state, and troubleshooting complexity alive long after the encapsulation that required them is gone.
:::

最后一步是运营商**最常拖延**的一步：在**已经不需要**它们的网络里**移除 LDP 与标签分配**。留着**不是免费的**——它会**让标签空间规划、协议状态、排障复杂度长期存在**，而需要它们的封装早已消失。

## 10.7 部署检查清单

| 类别 | 检查项 | 判据 |
|---|---|---|
| 地址 | Space 与现网 IPv6 业务地址无交集 | 无重叠前缀 |
| 地址 | 每算法一个 Block | Algo 0/128/129 各有独立 /32 |
| 地址 | Set 已用 < 50%，每区预留 ≥ 1 | 表格化登记 |
| 地址 | Block 宽度够（Set 数 ≥ 区域数 × 4） | 见 10.1.2 实算 |
| 汇总 | 边界通告的 /40 完全覆盖内部 /48 | 无遗漏、无多余 |
| 汇总 | 汇总后 IGP 表项 = Set 数级 | 非节点数级 |
| Loopback | 两套分离（locator / mgmt） | 各自在 IGP 中 passive |
| MTU | 所有链路 ≥ 客户 MTU + 40（建议 1600） | 含微波/互联段 |
| MTU | PMTUD 不被阻断，或已钳制 MSS | 大包探测通过 |
| 安全 | 域边界 ACL + uRPF 生效 | 定期审计 |
| 安全 | PSP 在不可信末端启用 | 客户侧抓包无 SRH |
| 演进 | 双栈 PE 可同时通告两种封装 | `show bgp` 两类信息都在 |
| 演进 | 回退路径可在一小时内恢复 | 演练记录 |

## 10.8 本章小结

:::en
The deployment chapter is an exercise in getting the irreversible decisions right the first time: the addressing hierarchy determines how far the network can grow, the MTU determines whether large packets survive, and the SR domain boundary determines whether the walled garden is real.
:::

部署这一章本质是"**把不可逆的决策一次做对**"：**地址层级决定网络能长多大，MTU 决定大包能不能活，SR 域边界决定 walled garden 是真是假。**

| 决策 | 一次做对的价值 | 做错的代价 |
|---|---|---|
| Block/Set 宽度 | 加区只需分配新 Set | **重编全网地址** |
| Set 汇总点 | 核心表项百级 | 核心表项万级，收敛变慢 |
| MTU = 1600 | 大包永不分片 | **逐链路返工**，且故障隐蔽 |
| 双套 loopback | 故障可二分定位 | 排障靠猜 |
| 域边界 ACL/uRPF | 攻击面收敛 | 随时可能被注入 |
| 演进四阶段 | 可回退、可并行 | 大爆炸式割接，风险集中 |

一句话收束：**SRv6 的复杂不在协议，在规划**。协议都在 RFC 里写死了，`Block` 切多宽、`Set` 留多少、`MTU` 取多少，**只有你自己能决定，而且改起来最贵**。

## 实战案例

### 案例 A：19,720 节点网的地址与 MTU 决策

**输入**：81 个区域（1 个 L2 骨干 + 80 个 L1），节点数 19,720，单区最大 700 节点。

**规划**：

```text
① Space 取 ULA 的一小段；每算法一个 Block（Algo 0 / 128 / 129 共 3 个）
② 每区按节点数分配 1~3 个 Set（700 / 256 ≈ 3），Set ID 全局唯一，
   不连续也无所谓
③ 边界路由器按 Set 做 /40 汇总
   核心 IGP 表项 ≈ 区域数 × Set 数，而非节点数
④ Underlay MTU 设 1600，边缘按客户 MTU 1500 计算余量；
   为 TI-LFA（可能压 SRH）留额外 24 字节
```

**结果**：核心表项从"**万级 locator**"降到"**百级 /40**"，新增区域只需**分配一个新 Set + 一条汇总**。

**检查清单**（与原书一致）：

| 项 | 判据 |
|---|---|
| 地址重叠 | Space 与现网 IPv6 业务地址无交集 |
| Set 余量 | 已用 Set < 50%，且每区预留 ≥ 1 个 |
| 汇总一致 | 边界通告的 /40 与内部实际 /48 完全覆盖 |
| MTU | 所有链路 ≥ 1600，且 PMTUD 不被阻断 |
| 安全 | 域边界 ACL/uRPF 已生效并定期审计 |

### 案例 B：Set 规划不足，扩容时被迫重编地址

**现象**：某省级网按 `/32` Block 规划，用掉 40 个 Set 后开始紧张；新开 20 个地市时发现**只剩 30 个 Set**，而每地市需要 2–3 个。

```text
① 原始规划：/32 Block = 8 bit Set 字段 = 256 个 Set
   当时评估"256 个 Set 足够"，因为按"节点数 12,000 / 256 = 47"计算
② 实际需求：每地市独立 Set（为了按地市汇总、按地市做故障隔离）
   → 需求 = 地市数 × (Set/地市 + 预留) = 60 × 3 ≈ 180
③ 加上 Flex-Algo 第二个 Block 也要同构规划，压力翻倍
④ 结果：只剩 30 个 Set，无法继续按"地市一个 Set"扩容
⑤ 补救：扩 Block 到 /30（Set 字段 10 bit = 1,024 个），
   但已分配的地址不能动 → 新地市用新 Block，形成"双 Block 共存"
⑥ 代价：运维要维护两套地址规则，排障时先判断"SID 在哪个 Block"
```

**教训**：

1. **Set 需求要按"汇总边界 + 故障隔离边界"算，不是按"节点数 / 256"算**；
2. **Block 宁可一次给宽**（`/30` 甚至 `/28`），地址用不完不花钱，**改地址要花几个月**；
3. 预留不是"留 20%"，而是"**每区至少 1 个，且总量 ≥ 需求 × 1.5**"。

### 案例 C：一条 1500 的互联链路，让整改全部回滚

**现象**：全网 MTU 整改到 1600 完成两周后，跨运营商互联的一条链路（对端设备不支持 >1500）导致**只有该方向的大包不通**，业务表现为"部分用户上传失败"。

```text
① ping 小包正常 → 误判为"应用问题"，排查了两天
② 用 ping size 1472 复现 → 定位到 MTU
③ show interface 该互联口 → MTU 1500（整改清单漏项，
   因为它不在"核心链路"分类里）
④ 方案：
   a. 短期：该互联口做 MSS 钳制 + 保证 ICMPv6 PTB 放行
   b. 长期：与对端协商升级 MTU，或把该互联移出 SRv6 域（走网关）
```

**教训**：**MTU 清单要按"拓扑自动发现"生成，不能按"人工分类"生成**——漏掉的永远是分类外的那条。

## 延伸阅读

- **RFC 8200**：IPv6 报文格式与分片规则（中间节点不分片，是 MTU 问题的根源）。
- **RFC 8754**：SRH 格式，8 字节固定头 + 16 字节/段的计算依据。
- **RFC 8986**：`End` 及 PSP/USP/USD flavor，10.5 的拓扑隐藏手段。
- **RFC 9259**：OAM，验证部署正确性的手段（第 9 章）。
- **RFC 6724 / RFC 4291**：地址选择与格式，ULA（`fc00::/7`）的使用依据。
- 交叉参考：第 3 章（locator 与行为）、第 5 章（泄露与汇总的 IGP 细节）、第 6 章（转置对 Address 空间的影响）、第 14/15 章（两家运营商的实际规划与算账）。
