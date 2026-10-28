# 12 · SR-aware 服务与内层报文暴露

> 对应原书第 12 章 *SR-aware Services*。问题很直接：**防火墙只看到外层 IPv6 头，看不到内层五元组，策略就失效了。** 这一章讲三类做法。

## 12.1 问题：服务设备"看不见"真实流量

:::en
When a packet is encapsulated in SRv6, the appliance in the middle sees only the outer IPv6 header. A firewall that must match on the customer's five-tuple, or a DPI engine that must inspect the payload, cannot do its job on the outer header alone. The service is blind unless something exposes the inner packet to it.
:::

报文一旦被 SRv6 封装，中间设备只能看到外层 IPv6 头。防火墙要按客户五元组匹配、DPI 要检查净荷，光看外层头根本做不了。**除非有机制把内层报文"暴露"给服务设备，否则服务就是瞎的。**

## 12.2 三种处理方式

| 方式 | 设备需要改造 | 能否看内层 | 典型场景 |
|---|---|---|---|
| **SR-aware**（原生解析） | 是（支持 SRv6） | 能 | 新一代 vFW / vDPI / MEC |
| **内层暴露**（SERA 类） | 少量（解析固定偏移） | 能 | 改造困难的老设备 |
| **SR Proxy**（第 13 章） | 否 | 不能（只看裸报文） | 完全不支持 IPv6 的老设备 |

:::en
An SR-aware service parses the SRv6 encapsulation, extracts the inner packet, applies its policy, then re-encapsulates the packet and continues the segment list. The cost is that the appliance must implement SRv6, including the SRH and the endpoint behaviors; the benefit is that it can also read and write metadata.
:::

**SR-aware** 服务解析 SRv6 封装、取出内层报文、执行策略，然后重新封装并继续段列表。代价是设备必须实现 SRv6（含 SRH 与端点行为）；收益是它还能**读写的元数据**。

:::en
Inner packet exposure is a lighter option: the appliance is told the fixed offset at which the inner packet starts, so it can inspect the inner headers after a simple shift, without implementing any SRv6 logic. This is how legacy appliances are given visibility without being replaced.
:::

**内层暴露**是更轻的方案：告诉设备"内层报文从固定偏移开始"，它做一次简单的偏移取指就能看到内层头部，**完全不需要实现 SRv6 逻辑**。这是让老设备"获得可见性"而不必换代的办法。

## 12.3 SERA：让防火墙看懂 SRv6

:::en
SERA (SR-aware Edge Router Architecture) places an SR-aware component in front of the appliance. It terminates the SRv6 encapsulation, hands the inner packet to the firewall in the clear, receives it back, and re-imposes the encapsulation with the remaining segment list. The firewall's policy model stays exactly the same, and the network gains service chaining.
:::

SERA（SR-aware Edge Router Architecture）在服务设备前面放一个 SR-aware 组件：它终止 SRv6 封装，把裸内层报文交给防火墙，收回处理后的报文，再按剩余段列表重新封装。**防火墙的策略模型一行不改**，网络侧却获得了服务链能力。

```text
报文: [IPv6 | SRH | 内层 IP ]
         │
         ▼
    SERA 组件 ──裸内层报文──► 防火墙 ──处理结果──► SERA 重新封装
         │
         ▼
    [IPv6 | SRH' | 内层 IP ]  → 继续下一段
```

## 12.4 元数据：把策略结果带回网络

:::en
SID arguments can carry metadata: a classification result, a tenant identifier, a policy tag. An SR-aware service can read the metadata without parsing the full payload, and can write its own verdict back into the argument so that downstream services do not repeat the same work.
:::

SID 的 **Argument 可以携带元数据**：分类结果、租户标识、策略标签。SR-aware 服务不用解析整个净荷就能读到元数据，还能把自己的判定写回 argument，**下游服务无需重复劳动**。

> 这也解释了第 15 章阿里为什么坚持把 TE-class 与 tenant ID 编进本地 SID 结构——他们用的是 WLIB（32 bit 本地 uSID）来腾出这些字段。

## 实战案例：SR-Snort 与"看不见"的排障

**背景**：某实验室把开源 IDS（Snort）接入 SRv6 服务链做验证，最初的做法是直接把流量引到 Snort 所在主机。

**现象**：Snort 一条告警都不出。抓包发现它收到的是 `IPv6 + SRv6` 封装包，规则库全部按内层 IPv4 匹配，自然全部落空。

**三种修法对比**：

| 方案 | 改动 | 结果 |
|---|---|---|
| 在 Snort 前加解封装 + 后加重新封装 | 需要旁挂组件 | 可用，但引入额外一跳与 MTU 问题 |
| 用 SR Proxy（第 13 章） | 平台侧配置 | Snort 收到裸报文，但**丢失 SID 元数据** |
| 改造为 SR-aware（SERA） | Snort 侧加解析层 | 能看内层 + 能读写元数据，最佳 |

**最终选择**：SERA 组件 + 原生 Snort 规则，规则不动、链路可编排；同时把分类结果写入 Arg，下游 DDoS 清洗直接读取，省一次检测。

**排障提示**：

- "服务设备没告警"优先怀疑：它看到的是不是裸报文？`tcpdump -i any -nn -v` 看外层有没有 IPv6 扩展头。
- 若设备报"未知协议"，检查它是否把 `Next Header = 43` 当成不可识别协议丢弃。
- 元数据被中间节点改写 → 检查是否有节点误配了 Arg 相关的行为。

## 本章小结

1. 封装导致服务设备失明，必须显式暴露内层或让设备 SR-aware。
2. 三条路线：原生 SR-aware、固定偏移暴露、SR Proxy。
3. 元数据（Arg）是"服务之间传递结论"的载体，避免重复检测。
4. 选型取决于设备改造能力，而不是网络侧偏好。
