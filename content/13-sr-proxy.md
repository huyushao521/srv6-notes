# 13 · 遗留应用的 SR Proxy

> 对应原书第 13 章 *SR Proxy*（RFC 8986 §8）。它解决的问题最现实：**设备完全不懂 SRv6，但它必须留在服务链里。**

## 13.1 为什么不能让它们直接进链

:::en
A legacy appliance may drop packets with an IPv6 routing header, or may not even support IPv6. It cannot be expected to parse a segment list, and it certainly cannot be expected to re-encapsulate. The SR proxy behavior solves this by moving the encapsulation logic into the adjacent SRv6-capable router: the proxy removes the encapsulation before the packet reaches the appliance, and restores it afterwards.
:::

老设备可能直接丢弃带 IPv6 路由头的报文，甚至根本不支持 IPv6。你不可能要求它解析段列表，更不可能要求它重新封装。SR Proxy 把封装逻辑搬到旁边那台支持 SRv6 的路由器上：**进设备前剥封装，出设备后恢复封装**。

核心动作只有三步：

```text
收到: [IPv6 | SRH | 净荷]  →  缓存外层头
      ↓
交给设备: [净荷]                      ← 裸报文，设备完全不知道 SRv6
      ↓
收回: 重新压上缓存的外层头（或下一段）  →  继续转发
```

## 13.2 三种代理行为

:::en
There are three flavors. A static proxy (End.AS) is configured with the encapsulation to restore, so it has no state but requires manual configuration per path. A dynamic proxy (End.AD) caches the encapsulation it removed, so it works with any path but needs shared memory to store it. A masquerading proxy (End.AM) rewrites the packet as if the appliance itself had originated it, which is the only option when the appliance also originates traffic.
:::

| 行为 | 名称 | 状态 | 适用 |
|---|---|---|---|
| **End.AS** | 静态代理 | 无状态（配置写死） | 服务链路径固定、设备只转发 |
| **End.AD** | 动态代理 | 有状态（缓存外层头） | 路径动态、设备只转发 |
| **End.AM** | 伪装代理 | 有状态（地址映射） | 设备自己也会发起流量 |

:::en
The static proxy is the simplest: the restoring encapsulation is part of the configuration, so the dataplane is stateless, but any change in the path requires a configuration change. The dynamic proxy removes the encapsulation, stores it in memory keyed by the inner flow, and restores it when the packet comes back — this costs memory and must be sized for the number of concurrent flows.
:::

- **End.AS（静态）**：恢复用的封装写在配置里，**转发面无状态**、性能最好；但路径一变就要改配置。
- **End.AD（动态）**：剥下来的封装按内层流做键缓存到内存，回来时按流查表恢复；灵活，但要按并发流数预留内存——高流量场景这是隐性成本。
- **End.AM（伪装）**：把报文改写成"设备自己发的"，返回时再还原；这是**设备会主动发起流量**时唯一可行的方案（例如某些代理型防火墙）。

## 13.3 代价与限制

| 限制 | 说明 |
|---|---|
| 丢失元数据 | 设备只看到裸报文，读不到 Arg 里的分类结果（对比第 12 章 SERA） |
| MTU 二次膨胀 | 恢复封装时包又变大，需要保证出口 MTU 足够 |
| 有状态风险 | End.AD/AM 的缓存丢失会导致流中断，需考虑高可用 |
| 无法做 SID 级策略 | 设备看不到 SID，不能按 SID 做差异化处理 |
| 路径可见性差 | 出问题时两端都"看起来正常"，故障定位困难 |

:::en
The most important limitation is the loss of metadata: the appliance sees a plain packet, so any classification result carried in the SID argument is invisible to it. This is the fundamental trade-off between SR Proxy, which requires no change to the appliance, and SR-aware processing, which requires the appliance to understand SRv6.
:::

最重要的限制是**元数据丢失**：设备看到的是裸报文，SID argument 里的分类结果它一概看不见。这就是 SR Proxy（设备零改造）与 SR-aware（设备懂 SRv6）之间的根本取舍：**一个省改造成本，一个省运维复杂度。**

## 实战案例：老防火墙进链的三种落地方式

**背景**：某运营商有 20 台老旧硬件防火墙（仅支持 IPv4/IPv6 双栈，不认识 SRH），必须继续承载南北向安全策略。

**方案对比与选择**：

| 方案 | 改造成本 | 运维复杂度 | 结论 |
|---|---|---|---|
| 换设备为 SR-aware | 高（CAPEX） | 低 | 长期方向 |
| SR Proxy（End.AD） | 低（仅 PE 配置） | 中（有状态、需容量规划） | **过渡期采用** |
| 旁路引流 + 重新注入 | 中 | 高（环路风险） | 不采用 |

**实施要点**：

1. PE 上为每台防火墙配置代理行为，服务链里用 Service SID 指向它。
2. End.AD 的缓存表按峰值并发流规划；主备切换时接受短暂重建（新流不受影响，老流会断）。
3. 抓包验证：防火墙侧应只看到裸报文；PE 出方向应恢复完整封装。
4. 与 UPA/TI-LFA 联动验证：代理有状态，故障切换后老流必然中断，需业务侧容忍或有会话同步。

**排障经验**：

| 现象 | 原因 |
|---|---|
| 设备侧收到带 SRH 的包 | 代理行为没生效，SID 未实例化 |
| 单向通 | 只配了入向代理，回程未还原 |
| 大包不通 | 恢复封装后超 MTU |
| 一段时间后偶发断流 | End.AD 缓存老化或内存不足 |

## 本章小结

1. SR Proxy 把封装逻辑外移到旁挂 PE，让完全不懂 SRv6 的设备也能进服务链。
2. 三种行为：静态（无状态）、动态（缓存）、伪装（设备也发流量）。
3. 代价是元数据不可见、有状态与 MTU 风险；与 SR-aware 是互补关系。
4. 过渡期用它保 CAPEX，长期仍应走向 SR-aware。
