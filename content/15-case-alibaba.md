# 15 · 案例：阿里巴巴核心网 SRv6 设计

> **本章定位**：原书第 15 章，与阿里核心网团队合作撰写。如果说 Bell 案例教你**地址怎么分**，阿里案例教你**业务怎么编排**：双 Block、Anycast、两级 TE、WLIB。英文块为原文摘录，中文为完整翻译，Figure 15.1–15.5 重绘。

**本章要拿到的东西**：

| 问题 | 对应小节 |
|---|---|
| "服务化核心网"落到配置上是什么 | 15.1 |
| 一个地址怎么同时是"普通路由"和"VRF SID" | 15.1.1 |
| 为什么边缘集群用 anycast，风险在哪、怎么压 | 15.2 |
| 两级 TE 为什么能把策略数量压到最少 | 15.3 |
| 为什么只用 Algo 0，不用 Flex-Algo | 15.4 |
| WLIB 的动机是"结构"还是"容量" | 15.4.1 |
| SID 不进 IGP，凭什么可控 | 15.5 |

一句话概括：**Bell 用地址的"层"换规模，阿里用地址的"位"换语义**——把 TE class 和 tenant ID **直接编进 SID 结构**，于是网络不需要任何额外信令就知道"这是谁的流量、要什么等级"。

## 15.0 三条主线

| 主线 | 做法 | 解决的问题 |
|---|---|---|
| **切片化** | 核心内建多张虚拟切片，业务绑定切片 | 时延/带宽 SLA 差异化 |
| **端网协同** | 端点自己决定进哪个切片 | 网络不需要猜业务意图 |
| **语义进地址** | TE class + tenant ID 编进 SID | 免信令、单次查表 |

## 15.1 设计目标：服务化核心网

:::en
Alibaba's architectural goal is to make the newly built core network service-oriented. Two keywords drive the design: network slicing and endpoint-network synergy, both based on SRv6. Different virtual slices are created inside the core to meet SLA requirements on latency and bandwidth, and each transmission service is bound to a slice.
:::

阿里的目标是把新建核心网做成**服务化**的，两个关键词都以 SRv6 为基础：

- **网络切片**：核心内建**多张虚拟切片**，满足不同的**时延/带宽 SLA**，每种传输业务**绑定到某张切片**；
- **端网协同（endpoint-network synergy）**：把"**选哪条路**"的权利**交给更懂业务的端点**。

:::en
Endpoints — switches, VXLAN gateways, Linux hosts or containers — use a one-way IP-in-IPv6 tunnel to access a slice. The tunnel destination is a routable address in the access network, which is normally a plain dual-stack network without SRv6 support, while on the edge device the same address has the semantics of an End.DT46 SID associated with a VRF.
:::

**端点**（交换机、VXLAN 网关、Linux 主机、容器）用一条**单向 IP-in-IPv6 隧道**接入切片。巧妙之处在于：这个**隧道目的地址**——

- 在**接入网**里就是**一个可路由的普通地址**（接入网是**纯双栈、完全不支持 SRv6**）；
- 在**边缘设备**上，**同一个地址**同时是**绑定某个 VRF 的 `End.DT46` SID**。

**一个地址，两种语义，接入网无需任何改造。**

### 15.1.1 一个地址的两种"读法"

```text
图 15-1：端网协同的封装（原书 Figure 15.1 重绘）

  端点（host/容器/VXLAN GW）
     │  ① 自己做一次 IP-in-IPv6 封装
     │     DA = 切片对应的 anycast End.DT46 SID
     ▼
  ┌──────────────────────────────────────────────┐
  │ 接入网（纯双栈，不支持 SRv6）                  │
  │  只看 IPv6 头 → 按普通路由转发到边缘集群       │
  │  （它不知道这是个 SID，也不需要知道）           │
  └──────────────────────────────────────────────┘
     │
     ▼
  边缘设备：DA 命中本地 End.DT46 → 查 VRF → 按服务等级转发进核心

  关键：封装在【端点】完成，接入网零改造，语义在【边缘】生效
```

| 视角 | 看到的是什么 | 需要什么能力 |
|---|---|---|
| 端点 | 一个"隧道目的地址" | 会做 IP-in-IPv6（Linux 原生即可） |
| 接入网 | 一个普通 IPv6 目的地 | **零 SRv6 能力** |
| 边缘设备 | 一个 `End.DT46` SID（绑定 VRF） | 标准 SRv6 |
| 核心 | 一个 anycast uN（含 TE class） | 标准 SRv6 + SR Policy |

