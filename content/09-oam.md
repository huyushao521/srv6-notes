# 09 · SRv6 Ping 与 Traceroute（RFC 9259）

> **本章定位**：原书第 9 章《SRv6 Ping and Traceroute》。这一章解决一个很实际的问题：**MPLS 时代的 `ping mpls` / `trace mpls` 没了，怎么验证一条段列表真的按你设计的方式转发？** 英文块为原文摘录，中文为完整翻译，Figure 9.1–9.4 重绘，Example 9.1–9.4 保留。

**本章要拿到的东西**：

| 问题 | 对应小节 |
|---|---|
| 为什么 LSP ping 那套不能直接搬过来 | 9.0 |
| O-flag 到底做什么，端点凭什么"改为回应" | 9.1 |
| ping 一个 locator / 一个 End.X / 一个业务 SID 分别证明了什么 | 9.2 |
| traceroute 带 SRH 与不带 SRH 结果不同，该信哪个 | 9.3 |
| uSID 压缩后 trace 输出为什么看不懂 | 9.4 |
| 怎么在故障发生**之前**验证 TI-LFA 备份路径真的能转发 | 9.5 |

一句话概括：**SRv6 的 OAM 不建在"路径"这个对象上，而是建在"报文自己携带的段列表"上**——探测包走的就是用户包走的那条路，所以它验证的是数据面本身。

## 9.0 为什么 MPLS 那套搬不过来

:::en
In an MPLS network, a label switched path can be tested with LSP ping: the probe carries the label stack, and each router along the path answers because the label identifies the path. In SRv6 there is no label stack and no per-path state, so the probe must carry the segment list itself, and the responder must be identified by a SID rather than by a label.
:::

MPLS 网络里一条 LSP 可以用 **LSP ping** 测：探测报文**带着标签栈**，沿途路由器**因为标签能标识路径**而回应。SRv6 里**没有标签栈、也没有"路径"这个被维护的对象**（无状态），于是：

1. **探测报文必须自己携带段列表**——路径信息在包里，不在设备上；
2. **回应方由 SID 标识**，而不是由标签标识。

| 维度 | MPLS LSP ping | SRv6 OAM（RFC 9259） |
|---|---|---|
| 路径信息在哪 | 设备上的标签转发表 | **报文里的 SRH 段列表** |
| 谁回应 | 每跳（按标签） | **端点（按 SID + O-flag）** |
| 是否需要逐跳状态 | 是（标签） | **否** |
| 探测与用户流量是否同路径 | 是 | **是（同一段列表）** |
| 无 SRH 的 uSID 场景 | — | **退化：只能逐 SID 探测** |

最后一行是关键限制，先说清楚：**uSID 业务转发不带 SRH**（第 6 章），所以**没有地方放 O-flag**。因此 uSID 场景下：

- **ping/traceroute 单个 SID** 照常可用（DA 就是那个 SID，用别的方式标记 OAM）；
- **验证"整条显式路径"** 需要人为构造带 SRH 的探测（诊断用，不是业务转发路径）。

## 9.1 O-flag：让端点从"转发"切换到"回应"

:::en
RFC 9259 defines the mechanisms. A probe is an IPv6 packet with an SRH whose segment list contains the path under test; the O-flag in the SRH flags indicates that this packet is an OAM packet, so that a segment endpoint that would normally forward it can instead respond with an ICMPv6 message.
:::

RFC 9259 定义了机制：**探测报文是一个带 SRH 的 IPv6 包，SRH 的段列表就是被测路径**；**SRH flags 里的 O-flag 标记"这是 OAM 报文"**，于是**本应继续转发的端点可以改为回一个 ICMPv6 消息**。

```text
图 9-1：O-flag 的处理（原书 Figure 9.1 重绘）

  探测报文（普通数据面路径，完全一样的封装）:
  ┌────────────┬─────────┬────────────────────────────┐
  │ IPv6 头    │ SRH     │ 内层报文 / 可选 TLV        │
  │ DA = S[n]  │ Flags:  │                            │
  │            │  O=1 ←──┼── 标记：这是 OAM 报文      │
  └────────────┴─────────┴────────────────────────────┘
                    │
     到达 SID 端点，查本地 SID 表
                    │
     ├─ O=0 ──► 正常执行行为（End / End.X / End.DT…）
     │
     └─ O=1 ──► OAM 处理：
                 ├─ ping：回 ICMPv6 Echo Reply
                 └─ traceroute：回 ICMPv6 Time Exceeded
                      （载荷里带 SRv6 TLV：剩余段列表、当前 SID、状态）
```

