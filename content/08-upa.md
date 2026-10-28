# 08 · 不可达前缀通告 UPA

> 对应原书第 8 章 *Unreachable Prefix Announcement (UPA)*。这是全书最短、却最"救命"的一章：**它解决汇总 + BGP PIC 组合下最隐蔽的静默黑洞。**

## 8.1 故障长什么样

:::en
Consider a PE that advertises a summary route for a large block of prefixes, and an upstream PE that uses BGP PIC edge protection with a backup path. When the downstream PE loses one specific prefix inside the summary, the summary route itself does not change: it is still originated by the summarizing router. The upstream PE therefore keeps sending traffic for the lost prefix toward a router that can no longer deliver it, and the packet is silently dropped.
:::

设想一台 PE 为一大段前缀通告汇总路由，上游 PE 使用 BGP PIC edge 备份路径。当下游 PE 丢失汇总内的**某一个具体前缀**时，汇总路由本身没有任何变化——它仍由汇总路由器产生。于是上游继续把该前缀的流量发给一台已经无法投递的路由器，报文被**静默丢弃**。

:::en
The failure is invisible to BGP: the BGP session is up, the next hop is reachable, and the summary route is present. Only the data plane knows, and only by dropping packets. This is one of the most expensive failure modes in a large network, because it can last for minutes with no alarm.
:::

对 BGP 来说这个故障是"看不见"的：会话正常、下一跳可达、汇总路由在表中。只有数据面知道，而它的表达方式就是丢包。这种故障在大网里代价极高——可能持续几分钟而没有任何告警。

## 8.2 UPA 怎么解决

:::en
UPA is an IGP signaling mechanism. When a router loses reachability to a prefix that it had previously advertised, or that is covered by a summary it originates, it sends an explicit IGP announcement stating that the prefix is unreachable. Upstream routers react immediately instead of waiting for a BGP timeout, and PIC can switch to the backup path.
:::

UPA 是一种 **IGP 信令机制**：当路由器丢失到某前缀的可达性（或该前缀被它自己产生的汇总覆盖）时，它发一条**显式的 IGP 通告，声明该前缀不可达**。上游路由器立即反应，而不必等 BGP 超时，PIC 也就有机会切到备份路径。

```text
正常:        [PE3] ==(iBGP 10.1.1.0/24, NH=PE3)==> [PE1]  → 数据走 PE3
故障:        [PE3] 失去 10.1.1.0/24
             PE3 --IGP UPA(10.1.1.0/24 unreachable)--> [ABR]
             [ABR] 立即撤销/压低该前缀 → 上游 PIC 切到备份 PE
```

:::en
The announcement carries the specific prefix, not the summary, so the summarization benefit is preserved: the core still only carries the aggregate, and UPA is only used as a fast negative signal for the affected component.
:::

关键在于：UPA 携带的是**具体前缀**，不是汇总。所以汇总带来的规模收益完全保留——核心仍然只装聚合路由，UPA 只是为受影响的分量提供一个"快速负面信号"。

## 8.3 与其他机制的分工

| 机制 | 解决什么 | 生效时间 |
|---|---|---|
| TI-LFA | 链路/节点故障的转发面保护 | < 50 ms |
| BGP PIC core | 下一跳不可达时的备份路径 | 亚秒 |
| BGP PIC edge | 边缘 PE 故障时的备份 | 亚秒 |
| 汇总 + Null0 | 抑制"汇总内有、实际没有"的流量外泄 | 立即（但会黑洞） |
| **UPA** | **让 PIC 知道"汇总内某分量没了"** | 立即 |

:::en
Without UPA, PIC edge and summarization fight each other: summarization hides the failure that PIC needs to see. With UPA, both can coexist, which is why operators who summarize aggressively also deploy UPA as a mandatory companion.
:::

没有 UPA 时，PIC edge 与汇总互相打架：**汇总恰好隐藏了 PIC 需要看到的故障**。有了 UPA，两者可以共存——所以激进做汇总的运营商都把 UPA 当作强制配套。

## 实战案例：一分钟的静默丢包

**现象**：核心到某地市的双 PE 冗余，协议全绿、监控无告警，但该地市 10.1.1.0/24 网段业务中断约 70 秒后自行恢复。

**复盘**：

1. 逻辑拓扑：地市 PE3 与 PE4 双归核心，PE3 为主用。核心侧对地市汇总为 `fdbb:bb00:0100::/40` 与 `10.1.0.0/16`。
2. 故障：PE3 上到某台汇聚的链路中断，导致 `10.1.1.0/24` 在 PE3 上不可达，但 PE3 仍通告 `10.1.0.0/16` 汇总。
3. 结果：核心 ABR 的 BGP 路由不变，流量继续压向 PE3，PE3 的 Null0 静默丢弃。直到 IGP 重收敛后 PE4 的明细路由胜出，业务才恢复。
4. 修正：在 PE3/PE4 与 ABR 上启用 UPA，并在 route-policy 里保证"分量丢失即发 UPA"；实测切换时间从 70 秒降到亚秒级。

**上线检查**：

| 检查项 | 说明 |
|---|---|
| IGP 是否支持 UPA | IOS XR 需在 IS-IS 地址族下开启 |
| 是否只对 locator/汇总分量发 | 避免 UPA 泛洪导致 IGP 抖动 |
| 与 BGP PIC 是否联动 | 确认 `bgp pic` 在 ABR 上生效 |
| 汇总边界是否保留明细 | UPA 需要知道分量状态 |

## 本章小结

1. 汇总 + PIC 的组合会产生"协议全绿、数据黑洞"的隐蔽故障。
2. UPA 用 IGP 显式通告"某分量不可达"，把故障信息从数据面搬到控制面。
3. 它不破坏汇总的规模收益，只是补上 PIC 缺失的那条负向信号。
4. 激进汇总的网络必须把 UPA 作为强制配套。
