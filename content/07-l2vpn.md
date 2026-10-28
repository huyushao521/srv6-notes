# 07 · SRv6 L2VPN（EVPN）

> 对应原书第 7 章 *SRv6 L2VPN*。核心是四个行为：`End.DX2`、`End.DX2V`、`End.DT2U`、`End.DT2M`，以及 EVPN 的多归与泛洪语义如何映射到 uSID。

## 7.1 四个二层行为

:::en
Layer 2 services need different behaviors depending on whether the frame must be sent out of one specific attachment circuit, looked up by VLAN, flooded to unknown destinations, or replicated to a set of remote peers. SRv6 defines End.DX2 for a single cross-connect, End.DX2V for VLAN-aware bundle services, End.DT2U for unknown unicast flooding, and End.DT2M for multicast and broadcast replication.
:::

二层业务的转发语义比三层复杂，因此 SRv6 定义了四个行为：

| 行为 | uSID 别名 | 语义 | 对应业务 |
|---|---|---|---|
| End.DX2 | uDX2 | 剥外层，从**指定 AC** 发出 | E-Line（点到点） |
| End.DX2V | uDX2V | 剥外层，按 **VLAN** 查表出 | VLAN-aware bundle |
| End.DT2U | uDT2U | 未知单播**泛洪** | E-LAN |
| End.DT2M | uDT2M | 组播/广播**复制**（Arg 携带 BD 标识） | E-LAN |

:::en
End.DT2M carries an argument that identifies the broadcast domain, so a single SID can serve many bridge domains on the same PE. End.DX2 needs no lookup at all: the SID itself points to exactly one attachment circuit, which makes it the most efficient option for large numbers of point-to-point E-Line services.
:::

`End.DT2M` 的 **Argument 里携带广播域（BD）标识**，所以一个 SID 就能服务同一台 PE 上的多个桥域。`End.DX2` 完全不做查找：SID 本身就指向唯一一条 AC，因此它是海量点到点 E-Line 的最高效选择——阿里的 VPWS 就是靠 32 bit Wide uSID 走这条路。

## 7.2 EVPN 怎么把 SID 送过去

:::en
EVPN route types are reused unchanged. The Ethernet A-D route per EVI and per ES, the MAC/IP advertisement route, the inclusive multicast route and the Ethernet segment route keep their existing encoding; what changes is that the NLRI now carries an SRv6 L2 Service TLV with the endpoint behavior and the SID, instead of an MPLS label.
:::

EVPN 路由类型原样复用：

| 路由类型 | 用途 | 携带的 SRv6 信息 |
|---|---|---|
| Type 1（Ethernet A-D） | 别名/备份、分割 Horizon | per-EVI / per-ES 的 uDX2 或 uDT2U SID |
| Type 2（MAC/IP） | MAC 学习、ARP/ND 代答 | 目的 PE 的 L2 SID |
| Type 3（IMET） | 泛洪复制列表 | uDT2M SID |
| Type 4（ES） | 多归发现 | — |

:::en
The label field of the NLRI is replaced by the SRv6 L2 Service TLV defined in RFC 9252, which carries the endpoint behavior and the 128-bit SID. From the control plane's point of view nothing else changes, which is why EVPN deployments can migrate independently of the underlay.
:::

NLRI 里的标签字段被 **RFC 9252 的 SRv6 L2 Service TLV** 取代，携带端点行为 + 128 bit SID。控制面其余部分没有任何变化——这正是 EVPN 可以独立于 Underlay 迁移的原因。

## 7.3 多归与 Anycast SID

:::en
For an all-active multi-homed Ethernet segment, all PE nodes attached to the same segment are configured with the same anycast SID for that segment. Remote nodes send a single copy of the frame to the anycast SID, and the receiving PE that gets the packet forwards it on the local segment. This gives per-flow load balancing across the multi-homing PEs without any additional signaling.
:::

全活多归场景下，接在同一 ES 上的所有 PE 配**同一个 anycast SID**。远端只发一份报文到 anycast SID，收到的那台 PE 在本地网段转发出去。于是多归 PE 之间**自动获得逐流负载分担**，不需要额外信令。

:::en
Designated forwarder election still applies for broadcast and multicast traffic: only the DF forwards flooded traffic onto the segment, so that a broadcast frame is not duplicated by every multi-homing PE.
:::

广播/组播仍需 **DF（指定转发者）选举**：只有 DF 把泛洪流量送到该网段，否则一个广播帧会被每台多归 PE 各复制一份。

## 7.4 配置骨架

```text
segment-routing
 srv6
  locator MAIN
   micro-segment behavior unode psp-usd
   prefix fc00:0:7::/48
  !
 !
!
l2vpn
 bridge group BG1
  bridge-domain BD100
   interface HundredGigE0/0/0/1.100
   !
   evi 100
   !
  !
 !
!
evpn
 interface HundredGigE0/0/0/1.100
  ethernet-segment
   identifier type 0 00.01.02.03.04.05.06.07.08
  !
 !
```

```text
show evpn evi 100
show l2vpn bridge-domain bd-name BD100 detail
show segment-routing srv6 sid
```

## 实战案例：DC 间 E-Line 迁移与三个坑

**场景**：两个 DC 之间用 E-Line 承载存储复制流量，原方案 VXLAN + 网关，改造为 SRv6 EVPN，要求迁移期零丢包。

**步骤**：

1. 两端 PE 建立 EVPN 邻居，先只通告 Type 4/1，确认多归与 DF 正常。
2. 建立 EVI，配置 `End.DX2` 的 per-EVI SID；先不开业务，只验证 SID 学习与 FIB。
3. 逐步把 AC 从旧网关切到新 PE，用 Type 2 的 MAC 学习确认无环路。
4. 全量切换后关闭 VXLAN 网关。

**三个典型问题**：

| 现象 | 根因 | 处理 |
|---|---|---|
| 切换后 MAC 抖动 | 新旧路径并存，同一 MAC 被两边学习 | 用 Type 1 的别名 + 分割 Horizon，或缩短 MAC 老化 |
| 广播风暴 | DF 选举异常，多台 PE 同时泛洪 | 检查 ES 配置与 Type 4 路由，确认 DF 唯一 |
| 大帧被丢 | 封装后超过 MTU | 提高 Underlay MTU 或对 E-Line 做分片策略（见第 10 章） |
| 多归链路利用率不均 | 用了单播 SID 而非 anycast SID | 统一 anycast SID，让 ECMP 生效 |

:::en
Note the interaction between L2 services and MTU: an L2 frame already carries its own header, and SRv6 adds an outer IPv6 header. If the underlay MTU is not increased, large frames are silently dropped, which in a storage replication service shows up as retransmissions rather than an obvious outage.
:::

特别注意二层业务与 MTU 的相互作用：二层帧本身有头部，SRv6 再加一层外层 IPv6。如果 Underlay MTU 没有提升，大帧会被静默丢弃——在存储复制业务里，这表现为"重传变多"而不是明显的中断，极难定位。

## 本章小结

1. 四个行为对应四种语义：点对点、VLAN 感知、未知单播泛洪、组播复制。
2. `End.DT2M` 的 Arg 携带 BD，一个 SID 服务多个桥域。
3. EVPN 路由类型不变，标签字段换成 SRv6 L2 Service TLV。
4. 多归用 anycast SID 获得自动负载分担，DF 仍负责泛洪去重。
5. 海量 E-Line 靠 `End.DX2` + 32 bit Wide uSID（第 15 章阿里案例）。
