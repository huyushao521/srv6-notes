# 10 · SRv6 网络部署：地址规划、MTU 与安全

> 对应原书第 10 章 *SRv6 Deployment*。这是全书最能直接抄进设计文档的一章：**地址怎么分层、Set 怎么汇总、MTU 怎么算、安全边界怎么划、怎么从 MPLS 平滑演进。**

## 10.1 地址分层：Space → Block → Set → Node

:::en
A scalable SRv6 addressing plan is hierarchical: an SRv6 Space, then one uSID block per algorithm, then sets of 256 uSIDs inside each block, then node IDs inside each set. Every level is a prefix, so every level can be summarized. The hierarchy is what makes an SRv6 network scale to tens of thousands of nodes without an explosion of IGP state.
:::

可扩展的 SRv6 地址规划是分层的：

```text
SRv6 Space    /24 或 /20     ← 一个运营商独占
  └ Block     /32            ← 每个算法一个
     └ Set    /40            ← 每 256 个 uSID 一组，按区域/机房分配
        └ Node /48           ← 每个节点一个 uN
           └ Function        ← uA / uDT / uDX
```

每一层都是前缀，**每一层都能汇总**。正是这个层级让 SRv6 网络能扩到几万节点而不炸 IGP 表。

:::en
In the example operator of the book, the space is fcbb:bb00::/24, one block per algorithm (fcbb:bb00::/32 for algorithm 0 and fcbb:bb01::/32 for Flex-Algo 128), set 0x01 for the core region, three sets for region 1 and two sets for region 2. Only six sets out of 224 are used, leaving 218 for growth.
:::

书中示例运营商的规划：Space 取 `fcbb:bb00::/24`，每个算法一个 Block（`fcbb:bb00::/32` 对应 Algo 0，`fcbb:bb01::/32` 对应 Flex-Algo 128）；核心区用 Set ID `0x01`，区域 1 用三个 Set（`0x02/0x03/0x04`，600 节点），区域 2 用两个 Set（`0x05/0x06`，400 节点）。224 个 Set 只用了 6 个，**剩下 218 个留给增长**。

:::en
The operator deliberately avoids set ID zero, so that the set prefix is not merely a longer version of the block prefix and remains visually distinguishable in show commands and configurations.
:::

一个很实用的细节：**故意不用 Set ID 0**。否则 Set 前缀与 Block 前缀只差长度（`fcbb:bb00::/40` 与 `fcbb:bb00::/32`），在命令行和配置里极易混淆；用 `0x01` 起，前缀一眼可分。

## 10.2 Set 与汇总

:::en
Because each set is a /40, border routers can advertise one /40 summary per set into the core, instead of 256 individual /48 locators. That is a 256-to-1 reduction, and it is the reason the core can stay small while the number of nodes grows.
:::

每个 Set 就是一个 /40，边界路由器**每个 Set 只向核心通告一条 /40**，而不是 256 个 /48。压缩比 256:1，核心表项不随节点数线性增长。

```text
Region 1 (600 节点):
  fdbb:bb00:0200::/40  ← Set 0x02 汇总
  fdbb:bb00:0300::/40  ← Set 0x03 汇总
  fdbb:bb00:0400::/40  ← Set 0x04 汇总
增长后追加:
  fdbb:bb00:0700::/40  ← Set 0x07 汇总（不要求连续）
```

Set 之间**不必连续**，扩容时随便挑一个空闲 Set 即可——这也是分层规划相对"等分地址"的优势（详见第 14 章 Bell 的算账）。

## 10.3 Loopback 与 Locator 的关系

:::en
Two kinds of loopback addresses coexist: the locator loopback, used as the source of SRv6 encapsulated traffic and as the node identifier in the IGP, and independent loopback addresses used by other protocols. Keeping them separate simplifies troubleshooting and avoids changing the locator when the IGP topology changes.
:::

两类 Loopback 并存：

| 类型 | 用途 | 注意 |
|---|---|---|
| Locator loopback | SRv6 封装源地址、IGP 节点标识 | 必须稳定，变更影响全网红 |
| 独立 loopback | 其他协议（BGP router-id、管理面） | 与 SRv6 解耦，便于排障 |

## 10.4 MTU：最容易低估的一项

:::en
SRv6 adds an outer IPv6 header of 40 bytes, plus an SRH when more than six uSIDs are required. The SRH size depends on the number of container SIDs: 8 bytes of fixed header plus 16 bytes per container. In the common case of no SRH, the overhead is exactly 40 bytes; with one SRH carrying one container SID, it is 64 bytes.
:::

开销计算：

```text
无 SRH（≤6 条 uSID）:      40 字节
1 个容器 SID 的 SRH:       40 + 8 + 16 = 64 字节
2 个容器 SID 的 SRH:       40 + 8 + 32 = 80 字节
```

