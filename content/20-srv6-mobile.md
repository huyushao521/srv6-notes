# 20 · SRv6 承载 5G 用户面：End.MAP 与 GTP-U

> **本章定位**：补章。前 19 章讲的都是"网络自己用 SRv6"；这一章讲**网络替别人搬流量**——把 5G 移动用户面（GTP-U 隧道）整体搬到 SRv6 上。这是 SRv6 全球商用规模最大、也最容易被国内工程师低估的场景。原书主线（《Segment Routing Part III》）只在案例里一笔带过，本章按 RFC 9433（SRv6 for Mobile User Plane）补齐。
>
> 一句话概括：**GTP-U 的问题从来不是"隧道不够快"，而是"隧道太多、而且每一层都要建状态"**；SRv6 在这件事上的价值，是把"每个 UE 一条隧道"换成"每个路径一条 SID 列表"。

**本章要拿到的东西**：

| 问题 | 对应小节 |
|---|---|
| 5G 用户面到底有几层封装，为什么要减 | 20.1 |
| End.MAP 是什么，和 End.DT4 差在哪 | 20.3 |
| 下行为什么需要 `End.M.GTP6.D`，`.D.Di` 又是什么 | 20.4 |
| 上行 `End.M.GTP6.E` 与 `H.M.GTP4.D` 分别落在哪 | 20.5 |
| 一次完整的 UE 上线到上网，报文怎么走位 | 20.6 |
| 移动承载和切片、TE、EPC 演进怎么衔接 | 20.7 |

## 20.0 本章拓扑

```text
图 20-1：本章拓扑（5G SA 用户面，SRv6 传输网）

      UE                gNB                  UPF-A                 UPF-B / DN
       │                 │                      │                      │
       │── 空口 ─────────│                      │                      │
       │                 │── N3 (GTP-U) ───────>│                      │
       │                 │                      │── N9 (GTP-U) ───────>│── N6 ── 互联网
       │                 │                      │                      │
       └────── 传输网（SRv6）───────────────────┴──────────────────────┘

  SID 约定（沿用本站）：
    gNB 侧传输节点   fc00:0:11::/48
    UPF-A  locator    fc00:0:21::/48   End.MAP    fc00:0:21:e001::
                                       End.M.GTP6.D fc00:0:21:e101::
                                       End.M.GTP6.E fc00:0:21:e102::
    UPF-B  locator    fc00:0:22::/48   End.DT6    fc00:0:22:e002::
    DN 出口 BSID      fc00:0:21:d000::20

  一个 UE 的标识（示意）：
    UE IP        10.60.0.7
    gNB GTP-U TEID 0x0000a1b2
    UPF GTP-U TEID 0x0000c3d4
```

| 角色 | 需要的能力 | 不需要的 |
|---|---|---|
| gNB（N3 侧） | 能发 GTP-U；能压 SRv6 头（或用 SR Proxy 兼容） | 知道 UPF 的 SID |
| UPF-A | End.MAP、GTP6.D、GTP6.E 行为 | 逐 UE 的传输隧道 |
| 传输网 P 节点 | 纯 SRv6 转发 | 任何 GTP 认知 |
| 控制器 | UE 标识 → SID 映射表下发 | 转发面配置 |

## 20.1 移动承载为什么盯上了 SRv6

:::en
This document defines a new SRv6 network programming model for the mobile user plane. It enables the mobile user plane to be programmed by SRv6 SIDs, so that the GTP-U tunnels are no longer required on every transport node.
:::

RFC 9433 为移动用户面定义了一套新的 SRv6 网络编程模型，让用户面可以被 SRv6 SID 编程，从而使**传输节点不再需要处理 GTP-U 隧道**。

### 20.1.1 GTP-U 的封装税

一个 5G 下行包，在传输网上长这样：

