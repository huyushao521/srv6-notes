# 13 · 遗留应用的 SR Proxy：让不懂 SRv6 的设备进链

> **本章定位**：原书第 13 章《SR Proxy》（RFC 8986 §8）。它解决的问题最现实：**设备完全不懂 SRv6，但它必须留在服务链里。** 英文块为原文摘录，中文为完整翻译，Figure 13.1–13.4 重绘，Example 13.1–13.3 保留。

**本章要拿到的东西**：

| 问题 | 对应小节 |
|---|---|
| 为什么老设备不能"直接进链" | 13.1 |
| 代理的核心动作只有三步，是哪三步 | 13.2 |
| 静态 / 动态 / 伪装三种代理的本质差别 | 13.3 |
| 动态代理的"状态"到底存的是什么，要多少内存 | 13.4 |
| 为什么 SR Proxy 一定丢元数据 | 13.5 |
| 什么情况下必须用 SR Proxy 而不是 SERA | 13.6 |
| 主备切换后老流为什么必断 | 13.7 |

一句话概括：**SR Proxy 把封装逻辑从"设备"搬到"旁边的路由器"**——设备看到的是**裸报文**，路由器负责**进前剥、出后恢复**。它是**唯一不需要碰设备**的方案，代价是**服务永远看不到 SID 与元数据**。

## 13.1 为什么不能让它们直接进链

:::en
A legacy appliance may drop packets with an IPv6 routing header, or may not even support IPv6. It cannot be expected to parse a segment list, and it certainly cannot be expected to re-encapsulate. The SR proxy behavior solves this by moving the encapsulation logic into the adjacent SRv6-capable router: the proxy removes the encapsulation before the packet reaches the appliance, and restores it afterwards.
:::

老设备可能**直接丢弃带 IPv6 路由头的报文**，甚至**根本不支持 IPv6**。你不可能要求它**解析段列表**，更不可能要求它**重新封装**。SR Proxy 把**封装逻辑搬到旁边那台支持 SRv6 的路由器**上：**进设备前剥封装，出设备后恢复封装**。

具体会遇到三类设备：

| 设备类型 | 行为 | 直接进链的后果 |
|---|---|---|
| 支持 IPv6，但丢弃带扩展头的包 | 见到 `Next Header=43` 就丢 | **静默丢包**，无日志 |
| 只支持 IPv4 | 完全不解析 IPv6 | 整包丢弃 |
| 支持 IPv6，且会**自己发起**流量 | 回程流量没有 SRv6 封装 | 回程无法进链，**单向通** |

第三类最容易被忽略：**设备主动发起的流量（健康检查、审计日志回传、DNS 查询）没有外层封装**，所以代理必须能**双向**处理。

## 13.2 代理的核心动作只有三步

```text
图 13-1：代理的三步（原书 Figure 13.1 重绘）

  收到: [IPv6 | SRH | 净荷]
        │
        ① 缓存外层头（或按配置构造）
        ▼
  交给设备: [净荷]                 ← 裸报文，设备完全不知道 SRv6
        │
        ② 设备处理（策略、检测、改写）
        ▼
  收回: ③ 重新压上缓存的外层头（或下一段）
        │
        ▼
  [IPv6 | SRH' | 净荷]  → 继续转发
```

:::en
The proxy is a behavior of the adjacent router, not of the appliance. That is the key architectural point: the SID in the segment list points at the router, and the router is what appears in the network as the service endpoint. The appliance is invisible to the SR domain.
:::

**代理是"旁边那台路由器"的行为，不是设备的行为**。这是关键架构点：**段列表里的 SID 指向路由器，路由器才是网络中"看起来的服务端点"**；**设备对 SR 域完全不可见**。

这个特性带来一个常被忽视的好处：**服务链的段列表不需要知道设备的地址**。换设备、改设备 IP，**段列表不用变**——只要代理配置改一下接口。

## 13.3 三种代理行为

:::en
There are three flavors. A static proxy (End.AS) is configured with the encapsulation to restore, so it has no state but requires manual configuration per path. A dynamic proxy (End.AD) caches the encapsulation it removed, so it works with any path but needs shared memory to store it. A masquerading proxy (End.AM) rewrites the packet as if the appliance itself had originated it, which is the only option when the appliance also originates traffic.
:::

三种行为：