:::en
The O-flag is set only for packets that are meant to be answered, and the SRv6 TLV carried in the ICMPv6 payload reports the segment list state back to the sender. This is what allows a traceroute to attribute each hop to a specific SID in the list rather than to an IP address along the path.
:::

O-flag **只对"希望被回应"的报文置位**，而 **ICMPv6 载荷里的 SRv6 TLV 把段列表状态带回给发送方**。这正是 traceroute 能把每一跳**归因到段列表中的某个 SID**、而不是归因到"路径上的某个 IP"的原因。

安全提醒（现网必须处理）：

| 风险 | 说明 | 建议 |
|---|---|---|
| O-flag 探测被滥用做拓扑探测 | 任何人可构造 O=1 报文让端点回应 | 边缘过滤带 SRH+O 的外部报文 |
| ICMPv6 速率限制过严 | 探测无回应，误判为不通 | 对 SRv6 OAM 单独放行/限速 |
| OAM 报文走治理面优先级 | 拥塞时探测全丢 | 给 OAM 流量独立队列 |

## 9.2 Ping：三种粒度，三种结论

```text
例 9.1：三种典型 ping
! ① 打到 locator 的 uN：只验证 locator 可达 + End 行为
ping srv6 fdbb:bb00:0005:e000::

! ② 打到某个 End.X（uA）：验证"这条指定链路"能转发
ping srv6 fdbb:bb00:0005:e001:: sid-list fdbb:bb00:0005:e001::

! ③ 打到业务 SID：验证 SID 已实例化
ping srv6 fdbb:bb00:0005:e101:: sid-list fdbb:bb00:0002::,fdbb:bb00:0005:e101::
```

:::en
The ping probe is forwarded along the segment list exactly like user traffic, so it validates the data plane, not just the control plane. If the last SID is a service SID such as End.DT46, the responder validates that the SID is instantiated and reachable, but does not perform the VPN lookup — which is why a successful ping to a VPN SID does not prove the VPN itself is healthy.
:::

ping 探测**沿段列表转发，和用户流量完全一样**，因此它验证的是**数据面**而非仅仅控制面。但注意：若最后一段是 `End.DT46` 这类业务 SID，回应方**只验证"SID 已实例化且可达"，不做 VPN 查表**——所以**"ping 通 VPN SID"并不等于 VPN 业务健康**。

| 探测目标 | 验证了什么 | **不能证明** |
|---|---|---|
| Locator / uN | locator 可达、End 行为正常 | 任何业务是否通 |
| uA（End.X） | **指定链路**可转发 | 对端是否继续正确转发 |
| 业务 SID（uDT/uDX） | SID 实例化、行为已注册 | VRF 内有无路由、CE 侧是否可达 |
| 完整 SID list | 整条显式路径可走 | 备份路径是否可用 |
| 带内层报文的 end-to-end ping | 封装 + 解封装 + 查表全链路 | 大包（MTU）是否通过 |

最后一行很重要：**"ping 通 SID" 和 "ping 通客户地址" 是两件事**。前者证明 SID 存在，后者才证明业务通：

```text
! 真正证明业务通的探测：目标地址是客户地址，SID list 是业务 SID
ping vrf CUSTOMER-100 10.1.2.1 source 10.1.1.1
! 这条走的是完整封装 + 出口 VRF 查表，才等价于用户流量
```

## 9.3 Traceroute：两种模式，两个问题

:::en
Traceroute can be run in two modes. In the "with SRH" mode the probe carries the full segment list and each segment endpoint reports itself, which reveals how the list is executed. In the "without SRH" mode, the tool sends individual probes to each SID in turn, which reveals the path the network would take to reach that SID. The two answers differ whenever the underlay ECMP splits traffic.
:::

traceroute 有两种模式：

- **带 SRH（with SRH）**：探测报文携带**完整段列表**，**每个端点各自上报**，反映"**段列表是怎么被执行的**"；
- **不带 SRH（without SRH）**：**逐个 SID 单独探测**，反映"**网络去往该 SID 走的是哪条路**"。

当 Underlay 的 ECMP 把流量分散到不同路径时，**两种结果会不一致**——这不是故障，而是 ECMP 的正常表现。

