# 11 · 服务编程：把业务链写进报文

> **本章定位**：原书第 11 章《Service Programming》。这是 SRv6 从"更好的 VPN"跃迁为"可编程网络"的一章：**把服务本身变成 SID，让源端直接把业务链写进报文**。英文块为原文摘录，中文为完整翻译，Figure 11.1–11.4 重绘，Example 11.1–11.3 保留。

**本章要拿到的东西**：

| 问题 | 对应小节 |
|---|---|
| 传统服务链（ACL/PBR/overlay）到底脆在哪 | 11.1 |
| Service SID、绑定 SID、元数据各是什么 | 11.2 |
| 为什么"绑定 SID"是解耦的关键 | 11.3 |
| 服务分为 SR-aware / SR-transparent / 传统三类，各怎么接 | 11.4 |
| 控制面怎么把服务信息传出去（BGP vs SDN） | 11.5 |
| 链太长会撞上什么硬限制 | 11.6 |

一句话概括：**服务编程不是新封装，是把"路径"这个概念从"设备里的策略"搬到"报文里的段列表"**。一旦搬过去，加一个服务、改一次顺序、扩一个实例，都变成**改一条段列表**，而不是**改全网策略**。

## 11.0 从一个运维场景说起

```text
图 11-1：传统服务链 vs 服务编程（原书 Figure 11.1 重绘）

  传统（PBR / ACL / VLAN 引流）:
    PE ──[策略 A]──► FW ──[策略 B]──► DPI ──[策略 C]──► PE ──► 目的
    每台设备都要维护一份"往哪送"的策略；
    FW 换型号 → 策略 A/B 全要改；FW 扩一台 → 引流要重新设计

  服务编程（段列表）:
    PE ──► [uN(FW) , uN(DPI) , uDT46(目的)]
            ↑ 一条段列表就说完了全部意图
    中间设备只执行自己的 SID，不维护"链"的概念
```

## 11.1 传统服务链的三个脆弱点

:::en
Classic service chaining uses ACLs, VLAN tags, policy based routing or dedicated overlay segments to steer traffic through a sequence of appliances. The chain is hardwired, the classification is fragile, and adding or scaling a service requires re-engineering the path. Service Programming replaces all of that with one idea: each service is a SID, and a chain is a list of SIDs.
:::

传统服务链靠 **ACL、VLAN 标签、策略路由（PBR）或专用 overlay 段**把流量"推"过一串设备：**链是硬接的、分类是脆弱的、加一个服务要重新设计路径**。服务编程把这一切换成一个想法：**每个服务是一个 SID，一条服务链就是一串 SID**。

三个脆弱点拆开看：

| 脆弱点 | 表现 | 根因 |
|---|---|---|
| **链是硬接的** | 换一台防火墙型号，上下游策略全要改 | "下一跳是谁"写死在设备配置里 |
| **分类是脆弱的** | 新增一类业务要加 ACL，ACL 越加越乱 | 分类靠五元组匹配，语义随业务漂移 |
| **扩容要重新设计** | 清洗平台从 1 台扩到 4 台，引流要重做 | 设备地址是引流锚点，扩缩容即改址 |

:::en
The deeper problem is that the chain lives in the network rather than in the packet. Because the chain is state distributed across many devices, every change must be coordinated across all of them, and any device that is missed becomes a silent bypass.
:::

更深层的问题是：**链活在网络里，而不活在报文里**。因为链是**分布在许多设备上的状态**，**每次变更都必须全网协调**，而**任何一台漏配的设备都会变成静默旁路**——流量悄悄绕过了防火墙，没人知道。

## 11.2 三个核心概念

:::en
A Service SID identifies a service instance. It is advertised in BGP, either as a binding SID for an SR policy or as an endpoint behavior, together with attributes such as whether the service is transparent or aware, and what metadata it expects. The source builds a SID list out of service SIDs plus underlay and VPN SIDs, and steers traffic into it.
:::

**Service SID** 标识一个服务实例。它通过 **BGP 通告**（作为 **SR Policy 的绑定 SID**，或作为**一个端点行为**），并携带属性：**服务是 SR-aware 还是 SR-transparent、期望什么元数据**。源端把这三种 SID 自由组合：