这个设计把"**端网协同**"落到了最朴素的地方：**端点只要会封装，网络就会按它选的地址办事**。业务意图不需要通过控制器翻译、不需要 ACL 分类，**写在 DA 里就够了**。

## 15.2 网络结构：UNI / NNI 与 Anycast

:::en
Edge clusters provide a UNI facing the DC and an NNI facing the core network. All edge nodes in a cluster are assigned the same SRv6 anycast locator, known as the UNI anycast locator, in addition to the unique locator of each node. The network offers three classes of service to the DC, represented by three VRFs, each with an explicit per-VRF End.DT46 SID allocated from the UNI anycast block.
:::

- 边缘集群同时提供面向 DC 的 **UNI** 与面向核心的 **NNI**；
- 集群内**所有边缘节点共享同一个 anycast locator**（**UNI anycast**），每个节点**另有自己的唯一 locator**；
- 对 DC 提供**三档服务（金/银/铜）**，对应**三个 VRF**；每个 VRF 从 anycast Block 里分配一个 **per-VRF 的 `End.DT46` SID**，在**集群内所有节点上配置同一份**。

于是 DC 侧网关只需把报文封装到"**对应等级的 anycast `End.DT46` SID**"，边缘集群就会**逐流负载分担**到任意一台成员，**不需要 DC 侧知道有几台边缘**。

```text
图 15-2：双 Block 与 Anycast（原书 Figure 15.2 重绘）

  SRv6 Space: fd00:cc
  ├─ Block 00（UNI，面向 DC）      fd00:cc00::/32
  │    ├─ anycast locator（集群共享）
  │    │    ├─ per-VRF SID 金  fd00:cc00:0100:0001::
  │    │    ├─ per-VRF SID 银  fd00:cc00:0100:0002::
  │    │    └─ per-VRF SID 铜  fd00:cc00:0100:0003::
  │    └─ 各成员唯一 locator（用于管理/单播）
  │
  └─ Block 01（NNI，面向核心）     fd00:cc01::/32
       ├─ uN（每台核心节点）
       └─ uA（每条链路）

  DC ──[DA=金级 anycast SID]──► 边缘集群（N 台，ECMP 任意一台）
```

| 设计点 | 好处 | 代价 |
|---|---|---|
| per-VRF SID 全集群统一配置 | DC 侧对边缘规模**完全无感** | 配置必须**严格一致**（不一致即黑洞） |
| anycast locator | 逐流负载分担，扩容**无需通知 DC** | 需要额外机制防黑洞（15.2.1） |
| 双 Block（UNI/NNI） | 内/外流量语义分离，便于策略与汇总 | 地址规划要预留两个 /32 |

### 15.2.1 Anycast 的黑洞风险与压制

:::en
The anycast design carries a known risk: if one member of the edge cluster fails to receive a prefix from the DC, it still advertises the anycast End.DT46 SIDs for the three VRFs, and traffic for that prefix may be steered to it and dropped. Alibaba mitigates this by additionally advertising the service prefixes as unicast routes with a unicast nexthop and the End.DT46 SID of the primary VRF, and leaking them between VRFs on the receiving edge node.
:::

**Anycast 的风险书中写得很直白**：集群内**某台成员没收到 DC 的某个前缀**，但它**仍然通告 anycast SID**，于是**发往该前缀的流量被引到它身上并被丢弃**。

阿里的缓解办法：**额外用"单播 nexthop + 主 VRF 的 `End.DT46` SID"通告业务前缀**，并在接收侧**边缘节点上做 VRF 间泄露**——**用单播路由压制 anycast 的"盲目吸引"**。

```text
图 15-3：anycast 吸引 vs 单播压制（原书 Figure 15.3 重绘）

  出问题的情况:
    DC ──[DA=anycast SID]──► 边缘集群
                               ├─ 成员 A：有该前缀 ✔
                               └─ 成员 B：没收到该前缀 ✘ → 丢包
        （ECMP 把一半流量分给 B，一半业务黑洞）

  压制后:
    成员 B 额外通告："该前缀的真实下一跳 = 成员 A 的单播地址"
    → 核心/边缘按最长匹配优先选单播路径
    → 流量绕开 B，直达 A
    → anycast 仍承担"默认分担"，但异常前缀被单播"兜住"
```