```text
图 9-2：两种模式问的是不同问题（原书 Figure 9.2 重绘）

  带 SRH：问"这段程序按顺序执行了吗"
    PE-1 ──[S1]──► P-1 ──[S2]──► P-2 ──[S3]──► PE-2
         每跳上报的是"SID Sx 已执行"，不是"某 IP 收到包"

  不带 SRH：问"去每个 SID 各自的路径是什么"
    PE-1 ──► S1 的路径（可能 ECMP 走 A 平面）
    PE-1 ──► S2 的路径（可能 ECMP 走 B 平面）
    PE-1 ──► S3 的路径（可能又走 A 平面）
         → 三段路径拼起来 ≠ 一条连续路径，不代表业务实际走法
```

**结论**：判断"**是否真的按设计路径转发**"，**必须用带 SRH 的模式**；不带 SRH 只适合"定位某个 SID 到不到得了"。

```text
例 9.2：带 SRH 的 trace（uSID 段列表）
traceroute srv6 fdbb:bb00:0002:e101:: sid-list fdbb:bb00:0009::,fdbb:bb00:000a::,fdbb:bb00:0002:e101::
 1  fdbb:bb00:0009::   0.4 ms    ← uN 执行（P-1）
 2  fdbb:bb00:000a::   0.7 ms    ← uN 执行（P-2）
 3  fdbb:bb00:0002:e101:: 1.1 ms ← 业务 SID 到达（PE-2）
```

| 输出特征 | 说明 |
|---|---|
| 每跳显示的是**SID**，不是 IP | 正常：RFC 9259 归因到段 |
| 中间某跳显示 `*` | 该 SID 未回应（O 未处理 / 被过滤 / SID 未实例化） |
| 跳数与段列表长度不一致 | 段列表被压缩/合并（uSID 常见，见 9.4） |
| 某跳时延突然 +15 ms | 该跳走了跨区/绕行，对照 Flex-Algo 设计 |

## 9.4 uSID 下的三个特殊现象

uSID 把多个微指令压进一个 128 bit 地址，这会让 trace 的输出"看起来不对"，其实是正常的：

| 现象 | 原因 | 是否故障 |
|---|---|---|
| trace 只显示 1–2 跳，但路径上有 4 个节点 | uSID 在 DA 里**边转发边移位**，不产生新的"段跳" | **正常** |
| 输出里的 SID 短于 128 bit（只剩 uSID 串） | 打印的是**压缩后的微指令串**，不是完整地址 | 正常 |
| 段列表长度与实际跳数不匹配 | 一个 128 bit 地址可装多个 uSID | 正常 |
| 某跳显示的是 `::` 或 `:0:0` | 该 uSID 位置的移位结果 | 正常 |

:::en
With micro-segments, the segment list is encoded inside a single address, and each node shifts the destination address as it forwards. The number of "hops" reported by a traceroute therefore does not equal the number of micro-segments, because a single packet can consume several micro-segments without a new SRH being examined. Reading a uSID trace requires mapping the printed value back to the micro-segment layout.
:::

用微段时，**段列表被编码进一个地址**，每个节点转发时**对目的地址做移位**。因此 **trace 报告的"跳数"不等于微指令个数**——**一个报文可以消耗多个微指令而不重新检查 SRH**。读 uSID 的 trace，**必须把打印出来的值映射回微指令布局**（`Block` + `uN` + 各 `uF`）。

**例 9.3：把 trace 输出翻译回微指令**

```text
traceroute 输出:
 1  fdbb:bb00:0009::        0.4 ms
 2  fdbb:bb00:000a::        0.7 ms
 3  fdbb:bb00:0002:e101::   1.1 ms

翻译（/48 locator + 16 bit uN）:
  fdbb:bb00:0009::        → block=fdbb:bb00, node=0009(P-1), 无 function
  fdbb:bb00:000a::        → block=fdbb:bb00, node=000a(P-2)
  fdbb:bb00:0002:e101::   → block=fdbb:bb00, node=0002(PE-2), func=e101(uDT46)

结论：路径 PE-1 → P-1 → P-2 → PE-2，业务 SID 在 PE-2 上命中
```

## 9.5 最有价值的用法：故障前验证 TI-LFA 修复路径

:::en
The most valuable use of SRv6 traceroute is verifying repair paths. You can inject the repair segment list that TI-LFA computed and trace it, which proves that the backup path is not only installed but actually forwarding. Without this, TI-LFA failures are only discovered during a real outage.
:::

