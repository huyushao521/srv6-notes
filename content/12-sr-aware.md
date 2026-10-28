# 12 · SR-aware 服务与内层报文暴露

> **本章定位**：原书第 12 章《SR-aware Services》。问题很直接：**防火墙只看到外层 IPv6 头，看不到内层五元组，策略就失效了。** 这一章讲三类做法。英文块为原文摘录，中文为完整翻译，Figure 12.1–12.4 重绘，Example 12.1–12.2 保留。

**本章要拿到的东西**：

| 问题 | 对应小节 |
|---|---|
| 为什么封装会让服务设备"失明" | 12.1 |
| 三条路线（原生 / 固定偏移 / 代理）怎么选 | 12.2 |
| SR-aware 服务具体要做哪五件事 | 12.3 |
| 老设备不换代的"固定偏移"法为什么可行 | 12.4 |
| SERA 架构解决了什么问题 | 12.5 |
| 元数据（Arg）怎么在服务之间传递结论 | 12.6 |
| "服务设备没告警"怎么排 | 12.7 |

一句话概括：**服务编排的前提是"服务能看见流量"**。SRv6 把真实报文藏进外层封装里，于是必须先解决"看得见"的问题，才谈得上"串起来"。

## 12.1 问题：服务设备"看不见"真实流量

:::en
When a packet is encapsulated in SRv6, the appliance in the middle sees only the outer IPv6 header. A firewall that must match on the customer's five-tuple, or a DPI engine that must inspect the payload, cannot do its job on the outer header alone. The service is blind unless something exposes the inner packet to it.
:::

报文一旦被 SRv6 封装，**中间设备只能看到外层 IPv6 头**。防火墙要按**客户五元组**匹配、DPI 要**检查净荷**，光看外层头根本做不了。**除非有机制把内层报文"暴露"给服务设备，否则服务就是瞎的。**

```text
图 12-1：失明的三个层次（原书 Figure 12.1 重绘）

  封装后的报文:
  ┌──────────────┬─────────┬─────────────────┬──────────┐
  │ 外层 IPv6 头 │ SRH     │ 内层 IPv4/IPv6  │ 净荷     │
  │ src/dst=SID  │ 段列表  │ 真实五元组 ★    │ 应用数据 │
  └──────────────┴─────────┴─────────────────┴──────────┘
        ▲            ▲              ▲              ▲
        │            │              │              │
     设备能看     设备能看       ★ 设备看不到    看不到
     （但没意义）  （拓扑信息）    策略无法匹配    无法检测
```

| 服务类型 | 需要什么 | 只看外层会怎样 |
|---|---|---|
| 防火墙 | 内层五元组 | **策略全部失效**（或退化为"全通/全禁"） |
| DPI / IDS | 净荷 | **零告警**（规则按内层协议写） |
| NAT | 内层地址 | 无法转换 |
| LB | 内层 L4 端口 | 无法分发 |
| QoS 整形 | 内层 DSCP | 分类失效 |
| 计费 | 内层流标识 | 计费错误 |

:::en
There is a subtlety worth stating: an appliance that is SR-aware sees more than the inner packet, it also sees the segment list. This can be an advantage (the service can make decisions based on the intended path) or a risk (the service can break the path by mishandling the SRH).
:::

一个值得点明的细节：**SR-aware 设备看到的不只是内层报文，还能看到段列表**。这既是优势（**服务可以按"预期路径"做决策**），也是风险（**服务处理不当就会把路径弄坏**）。

## 12.2 三条路线怎么选

| 方式 | 设备需要改造 | 能否看内层 | 能否读写元数据 | 典型场景 |
|---|---|---|---|---|
| **SR-aware**（原生解析） | 是（支持 SRv6/SRH） | 能 | **能** | 新一代 vFW / vDPI / MEC |
| **内层暴露**（SERA 类） | 少量（解析固定偏移） | 能 | 部分（可读固定字段） | 改造困难的老设备 |
| **SR Proxy**（第 13 章） | **否** | 不能（只看裸报文） | **不能** | 完全不支持 IPv6 的老设备 |

```text
图 12-2：三条路线的选择树（原书 Figure 12.2 重绘）

  服务设备支持 SRv6？
   ├─ 是 ──► ① SR-aware：直接分配 Service SID（最佳）
   └─ 否
       ├─ 能改代码/能配"偏移解析"？
       │   ├─ 是 ──► ② 内层暴露 / SERA：旁挂组件做封装终结
       │   └─ 否 ──► ③ SR Proxy（静态/动态/伪装的）
       └─ 连 IPv6 都不支持？ ──► ③ 静态代理（接口对绑定）
```