```text
图 20-2：经典 GTP-U 的封装层次

  ┌───────────┬───────────┬──────────┬──────────────┬───────────┬──────────┐
  │ 传输 IP   │  UDP      │  GTP-U   │  内层 IP      │  UDP/TCP  │  载荷    │
  │ (IPv4/v6) │ 2152      │ TEID     │  (UE 的业务)  │           │          │
  └───────────┴───────────┴──────────┴──────────────┴───────────┴──────────┘
       20/40      8          8           20/40           8         ...
```

开销不是最关键的，关键是**三层状态**：

| 层 | 状态 | 谁维护 | 问题 |
|---|---|---|---|
| 传输层 | 每对 (gNB, UPF) 的 IP 路径 | 传输网 | 路径不可编程，只能靠 IGP 最短路 |
| GTP 层 | 每 UE 的 TEID | UPF / gNB | 用户数 × 每用户状态，扩容线性增长 |
| 业务层 | UE 的 IP 会话 | SMF | 与传输解耦不彻底 |

### 20.1.2 SRv6 换掉了什么

| 维度 | GTP-U over IP | GTP-U over SRv6 |
|---|---|---|
| 传输路径 | IGP 最短路 | 可指定（SR Policy，第 18 章） |
| 传输节点认知 | 需识别 UDP 2152 | 只看 IPv6 DA |
| 路径保护 | 靠 IGP 收敛（秒级） | TI-LFA（<50 ms）+ SBFD |
| 切片 | 靠 VLAN / 独立链路 | Flex-Algo + BSID（第 22 章） |
| TE | 几乎无法做 | 天然支持，可带宽预留 |

> 一句话：**SRv6 没让 GTP-U 消失，只是让"传输"和"隧道"解耦了**——传输网只搬 IPv6 包，GTP-U 的语义被压进 SID 里。

## 20.2 六个行为，一张表看完

RFC 9433 定义的移动用户面行为，全在这张表里：

| 行为 | 全称含义 | 用在哪 | 关键动作 |
|---|---|---|---|
| `End.MAP` | 按映射表做 SID 转换 | UPF 内部，UE 标识 → 远端 SID | 查表换 DA，不碰载荷 |
| `End.M.GTP6.D` | 下行，GTP6 到 SRv6 | UPF-A 收到 N3 的 GTP-U 后转 SRv6 | 剥 GTP/UDP，压 SRH |
| `End.M.GTP6.D.Di` | 下行，中间节点形态 | 中间 UPF（不终结 GTP） | 改写 TEID 与 DA，**不重封装** |
| `End.M.GTP6.E` | 上行，SRv6 到 GTP6 | UPF 侧接 SRv6 转回 GTP-U | 压 GTP/UDP，出 N3 |
| `H.M.GTP4.D` | 下行，GTP4 到 SRv6（兼容 EPC） | 4G/5G 互操作 | 内层 IPv4 的 GTP-U 转 SRv6 |
| `End.M.GTP6.STD` | 静态形态 | 简单场景 / 测试 | 固定映射，不查表 |

两条判断口诀：

- **`.D` 结尾 = 进 SRv6 域**（往下走，Downlink），`.E` 结尾 = **出 SRv6 域**（往回走，Egress 到无线）。
- **带 `Di` = 中间节点形态**：它不终结 GTP，只改 TEID 与 SID 往下送，省掉"解封装再封装"。

## 20.3 End.MAP：一张"名字到位置"的表

:::en
The End.MAP behavior is used to map a SID to another SID according to a locally configured mapping table. The packet is not decapsulated.
:::

`End.MAP` 按本地映射表把一个 SID 换成另一个 SID，**报文不解封装**。

### 20.3.1 它解决的是"UE 动、锚点不变"

移动网里两个东西经常对不上：

- UE 的**会话锚点**（UPF）要保持不变（不然 IP 变了，业务断了）；
- UE 的**实际位置**一直在动（切换 gNB、切换 UPF）。

传统做法是把这层关系放在 GTP 的 TEID 里，靠 SMF 逐条改。`End.MAP` 的做法是把它变成一次**查表换 DA**：

