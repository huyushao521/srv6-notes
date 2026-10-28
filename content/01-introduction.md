# 01 · SRv6 导论：为什么是 SRv6

> 对应原书第 1 章 *Introduction*。阅读方式：**灰底英文是原书节选（保留原文表述），其后的中文是逐段讲解与工程解读。**

## 1.1 一张网取代三张网

:::en
IPv4 networks have been augmented with many overlay and underlay technologies over the years: MPLS for VPN and traffic engineering, VXLAN for Layer 2 extension in the data center, and entropy labels or deep packet inspection for load balancing. Each of them solves a real problem, and each of them adds a protocol, a gateway and an operational burden. SRv6 makes the radical but simple bet that IPv6, with a small architectural addition, can do all of it natively.
:::

IPv4 网络这些年被不断"打补丁"：VPN 和流量工程靠 MPLS，数据中心二层延伸靠 VXLAN，负载分担靠熵标签或深度报文检测。每一个补丁都解决过真问题，但也都带来一套新协议、一类新网关和一份新运维负担。SRv6 的赌注很大也很简单：**IPv6 只要加一点点架构能力，就能原生地把这些全做掉。**

```text
IPv4  →  MPLS(LDP/RSVP/BGP3107) → MP-BGP VPNv4    ← VPN / TE
IPv4  →  VXLAN/GRE + UDP        → EVPN            ← 二层延伸
IPv4  →  Entropy Label / DPI    → ECMP            ← 熵
------------------------------------------------------------
IPv6  →  DA = 有序微指令列表    → 转发/VPN/服务链/切片
```

## 1.2 网络程序：状态在报文里，不在路由器里

:::en
The network program is simply an ordered list of micro-instructions, called uSIDs, encoded in the destination address of the IPv6 header. The source decides the path; each transit router only needs to execute the instruction it is pointed at and move the pointer forward. No per-flow state is kept anywhere in the network.
:::

所谓"网络程序"，就是一个微指令（uSID）的有序列表，写在 IPv6 目的地址里。**路径由源端决定**，每台中间路由器只做三件事：读当前指令、执行它、把指针后移。全网任何地方都不保存每流状态——这是 SR 与 RSVP-TE 最本质的分野，也是它能扛住大规模的原因。

## 1.3 安全：围墙花园

:::en
A frequent objection is that IP addresses can be spoofed, so a segment list could be injected from outside. SRv6 answers this the same way MPLS and VXLAN do: the SR domain is a secure walled garden. All SIDs are allocated from a single IPv6 block, packets are encapsulated when they enter the domain and decapsulated when they leave it, and domain routers only accept SRv6 traffic whose outer source address belongs to the domain.
:::

常见的质疑是：IP 地址谁都能写，段列表会不会被外部伪造注入？SRv6 的回答和 MPLS、VXLAN 完全一致：**SR 域是一个安全围墙花园**。所有 SID 都从同一个 IPv6 地址块分配；报文进域封装、出域解封装；域内路由器只接受外层源地址属于本域的 SRv6 报文。域外节点即使伪造一个合法 SID，也无法把报文送进域内——它源地址不在域内前缀里。

> 注意：SRv6 的域内安全等级**不低于** MPLS，它靠的是域边界 + 封装/解封装 + ACL/uRPF，而不是加密。

## 1.4 地址空间：3216

:::en
A uSID container is 128 bits wide: a 32-bit block followed by six 16-bit uSIDs. A single block therefore provides about 57,000 global uSIDs. Most deployments use two blocks — one for minimum cost, one for minimum latency — but plan for 256 blocks, which yields about 15 million global uSIDs. 256 blocks out of the FC00::/7 private space consume less than 0.00153% of it.
:::

一个 uSID 容器正好 128 bit：**32 bit Block + 6 个 16 bit uSID**。单个 Block 提供约 5.7 万个全局 uSID。主流部署只用两个 Block（一个 min-cost、一个 min-delay），但规划上按 256 个 Block 预留 —— 合计约 **1500 万个全局 uSID**。256 个 /32 只相当于一个 /24，占 `FC00::/7` 私有空间的 **0.00153%**。地址从来不是瓶颈，缺的是规划纪律。

