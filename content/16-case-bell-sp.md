# 16 · 案例：Bell Canada 服务编程落地

> **本章定位**：原书第 16 章，与 **Daniel Bernier** 合作。这一章最"工程"：**真实的业务诉求、真实的 IOS XR 配置、真实的生产流量路径。** 英文块为原文摘录，中文为完整翻译，Figure 16.1–16.4 重绘，Example 16.1–16.3 即书中真实配置。

**本章要拿到的东西**：

| 问题 | 对应小节 |
|---|---|
| 传统服务链的"补丁堆叠"到底堆了什么 | 16.1 |
| Bell 的四条要求，为什么只有服务编程能全满足 | 16.2 |
| 绑定 SID 怎么把编排复杂度"消掉" | 16.2.1 |
| MEC 平台在 ASIC 里做了什么（逐步） | 16.3 |
| 生产配置长什么样（color + 策略 + ub6-insert-reduced） | 16.4 |
| 为什么两条 uSID 就够，不需要 SRH | 16.5 |
| 上线时最容易踩的三个坑 | 16.6 |

一句话概括：**这一章是"服务编程从 PPT 变成生产配置"的证据**——它给出了一条真实的 UPF 流量必须过 DDoS 的完整路径，并证明**整条链只写在外层目的地址的两个 uSID 里**。

## 16.1 传统服务链为什么不够用

:::en
Legacy service chaining relies heavily on ACLs and interface-based classification, with tweaks such as VLAN tags, TOS bits, route-leak policies or policy-based routing. Chains were typically deployed as static linear patterns, assuming applications always follow the same sequence, which is not always true. Adding a service or scaling one required re-engineering the whole path.
:::

老办法靠 **ACL + 接口分类**，再叠一堆**补丁**：**VLAN 标签、TOS 位、路由泄露策略、策略路由**。链按**静态线性模式**硬接，**假设应用永远按 A→B→C 的顺序走**——而这**并不总成立**。**加一个服务、扩一次容量，都要把整条路径重新设计一遍。**

把"补丁"列清楚，才知道复杂度从哪来：

| 补丁 | 用来解决 | 带来的新问题 |
|---|---|---|
| ACL | 分类哪些流量要进链 | 规则爆炸、随业务漂移 |
| 接口/VLAN 分类 | 区分接入点 | 拓扑变更即失效 |
| TOS/DSCP 标记 | 传递"等级" | 6 bit 空间不够、跨域被改写 |
| 路由泄露 | 让服务段可达 | 路由域被污染，排障困难 |
| PBR | 强制下一跳 | 每台设备一份策略，**漏配即旁路** |

:::en
Another challenge is the integration of existing appliances: operators have invested significant CAPEX and OPEX in physical and virtual network functions that have long lives ahead of them and cannot simply be replaced. The solution had to integrate them, not replace them.
:::

另一个硬约束是**存量设备**：运营商在 **PNF/VNF** 上投了大量 **CAPEX 与 OPEX**，这些设备**寿命还长，不可能说换就换**。方案必须能"**接进来**"，而不是"**替掉**"。

这一条直接决定了架构选择：**任何要求"服务设备支持 SRv6"的方案，在现网都过不了评审**。所以 Bell 的落点必然是 **SR Proxy / MEC 平台代为处理**（第 13 章的思路），而不是等设备换代。

## 16.2 四条要求与唯一解

:::en
Bell was looking for simple classification and steering, flexibility of service mobility and scaling, integration of existing functions, and control plane flexibility. Service Programming was the only approach that met all four: each service gets a SID, the source builds a SID list, and the fabric stays completely stateless.
:::

Bell 的四条要求：

| 要求 | 具体含义 | 传统方案为什么不行 |
|---|---|---|
| **分类引流要简单** | 少量规则覆盖多业务 | ACL/PBR 规则随业务线性增长 |
| **服务能移动、能扩缩** | 换位置/加实例不改网络 | 引流锚点是设备地址，一改就全网动 |
| **存量设备能接** | PNF/VNF 零改造 | overlay 方案需要设备支持新封装 |
| **控制面要灵活** | 可编程、可编排 | 静态线性链无法表达分支/重排 |