:::en
An SR-aware service parses the SRv6 encapsulation, extracts the inner packet, applies its policy, then re-encapsulates the packet and continues the segment list. The cost is that the appliance must implement SRv6, including the SRH and the endpoint behaviors; the benefit is that it can also read and write metadata.
:::

**SR-aware** 服务**解析 SRv6 封装、取出内层报文、执行策略，然后重新封装并继续段列表**。代价是**设备必须实现 SRv6（含 SRH 与端点行为）**；收益是它**还能读写元数据**。

:::en
Inner packet exposure is a lighter option: the appliance is told the fixed offset at which the inner packet starts, so it can inspect the inner headers after a simple shift, without implementing any SRv6 logic. This is how legacy appliances are given visibility without being replaced.
:::

**内层暴露**是更轻的方案：**告诉设备"内层报文从固定偏移开始"**，它做一次简单的**偏移取指**就能看到内层头部，**完全不需要实现 SRv6 逻辑**。这是让**老设备"获得可见性"而不必换代**的办法。

三条路线的成本对比（含隐性成本）：

| 路线 | 一次性成本 | 长期成本 | 性能影响 | 适用寿命 |
|---|---|---|---|---|
| SR-aware | 高（设备换代） | 低 | 线速（硬件） | 长 |
| 内层暴露 | 中（旁挂组件） | 中（组件要维护） | 略降（多一跳/一次拷贝） | 中 |
| SR Proxy | 低 | **高（静态配置漂移）** | 低 | 短（作为过渡） |

## 12.3 SR-aware 服务必须做的五件事

1. **识别 SID**：DA 命中本地分配的 Service SID；
2. **取内层**：跳过 IPv6 头与 SRH（含 TLV），定位内层报文起始；
3. **执行策略**：用内层五元组/净荷做匹配；
4. **重建封装**：按**剩余段列表**重新封装（不能把 SID 列表弄丢或弄乱）；
5. **可选：写元数据**：把自己的判定写回 Arg/TLV，供下游使用。

:::en
The fourth step is where most implementations fail: re-encapsulation must preserve the remaining segment list and decrement the segment left pointer correctly. An appliance that pops the SRH and re-pushes a fresh one will silently break any chain longer than one segment.
:::

**第四步是大多数实现翻车的地方**：重新封装**必须保留剩余段列表，并正确递减 Segment Left 指针**。**一个"弹出 SRH 再重新压一个全新 SRH"的实现，会静默破坏任何长度大于 1 的链**——它自己"工作正常"，但后面所有段都失效。

| 实现错误 | 现象 | 排查方法 |
|---|---|---|
| SL 指针未正确递减 | 报文在服务后回到"已访问过的段" | trace 看是否回跳 |
| 剩余段被清空 | 服务后报文直接按外层 DA 路由 | trace 后续段无回应 |
| SRH 重写丢失 TLV | 元数据丢失，下游策略失效 | 服务侧抓包比对 |
| 内层偏移硬编码 | 带 SRH 的报文解析错位 | 只在不带 SRH 时正常 |

```text
例 12.1：SR-aware 服务的处理骨架（伪代码）
on packet:
    if DA not in local_service_sids: forward_normally()
    srh   = parse_srh(ipv6)
    inner = strip(ipv6, srh)
    verdict = policy_engine(inner)          # 五元组/净荷
    if verdict == DROP: drop(); return
    if verdict == MODIFY: inner = rewrite(inner)
    meta = encode_verdict(verdict)          # 可选：写回 Arg
    out = reencap(inner, remaining_segments(srh), meta)
    forward(out)                            # 继续段列表
```

## 12.4 内层暴露：为什么"固定偏移"能work

:::en
Inner packet exposure works because the encapsulation has a deterministic shape: after the outer IPv6 header and, when present, the SRH, the inner packet begins at an offset that the appliance can be configured with. The appliance is not required to understand SRv6; it only needs to be told where to look.
:::

内层暴露能成立，是因为**封装具有确定的形状**：**外层 IPv6 头之后、以及（存在时）SRH 之后，内层报文从一个可配置的偏移开始**。设备**不需要理解 SRv6**，**只需要被告知"从哪看"**。

