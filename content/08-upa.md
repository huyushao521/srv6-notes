# 08 · UPA：汇总与 BGP PIC 之间那条黑缝

> **本章定位**：原书第 8 章《Unreachable Prefix Announcement (UPA)》。全书最短、却最"救命"的一章：它解决的是**汇总 + BGP PIC 组合下最隐蔽的静默黑洞**。本章按原书段落逐段对照，Figure 8.1–8.3 重绘，Example 8.1–8.3 保留。

**本章要拿到的东西**：

| 问题 | 对应小节 |
|---|---|
| 为什么"协议全绿、业务中断"能持续几十秒 | 8.1 |
| 汇总、PIC、IGP 三者怎么互相"欺骗" | 8.1.1 |
| UPA 到底发的是什么，一个前缀还是一条路由 | 8.2 |
| UPA 与 Summary-only、Null0、TI-LFA 的分工 | 8.3 |
| UPA 会不会把 IGP 搞炸（规模与作用域） | 8.4 |
| 现网怎么配、怎么验证生效 | 8.5、8.6 |

这一章只有一句话的核心：**汇总把"分量死了"这个信息藏起来了，PIC 需要这个信息才能切备份，UPA 就是把这条信息从数据面（丢包）搬到控制面（IGP 通告）的机制。**

## 8.0 先把三个词摆清楚

| 词 | 是什么 | 本章里的角色 |
|---|---|---|
| **汇总（summarization）** | 把 N 条明细压成 1 条聚合路由通告 | **藏信息的那一方** |
| **BGP PIC edge** | 为每条 BGP 路由预装备份下一跳 | **需要信息的那一方** |
| **UPA** | IGP 里显式声明"某前缀不可达" | **传信息的信使** |

```text
图 8-1：三个角色的位置（原书 Figure 8.1 重绘）

        ┌──────────────── 核心 ────────────────┐
        │  ABR / PE-1（PIC edge，有备份路径）    │
        │    BGP 表：10.1.0.0/16 → PE3（主）     │
        │                          → PE4（备）   │
        └───────────────┬──────────────────────┘
                        │  只收到 10.1.0.0/16（汇总）
                        │
        ┌───────────────┴──────────────────────┐
        │  地市汇聚 PE3（汇总发起者）             │
        │    BGP 表：10.1.0.0/16 → Null0        │
        │    明细：10.1.1.0/24 → 挂了 ✘          │
        └──────────────────────────────────────┘

  问题：PE3 上 10.1.1.0/24 消失，但 10.1.0.0/16 依然在
        → 核心的 BGP 表毫无变化 → PIC 没有理由切备份 → 报文进 Null0
```

## 8.1 故障长什么样

:::en
Consider a PE that advertises a summary route for a large block of prefixes, and an upstream PE that uses BGP PIC edge protection with a backup path. When the downstream PE loses one specific prefix inside the summary, the summary route itself does not change: it is still originated by the summarizing router. The upstream PE therefore keeps sending traffic for the lost prefix toward a router that can no longer deliver it, and the packet is silently dropped.
:::

设想一台 PE 为一大段前缀通告**汇总路由**，上游 PE 使用 **BGP PIC edge** 备份路径。当下游 PE 丢失汇总内的**某一个具体前缀**时，**汇总路由本身没有任何变化**——它仍由汇总路由器产生。于是上游**继续把该前缀的流量发给一台已经无法投递的路由器**，报文被**静默丢弃**。

:::en
The failure is invisible to BGP: the BGP session is up, the next hop is reachable, and the summary route is present. Only the data plane knows, and only by dropping packets. This is one of the most expensive failure modes in a large network, because it can last for minutes with no alarm.
:::

对 BGP 来说这个故障是"**看不见**"的：会话正常、下一跳可达、汇总路由在表中。**只有数据面知道，而它的表达方式就是丢包**。这种故障在大网里代价极高——**可能持续几分钟而没有任何告警**。

### 8.1.1 三方各说各话：为什么能持续几十秒

把三个平面的"认知"并排列出来，黑缝就一目了然：

| 平面 | 它看到的事实 | 它的结论 |
|---|---|---|
| 数据面（PE3 转发） | 明细 `10.1.1.0/24` 的下一跳没了 | 命中汇总的 Null0 → **丢包** |
| BGP（PE3 的 RIB） | 汇总 `10.1.0.0/16` 仍由自己发起 | **没有变化，不发 update** |
| BGP（ABR 的 RIB） | 只有汇总，看不到明细 | **主路径仍有效，不切备份** |
| IGP | 明细前缀的可达性变化**不在 IGP 里**（它是 BGP 前缀） | **完全沉默** |