**服务编程是唯一同时满足四者的方案**：**每个服务一个 SID，源端拼段列表，转发面完全无状态**。

### 16.2.1 绑定 SID 把"编排复杂度"消掉

:::en
Because the service SID is a binding SID, the chain can be changed inside the platform — reordering appliances, adding one, scaling out — without changing any steering policy in the network. The policy stays valid as long as the SID does not change.
:::

因为 Service SID 是**绑定 SID**，**链内部怎么改**（换顺序、加设备、扩实例）**都不用动网络里的引流策略**——**只要 SID 不变，策略就永远有效**。**这就是"编排复杂度"被消掉的地方。**

```text
图 16-1：策略与链解耦（原书 Figure 16.1 重绘）

  网络侧（很少变）                 平台侧（经常变）
  ──────────────────────────────────────────────────
  color 10 ──► SR Policy ──► [Service SID A] ──┬─► PNF_A → PNF_B → PNF_C
  （一次配置，长期有效）                        │
                                              └─► 变更：重排/扩容/换型号
                                                  （网络侧零改动）
```

| 变更 | 传统方案要改的地方 | 绑定 SID 方案 |
|---|---|---|
| 设备换型号 | 所有入口的策略 | **平台内部** |
| 链顺序调整 | 所有入口的策略 | **平台内部** |
| 扩容 1→4 台 | 重新设计引流 | **平台内部（ECMP）** |
| 服务迁移到新站点 | 改 SID/地址 | **改绑定列表** |
| 加一类业务走同链 | 重新设计 | **复用同一 SID** |

## 16.3 MEC 平台：在 ASIC 里代替设备实现 SR Proxy

:::en
Bell partnered with Cisco and other ecosystem partners to build a Mobile Edge Core platform based on a programmable ASIC. The platform implements the SR proxy behavior on behalf of the network functions: it removes the SRv6 encapsulation and caches it in memory, forwards the packet through the chain of functions in order, then restores the encapsulation and performs the SRv6 endpoint behavior to forward the packet to the next SID.
:::

Bell 与 Cisco 等伙伴共建了**基于可编程 ASIC 的 MEC（Mobile Edge Core）平台**。平台**代替网络功能实现 SR Proxy**：

1. 收到报文时**剥掉 SRv6 封装并缓存到内存**；
2. **按顺序**把包送过 `PNF_A → PNF_B → PNF_C`；
3. **回收后恢复封装**；
4. **执行 SRv6 端点行为（uN）** 转发到下一段。

```text
图 16-2：MEC 平台的流水线（原书 Figure 16.2 重绘）

  进: [IPv6 | DA=SID A | 内层]
        │
        ▼
   ┌────────────────────────────────────────────┐
   │ MEC ASIC（可编程流水线）                    │
   │  ① 剥封装，SRH/容器缓存到内存               │
   │  ② 依次送过 PNF_A → PNF_B → PNF_C           │
   │      （设备只看到裸报文，完全不知道 SRv6）    │
   │  ③ 收回，恢复封装                           │
   │  ④ 执行 uN：DA 移位到下一段                 │
   └────────────────────────────────────────────┘
        │
        ▼
  出: [IPv6 | DA=下一段 | 内层]
```

:::en
This is what allows existing physical and virtual network functions to join a service chain without any modification, while the chain itself can be changed in the ASIC pipeline independently of the steering policy.
:::

这就是**老 PNF/VNF 零改造入链**的原因；而**链的组成可以在 ASIC 流水线里独立变更**，**网络侧的引流策略对此完全无感**。

| 设计选择 | 为什么 | 代价 |
|---|---|---|
| 用**可编程 ASIC** 而非通用 CPU | 线速转发 + 可改流水线 | 流水线变更需谨慎（影响在跑的业务） |
| 平台**代为实现 SR Proxy** | 设备零改造 | 平台成为关键依赖，必须冗余 |
| **有序送过链** | 保证语义（FW → DPI → ...） | 顺序变更要走变更流程 |
| 恢复后**执行 uN** | 与普通 SRv6 节点一致 | 需正确处理容器移位 |

## 16.4 生产配置：UPF 流量必须过 DDoS

