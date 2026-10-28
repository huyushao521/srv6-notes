# 17 · IPv6 必备知识

> 对应原书第 17 章 *IPv6 Essentials*。SRv6 的所有"魔法"都建立在 IPv6 的这几条规则上，读不懂这一章，前面 16 章都只能背结论。

## 17.1 固定 40 字节的基本头

:::en
The IPv6 header is fixed at 40 bytes and contains only what is needed for forwarding: version, traffic class, flow label, payload length, next header, hop limit, source and destination addresses. Everything else — fragmentation, routing, options — has been moved into extension headers, which is what makes IPv6 extensible without changing the base header.
:::

IPv6 基本头固定 **40 字节**，只放转发必需的信息：版本、流量类别、流标签、净荷长度、下一头部、跳数限制、源与目的地址。其余一切（分片、路由、选项）全部移到**扩展头**——这正是 IPv6 无需改基本头就能扩展的原因，也是 SRv6 能"只加一个路由头"的前提。

| 字段 | 长度 | 与 SRv6 的关系 |
|---|---|---|
| Version | 4b | 固定 6 |
| Traffic Class | 8b | 可用于 DSCP 映射 |
| **Flow Label** | **20b** | **SRv6 的熵来源（第 2.8 节）** |
| Payload Length | 16b | 含扩展头 |
| **Next Header** | **8b** | **43 = 路由头（SRH）** |
| Hop Limit | 8b | TTL 语义 |
| SA / DA | 128b×2 | **DA 承载 uSID 容器** |

## 17.2 扩展头链

:::en
Extension headers are chained: each header carries a Next Header field pointing to the next one, and the chain ends with a value that identifies the upper layer protocol, such as 4 for IPv4 or 6 for TCP. SRv6 uses a routing header of type 4, which means a packet with SRv6 encapsulation has Next Header 43 and, inside the SRH, another Next Header for the payload.
:::

扩展头是**链式**的：每个头带一个 `Next Header` 指向下一个，链尾的值标识上层协议（4 = IPv4、6 = TCP、17 = UDP、58 = ICMPv6）。SRv6 用的是 **Routing Header Type 4**，所以一个 SRv6 封装包的外层是 `Next Header = 43`，SRH 内部又有一个 `Next Header` 指向净荷。

```text
[IPv6 NH=43][SRH NH=4][IPv4 净荷]
              │        └─ 内层版本
              └─ 路由头类型 4
```

:::en
This chaining explains a very common deployment issue: devices and firewalls that only parse the base header, or that reject unknown extension headers, will drop SRv6 packets even though the payload is perfectly valid. Rule sets must be updated to allow protocol 43 within the SR domain.
:::

链式结构解释了一个非常常见的部署问题：**只解析基本头、或"遇到未知扩展头就丢"的设备与防火墙，会把完全合法的 SRv6 报文丢掉**。域内规则必须显式放行协议号 43。

## 17.3 关键规则：谁能处理路由头

:::en
RFC 8200 states that a routing header is processed only by the node identified in the destination address of the packet. Intermediate nodes must not examine or process it. This single rule is what allows transit routers to remain SRv6-unaware: they forward on the destination address, and the routing header is invisible to them until the packet reaches the node it names.
:::

RFC 8200 规定：**路由头只由目的地址所指的节点处理**，中间节点不得检查或处理它。就这一条规则，让转发节点可以完全不支持 SRv6——它们只按目的地址转发，路由头在到达被寻址节点前对它们"不可见"。

> 反过来也要记住：**如果一台 P 路由器上配了与报文 DA 匹配的 SID，它就会"越权"处理**。这类误配在现网表现为"路径莫名中断"或"SL 被意外修改"。

## 17.4 地址类型与前缀

:::en
Three address types matter: global unicast addresses, unique local addresses in FC00::/7, and link-local addresses in FE80::/10. SRv6 deployments typically use ULA space for the SR domain, because ULA is not routable outside the domain and therefore provides both opacity and a guarantee that SIDs cannot leak to the Internet.
:::

三类地址需要分清：