:::en
The chain is broken at the point where the information should travel: the prefix that failed is a BGP prefix, so its failure is not visible to the IGP, and the summary that hides it is a BGP route, so its presence is not affected. Neither protocol is misconfigured; the combination is.
:::

链条断在"信息本该传递的那一点"：**失效的前缀是 BGP 前缀**，所以它的失效对 **IGP 不可见**；**掩盖它的汇总是 BGP 路由**，所以它的存在**不受影响**。两个协议都没有配错，**是组合错了**。

这也解释了为什么现象总是"**70 秒左右自愈**"：直到 IGP 重收敛后 PE4 的明细路由胜出、或 BGP 会话超时/扫描周期触发，业务才回来。**自愈不是保护机制起作用，是"等到了"**。

## 8.2 UPA 怎么解决

:::en
UPA is an IGP signaling mechanism. When a router loses reachability to a prefix that it had previously advertised, or that is covered by a summary it originates, it sends an explicit IGP announcement stating that the prefix is unreachable. Upstream routers react immediately instead of waiting for a BGP timeout, and PIC can switch to the backup path.
:::

UPA 是一种 **IGP 信令机制**：当路由器丢失到某前缀的可达性（或该前缀被**它自己产生的汇总**覆盖）时，它发一条**显式的 IGP 通告，声明该前缀不可达**。上游路由器**立即反应**，而不必等 BGP 超时，**PIC 也就有机会切到备份路径**。

```text
图 8-2：UPA 的时序（原书 Figure 8.2 重绘）

  t=0     PE3 上 10.1.1.0/24 的下一跳失效
  t=1ms   PE3 检测到（IGP/BFD/接口 down）
  t=5ms   PE3 发出 IGP UPA：10.1.1.0/24 unreachable
  t=20ms  ABR 收到 → 立即把 10.1.1.0/24 从 FIB 移除
          → BGP PIC 触发，切到 PE4 的备份路径
  t<50ms  业务恢复（与 TI-LFA 同量级）

  对照：无 UPA
  t=0     同样失效
  t=70s   IGP 重收敛 + BGP 最优路径重算完成 → 才恢复
```

:::en
The announcement carries the specific prefix, not the summary, so the summarization benefit is preserved: the core still only carries the aggregate, and UPA is only used as a fast negative signal for the affected component.
:::

关键在于：UPA 携带的是**具体前缀**，**不是汇总**。所以**汇总的规模收益完全保留**——核心仍然只装聚合路由，**UPA 只是为受影响的那一个分量提供一个"快速负面信号"**。

### 8.2.1 报文里到底装了什么

UPA 不是新协议，是 **IGP（IS-IS / OSPF）的一个扩展通告**：

| 字段 | 内容 | 作用 |
|---|---|---|
| 前缀 | 失效的**具体前缀**（如 `10.1.1.0/24`） | 精确指出坏的是哪一个 |
| UPA 标志 | 置位（unreachable） | 告诉接收方"这是负向信号" |
| 原因码（可选） | 链路失效 / 分量丢失 / 管理性关闭 | 便于排障归因 |
| 度量 | 通常置最大值 | 确保不被当作可用路径 |
| 作用域 | 通常限定在汇总边界内 | 防止全网泛洪（8.4） |

:::en
UPA is deliberately a negative signal rather than a route withdrawal in the usual sense: the prefix was never in the IGP, so there is nothing to withdraw. The announcement creates a temporary, explicit statement of unreachability that overrides the covering aggregate for forwarding purposes, and it is removed once reachability is restored.
:::

UPA 刻意设计成**负向信号**，而不是常规意义上的"路由撤销"：**这个前缀本来就不在 IGP 里，没有东西可撤销**。这条通告只是**临时、显式地声明不可达**，在转发层面**覆盖掉覆盖它的聚合路由**；一旦可达性恢复，通告就被撤销。

这一点是 UPA 与"明细进 IGP"的根本区别：

| 方案 | 做法 | 代价 |
|---|---|---|
| 明细全进 IGP | 每条 BGP 前缀都进 IGP | **IGP 规模爆炸，不可接受** |
| 不汇总 | 全网跑明细 | 核心表项爆炸 |
| 汇总 + Null0 | 抑制外泄 | **正是本章的黑洞来源** |
| **汇总 + UPA** | 只在失效时发一条负向通告 | 规模收益保留，**只在故障时产生开销** |