```text
<uN 传输> + <Service SID 防火墙> + <Service SID DPI> + <uDT46 VPN SID>
   ↑underlay        ↑服务                ↑服务              ↑业务落地
```

| 概念 | 是什么 | 谁分配 | 关键属性 |
|---|---|---|---|
| **Service SID** | 一个服务实例的地址 | 服务节点/控制器 | 行为、是否 SR-aware、元数据格式 |
| **绑定 SID（BSID）** | 一条策略/一条链的"对外句柄" | 头端或控制器 | 指向一条段列表，可随时改 |
| **元数据（Metadata）** | 随报文带给服务的附加信息 | 头端 | 租户、SLA、站点、app-id |

:::en
Because the SID list mixes underlay, service and overlay instructions, traffic engineering, service chaining and VPN can be expressed in one program. The network fabric stays stateless: no per-chain state, no policy on transit routers.
:::

因为段列表把 **Underlay、服务、Overlay 三类指令混在一起**，**TE + 服务链 + VPN 可以用一个程序同时表达**，而**转发面依旧无状态**：中间路由器**没有"链"的概念，也没有策略**。

这张"三类指令混编"的表，是理解服务编程的钥匙：

| 段位置 | SID 类型 | 表达什么 | 例子 |
|---|---|---|---|
| 第 1 段 | uN / uA | **怎么走**（Underlay 路径、低时延） | `fdbb:bb01:0002::`（Algo 128） |
| 中间段 | Service SID | **经过谁**（服务链） | `fdbb:bb00:0a00:e100::`（清洗） |
| 最后段 | uDT46 / uDX | **送到哪**（Overlay 落地） | `fdbb:bb00:0005:e101::` |

## 11.3 绑定 SID：解耦"链的实现"与"引流策略"

:::en
A binding SID decouples the service chain from the policy that selects it. The chain "PNF_A + PNF_B + PNF_C" gets one binding SID, call it SID A. Applications and edge routers steer traffic to SID A. If the chain is re-ordered, scaled out, or replaced with different appliances, only the binding changes; every steering policy in the network stays untouched.
:::

绑定 SID 把**服务链的实现**与**选择该链的策略**解耦。链 `PNF_A + PNF_B + PNF_C` 分配一个绑定 SID（记作 **SID A**），应用和边缘**只往 SID A 引流**。链内部**换设备、调顺序、扩实例，只改绑定，全网引流策略一行不动**。

```text
图 11-2：绑定 SID 的解耦效果（原书 Figure 11.2 重绘）

  对外（不变）              对内（随时可变）
  ─────────────────────────────────────────────────
  引流策略 ──► SID A ──┬──► FW-1 ──► DPI-1
  （全网唯一一处）        │
                        └──► FW-2 ──► DPI-2   ← 扩容/换型号
                              ▲
                              └─ 只改 SID A 的绑定列表

  对比：无绑定 SID
  引流策略 ──► <FW-1 的 SID> ──► <DPI-1 的 SID>
                ↑ 换设备 = 改引流策略 = 全网协调
```

```text
例 11.1：绑定 SID 的表达
SID A ──► <uN(A), uA(到PNF_A), uA(到PNF_B), uA(到PNF_C), uDT46>
          ↑ 链内部随便改，对外只暴露 SID A
```

| 变更类型 | 无绑定 SID | 有绑定 SID |
|---|---|---|
| 换一台防火墙 | 改所有引流策略 | **改绑定列表** |
| 链顺序调整 | 改所有引流策略 | 改绑定列表 |
| 服务扩容（1→4 台） | 重新设计引流 | 改绑定列表（ECMP） |
| 新增一类业务走同链 | 重新设计 | **复用 SID A** |
| 回滚 | 逐台恢复配置 | **切换重写到旧列表** |

:::en
This decoupling is the operational heart of service programming: the number of places that must change when a service changes drops from "every ingress router" to "one binding".
:::

这个解耦是服务编程的**运维核心**：**服务变更时需要改的地方，从"每台入口路由器"降到"一个绑定"**。

## 11.4 三类服务节点怎么接

这是设计与招标时最先要问的问题：**你要接的服务设备，看不看得懂 SRv6？**

