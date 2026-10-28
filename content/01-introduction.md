# 01 · SRv6 导论：为什么是 SRv6

> **本章定位**：原书第 1 章《Introduction》。它不教你配命令，只回答一个问题：**为什么值得把网络的数据面换掉。** 英文块为原文摘录，中文为完整翻译，Figure 1.1–1.3 重绘。

**本章要拿到的东西**：

| 问题 | 对应小节 |
|---|---|
| SRv6 到底"新"在哪，为什么不是 MPLS 的又一次升级 | 1.1、1.2 |
| "状态在报文里"具体指什么，凭什么能扛规模 | 1.2 |
| IP 地址可伪造，段列表会不会被注入 | 1.3 |
| 地址够不够用（3216 是什么意思） | 1.4 |
| 引入 SRv6 要不要重编全网地址 | 1.5 |
| 为什么很多部署根本不用 SRH | 1.8 |
| 决策依据是哪四个数 | 1.9 |

一句话概括：**SRv6 把"路径"从网络里的状态，变成报文里的数据**。所有收益（无状态、免信令、可汇总、可编程）与所有代价（40 字节开销、MTU、设备要认扩展头）都从这一句推出来。

## 1.0 三个必须先回答的问题

| 问题 | 短答案 | 展开在 |
|---|---|---|
| SRv6 是"IPv6 版的 MPLS"吗 | 不是。它取消了"标签"这个对象，改用地址 | 1.1 |
| 为什么不用 SR-MPLS 就够了 | SR-MPLS 仍需要标签分发与标签栈，且**标签无法汇总** | 1.5、1.9 |
| 现在换的时机对吗 | 芯片已经能线速处理，且 MPLS 的"复杂度税"已到临界 | 1.8、1.9 |

## 1.1 一张网取代三张网

:::en
IPv4 networks have been augmented with many overlay and underlay technologies over the years: MPLS for VPN and traffic engineering, VXLAN for Layer 2 extension in the data center, and entropy labels or deep packet inspection for load balancing. Each of them solves a real problem, and each of them adds a protocol, a gateway and an operational burden. SRv6 makes the radical but simple bet that IPv6, with a small architectural addition, can do all of it natively.
:::

IPv4 网络这些年被不断"打补丁"：**VPN 和流量工程靠 MPLS**，**数据中心二层延伸靠 VXLAN**，**负载分担靠熵标签或深度报文检测**。每一个补丁都解决过真问题，但也都带来**一套新协议、一类新网关和一份新运维负担**。SRv6 押的是一个**大胆但简单**的赌注：**IPv6 只要加一点点架构能力，就能原生地把这些全做掉**。

```text
图 1-1：三张网 → 一张网（原书 Figure 1.1 重绘）

  IPv4  →  MPLS(LDP/RSVP/BGP3107) → MP-BGP VPNv4    ← VPN / TE
  IPv4  →  VXLAN/GRE + UDP        → EVPN            ← 二层延伸
  IPv4  →  Entropy Label / DPI    → ECMP            ← 熵
  ──────────────────────────────────────────────────────────
  IPv6  →  DA = 有序微指令列表    → 转发/VPN/服务链/切片
```

代价对账（每一行都是"要维护的东西"）：

| 需求 | IPv4 时代的补丁 | 要维护的对象 | SRv6 里 |
|---|---|---|---|
| VPN | MPLS + MP-BGP（VPNv4/VPNv6）+ 3107 | 标签池、会话、标签绑定 | **一个 SID** |
| 二层延伸 | VXLAN/GRE + EVPN | VTEP 表、VNI 规划 | **一个 SID** |
| 流量工程 | RSVP-TE 或 SR-MPLS 标签栈 | 隧道状态 / 标签栈深度 | **段列表** |
| 负载分担 | Entropy Label 或 DPI | 芯片能力、DPI 性能 | **Flow Label** |
| 服务链 | ACL + PBR + VLAN 引流 | 每台设备一份策略 | **段列表** |

:::en
The bet is not that IPv6 is faster; it is that one encapsulation, one address space and one forwarding behavior can replace three stacks. The savings are operational, not just technical: fewer protocols, fewer gateways, fewer places for a configuration to drift.
:::

