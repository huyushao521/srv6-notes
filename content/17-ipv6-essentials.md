# 17 · IPv6 必备知识：SRv6 的地基

> **本章定位**：原书第 17 章《IPv6 Essentials》。前面 16 章的所有"魔法"都压在 IPv6 的五六条规则上；**读不懂这一章，前面只能背结论**。英文块为原文摘录，中文为完整翻译，Figure 17.1–17.4 重绘。

**本章要拿到的东西**：

| 问题 | 对应小节 |
|---|---|
| 为什么 P 路由器不支持 SRv6 也能转发 | 17.3 |
| 为什么"P 上误配 SID"会让路径莫名中断 | 17.3.1 |
| 扩展头链是什么形状，NH=43 是什么意思 | 17.2 |
| 为什么 SR 域几乎都用 ULA | 17.4 |
| 1280 与 1500 之间那 220 字节为什么是雷区 | 17.5 |
| Flow Label 写 0 会发生什么 | 17.6 |

一句话概括：**这一章不用背，只需要理解四条"约束"**——**头是固定的、扩展是链式的、路由头只有目的节点处理、中间不许分片**。SRv6 的所有设计（无状态、P 节点零改造、必须提 MTU）都是这四条的直接推论。

## 17.0 四条规则如何决定 SRv6 的设计

| IPv6 规则 | 直接推出 |
|---|---|
| 基本头固定 40 字节，其余进扩展头 | SRv6 可以"只加一个路由头"，不必改基本头 |
| 路由头**只由 DA 所指节点处理** | **P 节点无需支持 SRv6**（这正是全书的前提） |
| 中间节点**禁止分片** | **MTU 必须规划**，PMTUD 只能兜底 |
| 哈希用 (SA, DA, Flow Label) | 入口必须写入**稳定的 Flow Label** |

```text
图 17-1：四条规则的因果（原书 Figure 17.1 重绘）

  40B 固定头 ──► 扩展头链 ──► SRH(NH=43) ──► uSID 塞进 DA
                                     │
  只有 DA 节点处理路由头 ─────────────┘
        │
        └──► P 节点只按 DA 转发（零 SRv6 状态）★ 全书基石

  禁止中间分片 ──► MTU 必须 ≥ 客户 MTU + 40（第 10 章）
  Flow Label 参与哈希 ──► 入口写稳定熵（17.6）
```

## 17.1 固定 40 字节的基本头

:::en
The IPv6 header is fixed at 40 bytes and contains only what is needed for forwarding: version, traffic class, flow label, payload length, next header, hop limit, source and destination addresses. Everything else — fragmentation, routing, options — has been moved into extension headers, which is what makes IPv6 extensible without changing the base header.
:::

IPv6 基本头固定 **40 字节**，只放转发必需的信息：版本、流量类别、流标签、净荷长度、下一头部、跳数限制、源与目的地址。其余一切（分片、路由、选项）全部移到**扩展头**——**这正是 IPv6 无需改基本头就能扩展的原因，也是 SRv6 能"只加一个路由头"的前提**。

| 字段 | 长度 | 与 SRv6 的关系 |
|---|---|---|
| Version | 4 b | 固定 6 |
| Traffic Class | 8 b | DSCP 映射（第 12 章元数据的替代承载处） |
| **Flow Label** | **20 b** | **熵来源，决定 ECMP 分担（17.6）** |
| Payload Length | 16 b | **含扩展头**，不含基本头 |
| **Next Header** | **8 b** | **43 = 路由头（SRH）**；4 = IPv4；6 = TCP；17 = UDP；58 = ICMPv6 |
| Hop Limit | 8 b | TTL 语义 |
| SA / DA | 128 b × 2 | **DA 承载 uSID 容器**（第 15 章 WLIB） |

## 17.2 扩展头链

:::en
Extension headers are chained: each header carries a Next Header field pointing to the next one, and the chain ends with a value that identifies the upper layer protocol, such as 4 for IPv4 or 6 for TCP. SRv6 uses a routing header of type 4, which means a packet with SRv6 encapsulation has Next Header 43 and, inside the SRH, another Next Header for the payload.
:::