| 类型 | 能力 | 接入方式 | 代价 |
|---|---|---|---|
| **SR-aware** | 能解析 SRH/uSID，能当端点 | 直接分配 Service SID，作为端点行为 | 需设备支持 SRv6 |
| **SR-transparent** | 不看外层，只处理内层 | **动态代理**（Dynamic Proxy）：边缘代它处理 SID | 代理需维护状态 |
| **传统设备** | 完全不认识 IPv6 扩展头 | **静态代理**（Static Proxy）：用固定 SID 绑定固定邻接 | 配置静态、灵活性差 |

```text
图 11-3：三类接入方式（原书 Figure 11.3 重绘）

  ① SR-aware
     PE ──[DA=Service SID]──► [FW 解析 SID，处理后继续查表] ──► PE

  ② SR-transparent（动态代理）
     PE ──[DA=Proxy SID]──► [PE 自己的代理端点]
                              ├─ 剥 SRH（暂存）
                              ├─ 把内层送进 FW
                              └─ FW 返回后恢复 SRH，继续下一段

  ③ 传统设备（静态代理）
     PE ──[DA=静态绑定的 SID]──► [固定出接口] ──► FW ──► [固定入接口] ──► PE
          ↑ 无动态状态，靠"接口对"绑定
```

:::en
The choice between these three is driven by the appliance, not by the network. What the network must guarantee in all three cases is that the SID list remains semantically valid after the service: the service must not consume or corrupt the remaining segments, and the metadata must survive unchanged.
:::

这三者之间怎么选，**由设备能力决定，不是由网络设计决定**。而无论哪种，网络都必须保证一件事：**服务处理完之后，段列表在语义上仍然有效**——**服务不能消耗或破坏剩余段，元数据必须原样存活**。

第 13 章会把三种代理的细节展开，本章只需记住结论：**服务设备越"笨"，代理就要越"聪明"，而代理的状态就越难运维**。

## 11.5 控制面：服务信息怎么传出去

| 机制 | 作用 | 标准化 |
|---|---|---|
| **BGP SR Policy**（SAFI 73） | 下发带段列表的策略、绑定 SID、候选路径 | RFC 9256 |
| **BGP-LS Service Chaining TLV** | 把服务节点/服务能力注入控制器拓扑 | draft |
| **BGP-LS Opaque Metadata TLV** | 携带与服务相关的元数据（SLA、站点） | draft |
| **BGP Color + Automated Steering** | 按业务类别自动把流量导入对应策略 | RFC 9256 的一部分 |
| **PCEP** | 传统 TE 控制器下发路径（可携带 SRv6 段列表） | RFC 8664 等 |

:::en
Two control plane styles are supported and they can coexist: the classical BGP approach, where the service information is carried in BGP attributes and processed by routers, and the SDN approach, where a controller computes the chain and programs it via BGP SR Policy or an API. Bell Canada's deployment uses both: BGP for the transport policy, and an orchestration layer for the service chain itself.
:::

两种控制面风格**可以共存**：

- **BGP 式**：服务信息在 BGP 属性里，**路由器自己处理**；
- **SDN 式**：**控制器算好链**，用 BGP SR Policy 或 API 下发。

**Bell Canada 的生产部署两者都用**：**传输策略走 BGP，服务链本身由编排层管理**（第 14 章）。

```text
图 11-4：两种控制面共存（原书 Figure 11.4 重绘）

  编排层 / 控制器
     │  ① 算出服务链
     │  ② 用 BGP SR Policy（SAFI 73）下发
     ▼
  头端 PE ──[段列表]──► P ──► 服务节点 ──► P ──► 出口 PE
     ▲                       ▲
     └─ ③ BGP Color 自动引流 ─┘
        （业务路由带 Color → 自动导入策略，无需逐条配置）
```

## 11.6 硬限制：链有多长

| 限制 | 数值 | 后果 | 缓解 |
|---|---|---|---|
| 无 SRH 的 uSID 深度 | 一个 128 bit 地址能装约 6 条 | 超过即需 SRH | 用绑定 SID 压缩链 |
| 带 SRH 的开销 | +8 B + 16 B/容器 | MTU 与线速下降 | 控制链长 ≤ 3 |
| 硬件 SRH 处理能力 | 各芯片不同（常见 3–8 段） | 超限降级到软件转发 | 招标时明确段数指标 |
| 元数据长度 | 受 SRH TLV 空间限制 | 元数据被截断 | 只带必要字段（app-id、租户） |