这个赌注**不是"IPv6 更快"**，而是**"一种封装、一套地址、一种转发行为，可以替掉三套协议栈"**。省下来的是**运维成本**，不只是技术复杂度：**更少的协议、更少的网关、更少会漂移的配置点**。

## 1.2 网络程序：状态在报文里，不在路由器里

:::en
The network program is simply an ordered list of micro-instructions, called uSIDs, encoded in the destination address of the IPv6 header. The source decides the path; each transit router only needs to execute the instruction it is pointed at and move the pointer forward. No per-flow state is kept anywhere in the network.
:::

所谓"**网络程序**"，就是**一个微指令（uSID）的有序列表，写在 IPv6 目的地址里**。**路径由源端决定**；每台中间路由器只做三件事：**读当前指令、执行它、把指针后移**。**全网任何地方都不保存每流状态。**

```text
图 1-2：程序在包里，指针随转发前移（原书 Figure 1.2 重绘）

  DA:  fdbb:bb00 : 0002 : e100 : 0000 ::
       └───┬───┘   └─┬──┘ └─┬─┘
         Block      uN    uDT46

  在 PE-1：  DA = fdbb:bb00:0002:e100::   → 沿最短路径送往 2 号节点
  在 P-1 ：  只看 /48 前缀 fdbb:bb00:0002:: → 转发（不看后面）
  在 PE-2：  DA 命中本地 uDT46 → 查 VRF → 投递

  没有"隧道状态"、没有"标签绑定"、没有"每流表项"
  唯一的状态就是报文自己
```

| 维度 | RSVP-TE | SR-MPLS | **SRv6 uSID** |
|---|---|---|---|
| 路径状态存在哪 | **每台路由器**（每隧道） | 标签栈（报文里） | **报文里（DA）** |
| 中间节点需要什么 | 隧道状态 | 标签栈处理 | **只看前缀** |
| 扩容时 | 新建隧道、逐跳信令 | 改标签栈 | **改段列表** |
| 故障时 | 逐跳重信令 | 重算标签栈 | **重算段列表** |

这就是 SR 与 RSVP-TE 最本质的分野，也是它能扛住大规模的原因：**规模不来自"更快的协议"，来自"不需要同步的状态"**。

## 1.3 安全：围墙花园

:::en
A frequent objection is that IP addresses can be spoofed, so a segment list could be injected from outside. SRv6 answers this the same way MPLS and VXLAN do: the SR domain is a secure walled garden. All SIDs are allocated from a single IPv6 block, packets are encapsulated when they enter the domain and decapsulated when they leave it, and domain routers only accept SRv6 traffic whose outer source address belongs to the domain.
:::

常见的质疑是：**IP 地址谁都能写，段列表会不会被外部伪造注入？** SRv6 的回答和 MPLS、VXLAN 完全一致：**SR 域是一个安全围墙花园**：

1. **所有 SID 都从同一个 IPv6 地址块分配**（例如 `fdbb:bb00::/24`）；
2. **报文进域封装、出域解封装**；
3. **域内路由器只接受外层源地址属于本域的 SRv6 报文**。

**域外节点即使伪造一个合法 SID，也无法把报文送进域内**——它的**源地址不在域内前缀里**。

```text
图 1-3：围墙的三道门（原书 Figure 1.3 重绘）

  域外 ──►[①ACL: 外层 src ∉ SRv6 Space → 丢]──► 域内
           [②进域封装 / 出域解封装]
           [③域内接口只信域内邻居 + uRPF]

  伪造一个合法 DA？可以，但源地址过不了 ①
  伪造源地址？可以，但过不了 ③ 的反向路径检查
```

:::en
Note the honest framing: SRv6 does not encrypt, and it does not authenticate individual segment lists. Its security model is the same as MPLS and VXLAN — trust the boundary, verify the source, and treat the domain interior as trusted. Anyone who claims SRv6 is "insecure because IP can be spoofed" is applying an end-to-end threat model to a domain technology.
:::

诚实地说清楚：**SRv6 不加密，也不逐条认证段列表**。它的安全模型与 MPLS、VXLAN 相同——**信任边界、校验源地址、把域内当可信**。**任何"因为 IP 可伪造所以 SRv6 不安全"的说法，都是把端到端威胁模型套在域技术头上。**