## 8.3 与其他机制的分工

:::en
Without UPA, PIC edge and summarization fight each other: summarization hides the failure that PIC needs to see. With UPA, both can coexist, which is why operators who summarize aggressively also deploy UPA as a mandatory companion.
:::

没有 UPA 时，**PIC edge 与汇总互相打架**：**汇总恰好隐藏了 PIC 需要看到的故障**。有了 UPA，两者可以共存——所以**激进做汇总的运营商都把 UPA 当作强制配套**。

| 机制 | 解决什么 | 生效时间 | 覆盖面 |
|---|---|---|---|
| **TI-LFA** | 链路/节点故障的**转发面**保护 | < 50 ms | 单链路/单节点 |
| **BGP PIC core** | 下一跳不可达时的备份路径 | 亚秒 | 核心 IGP 前缀 |
| **BGP PIC edge** | 边缘 PE 故障时的备份 | 亚秒 | PE 级 |
| **汇总 + Null0** | 抑制"汇总内有、实际没有"的流量外泄 | 立即（但**会黑洞**） | 汇总边界 |
| **UPA** | **让 PIC 知道"汇总内某分量没了"** | 立即（< 50 ms） | 汇总边界 |

:::en
It is important to see that UPA does not replace any of these mechanisms; it supplies the one input that PIC edge is missing when summarization is in place. TI-LFA protects the path to the summarizing router, PIC protects against the summarizer's failure, and UPA covers the case where the summarizer is alive but one of its components is not.
:::

关键认识：**UPA 不替代上面任何一个机制，它补的是"汇总存在时 PIC edge 缺的那一个输入"**。TI-LFA 保护"到汇总路由器的路径"，PIC 保护"汇总路由器本身挂了"，**UPA 覆盖的正是第三种情况：汇总路由器活着，但它下面某个分量没了。**

```text
图 8-3：三种故障与对应的保护（原书 Figure 8.3 重绘）

  ① 链路断    ──► TI-LFA（<50ms，本地修复，不影响控制面）
  ② 汇总路由器挂 ──► BGP PIC edge（切到备份 PE，亚秒）
  ③ 汇总路由器活着，但某个分量丢了 ──► 【无机制覆盖】← UPA 补这个洞
```

第 ③ 种是唯一"协议层面无解"的，因为它**在控制面不可见**：路由器没有挂、汇总还在、会话还 up。

## 8.4 规模与作用域：UPA 会不会把 IGP 搞炸

这是部署前必须回答的问题。答案是：**默认不会，前提是限制作用域**。

| 风险 | 机制 | 建议 |
|---|---|---|
| 全网泛洪导致 IGP 抖动 | UPA 通告**限定在汇总边界内**（只在发起者与汇总路由器之间有效） | 只在汇聚层启用，核心层不发起 |
| 大量分量同时失效（如整台 PE 掉电） | 应触发**汇总路由本身撤销**，而不是发 N 条 UPA | 设阈值：分量失效数 > N 时改为撤销汇总 |
| UPA 与 UPA 冲突（多条路径宣称不可达） | 按优先级/度量裁决 | 保持"最近发起者优先" |
| 老旧设备不识别 UPA TLV | 未知 TLV 被忽略 → 行为退化为无 UPA | 逐区域灰度升级 |

:::en
A useful operational rule is that UPA should be scoped to the aggregation layer, where summaries are originated, and should never be generated for a mass failure. If an entire PE is lost, the summary advertisement itself must be withdrawn, because that is the failure the BGP layer is designed to see.
:::

一条实用的运维规则：**UPA 应限定在汇总产生的汇聚层使用，且绝不为"大面积失效"产生**。如果整台 PE 丢失，应当**撤销汇总通告本身**——那正是 BGP 层设计上能看到的故障。

**例 8.1：把"分量失效"与"整机失效"分开处理**

```text
! 汇聚 PE 上：允许为单个分量发 UPA，但设阈值
router isis 1
 address-family ipv6 unicast
  upa
   enable
   max-prefix-per-update 50      ! 单次更新最多携带 50 个分量
   suppress-above 500            ! 超过 500 个分量失效 → 直接撤销汇总
  !
 !
!
```

阈值的设计逻辑：**少量分量失效用 UPA 精准通知；大面积失效用撤销汇总让 BGP 重新算路**。两者混用会导致 IGP 被 UPA 淹没而 BGP 又不知道发生了什么。