:::en
A useful design rule is to keep the explicit chain short and push complexity into binding SIDs: a chain of three segments at the head end can expand into a much longer chain inside the domain, because each binding SID hides its own expansion.
:::

一条实用的设计规则：**让显式链保持短，把复杂度推进绑定 SID 里**——头端**三段**的链，在域内可以**展开成更长的链**，因为**每个绑定 SID 都隐藏了自己的展开**。

这就是"**分段编排**"：头端只关心"去哪、经过哪个域、送到哪个 VPN"，域内由各域的绑定 SID 自己展开。

## 11.7 排障

```text
服务链不通
  │
  ├─ ① Service SID 存在吗
  │    ping srv6 <Service SID>
  │    └─ 不通 → 服务节点未注册 / 未通告
  │
  ├─ ② 段列表在头端生效了吗
  │    show segment-routing srv6 policy <name> detail
  │    └─ 有策略但无流量 → 引流（Color/ACL）没命中
  │
  ├─ ③ 服务节点处理完了吗
  │    服务侧计数 / 抓包：内层报文有没有到、有没有回
  │    └─ 到了没回 → 服务节点丢弃（多为 SR-transparent 未配代理）
  │
  ├─ ④ 剩余段还在吗
  │    traceroute srv6 ... sid-list <完整列表>
  │    └─ 服务后中断 → 服务消费/破坏了 SRH
  │
  └─ ⑤ 大包通吗
       ping size 1472
       └─ 不通 → 链过长触发 SRH，MTU 不够（11.6）
```

| 检查项 | 命令 | 期望 |
|---|---|---|
| Service SID 可达 | `ping srv6 <SID>` | 通 |
| 策略状态 | `show segment-routing srv6 policy detail` | Active，段列表正确 |
| 引流命中 | `show segment-routing srv6 forwarding` | 有对应表项与计数 |
| 段列表执行 | `traceroute srv6 ... sid-list ...` | 每段都回应 |
| 元数据完整 | 服务侧抓包 | 字段未被改写 |
| MTU | `ping ... size 1472` | 通 |

## 11.8 本章小结

:::en
Service programming turns the service chain into a program carried by the packet. The chain becomes a list of SIDs, the policy that selects the chain becomes a binding SID, and the fabric becomes stateless with respect to services. The operational gain is that changing a service changes one binding instead of every ingress policy.
:::

服务编程把**服务链变成报文携带的程序**：**链 = SID 列表，选链的策略 = 绑定 SID，转发面相对服务无状态**。运维收益是：**改一个服务只改一个绑定，而不是改每一条入口策略**。

| 维度 | 传统服务链 | 服务编程 |
|---|---|---|
| 链在哪 | 分布在设备配置里 | **报文里（段列表）** |
| 变更半径 | 全网入口设备 | **一个绑定 SID** |
| 分类 | ACL 五元组 | Color / 策略（语义化） |
| 扩容 | 改引流 | 改绑定列表（ECMP） |
| 中间设备状态 | 每台维护"下一跳是谁" | **无** |
| 回退 | 逐台恢复 | 切换绑定 |
| 主要代价 | 配置漂移 | **服务设备要支持 SR / 需代理** |

一句话收束：**服务编程的价值不在"能编"，而在"改得动"**——它把服务变更从"跨团队、跨设备、跨周"的协调，变成**一条段列表的更新**。

## 实战案例

### 案例 A：把 DDoS 清洗塞进转发路径（原书案例）

**需求**：某城域网上行流量必须经过 DDoS 清洗平台，但**只对特定业务**（游戏、直播）生效，且**清洗平台故障时不能中断业务**。