```text
|  Block 32b  |  uSID 16b  |  uSID 16b  | ... |  uSID 16b  |
   fdbb:bb00       0007         0100                0000
```

## 1.5 不需要重新编址

:::en
Unlike MPLS, which required a separate label space with its own allocation and signaling, SRv6 reuses the existing IPv6 addressing. Locators are carved out of existing loopback prefixes, so introducing SRv6 does not force a re-addressing of the network. This is the property operators care about most when the change window is small and the network is large.
:::

MPLS 需要一套独立的标签空间，自己分配、自己信令；SRv6 直接复用现有 IPv6 地址。Locator 就是从现网 Loopback 前缀里划出来的一段，因此**引入 SRv6 不必重编全网地址**。对网络大、割接窗口小的运营商来说，这一条比任何性能数字都重要。

## 1.6 Global uSID 与 Local uSID

:::en
A global uSID is known to every node in the domain: it means "follow the shortest path to that node". A local uSID is only meaningful on the node that allocated it: it might mean "exit through this specific link" or "look up this VRF". Since a local instruction is only valid on one router, it is usually preceded by a global instruction that brings the packet to that router first.
:::

**全局 uSID** 域内所有节点都认识，语义是"沿最短路径去那台机器"；**本地 uSID** 只有分配它的那台机器能执行，语义可能是"从这条链路出去"或"在这张 VRF 里查表"。正因为本地指令只在一台路由器上有效，它前面通常要先跟一条全局指令，把包送到那台机器上。

| 类型 | 谁能执行 | 例子 | MPLS 类比 |
|---|---|---|---|
| Global（uN） | 域内所有节点 | 走到 7 号节点 | Node / Prefix-SID |
| Local（uA） | 仅分配节点 | 从 Et0/0/0/1 出去 | Adj-SID |
| Local（uDT4/uDX2…） | 仅分配节点 | 解封装进 VRF / 出二层口 | VPN / PW 标签 |

## 1.7 最长匹配是免费的压缩引擎

:::en
Because forwarding is based on longest prefix match, a router can install a single /48 entry for its locator and never look at the bits beyond it — those bits are the next instruction. This single property allows one lookup to execute two instructions (a uN plus a uA, for example), allows 16-bit and 32-bit uSIDs to coexist in the same program, and allows /48 prefixes to be summarized into /40 aggregates.
:::

转发靠最长前缀匹配，于是路由器只要装一条自己 Locator 的 /48 表项，**后面的位它根本不用看**——那些位就是下一条指令。仅凭这一条性质，SRv6 就能做到：一次查表执行两条指令（例如 uN + uA）、16 bit 与 32 bit uSID 在同一程序里混用、以及把 256 个 /48 汇总成一个 /40。MPLS 的标签栈做不到任何一条。

## 1.8 SRH 只在必要时出现

:::en
Many people assume SRv6 always requires a Segment Routing Header. It does not. Up to six uSIDs fit inside the 128-bit destination address, and no SRH is needed. Beyond six, an SRH is pushed, carrying 16-byte container SIDs. All current production deployments require fewer than six uSIDs per program.
:::

很多人以为 SRv6 一定带 SRH，其实不是。**6 条以内 uSID 全部塞进 128 bit 目的地址，不需要 SRH**；超过 6 条才压 SRH，里面装的是 16 字节容器 SID。目前所有生产部署的程序都在 6 条以内。

| 程序所需 uSID 数 | 是否带 SRH | SRH 中容器 SID 数 |
|---|---|---|
| 5 | 否 | — |
| 6 | 否 | — |
| 7 | 是 | 1 |
| 12 | 是 | 1 |
| 13 | 是 | 2 |
| 18 | 是 | 2 |

:::en
In a 2022 demonstration, a Cisco NCS router based on Broadcom J2 merchant silicon encapsulated at line rate with an SRH carrying 30 uSIDs, while the MPLS dataplane could impose only about ten labels at line rate. The uSID dataplane, twenty years younger, already outperformed its ancestor by a factor of three.
:::