**需求**：从基站侧路由器到 **UPF** 的流量，① **必须在 VRF9 内转发**；② **必须经过 DDoS 清洗**。

:::en
The requirement is expressed with two BGP mechanisms: the ToR2 router attaches a color extended community of 10 to the UPF prefix, and the same router advertises the VPN SID for VRF9. On PE1, an SR-TE policy with color 10 and an explicit segment list steers the traffic through the DDoS platform before it reaches the UPF.
:::

这个需求用**两个 BGP 机制**表达：**ToR2 给 UPF 前缀打上 color 10，并通告 VRF9 的 VPN SID**；**PE1 上用 color 10 的 SR-TE 策略 + 显式段列表，把流量先引到 DDoS 平台**。

**例 16.1：ToR2 打 color（书中真实配置）**

```text
extcommunity-set opaque color_10
  10
end-set
!
route-policy set_color
  if destination in (UPF_Prefix) then
    set extcommunity color 10
  endif
end-policy
!
router bgp 577
  neighbor <PE1>
  route-policy set_color out
```

**例 16.2：PE1 建策略并自动引流**

```text
segment-routing
 traffic-eng
  srv6
   locator Locator0 binding-sid dynamic behavior ub6-insert-reduced
  !
  segment-list exp-path__netpgm01
   index 10 srv6 usid fc00:0:a100:e100::/64
  !
  policy exp-path-pol1
   srv6
   !
   color 10 end-point ipv6 <ToR2>
   candidate-paths
    preference 100
     explicit segment-list exp-path__netpgm01
```

:::en
The resulting packet is encapsulated with an outer IPv6 header whose destination address is a uSID container that encodes two instructions: the Service SID of the proxy connection to the DDoS platform, and the VPN SID for VRF9. Two instructions, no SRH, and the whole chain is expressed in the destination address.
:::

最终报文的**外层目的地址是一个 uSID 容器**，里面只有**两条指令**：

```text
图 16-3：两条指令的服务链（原书 Figure 16.3 重绘）

  DA = fc00:0:a100:e100 : fc00:0:2:e009 ::
       └─ DDoS Service SID ┘└─ VRF9 的 VPN SID ┘
       （代理到 DDoS 平台）    （落地到 VRF9）

  ┌────────────┬────────────────────────────────────┐
  │ IPv6 头    │ 内层报文（GTP-U / 用户 IP）         │
  │ DA=上面    │                                    │
  │ 无 SRH ★  │                                    │
  └────────────┴────────────────────────────────────┘
```

**两条指令、无 SRH**，整条服务链就写进目的地址里了。这就是 uSID 相对 SRH 方案的直观优势：**链路可编程，开销为零**（相对 SRH 而言）。

:::en
The binding SID of the policy is dynamic, with behavior ub6-insert-reduced, which inserts a compressed uSID container rather than a full SRH. This keeps the encapsulation small and avoids MTU surprises in the transport network.
:::

注意 `binding-sid dynamic behavior ub6-insert-reduced`：绑定 SID 是**动态的**，行为是"**插入压缩后的 uSID 容器**"而不是完整 SRH——**封装更小，避免传输网 MTU 问题**。这是 uSID 方案在生产里**必须关注的配置细节**：写错成 `ub6-insert`（插入完整 SRH）就会**多出几十字节**，在 MTU 刚好 1500 的老链路上直接丢包。

## 16.5 为什么两条指令就够

```text
例 16.3：uSID 容器的算术

一个 128 bit 地址，按 /64 切分可用空间：
  每条 uSID 占 16 bit → 最多 6 条（受 block 长度影响）

Bell 的用法：
  第 1 条：Service SID（DDoS 代理）     16 bit
  第 2 条：VPN SID（VRF9）              16 bit
  → 只用了 2 条，还剩 4 条位置

为什么不需要更多？
  传输路径：由 IGP 最短路 / Flex-Algo 决定（不需要写进段列表）
  服务链  ：只有两个点（清洗 + UPF）
  VPN     ：一个终点
  → 三件事，两条指令（传输隐含在 block 的路由里）
```