:::en
Operators therefore raise the underlay MTU, typically to 1600 bytes or more, so that customer packets of 1500 bytes never need fragmentation. Relying on path MTU discovery is fragile in an SRv6 domain: ICMPv6 messages may be filtered, and a lost PMTUD message turns into a silent black hole for large packets only.
:::

因此运营商通常把 Underlay MTU 提到 **1600 字节以上**，让 1500 字节的客户报文永远不需要分片。依赖 PMTUD 在 SRv6 域内很脆弱：ICMPv6 可能被过滤，一条丢失的 PMTUD 消息就变成"只有大包不通"的静默黑洞——比全不通更难查。

## 10.5 安全边界

:::en
The SR domain boundary must be explicit. On edge interfaces, ACLs drop packets whose outer source address is not part of the SRv6 space, and uRPF is enabled where the topology allows it. Interior interfaces accept SRv6 traffic only from interior neighbors. Without this, the walled garden is a claim rather than a fact.
:::

SR 域边界必须显式加固：

| 位置 | 措施 |
|---|---|
| 域外入向接口 | ACL 丢弃"外层源地址不属于 SRv6 Space"的报文 |
| 客户侧接口 | 不接受任何带 SRv6 封装的报文（防注入） |
| 域内接口 | 只接受来自域内邻居的 SRv6 流量；可行时开 uRPF |
| 管理面 | 只允许域内地址访问 SID 相关控制面 |

:::en
A second, less obvious exposure is the SID list itself: an SRH delivered to an untrusted endpoint reveals the internal topology. This is exactly what the PSP flavor is for — the penultimate endpoint removes the SRH before the packet reaches a node that should not see the path.
:::

第二个不那么显眼的暴露面是 **SID 列表本身**：带 SRH 的报文送到不可信末端，就把内部拓扑泄露出去了。这正是 **PSP flavor** 的用途——倒数第二个端点先把 SRH 删掉，末端看不到路径。

## 10.6 无缝演进路径

:::en
MPLS and SRv6 can coexist for a long time. A PE that supports both can advertise the same VPN route with both an MPLS label and an SRv6 SID; the ingress chooses the encapsulation based on the next hop's capability. This allows the migration to proceed island by island, with gateways only at the boundaries between islands.
:::

MPLS 与 SRv6 可以长期共存：双栈 PE 对同一条 VPN 路由同时携带 MPLS 标签与 SRv6 SID，入口按下一跳能力选择封装。于是迁移可以**一个区域一个区域地做**，只在"孤岛"边界放互通网关，最终网关全部下线。

```text
阶段 1: 核心 SRv6, 边缘 MPLS        → 边界网关
阶段 2: 区域 A 全 SRv6              → 网关下沉
阶段 3: 全网 SRv6, MPLS 仅回退      → 网关删除
阶段 4: 删 LDP / BGP3107 / 熵标签   → 纯 IPv6 数据面
```

## 实战案例：19,000 节点网的地址与 MTU 决策

**输入**：81 个区域（1 个 L2 骨干 + 80 个 L1），节点数 19,720，单区最大 700 节点。

**规划**：

1. Space 取 ULA 的一小段；每个算法一个 Block（Algo 0 / 128 / 129 共 3 个）。
2. 每区按节点数分配 1~3 个 Set（700 / 256 ≈ 3），Set ID 全局唯一、不连续也无所谓。
3. 边界路由器按 Set 做 /40 汇总，核心 IGP 表项 ≈ 区域数 × Set 数，而非节点数。
4. Underlay MTU 设 1600，边缘按客户 MTU 1500 计算余量；为 TI-LFA（可能压 SRH）留 24 字节额外余量。

**结果**：核心表项从"万级 locator"降到"百级 /40"，且新增区域只需分配一个新 Set + 一条汇总。

**检查清单**：

| 项 | 判据 |
|---|---|
| 地址重叠 | Space 与现网 IPv6 业务地址无交集 |
| Set 余量 | 已用 Set < 50%，且每区预留 ≥ 1 个 |
| 汇总一致 | 边界通告的 /40 与内部实际 /48 完全覆盖 |
| MTU | 所有链路 ≥ 1600，且 PMTUD 不被阻断 |
| 安全 | 域边界 ACL/uRPF 已生效并定期审计 |

## 本章小结

1. 分层地址（Space/Block/Set/Node）是可扩展性的根，Set 的 256:1 汇总是核心。
2. 刻意避开 Set ID 0，减少人工误判。
3. MTU 按"40 字节起、含 SRH 64/80 字节"预留，别依赖 PMTUD。
4. 安全靠域边界 ACL/uRPF + PSP 隐藏 SID list。
5. 演进靠双栈 PE 与孤岛式迁移，最后删网关。