| 行为 | 名称 | 行为码 | 状态 | 适用 |
|---|---|---|---|---|
| **`End.AS`** | 静态代理 | 0x0041 | **无状态**（配置写死恢复内容） | 服务链路径固定、设备只转发 |
| **`End.AD`** | 动态代理 | 0x0043 | **有状态**（缓存外层头） | 路径动态、设备只转发 |
| **`End.AM`** | 伪装代理 | 0x0042 | **有状态**（地址映射） | **设备自己也会发起流量** |

:::en
The static proxy is the simplest: the restoring encapsulation is part of the configuration, so the dataplane is stateless, but any change in the path requires a configuration change. The dynamic proxy removes the encapsulation, stores it in memory keyed by the inner flow, and restores it when the packet comes back — this costs memory and must be sized for the number of concurrent flows.
:::

- **`End.AS`（静态）**：**恢复用的封装写在配置里**，**转发面无状态**、性能最好；但**路径一变就要改配置**；
- **`End.AD`（动态）**：**剥下来的封装按内层流做键缓存到内存**，回来时**按流查表恢复**；灵活，但要**按并发流数预留内存**——高流量场景这是隐性成本；
- **`End.AM`（伪装）**：把报文**改写成"设备自己发的"**，返回时再还原；这是**设备会主动发起流量**时**唯一可行**的方案（例如某些代理型防火墙）。

```text
图 13-2：三种代理的处理对比（原书 Figure 13.2 重绘）

  End.AS（静态）
    进: [IPv6|SRH|P] → 缓存策略：不看实际头，按配置构造
    出: 按"配置里写的下一段"重新封装
      ✔ 无状态、最快   ✘ 路径变了要改配置；多路径场景做不到

  End.AD（动态）
    进: [IPv6|SRH|P] → 缓存(key=内层五元组, value=外层头+剩余段)
    出: 按 key 查表 → 恢复原封装
      ✔ 任意路径都能用  ✘ 占内存；缓存丢失/老化 = 流断

  End.AM（伪装）
    进: [IPv6|SRH|P] → 改写源地址为"设备地址"，剥封装
    出: 设备主动发的流也能被识别并重新封装
      ✔ 双向都能进链    ✘ 地址映射有状态，NAT 语义复杂
```

| 维度 | End.AS | End.AD | End.AM |
|---|---|---|---|
| 转发面状态 | **无** | 每流一条 | 每流/每映射一条 |
| 内存需求 | 0 | 并发流数 × 约 100 B | 并发流数 × 映射表项 |
| 路径变更 | **需改配置** | 自动适应 | 自动适应 |
| 设备主动流量 | 不支持 | 不支持 | **支持** |
| 主备切换 | **无缝** | 老流中断 | 老流中断 |
| 典型用途 | 固定拓扑、单路径 | 多路径/SR Policy | 代理型防火墙、LB |

## 13.4 状态到底存了什么：End.AD 的容量账

:::en
The dynamic proxy's state is the encapsulation it removed, keyed by the inner flow. The size of that state is therefore a function of two numbers: how many concurrent flows traverse the appliance, and how large the saved encapsulation is. Both must be estimated before deployment, because an undersized cache silently degrades into dropped flows.
:::

**动态代理的状态，就是"它剥下来的那个封装"**，用**内层流做键**。所以这张表的大小是**两个数的函数**：**并发穿越设备的流数**，以及**保存的封装有多大**。**两者都必须在部署前估算**，因为**缓存不够时会静默退化成"丢流"**。

```text
例 13.1：End.AD 的缓存容量估算

单个表项：
  key   = 内层五元组 + 接口          约 32 B
  value = 外层 IPv6 头(40) + SRH(8~40) + 元信息  约 64–96 B
  合计  ≈ 100–130 B / 流

场景 A：小型企业出口，并发 20,000 流
  20,000 × 130 B ≈ 2.6 MB          → 任何平台都够

场景 B：城域清洗中心，并发 2,000,000 流
  2,000,000 × 130 B ≈ 260 MB       → 需要专门的内存规划

场景 C：老化时间 30 s，新建速率 60,000 流/s
  稳态流数 ≈ 60,000 × 30 = 1,800,000（与场景 B 同量级）
  → 必须同时配"表满告警"与"老化时间调优"
```

| 参数 | 影响 | 建议 |
|---|---|---|
| 缓存表大小 | 决定能承载多少并发流 | 按峰值 × 1.5 规划 |
| 老化时间 | 太短 → 长连接被误删；太长 → 表满 | 大于最长空闲间隔（通常 60–120 s） |
| 表满策略 | 丢新流 / 丢老流 | **丢新流并告警**（可观测） |
| 主备同步 | 无同步 → 切换后老流断 | 业务侧能容忍，或用会话同步 |

