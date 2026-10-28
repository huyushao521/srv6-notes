# 06 · SRv6 L3VPN

> 对应原书第 6 章 *SRv6 L3VPN*。这是运营商把 SRv6 变成收入的第一站：**用 uSID 替掉 per-VRF 的 VPN 标签**，把 MP-BGP VPNv4/VPNv6 原封不动地平移到 IPv6 数据面。

## 6.1 三种封装业务行为

:::en
An L3VPN service in SRv6 is implemented by endpoint behaviors that decapsulate the packet and forward it in a particular VRF. End.DT4 looks up the inner IPv4 packet in the VRF table, End.DT6 does the same for IPv6, and End.DT46 handles both families. In the micro-segment encoding these are called uDT4, uDT6 and uDT46 — the last two hex digits of the SID identify the VRF.
:::

SRv6 里的 L3VPN 由"解封装 + 在指定 VRF 查表转发"这一类端点行为实现：

| 行为 | 处理内层 | uSID 别名 | 用途 |
|---|---|---|---|
| End.DT4 | IPv4 查 VRF 表 | uDT4 | IPv4 VPN |
| End.DT6 | IPv6 查 VRF 表 | uDT6 | IPv6 VPN |
| End.DT46 | 按内层版本分别查表 | uDT46 | 双栈 VPN（最常用） |
| End.DX4 | 从指定接口发出（不查 VRF） | uDX4 | PE-CE 直连、无 VRF |
| End.DX6 | 同上（IPv6） | uDX6 | 同上 |

:::en
End.DX4 and End.DX6 do not consult a VRF table at all: they strip the outer header and send the packet out of a specific interface. They are used when the egress PE is directly connected to the customer edge and no lookup is required, which saves both a table and a lookup.
:::

`End.DX4/DX6` 完全不查 VRF 表：剥掉外层头后直接从**指定接口**发出去。用在出口 PE 与 CE 直连、无需查表的场景，省一张表、省一次查找。

## 6.2 SID 分配模式

:::en
There are two common allocation models. With per-VRF allocation, each VRF on the PE gets one SID from the locator; the SID identifies the VRF. With per-CE allocation, each CE-facing attachment gets its own SID, which is useful when the PE has many VRFs or when the same VRF is attached to several CEs and you want to distinguish them.
:::

两种主流分配：

| 模式 | 粒度 | 优点 | 代价 |
|---|---|---|---|
| **per-VRF** | 每 VRF 一个 SID | 简单、表项少 | VRF 多时消耗 locator 空间 |
| **per-CE / per-interface** | 每个 CE 接入点一个 SID | 可精确定向到某条接入链路 | SID 数量随接入点增长 |

多数运营商用 per-VRF；只有需要"从特定 PE-CE 链路出"时（例如差异化回程）才用 per-CE 的 `End.DX`。

## 6.3 BGP 如何携带 SID

:::en
The VPN route is advertised exactly as before, with an MP-BGP VPNv4 or VPNv6 update carrying the route target and the RD. What is new is the BGP Prefix-SID attribute: RFC 9252 defines the SRv6 L3 Service TLV, which carries the endpoint behavior and the SID itself. The ingress PE receives the route, learns the SID from the attribute, and pushes it as the last instruction of the program.
:::

VPN 路由的通告方式**完全没变**：还是 MP-BGP VPNv4/VPNv6，还是 RT + RD。新增的是 **BGP Prefix-SID 属性**——RFC 9252 定义的 SRv6 L3 Service TLV，里面携带端点行为与 SID 本身。入口 PE 收到路由，从属性里学到 SID，把它作为程序的最后一条指令压进去。

```text
VPNv4 update:
  RD: 100:1   Prefix: 10.1.1.0/24   RT: 100:1
  Prefix-SID (SRv6 L3 Service TLV):
     Behavior = End.DT46
     SID      = fc00:0:5:e001::
```

:::en
Because the SID is carried in BGP and not in the IGP, the core does not need to know about VRFs at all. This is the BGP-free core principle: P routers only forward on locators, and all VPN state lives at the edge.
:::