| 机制 | 作用 | 何时生效 |
|---|---|---|
| anycast SID | 默认逐流分担 | 正常情况 |
| **单播前缀 + 主 VRF SID** | **兜住"某成员缺前缀"的异常** | 成员状态不一致时 |
| VRF 间泄露 | 让单播路由在接收侧可见 | 与上一条配合 |
| 一致性校验 | 提前发现成员配置/路由不一致 | 持续 |

:::en
The lesson generalizes: anycast gives scale and simplicity, but it removes the ability to know which member will serve a given flow, so any per-member state (a missing prefix, a stale route, a half-configured VRF) becomes a probabilistic black hole. The fix is always the same: provide a unicast path that overrides the anycast shortcut for the affected prefix.
:::

这个教训可以推广：**anycast 带来规模与简单，但也拿掉了"知道哪台成员会服务这条流"的能力**，于是**任何"成员级"的不一致**（缺前缀、旧路由、半配的 VRF）都会变成**概率性黑洞**。**解法永远是同一个：为受影响的前缀提供一条"能覆盖 anycast 捷径"的单播路径。**

## 15.3 两级引流：把策略数量压到最少

:::en
The core consists of several independent planes for redundancy and scalability. BGP is the routing protocol: single-hop eBGP between edge and core, iBGP inside the core. SRv6 uN and uA SIDs are explicitly allocated and configured, and are not advertised in the IGP; IS-IS only provides loopback reachability for the iBGP sessions.
:::

核心由**多个独立平面**组成（冗余 + 扩展性）。协议是 **BGP**：**边缘↔核心 eBGP 单跳，核心内 iBGP**。

一个非常"阿里"的选择：**uN/uA SID 显式分配并配置，但不在 IGP 里通告**；**IS-IS 只负责 Loopback 可达性**，用于建 iBGP 会话。

:::en
Two levels of traffic steering are used. At the first level, edge nodes steer traffic to one or several planes in the core, using weighted ECMP when multiple planes are used. At the second level, core nodes steer the traffic inside the plane along the path that provides the required characteristics, using SR policies installed by an SDN controller with explicit SID lists.
:::

**两级引流**：

| 级别 | 在哪做 | 手段 | SID 列表长度 |
|---|---|---|---|
| **第一级** | 边缘节点 | SR Policy（每平面一条候选路径）+ **加权 ECMP** | **2 条**：`<uA 进平面>` , `<远端集群 anycast uN>` |
| **第二级** | 入口侧核心节点 | SR Policy（**显式列表**） | 平面内路径（按需长） |

```text
图 15-4：两级引流（原书 Figure 15.4 重绘）

  端点 ──► 边缘 ──┬─ 平面 1 ──► 核心节点 X ──┐
                  │   （加权 60%）           │
                  ├─ 平面 2 ──► 核心节点 Y ──┼──► 边缘集群（anycast）
                  │   （加权 30%）           │
                  └─ 平面 3 ──► 核心节点 Z ──┘
                     （加权 10%）             ▲
                                             │
        第一级：边缘选平面（策略很少，按需下发）  │
        第二级：核心节点内选路径（显式列表，SDN 下发）
```

:::en
The first level policies are instantiated on demand, only when the default load balancing across planes must be overridden for some reason. The second level resolves most of the TE problems on its own. Since the number of core nodes is much smaller than the number of edge nodes, this two-level design greatly reduces the number of SR policies to maintain.
:::

**第一级策略按需实例化**——默认**就靠 anycast + ECMP 跨平面分担**，**只有需要覆盖默认行为时才下发**；**第二级自己解决大部分 TE 问题**。因为**核心节点数远少于边缘节点数**，这个设计把**需要维护的 SR Policy 数量压下来**——**这是全书里最值得抄的一个架构决策**。

策略数量的账：

| 方案 | 策略数量 | 变更影响 | 收敛 |
|---|---|---|---|
| 单级（边缘直接下全路径） | 边缘数 × 业务数（**万级**） | 一条路径变动 → 改所有边缘 | 慢 |
| **两级（本案例）** | 边缘数 × 平面数（**百级**）+ 核心节点数 × 需求（**十级**） | 平面内变更只改核心 | **快** |
| 纯控制器下发（无 BGP） | 不受 BGP 规模限制 | 控制器是关键依赖 | 取决于控制器 |

### 15.3.1 第二级的具体做法：把"服务等级"传进核心