```text
图 12-3：固定偏移（原书 Figure 12.3 重绘）

  情况 A：无 SRH（uSID 业务转发最常见）
    [IPv6 40B][内层 IP ...]
              ↑ 偏移 = 40（固定）

  情况 B：带 SRH，1 个容器 SID
    [IPv6 40B][SRH 8B][SID 16B][内层 IP ...]
              ↑ 偏移 = 64

  情况 C：带 SRH，2 个容器 SID
    [IPv6 40B][SRH 8B][SID 16B][SID 16B][内层 IP ...]
              ↑ 偏移 = 80

  老设备配置示例（只需一个数字）：
    inspect-offset 40     ← 无 SRH 场景
    inspect-offset 64     ← 带 SRH 场景
```

| 前提 | 说明 | 违反后果 |
|---|---|---|
| 偏移可配置 | 设备支持配"从第 N 字节开始看" | 只能用 SR Proxy |
| 偏移**稳定** | 该链路上封装形状不变（总是 40 或总是 64） | 解析错位，误判 |
| 不需要写回 | 设备只做"看"，不改报文 | 需 SR-aware 或代理 |

:::en
The constraint that makes this fragile in practice is the requirement that the offset be stable. If some traffic on the same appliance arrives with an SRH and some without, a single configured offset cannot serve both, and the operator must either split the traffic by policy or move to an SR-aware implementation.
:::

这个办法在工程上**真正脆弱的地方**是：**它要求偏移稳定**。如果**同一台设备上，一部分流量带 SRH、一部分不带**，**一个固定偏移不可能同时适配两者**，运维只能**按策略把流量分开**，或者**改用 SR-aware 实现**。

## 12.5 SERA：在设备前面放一个"翻译层"

:::en
SERA (SR-aware Edge Router Architecture) places an SR-aware component in front of the appliance. It terminates the SRv6 encapsulation, hands the inner packet to the firewall in the clear, receives it back, and re-imposes the encapsulation with the remaining segment list. The firewall's policy model stays exactly the same, and the network gains service chaining.
:::

**SERA（SR-aware Edge Router Architecture）** 在服务设备**前面**放一个 SR-aware 组件：它**终止 SRv6 封装**，把**裸内层报文**交给防火墙，**收回**处理后的报文，再**按剩余段列表重新封装**。**防火墙的策略模型一行不改**，网络侧却获得了服务链能力。

```text
图 12-4：SERA 的处理回路（原书 Figure 12.4 重绘）

  进: [IPv6 | SRH | 内层 IP ]
         │
         ▼
    SERA 组件（旁挂或内联）
         ├─ ① 暂存 SRH 与剩余段
         ├─ ② 剥封装 → 裸内层报文
         │        │
         │        ▼
         │    防火墙（策略完全不变）
         │        │
         │        ▼
         ├─ ③ 收回处理结果（可能被改、可能被丢）
         ├─ ④ 按暂存的段列表重新封装
         └─ ⑤ 写回元数据（判定结果）→ 继续下一段

  出: [IPv6 | SRH' | 内层 IP ]
```

SERA 与"固定偏移"的本质区别：

| 维度 | 固定偏移 | SERA |
|---|---|---|
| 谁解析封装 | **服务设备自己**（按偏移） | **外部组件** |
| 服务设备改动 | 需要"偏移可配" | **零改动** |
| 能否写回元数据 | 一般不能 | **能** |
| 适应 SRH 变化 | 不能（偏移固定） | **能**（组件动态解析） |
| 额外故障点 | 无 | **组件本身**（需高可用） |

:::en
The trade-off is explicit: SERA moves all SRv6 complexity into one well-understood component, at the price of making that component a critical dependency. In production it must be redundant, because its failure takes the service chain down even though the appliance itself is healthy.
:::

这个交换是显式的：**SERA 把所有 SRv6 复杂度集中到一个"懂 SRv6 的组件"里**，代价是**这个组件成了关键依赖**。生产环境里**它必须做冗余**——因为它挂了，**即使服务设备本身健康，服务链也会断**。

## 12.6 元数据：让服务之间传递结论

:::en
SID arguments can carry metadata: a classification result, a tenant identifier, a policy tag. An SR-aware service can read the metadata without parsing the full payload, and can write its own verdict back into the argument so that downstream services do not repeat the same work.
:::

SID 的 **Argument 可以携带元数据**：分类结果、租户标识、策略标签。SR-aware 服务**不用解析整个净荷就能读到元数据**，还能**把自己的判定写回 argument**，**下游服务无需重复劳动**。