2022 年的一次公开测试里，基于 Broadcom J2 商用芯片的 NCS 路由器可以**线速**压入携带 30 条 uSID 的 SRH；而同场对比的 MPLS 数据面线速只能压十个左右的标签。晚诞生二十年的 uSID 数据面，能力是前辈的三倍。

## 1.9 规模账本

| 维度 | MPLS | SRv6 uSID |
|---|---|---|
| 域内唯一节点数 | ~0.8M | 15M（可扩至 240M） |
| 单节点唯一业务数 | ~0.2M | 512k（8k LIB + 8 个 Wide-LIB） |
| 线速可压 SID/标签 | ~12 | 26（J2 实测 30） |
| 熵来源 | DPI 或 Entropy Label | Flow Label（20 bit，固定浅位置） |
| 路由汇总 | 无 | 有（/48 → /40，256:1） |
| 跨域网关 | 需要协议翻译网关 | 不需要，统一 IPv6 |

:::en
Bell Canada reported that adopting SRv6 uSID can reduce carrier network service cost by up to 90% in OPEX, shrink equipment footprint by 75% and power consumption by as much as 66% per central office when service programming is used, while removing MPLS gateways and the BGP 3107 complexity tax.
:::

Bell Canada 给出的数字是：采用 SRv6 uSID 后，载波网络业务成本（OPEX）最多下降 **90%**，机房设备占地下降 **75%**，启用服务编程后单局功耗最多下降 **66%**，同时也删掉了 MPLS 网关和 BGP 3107 那笔"复杂度税"。

## 1.10 历史与四条原则

:::en
In January 2017, a small group of operator engineers met in Rome and set the direction: do not invent a new protocol, strengthen IP itself. Rakuten later published production measurements showing latency, reliability and cost all improving at the same time. Four principles guided the work: strengthen IP, it must make business sense, festina lente (make haste slowly), and less is more.
:::

2017 年 1 月，几位运营商工程师在罗马闭门定下方向：**不发明新协议，只增强 IP 本身**。后来 Rakuten 公布了生产网测量结果——时延、可靠性、成本三条曲线同时向好。整个工作由四条原则约束：增强 IP；必须有商业意义；欲速则不达（标准化与互通先行）；能删的层就删。

## 实战案例：一次"删层"决策的算账过程

**场景**：某运营商城域网现状 `接入(IPv4) → 汇聚(MPLS/LDP) → 核心(SR-MPLS) → DC(VXLAN/EVPN)`，域边界上 3 类网关（LDP↔SR、MPLS↔VXLAN、IPv4↔IPv6），每次扩容都要在网关上开会话、加表项、加故障点。

**按本章逻辑重构的四步**：

1. **统一数据面**：全网（含 DC 与主机 smartNIC）只保留 SRv6 uSID 一种封装，DC 侧不再需要 VXLAN 网关。
2. **统一地址**：从 `fdbb:bb00::/24` 取 Block，`/32` 按算法分、`/40` 按区域分、`/48` 按节点分，把原本散在 MPLS 标签、VXLAN VNI、VRF 里的标识收拢到一处。
3. **删掉网关**：域边界从"协议翻译"变成 L2/L3 直连，故障域收敛，运维对象从 4 套协议栈变成 1 套。
4. **熵改用 Flow Label**：入口 PE 哈希一次写入 Flow Label，P 节点按 `(SA, DA, FlowLabel)` 做 ECMP，DPI 与 Entropy Label 全部下线。

**排障要点**：

- 检查"围墙"是否真的闭合：若域外报文能在边界被解封装，说明 ACL/uRPF 没做，SRv6 的安全前提不成立。
- uSID Block 与现网 IPv6 业务地址**绝不能重叠**，否则最长匹配会把业务流量导进 SID 表项。
- 别按"必须带 SRH"去规划 MTU，先按无 SRH 算，再为 TI-LFA 与服务链预留余量（详见第 10 章）。

## 本章小结

1. SRv6 = 用 IPv6 地址承载有序指令列表；无状态，状态在报文里。
2. 五条关键性质：围墙花园、边缘到边缘、3216、免重编址、最长匹配压缩。
3. SRH 是例外而非常态；6 条以内全在 DA 中。
4. 决策依据永远是这四条：规模、熵、汇总、删网关。