SID 走 BGP 而**不走 IGP**，所以核心完全不需要知道 VRF 的存在——这就是 **BGP-free core**：P 路由器只按 locator 转发，所有 VPN 状态都在边缘。

## 6.4 SID 转置（Transposition）

:::en
The transposition mechanism separates the SID into a routable part and a service part: the egress advertises a locator plus an argument that encodes the VPN identifier, so that many VPNs can share one locator space and even one function. It saves SID space and keeps the advertised locator stable when services are added, at the cost of a slightly more complex dataplane.
:::

转置机制把 SID 拆成"可路由部分 + 业务部分"：出口 PE 通告 locator + 一段编码 VPN 标识的 argument，于是**多个 VPN 可以共享同一个 locator 空间、甚至同一个 function**。好处是省 SID、且新增业务时通告的 locator 不变；代价是数据面处理稍复杂。阿里在超大规格场景里正是用 WLIB + 这类机制解决 8000 个本地 SID 不够用的问题。

## 6.5 完整转发过程

```text
PE1（入）:
  1. CE1 的 IPv4 报文到达 PE1 的 VRF-100 接口
  2. 查 VPN 路由 10.1.1.0/24 → 下一跳 PE3，SID = fc00:0:5:e001::
  3. 压外层：SA=PE1 locator, DA=fc00:0:5:e001::, NH=4(IPv4)
  4. 按 DA 转发（P 路由器只看 locator）

PE3（出）:
  5. DA 命中本地 uDT46 SID → 剥外层
  6. 内层 IPv4 在 VRF-100 查表 → 出 CE 接口
```

:::en
Notice that only two instructions are needed in the common case: the destination PE's locator is encoded in the SID itself, so no additional uN is required. The whole program fits in the destination address and no SRH is pushed. This is why L3VPN is the workload where uSID saves the most overhead.
:::

注意常见场景只需**一条指令**：目的 PE 的 locator 已经包含在 SID 里，不需要额外的 uN。整个程序就在目的地址中，**不压 SRH**。这就是 L3VPN 在 uSID 下开销最小的原因（对比 MPLS 需要两层标签 + 外层传输标签）。

## 实战案例：从 MPLS L3VPN 平滑迁移到 SRv6 L3VPN

**背景**：某运营商 300 台 PE，几千个 VRF，现网 MPLS L3VPN，计划分三批迁移。

**迁移策略**：

1. **共存期**：PE 同时支持 MPLS 与 SRv6，同一条 VPN 路由通过 BGP 携带两种封装信息（MPLS 标签 + SRv6 SID）。入口 PE 按"下一跳能力"选择封装，域边界设备做互通。
2. **按区域收口**：先在一个区域内部全 SRv6，区域间仍走 MPLS；验证业务、性能、故障恢复后再推下一个区域。
3. **切默认**：区域全 SRv6 后，把"优先 SRv6 封装"设为默认，MPLS 仅作回退。
4. **清理**：全网 SRv6 后删除 LDP、BGP 3107、互通网关。

**验证清单**：

| 项目 | 方法 |
|---|---|
| SID 学习正确 | `show bgp vpnv4 unicast <prefix>` 看 Prefix-SID 属性 |
| 转发表项 | `show segment-routing srv6 sid` / `show cef vrf` |
| 双栈业务 | DT46 同时验证 IPv4/IPv6 内层 |
| MTU | 迁移后封装变小（无 SRH），但 TI-LFA 期间会变大，需预留 |
| 故障切换 | 拔纤验证 TI-LFA + BGP PIC 组合行为 |

**典型故障**：迁移后部分站点业务通、部分不通 → 多半是出口 PE 的 SID 从 locator 分配时与其他业务冲突，或某个 VRF 没配 SID；用 `show segment-routing srv6 locator` 与 BGP 属性对照即可定位。

## 本章小结

1. L3VPN = `End.DT4/DT6/DT46`（uDT\*）；无 VRF 时用 `End.DX4/DX6`。
2. SID 分配按需选 per-VRF 或 per-CE；per-VRF 最常用。
3. SID 由 BGP Prefix-SID（RFC 9252）携带，核心保持 BGP-free。
4. 常见场景单条指令即可完成，无 SRH，开销小于 MPLS。