:::en
The second level works by advertising the anycast End.DT46 SIDs as IPv6 transport routes with a /80 prefix into the core, using BGP and carrying the color extended community of the class of service. The core node attached to the ingress edge installs this route and steers it into an SR policy using BGP automated steering.
:::

第二级的实现有点"绕"但很巧：

1. **出口边缘**把各 VRF 的 **anycast `End.DT46` SID 当作 IPv6 传输路由（`/80`）**用 BGP 通告进核心，并带**表示服务等级的 color 扩展团体**；
2. 与出口相连的**核心节点**把它重通告进 iBGP，并**把自己设为 nexthop**；
3. 与入口相连的**核心节点**安装该路由，用 **BGP 自动引流（Automated Steering）**把它导入一条**指向"出口侧核心节点"的 SR Policy**。

于是"**服务等级**"这一语义，**从 DC 侧的封装一路传到了核心内的路径选择**。

```text
例 15.1：第二级的路径传递
① DC → 边缘：DA = fd00:cc00:0100:0001::（金级 anycast End.DT46）
② 出口边缘 → 核心：BGP 通告 fd00:cc00:0100:0001::/80
                   color = 金级（如 color 10）
③ 出口核心节点 → iBGP：重通告，next-hop = 自己
④ 入口核心节点：安装 /80 路由 → 按 color 自动匹配 SR Policy
                → 沿显式列表（低时延路径）转发
⑤ 结果：一个"金级"标记，既决定了 VRF，也决定了核心路径
```

| 传递环节 | 携带的语义 | 载体 |
|---|---|---|
| 端点 → 边缘 | 服务等级 | DA 里的 per-VRF SID |
| 边缘 → 核心 | 服务等级 | `/80` 路由 + color 扩展团体 |
| 核心内部 | 路径要求 | SR Policy + 显式 SID 列表 |
| 出口 → DC | 已落地 | VRF 查表 |

## 15.4 地址结构：WLIB 与"语义进地址"

:::en
Alibaba uses only algorithm 0 locators and does not use Flex-Algo. They wanted to encode both the TE class and the tenant ID inside the local SID structure, so they adopted the Wide Local Identifier Block (WLIB) for local SID allocation. The choice was driven by the desired SID structure, not by scaling requirements.
:::

阿里**只用 Algo 0，不用 Flex-Algo**（TE 全交给 SR Policy）。他们希望把 **TE class 与 tenant ID 编进本地 SID 结构**，于是采用 **WLIB（32 bit 本地 uSID）**——注意：**动机是"想要这个结构"，不是"地址不够用"**。

```text
图 15-5：阿里的 SID 结构（原书 Figure 15.5 重绘）

  fd00:cc00:0001:0100:0a01:0002:0000:0000
  └──┬──┘ └┬─┘ └┬─┘ └┬─┘ └───┬───┘
   Space  Block  uN   Func   WLIB（32 bit 本地标识）
   fd00:cc  00    0001 0100   0a01:0002
                              └─┬─┘ └─┬┘
                          TE class  tenant ID

  对比标准 uSID（16 bit function）：
    只能表达"哪个行为"，无法表达"哪类业务 + 哪个租户"
  WLIB（32 bit function）：
    一次查表同时得到 行为 + 服务等级 + 租户
```

:::en
The SRv6 space is fd00:cc, the block ID is 00 for the UNI block and 01 for the NNI block. Because the addressing structure carries service semantics, the network can express tenant and TE class without any additional signaling, and the forwarding hardware only needs a single lookup.
:::

Space 用 `fd00:cc`，**UNI Block ID = `00`**，**NNI Block ID = `01`**。因为**地址结构自带业务语义**，网络**不需要任何额外信令**就能表达"**租户 + 服务等级**"，硬件也**只需一次查表**。

### 15.4.1 为什么不用 Flex-Algo，而用 WLIB

| 方案 | TE 语义怎么表达 | 需要什么 | 阿里的判断 |
|---|---|---|---|
| Flex-Algo | 算法号（128 低时延 / 129 绕行） | IGP 内定义约束 + 每算法一个 Block | **粒度粗**（只能表达"低时延"，不能表达"租户"） |
| **WLIB + SR Policy** | **编进 SID 的 32 bit** | 控制器下发策略 | **粒度细、可组合** |
| 元数据 TLV | SRH 里带 TLV | 需 SR-aware 设备 | 开销大、易丢（第 12 章） |