SRv6 traceroute **最有价值的用法是验证修复路径**：把 TI-LFA 算出来的**修复段列表手工注入并 trace**，证明备份路径**不仅装了表、而且真的能转发**。没有这一步，**TI-LFA 的问题只能在真实故障时才暴露**——那时已经晚了。

```text
图 9-3：TI-LFA 修复路径的验证（原书 Figure 9.3 重绘）

  正常路径:   PE-1 ──► P-1 ──► P-2 ──► PE-2
  故障(预期): P-1 ✘

  TI-LFA 计算出的修复列表（PQ 节点 P-2 转发）:
    [ fdbb:bb00:0009:e001:: (P-1 的 End.X 指向备份链路),
      fdbb:bb00:000a::     (P-2 的 uN),
      fdbb:bb00:0002::     (PE-2 的 uN) ]

  验证（不制造故障！）:
    traceroute srv6 <PE-2> sid-list <修复列表>
    ├─ 全部回应 ──► 备份路径可用 ✔
    └─ 中间断 ────► TI-LFA 修复列表是"死"的，故障时会断 ✘
```

:::en
This is a preventive test: it exercises the exact forwarding entries that will be used after a failure, without causing the failure. Operators who run it periodically discover broken repair paths long before an outage, which is the difference between a 50-millisecond protection and a multi-minute outage.
:::

这是一种**预防性测试**：它**验的正是故障后要用的那些转发表项**，却**不需要制造故障**。定期执行这个测试的运营商，会在故障发生很久之前就发现"修复路径是坏的"——这就是**"50 毫秒保护" 与 "几分钟中断" 的差别**。

**例 9.4：把修复列表验证做成周期任务**

```text
! 手工验证一条修复路径（PQ 节点 = P-2）
RP/0/RP0/CPU0:PE-1# traceroute srv6 fdbb:bb00:0002:: sid-list fdbb:bb00:0009:e001::,fdbb:bb00:000a::,fdbb:bb00:0002::
 1  fdbb:bb00:0009:e001::   0.5 ms
 2  fdbb:bb00:000a::        0.8 ms
 3  fdbb:bb00:0002::        1.2 ms
! 全回应 → 修复路径健康

! 建议做成定时任务（每 15 分钟），结果入监控
! 告警条件：任一修复路径连续 3 次无回应
```

| 验证对象 | 频率 | 告警条件 |
|---|---|---|
| 每条链路的 TI-LFA 修复列表 | 15 分钟 | 连续 3 次失败 |
| 每个 locator 的 uN ping | 1 分钟 | 连续 3 次失败 |
| 每个业务 SID 的 ping | 5 分钟 | 连续 2 次失败 |
| 端到端客户地址 ping（大包） | 5 分钟 | 任一失败（含 MTU） |

## 9.6 排障清单

| 症状 | 先看什么 | 命令 |
|---|---|---|
| 完全不通 | 先 ping locator → 再 ping 业务 SID，逐段收窄 | `ping srv6 <SID>` |
| ping 通 SID 但业务不通 | 是不是只验证了 SID 存在（9.2） | `ping vrf X <CE 地址>` |
| 通但绕远 | 对比 SID 前缀属于哪个 algo 的 Block | `traceroute srv6 ... sid-list ...` |
| 间歇不通 | 带 SRH trace 多次执行，看是否某条 ECMP 成员坏 | 重复 10 次 trace 比对 |
| 故障后不恢复 | 手工注入 TI-LFA 修复列表 trace | 9.5 的方法 |
| trace 输出看不懂 | 按 uSID 布局翻译（9.4） | 手算 Block/Node/Func |
| 中间跳全 `*` | ICMPv6 被过滤 / O-flag 未处理 | 查 ACL 与 ICMPv6 放行 |

## 9.7 本章小结

:::en
SRv6 OAM reuses the data plane itself as the probe path: an SRH with the O-flag set tells a segment endpoint to answer instead of forward, and the ICMPv6 payload carries the segment list state back to the sender. This makes the probe validate exactly the entries that user traffic will use.
:::

SRv6 OAM **把数据面本身当作探测路径**：**置了 O-flag 的 SRH** 告诉端点"**别转发、请回应**"，而 **ICMPv6 载荷把段列表状态带回发送方**。这让探测**验证的正是用户流量会用的那些表项**。