| 说法 | 是否成立 | 说明 |
|---|---|---|
| 域外可伪造 SID 注入 | **不成立** | 源地址过不了 ACL/uRPF |
| 域内节点可互相攻击 | 成立（与 MPLS 相同） | 域内是可信区，需管理面隔离 |
| 客户侧可探测内部拓扑 | **部分成立** | 用 PSP 隐藏 SRH（第 10 章） |
| SRv6 提供加密 | **不成立** | 需要 IPsec / MACsec 等叠加 |

## 1.4 地址空间：3216

:::en
A uSID container is 128 bits wide: a 32-bit block followed by six 16-bit uSIDs. A single block therefore provides about 57,000 global uSIDs. Most deployments use two blocks — one for minimum cost, one for minimum latency — but plan for 256 blocks, which yields about 15 million global uSIDs. 256 blocks out of the FC00::/7 private space consume less than 0.00153% of it.
:::

一个 uSID 容器正好 **128 bit**：**32 bit Block + 6 个 16 bit uSID**（这就是"**3216**"这个缩写的来源）。**单个 Block 提供约 5.7 万个全局 uSID**。主流部署**只用两个 Block**（一个 min-cost、一个 min-delay），但**规划上按 256 个 Block 预留**——合计约 **1500 万个全局 uSID**。**256 个 /32 只相当于一个 /24**，占 `FC00::/7` 私有空间的 **0.00153%**。

```text
|  Block 32b  |  uSID 16b  |  uSID 16b  | ... |  uSID 16b  |
   fdbb:bb00       0007         0100                0000
   └─ 可路由 ─┘   └─ 全局 uN ─┘ └─ 本地 uF/uA/uDT ─┘

算术：
  1 Block = 2^16 个 uN（65,536）× 2^16 个 function = 4.3e9
  但实际按"节点 × 每节点业务"约束：
    1 Block ≈ 57,000 个全局 uSID
    256 Block ≈ 15,000,000 个全局 uSID
```

| 量级 | 数值 | 对照 |
|---|---|---|
| 单 Block 全局 uSID | ~57,000 | 足够一个省级网 |
| 256 Block 全局 uSID | ~15,000,000 | 足够全球级运营商 |
| 占 ULA 比例 | **0.00153%** | 几乎没有成本 |
| 理论上限（可扩） | ~240,000,000 | 仍只是 ULA 的零头 |

:::en
The point is not the size of the number but the discipline it enables: because the plan is hierarchical, an operator can add a region by allocating one more set, and can summarize 256 locators into one aggregate. Address space is abundant; planning discipline is what is scarce.
:::

重点**不是这个数字有多大**，而是它**支撑的纪律**：因为规划是**分层**的，运营商**加一个区域只需分配一个 Set**，并且能把 **256 个 locator 汇总成一条聚合路由**。**地址abundant，稀缺的是规划纪律。**

## 1.5 不需要重新编址

:::en
Unlike MPLS, which required a separate label space with its own allocation and signaling, SRv6 reuses the existing IPv6 addressing. Locators are carved out of existing loopback prefixes, so introducing SRv6 does not force a re-addressing of the network. This is the property operators care about most when the change window is small and the network is large.
:::

MPLS 需要**一套独立的标签空间**，自己分配、自己信令；**SRv6 直接复用现有 IPv6 地址**。**Locator 就是从现网 Loopback 前缀里划出来的一段**，因此**引入 SRv6 不必重编全网地址**。对**网络大、割接窗口小**的运营商来说，这一条**比任何性能数字都重要**。

| 引入新技术的成本 | MPLS / SR-MPLS | SRv6 |
|---|---|---|
| 地址/标识重新规划 | 需新建标签空间 | **从现有 IPv6 前缀里切** |
| 协议新增 | LDP/RSVP/BGP 3107 | **无（复用 BGP/IGP）** |
| 现网设备地址变更 | 若换标识则需重编 | **不需要** |
| 割接方式 | 分段替换 | **双栈共存、孤岛推进** |

:::en
This is also why SRv6 migration is often described as "island by island": because the address space is shared with ordinary IPv6, an SRv6 island can be introduced next to an MPLS island and connected with a gateway, and the gateway can be removed once the islands merge.
:::