:::en
The choice of WLIB over Flex-Algo reflects a different philosophy: Flex-Algo encodes the path constraint in the IGP and lets the IGP compute, while WLIB encodes the service identity in the address and lets the controller decide the path. Alibaba wanted the second, because the TE class and tenant are service attributes, not topology attributes.
:::

**选 WLIB 而不是 Flex-Algo，反映的是两种哲学**：

- **Flex-Algo 把"路径约束"编进 IGP**，让 **IGP 去算**；
- **WLIB 把"服务身份"编进地址**，让**控制器去定路径**。

阿里要的是后者，**因为 TE class 与 tenant 是"业务属性"，不是"拓扑属性"**。用拓扑机制表达业务属性，**必然要么粒度不够、要么组合不了**。

| 维度 | Flex-Algo | WLIB |
|---|---|---|
| 表达力 | 路径约束（时延/绕行/带宽） | **业务身份 + 路径约束** |
| 组合能力 | 算法之间互斥 | **可与任意 SR Policy 组合** |
| 变更成本 | 改 IGP 定义 + 全网重算 | **改策略** |
| 硬件要求 | 支持多算法 FIB | **支持 32 bit 本地 uSID** |
| 地址消耗 | 每算法一个 Block | **一个 Block 内解决** |

## 15.5 不把 SID 放进 IGP：三个理由与一个代价

**背景**：大多数运营商把 locator 放 IGP 通告，靠 IGP 算最短路。**阿里反其道：SID 显式配置、不进 IGP，IS-IS 只管 Loopback。**

:::en
Keeping the uN and uA SIDs out of the IGP is a deliberate choice: it removes the SID allocation from the topology convergence path, so a topology change never reallocates or re-advertises a SID. The cost is that the network loses the automatic detection that IGP flooding would otherwise provide, and must therefore validate SID consistency by other means.
:::

**把 uN/uA 排除在 IGP 之外是刻意的**：它**把 SID 分配从拓扑收敛路径上摘掉**，于是**拓扑变化永远不会触发 SID 的重新分配或重通告**。**代价是失去了 IGP 泛洪带来的自动发现能力**，因此**必须用别的手段校验 SID 一致性**。

三个理由（可迁移到你自己的设计）：

| 理由 | 说明 |
|---|---|
| **规模** | 核心节点远少于边缘，IGP 里只需 Loopback 前缀，**IGP 负担最小** |
| **可控** | 路径由 SR Policy 决定，**不受 IGP 度量变化影响**，TE 意图稳定 |
| **解耦** | SID 规划与拓扑解耦：**改地址不动协议、改拓扑不动地址** |

**代价**：**失去 IGP 自动收敛带来的保护**，必须自己做**一致性校验**——**谁配置错了 SID，网络不会自动纠正，只会静默不通**。

| 配套 | 作用 | 缺了会怎样 |
|---|---|---|
| SID 台账 / 自动生成 | 防人工配错 | 新增节点 SID 冲突，静默黑洞 |
| 端到端探测（第 9 章） | 主动发现 SID 不可达 | 故障只能靠业务投诉发现 |
| 控制器下发 + 校验 | 保证全网 SID 语义一致 | 配置漂移无人察觉 |
| 变更评审 | 防止"顺手改个 SID" | 单点变更引发区域中断 |

## 15.6 本章小结

:::en
Alibaba's design shows a different center of gravity from Bell's: Bell optimizes the address plan for scale and summarization, while Alibaba optimizes the address structure for service semantics. Both use the same building blocks — uSIDs, anycast, SR policies — but arrange them around different goals.
:::

阿里与 Bell 的**重心不同**：**Bell 优化"地址规划的规模与汇总"，阿里优化"地址结构的业务语义"**。两者用**同一套积木**（uSID、anycast、SR Policy），但**围绕不同目标排列**。

| 维度 | Bell（第 14 章） | 阿里（本章） |
|---|---|---|
| 核心诉求 | 规模 + 汇总 | **业务语义 + 编排** |
| 地址层级 | Space→Block→Set→Node 四层 | Space→Block(UNI/NNI)→Node→**WLIB** |
| 算法 | Algo 0 + Flex-Algo 128/129 | **只用 Algo 0** |
| TE 手段 | Flex-Algo + 少量 SR Policy | **SR Policy 两级** |
| 汇总 | 按 Set `/40`（256:1） | 按 Block（UNI/NNI 分离） |
| IGP 里的 SID | locator 通告 | **SID 不进 IGP** |
| 可靠性机制 | UPA + TI-LFA | anycast + 单播压制 + 探测 |