| 要表达的东西 | 用什么表达 | 占几条 uSID |
|---|---|---|
| 怎么到 DDoS 平台 | **block 的 IGP 路由** | **0**（locator 本身可路由） |
| 经过 DDoS 平台 | Service SID | 1 |
| 落地哪个 VRF | VPN SID（uDT46） | 1 |
| （可选）指定路径 | 额外 uSID / Flex-Algo | 0–2 |

:::en
This is the same principle as in the L3VPN chapter: the transport part of the instruction is already encoded in the locator, so the segment list only needs to carry the parts that are not implied by routing. A well-planned address structure therefore reduces the number of instructions, which in turn removes the need for an SRH.
:::

与第 6 章同一原理：**指令中的"传输"部分已经隐含在 locator 里**，所以**段列表只需要携带"路由无法隐含"的部分**。**地址规划得好，指令数就少；指令数少，就不需要 SRH。**

## 16.6 验证、运维与常见坑

| 项 | 方法 | 期望 |
|---|---|---|
| 服务链是否生效 | `traceroute srv6 ... sid-list <两条 SID>` | 依次到达 DDoS 平台与 ToR2 |
| 封装形态 | 抓包看外层 DA | **只有 DA，无 SRH** |
| VRF 是否正确 | `show cef vrf VRF9 <UPF 前缀>` | 下一跳为 SRv6 SID |
| 策略是否被选中 | `show segment-routing traffic-eng policy color 10` | 状态 Up，路径为显式列表 |
| 服务故障回退 | 撤销 Service SID | 流量回落普通路径，业务不断 |
| MTU | `ping size 1472`（经 DDoS 平台） | 通 |

:::en
Three pitfalls are worth calling out because they all present as "the service is deployed but traffic does not go through it": the color is attached but the VPN SID is not advertised, the ub6-insert and ub6-insert-reduced behaviors are mixed across the network, and the DDoS platform does not implement the SR proxy behavior at all.
:::

**三个坑之所以值得单独列出，是因为它们的现象完全相同**——"**服务配好了，但流量没走它**"：

| 坑 | 根因 | 现象 | 排查 |
|---|---|---|---|
| 只打了 color，没通告 VPN SID | 封装信息不全 | 有策略但走默认路径 | `show bgp ... detail` 看有没有 VPN SID |
| `ub6-insert` 与 `ub6-insert-reduced` 混用 | 部分节点解析不一致 | **部分链路通、部分不通** | 逐节点比对配置 |
| DDoS 平台未启用 SR Proxy | 设备丢弃带扩展头的包 | **链断在第一跳** | 平台侧抓包 |

## 16.7 本章小结

:::en
This case is the proof that service programming works in production: a real requirement, a real configuration, and a real packet with two uSIDs in the destination address. The chain is a binding SID, the appliances are untouched, and the fabric is stateless with respect to the service.
:::

这个案例是**服务编程能在生产跑通的证据**：**真实的诉求、真实的配置、真实的报文（目的地址里两个 uSID）**。**链是一个绑定 SID，设备完全没动，转发面对服务无状态。**

| 维度 | 传统服务链 | Bell 的生产方案 |
|---|---|---|
| 分类 | ACL + 接口 + TOS 补丁 | **color 扩展团体** |
| 引流 | PBR（每台一份） | **BGP 自动引流（一次）** |
| 链表达 | 静态线性、写在设备里 | **两条 uSID、写在 DA 里** |
| 设备改造 | — | **零改造（MEC 代理）** |
| 封装开销 | 视方案 | **无 SRH，最小** |
| 变更 | 全网重新设计 | **改绑定列表** |

一句话收束：**"服务链进报文"这句话在生产上的样子，就是 DA 里那两个 uSID**——剩下的都是围绕"怎么让老设备也能参与"所做的工程妥协（MEC + SR Proxy），而这些妥协**恰好也是可控的**。

## 实战案例

### 案例 A：割接 Order of Operations（顺序错一步就断）

**背景**：把 UPF 流量从"直连"改为"必须过 DDoS"，属于**在线变更**，不能中断。