```text
图 20-3：End.MAP 的一次执行

  进包： DA = fc00:0:21:e001::（End.MAP）  内层 = UE 的业务包
         SRH 里：Segment List[0] = 旧锚点 SID

  查表： fc00:0:21:e001:: + 内层信息 → fc00:0:22:e002::（新锚点）

  出包： DA = fc00:0:22:e002::
         载荷一个字节没动，没有解封装、没有重新压栈

  控制器改一行映射表 → 下一次转发立即生效
```

### 20.3.2 和 End.DT4/DT6 的区别

| 对比项 | End.DT4 / End.DT6（第 6 章） | End.MAP |
|---|---|---|
| 用途 | VPN 查表转发到 CE | 移动网锚点重定向 |
| 是否解封装 | 是（剥外层，按 VRF 查内层） | **否**（整包往下送） |
| 依赖表 | VRF 路由表 | 移动映射表（控制器下发） |
| 触发的业务 | L3VPN | 会话迁移、锚点变更、切片切换 |

> 混淆这两者是移动承载排障的第一号错误现象：**"UPF 收到了包，但内层没进去"**——那是 End.MAP 该做的事被配成了 End.DT6。

## 20.4 下行：End.M.GTP6.D 与 .D.Di

### 20.4.1 End.M.GTP6.D：把 GTP-U 换成 SRv6

:::en
The End.M.GTP6.D behavior is used to decapsulate the GTP-U packet and to encapsulate the payload into an SRv6 packet, using the SID list carried in the GTP-U extension header or derived from the TEID.
:::

`End.M.GTP6.D` 用于**剥掉 GTP-U 封装**，再把载荷装进 SRv6 报文；SID 列表可以来自 GTP-U 扩展头，也可以由 TEID 推导。

```text
图 20-4：下行封装转换（N3 → SRv6）

  进（来自 gNB）：
    IPv6(传输) / UDP(2152) / GTP-U(TEID=0xa1b2) / IPv6(UE 内层) / 业务
                │
                ▼  UPF-A 执行 End.M.GTP6.D
  出：
    IPv6(src=UPF-A, dst=fc00:0:22:e002::) / 业务
        （GTP 与 UDP 全部剥掉，载荷直通；需要多跳时加 SRH）
```

三个必须记住的点：

1. **不是"隧道套隧道"，是"剥掉一层"**。所以 SRv6 承载的移动包比 GTP-U over IP 更短，MTU 反而更宽松。
2. **TEID 变成"引子"**。有些实现直接从 TEID 推导目的 SID（`End.M.GTP6.STD`），有些从 GTP-U 扩展头里读显式 SID 列表（更灵活，支持按业务选路径）。
3. **SID 列表决定 QoS**。同一个 UPF 的不同 UE 可以走不同 SID 列表——这就是移动网做切片、做差异化 SLA 的抓手（20.7）。

### 20.4.2 End.M.GTP6.D.Di：中间节点不重封装

:::en
The End.M.GTP6.D.Di behavior is used at an intermediate UPF. It does not decapsulate the GTP-U packet; instead it updates the TEID and the Destination Address, then forwards the packet.
:::

`End.M.GTP6.D.Di` 用在**中间 UPF**：**不剥 GTP-U**，只更新 TEID 与 DA 就往下转。

这解决了 5G 里的一个现实问题：核心网有 I-UPF（中间）/ A-UPF（锚点）两级，UE 移动时只有 I-UPF 变，A-UPF 不变。如果每一级都"剥了再封"，代价是两次完整解析：

| 做法 | 每包动作 | 时延 | 实现复杂度 |
|---|---|---|---|
| 每级都终结 GTP（不用 Di） | 剥 GTP → 压 SRv6 → 到下一级再压回 GTP | 高 | 高 |
| 用 `.D.Di` | 改 TEID + 改 DA，载荷不动 | 低 | 低 |

```text
图 20-5：两级 UPF 的下行对比

  不用 Di：
    gNB ──GTP──> I-UPF ──SRv6──> A-UPF ──GTP──> DN
                  剥+压          剥+压       （两处封装转换）

  用 .D.Di：
    gNB ──GTP──> I-UPF ──(TEID/DA 改写)──> A-UPF ──GTP──> DN
                  End.M.GTP6.D.Di      只在一处转换
```