## 8.5 配置与验证

**例 8.2：IOS XR 上启用 UPA 与 PIC**

```text
! ① 汇总发起者（地市汇聚 PE3）：允许为被汇总覆盖的分量发 UPA
router isis 1
 net 49.0001.0000.0000.0003.00
 address-family ipv6 unicast
  metric-style wide
  upa                            ! 关键：开启 UPA 能力
  !
 !
!

! ② 汇总路由器（ABR）：接收并利用 UPA
router isis 1
 address-family ipv6 unicast
  upa
  !
 !
!
router bgp 65000
 address-family ipv4 unicast
  additional-paths receive
  bgp additional-paths install
  ! PIC edge 前置条件：必须有可用备份路径
 !
!
```

**例 8.3：验证 UPA 真的在起作用**

```text
! ① 确认能力已协商
RP/0/RP0/CPU0:ABR# show isis database detail | include "UPA|Router Capability"
  Router Capability: UPA supported

! ② 人为制造一次分量失效（关掉某条明细的下一跳），观察 UPA
RP/0/RP0/CPU0:ABR# show isis database detail | include UPA
  Prefix: 10.1.1.0/24  UPA: set  Reason: component-lost

! ③ 确认 FIB 立刻变化（不必等 BGP）
RP/0/RP0/CPU0:ABR# show cef 10.1.1.0/24
  10.1.1.0/24, version 4412
    via 2001:db8::4            ← 已经切到备份 PE4
    recursive via fdbb:bb00:0004::

! ④ 业务侧验证：切换时间
RP/0/RP0/CPU0:ABR# ping 10.1.1.1 count 1000 interval 10 timeout 1
  Success rate 100%, max RTT 6 ms     ← 切到备份后无丢包
```

第 ③ 步是**最直接的证据**：**不用等 BGP 的 70 秒，FIB 已经指向备份**。

## 8.6 排障：UPA 没生效怎么查

```text
业务中断几十秒后自愈，怀疑 UPA 未生效
  │
  ├─ ① IGP 能力协商了吗
  │    show isis database detail | include "Router Capability"
  │    └─ 两台设备都必须支持（否则未知 TLV 被忽略）
  │
  ├─ ② UPA 起了吗（是否只在发起侧配了）
  │    └─ 发起侧与汇总侧都要配，只配一边等于没配
  │
  ├─ ③ 分量失效时真的发了吗
  │    show isis database detail | include UPA
  │    └─ 没有 → 明细前缀未被视为"被汇总覆盖"，检查汇总配置
  │
  ├─ ④ 收到 UPA 后 FIB 变了吗
  │    show cef <prefix>
  │    └─ 没变 → PIC 没有备份路径可切（备份路径本身不存在）
  │
  └─ ⑤ 有备份路径吗
       show bgp <prefix> | include "Backup"
       └─ 无 → PIC 无从切起，问题回到 BGP 拓扑本身
```

| 检查项 | 命令 | 期望 |
|---|---|---|
| UPA 能力 | `show isis database detail` | Router Capability 有 UPA |
| UPA 通告 | `show isis database detail \| include UPA` | 故障时出现，恢复后消失 |
| FIB 切换 | `show cef <prefix>` | 指向备份，不必等 BGP |
| PIC 备份路径 | `show bgp <prefix>` | 有 Backup path |
| 汇总与明细 | `show route <summary>` | 汇总在 Null0，明细来自正确下一跳 |
| 阈值配置 | `show running-config router isis` | 有 max-prefix / suppress-above |

## 8.7 本章小结

:::en
UPA closes a gap that exists only when summarization and BGP PIC edge are combined: the aggregate hides the component failure that PIC needs to observe. By announcing the specific unreachable prefix in the IGP, the summarizing router makes the failure visible in milliseconds, and the traffic is moved to the backup path before the aggregate would have changed.
:::

UPA 补的洞**只在"汇总 + BGP PIC edge"同时存在时才出现**：聚合路由**隐藏了 PIC 需要观察的分量故障**。通过**在 IGP 里通告具体的不可达前缀**，汇总路由器让故障在**毫秒级可见**，流量在聚合路由本来要变化之前就被移到备份路径。

| 维度 | 无 UPA | 有 UPA |
|---|---|---|
| 故障可见性 | 仅数据面丢包 | IGP 显式可见 |
| 恢复时间 | 70 秒级（等 IGP/BGP） | < 50 ms |
| 告警 | 无 | 有（UPA 通告可被监控） |
| 规模收益 | 保留 | **保留**（核心仍只装汇总） |
| 配置复杂度 | 低 | 中（两侧都要配 + 阈值） |
| 适用网络 | 不汇总的小网 | **任何激进汇总的大网** |

