# 03 · Underlay 指令：Locator、End/End.X 与 TI-LFA

> 对应原书第 3 章 *Underlay Instructions*。前一章讲"指令长什么样"，这一章讲**域内到底有哪几条指令、怎么配、怎么通告、怎么被保护**。

## 3.1 Locator：一切的根

:::en
The locator is an IPv6 prefix, typically a /48, from which all SIDs of a node are derived. It must be routable within the SR domain, and it is advertised in the IGP just like any other IPv6 prefix. A node may have several locators — for different algorithms, different slices, or different service families.
:::

Locator 是一段 IPv6 前缀（通常 /48），节点所有 SID 都从它派生。它在 SR 域内必须可路由，并且像普通 IPv6 前缀一样由 IGP 通告。一个节点可以有**多个 Locator**——分别对应不同算法、不同切片、不同业务族，这是 Flex-Algo 与网络切片的地址基础。

```text
segment-routing
 srv6
  locator MAIN
   micro-segment behavior unode psp-usd
   prefix fc00:0:7::/48
  !
 !
!
router isis 1
 address-family ipv6 unicast
  segment-routing srv6
   locator MAIN
```

:::en
The locator is advertised as part of the SRv6 Locator TLV in IS-IS (RFC 9352) or OSPF (RFC 9513). Receiving routers process it like IPv6 prefix reachability: they compute the shortest path to it and install it in the FIB. The locator advertisement provides reachability; the individual SIDs instantiated on that locator are carried in sub-TLVs and are used by remote nodes for repair path computation and for building SR policies.
:::

Locator 通过 IS-IS 的 **SRv6 Locator TLV**（RFC 9352）或 OSPF 的对应 TLV（RFC 9513）通告；接收方按 IPv6 前缀可达性处理：算最短路径、装 FIB。**通告 Locator 只解决"可达"，"这个 Locator 上有哪些 SID"则由子 TLV 携带**，远端节点用它做 TI-LFA 修复路径计算和策略构造。

:::en
Some SIDs are intentionally not advertised with a routable locator, for security or scale reasons. Such a local SID only works if a preceding instruction brings the packet to that node first, which is why non-routable locators always appear at the end of a program.
:::

出于安全或规模考虑，有些 SID **故意不**配可路由 Locator。这类本地 SID 只有在前面有指令把包先送到该节点时才有效——所以不可路由 locator 永远出现在程序末尾。

## 3.2 End / uN：前缀段行为

:::en
The End behavior, called uN in the micro-segment variant, is the fundamental prefix segment instruction: the packet has reached the node identified by the locator, and the active segment pointer must move forward. With uSID, this is implemented as a 16-bit left shift of the container.
:::

End（uSID 变体叫 **uN**）是最基础的前缀段指令：报文已经到达 locator 所指节点，活动段指针需要前移。uSID 下它就是容器左移 16 bit。

:::en
Two optional flavors exist. Penultimate Segment Popping (PSP) triggers when an endpoint decrements Segments Left from one to zero: it deletes the SRH from the packet, which simplifies processing at the final destination and hides the SID list from an untrusted node. Ultimate Segment Decapsulation (USD) removes the whole SRv6 encapsulation at the last segment, so that the final node receives a plain payload.
:::

两个可选 flavor：

- **PSP**（倒数第二段弹出）：当端点把 `Segments Left` 由 1 减到 0 时，顺手删掉整条 SRH。好处是让末端少解析头部，并且**对不可信的末端隐藏 SID list**。
- **USD**（最后一段解封装）：最后一段执行完，把整个 SRv6 封装都剥掉，末端只收到裸净荷。

生产环境基本都开 `psp-usd`：既省带宽，又避免把路径暴露给末端。

## 3.3 End.X / uA：邻接段行为

:::en
The End.X behavior, or uA, forwards the packet out of a specific interface, or a specific set of interfaces, regardless of the shortest path. It is the building block for explicit traffic engineering paths, for TI-LFA repair paths, and for steering traffic into a particular plane or slice.
:::

End.X（**uA**）把报文从**指定的一条或一组链路**发出去，无视最短路径。它是显式 TE 路径、TI-LFA 修复路径、以及"把流量压进某个平面/切片"的基础积木。

```text
interface HundredGigE0/0/0/1
 description to-PE2
router isis 1
 interface HundredGigE0/0/0/1
  address-family ipv6 unicast
   segment-routing srv6
    adjacency-segment
```

:::en
For point-to-point adjacencies, the End.X SID is advertised in a sub-TLV under the adjacency TLV. On broadcast networks, a LAN End.X TLV is required instead, because several neighbors share the same link and the advertisement must identify which neighbor the SID points to.
:::

点对点邻接的 End.X 挂在邻接 TLV 下的 **SRv6 End.X SID 子 TLV**（IS-IS 的 22/23/222/223/141）。广播网必须用 **SRv6 LAN End.X TLV**，因为同一网段上有多台邻居，通告里要带邻居 System-ID 才能指明这个 SID 指向谁。两者都带 128 bit SID + 16 bit 行为码点（含 flavor 位）。