这也是**为什么 SRv6 迁移常被描述为"孤岛式推进"**：因为**地址空间与普通 IPv6 共用**，**一个 SRv6 孤岛可以紧邻 MPLS 孤岛部署，用网关连接**，**两岛合并后网关即可拆除**（第 10.6 节的四阶段）。

## 1.6 Global uSID 与 Local uSID

:::en
A global uSID is known to every node in the domain: it means "follow the shortest path to that node". A local uSID is only meaningful on the node that allocated it: it might mean "exit through this specific link" or "look up this VRF". Since a local instruction is only valid on one router, it is usually preceded by a global instruction that brings the packet to that router first.
:::

- **全局 uSID**：**域内所有节点都认识**，语义是"**沿最短路径去那台机器**"（对应 `uN`）；
- **本地 uSID**：**只有分配它的那台机器能执行**，语义可能是"**从这条链路出去**"（`uA`）或"**在这张 VRF 里查表**"（`uDT46`）。

正因为**本地指令只在一台路由器上有效**，它**前面通常要先跟一条全局指令**，把包送到那台机器上。

| 类型 | 谁能执行 | 例子 | MPLS 类比 |
|---|---|---|---|
| Global（`uN`） | 域内所有节点 | 走到 7 号节点 | Node / Prefix-SID |
| Local（`uA`） | **仅分配节点** | 从 `Hu0/0/0/1` 出去 | Adj-SID |
| Local（`uDT4/uDX2`…） | **仅分配节点** | 解封装进 VRF / 出二层口 | VPN / PW 标签 |

:::en
The consequence is a simple rule for building programs: a local instruction is never useful on its own, because no other node can execute it. Every program is therefore a sequence of global instructions that move the packet, interleaved with local instructions that execute on the node the packet has just reached.
:::

由此得到一条**写程序的简单规则**：**本地指令单独出现是没有意义的**，因为**没有别的节点能执行它**。所以**任何程序都是"全局指令负责移动、本地指令负责执行"的交替序列**——这也解释了后面每一章里**段列表为什么总以 `uN` 或 `uA` 开头**。

## 1.7 最长匹配是免费的压缩引擎

:::en
Because forwarding is based on longest prefix match, a router can install a single /48 entry for its locator and never look at the bits beyond it — those bits are the next instruction. This single property allows one lookup to execute two instructions (a uN plus a uA, for example), allows 16-bit and 32-bit uSIDs to coexist in the same program, and allows /48 prefixes to be summarized into /40 aggregates.
:::

转发靠**最长前缀匹配**，于是路由器**只要装一条自己 Locator 的 `/48` 表项，后面的位它根本不用看**——**那些位就是下一条指令**。仅凭这一条性质，SRv6 就能做到三件事：

1. **一次查表执行两条指令**（例如 `uN` + `uA`）；
2. **16 bit 与 32 bit uSID 在同一程序里混用**（第 15 章的 WLIB）；
3. **把 256 个 `/48` 汇总成一个 `/40`**（第 14 章的 Set 汇总）。

**MPLS 的标签栈做不到任何一条。**

```text
图 1-4：一次查表执行两条指令（原书 Figure 1.2 后半段重绘）

  DA = fdbb:bb00 : 0009 : e001 ::
       └─/32─┘   └─uN─┘ └─uA─┘
                        └─ 本节点只需匹配 /48: fdbb:bb00:0009::
                           ↓
                   命中后看剩余位：e001 → 出 Hu0/0/0/1
                   ★ 一次查表 = uN（到达）+ uA（出链路）

  对比标签栈：需要两个标签、两次弹栈、两次查表
```

| 性质 | 靠什么实现 | 收益 |
|---|---|---|
| 一次查表两指令 | 最长匹配 + 剩余位是 function | 性能、硬件简单 |
| 16/32 bit 混用 | 剩余位长度可变 | 业务可挤进地址（WLIB） |
| `/48` → `/40` 汇总 | 前缀天然分层 | **核心表项降两个数量级** |
| 无需标签分发 | 前缀即可路由 | **删掉 LDP/3107** |

## 1.8 SRH 只在必要时出现