| 维度 | MPLS OAM | SRv6 OAM |
|---|---|---|
| 探测携带什么 | 标签栈 | **SRH 段列表 + O-flag** |
| 谁回应 | 沿途每跳 | **段端点** |
| 归因粒度 | 标签跳 | **SID（微指令）** |
| 能否验证备份路径 | 需构造备份 LSP | **可注入修复段列表** |
| 业务 SID 能证明什么 | — | **只证明 SID 存在，不证明业务通** |
| uSID 特殊性 | — | **跳数 ≠ 微指令数** |

一句话收束：**SRv6 的 OAM 比 MPLS 更强的地方是"可以注入任意段列表"**——这让"故障前验证备份路径"从不可能变成日常操作；**更弱的地方是"没有路径对象"**——你得自己知道想验什么。

## 实战案例

### 案例 A：一次"业务通但绕远"的定位

**现象**：A 市到 B 市业务时延从 8 ms 涨到 21 ms，业务可用，客户投诉。

```text
① traceroute srv6 <B市PE的uN>（不带 SRH）
   → 路径在核心绕了一个平面
② 对照设计：该业务本应走 algo 128 的 locator，实际走 algo 0
③ show bgp vpnv4 unicast <prefix>
   → 收到的 SID 是 fdbb:bb00:...（algo 0 块），
     而不是 fdbb:bb01:...（algo 128 块）
④ 根因：出口 PE 上该 VRF 的 locator 绑定错了
   配置里 locator LOWLAT 没在 BGP 侧生效，实际用了 MAIN
⑤ 修正 locator 绑定 → trace 显示回到低时延平面 → 时延恢复 8 ms
```

**教训**：**"业务通" 从来不是 SLA 达标的证据**。Flex-Algo 类设计必须配"时延基线巡检"，否则劣化会长期潜伏（第 4 章）。

### 案例 B：TI-LFA 修复列表是"死"的

**现象**：某条链路真断时，TI-LFA 没生效，业务断了 40 秒——但每次演练"拔纤"都正常。

```text
① 常规演练：拔纤 → TI-LFA 生效（因为拔纤触发了 IGP 重收敛，
   期间靠的是另一套机制，掩盖了修复列表本身的问题）
② 用 9.5 的方法注入修复列表 trace：
   traceroute srv6 <PE-2> sid-list <修复列表>
   → 第 1 跳就 * * *（P-1 的 End.X SID 没回应）
③ 查 P-1：show segment-routing srv6 sid | include e001
   → 该 End.X SID 不存在（备份链路的 adjacency SID 没生成）
④ 根因：备份链路开了 ISIS 但没开 SRv6，adjacency SID 未分配
⑤ 修复后：修复列表 trace 全回应；再拔纤实测保护 32 ms
```

**教训**：**"演练通过"不等于"保护可用"**。演练时要**看切换后的路径是不是设计的修复路径**，而不是只看"业务没断"。

### 案例 C：uSID trace 只显示 1 跳，被误判为"路径没生效"

**现象**：割接到 uSID 后，trace 一条 5 节点的路径只显示 2 跳，运维判断"段列表没生效"，回退。

```text
① trace 输出：
   1  fdbb:bb00:0001::   0.4 ms
   2  fdbb:bb00:0005::   1.2 ms
② 实际路径：PE-1 → P-1 → P-2 → P-3 → PE-5（5 个节点）
③ 原因：uSID 压缩后，中间节点的 uN 在 DA 内被"移位消耗"，
   不产生独立的 SRH 处理，因此不各自回应
④ 正确验证方式：查每个中间节点的 SID 计数
   show segment-routing srv6 sid detail  → Packets 递增
⑤ 结论：路径是对的，是"读法"错了
```

**教训**：**uSID 场景不能用"跳数"判断路径**，要用 **SID 计数 + CEF 下一跳**交叉验证。这一条应写进割接检查单。

## 延伸阅读

- **RFC 9259**：Operations, Administration, and Maintenance for SRv6，O-flag、ICMPv6 扩展、SRv6 TLV 的规范依据。
- **RFC 8986**：端点行为定义（含 OAM 处理与 `End` 的 O-bit 语义）。
- **RFC 8754**：SRH，Flags 字段与 O-bit 的位置。
- **RFC 8200 / RFC 4443**：IPv6 与 ICMPv6 基础，理解 Time Exceeded / Echo Reply 的承载。
- **draft-ietf-6man-srv6-oam**（如已更新）：uSID 场景下的 OAM 补充。
- 交叉参考：第 3 章（End/End.X 行为）、第 6 章（业务 SID 的语义）、第 10 章（运维巡检项设计）。