```text
例 12.2：元数据在链上流动
① 头端分类：识别为"游戏流量，租户 T-100，SLA 低时延"
   → 写入 Arg：app=GAME, tenant=100, sla=low

② 防火墙：读 Arg → 免做 DPI（已知是游戏）→ 只做 ACL 检查
   → 写回：verdict=allow

③ DDoS 清洗：读 verdict=allow + app=GAME
   → 跳过重复分类，直接进入游戏专用清洗模板

④ 出口 VPN SID：不再需要元数据（已落地）

收益：全链只做一次深度检测，其余节点读结论
```

> 这也解释了第 15 章阿里为什么坚持把 TE-class 与 tenant ID 编进本地 SID 结构——他们用 **WLIB（32 bit 本地 uSID）** 腾出这些字段。

| 元数据承载方式 | 空间 | 可见范围 | 适用 |
|---|---|---|---|
| SID 的 **Argument 字段** | 随 locator 规划而定（16–48 bit） | 沿途所有节点 | 简短标签（app/tenant/class） |
| **SRH TLV** | 较大（受 MTU 限制） | SR-aware 节点 | 结构化信息 |
| **内层封装**（如 NSH、VXLAN-GPE） | 大 | 需内层解析能力 | 已有 overlay 体系 |

:::en
Metadata must be treated as untrusted when it crosses a boundary: an argument set by one administrative domain should not be relied upon by another without validation, because it is carried in the packet and can be forged.
:::

元数据**在跨域时必须当作不可信输入**：**一个管理域写入的 argument，另一个域在使用前必须校验**——因为它**装在报文里，是可以被伪造的**。

## 12.7 排障：服务设备"没反应"

```text
服务设备没告警 / 策略不生效
  │
  ├─ ① 它看到的是不是裸报文？
  │    tcpdump -i any -nn -v
  │    └─ 看到 IPv6 + Next Header=43 → 封装没剥，设备失明
  │
  ├─ ② 是不是把扩展头当"未知协议"丢了？
  │    设备日志 "unknown protocol 43" / "unsupported next header"
  │    └─ 需 SERA 或 SR Proxy
  │
  ├─ ③ 偏移对不对？
  │    同一链路上部分流量带 SRH、部分不带
  │    └─ 偏移配错 → 解析错位，规则乱匹配
  │
  ├─ ④ 元数据还在吗？
  │    服务侧抓包看 Arg/TLV
  │    └─ 丢失 → 中间有节点重写了 SRH
  │
  └─ ⑤ 服务之后为什么断了？
       trace 带完整列表
       └─ 后续段无回应 → 服务重封装时破坏了剩余段
```

| 检查项 | 命令/方法 | 期望 |
|---|---|---|
| 服务侧看到的报文 | `tcpdump -nn -v` | 裸内层（或已知偏移） |
| Next Header | 同上 | 不是 43（或设备能处理 43） |
| 策略命中 | 设备计数 | 有匹配计数增长 |
| 剩余段完好 | `traceroute srv6 ... sid-list ...` | 服务后续段有回应 |
| 元数据 | 抓包比对 Arg/TLV | 与写入值一致 |
| SERA 组件状态 | 组件自身健康检查 | 主备都正常 |

## 12.8 本章小结

:::en
Encapsulation hides the packet from the service, and every option in this chapter is a way of giving the service its sight back: native SR-awareness, inner packet exposure at a fixed offset, or an SR-aware proxy in front. The choice is dictated by what the appliance can be made to do, not by what the network would prefer.
:::

**封装让服务失明**，本章的每一个选项都是**把"视力"还给服务的办法**：**原生 SR-aware、固定偏移的内层暴露、或者前置一个 SR-aware 代理**。选择**由设备能被改到什么程度决定，而不是由网络侧的偏好决定**。

| 维度 | SR-aware | 固定偏移 | SR Proxy |
|---|---|---|---|
| 服务设备改动 | 大 | 小（偏移可配） | **零** |
| 看内层 | 能 | 能 | **不能**（只看裸报文） |
| 读写元数据 | 能 | 一般不能 | **不能** |
| 对 SRH 变化的适应性 | 强 | 弱 | 中 |
| 额外组件 | 无 | 无 | 有 |
| 推荐度 | **首选** | 过渡 | **过渡** |

一句话收束：**"服务能编排" 的前提是 "服务能看见"**；而**能不能看见，取决于你愿不愿意改设备**——不改设备，就只能接受"看不见元数据"的代价。

## 实战案例

### 案例 A：SR-Snort 与"看不见"的排障（原书案例）

**背景**：某实验室把开源 IDS（Snort）接入 SRv6 服务链做验证，最初把流量直接引到 Snort 所在主机。