一句话收束：**Bell 教你"把地址分对"，阿里教你"把语义放进地址"**。前者决定网络能长多大，后者决定网络能表达多细的业务。

## 实战案例

### 案例 A：为什么"不把 SID 放进 IGP"是对的（原书案例）

**背景**：大多数运营商把 locator 放 IGP 通告，靠 IGP 算最短路。阿里反其道：**SID 显式配置、不进 IGP**，IS-IS 只管 Loopback。

**三个理由**（见 15.5 表）：规模、可控、解耦。

**代价与配套**：

| 配套 | 作用 |
|---|---|
| SID 台账 / 自动生成 | 防人工配错 |
| 端到端探测（第 9 章） | 主动发现 SID 不可达 |
| 控制器下发 + 校验 | 保证全网 SID 语义一致 |

**反例（最常见的事故）**：某次扩容手配 uA SID 时**重复使用了一个已存在的值**，IGP 完全正常（因为 SID 不在 IGP 里），**只有经过该链路的部分业务不通**，且 `show` 命令一切正常——**这就是"用可控性换掉自动纠错"必须付出的运维代价**。

### 案例 B：anycast 黑洞的一次现场

**现象**：DC 侧到某金级 VRF 的业务"约一半新建连接失败"，失败率稳定在 50% 左右。

```text
① 边缘集群 4 台成员，anycast SID 全一致
② show bgp vrf GOLD <prefix> 在 4 台上逐一查看：
   3 台有该前缀，1 台（成员 D）没有
③ 原因：成员 D 与该 DC 的 BGP 会话异常（单向建立），
   但 anycast SID 仍照常通告 → ECMP 把 1/4 流量给它，全丢
④ 修复：
   a. 立即：修复 D 的 BGP 会话
   b. 加固：按 15.2.1 启用"单播前缀 + 主 VRF SID"通告，
      让缺前缀的成员自动被绕过
   c. 监控：加"成员间前缀数量差异"告警
⑤ 复测：人为断开一台成员的 BGP，业务无感（被单播路径兜住）
```

**教训**：**anycast 把"成员不一致"变成了"概率性丢包"**。**必须有机制把概率变成 0**——否则故障率永远是 `1/N`（N = 成员数），且随扩容"看起来"变小但**永远不消失**。

### 案例 C：WLIB 让"金级 + 租户 100"免于任何信令

**需求**：某租户的流量必须走金级切片，且核心需要按租户做独立计费与限速。

```text
方案对比:
① 用 ACL/分类器识别租户 → 每个入口配规则（万级配置）
② 用 Flex-Algo + QoS 组合 → 只能表达"等级"，租户要靠其他手段
③ 用 WLIB：SID 里直接编 TE class + tenant ID
   fd00:cc00:0001:0100:0a01:0002::
                        └─┬─┘ └─┬─┘
                     class=10  tenant=0x00020002

  核心节点一次查表即得：行为 + 等级 + 租户
  → 无需 ACL、无需额外信令、无需二次查表
```

**收益**：

| 项 | 传统方式 | WLIB |
|---|---|---|
| 租户识别 | ACL / 五元组（万级配置） | **SID 位段** |
| 配置下发 | 每入口设备 | **无**（地址即语义） |
| 查表次数 | 分类 + 查表（≥2 次） | **1 次** |
| 变更 | 全网改 ACL | **改地址分配** |

**启示**：**当"分类"是长期存在的需求时，把分类信息放进地址比放进 ACL 更省事**——ACL 会随业务增长而失控，地址位段不会。

## 延伸阅读

- **RFC 9256**：BGP SR Policy，第一/二级引流的策略载体。
- **RFC 9352 / Flex-Algo 相关**：Algo 0/128/129 的定义，理解"为什么阿里不用它"。
- **RFC 9343 / BGP over IPv6**：`/80` 传输路由的承载方式。
- **draft-ietf-spring-srv6-srh-compression**：uSID 与 Wide uSID（WLIB）的压缩编码。
- **RFC 8950**：IPv6 next-hop，15.1 的封装前提。
- 交叉参考：第 10 章（通用规划）、第 11 章（服务编程与 SR Policy）、第 14 章（Bell 的对照）、第 16 章（Bell SP 的生产链）。