排障要点：`.D.Di` 节点上**看不到 GTP 层被终结**（没有会话表增长），如果按"会话数"监控 I-UPF，会误判为"没有承载流量"。

## 20.5 上行：End.M.GTP6.E 与 H.M.GTP4.D

### 20.5.1 End.M.GTP6.E：SRv6 转回 GTP-U

:::en
The End.M.GTP6.E behavior is used to encapsulate the SRv6 payload into a GTP-U packet, when the packet is sent toward the radio access network.
:::

`End.M.GTP6.E` 负责反向：把 SRv6 载荷重新装进 GTP-U，发往无线侧。

```text
图 20-6：上行封装转换（SRv6 → N3）

  进（来自 DN 或对端 UPF）：
    IPv6(dst = fc00:0:21:e102::) / IPv6(UE 内层) / 业务
                │
                ▼  UPF 执行 End.M.GTP6.E
  出：
    IPv6(传输) / UDP(2152) / GTP-U(TEID=0xa1b2) / IPv6(UE 内层) / 业务
```

关键：**TEID 从哪来**。三种来源，配置要对上：

| 来源 | 配置方式 | 适用 |
|---|---|---|
| SID 携带 | 上行 SID 里编入 TEID（SID 结构中的 Arg 字段） | 主流，推荐 |
| 本地表 | 按 UE 地址查表 | 兼容老 gNB |
| 静态映射 | `End.M.GTP6.STD` | 测试、固定场景 |

### 20.5.2 H.M.GTP4.D：4G 兼容的那一个

:::en
The H.M.GTP4.D behavior is used when the GTP-U payload carries an IPv4 packet, so that the packet can be forwarded into an SRv6 domain without changing the inner IPv4 header.
:::

`H.M.GTP4.D` 用于**内层是 IPv4 的 GTP-U** 转入 SRv6 域，且**不改动内层 IPv4 头**。典型场景是 EPC/5GC 互操作，或存量 4G 基站接入。

| 场景 | 用哪个行为 |
|---|---|
| 5G gNB（IPv6 内层）下行 | `End.M.GTP6.D` |
| 5G gNB 上行 | `End.M.GTP6.E` |
| 4G eNB / 双连接 下行 | `H.M.GTP4.D` |
| 中间 UPF | `End.M.GTP6.D.Di` |
| 固定映射（测试） | `End.M.GTP6.STD` |

**注意命名里的 6 和 4 指内层 IP 版本，不是传输网版本**。传输网永远是 IPv6（SRv6 的前提）。这一点搞错，配置会全盘错位。

## 20.6 一次完整走位：从 UE 上线到上网

```text
图 20-7：UL/DL 全景（七步）

  UE            gNB           I-UPF          A-UPF            DN
   │             │              │              │               │
   │ 1. PDU 会话建立（SMF 下发规则）             │               │
   │             │              │              │               │
   │ 2. UL ─────>│              │              │               │
   │             │── GTP-U ────>│              │               │
   │             │  TEID=0xa1b2 │              │               │
   │             │              │ 3. .D.Di 改 TEID/DA ─────────>│
   │             │              │              │ 4. End.MAP    │
   │             │              │              │    → 锚点 SID │
   │             │              │              │ 5. 出 N6 ────>│
   │             │              │              │               │
   │             │              │ 6. DL: 锚点 → End.M.GTP6.E    │
   │             │<── GTP-U ────│              │<── 业务 ──────│
   │ 7. 收到业务 │              │              │               │
```