:::en
Note that the failure mode of an undersized dynamic proxy cache is not a clean error: the flow simply stops forwarding in one direction, and the appliance reports normal operation because it never sees the encapsulated packet again.
:::

注意：**动态代理缓存不够时的失败方式不是"报错"**，而是**该方向突然停止转发**；而**设备侧显示一切正常**——因为它**再也收不到那个封装包了**。这是本章最难排查的故障模式。

## 13.5 代价：为什么 SR Proxy 一定丢元数据

:::en
The most important limitation is the loss of metadata: the appliance sees a plain packet, so any classification result carried in the SID argument is invisible to it. This is the fundamental trade-off between SR Proxy, which requires no change to the appliance, and SR-aware processing, which requires the appliance to understand SRv6.
:::

最重要的限制是**元数据丢失**：设备看到的是**裸报文**，**SID argument 里的分类结果它一概看不见**。这就是 **SR Proxy（设备零改造）** 与 **SR-aware（设备懂 SRv6）** 之间的**根本取舍**：**一个省改造成本，一个省运维复杂度**。

| 限制 | 说明 | 缓解 |
|---|---|---|
| **丢失元数据** | 设备读不到 Arg/TLV | 把结论放到**内层**（如 DSCP、ToS 位）或改用 SERA |
| MTU 二次膨胀 | 恢复封装时包又变大 | 出口 MTU 按"最大封装"预留 |
| 有状态风险 | End.AD/AM 缓存丢失 → 流中断 | 高可用 + 业务容忍 |
| 无法做 SID 级策略 | 设备看不到 SID | 由代理路由器做 SID 级策略 |
| 路径可见性差 | 两端都"看起来正常" | 在代理上加计数与 trace 埋点 |

:::en
A practical workaround for the metadata loss is to carry the classification in a field that the appliance already understands, such as the DSCP or the ToS bits of the inner header. This requires the proxy to copy the metadata into the inner header before exposing the packet, and to restore it afterwards if the appliance is expected to preserve it.
:::

元数据丢失的一个**实用绕法**：**把分类信息放进设备本来就懂的字段**——比如**内层头的 DSCP / ToS**。这要求**代理在暴露报文前把元数据写进内层头**，并在收回后**恢复**（如果设备会改它）。

| 承载位置 | 设备可见 | 可写回 | 空间 |
|---|---|---|---|
| SID Arg（原方案） | **不可见** | — | 16–48 bit |
| 内层 DSCP/ToS | 可见 | 可以 | 6–8 bit（很挤） |
| 内层 VLAN Tag | 可见（若二层） | 可以 | 12 bit |
| 内层 IP 选项/扩展头 | 可见（但常被丢） | 不一定 | 有限 |

## 13.6 什么时候必须用 SR Proxy：与 SERA 的分界

| 条件 | 选择 | 理由 |
|---|---|---|
| 设备能改代码/能配偏移解析 | **SERA / 内层暴露**（第 12 章） | 保留元数据、无状态 |
| 设备完全不支持 IPv6 | **SR Proxy** | 唯一选择 |
| 设备会主动发起流量 | **End.AM** | 普通代理无法处理回程 |
| 设备只转发、路径固定 | **End.AS** | 无状态、最快 |
| 设备只转发、路径动态 | **End.AD** | 自动适应 |
| 需要按规定保留元数据 | **SR-aware** | 代理做不到 |

```text
图 13-3：决策路径（原书 Figure 13.3 重绘）

  设备支持 SRv6？──是──► SR-aware（第 12 章）
        │否
  能改造成"能配偏移"？──是──► 内层暴露 / SERA
        │否
  设备会主动发起流量？──是──► End.AM（伪装代理）
        │否
  路径固定（单链路/单策略）？──是──► End.AS（静态）
        │否
        └──────────────────────► End.AD（动态）
```

## 13.7 配置与验证

**例 13.2：End.AD 代理一台老防火墙**

```text
! ① 定义代理 SID：进入后剥封装，交给防火墙，回来后恢复
segment-routing
 srv6
  locators
   locator MAIN
    micro-segment behavior unode pfx-16
    prefix fdbb:bb00:0001::/48
   !
  !
 !
!
segment-routing
 srv6
  static-sids
   sid fdbb:bb00:0001:ad00:: behavior End.AD
    interface HundredGigE0/0/0/2      ! 面向老防火墙的接口
   !
  !
 !
!
! ② 服务链里用这个代理 SID（由控制器或头端策略下发）
!    <uN 传输> , <End.AD 代理 SID> , <uDT46 目的>

! ③ 若设备只转发且路径固定，改用 End.AS（无状态、性能更好）
!    sid fdbb:bb00:0001:as00:: behavior End.AS
!     interface HundredGigE0/0/0/2
!     next-hop  fdbb:bb00:0001:e00a::   ! 恢复时用的下一段（写死在配置里）
```