扩展头是**链式**的：每个头带一个 `Next Header` 指向下一个，链尾的值标识上层协议（**4 = IPv4、6 = TCP、17 = UDP、58 = ICMPv6**）。SRv6 用的是 **Routing Header Type 4**，所以 SRv6 封装包的外层是 `Next Header = 43`，**SRH 内部又有一个 `Next Header` 指向净荷**。

```text
图 17-2：两种封装的头部链（原书 Figure 17.2 重绘）

  ① uSID 业务转发（无 SRH，最常见）
     [IPv6 NH=4 ] [内层 IPv4] [TCP]
                 └─ 直接指向内层协议，只有 40 B 外层

  ② 带 SRH（段列表需要显式表达时）
     [IPv6 NH=43] [SRH NH=4] [内层 IPv4] [TCP]
                    │     └─ 内层版本
                    └─ 路由头类型 4（SRH = Segment Routing Header）

  ③ 分层封装（VPN 承载）
     [IPv6 NH=4] [IPv4 内层] [UDP] [GTP-U] [用户 IP]
```

:::en
This chaining explains a very common deployment issue: devices and firewalls that only parse the base header, or that reject unknown extension headers, will drop SRv6 packets even though the payload is perfectly valid. Rule sets must be updated to allow protocol 43 within the SR domain.
:::

链式结构解释了一个**非常常见的部署问题**：**只解析基本头、或"遇到未知扩展头就丢"的设备与防火墙，会把完全合法的 SRv6 报文丢掉**。**域内规则必须显式放行协议号 43。**

| 设备行为 | 后果 | 现象 |
|---|---|---|
| 见 NH=43 就丢 | 报文在设备处消失 | **无日志**，只有丢包计数 |
| 只解析到 IPv4/IPv6 就停 | 看不到更内层 | 策略不匹配（第 12 章） |
| 重写扩展头 | SRH 被改/被删 | 后续段失效、元数据丢失 |
| 正常放行 | 无影响 | — |

## 17.3 关键规则：谁能处理路由头

:::en
RFC 8200 states that a routing header is processed only by the node identified in the destination address of the packet. Intermediate nodes must not examine or process it. This single rule is what allows transit routers to remain SRv6-unaware: they forward on the destination address, and the routing header is invisible to them until the packet reaches the node it names.
:::

RFC 8200 规定：**路由头只由目的地址所指的节点处理，中间节点不得检查或处理它**。**就这一条规则，让转发节点可以完全不支持 SRv6**——它们**只按目的地址转发**，路由头在**到达被寻址节点前对它们"不可见"**。

```text
图 17-3：中间节点对 SRH "不可见"（原书 Figure 17.3 重绘）

  PE-1 ──► P-1 ──► P-2 ──► PE-2
           │       │
           │       └─ 只看 DA 的 locator，转发
           └─ 完全不解析 SRH（也无需实现 SRv6）
                    │
                    └──► PE-2：DA 命中本地 SID → 才处理 SRH

  如果 P-1 上误配了与 DA 匹配的 SID：
  → P-1 认为自己就是"目的节点" → 越权处理 SRH → 路径中断
```

### 17.3.1 反过来也要记住：越权处理的风险

:::en
The same rule has a sharp edge: a transit router that happens to have a local SID matching the destination address will consider itself the addressed node and will process the routing header. This is how a misconfigured SID on a core router silently breaks a path that is otherwise correct.
:::

这条规则有锋利的一面：**一台核心路由器如果恰好配了与 DA 匹配的本地 SID**，它就会**认为自己是"被寻址节点"**，从而**处理路由头**。**这就是"核心路由器上误配 SID 会静默中断路径"的原因。**

| 误配场景 | 现象 | 排查 |
|---|---|---|
| P 上配了与某 locator 重叠的 SID | 路径在 P 处中断，业务不通 | `show segment-routing srv6 sid all` 在 P 上查 |
| P 上配了 anycast SID | 流量被"吸"到 P | 对比各节点 SID 表 |
| 服务设备配了同名 SID | 包被设备消费 | 设备侧抓包 |

