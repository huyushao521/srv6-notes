# 05 · IS-IS 中 Locator 的泄露、重分发与汇总

> 对应原书第 5 章 *IS-IS Locator Leaking, Redistribution and Summarization*。这是"多区域一定能通"的关键一章，也是现网 80% 的"跨区业务不通"故障的根因所在。

## 5.1 问题从哪来

:::en
IS-IS is a hierarchical protocol: Level-1 routers know only their own area, and they reach the rest of the network through the nearest Level-1/Level-2 router. A Level-2 router does not normally advertise Level-2 prefixes into a Level-1 area. As a result, an SRv6 locator originated in area A is, by default, not reachable from area B: the routers in area B have no route to it, and packets destined to its SIDs are dropped.
:::

IS-IS 是分层协议：Level-1 路由器只知道本区域，靠最近的 L1/L2 路由器出区；L2 路由器默认**不会**把 L2 前缀通告进 L1 区域。于是：**A 区产生的 SRv6 Locator，B 区默认根本不可达**——B 区的路由器没有路由，打向该 SID 的报文被直接丢弃。

这就是"PE 之间 IPv4 业务通、但 SRv6 封装后的外层 IPv6 不通"的经典现象：内层没事，外层 Locator 不可达。

## 5.2 泄露（Leaking）

:::en
Leaking means advertising a prefix from one level into another: typically from Level-2 into Level-1, so that intra-area routers can reach remote locators, and from Level-1 into Level-2, so that the backbone can reach the locators of all areas. Leaking is controlled by route policies, and it is the mechanism that makes locators reachable across the whole domain without a full mesh of adjacencies.
:::

泄露就是把前缀从一个层级通告到另一个层级：

- **L2 → L1**：让区内路由器能到达远端 locator。
- **L1 → L2**：让骨干能到达各区域的 locator。

泄露靠 route-policy 精确控制匹配（只放 locator 前缀，不放用户路由），这是它能规模化的前提。它也是"整个域内 locator 全可达、但不需要全互联邻接"的机制。

```text
router isis 1
 address-family ipv6 unicast
  advertise passive-only
  !
  redistribute isis 2 level-1 into level-2 route-policy LOC-ONLY
  redistribute isis 2 level-2 into level-1 route-policy LOC-ONLY
```

:::en
When a prefix is leaked downward, the up/down bit is set in the advertisement. If a router ever receives a leaked prefix back in the up direction, it must ignore it: this simple rule prevents loops between levels.
:::

前缀向下泄露时，通告里会置 **up/down bit**。如果某台路由器又在"向上"的方向收到同一条被泄露的前缀，必须忽略它——这一条简单规则就防止了层级之间的路由环路。

## 5.3 汇总（Summarization）

:::en
Summarization is where SRv6 pays off compared to MPLS. Because SIDs are IPv6 prefixes, 256 /48 locators can be summarized into a single /40, a gain of 256 to 1. Border routers advertise the summary into the core, and the core never needs to know the individual nodes. MPLS has no equivalent: label spaces cannot be summarized.
:::

汇总正是 SRv6 相对 MPLS 的"分红"：SID 本质是 IPv6 前缀，**256 个 /48 可以汇总成一个 /40，压缩比 256:1**。区域边界路由器把汇总前缀通告进核心，核心完全不必知道区域内部有多少节点。MPLS 做不到——标签空间不可汇总。

```text
router isis 1
 address-family ipv6 unicast
  summary-prefix fdbb:bb00:0100::/40 level-2
  summary-prefix fdbb:bb00:0200::/40 level-2
```

:::en
When a router originates a summary, it also installs a discard route for the summary prefix pointing to Null0. This guarantees that packets for components that are not actually present are dropped at the summarizing router rather than looping in the core. But it also creates a well-known failure mode: when the summarizing router loses reachability to a specific component, the discard route still attracts the traffic and silently black-holes it — this is exactly the problem that UPA solves in chapter 8.
:::

产生汇总的路由器同时会装一条指向 **Null0** 的丢弃路由。这保证"汇总里有、实际不存在"的报文在汇总点被丢弃，而不是在核心兜圈子。但它也埋下一个著名故障模式：**当汇总路由器丢失到某个具体分量的可达性时，Null0 仍在吸引流量，形成静默黑洞**——这正是第 8 章 UPA 要解决的问题。

## 5.4 多实例重分发

:::en
Large networks are often split into several IGP instances, for example a core instance and a metro instance. Locators must be redistributed between them with a route policy that matches only the locator prefixes, so that the instances exchange reachability of SIDs without exchanging customer routes.
:::

大型网络常拆成多个 IGP 实例（如 CORE 实例 + METRO 实例）。Locator 必须用 route-policy **只匹配 locator 前缀**在两个实例间重分发——让两个实例交换 SID 可达性，但不交换客户路由。混着重分发会带来路由震荡与规模爆炸。

```text
route-policy LOC-ONLY
  if destination in (SRV6-LOCATORS) then
    pass
  else
    drop
  endif
end-policy

router isis CORE
 address-family ipv6 unicast
  redistribute isis METRO level-2 into level-2 route-policy LOC-ONLY
```

## 实战案例：三个跨区故障，一个知识点

**故障一：跨区业务不通，但两端 PE 的 IPv4 客户路由都正常。**

- 现象：`ping` 客户地址通？不，实际是内层报文能生成但出不了区；抓包看到封装后的外层报文在区域边界被丢。
- 定位：`show isis route <远端 locator>` 在区内路由器上无路由 → 说明 L2 的 locator 没有泄露进 L1。
- 修复：配置 `redistribute ... level-2 into level-1`，并用 route-policy 只放 locator。

**故障二：跨区能通但绕行，时延偏高。**

- 定位：区内路由器通过最近 ABR 出区，而远端 locator 被所有 ABR 都泄露进来 → 走的是"最近出口"而非全局最优。
- 修复：结合第 4 章的 Flex-Algo，或对特定业务使用 SR Policy 显式路径；同时在 ABR 上正确设置度量，避免泄露路由的度量被人为抬高。

**故障三：某个二级区域整段失联，核心侧看到的是汇总路由仍然存在。**

- 定位：汇总路由器上 `summary-prefix` 仍然生效，Null0 路由吸引流量；实际分量已不可达。
- 修复：启用第 8 章 UPA，让汇总路由器在分量丢失时发 IGP Unreachable Prefix Announcement，触发上游 BGP PIC 切换。

**配置检查清单**：

| 检查项 | 命令/要点 |
|---|---|
| locator 是否被泄露 | `show isis database verbose` 看 TLV 与 metric |
| 是否只泄露 locator | route-policy 匹配 locator 汇总前缀 |
| up/down bit 是否生效 | 防止跨层环路 |
| 汇总是否有 Null0 | `show route <summary>` 应指向 Null0 |
| 汇总后是否还有明细 | 边界路由器需保留明细用于 UPA |

## 本章小结

1. 默认情况下跨区 locator 不可达，必须泄露；泄露必须用策略收窄到 locator。
2. up/down bit 是层级防环的关键。
3. 汇总是 SRv6 相对 MPLS 的结构性优势（256:1），代价是 Null0 黑洞风险。
4. 多实例场景只重分发 locator，不重分发客户路由。