一句话收束：**汇总不是错，PIC 也不是错，错在两者之间没有信使**。UPA 就是那个信使，成本极低、收益是"把 70 秒的黑洞变成 50 毫秒的切换"。

## 实战案例

### 案例 A：一分钟的静默丢包（原书案例）

**现象**：核心到某地市的双 PE 冗余，协议全绿、监控无告警，但该地市 `10.1.1.0/24` 业务中断约 **70 秒**后自行恢复，且每隔几个月复现一次。

**复盘**：

```text
① 拓扑：地市 PE3 与 PE4 双归核心，PE3 为主用
        核心对地市汇总为 10.1.0.0/16，明细不进核心
② 故障：PE3 到某台汇聚的链路中断 → 10.1.1.0/24 在 PE3 上不可达
        但 PE3 仍通告 10.1.0.0/16（汇总没有任何变化）
③ 结果：核心 ABR 的 BGP 路由不变，流量继续压向 PE3
        PE3 命中 Null0 静默丢弃，直到 IGP 重收敛后 PE4 明细胜出
④ 修正：PE3/PE4 与 ABR 启用 UPA，并保证"分量丢失即发 UPA"
⑤ 实测：切换时间从 70 秒 → 亚秒级（ping 1000 包 0 丢）
```

**上线检查**：

| 检查项 | 说明 |
|---|---|
| IGP 是否支持 UPA | IOS XR 需在 IS-IS 地址族下开启 |
| 是否只对汇总分量发 | 避免 UPA 泛洪导致 IGP 抖动 |
| 与 BGP PIC 是否联动 | 确认 `bgp additional-paths install` 在 ABR 生效 |
| 汇总边界是否保留明细 | UPA 需要知道分量状态 |

### 案例 B：阈值救了 IGP 一命

**场景**：某运营商全网启用 UPA 后三个月，一台地市汇聚 PE 因电源故障整机重启。若按"每个分量发一条 UPA"的设计，该 PE 下有 **8,000 条明细**会同时产生 UPA。

```text
① 实际观察：重启瞬间 IGP LSP 大小从 1.2 KB 涨到 3.8 MB
② 原因：8,000 条 UPA 被逐个泛洪，LSP 分片激增，SPF 反复计算
③ 后果：核心 CPU 打满 40 秒，比原故障更严重
④ 修正：配置 suppress-above 500
        → 分量失效数 > 500 时，直接撤销汇总通告，不再发 UPA
⑤ 复测：同样的整机重启，IGP 平稳，业务切换 300 ms（BGP 重新收敛）
```

**教训**：**UPA 是"精准通知"机制，不是"批量通知"机制**。整机级故障必须交给 BGP，否则会把一个业务故障放大成一次控制面故障。

### 案例 C：只配了一侧

**现象**：新版本升级后按文档配了 UPA，但故障恢复时间仍是 60 多秒。

```text
① show isis database detail | include UPA  → 故障时确实有通告
② show cef 10.1.1.0/24                     → 仍指向 PE3，没切
③ 差异比对：发起侧配了 upa，汇总侧（ABR）漏配 upa
④ 原因：ABR 不识别 UPA 标志位，把它当作普通前缀忽略
⑤ 修复：ABR 补配 upa，重启 ISIS 进程（或等待能力重新协商）
⑥ 复测：FIB 在 20 ms 内切换
```

**教训**：**UPA 是双向能力协商，不是单向开关**。配置检查清单里必须包含"发起侧 + 汇总侧 + 中间所有 ABR"。

## 延伸阅读

- **draft-ietf-rtgwg-upa**：Unreachable Prefix Announcement，UPA 的原始草案（IGP 扩展、标志位、作用域）。
- **RFC 8277 / RFC 3107**：BGP 携带标签与前缀，理解"汇总在 BGP 侧如何表达"。
- **RFC 7911**：Add-Paths，PIC 需要的多路径能力基础。
- **RFC 9494 / draft-ietf-rtgwg-segment-routing-ti-lfa**：TI-LFA，8.3 中"第一种故障"的保护机制。
- 交叉参考：第 5 章（汇总与泄露，locator 侧的同类问题）、第 6 章（L3VPN 中的 PIC 与多路径）、第 14 章（Bell 大网里的汇总边界设计）。