**例 13.3：验证代理真的在工作**

```text
! ① 防火墙侧：应只看到裸报文，绝不能看到 IPv6 扩展头
RP/0/RP0/CPU0:FW# monitor capture ...
  → 抓到的报文：以太 + IPv4 + TCP，无 IPv6 头  ✔

! ② 代理侧：动态缓存表有表项
RP/0/RP0/CPU0:PE-1# show segment-routing srv6 proxy state
Behavior      SID                          Flows    HWM
End.AD        fdbb:bb00:0001:ad00::        18,442   21,006
End.AS        fdbb:bb00:0001:as00::        -        -

! ③ 端到端：段列表完整执行
RP/0/RP0/CPU0:PE-1# traceroute srv6 fdbb:bb00:0005:e101:: sid-list fdbb:bb00:0001:ad00::,fdbb:bb00:0005:e101::
 1  fdbb:bb00:0001:ad00::   0.6 ms
 2  fdbb:bb00:0005:e101::   1.3 ms

! ④ 大包：恢复封装后不超 MTU
RP/0/RP0/CPU0:PE-1# ping vrf CUSTOMER-100 10.1.2.1 size 1472 repeat 5
!!!!!
```

| 检查项 | 命令 | 期望 |
|---|---|---|
| 代理 SID 已实例化 | `show segment-routing srv6 sid all` | 有 End.AS/AD/AM 条目 |
| 设备侧看到裸报文 | 设备抓包 | 无 IPv6 扩展头 |
| 缓存表水位 | `show ... proxy state` | HWM < 容量 80% |
| 双向都恢复 | 双向业务测试 | 不单向 |
| 大包 | `ping size 1472` | 通 |
| 故障切换 | 主备切换测试 | 老流断、新流正常（End.AD/AM） |

## 13.8 排障

| 现象 | 原因 | 处理 |
|---|---|---|
| 设备侧收到带 SRH 的包 | 代理行为没生效 / SID 未实例化 | 查 `show segment-routing srv6 sid` |
| **单向通** | 只配了入向代理，回程未还原 | 检查双向接口与 End.AM 是否必要 |
| 大包不通 | 恢复封装后超 MTU | 提高出口 MTU / 钳制 MSS |
| 一段时间后偶发断流 | End.AD 缓存老化或内存不足 | 调老化时间 / 扩容量 / 查 HWM |
| 主备切换后老流全断 | End.AD/AM 状态未同步 | 业务容忍，或会话同步 |
| 设备策略不生效 | 设备看到的是裸报文但**看不到元数据** | 改用 SERA（第 12 章） |

:::en
The single most useful diagnostic is to capture on the appliance side: if the appliance sees an IPv6 header with a routing header, the proxy is not working; if it sees a clean inner packet but still does not apply policy, the problem is the missing metadata rather than the proxy.
:::

**最有价值的一条排障判据**：**在设备侧抓包**——**如果设备看到带路由头的 IPv6 头，说明代理没生效**；**如果设备看到干净的裸报文、但策略仍然不生效，那问题不是代理，而是元数据丢了**（第 12 章）。

## 13.9 本章小结

:::en
SR Proxy is the bridge for appliances that cannot be changed: the adjacent router terminates the encapsulation, exposes the plain packet, and restores the encapsulation afterwards. Static, dynamic and masquerading flavors cover the cases of fixed paths, dynamic paths, and appliances that also originate traffic. The cost is state and the loss of metadata.
:::

SR Proxy 是**"改不了的设备"的桥**：**旁边那台路由器终结封装、暴露裸报文、之后再恢复封装**。**静态、动态、伪装**三种，分别覆盖**固定路径、动态路径、设备也发流量**三种情况。代价是**状态**与**元数据丢失**。

| 维度 | End.AS | End.AD | End.AM |
|---|---|---|---|
| 状态 | 无 | 有 | 有 |
| 路径变更 | 需改配置 | 自动 | 自动 |
| 设备主动流量 | ✘ | ✘ | ✔ |
| 主备切换 | 无缝 | 老流断 | 老流断 |
| 元数据 | 丢失 | 丢失 | 丢失 |
| 推荐 | 固定拓扑首选 | 通用过渡 | 双向必需时 |