:::en
Many people assume SRv6 always requires a Segment Routing Header. It does not. Up to six uSIDs fit inside the 128-bit destination address, and no SRH is needed. Beyond six, an SRH is pushed, carrying 16-byte container SIDs. All current production deployments require fewer than six uSIDs per program.
:::

**很多人以为 SRv6 一定带 SRH，其实不是。** **6 条以内 uSID 全部塞进 128 bit 目的地址，不需要 SRH**；**超过 6 条才压 SRH**，里面装的是 **16 字节容器 SID**。**目前所有生产部署的程序都在 6 条以内。**

| 程序所需 uSID 数 | 是否带 SRH | SRH 中容器 SID 数 | 外层总开销 |
|---|---|---|---|
| ≤ 6 | **否** | — | **40 B** |
| 7–12 | 是 | 1 | 64 B |
| 13–18 | 是 | 2 | 80 B |

:::en
In a 2022 demonstration, a Cisco NCS router based on Broadcom J2 merchant silicon encapsulated at line rate with an SRH carrying 30 uSIDs, while the MPLS dataplane could impose only about ten labels at line rate. The uSID dataplane, twenty years younger, already outperformed its ancestor by a factor of three.
:::

2022 年的一次公开测试里，基于 **Broadcom J2 商用芯片**的 NCS 路由器可以**线速**压入携带 **30 条 uSID** 的 SRH；而同场对比的 **MPLS 数据面线速只能压十个左右的标签**。**晚诞生二十年的 uSID 数据面，能力是前辈的三倍。**

| 数据面 | 线速可压层数 | 说明 |
|---|---|---|
| MPLS | ~10–12 个标签 | 受芯片标签栈深度限制 |
| SRv6（J2 实测） | **30 条 uSID** | 单次 SRH，容器化编码 |
| SRv6（常规芯片） | 3–8 段 | 招标时要写入指标 |

## 1.9 规模账本

| 维度 | MPLS | SRv6 uSID |
|---|---|---|
| 域内唯一节点数 | ~0.8 M | **15 M**（可扩至 240 M） |
| 单节点唯一业务数 | ~0.2 M | 512 k（8k LIB + 8 个 Wide-LIB） |
| 线速可压 SID/标签 | ~12 | **26**（J2 实测 30） |
| 熵来源 | DPI 或 Entropy Label | **Flow Label**（20 bit，固定浅位置） |
| 路由汇总 | **无** | **有**（/48 → /40，256:1） |
| 跨域网关 | 需要协议翻译网关 | **不需要**，统一 IPv6 |
| 报文开销 | 8 B（两层标签） | **40 B**（无 SRH） |

:::en
Bell Canada reported that adopting SRv6 uSID can reduce carrier network service cost by up to 90% in OPEX, shrink equipment footprint by 75% and power consumption by as much as 66% per central office when service programming is used, while removing MPLS gateways and the BGP 3107 complexity tax.
:::

Bell Canada 给出的数字：**载波网络业务成本（OPEX）最多下降 90%**，**机房设备占地下降 75%**，**启用服务编程后单局功耗最多下降 66%**，同时也**删掉了 MPLS 网关和 BGP 3107 那笔"复杂度税"**。

必须同时记住的**代价**（第 10.4 节）：**SRv6 的每包开销大于 MPLS**（40 B vs 8 B）。**省的是协议与状态，不是字节。**

## 1.10 历史与四条原则

:::en
In January 2017, a small group of operator engineers met in Rome and set the direction: do not invent a new protocol, strengthen IP itself. Rakuten later published production measurements showing latency, reliability and cost all improving at the same time. Four principles guided the work: strengthen IP, it must make business sense, festina lente (make haste slowly), and less is more.
:::

**2017 年 1 月**，几位运营商工程师在**罗马**闭门定下方向：**不发明新协议，只增强 IP 本身**。后来 **Rakuten 公布了生产网测量结果**——**时延、可靠性、成本三条曲线同时向好**。整个工作由四条原则约束：