```text
正确顺序（每一步都可回退）:
① ToR2：先给 UPF 前缀打 color（此时没有策略，color 无副作用）
② PE1：建 SR Policy（含 Service SID），但**先不启用自动引流**
③ PE1：用 sid-list 手工 traceroute 验证策略路径
   traceroute srv6 <ToR2> sid-list <Service SID>,<VPN SID>
   → 两跳都回应，证明 DDoS 代理链路可用
④ PE1：启用 color 10 自动引流（一处变更）
⑤ 验证：抓包确认外层 DA 是两条 uSID、无 SRH
⑥ 业务验证：ping size 1472 + 现网 KPI 观察 24 小时

错误顺序（常见事故）:
① 先启用自动引流 → 策略指向的 Service SID 还不存在
   → 流量被黑洞或回落，业务抖动
② 先配 Service SID 但没验证 → 平台未启用 SR Proxy
   → 链断在第一跳，且无告警
```

| 阶段 | 关键动作 | 回退方式 |
|---|---|---|
| 打 color | 只加团体，无转发影响 | 删 route-policy |
| 建策略 | 不启用引流 | 删 policy |
| 验证路径 | 手工 sid-list trace | 无影响 |
| 启用引流 | 一处生效 | 撤销 color 匹配 |
| 观察 | KPI + 抓包 | 同上 |

### 案例 B：三个坑的现场还原

**坑 1：只打了 color，没通告 VPN SID**

```text
现象：show segment-routing traffic-eng policy color 10 → Up
      但抓包看不到 SRv6 封装，流量仍走普通路径
根因：ToR2 的通告里只有 IPv4 前缀 + color，
      没有该 VRF 的 uDT46 SID → PE1 有策略但拼不出封装
修复：ToR2 的 VRF9 下启用 segment-routing srv6（per-VRF 分配）
验证：show bgp vpnv4 unicast <prefix> → 出现 Prefix-SID
```

**坑 2：`ub6-insert` 与 `ub6-insert-reduced` 混用**

```text
现象：同一业务"部分链路通、部分不通"（约 30% 丢包）
根因：部分 PE 配 ub6-insert（插入完整 SRH），
      部分配 ub6-insert-reduced（插入压缩容器）
      → 接收端对两种封装的解析不一致
修复：全网统一为 ub6-insert-reduced
验证：抓包看所有方向都"只有 DA，无 SRH"
```

**坑 3：DDoS 平台没启用 SR Proxy**

```text
现象：链断在第一跳，平台侧无日志
根因：平台不认识 IPv6 路由头，直接丢弃
      （它连"这条流量该不该放行"都没机会判断）
修复：平台侧启用 SR Proxy（或在 MEC ASIC 上做代理）
验证：平台侧抓包应只看到裸报文
```

### 案例 C：服务扩容，网络侧零变更

**需求**：DDoS 清洗能力从 1 台扩到 3 台，保持 UPF 业务不中断。

```text
做法:
① 网络侧完全不动：color 10、SR Policy、Service SID 全部保持
② MEC 平台侧把"1 个 Service SID → 1 台平台"
   改为"1 个 Service SID → 3 台平台（ECMP/一致性哈希）"
③ 灰度：先把 10% 流量分到新平台，观察清洗准确率与延迟
④ 全量：逐步提到 100%
⑤ 回退：把权重改回 0（一条平台侧命令）

关键：40 台入口 PE 的策略一条没改
```

| 项 | 传统方案 | 本方案 |
|---|---|---|
| 网络侧变更 | 40 台 PE 改策略 | **0 台** |
| 变更窗口 | 每台 15 分钟 | **1 次 10 分钟** |
| 漏配风险 | 高（漏一台即旁路） | **无** |
| 回退 | 逐台恢复 | **一条命令** |

## 延伸阅读

- **RFC 9256**：BGP SR Policy，`color` + 自动引流的规范依据。
- **RFC 9252**：BGP Overlay Services（VPN SID 的携带）。
- **RFC 8986 §8**：SR Proxy（平台代为处理的理论基础）。
- **draft-ietf-spring-srv6-srh-compression**：uSID 容器与 `ub6-insert-reduced` 的编码。
- **RFC 8950**：IPv6 next-hop，VPN SID 可达的前提。
- 交叉参考：第 11 章（服务编程概念）、第 13 章（SR Proxy 三种行为）、第 14 章（同一家运营商的地址规划）、第 10 章（MTU 预算）。
