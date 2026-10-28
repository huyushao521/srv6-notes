# 15 · 案例：阿里巴巴核心网 SRv6 设计

> 对应原书第 15 章，与阿里核心网团队合作撰写。如果说 Bell 案例教你**地址怎么分**，阿里案例教你**业务怎么编排**：双 Block、Anycast、两级 TE、WLIB。

## 15.1 设计目标：服务化核心网

:::en
Alibaba's architectural goal is to make the newly built core network service-oriented. Two keywords drive the design: network slicing and endpoint-network synergy, both based on SRv6. Different virtual slices are created inside the core to meet SLA requirements on latency and bandwidth, and each transmission service is bound to a slice.
:::

阿里的目标是把新建核心网做成**服务化**的，两个关键词都以 SRv6 为基础：

- **网络切片**：核心内建多张虚拟切片，满足不同的时延/带宽 SLA，每种传输业务绑定到某张切片。
- **端网协同**（endpoint-network synergy）：把"选哪条路"的权利交给更懂业务的端点。

:::en
Endpoints — switches, VXLAN gateways, Linux hosts or containers — use a one-way IP-in-IPv6 tunnel to access a slice. The tunnel destination is a routable address in the access network, which is normally a plain dual-stack network without SRv6 support, while on the edge device the same address has the semantics of an End.DT46 SID associated with a VRF.
:::

**端点**（交换机、VXLAN 网关、Linux 主机、容器）用一条**单向 IP-in-IPv6 隧道**接入切片。巧妙之处在于：这个隧道目的地址在接入网里就是一个**可路由的普通地址**（接入网是纯双栈、完全不支持 SRv6），而在边缘设备上它同时是**绑定某个 VRF 的 End.DT46 SID**。一个地址，两种语义，接入网无需任何改造。

## 15.2 网络结构

:::en
Edge clusters provide a UNI facing the DC and an NNI facing the core network. All edge nodes in a cluster are assigned the same SRv6 anycast locator, known as the UNI anycast locator, in addition to the unique locator of each node. The network offers three classes of service to the DC, represented by three VRFs, each with an explicit per-VRF End.DT46 SID allocated from the UNI anycast block.
:::

- 边缘集群同时提供面向 DC 的 **UNI** 与面向核心的 **NNI**。
- 集群内**所有边缘节点共享同一个 anycast locator**（UNI anycast），每个节点另有自己的唯一 locator。
- 对 DC 提供三档服务（金/银/铜），对应三个 VRF；每个 VRF 从 anycast Block 里分配一个 **per-VRF 的 End.DT46 SID**，在集群内所有节点上**配置同一份**。

于是 DC 侧网关只需把报文封装到"对应等级的 anycast End.DT46 SID"，边缘集群就会**逐流负载分担**到任意一台成员，不需要 DC 侧知道有几台边缘。

:::en
The anycast design carries a known risk: if one member of the edge cluster fails to receive a prefix from the DC, it still advertises the anycast End.DT46 SIDs for the three VRFs, and traffic for that prefix may be steered to it and dropped. Alibaba mitigates this by additionally advertising the service prefixes as unicast routes with a unicast nexthop and the End.DT46 SID of the primary VRF, and leaking them between VRFs on the receiving edge node.
:::

Anycast 的风险书中写得很直白：**集群内某台成员没收到 DC 的某个前缀，但它仍然通告 anycast SID**，于是发往该前缀的流量被引到它身上并被丢弃。阿里的缓解办法：额外用**单播 nexthop + VRF0 的 End.DT46 SID** 通告业务前缀，并在接收侧边缘节点上做 VRF 间泄露——用单播路由压制 anycast 的"盲目吸引"。

## 15.3 核心内传输：两级引流

:::en
The core consists of several independent planes for redundancy and scalability. BGP is the routing protocol: single-hop eBGP between edge and core, iBGP inside the core. SRv6 uN and uA SIDs are explicitly allocated and configured, and are not advertised in the IGP; IS-IS only provides loopback reachability for the iBGP sessions.
:::

核心由多个**独立平面**组成（冗余 + 扩展性）。协议是 BGP：边缘↔核心 eBGP 单跳，核心内 iBGP。注意一个非常"阿里"的选择：**uN/uA SID 显式分配并配置，但不在 IGP 里通告**；IS-IS 只负责 Loopback 可达性，用于建 iBGP 会话。

:::en
Two levels of traffic steering are used. At the first level, edge nodes steer traffic to one or several planes in the core, using weighted ECMP when multiple planes are used. At the second level, core nodes steer the traffic inside the plane along the path that provides the required characteristics, using SR policies installed by an SDN controller with explicit SID lists.
:::

两级引流：

