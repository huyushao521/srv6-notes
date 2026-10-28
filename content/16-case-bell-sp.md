# 16 · 案例：Bell Canada 服务编程落地

> 对应原书第 16 章，与 Daniel Bernier 合作。这一章最"工程"：**真实的业务诉求、真实的 IOS XR 配置、真实的生产流量路径。**

## 16.1 传统服务链为什么不够用

:::en
Legacy service chaining relies heavily on ACLs and interface-based classification, with tweaks such as VLAN tags, TOS bits, route-leak policies or policy-based routing. Chains were typically deployed as static linear patterns, assuming applications always follow the same sequence, which is not always true. Adding a service or scaling one required re-engineering the whole path.
:::

老办法靠 ACL + 接口分类，再叠一堆 VLAN 标签、TOS、路由泄露、策略路由的补丁；链按静态线性模式硬接，假设应用永远按 A→B→C 的顺序走。**加一个服务、扩一次容量，都要把整条路径重新设计一遍。**

:::en
Another challenge is the integration of existing appliances: operators have invested significant CAPEX and OPEX in physical and virtual network functions that have long lives ahead of them and cannot simply be replaced. The solution had to integrate them, not replace them.
:::

另一个硬约束是**存量设备**：运营商在 PNF/VNF 上投了大量 CAPEX 与 OPEX，这些设备寿命还长，不可能说换就换。方案必须能"接进来"，而不是"替掉"。

## 16.2 目标与方案

:::en
Bell was looking for simple classification and steering, flexibility of service mobility and scaling, integration of existing functions, and control plane flexibility. Service Programming was the only approach that met all four: each service gets a SID, the source builds a SID list, and the fabric stays completely stateless.
:::

Bell 的四条要求：分类引流要简单、服务能移动能扩缩、存量设备能接、控制面要灵活。服务编程是唯一同时满足四者的方案：**每个服务一个 SID，源端拼段列表，转发面完全无状态**。

:::en
Because the service SID is a binding SID, the chain can be changed inside the platform — reordering appliances, adding one, scaling out — without changing any steering policy in the network. The policy stays valid as long as the SID does not change.
:::

因为 Service SID 是**绑定 SID**，链内部怎么改（换顺序、加设备、扩实例）都不用动网络里的引流策略——**只要 SID 不变，策略就永远有效**。这就是"编排复杂度"被消掉的地方。

## 16.3 MEC 平台：让老设备进链

:::en
Bell partnered with Cisco and other ecosystem partners to build a Mobile Edge Core platform based on a programmable ASIC. The platform implements the SR proxy behavior on behalf of the network functions: it removes the SRv6 encapsulation and caches it in memory, forwards the packet through the chain of functions in order, then restores the encapsulation and performs the SRv6 endpoint behavior to forward the packet to the next SID.
:::

Bell 与 Cisco 等伙伴共建了基于**可编程 ASIC** 的 MEC 平台。平台代替网络功能实现 **SR Proxy**：收到报文时剥掉 SRv6 封装并缓存到内存 → 按顺序把包送过 `PNF_A → PNF_B → PNF_C` → 回收后恢复封装 → 执行 SRv6 端点行为（uN）转发到下一段。

```text
[SID A][内层] → MEC ASIC
                 ├─ 剥封装，缓存
                 ├─ PNF_A → PNF_B → PNF_C   （设备完全不知道 SRv6）
                 ├─ 恢复封装
                 └─ 执行 uN，转发到下一 SID
```

:::en
This is what allows existing physical and virtual network functions to join a service chain without any modification, while the chain itself can be changed in the ASIC pipeline independently of the steering policy.
:::

老 PNF/VNF **零改造**入链，而链的组成可以在 ASIC 流水线里独立变更——网络侧的引流策略对此完全无感。

## 16.4 生产配置：UPF 流量必须过 DDoS

**需求**：从基站侧路由器到 UPF 的流量，① 必须在 VRF9 内转发；② 必须经过 DDoS 清洗。

**做法（书中真实配置）**：

```text
! ToR2：给 UPF 前缀打 color，并通告 VRF9 的 VPN SID
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

```text
! PE1：为 DDoS 服务建显式路径的 SR-TE 策略，并把 color 10 的流量引进去
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

最终报文的外层目的地址是一个 uSID 容器，里面只有**两条指令**：

```text
DA = fc00:0:a100:e100 : fc00:0:2:e009 ::
      └ DDoS Service SID ┘└ VRF9 的 VPN SID ┘
```

**两条指令、无 SRH**，整条服务链就写进目的地址里了。这就是 uSID 相对 SRH 方案的直观优势：链路可编程，开销为零。

:::en
The binding SID of the policy is dynamic, with behavior ub6-insert-reduced, which inserts a compressed uSID container rather than a full SRH. This keeps the encapsulation small and avoids MTU surprises in the transport network.
:::

注意 `binding-sid dynamic behavior ub6-insert-reduced`：绑定 SID 是**动态的**，行为是"插入压缩后的 uSID 容器"而不是完整 SRH——封装更小，避免传输网 MTU 问题。这是 uSID 方案在生产里必须关注的配置细节。

## 16.5 验证与运维

| 项 | 方法 | 期望 |
|---|---|---|
| 服务链是否生效 | `traceroute srv6 ... sid-list <两条 SID>` | 依次到达 DDoS 平台与 ToR2 |
| 封装形态 | 抓包看外层 DA | 只有 DA，无 SRH |
| VRF 是否正确 | `show cef vrf VRF9 <UPF 前缀>` | 下一跳为 SRv6 SID |
| 策略是否被选中 | `show segment-routing traffic-eng policy color 10` | 状态 Up，路径为显式列表 |
| 服务故障回退 | 撤销 Service SID | 流量回落普通路径，业务不断 |

**常见坑**：

- ToR2 只打了 color 但没通告 VPN SID → PE1 有策略但无可用封装信息，流量走默认路径。
- `ub6-insert-reduced` 与 `ub6-insert` 混用 → 部分节点解析不一致，表现为"部分链路通"。
- DDoS 平台侧未启用 SR Proxy → 设备丢弃带扩展头的报文，链断在第一跳。

## 本章小结

1. 服务编程把"编排复杂度"换成"一个绑定 SID"。
2. MEC 平台用 SR Proxy 让存量 PNF/VNF 零改造入链。
3. 生产配置的关键是 `color + 自动引流 + ub6-insert-reduced`。
4. 典型报文只有两条 uSID、无 SRH，服务链写在目的地址里。