**现象**：**Snort 一条告警都不出**。抓包发现它收到的是 `IPv6 + SRv6` 封装包，**规则库全部按内层 IPv4 匹配**，自然全部落空。

| 方案 | 改动 | 结果 |
|---|---|---|
| Snort 前加解封装 + 后加重新封装 | 需旁挂组件 | 可用，但引入额外一跳与 MTU 问题 |
| 用 SR Proxy（第 13 章） | 平台侧配置 | Snort 收到裸报文，但**丢失 SID 元数据** |
| 改造为 SR-aware（SERA） | Snort 侧加解析层 | **能看内层 + 能读写元数据，最佳** |

**最终选择**：SERA 组件 + 原生 Snort 规则，**规则不动、链路可编排**；同时**把分类结果写入 Arg**，下游 DDoS 清洗直接读取，**省一次检测**。

**排障提示**：

- "服务设备没告警"优先怀疑：**它看到的是不是裸报文**？`tcpdump -i any -nn -v` 看外层有没有 IPv6 扩展头；
- 若设备报"未知协议"，检查它是否把 `Next Header = 43` 当成不可识别协议丢弃；
- 元数据被中间节点改写 → 检查是否有节点误配了 Arg 相关的行为。

### 案例 B：防火墙上线后"策略全放通"

**现象**：某企业专线接入 SRv6 服务链后，防火墙（老型号，不支持 IPv6 扩展头）显示"策略命中为零"，但业务全部通——**等于没有防护**。

```text
① 防火墙侧日志：无匹配记录，会话表为空
② 抓包：防火墙上收到的是 [IPv6][SRH][内层 IPv4]，
   它把 IPv6 头当作"透明"跳过，直接看到的是……什么都没有
   因为它只解析到 IPv4 就停，遇到 IPv6 直接按默认策略放行
③ 关键风险：默认策略是"允许"，于是全通
④ 临时措施：把默认策略改为"拒绝" → 业务全断（说明确实没生效）
⑤ 修复：加 SERA 组件，防火墙收到裸 IPv4 报文，策略立刻正常命中
⑥ 复盘：割接前必须做"负向验证"——用一条本该被拒绝的流量试一下
```

**教训**：**"业务通" 可能是"防护没生效"的伪装**。服务链上线验收必须包含**负向测试**：

| 验收项 | 方法 | 判据 |
|---|---|---|
| 策略真的生效 | 发一条应被拒绝的流量 | 被拒（而非放通） |
| 策略不是默认放通 | 清空策略后重试 | 应全断 |
| 内层可见 | 设备侧抓包 | 能看到内层五元组 |
| 计数器 | 设备策略计数 | 有增长 |

### 案例 C：元数据被"好心"的中间节点抹掉

**现象**：链上第 2 跳（DPI）写入的 `verdict` 元数据，到第 3 跳（清洗）时读不到，导致清洗平台重复做全量检测，性能掉 40%。

```text
① 抓包对比：DPI 出口的 SRH 有 TLV（verdict=allow）
② 清洗平台入口的 SRH 没有 TLV
③ 逐跳排查：中间的 PE 上启用了某"SRH 规范化"特性
   ——它为了兼容老硬件，重建 SRH 时只保留 SID 列表，丢弃 TLV
④ 修复：该 PE 关闭规范化；或将元数据改放到 Arg（Arg 随 SID 保留）
⑤ 复测：清洗平台读到 verdict，跳过重复检测，性能恢复
```

**教训**：**元数据放在 TLV 里最"脆"，放在 Arg 里最"稳"**——因为 **Arg 是 SID 的一部分，任何按 SID 转发的节点都不会动它**；TLV 则可能在任何一次"重建 SRH"中丢失。

## 延伸阅读

- **RFC 8986**：端点行为与 `End.DT`/`End.DX` 族，SR-aware 服务需要实现的语义。
- **RFC 8754**：SRH 格式与 SL 指针，12.3 中"重封装必须正确"的规范依据。
- **RFC 8300**：NSH（Network Service Header），另一种"服务链元数据"思路的对照。
- **draft-ietf-spring-sr-service-programming**：Service SID 与 SR-aware 服务架构。
- **SERA**：SR-aware Edge Router Architecture（原书引用的架构提案）。
- 交叉参考：第 11 章（服务编程的控制面）、第 13 章（SR Proxy 的三种实现）、第 16 章（Bell SP 的 DDoS 生产链怎么处理元数据）。