| 级别 | 在哪做 | 手段 | SID 列表长度 |
|---|---|---|---|
| 第一级 | 边缘节点 | SR Policy（每平面一条候选路径）+ 加权 ECMP | 2 条：`<uA 进平面> , <远端集群 anycast uN>` |
| 第二级 | 入口侧核心节点 | SR Policy（显式列表） | 平面内路径 |

:::en
The first level policies are instantiated on demand, only when the default load balancing across planes must be overridden for some reason. The second level resolves most of the TE problems on its own. Since the number of core nodes is much smaller than the number of edge nodes, this two-level design greatly reduces the number of SR policies to maintain.
:::

第一级策略**按需实例化**（默认就靠 anycast + ECMP 跨平面分担，只有需要覆盖默认行为时才下发）；第二级自己解决大部分 TE 问题。因为核心节点数远少于边缘节点数，这个设计把需要维护的 SR Policy 数量压下来——**这是全书里最值得抄的一个架构决策**。

:::en
The second level works by advertising the anycast End.DT46 SIDs as IPv6 transport routes with a /80 prefix into the core, using BGP and carrying the color extended community of the class of service. The core node attached to the ingress edge installs this route and steers it into an SR policy using BGP automated steering.
:::

第二级的实现有点"绕"但很巧：

1. 出口边缘把各 VRF 的 anycast End.DT46 SID **当作 IPv6 传输路由**（/80）用 BGP 通告进核心，并带**表示服务等级的 color 扩展团体**。
2. 与出口相连的核心节点把它重通告进 iBGP，并把自己设为 nexthop。
3. 与入口相连的核心节点安装该路由，用 **BGP 自动引流（Automated Steering）**把它导入一条指向"出口侧核心节点"的 SR Policy。

于是"服务等级"这一语义，从 DC 侧的封装一路传到了核心内的路径选择。

## 15.4 地址结构：为什么用 WLIB

:::en
Alibaba uses only algorithm 0 locators and does not use Flex-Algo. They wanted to encode both the TE class and the tenant ID inside the local SID structure, so they adopted the Wide Local Identifier Block (WLIB) for local SID allocation. The choice was driven by the desired SID structure, not by scaling requirements.
:::

阿里**只用 Algo 0，不用 Flex-Algo**（TE 全交给 SR Policy）。他们希望把 **TE class 与 tenant ID 编进本地 SID 结构**，于是采用 **WLIB（32 bit 本地 uSID）**——注意：**动机是"想要这个结构"，不是"地址不够用"**。

```text
PPPP:PPBB:SSSN:FFFF:EEEE::/80
  │      │    │    │    └─ 32 bit 本地标识（服务/租户等）
  │      │    │    └────── 32 bit WLIB Function
  │      │    └─────────── 16 bit uSID
  │      └──────────────── Block（UNI=00，NNI=01）
  └─────────────────────── SRv6 Space（fd00:cc）
```

:::en
The SRv6 space is fd00:cc, the block ID is 00 for the UNI block and 01 for the NNI block. Because the addressing structure carries service semantics, the network can express tenant and TE class without any additional signaling, and the forwarding hardware only needs a single lookup.
:::

Space 用 `fd00:cc`，UNI Block ID = `00`，NNI Block ID = `01`。因为地址结构自带业务语义，网络**不需要任何额外信令**就能表达"租户 + 服务等级"，硬件也只需一次查表。

## 实战案例：为什么"不把 SID 放进 IGP"是对的

**背景**：大多数运营商把 locator 放 IGP 通告，靠 IGP 算最短路。阿里反其道：SID 显式配置、不进 IGP，IS-IS 只管 Loopback。

**三个理由（可迁移到你自己的设计）**：

1. **规模**：核心节点数远少于边缘，IGP 里只需要 Loopback 前缀，SID 表由控制器/配置保证一致，IGP 负担最小。
2. **可控**：路径由 SR Policy 决定，不受 IGP 度量变化影响，TE 意图稳定。
3. **解耦**：SID 规划与 IGP 拓扑解耦，改地址不动协议、改拓扑不动地址。

**代价**：失去 IGP 自动收敛带来的保护，必须自己做**一致性校验**（谁配置错了 SID，网络不会自动纠正，只会静默不通）。这类网络必须配套：

| 配套 | 作用 |
|---|---|
| SID 台账/自动生成 | 防人工配错 |
| 端到端探测（第 9 章） | 主动发现 SID 不可达 |
| 控制器下发 + 校验 | 保证全网 SID 语义一致 |

## 本章小结

1. 双 Block（UNI/NNI）+ Anycast locator，让 DC 侧对边缘集群"无感知"。
2. 两级 TE：边缘选平面、核心选路径，策略数量被压到最少。
3. Anycast 有黑洞风险，用单播路由 + VRF 泄露压制。
4. WLIB 的动机是"结构表达业务语义"，不是地址不够。
5. SID 不进 IGP 换取可控性，代价是必须自建一致性与探测体系。