**这条规则也解释了为什么 locator 规划必须"全网唯一"**（第 10 章）：只有唯一，才不会有第二台设备认为自己该处理这个 DA。

## 17.4 地址类型与前缀

:::en
Three address types matter: global unicast addresses, unique local addresses in FC00::/7, and link-local addresses in FE80::/10. SRv6 deployments typically use ULA space for the SR domain, because ULA is not routable outside the domain and therefore provides both opacity and a guarantee that SIDs cannot leak to the Internet.
:::

三类地址需要分清：

| 类型 | 前缀 | 用途 | 在 SRv6 里的角色 |
|---|---|---|---|
| 全球单播（GUA） | `2000::/3` | 公网可达 | 不建议用于 SID（会泄露到 Internet） |
| **唯一本地（ULA）** | `FC00::/7` | **域内私有** | **SR 域首选**：不可域外路由，天然不透明 |
| 链路本地 | `FE80::/10` | 邻居发现、单跳协议 | 不用于 SID |

:::en
Using ULA for the SR domain is the common choice of both Bell and Alibaba: it provides scale, because FC00::/7 is enormous, and it provides security, because SIDs cannot leak to the Internet.
:::

用 ULA 做 SR 域是 **Bell 与阿里的共同选择**：**既是规模**（`FC00::/7` 巨大，Bell 只用了 0.0015%），**也是安全**（**SID 不会泄露到 Internet**）。

| 选择 | 规模 | 风险 | 谁的用法 |
|---|---|---|---|
| ULA `fd00::/8` 的子段 | 2^120 | 需自管唯一性 | Bell `fdbb:bb00::/24` |
| ULA `fd00:cc::/24` | 充裕 | 同上 | 阿里 `fd00:cc::` |
| GUA | 大 | **SID 暴露在公网**，可被探测 | 不推荐 |
| 2001:db8::/32 | 文档专用 | 不可用于生产 | 仅示例 |

## 17.5 MTU 与 PMTUD

:::en
IPv6 requires a minimum link MTU of 1280 bytes and forbids routers from fragmenting packets. Fragmentation is left to the source, which discovers the path MTU using ICMPv6 Packet Too Big messages. In an SRv6 domain this makes MTU planning mandatory: the encapsulation adds 40 bytes and possibly an SRH, so the underlay MTU must be raised above the customer MTU plus the encapsulation overhead.
:::

IPv6 规定**链路最小 MTU 为 1280 字节**，且**禁止路由器分片**；分片只能由源端做，源端靠 **ICMPv6 Packet Too Big** 发现路径 MTU。于是 SRv6 域里 **MTU 规划是硬要求**：**封装 +40 字节（含 SRH 更多）**，**Underlay MTU 必须大于"客户 MTU + 封装开销"**。

```text
图 17-4：MTU 的三个数字（原书 Figure 17.4 重绘）

  1280 ──────────── IPv6 强制最小链路 MTU
                      低于此值无法运行 IPv6（不是"性能差"，是"不通"）
  1500 ──────────── 以太网标准 MTU（客户侧通常按此规划）
  1540 ──────────── 1500 + 40（SRv6 无 SRH）
  1564 ──────────── 1500 + 64（SRv6 带 1 个容器 SID 的 SRH）
  1600 ──────────── 生产网推荐值（留余量给 SRH/未来扩展头）

  1500 → 1540 之间那 40 字节，就是最经典的雷区：
  客户侧一切正常，加上封装就超了，且中间不报错，只静默丢
```

:::en
Relying on PMTUD is fragile: ICMPv6 is often filtered by security policies, and a lost Packet Too Big message turns into a black hole that affects only large packets. This is exactly the failure mode that is hardest to diagnose, because pings and small transactions keep working.
:::

**依赖 PMTUD 很脆弱**：ICMPv6 常被安全策略过滤，**一条 Packet Too Big 丢了就形成"只影响大包的黑洞"**——ping 与小事务全正常，最难查。所以**生产网直接抬高 MTU（常见 1600 / 9000），把 PMTUD 当兜底**。

