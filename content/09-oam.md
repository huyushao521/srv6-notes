# 09 · SRv6 Ping 与 Traceroute

> 对应原书第 9 章 *SRv6 Ping and Traceroute*（RFC 9259）。这一章解决一个很实际的问题：**MPLS 时代那套 `ping mpls` / `trace mpls` 没了，怎么验证一条 SID 列表真的按你设计的方式转发？**

## 9.1 为什么要新的 OAM

:::en
In an MPLS network, a label switched path can be tested with LSP ping: the probe carries the label stack, and each router along the path answers because the label identifies the path. In SRv6 there is no label stack and no per-path state, so the probe must carry the segment list itself, and the responder must be identified by a SID rather than by a label.
:::

MPLS 用 LSP ping 测一条 LSP：探测报文带着标签栈，沿途路由器因为标签能标识路径而回应。SRv6 没有标签栈、也没有"路径"这个对象，于是**探测报文必须自己携带段列表**，回应方由 SID 标识而不是标签。

:::en
RFC 9259 defines the mechanisms. A probe is an IPv6 packet with an SRH whose segment list contains the path under test; the O-flag in the SRH flags indicates that this packet is an OAM packet, so that a segment endpoint that would normally forward it can instead respond with an ICMPv6 message.
:::

RFC 9259 定义了机制：探测报文是一个带 SRH 的 IPv6 包，SRH 的段列表就是被测路径；SRH flags 里的 **O-flag** 标记"这是 OAM 报文"，于是本应转发的端点可以改为回一个 ICMPv6 消息。

## 9.2 Ping 的工作方式

```text
ping srv6 fc00:0:5:e001:: sid-list fc00:0:2::, fc00:0:3::, fc00:0:5:e001::
```

:::en
The ping probe is forwarded along the segment list exactly like user traffic, so it validates the data plane, not just the control plane. If the last SID is a service SID such as End.DT46, the responder validates that the SID is instantiated and reachable, but does not perform the VPN lookup — which is why a successful ping to a VPN SID does not prove the VPN itself is healthy.
:::

ping 探测沿段列表转发，**和用户流量完全一样**，因此它验证的是数据面而非仅仅控制面。但注意：若最后一段是 `End.DT46` 这类业务 SID，回应方只验证"SID 已实例化且可达"，**不做 VPN 查表**——所以"ping 通 VPN SID"并不等于 VPN 业务健康。

| 探测目标 | 验证内容 | 不能证明 |
|---|---|---|
| Locator / uN | locator 可达、End 行为正常 | 业务是否通 |
| uA（End.X） | 指定链路可转发 | 对端是否继续正确转发 |
| 业务 SID（uDT/uDX） | SID 实例化、行为注册 | VRF 内路由、CE 侧 |
| 完整 SID list | 整条显式路径可走 | 备份路径 |

## 9.3 Traceroute 的两种模式

:::en
Traceroute can be run in two modes. In the "with SRH" mode the probe carries the full segment list and each segment endpoint reports itself, which reveals how the list is executed. In the "without SRH" mode, the tool sends individual probes to each SID in turn, which reveals the path the network would take to reach that SID. The two answers differ whenever the underlay ECMP splits traffic.
:::

traceroute 有两种模式：

- **带 SRH**：探测报文携带完整段列表，每个端点各自上报，反映"段列表是怎么被执行的"。
- **不带 SRH**：逐个 SID 单独探测，反映"网络去往该 SID 走的是哪条路"。

当 Underlay 的 ECMP 把流量分散到不同路径时，两种结果会不一致——这不是故障，而是 ECMP 的正常表现。判断"是否真的按设计路径转发"，必须用带 SRH 的模式。

```text
traceroute srv6 fc00:0:5:e001:: sid-list fc00:0:2::,fc00:0:3::,fc00:0:5:e001::
 1  fc00:0:2::    0.4 ms   ← uN 执行
 2  fc00:0:3::    0.7 ms
 3  fc00:0:5:e001:: 1.1 ms ← 业务 SID 到达
```

## 9.4 与 TI-LFA 的配合

:::en
The most valuable use of SRv6 traceroute is verifying repair paths. You can inject the repair segment list that TI-LFA computed and trace it, which proves that the backup path is not only installed but actually forwarding. Without this, TI-LFA failures are only discovered during a real outage.
:::

SRv6 traceroute 最有价值的用法是**验证修复路径**：把 TI-LFA 算出来的修复段列表手工注入并 trace，证明备份路径不仅装了表、而且真的能转发。没有这一步，TI-LFA 的问题只能在真实故障时才暴露——那时已经晚了。

## 实战案例：一次"业务通但绕远"的定位

**现象**：A 市到 B 市业务时延从 8 ms 涨到 21 ms，业务可用，客户投诉。

**定位过程**：

1. `traceroute srv6 <B市PE的uN>`（不带 SRH）→ 发现路径在核心绕了一个平面。
2. 对照设计文档：该业务本应走 algo 128 的 locator，实际走的是 algo 0 的 locator。
3. `show bgp vpnv4 unicast <prefix>` → 收到的 SID 是 `fdbb:bb00:...`（algo 0 块），而不是 `fdbb:bb01:...`（algo 128 块）。
4. 根因：出口 PE 上该 VRF 的 locator 绑定错了——配置里 `locator LOWLAT` 没有在 BGP 侧生效，实际用了 MAIN。
5. 修正 locator 绑定后，`traceroute` 显示路径回到低时延平面，时延恢复 8 ms。

**排障清单**：

| 症状 | 先看什么 |
|---|---|
| 完全不通 | 先用 ping 打 locator，再 ping 业务 SID，逐段收窄 |
| 通但绕远 | 对比 SID 前缀（哪个 algo 的 Block）与设计 |
| 间歇不通 | 用带 SRH 的 trace 验证是否 ECMP 某条成员坏了 |
| 故障后不恢复 | 手工注入 TI-LFA 修复列表 trace，验证备份路径 |

## 本章小结

1. SRv6 OAM 用 SRH + O-flag 实现，探测沿真实数据面走。
2. ping 业务 SID 只证明 SID 存在，不证明业务健康。
3. traceroute 分"带 SRH"与"不带 SRH"，前者验证程序执行，后者验证可达路径。
4. 最有价值的用法：故障前验证 TI-LFA 修复路径。