一句话收束：**SR Proxy 让"设备零改造"成为可能，但它把复杂度转移给了"有状态的路由器"**——**能不用就不用，要用就优先 End.AS**（无状态），**只有设备会发流量时才上 End.AM**。

## 实战案例

### 案例 A：20 台老防火墙进链（原书案例）

**背景**：某运营商有 **20 台老旧硬件防火墙**（支持 IPv4/IPv6 双栈，但**不认识 SRH**），必须继续承载南北向安全策略。

| 方案 | 改造成本 | 运维复杂度 | 结论 |
|---|---|---|---|
| 换设备为 SR-aware | 高（CAPEX） | 低 | 长期方向 |
| **SR Proxy（End.AD）** | 低（仅 PE 配置） | 中（有状态、需容量规划） | **过渡期采用** |
| 旁路引流 + 重新注入 | 中 | 高（环路风险） | 不采用 |

**实施要点**：

1. PE 上为每台防火墙配置代理行为，**服务链里用 Service SID 指向它**；
2. `End.AD` 的缓存表**按峰值并发流规划**；主备切换时**接受短暂重建**（新流不受影响，老流会断）；
3. 抓包验证：**防火墙侧应只看到裸报文**；**PE 出方向应恢复完整封装**；
4. 与 UPA/TI-LFA 联动验证：**代理有状态，故障切换后老流必然中断**，需业务侧容忍或有会话同步。

**排障经验**（与原书一致）：

| 现象 | 原因 |
|---|---|
| 设备侧收到带 SRH 的包 | 代理行为没生效，SID 未实例化 |
| 单向通 | 只配了入向代理，回程未还原 |
| 大包不通 | 恢复封装后超 MTU |
| 一段时间后偶发断流 | End.AD 缓存老化或内存不足 |

### 案例 B：End.AS 省了内存，败在了"加了一条备份链路"

**背景**：某市网为省内存，全部用 `End.AS`（无状态）。半年后为防火墙加了第二条上行链路做负载分担。

```text
① 加链路后：约 50% 的会话"建立成功但传不动数据"
② 抓包：防火墙回来的报文，代理按配置里写死的 next-hop 恢复封装
   → 一律送回"原来的那条链路"
   → 而那条链路对应的会话已在另一侧，状态不匹配 → 丢弃
③ 根因：End.AS 的恢复封装是"配置写死"的，无法表达"从哪条链来就回哪条"
④ 修复：改为 End.AD（按内层流键缓存），或让两条链路各配一个 End.AS
   并在链路上做严格区分（成本高、易错）
⑤ 结论：End.AS 只适合"单入单出"的固定拓扑
```

**教训**：**"省内存"的代价是"拓扑刚性"**。选 End.AS 前必须回答：**这条路径未来会不会加链路、加节点、加策略？** 只要答案是"会"，就该直接上 End.AD。

### 案例 C：缓存溢出，每小时断几秒

**现象**：某清洗中心每小时出现 **2–5 秒的"业务抖动"**，监控显示设备与链路均正常。

```text
① 抖动时间点无规律，但都与"新建连接高峰"相关
② show segment-routing srv6 proxy state
   Flows = 262,100   HWM = 262,144   ← 正好在容量上限
③ 表满策略是"丢新流" → 新流建不起来 → 业务抖动
④ 根因：容量按"平均并发 15 万"规划，实际峰值 26 万（NAT 后放大）
⑤ 修复：
   a. 扩缓存容量（按峰值 × 1.5）
   b. 老化时间从 30 s 调到 90 s（减少无效重建）
   c. 加 HWM > 80% 告警
⑥ 复测：HWM 稳定在 55%，抖动消失
```

**教训**：**有状态代理的容量规划要按"峰值 × 1.5"，不是"平均"**；并且**必须监控 HWM（高水位）**——表满时它不会报错，只会静默丢流。

## 延伸阅读

- **RFC 8986 §8**：SR Proxy 的规范定义，`End.AS`、`End.AM`、`End.AD` 三种行为与处理流程。
- **RFC 8754**：SRH 格式，理解"剥掉什么、恢复什么"。
- **RFC 8200**：IPv6 扩展头处理规则，解释老设备为何会丢 `Next Header=43`。
- **draft-ietf-spring-sr-service-programming**：Service SID 与代理的组合方式。
- 交叉参考：第 11 章（服务编程，代理作为链中的一段）、第 12 章（SERA，保留元数据的替代方案）、第 16 章（Bell SP 生产链中如何取舍代理与 SR-aware）。