| 步 | 动作 | 责任网元 | 失败时的现象 |
|---|---|---|---|
| 1 | 会话建立、下发 SID 与映射 | SMF / 控制器 | UE 有 IP 但无法上网 |
| 2 | gNB 发 GTP-U | gNB | 上行 0 包，N3 无计数 |
| 3 | `.D.Di` 改 TEID/DA | I-UPF | 上行到 A-UPF 但 TEID 错，A-UPF 丢包 |
| 4 | `End.MAP` 锚点重定向 | A-UPF | 包在锚点绕圈或回不来 |
| 5 | 出 N6 到 DN | A-UPF | DN 侧无流量 |
| 6 | `End.M.GTP6.E` 回 GTP | A-UPF | 下行到 UPF 但 gNB 收不到 |
| 7 | UE 收包 | UE | 业务慢/断，但链路全通（查 QoS/SID 列表） |

> 一句话：**移动承载排障的优势是"每一步都有确定的责任网元"**——不像纯 IP 转发只能靠抓包对齐。把这张表做成 check list，比看十份设计文档有用。

## 20.7 和切片、TE、演进怎么衔接

### 20.7.1 切片：同一个 UPF，不同 SID 列表

移动网切片最实用的落地方式不是"独立设备"，而是**同一套物理网 + 不同 SID 列表**：

| 切片 | SID 列表选择 | 底层保障 |
|---|---|---|
| eMBB（大带宽） | 走大带宽路径 | Flex-Algo 排除小带宽链路（第 4 章） |
| URLLC（低时延） | 走最短时延路径 | Flex-Algo min-delay + 硬隔离队列 |
| mMTC（海量连接） | 走普通路径、低优先级 | 队列调度 + 限速 |

配置上就是"每个切片一个 SRv6 Policy，用 color 区分"（18.6.2），头端仍是同一个 UPF：

```text
segment-routing
 traffic-eng
  policies
   policy UPF-A-URLLC
    color 300 end-point ipv6 fc00:0:22::1
    candidate-paths
     preference 100
      constraints
       segments
        sid-algorithm 130          ! min-delay 的 Flex-Algo
   policy UPF-A-EMBB
    color 330 end-point ipv6 fc00:0:22::1
    candidate-paths
     preference 100
      constraints
       segments
        sid-algorithm 128          ! min-cost
```

### 20.7.2 和 TE 的关系

移动承载对 TE 的需求和政企专线不一样：

| 需求 | 政企专线（第 18 章） | 移动承载 |
|---|---|---|
| 带宽保证 | 强（可预留） | 强，但按切片聚合，不按 UE |
| 时延 | 有 SLA 但粒度粗 | 严格，且要可测量（URLLC） |
| 路径稳定 | 越稳越好 | 允许频繁重算（UE 移动） |
| 收敛时间 | < 50 ms | < 100 ms 可接受，但**不能抖** |

**关键差异是"抖动"**：移动网的路径切换会引起 GTP 的 TEID 与序列号乱序，应用层（尤其 VoNR）对乱序极敏感。所以移动承载用 TE 时要额外开**有序转发/去抖**，不能只看收敛时间。

### 20.7.3 演进路径

```text
阶段 1：GTP-U over IP（现状）
   └─ 传输网纯 IP，UPF 之间靠路由

阶段 2：GTP-U over SRv6（本章）
   └─ 传输网 SRv6，UPF 承担 SID 行为；gNB 侧可先用 SR Proxy 兼容（第 13 章）

阶段 3：全 SRv6 用户面
   └─ gNB 直接发 SRv6（省掉 GTP 层），UPF 只做业务锚点
```

阶段 2 到 3 的坎不是协议，而是**基站**：存量 gNB 只认 GTP-U，所以阶段 2 会长期存在，`End.M.GTP6.*` 这组行为是必经之路。

## 20.8 本章小结

| 记住这一条 | 为什么 |
|---|---|
| SRv6 承载移动网是"剥一层"不是"套一层" | 所以 MTU 比 GTP-U over IP 更宽松 |
| `.D` 进 SRv6 域、`.E` 出 SRv6 域 | 记反了整条链路方向全错 |
| `Di` 是中间节点形态，不终结 GTP | 会话数监控会看不到流量 |
| `End.MAP` 只换 DA，不解封装 | 配成 End.DT6 就是"包到了但内层没进去" |
| 命名里的 4/6 指内层 IP 版本 | 传输网永远是 IPv6 |
| 切片落地 = 不同 color 的 SID 列表 | 不是独立设备 |