| 原则 | 含义 | 在哪一章体现 |
|---|---|---|
| **Strengthen IP** | 不新增协议，只用 IPv6 现有能力 | 第 3 章（行为都用 IPv6 头 + SRH） |
| **Make business sense** | 每项能力都要有商业场景 | 第 6/11/14/15 章 |
| **Festina lente** | 标准化与互通先行，慢即是快 | 第 17 章、RFC 进度 |
| **Less is more** | 能删的层就删 | 1.1 的"三张网变一张" |

## 1.11 本章小结

:::en
SRv6 is not a faster MPLS; it is a different place to put the state. By encoding the program in the destination address, the network keeps no per-flow state, needs no label distribution, and gains the ability to summarize prefixes. The price is a larger outer header and a stricter MTU plan.
:::

**SRv6 不是"更快的 MPLS"，而是"把状态换了个地方放"**。把程序编进目的地址后，网络**不保存每流状态、不需要标签分发、并且获得了前缀汇总能力**。代价是**更大的外层头**与**更严格的 MTU 规划**。

| 结论 | 支撑 |
|---|---|
| SRv6 = 用 IPv6 地址承载有序指令 | 1.2 |
| 五条关键性质：围墙花园、状态在包里、3216、免重编址、最长匹配压缩 | 1.3–1.7 |
| SRH 是例外而非常态 | 1.8 |
| 决策依据四个数：**规模、熵、汇总、删网关** | 1.9 |
| 代价必须承认：**40 B 开销 + MTU** | 1.9、第 10 章 |

## 实战案例：一次"删层"决策的算账过程

**场景**：某运营商城域网现状 `接入(IPv4) → 汇聚(MPLS/LDP) → 核心(SR-MPLS) → DC(VXLAN/EVPN)`，域边界上有 **3 类网关**（LDP↔SR、MPLS↔VXLAN、IPv4↔IPv6）。每次扩容都要在网关上**开会话、加表项、加故障点**。

**按本章逻辑重构的四步**：

```text
① 统一数据面：全网（含 DC 与主机 smartNIC）只保留 SRv6 uSID 一种封装
   → DC 侧不再需要 VXLAN 网关
② 统一地址：从 fdbb:bb00::/24 取 Block
   → /32 按算法、/40 按区域、/48 按节点
   → 原本散在 MPLS 标签、VXLAN VNI、VRF 里的标识收拢到一处
③ 删掉网关：域边界从"协议翻译"变成 L2/L3 直连
   → 运维对象从 4 套协议栈变成 1 套
④ 熵改用 Flow Label：入口 PE 哈希一次写入
   → P 节点按 (SA, DA, FlowLabel) 做 ECMP
   → DPI 与 Entropy Label 全部下线
```

**收益与代价对照（必须一起算）**：

| 项 | 变化 | 说明 |
|---|---|---|
| 协议栈 | 4 套 → **1 套** | 运维对象大幅减少 |
| 网关数量 | 3 类 → **0** | 故障点减少 |
| 核心表项 | 万级 → **百级 /40** | 汇总生效 |
| 每包开销 | 8 B → **40 B** | **带宽成本上升** |
| MTU 要求 | 1500 → **≥1540（建议 1600）** | **需逐链路整改** |

**排障要点**：

- 检查"围墙"是否真的闭合：**若域外报文能在边界被解封装，说明 ACL/uRPF 没做**，SRv6 的安全前提不成立；
- **uSID Block 与现网 IPv6 业务地址绝不能重叠**，否则最长匹配会把业务流量导进 SID 表项；
- **别按"必须带 SRH"去规划 MTU**，先按无 SRH 算（40 B），再为 TI-LFA 与服务链预留余量（第 10 章）。

## 延伸阅读

- **RFC 8402**：Segment Routing Architecture，SR 的基本原则（与 MPLS/SRv6 无关的抽象层）。
- **RFC 8754**：SRH，第 1.8 节"何时才需要 SRH"的规范依据。
- **RFC 8986**：SRv6 网络编程，端点行为清单（第 3 章展开）。
- **RFC 4193**：ULA，第 1.4 节"3216 从哪来"的地址空间基础。
- **draft-ietf-spring-srv6-srh-compression**：uSID 容器（32 bit block + 16 bit uSID）。
- 交叉参考：第 2 章（封装与熵）、第 3 章（行为）、第 10 章（MTU 与地址规划）、第 14/15 章（两家运营商的真实账本）。
