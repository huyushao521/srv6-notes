# 11 · 服务编程 Service Programming

> 对应原书第 11 章 *Service Programming*。这是 SRv6 从"更好的 VPN"跃迁为"可编程网络"的一章：**把服务本身变成 SID，让源端直接把业务链写进报文。**

## 11.1 从服务链的痛点说起

:::en
Classic service chaining uses ACLs, VLAN tags, policy based routing or dedicated overlay segments to steer traffic through a sequence of appliances. The chain is hardwired, the classification is fragile, and adding or scaling a service requires re-engineering the path. Service Programming replaces all of that with one idea: each service is a SID, and a chain is a list of SIDs.
:::

传统服务链靠 ACL、VLAN 标签、策略路由或专用 overlay 段把流量"推"过一串设备：链是硬接的、分类是脆弱的、加一个服务要重新设计路径。服务编程把这一切换成一个想法：**每个服务是一个 SID，一条服务链就是一串 SID**。

## 11.2 Service SID 与 SR Service Policy

:::en
A Service SID identifies a service instance. It is advertised in BGP, either as a binding SID for an SR policy or as an endpoint behavior, together with attributes such as whether the service is transparent or aware, and what metadata it expects. The source builds a SID list out of service SIDs plus underlay and VPN SIDs, and steers traffic into it.
:::

**Service SID** 标识一个服务实例。它通过 BGP 通告（作为 SR Policy 的**绑定 SID**，或作为一个端点行为），并携带属性：服务是 SR-aware 还是 SR-transparent、期望什么元数据。

源端把这三种 SID 自由组合：

```text
<uN 传输> + <Service SID 防火墙> + <Service SID DPI> + <uDT46 VPN SID>
   ↑underlay        ↑服务                ↑服务              ↑业务落地
```

:::en
Because the SID list mixes underlay, service and overlay instructions, traffic engineering, service chaining and VPN can be expressed in one program. The network fabric stays stateless: no per-chain state, no policy on transit routers.
:::

因为段列表把 Underlay、服务、Overlay 三类指令混在一起，**TE + 服务链 + VPN 可以用一个程序同时表达**，而转发面依旧无状态：中间路由器没有"链"的概念，也没有策略。

## 11.3 绑定 SID 的作用

:::en
A binding SID decouples the service chain from the policy that selects it. The chain "PNF_A + PNF_B + PNF_C" gets one binding SID, call it SID A. Applications and edge routers steer traffic to SID A. If the chain is re-ordered, scaled out, or replaced with different appliances, only the binding changes; every steering policy in the network stays untouched.
:::

绑定 SID 把"服务链的实现"与"选择该链的策略"解耦。链 `PNF_A + PNF_B + PNF_C` 分配一个绑定 SID（记作 SID A），应用和边缘只往 SID A 引流。链内部换设备、调顺序、扩实例，**只改绑定，全网引流策略一行不动**。

```text
SID A ──► <uN(A) , uA(到PNF_A) , uA(到PNF_B) , uA(到PNF_C) , uDT46>
          ↑ 链内部随便改，对外只暴露 SID A
```

## 11.4 控制面：怎么把服务信息传出去

| 机制 | 作用 |
|---|---|
| BGP SR Policy（SAFI 73，RFC 9256） | 下发带段列表的策略、绑定 SID、候选路径 |
| BGP-LS Service Chaining TLV | 把服务节点/服务能力注入控制器拓扑 |
| BGP-LS Opaque Metadata TLV | 携带与服务相关的元数据（如 SLA、站点） |
| BGP Color + Automated Steering | 按业务类别自动把流量导入对应策略 |

:::en
Two control plane styles are supported and they can coexist: the classical BGP approach, where the service information is carried in BGP attributes and processed by routers, and the SDN approach, where a controller computes the chain and programs it via BGP SR Policy or an API. Bell Canada's deployment uses both: BGP for the transport policy, and an orchestration layer for the service chain itself.
:::

两种控制面风格可以共存：**BGP 式**（服务信息在 BGP 属性里，路由器自己处理）与 **SDN 式**（控制器算好链，用 BGP SR Policy 或 API 下发）。Bell Canada 的生产部署两者都用：传输策略走 BGP，服务链本身由编排层管理。

## 11.5 与 TE、VPN 的关系

:::en
Service Programming does not replace traffic engineering or VPN: it composes with them. A single SR policy may include a low-latency underlay path, one or more service SIDs, and terminate on a VPN SID. This composition is what makes "one program, many intents" possible.
:::

服务编程不取代 TE 与 VPN，而是与它们**组合**：一条 SR Policy 可以同时包含低时延 Underlay 路径、若干 Service SID，并以 VPN SID 结尾。这种"一条程序、多个意图"的能力，正是它区别于传统服务链的地方。

## 实战案例：把 DDoS 清洗塞进转发路径

**需求**：某城域网上行流量必须经过 DDoS 清洗平台，但只对特定业务（如游戏、直播）生效，且清洗平台故障时不能中断业务。

**设计**：

1. 清洗平台前的 MEC/ASIC 平台分配一个 **Service SID（绑定 SID）**：`fc00:0:a100:e100::`。
2. 边缘 PE 为受保护业务配置 SR Policy：`<低时延 uN> , <清洗 Service SID> , <uDT46 目的 VPN SID>`。
3. BGP 用 Color 把"游戏/直播"类路由自动引入该策略（Color-based Automated Steering）。
4. 清洗平台故障 → 控制器撤销该 Service SID 的 BGP 通告 → 边缘自动回落到不含清洗段的普通策略，业务继续。

**验证**：

| 项 | 命令/方法 |
|---|---|
| SID 是否可达 | `ping srv6 <Service SID>` |
| 链是否生效 | `traceroute srv6 ... sid-list <完整列表>` |
| 故障回退 | 手工撤销 Service SID 通告，观察边缘策略切换时间 |
| 元数据 | 抓包确认 Arg/Metadata 未被中间节点改写 |

**常见坑**：

- Service SID 与 VPN SID 混在同一 locator 下，导致转置/汇总时语义冲突。
- 清洗平台不支持 SR-aware，需要 SR Proxy（第 13 章）——否则平台看不懂外层头，直接丢弃。
- 链过长（>6 段）触发 SRH，MTU 与硬件能力都要重新评估。

## 本章小结

1. 服务 = SID；服务链 = SID 列表；转发面保持无状态。
2. 绑定 SID 是解耦链实现与引流策略的关键。
3. BGP SR Policy 与 BGP-LS 扩展构成控制面；SDN 与 BGP 两种风格可共存。
4. 与 TE、VPN 组合使用，形成"一条程序多意图"。