## 实战案例

### 案例 A：UE 能上网，但一切换基站就断

**现象**：单站覆盖下业务正常；UE 从 gNB-1 切到 gNB-2，业务中断 3–5 秒后恢复。

**排障分支**：

| 检查项 | 位置 | 期望值 | 实际值 |
|---|---|---|---|
| 切换后上行 TEID 是否更新 | I-UPF `.D.Di` 表 | 新 TEID | 仍为旧值 |
| 映射表版本 | 控制器 / UPF `End.MAP` 表 | 一致 | UPF 落后一个版本 |
| A-UPF 是否收到上行 | 接口计数 | 增长 | 不增长 |
| 锚点 SID 是否可达 | `ping fc00:0:22:e002::` | 通 | 通 |

**根因**：切换后 SMF 下发了新 TEID，但 `End.MAP` 的映射表由控制器异步推送，慢了一个周期；期间上行包被 `.D.Di` 按旧 TEID 改写，A-UPF 查不到会话直接丢。

**修复**：映射表推送改为**与切换信令同步**（或让 `.D.Di` 支持 TEID 通配回退），并加一条"表版本落后"告警。

### 案例 B：下行 0 包，UPF 侧一切正常

**现象**：UE 有 IP、能发上行（DN 能看到流量），下行完全收不到。

**期望值判定表**：

| 步 | 期望 | 常见错配 |
|---|---|---|
| DN → A-UPF | 有包 | 无：N6 路由缺失 |
| A-UPF 执行 `End.M.GTP6.E` | 生成 GTP-U，TEID 正确 | TEID 取自 SID Arg，Arg 位宽配错 → TEID 错 |
| A-UPF → gNB | N3 有计数 | 有计数但 gNB 丢弃（TEID 不匹配） |
| gNB → UE | 空口有调度 | 无：QoS flow 未建立 |

**根因**：上行 SID 的 SID 结构（Locator/Function/Arg 位宽）在头端与 UPF 两侧配置不一致，`End.M.GTP6.E` 从 Arg 里取出的 TEID 与 gNB 期望值差一位。

**教训**：**SID 结构（SID Structure）必须在全网一致**，这不是"建议"，是硬约束。18.2.2 的 SID Structure TLV 就是干这个用的——排障时先比对它。

### 案例 C：切片专线时延达标，但语音有杂音

**现象**：URLLC 切片时延 P99 达标（8 ms），但 VoNR 通话有断续。

**判据**：

| 指标 | 达标值 | 实测 | 结论 |
|---|---|---|---|
| 单向时延 P99 | < 10 ms | 8 ms | 达标 |
| 抖动 | < 1 ms | 0.6 ms | 达标 |
| 乱序率 | ≈ 0 | 0.4% | **不达标** |
| 路径切换次数/小时 | < 5 | 42 | **不达标** |

**根因**：Flex-Algo min-delay 在两条等时延链路间反复优选，每次切换造成乱序；语音对乱序的容忍度远低于时延。

**修复**：给候选路径加**粘性（sticky）**，度量差异在阈值内不重算；同时开有序转发。**结论：移动承载优化"稳定性"优先于"最优性"。**

## 延伸阅读

- RFC 9433：Segment Routing over IPv6 for the Mobile User Plane（End.MAP、End.M.GTP6.D/.D.Di/.E、H.M.GTP4.D）
- RFC 8754 / RFC 8986：SRH 与 SRv6 行为基础（第 2 章）
- RFC 9256：SR Policy 与候选路径（第 18 章）
- RFC 9350：IGP Flexible Algorithm（第 4 章、第 22 章）
- 交叉章节：第 4 章（Flex-Algo 切片）、第 6 章（End.DT 与 VRF）、第 13 章（用 SR Proxy 兼容存量基站）、第 18 章（SR Policy 与 color）、第 22 章（切片与确定性）