| 措施 | 说明 | 优先级 |
|---|---|---|
| Underlay MTU ≥ 1600 | 预留 SRH 与 TI-LFA 余量 | **必做** |
| 放行 ICMPv6 type 2 | 不要一刀切过滤 ICMPv6 | 必做 |
| 业务侧 MSS clamp | TCP 场景兜底 | 建议 |
| 监控大包丢包率 | 单独统计 > 1400 字节 | 建议 |

## 17.6 邻居发现、Flow Label 与 ECMP

:::en
Neighbor Discovery replaces ARP, and Router Advertisement provides prefixes and the default router. For SRv6, the relevant part is that flow hashing in the fabric uses the source address, destination address and flow label — which is why the ingress node must write a stable, well-distributed value into the flow label.
:::

**ND 取代 ARP，RA 提供前缀与默认路由**。对 SRv6 而言相关的点是：**转发面哈希用 (SA, DA, Flow Label)**，所以**入口节点必须写入稳定且分布良好的 Flow Label**：

- **写 0** → 所有流在同一位置哈希 → **全走一条链路**，带宽浪费；
- **每包随机** → 同一条流的不同包走不同路径 → **乱序**，TCP 性能骤降。

| Flow Label 取值 | 结果 | 推荐度 |
|---|---|---|
| 全 0 | 单路径，ECMP 失效 | ✘ |
| 每包随机 | 乱序，TCP 重排 | ✘ |
| **按流的五元组哈希** | **同流同路径，异流分担** | **✔** |
| 继承内层 Flow Label | 透传端到端语义 | 视实现 |

:::en
The rule of thumb is that entropy must be computed once, at the ingress, from the inner flow, and must remain constant for the lifetime of that flow. Recomputing it at every hop, or deriving it from the outer header alone, defeats the purpose.
:::

经验法则：**熵只能在入口算一次，从内层流算出来，且在该流的生命周期内保持不变**。**逐跳重算**、或**只从外层头推导**，都会让哈希失去意义。

## 17.7 SRv6 相关字段速查

| 需要知道的 | 值/规则 | 出现在哪一章 |
|---|---|---|
| SRH 的 NH 值 | 43 | 17.2 |
| SRH 类型 | Routing Header Type 4 | 17.2 |
| 内层 IPv4 / TCP / UDP / ICMPv6 | 4 / 6 / 17 / 58 | 17.2 |
| 路由头处理者 | **DA 所指节点** | 17.3 |
| 最小链路 MTU | 1280 | 17.5 |
| 推荐 Underlay MTU | 1600 | 10.4 / 17.5 |
| ULA 前缀 | `FC00::/7`（常用 `fd00::/8`） | 14.3 / 15.4 |
| 链路本地 | `FE80::/10` | 17.4 |
| 哈希输入 | SA + DA + Flow Label | 17.6 |
| ICMPv6 Packet Too Big | type 2 | 17.5 |

## 17.8 本章小结

:::en
IPv6 is not a detail of SRv6; it is the reason SRv6 works the way it does. The fixed header and the extension chain make a routing header possible without touching the base header, the routing header processing rule keeps transit routers stateless, the no-fragmentation rule makes MTU planning mandatory, and the flow label rule makes load balancing the ingress node's responsibility.
:::

IPv6 **不是 SRv6 的细节，而是 SRv6 之所以长成这样**：**固定头 + 扩展链**让"加一个路由头"成为可能；**路由头处理规则**让**转发节点保持无状态**；**禁止中间分片**把 **MTU 规划变成硬要求**；**Flow Label 参与哈希**把**负载分担的责任交给入口**。

| 规则 | 正面推论 | 反面风险 |
|---|---|---|
| 40 B 固定头 | 扩展不需改基本头 | 扩展头被老设备丢弃 |
| 只有 DA 节点处理路由头 | **P 节点零改造** | **P 上误配 SID 即越权** |
| 禁止中间分片 | 转发简单、时延可预测 | **MTU 不规划就静默丢大包** |
| Flow Label 参与哈希 | ECMP 有效 | 写 0 / 随机 → 单路径或乱序 |
| ULA 私有空间 | 规模 + 不泄露 | 需自管唯一性、跨域需转换 |