| 类型 | 前缀 | 用途 |
|---|---|---|
| 全球单播（GUA） | 2000::/3 | 公网可达 |
| 唯一本地（ULA） | FC00::/7 | **SRv6 域内首选**：不可在域外路由，天然不透明 |
| 链路本地 | FE80::/10 | 邻居发现、单跳协议 |

用 ULA 做 SR 域是 Bell、阿里共同的选择：既是规模（`FC00::/7` 巨大），也是安全（SID 不会泄露到 Internet）。

## 17.5 MTU 与 PMTUD

:::en
IPv6 requires a minimum link MTU of 1280 bytes and forbids routers from fragmenting packets. Fragmentation is left to the source, which discovers the path MTU using ICMPv6 Packet Too Big messages. In an SRv6 domain this makes MTU planning mandatory: the encapsulation adds 40 bytes and possibly an SRH, so the underlay MTU must be raised above the customer MTU plus the encapsulation overhead.
:::

IPv6 规定链路最小 MTU 为 **1280 字节**，且**禁止路由器分片**；分片只能由源端做，源端靠 ICMPv6 的 **Packet Too Big** 消息发现路径 MTU。于是 SRv6 域里 MTU 规划是硬要求：封装 +40 字节（含 SRH 更多），Underlay MTU 必须大于"客户 MTU + 封装开销"。

:::en
Relying on PMTUD is fragile: ICMPv6 is often filtered by security policies, and a lost Packet Too Big message turns into a black hole that affects only large packets. This is exactly the failure mode that is hardest to diagnose, because pings and small transactions keep working.
:::

依赖 PMTUD 很脆弱：ICMPv6 常被安全策略过滤，一条 Packet Too Big 丢了就形成**只影响大包的黑洞**——ping 和小事务全正常，最难查。所以生产网直接抬高 MTU（常见 1600/9000），把 PMTUD 当兜底。

## 17.6 邻居发现与 ECMP

:::en
Neighbor Discovery replaces ARP, and Router Advertisement provides prefixes and the default router. For SRv6, the relevant part is that flow hashing in the fabric uses the source address, destination address and flow label — which is why the ingress node must write a stable, well-distributed value into the flow label.
:::

ND 取代 ARP，RA 提供前缀与默认路由。对 SRv6 而言相关的点是：**转发面哈希用 (SA, DA, FlowLabel)**，所以入口节点必须写入稳定且分布良好的 Flow Label 值——写 0 或随机每包变化，都会破坏负载分担（前者导致全走一条，后者导致乱序）。

## 实战案例：一次"只有大包不通"的定位

**现象**：SRv6 改造后，同一业务 `ping -s 64` 通、`ping -s 1400` 不通；TCP 建连成功但传输卡死。

**排查路径**：

1. 先用不同包长二分：确认 1452 字节附近开始失败 → 典型 MTU 问题。
2. 在两端抓包：大包发出后无回应，中间链路无 ICMPv6 Too Big（被过滤）。
3. 计算：客户 1500 + 外层 40 = 1540 > 链路 MTU 1500 → 必须丢。
4. 处理：把核心链路 MTU 提到 1600；同时放行 ICMPv6 type 2（Packet Too Big），让 PMTUD 至少有兜底。

**预防措施**：

| 措施 | 说明 |
|---|---|
| Underlay MTU ≥ 1600 | 预留 SRH 与 TI-LFA 余量 |
| 放行 ICMPv6 type 2 | 不要一刀切过滤 ICMPv6 |
| 业务侧 MSS 调整 | TCP 场景用 MSS clamp 兜底 |
| 监控大包丢包率 | 单独统计 >1400 字节的丢包 |

## 本章小结

1. 40 字节固定头 + 扩展头链，NH=43 即 SRH。
2. 路由头只由 DA 所指节点处理——这既是"P 节点无需支持 SRv6"的依据，也是"SID 误配即越权"的风险源。
3. ULA（FC00::/7）是 SR 域的首选空间。
4. IPv6 禁止中间分片，MTU 必须规划，PMTUD 只能兜底。
5. Flow Label 是负载分担的熵，必须由入口节点正确写入。