```text
设计:
① 清洗平台前的 MEC/ASIC 平台分配一个 Service SID（绑定 SID）：
   fc00:0:a100:e100::
② 边缘 PE 为受保护业务配置 SR Policy：
   <低时延 uN> , <清洗 Service SID> , <uDT46 目的 VPN SID>
③ BGP 用 Color 把"游戏/直播"类路由自动引入该策略
   （Color-based Automated Steering）
④ 清洗平台故障 → 控制器撤销该 Service SID 的 BGP 通告
   → 边缘自动回落到不含清洗段的普通策略，业务继续
```

**验证**：

| 项 | 命令/方法 | 期望 |
|---|---|---|
| SID 是否可达 | `ping srv6 <Service SID>` | 通 |
| 链是否生效 | `traceroute srv6 ... sid-list <完整列表>` | 三段都回应 |
| 故障回退 | 手工撤销 Service SID 通告 | 边缘策略在秒级切换 |
| 元数据 | 抓包确认 Arg/Metadata 未被中间节点改写 | 字段完整 |

**三个常见坑**：

1. **Service SID 与 VPN SID 混在同一 locator 下**，导致转置/汇总时语义冲突（第 6 章）；
2. **清洗平台不支持 SR-aware**，需要 SR Proxy（第 13 章）——否则平台看不懂外层头，**直接丢弃**；
3. **链过长（>6 段）触发 SRH**，MTU 与硬件能力都要重新评估。

### 案例 B：清洗平台从 1 台扩到 4 台，引流策略零改动

**背景**：某省网上行清洗能力不足，需要把清洗平台从 1 台扩到 4 台，并保证扩容期间业务不中断。

```text
无绑定 SID 的做法（预估）:
  ① 4 台平台各分配 SID
  ② 修改所有入口 PE 的引流策略，加入 4 个 SID 并做 ECMP
  ③ 每台 PE 变更窗口 15 分钟 × 40 台 = 10 小时
  ④ 风险：漏改一台 → 该台流量绕过清洗

有绑定 SID 的做法（实际）:
  ① 保留原绑定 SID A 不变（对外零变化）
  ② 只改 SID A 的内部展开：1 段 → 4 段 ECMP
  ③ 变更窗口：1 次，约 10 分钟
  ④ 回退：把展开改回 1 段，秒级
```

**结果**：**40 台入口 PE 一条策略都没动**，扩容对全网"不可见"。

**教训**：**绑定 SID 不是"可选项"，是服务链能否长期运维的前提**。设计阶段不引入绑定 SID，后期每次扩容都要全网协调。

### 案例 C：服务消费了 SRH，导致后续段失效

**现象**：接入某 DPI 设备后，业务在 DPI 之后全部不通，但 DPI 本身显示"转发正常"。

```text
① 头端策略：<uN> , <DPI Service SID> , <uDT46>
② traceroute 带完整列表：
   1  uN          0.4 ms
   2  DPI SID     0.8 ms
   3  uDT46       * * *          ← 第 3 段丢失
③ DPI 侧抓包：出去的报文没有 SRH，只剩内层 IPv4
④ 根因：DPI 是"传统设备 + 静态代理"，但代理配的是"弹出 SRH"模式，
        而不是"暂存后恢复"
⑤ 修复：改为动态代理（SR-transparent 模式），或把 DPI 移到链尾
         （链尾之后不需要剩余段）
⑥ 复测：三段全部回应，业务恢复
```

**教训**：**服务节点必须保证"剩余段完好"**。链中位置越靠前，对服务的要求越高——**最省事的做法是把不透明设备放在链尾**。

## 延伸阅读

- **RFC 9256**：BGP SR Policy（SAFI 73），段列表与绑定 SID 的标准化承载，11.5 的基础。
- **RFC 8986**：端点行为，Service SID 作为"端点行为"的语义来源。
- **draft-ietf-spring-sr-service-programming**：SRv6 服务编程的架构与 Service SID 定义。
- **draft-ietf-idr-bgp-ls-sr-service-segments**：BGP-LS Service Chaining TLV。
- **draft-ietf-spring-srv6-network-programming**（历史版本）：与 RFC 8986 的演进关系。
- 交叉参考：第 6 章（VPN SID 作为链尾）、第 12 章（SR-aware 服务如何读内层与元数据）、第 13 章（SR Proxy 的三种实现）、第 16 章（Bell SP 的 DDoS 生产链）。