一句话收束：**SRv6 没有发明任何东西，它只是把 IPv6 已有的四条规则用到了极致**——理解了这四条，前面 16 章的每个"为什么"都有了答案。

## 实战案例

### 案例 A：一次"只有大包不通"的定位

**现象**：SRv6 改造后，同一业务 `ping -s 64` 通、`ping -s 1400` 不通；TCP 建连成功但传输卡死。

**排查路径**：

```text
① 二分包长：1400 通、1452 开始失败 → 典型 MTU
② 两端抓包：大包发出后无回应，中间没有 ICMPv6 Too Big
   （说明 PTB 被过滤了，源端永远不知道）
③ 计算：客户 1500 + 外层 40 = 1540 > 链路 MTU 1500 → 必丢
④ 处理：
   a. 核心链路 MTU 提到 1600（根治）
   b. 放行 ICMPv6 type 2（兜底，让 PMTUD 至少能工作）
   c. TCP 业务加 MSS clamp（过渡期）
```

| 预防措施 | 说明 |
|---|---|
| Underlay MTU ≥ 1600 | 预留 SRH 与 TI-LFA 余量 |
| 放行 ICMPv6 type 2 | 不要一刀切过滤 ICMPv6 |
| 业务侧 MSS 调整 | TCP 场景兜底 |
| 监控大包丢包率 | 单独统计 > 1400 字节的丢包 |

### 案例 B：Flow Label 写 0，链路利用率只有 1/N

**现象**：两条 100G 链路做 ECMP，割接后**一条 95%、一条 12%**，业务本身正常。

```text
① 抓包看外层 Flow Label：全部为 0
② 入口 PE 的封装实现把 Flow Label 固定填 0
   → 哈希输入只剩 (SA, DA)，而 SA/DA 对同一业务是固定的
   → 所有流落到同一条成员链路
③ 修复：入口改为"按内层五元组哈希写 Flow Label"
④ 复测：两条链路接近 50:50
```

**教训**：**ECMP 不是"配了就生效"**，它依赖**入口写入足够熵**。这条在 uSID 场景尤其容易踩——因为外层头很短，**除了 Flow Label 几乎没有可变字段**（DA 是 SID，SA 是本机 locator）。

### 案例 C：防火墙丢弃 NH=43，业务"无日志中断"

**现象**：服务链上线后业务全断，**防火墙没有任何日志**，接口计数显示"收到并丢弃"。

```text
① 防火墙侧抓包：报文为 [IPv6 NH=43][SRH][内层 IPv4]
② 设备策略："未识别的 IPv6 扩展头一律丢弃"（默认安全加固）
③ 结果：报文在防火墙处被静默丢弃，无应用层日志
④ 修复方案（择一）：
   a. 防火墙放行 NH=43（仅限 SR 域内接口）
   b. 用 SR Proxy / SERA 让设备只看到裸报文（第 13 章）
⑤ 复测：策略计数正常增长，业务恢复
```

**教训**：**"安全加固"与"SRv6 可用性"经常直接冲突**。上线前的检查单必须包含一条：**域内所有中间设备是否放行 NH=43**。

## 延伸阅读

- **RFC 8200**：IPv6 协议规范，40 字节头、扩展头链、"只有 DA 节点处理路由头"、禁止中间分片的原始条文。
- **RFC 8201**：PMTUD for IPv6，1280 最小 MTU 与 Packet Too Big 机制。
- **RFC 8754**：SRH，Routing Header Type 4 的格式与处理。
- **RFC 4193**：ULA（`FC00::/7`），17.4 的规范依据。
- **RFC 6437 / RFC 6438**：Flow Label 规范与隧道中的使用，17.6 的依据。
- **RFC 4861**：邻居发现（ND/RA），17.6 的前半部分。
- 交叉参考：第 2 章（封装与熵）、第 10 章（MTU 预算）、第 12/13 章（扩展头导致的服务失明）、第 14/15 章（ULA 的实际用法）。