## 3.4 TI-LFA：把故障恢复压进 SID list

:::en
TI-LFA computes, at the point of local repair, a backup path that does not depend on the topology after the failure, and encodes it as a segment list pushed onto the packet. For prefix protection the repair list is typically the uN of a PQ node followed by the uN of the destination; for adjacency protection it is the uA of the protected neighbor followed by the destination, which implements directed forwarding.
:::

TI-LFA 在**本地修复点（PLR）**计算一条**不依赖故障后拓扑**的备份路径，并把它编码成压入报文的段列表。

- **保护前缀**：修复列表通常是 `<PQ 节点的 uN, 目的 uN>`。
- **保护邻接**：修复列表是 `<被保护邻居的 uA, 目的 uN>`，即"定向转发"。

:::en
The P-space contains the nodes reachable from the PLR without crossing the failure; the Q-space contains the nodes from which the destination is reachable without crossing the failure, and whose path back to the source avoids the failure. A node in both spaces is a PQ node. If no PQ node exists, the repair path is expressed as a P node followed by a few uA instructions that steer the packet around the failure.
:::

- **P 空间**：从 PLR 出发、不经过故障即可到达的节点集合。
- **Q 空间**：从该节点到目的不经过故障，且**回程到源也不经过故障**的节点集合。
- 交集即 **PQ 节点**。若不存在 PQ，就把修复路径写成"<某 P 节点> + 若干 uA 绕行指令"。

```text
保护前缀（有 PQ）:   <PQ-uN>        , <目的-uN>      → 2 条，无 SRH
保护前缀（无 PQ）:   <P-uN> , <uA> , <uA> , <目的-uN> → 仍常在 6 条以内
保护邻接（定向转发）: <邻居-uA>      , <目的-uN>
```

**为什么运营商先上 TI-LFA**：它是 SR 里收益最直接的功能——**亚 50 ms** 恢复，不需要 RSVP-TE，不需要每流状态，且 uSID 场景下修复列表通常只有 2~3 条，连 SRH 都不用压。

## 3.5 报文示例：单链路故障下的修复

拓扑：`PE1 — P1 — P2 — PE3`，另有 `P1 — P3 — P2` 作为旁路。P1 到 P2 的直连链路故障。

```text
正常工作：DA = fc00:0:3::            （PE3 的 uN）
故障瞬间（P1 为 PLR）：DA = fc00:0:9:0003::
                          └ P3 的 uN ┘└ PE3 的 uN ┘
```

P1 命中自己的 /48 表项（`fc00:0:9::/48` 是邻居 P3 的 locator 时，只需普通转发；若修复路径要求"从某条特定链路出"，则前面的段换成 P3 的 uN、后面跟一个 uA）。P3 执行 uN 位移，DA 变成 `fc00:0:3::`，沿最短路径送到 PE3。整个过程**报文没有被丢弃，也没有等待 IGP 收敛**。

## 实战案例：环形城域网的 50 ms 保护与微环

**场景**：城域环形网 8 个节点，跑 SRv6 uSID + TI-LFA，要求链路故障业务中断 < 50 ms。

**落地配置要点**：

```text
router isis 1
 interface HundredGigE0/0/0/1
  address-family ipv6 unicast
   fast-reroute per-prefix
   fast-reroute per-prefix ti-lfa
```

**验证步骤**：

1. `show isis fast-reroute ti-lfa` 确认每个前缀都有 backup 路径与修复列表。
2. 抓包看故障瞬间的修复列表是否与预期一致（通常 `<PQ-uN, 目的-uN>`）。
3. 拔纤测试：业务丢包应 < 50 ms；若达到数百毫秒，说明 TI-LFA 没生效，退回了普通 SPF 收敛。
4. 检查是否出现微环（microloop）：收敛期间两台相邻节点互相认为对方是"更优下一跳"。SR 场景可用 UPA（第 8 章）或分段收敛手段抑制。

**常见坑**：

| 现象 | 根因 |
|---|---|
| 部分前缀没有 backup | Locator 未参与 TI-LFA 计算，或缺 SID Structure 子 TLV |
| 修复路径绕远但通 | PQ 不存在，退化为 P + uA 列表，属正常 |
| 故障后短暂黑洞 | 修复列表指向的 uA 所在链路也被同一故障影响 |
| 双向都断 | 保护只做了单向（TI-LFA 是本地行为，需两端都开） |

## 本章小结

1. Locator 是 SID 之根，/48 起步，可多实例；通告的是可达性，子 TLV 通告的是 SID 本身。
2. End/uN 只做一件事：位移；PSP/USD 是省带宽与隐藏路径的优化。
3. End.X/uA 是显式路径与修复路径的积木；广播网要用 LAN End.X。
4. TI-LFA = P/Q/PQ 空间 + 修复列表，uSID 下通常 2~3 条指令、无需 SRH。
