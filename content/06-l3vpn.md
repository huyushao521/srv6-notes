# 06 · SRv6 L3VPN：把 VPN 标签换成 SID

> **本章定位**：原书第 6 章《L3VPN》。本版按原书主题顺序**逐段对照**：灰色英文块是原文摘录（保留原句与术语），紧随其后的中文是该段的完整翻译，必要时补一段工程注解。书中的 Figure 6.1–6.5 按原文描述用 ASCII 重绘，图注标明来源。配置与命令输出来自原书 Example 6.1–6.6，按 IOS XR 风格保留。

**本章要拿到的东西**（原书章首列表）：

| 问题 | 对应小节 |
|---|---|
| SRv6 到底替掉了 MPLS L3VPN 里的什么 | 6.1、6.2 |
| `End.DT4/DT6/DT46` 与 `End.DX4/DX6` 怎么选，uSID 下叫什么 | 6.2 |
| 一台 PE 上几千个 VRF，SID 怎么分配才不炸 | 6.3 |
| SID 是怎么从出口 PE 传到入口 PE 的（不进 IGP） | 6.4 |
| 为什么 uSID 下 L3VPN 只需要一条指令、不压 SRH | 6.5 |
| 转置（transposition）什么时候用，代价是什么 | 6.6 |
| MTU 会怎么咬人 | 6.8 |

先记住一句话：**L3VPN 是 SRv6 唯一一个"什么都不用新做"的业务**——VPNv4/VPNv6 的 BGP 机制、RD/RT、路由反射器、BGP-free core 全部原样保留，唯一被替换的是"出口 PE 的 VPN 标签"换成了"出口 PE 的一个 SID"。所以这一章的重点不是新协议，而是**这个替换在状态、规模、封装、互通四个维度上换来了什么、又付出了什么**。

## 6.0 本章拓扑

```text
图 6-1：本章拓扑（原书 Figure 6.1 重绘）

   CE-1                        P-1               P-2                    CE-2
  10.1.1.0/24                                                     10.1.2.0/24
      │                            │                 │                  │
   ┌──┴───────────┐            ┌───┴───┐         ┌───┴───┐         ┌────┴─────────┐
   │   PE-1       │────────────│       │─────────│       │─────────│    PE-2      │
   │ VRF-100      │            └───────┘         └───────┘         │  VRF-100     │
   │ locator      │                                                │  locator     │
   │ fdbb:bb00:   │                                                │  fdbb:bb00:  │
   │   0001::/48  │                                                │    0002::/48 │
   └──────────────┘                                                └──────────────┘

   SID block：fdbb:bb00::/32（uSID 压缩编码，locator node 16 bit）
   P-1、P-2 只跑 IGP + locator 路由，无任何 VPN 状态 → BGP-free core
```

| 节点 | 角色 | locator | 本机 SID（示例） | 是否感知 VRF |
|---|---|---|---|---|
| PE-1 | 入口 PE | `fdbb:bb00:0001::/48` | `fdbb:bb00:0001:e000::`（uN） | 是（VRF-100） |
| PE-2 | 出口 PE | `fdbb:bb00:0002::/48` | `fdbb:bb00:0002:e001::`（uDT46，VRF-100） | 是（VRF-100） |
| P-1、P-2 | 核心 P | `fdbb:bb00:0009::/48` 等 | 只有 uN | **否** |
| CE-1/CE-2 | 客户 | 无 | 无 | 无 |

## 6.1 先回忆：MPLS L3VPN 的状态到底存在哪里

:::en
An L3VPN service is built from four components: a VRF that separates customer routing tables on the PE, a route distinguisher that makes the customer prefixes unique in BGP, a route target that controls import and export of the routes, and a VPN label that tells the egress PE which VRF the packet belongs to.
:::

L3VPN 由四个部件构成：**VRF**（在 PE 上隔离客户路由表）、**RD**（让客户前缀在 BGP 里唯一）、**RT**（控制路由的导入导出）、**VPN 标签**（告诉出口 PE 这个报文属于哪个 VRF）。

:::en
The VPN label is allocated by the egress PE, one per VRF, and is carried in the MP-BGP update together with the RD and the route target. Because the label is locally significant, the operator must plan label space on every PE, and the same VPN can be identified by a different label on every egress PE.
:::

VPN 标签由**出口 PE 分配，每个 VRF 一个**，随 RD 和 RT 一起放在 MP-BGP update 里。因为标签是**本地有效**的，运营商必须**在每台 PE 上规划标签空间**，而且**同一个 VPN 在不同的出口 PE 上标签可以完全不同**。

这是理解 SRv6 改动的关键对比点：

| 维度 | MPLS L3VPN 的 VPN 标签 | SRv6 的 SID |
|---|---|---|
| 谁分配 | 出口 PE，本地分配 | 出口 PE，但**全局唯一** |
| 作用域 | **本地有效**（同一 PE 内唯一即可） | **全局有效**（就是 IPv6 地址） |
| 需要规划什么 | SRGB / 标签池，防冲突 | locator 空间（第 10 章） |
| 报文里是什么 | 20 bit 标签（4 字节） | 128 bit IPv6 地址（16 字节） |
| 是否需要传输标签 | **需要**（外层 transport label 用来把包送到出口 PE） | **不需要**（locator 本身就是可路由前缀） |
| BGP 携带方式 | Label 字段（NLRI 内） | Prefix-SID 属性（RFC 9252） |

:::en
The key architectural consequence is that the transport label and the service label collapse into a single entity: the SRv6 SID is at the same time routable in the core and meaningful at the egress. There is no separate transport segment to distribute, and therefore no LDP, no SR-MPLS label stack, and no label binding protocol in the core.
:::

关键架构后果是：**传输标签与服务标签塌缩成同一个东西**——SRv6 的 SID **既能在核心被路由、又能在出口被理解**。既然不需要单独分发传输段，核心就**不需要 LDP、不需要 MPLS 标签栈、不需要标签绑定协议**。

一句话总结这一节：MPLS L3VPN 用**两个标签**（外层负责"送到哪台 PE"，内层负责"进哪个 VRF"）；SRv6 用**一个地址**同时承担这两件事。这是全章所有收益与代价的源头。

## 6.2 换成了什么：End.DT 行为族

:::en
In SRv6, the VPN service is expressed as an endpoint behavior. End.DT4 decapsulates the packet and performs an IPv4 lookup in the VRF identified by the SID; End.DT6 does the same for IPv6; End.DT46 selects the lookup table according to the inner header version and therefore serves a dual-stack VRF with a single SID.
:::

在 SRv6 里，VPN 服务被表达成**端点行为**。`End.DT4` 剥掉外层后按 **IPv4** 在 SID 所标识的 VRF 里查表；`End.DT6` 同样但针对 IPv6；`End.DT46` **按内层头版本**选择查哪张表，因此**一个 SID 就能服务双栈 VRF**。

:::en
End.DX4 and End.DX6 are a variant used when the egress PE is directly connected to the customer edge: the behavior strips the outer header and sends the packet out of a specific interface without consulting any VRF table. This is the natural choice for per-CE allocation, because the SID then identifies an attachment circuit rather than a VRF.
:::

`End.DX4`/`End.DX6` 是变体，用在**出口 PE 与 CE 直连**的场景：剥掉外层后从**指定接口**发出去，**完全不查 VRF 表**。这正是 **per-CE 分配**的自然选择——此时 SID 标识的是**一条接入电路**，而不是一个 VRF。

| 行为 | 行为码（RFC 8986） | 内层处理 | uSID 别名 | 典型用途 |
|---|---|---|---|---|
| `End.DX6` | 0x0010 | 从指定接口发出，不查表 | uDX6 | per-CE，IPv6 接入 |
| `End.DX4` | 0x0011 | 同上，IPv4 | uDX4 | per-CE，IPv4 接入 |
| `End.DT6` | 0x0012 | IPv6 查 VRF 表 | uDT6 | IPv6-only VPN |
| `End.DT4` | 0x0013 | IPv4 查 VRF 表 | uDT4 | IPv4-only VPN |
| `End.DT46` | 0x0014 | 按内层版本查表 | uDT46 | **双栈 VPN，最常用** |

:::en
Note that the packet is not encapsulated in a tunnel at the egress: the outer IPv6 header is simply removed, and the inner packet is routed natively. This is decapsulation-and-lookup, not tunnel termination in the traditional sense, which is why the behavior is called decapsulation and table lookup rather than VRF termination.
:::

注意出口侧**不是"隧道终结"**：外层 IPv6 头被**直接删掉**，内层报文按原生方式被路由。这是"**解封装 + 查表**"，不是传统意义上的隧道出口——这也是该行为被命名为 "decapsulation and table lookup（DT）" 而不是 "VRF termination" 的原因。

### 6.2.1 一个必须先纠正的常见误解：SRv6 的开销并不比 MPLS 小

:::en
It is tempting to conclude that SRv6 reduces the encapsulation overhead compared with MPLS. It does not. A single SRv6 SID is carried in a 40-byte IPv6 header, whereas an MPLS label stack of two labels occupies 8 bytes. What SRv6 removes is protocol and state overhead, not bytes.
:::

很容易顺势得出"SRv6 比 MPLS 封装更小"的结论——**这是错的**。一个 SRv6 SID 装在 **40 字节 IPv6 头**里，而 MPLS 两层标签只占 **8 字节**。SRv6 减掉的是**协议开销与状态开销，不是字节开销**。

把账算清楚（以承载一个 100 字节的客户报文为例）：

| 封装 | 外层开销 | 总长度 | 相对 MPLS |
|---|---|---|---|
| MPLS L3VPN（transport + VPN 两层标签） | 8 B | 108 B | 基准 |
| SRv6 常规（IPv6 头 + 无 SRH） | 40 B | 140 B | **+32 B** |
| SRv6 + SRH（2 段列表） | 40 B + 至少 8 B SRH + 16 B/段 | ≥ 180 B | **+72 B** |
| uSID 压缩（全部指令塞进 DA） | 40 B | 140 B | **+32 B** |

所以在带宽敏感场景（大流量城域网、视频回传）上，**SRv6 的每比特成本确实高于 MPLS**，这是必须承认的代价；它换来的是：

1. 核心不再需要标签分发协议（LDP/SR-MPLS），**协议栈简化**；
2. 没有 SRGB 规划、没有标签冲突排查，**运维简化**；
3. VPN 状态只存在于边缘，**P 路由器零 VPN 状态**；
4. 与 IPv6 生态（流量工程、OAM、安全）**天然对齐**。

:::en
The operator therefore trades a small increase in packet size for a large decrease in protocol and operational complexity. Where the average packet is small and the traffic volume is high, this trade-off must be evaluated explicitly rather than assumed away.
:::

也就是说，运营商是**用一点报文尺寸换掉大量协议与运维复杂度**。在"平均包小、流量大"的场景里，这个交换**必须显式计算**，不能想当然。

## 6.3 SID 分配：per-VRF 还是 per-CE

:::en
Two allocation models are common. With per-VRF allocation, one SID is allocated per VRF on the PE, and the behavior is End.DT46: the SID identifies the VRF, and the same SID serves all the attachment circuits of that VRF. With per-CE allocation, one SID is allocated per attachment circuit, with the behavior End.DX4 or End.DX6, so that the SID identifies the specific link through which the customer is reached.
:::

常见两种模型。**per-VRF**：PE 上**每个 VRF 一个 SID**，行为是 `End.DT46`——SID 标识 VRF，**同一个 VRF 的所有接入电路共用一个 SID**。**per-CE**：**每条接入电路一个 SID**，行为是 `End.DX4/DX6`——SID 标识**通向客户的那条具体链路**。

:::en
Per-VRF allocation is the default choice: it consumes one SID per VRF, it is simple to operate, and it is sufficient as long as the VRF is attached to a single CE. Per-CE allocation is required when the PE has several attachment circuits in the same VRF and the operator wants a remote PE to select one of them, for example to steer return traffic over a specific link.
:::

**per-VRF 是默认选择**：一个 VRF 消耗一个 SID，运维简单；只要这个 VRF 只挂一个 CE，它就够用。**per-CE 只在下列情况才必须**：同一 VRF 挂了多条接入电路，且需要**远端 PE 能指定走其中某一条**——典型场景是**差异化回程**（去程走 A 链路、回程走 B 链路）。

两者的账本：

| 维度 | per-VRF（`uDT46`） | per-CE（`uDX4/DX6`） |
|---|---|---|
| SID 消耗 | = VRF 数 | = 接入电路数（≥ VRF 数） |
| 出口 PE 查表 | 查 VRF 表（一次） | 不查表，直接出接口（更快） |
| 能否区分同 VRF 的不同 CE | **不能** | **能** |
| 能否做差异化回程 | 不能 | 能 |
| 双栈支持 | 一个 SID 搞定（DT46） | 需 DT4/DT6 两个（DX4 vs DX6 分开） |
| 运维复杂度 | 低 | 中（SID 数随接入点膨胀） |
| 适用规模 | VRF 数千级 | 接入点数百级、需精细控制 |

**例 6.1：per-VRF 分配（IOS XR）**

```text
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
router bgp 65000
 vrf CUSTOMER-100
  rd 65000:100
  address-family ipv4 unicast
   segment-routing srv6
    locator MAIN
    alloc mode per-vrf
```

`micro-segment behavior unode pfx-16` 说明 locator 后 16 bit 是 **locator node**，剩余空间按 uSID 容器分配（16 bit 一个微指令）。`alloc mode per-vrf` 让每个 VRF 自动拿到一个 `uDT46` 微指令，**不需要手工给每个 VRF 编号**。

**例 6.2：确认某个 VRF 的 SID 落在哪里**

```text
RP/0/RP0/CPU0:PE-2# show segment-routing srv6 sid all
SID                         Behavior    Context
fdbb:bb00:0002:e000::       uN          'default'
fdbb:bb00:0002:e001::       uDT46       'CUSTOMER-100'
fdbb:bb00:0002:e002::       uDT46       'CUSTOMER-200'
```

`Context` 一列就是 VRF 名。排障时**第一件事就是确认这条 SID 存在**——SID 没分配出来，BGP 里也不会有 Prefix-SID，入口 PE 就无法用 SRv6 封装这条 VPN 路由。

### 6.3.1 SID 空间够不够：一个实算

uSID locator 的容量是硬约束。以 `/48` locator + `pfx-16`（node 16 bit）为例，剩余 128 − 48 = 80 bit 可作 uSID 容器，即 **5 个 16 bit 微指令**（第 6 个位置在块尾被截断，具体取决于 block 长度）。按每个 VRF 一个 `uDT46` 计：

```text
先分清两个不同的"容量"：
  ① 容器深度：一条报文里能串几个 uSID（/48 locator 下约 5 个 16 bit 位）
  ② function 空间：一个 locator 能分配多少个不同 SID（每 16 bit 位 65,536 个）

VRF 容量看 ②：
  1 个 /48 locator ≈ 65,536 个 uDT46 SID
  单台 PE 的 VRF 规模通常在 4,000 以内 → 一个 /48 绰绰有余
  300 台 PE × 1 个 /48 → 全网近 2,000 万 SID 空间

真正吃空间的是 per-CE：
  接入电路 20,000 条 → 20,000 个 uDX SID，占掉一个 /48 的三分之一
  → 这才是 6.6 节转置（argument 复用）出现的动机
```

一个容易混淆的点要先说清：**"一条报文里能装几条指令"（容器深度）和"一个 locator 能分配多少个 SID"（function 空间）是两件事**。前者决定段列表长度，后者决定 VRF 容量。VRF 数量爆炸的运营商会用 **argument 复用**（6.6 节的转置）把多个 VRF 压进同一个 function。

## 6.4 SID 怎么从出口走到入口：RFC 9252

:::en
The VPN route is advertised exactly as in an MPLS L3VPN: an MP-BGP VPNv4 or VPNv6 update with a route distinguisher, a route target, and the usual path attributes. What changes is that the VPN label is replaced by a BGP Prefix-SID attribute, defined in RFC 9252, which carries the SRv6 L3 Service TLV and, inside it, the SID and the endpoint behavior.
:::

VPN 路由的通告方式**与 MPLS L3VPN 完全一样**：MP-BGP VPNv4/VPNv6 update，带 RD、RT 和常规路径属性。唯一变化是 **VPN 标签被 BGP Prefix-SID 属性替换**——RFC 9252 定义，里面装 **SRv6 L3 Service TLV**，TLV 内再装 **SID 与端点行为**。

:::en
The TLVs are nested: the SRv6 L3 Service TLV (type 5) contains one or more SRv6 SID Information Sub-TLVs (type 1), each of which carries a SID, a behavior code, and an optional SID Structure Sub-Sub-TLV that describes how the SID is partitioned into locator, function, and argument. The SID Structure is what allows a receiver to understand a SID whose internal layout is not the default one.
:::

TLV 是**嵌套**的：**SRv6 L3 Service TLV（type 5）** 内含一个或多个 **SRv6 SID Information Sub-TLV（type 1）**，每个 Sub-TLV 携带 SID、行为码，以及可选的 **SID Structure Sub-Sub-TLV**（描述 SID 如何切分成 locator / function / argument）。**SID Structure 正是让接收方能理解"非默认布局"SID 的关键**——转置与互通全靠它。

```text
图 6-2：BGP Prefix-SID 属性结构（原书 Figure 6.2 重绘）

  BGP Update（VPNv4，10.1.2.0/24）
  ├─ NLRI：RD 65000:100 + 10.1.2.0/24
  ├─ RT：65000:100（扩展团体）
  ├─ Next-Hop：2001:db8::2  ←【必须是 IPv6，见 6.4.1】
  └─ Prefix-SID Attribute（type 40）
       └─ SRv6 L3 Service TLV（type 5）
            └─ SRv6 SID Information Sub-TLV（type 1）
                 ├─ SID      = fdbb:bb00:0002:e001::
                 ├─ Behavior = 0x0014（End.DT46）
                 └─ SID Structure Sub-Sub-TLV（type 1）
                      ├─ Locator Length  = 48
                      ├─ Function Length = 16
                      └─ Argument Length = 0
```

**例 6.3：入口 PE 上确认"SID 学到了"**

```text
RP/0/RP0/CPU0:PE-1# show bgp vpnv4 unicast rd 65000:100 10.1.2.0/24
BGP routing table entry for 10.1.2.0/24, Route Distinguisher: 65000:100
  Paths: (1 available)
    Local
      2001:db8::2 from 2001:db8::2 (192.0.2.2)
        Origin IGP, metric 0, localpref 100, valid, internal, best
        Extended Community: RT:65000:100
        Prefix-SID: SRv6 L3 Service TLV
          SID: fdbb:bb00:0002:e001::
          Behavior: End.DT46
          Structure: L=48 F=16 A=0
```

这四行就是排障的核心证据链：**有路由、有 RT、有 IPv6 下一跳、有 Prefix-SID**。缺任何一项，SRv6 封装就出不来。

:::en
Because the SID is carried only in BGP, the core routers never learn about VRFs, prefixes, or behaviors. They only need the locator prefix in their IGP table. This is the same BGP-free core principle as in MPLS L3VPN, but it is stronger: there is no label to distribute and no transport segment to allocate.
:::

因为 SID **只在 BGP 里传**，核心路由器永远不知道 VRF、客户前缀和行为。它们在 IGP 表里只需要 **locator 前缀**。这与 MPLS L3VPN 的 **BGP-free core** 是同一原则，但**更强**：**没有标签要分发，也没有传输段要分配**。

### 6.4.1 现网第一号坑：VPNv4 的下一跳必须是 IPv6

:::en
For SRv6 encapsulation to be possible, the ingress PE must be able to build an IPv6 outer header whose destination is the remote SID. The next hop of the VPN route must therefore be an IPv6 address, even when the VPN carries only IPv4 prefixes. This is achieved by advertising the VPN routes with an IPv6 next hop, as specified in RFC 8950.
:::

要让 SRv6 封装成立，入口 PE 必须能构造一个**外层 IPv6 头**，其目的地址是远端 SID。因此 **VPN 路由的下一跳必须是 IPv6 地址**——即使这条 VPN 只承载 IPv4 前缀。实现方式是按 **RFC 8950** 用 IPv6 下一跳通告 VPN 路由。

:::en
If the VPN routes are advertised over an IPv4 session, or if the next hop is an IPv4 address, the ingress PE has the Prefix-SID but cannot use it to build the outer header, and the route is either not installed or falls back to another encapsulation.
:::

如果 VPN 路由跑在 **IPv4 会话**上，或者下一跳是 **IPv4 地址**，入口 PE **虽然拿到了 Prefix-SID 却无法用它构造外层头**，这条路由要么不被安装、要么回退到别的封装。

这条的现网表现非常典型：

| 现象 | 根因 | 检查点 |
|---|---|---|
| BGP 有路由、`show bgp` 显示 SID 也在，但业务不通 | 下一跳是 IPv4 | `show bgp vpnv4 unicast <prefix>` 看 Next-Hop 是否为 IPv6 |
| 部分 PE 通、部分不通 | 新加的 PE 用 IPv4 会话建 BGP | `show bgp neighbor <ip>` 看会话 AFI |
| 迁移期间时通时不通 | 双栈会话未起，回落到 IPv4 会话 | `show bgp ipv6 unicast summary` 邻居状态 |
| 路由装上了但转发走了 MPLS | 两种封装信息都在，选优规则不同 | `show cef vrf <vrf> <prefix> detail` 看封装类型 |

所以**迁移到 SRv6 的第一步不是配 locator，而是把 BGP 会话升级到 IPv6**（RFC 8950 的 IPv6 next-hop 能力，或用 IPv6 传输会话跑 VPNv4）。这一步没做完，后面配什么都是空的。

## 6.5 uSID 下的 L3VPN：整个业务只要一条指令

:::en
With micro-segments, the L3VPN service need not be expressed as a segment list at all. The destination SID itself contains the locator of the egress PE and the uDT46 function that identifies the VRF, so a single 128-bit destination address carries the complete instruction set: route to the egress PE, then decapsulate and look up in the VRF.
:::

用微段（uSID）时，L3VPN **根本不需要"段列表"**。目的 SID 本身已经包含**出口 PE 的 locator** 和**标识 VRF 的 uDT46 功能**，所以**一个 128 bit 目的地址就承载了完整指令集**：先路由到出口 PE，再解封装、查 VRF 表。

:::en
As a result, no SRH is pushed, no uN needs to be prepended, and the encapsulation is exactly one IPv6 header. The program has a single instruction, and the dataplane cost at the egress is a single SID lookup followed by a single VRF lookup.
:::

由此得到三个"没有"：**不压 SRH、不需要前置 uN、封装就是恰好一个 IPv6 头**。整个程序只有**一条指令**，出口的数据面成本是**一次 SID 查找 + 一次 VRF 查找**。

```text
图 6-3：uSID L3VPN 的封装（原书 Figure 6.3 重绘）

  客户报文（PE-1 收到）:
  ┌────────────┬──────────────────┐
  │ IPv4 头    │ 10.1.1.x→10.1.2.x │
  └────────────┴──────────────────┘

  PE-1 压入外层（无 SRH）:
  ┌───────────────────────┬──────────────┬──────────────────┐
  │ IPv6 头               │ 内层 IPv4    │ 内层载荷          │
  │ SA = fdbb:bb00:0001:e000::（PE-1 的 uN）               │
  │ DA = fdbb:bb00:0002:e001::（PE-2 的 uDT46，含 VRF-100）│
  │ NH = 4（指向内层 IPv4）                                 │
  └───────────────────────┴──────────────┴──────────────────┘

  P-1/P-2 转发：只看 DA 的 locator 部分 fdbb:bb00:0002::/48
                → 与 VRF 无关、与业务无关

  PE-2 收到：DA 命中本地 uDT46 → 剥外层 → 内层 IPv4 查 VRF-100 → 出 CE-2
```

:::en
Notice how the packet crosses the core: the P routers perform a longest-prefix match on the locator, exactly as they would for any IPv6 packet. They have no VPN route, no VRF, no label, and no SRH to process.
:::

注意报文过核心的方式：P 路由器对 locator 做**最长前缀匹配**，与处理任何 IPv6 报文没有区别。它们**没有 VPN 路由、没有 VRF、没有标签、也没有 SRH 要处理**。

三种封装放在一起，看"一条指令"到底省了什么：

| 方案 | 外层内容 | 出口处理 | 需要 SRH？ | 核心状态 |
|---|---|---|---|---|
| MPLS L3VPN | 传输标签 + VPN 标签 | 弹栈 + 查 VRF | — | LDP/SR-MPLS 标签 |
| SRv6 常规 + 段列表 | IPv6 头 + SRH（含 DA 段 + 最终 SID） | 查 SRH → 查 SID | **是** | locator 路由 |
| **SRv6 uSID（本章）** | **仅 IPv6 头，DA 内嵌 locator+uDT46** | **一次 SID 查表** | **否** | locator 路由 |

**例 6.4：出口 PE 上验证解封装路径**

```text
RP/0/RP0/CPU0:PE-2# show segment-routing srv6 sid fdbb:bb00:0002:e001:: detail
SID          : fdbb:bb00:0002:e001::
Behavior     : uDT46
Context      : CUSTOMER-100 (VRF)
Locator      : MAIN
Structure    : L=48 F=16 A=0
Packets      : 1,284,551
Bytes        : 1,412,006,100
```

`Packets` 计数持续增长 = 这条 SID 真的在被命中。**排障时最有用的一行**：如果业务不通而计数不涨，说明报文压根没到这台 PE（回到 6.4.1 查下一跳），或者到了但没命中这个 SID（查结构与分配）。

## 6.6 转置（Transposition）：把多个业务压进一个 SID

:::en
SID transposition separates the SID into a routable part and a variable part: the locator and function are advertised in BGP, while the argument field is used to encode the service instance locally. The remote PE copies the advertised part unchanged into the destination address and appends the argument, so that many service instances share a single advertised SID.
:::

**转置**把 SID 拆成"**可路由部分**"和"**可变部分**"：**locator 与 function 在 BGP 里通告**，而 **argument 字段用于在本地编码业务实例**。远端 PE 把通告来的部分**原样**拷进目的地址，再**拼上 argument**，于是**多个业务实例共用一个通告 SID**。

:::en
Transposition has two distinct uses. The first is SID space conservation: a PE with tens of thousands of attachment circuits can advertise one SID and encode the circuit in the argument rather than allocating one SID per circuit. The second is interworking, where the argument carries a value derived from an MPLS VPN label so that a gateway can map between the two encapsulations without maintaining a per-prefix state.
:::

转置有**两个完全不同的用途**：

1. **节省 SID 空间**：一台有几万条接入电路的 PE 可以**只通告一个 SID**，把电路编号编进 argument，而不是每条电路一个 SID；
2. **互通**：argument 里装**由 MPLS VPN 标签推导出的值**，网关就能在两种封装之间映射，**不需要为每条前缀维护状态**。

```text
图 6-4：转置的 SID 结构（原书 Figure 6.4 重绘）

  通告的部分（BGP 里不变）              本地可变部分
  ┌──────────┬──────────┬─────────────────────────┐
  │ Locator  │ Function │ Argument                │
  │ 32–48 bit│ 16 bit   │ 剩余位（可 16–48 bit）  │
  └──────────┴──────────┴─────────────────────────┘
       │           │              │
       │           │              └─ 编码：VRF ID / 接入电路 ID / VPN label
       │           └─ 行为：End.DT46 / End.DX4 / End.DT6 …
       └─ 全局可路由（IGP 中的 locator）

  效果：10,000 条接入电路 → 1 条 BGP Prefix-SID + 10,000 个 argument 值
```

:::en
The trade-off is dataplane and operational complexity: the argument must be interpreted correctly on both sides, the SID structure must be advertised and understood, and a packet that carries a wrong or unexpected argument is dropped silently. Transposition is therefore used where the SID space is genuinely the constraint, not as a default design.
:::

代价是**数据面与运维复杂度**：argument 必须两边**解释一致**，**SID 结构必须被通告且被理解**，而 argument 不对的报文会被**静默丢弃**。所以转置只在**SID 空间真的成为瓶颈**时使用，不作为默认设计。

三种"省 SID"的手段对比（选型时按这个顺序考虑）：

| 手段 | 做法 | 省的是 | 代价 | 何时用 |
|---|---|---|---|---|
| 扩大 locator | 每 PE 从 /48 改 /44 或 /40 | function 空间（×16/×256） | 吃掉 IPv6 地址规划余量 | **首选**，最无副作用 |
| per-VRF 替代 per-CE | 只给 VRF 分配 SID | SID 数降到 VRF 数 | 失去按电路定向能力 | 不需要差异化回程时 |
| 转置（argument） | 一个 SID + argument 编码 | SID 数降到 1 | 数据面复杂、排障难 | SID 空间硬约束 / 互通网关 |

**例 6.5：互通网关上的转置（MPLS 域 ↔ SRv6 域）**

```text
! 网关一侧对接 MPLS L3VPN（VPN label 由对端分配），另一侧 SRv6
router bgp 65000
 vrf CUSTOMER-100
  address-family ipv4 unicast
   segment-routing srv6
    locator GW
    alloc mode per-vrf
    ! argument 由入向 VPN label 推导，出向再映射回 SRv6 SID
```

实际部署里，网关的职责是**双向翻译**：MPLS → SRv6 方向把 VPN 标签映射成 argument；SRv6 → MPLS 方向把 argument 还原成标签。**关键是"映射无需逐前缀状态"**——这正是转置对互通的价值：300 台 PE、几千个 VRF 的互通网关不需要几万条状态表项，只需要一张"标签 ↔ argument"的映射规则。

## 6.7 双栈：一个 DT46 还是两个 SID

:::en
End.DT46 handles both address families with one SID, which halves the SID consumption of a dual-stack VRF and simplifies the BGP advertisement: a single Prefix-SID serves both the IPv4 and the IPv6 VPN routes of the same VRF.
:::

`End.DT46` 用**一个 SID 同时处理两个地址族**，把双栈 VRF 的 SID 消耗**减半**，也简化了 BGP 通告：**同一条 Prefix-SID 同时服务该 VRF 的 IPv4 与 IPv6 VPN 路由**。

:::en
The alternative is to allocate separate SIDs with End.DT4 and End.DT6, which is useful when the two families are administered separately or when the egress needs to apply different policies per family, but doubles the state and the advertisement.
:::

另一种做法是分别分配 `End.DT4` 与 `End.DT6` 的独立 SID——当**两个地址族分开管理**，或出口需要**按族施加不同策略**时有用，但**状态与通告都翻倍**。

| 方案 | SID 数 | BGP 通告 | 适用 |
|---|---|---|---|
| **`End.DT46` × 1** | 1 / VRF | VPNv4 与 VPNv6 各一条路由，但引用同一个 SID | 绝大多数双栈 VPN |
| `End.DT4` + `End.DT6` | 2 / VRF | 各自独立 | 分族策略、分族运维 |

工程默认：**除非有明确的分族策略需求，一律用 DT46。** 判定标准很简单——如果运维上你把 IPv4 与 IPv6 当作"同一个 VPN 的两个地址族"，就用一个 SID；如果当作"两个独立业务"，才拆开。

## 6.8 MTU：SRv6 L3VPN 最容易踩的物理约束

:::en
The SRv6 encapsulation adds a 40-byte outer IPv6 header. Because IPv6 routers do not fragment packets in transit, any packet that exceeds the MTU of a core link is dropped and, unless path MTU discovery works end to end, the sender never learns why.
:::

SRv6 封装**加 40 字节外层 IPv6 头**。而 **IPv6 路由器不在中间分片**，所以任何超过核心链路 MTU 的报文会被**丢弃**；如果**端到端 PMTUD 不工作，发送方永远不知道原因**。

:::en
The classic symptom is that small packets pass and large packets do not: a ping succeeds, a TCP handshake succeeds, but a bulk transfer stalls, or an SSH session hangs as soon as the terminal output grows. This is a size problem, not a routing problem, and no amount of show command on the routing side will reveal it.
:::

经典现象：**小包通、大包不通**——`ping` 通、TCP 三次握手成功，但**大文件传输卡死**，或者 **SSH 一有大量输出就挂住**。这是**尺寸问题，不是路由问题**，在路由侧敲再多 `show` 命令也看不出来。

账要这么算：

```text
图 6-5：MTU 预算（原书 Figure 6.5 重绘）

  CE 侧接口 MTU = 1500
  ＋SRv6 外层（IPv6 头）          40 B
  ─────────────────────────────────────
  核心链路最小 MTU 需求          = 1540 B

  若某台 PE 要加 SRH（TI-LFA/段列表场景）：
  1540 + SRH(8) + 段(16×N)  → 建议核心统一 ≥ 1600 B

  现网做法（三选一，通常同时用）：
  ① 核心链路 MTU 提到 9000（jumbo），一劳永逸
  ② 核心链路 MTU 提到 1580–1600，覆盖 L3VPN + 少量 SRH
  ③ 保持 1500，在 PE 上做 TCP MSS 钳制（mss-adjust）+ 保证 ICMPv6 PTB 不被过滤
```

:::en
In practice, operators either raise the MTU of the core to accommodate the encapsulation with margin, or clamp the TCP MSS at the PE, or both. Relying on path MTU discovery alone is fragile because ICMPv6 Packet Too Big messages are frequently filtered by security policies.
:::

实践中，运营商要么**把核心 MTU 抬高并留余量**，要么**在 PE 上钳制 TCP MSS**，通常**两者都做**。只依赖 PMTUD 很脆弱，因为 **ICMPv6 Packet Too Big 经常被安全策略过滤**。

**例 6.6：用大小包快速判断"是不是 MTU"**

```text
RP/0/RP0/CPU0:PE-1# ping vrf CUSTOMER-100 10.1.2.1 size 100 repeat 5
!!!!!   ← 小包通

RP/0/RP0/CPU0:PE-1# ping vrf CUSTOMER-100 10.1.2.1 size 1472 repeat 5
.....   ← 大包全丢 → 100% 是封装后超 MTU（1472+8+40 = 1520 > 1500 路径 MTU）

RP/0/RP0/CPU0:PE-1# ping vrf CUSTOMER-100 10.1.2.1 size 1400 repeat 5
!!!!!   ← 1400+8+40 = 1448 < 1500 → 通
```

这条判据非常实用：**在 1400 与 1472 之间二分，就能算出实际可用的路径 MTU**，再反推哪一段没做 MTU 提升。

## 6.9 排障：六步定位法

L3VPN 故障的现象高度雷同（"VPN 路由在、业务不通"），但根因分布在六个层次。按顺序走，每步都有明确判据：

```text
第 1 步：BGP 里有这条 VPN 路由吗？
  show bgp vpnv4 unicast rd <RD> <prefix>
  ├─ 无 ────────────────► RT 导入导出、RR、会话（与 SRv6 无关，先修 BGP）
  └─ 有 ──► 第 2 步

第 2 步：下一跳是 IPv6 吗？
  show bgp vpnv4 unicast rd <RD> <prefix>
  ├─ Next-Hop 是 IPv4 ──► RFC 8950 未启用，SRv6 封装出不来（6.4.1）
  └─ 是 IPv6 ──► 第 3 步

第 3 步：Prefix-SID 属性在吗？
  show bgp vpnv4 unicast ... detail | include Prefix-SID
  ├─ 无 ────────────────► 出口 PE 没分配 SID（6.3 的 alloc mode / VRF 未配）
  └─ 有 ──► 第 4 步

第 4 步：locator 在入口 PE 的 IGP 表里吗？
  show isis route <远端 locator>
  ├─ 无 ────────────────► 第 5 章的事：泄露/重分发/汇总
  └─ 有 ──► 第 5 步

第 5 步：报文到了出口 PE 吗？SID 命中了吗？
  show segment-routing srv6 sid <SID> detail     （看 Packets 计数）
  ├─ 计数不涨 ──────────► 报文没到（IGP 转发问题，回第 4 步）
  ├─ 计数涨但不通 ──────► 命中后查表失败（VRF 缺路由 / 缺 CE 侧明细）
  └─ 正常 ──► 第 6 步

第 6 步：大包通不通？
  ping vrf <vrf> <CE 地址> size 1472
  ├─ 大包丢 ────────────► MTU（6.8）
  └─ 通 ────────────────► 客户侧策略（ACL/NAT/QoS）
```

配套巡检项：

| 检查项 | 命令 | 期望 |
|---|---|---|
| 每个 VRF 都有 SID | `show segment-routing srv6 sid all` | 每 VRF 一条 `uDT46`，Context 对得上 |
| VPN 路由带 Prefix-SID | `show bgp vpnv4 unicast detail` | 每条都有，且 Behavior 正确 |
| 下一跳全 IPv6 | 同上 | 无 IPv4 next-hop |
| 核心零 VPN 状态 | `show cef vrf` on P | **应为空**（P 上没有 VRF 配置） |
| locator 路由完整 | `show isis route` | 全网 locator 可达 |
| SID 命中计数在涨 | `show segment-routing srv6 sid detail` | 业务量正相关 |
| MTU 余量 | `show interface \| include MTU` | 核心 ≥ CE MTU + 40（建议 +100） |

## 6.10 本章小结

:::en
In this chapter, we have shown that SRv6 L3VPN reuses the entire MPLS L3VPN control plane: the same VRFs, route distinguishers, route targets, and the same MP-BGP VPNv4/VPNv6 advertisement. Only the service identifier changes, from a locally significant VPN label to a globally unique SRv6 SID.
:::

本章说明了：SRv6 L3VPN **复用了 MPLS L3VPN 的全部控制面**——同样的 VRF、RD、RT，同样的 MP-BGP VPNv4/VPNv6 通告。**只有服务标识变了**：从**本地有效的 VPN 标签**换成**全局唯一的 SRv6 SID**。

:::en
The endpoint behaviors End.DT4, End.DT6, and End.DT46 perform decapsulation and a VRF lookup, while End.DX4 and End.DX6 send the packet out of a specific interface, which is the natural choice for per-CE allocation. The SID reaches the ingress PE in the BGP Prefix-SID attribute of RFC 9252, so the core remains free of VPN state.
:::

端点行为 `End.DT4/DT6/DT46` 执行**解封装 + VRF 查表**；`End.DX4/DX6` **从指定接口发出**，是 per-CE 分配的自然选择。SID 通过 **RFC 9252 的 BGP Prefix-SID 属性**到达入口 PE，因此**核心保持零 VPN 状态**。

:::en
With micro-segments, the whole service is encoded in the destination address: no SRH, no uN, one instruction. The price is a 40-byte outer header, which makes MTU planning a first-class design task rather than an afterthought.
:::

用微段时，**整个业务编码在目的地址里**：无 SRH、无 uN、一条指令。代价是**40 字节外层头**，这使 **MTU 规划成为一等设计任务**，而不是事后再说。

把全章压成一张表：

| 维度 | MPLS L3VPN | SRv6 L3VPN | 结论 |
|---|---|---|---|
| 控制面 | MP-BGP VPNv4/VPNv6 | **完全相同** | 迁移成本低，RR/RT 全部复用 |
| 服务标识 | VPN 标签（本地有效） | SID（全局唯一） | 不再需要 SRGB 规划 |
| 传输标识 | 外层 transport 标签 | **locator 前缀**（即 SID 的一部分） | 标签分发协议退场 |
| 核心状态 | 标签 + IGP | 只有 locator 路由 | 更强的 BGP-free |
| 封装开销 | 8 B | 40 B（uSID 无 SRH） | **SRv6 更大，必须承认** |
| 出口行为 | 弹栈 + 查 VRF | `End.DT4/6/46` | 等价 |
| 关键前提 | 标签分发正常 | **IPv6 下一跳（RFC 8950）** | 迁移第一号坑 |
| 规模瓶颈 | 标签空间（可控） | uSID 空间 + MTU | 靠 /48 规划与 MTU 提升解决 |

一句话收束：**SRv6 L3VPN 不是"另一套 VPN"，而是"同一套 VPN 换了个服务标识"**。真正需要重新设计的只有三件事：**SID 空间（locator 规划）、IPv6 下一跳、MTU**。

## 实战案例

### 案例 A：300 台 PE 从 MPLS L3VPN 平滑迁移到 SRv6

**背景**：某运营商 300 台 PE、约 4,000 个 VRF，现网 MPLS L3VPN（LDP + BGP 3107），计划分三批迁移，要求**业务零中断、可随时回退**。

**阶段一：共存（不改任何业务路径）**

```text
① 全网 P/PE 升级到支持 SRv6 与 uSID 的版本，locator 从统一 SID block 规划
② 每台 PE 配 locator（例 6.1），但先不设 alloc mode → 只通告 locator，不产生 VPN SID
③ BGP 会话升级到 IPv6（或启用 RFC 8950 的 IPv6 next-hop 能力）
④ 核心链路 MTU 从 1500 提升到 1600（分批，先改核心，再改边缘）
⑤ 此时 VPN 路由仍只带 MPLS 标签，SRv6 侧"看得见但不用"
```

**阶段二：按区域切流（可回退的关键）**

```text
⑥ 选定一个区域（约 40 台 PE），给 VRF 开启 alloc mode per-vrf
⑦ 同一条 VPN 路由同时携带 MPLS 标签与 Prefix-SID（双封装信息）
⑧ 入口 PE 的封装选择策略：区域内优先 SRv6，跨区仍走 MPLS
⑨ 观察一周：SID 命中计数、CPU、MTU 告警、故障切换
```

**阶段三：切默认与清退**

```text
⑩ 全网区域都验证通过后，把"优先 SRv6"设为默认，MPLS 仅作回退
⑪ 拆除互通网关 → 关闭 LDP / BGP 3107 → 移除 MPLS 标签池
⑫ 保留一个月的回退窗口（配置文件 + 标签池预留）
```

**验收矩阵**：

| 阶段 | 验收项 | 判据 |
|---|---|---|
| 一 | locator 全网可达 | 每台 PE 能 ping 到全部 locator |
| 一 | BGP IPv6 下一跳 | 无 IPv4 next-hop 的 VPN 路由 |
| 一 | MTU 余量 | 核心 ≥ 1600，且 PMTUD 探测通过 |
| 二 | SID 学习正确 | `show bgp vpnv4 unicast` 有 Prefix-SID，Behavior = DT46 |
| 二 | 业务正确性 | 每条 VPN 双向 ping size 1472 通过 |
| 二 | 双封装共存 | `show cef vrf` 显示按策略选 SRv6 |
| 三 | MPLS 残留 | `show mpls ldp neighbor` 为空、无 3107 路由 |
| 三 | 故障切换 | 拔纤验证 TI-LFA + BGP PIC 仍达秒级 |

**三个必踩的坑（提前准备）**：

1. **IPv4 下一跳残留**：部分老 PE 的 BGP 会话仍是 IPv4，必须在阶段一全部清掉，否则阶段二会"部分站点不通"且现象随机；
2. **MTU 遗漏链路**：微波、跨运营商互联段经常被漏掉，表现为"某些站点大包不通"；
3. **VRF 未分配 SID**：新建 VRF 忘了开 alloc mode，路由能学到但没有 SID → 用巡检脚本每天比对"VRF 数 vs uDT46 SID 数"。

### 案例 B：双归属 PE + per-CE SID 做差异化回程

**场景**：某企业站点双归到 PE-2 与 PE-3（同一 VRF-100），要求**去程走 PE-2、回程走 PE-3**，以利用两条不同运营商链路的带宽与资费。

**做法**：

```text
① 两台 PE 上同一 VRF 各配 per-CE 的 uDX SID：
     PE-2: fdbb:bb00:0002:e101::  → End.DX4，指向 CE 的 Gi0/0/0/2
     PE-3: fdbb:bb00:0003:e101::  → End.DX4，指向 CE 的 Gi0/0/0/2
② 对外通告时，PE-2 与 PE-3 用不同的 RT 或 BGP 属性（如 MED / 团体）区分
③ 对端 PE（发起回程方向）按策略选 PE-3 的 SID 作为出口
④ 去程仍由 IGP 度量自然选到 PE-2
```

**关键点：不能只靠 anycast locator。**

| 方案 | 去程 | 回程 | 问题 |
|---|---|---|---|
| 两 PE 用 anycast locator（同前缀） | 按 IGP 度量就近 | **随机**（ECMP 到两台） | 无法定向，回程不可控 |
| **per-CE SID 各自独立** | 按策略或度量 | **可精确指定** | SID 数翻倍，需 per-CE 管理 |
| anycast + anycast SID | 就近 | 就近 | 双活够用，定向不行 |

:::en
An anycast locator shared by two PEs gives active-active reachability but no control over which PE receives the traffic. When the operator needs directional control, per-CE SIDs on distinct locators are the only way to express it, because the SID is then a specific attachment rather than a shared VRF endpoint.
:::

两台 PE 共享 anycast locator 能提供**双活可达性**，但**无法控制哪台 PE 收流量**。需要**方向性控制**时，**不同 locator 上的 per-CE SID 是唯一能表达它的手段**——此时 SID 标识的是**一条具体接入链路**，而不是一个共享的 VRF 端点。

**验证**：

```text
PE-1# show bgp vpnv4 unicast rd 65000:100 10.1.1.0/24 detail | include SID
  SID: fdbb:bb00:0003:e101::  Behavior: End.DX4   ← 回程确实指向 PE-3
PE-1# traceroute vrf CUSTOMER-100 10.1.1.1
  1  fdbb:bb00:0003::   ← 去程/回程路径符合设计
```

### 案例 C：迁移后"ping 通、传文件卡死"的 45 分钟

**现象**：某批 12 台 PE 切到 SRv6 后，VPN 路由正常、`ping` 正常、SSH 登录正常，但**文件传输一开始就卡死**，且只有这 12 台侧的业务受影响。

**排查过程**：

```text
① 第 1–4 步全部通过（路由在、下一跳 IPv6、有 Prefix-SID、locator 可达）
② 第 5 步：出口 PE 的 SID 命中计数在涨 → 报文到了，也在被处理
③ 第 6 步：ping size 1472
   PE-1# ping vrf CUSTOMER-100 10.1.2.1 size 1472 repeat 5
   .....  → 全丢
   PE-1# ping vrf CUSTOMER-100 10.1.2.1 size 1400 repeat 5
   !!!!!  → 全通
④ 二分：1420 通、1440 丢 → 路径实际可用 payload ≈ 1432
   1432 + 8(ICMP) + 40(SRv6) = 1480 → 某段链路 MTU 仍是 1500 而非 1540
⑤ 逐跳查：show interface | include MTU
   发现这 12 台 PE 的上行链路在同一个微波环上，MTU 仍是 1500
   （批量脚本只改了光纤直连段，微波段被漏掉）
```

**修复**：

```text
! 短期：PE 上钳制 MSS，避免 TCP 大包（立即恢复业务）
router bgp 65000
 vrf CUSTOMER-100
  address-family ipv4 unicast
   ! 该 VRF 内所有 TCP 会话的 MSS 上限
!
interface GigabitEthernet0/0/0/2.100
 ipv4 tcp-mss-adjust 1360
!
! 长期：把微波段 MTU 提到 1600，或让该环的业务走别的封装
```

**经验**：

1. **MTU 巡检必须按拓扑自动发现，不能按"光纤/微波"人工分类**——漏掉的一定是手工分类的那一段；
2. **迁移前用 `ping size 1472` 做全 PE 自动探测**，比事后排障便宜得多；
3. **"ping 通 ≠ 业务通"**：ICMP 默认小包，它验证的是连通性，不是 MTU。

## 延伸阅读

- **RFC 4364**：BGP/MPLS IP VPN（VRF、RD、RT、VPN 标签的原始定义），本章 6.1 的对照基准。
- **RFC 9252**：BGP Overlay Services Based on SRv6，Prefix-SID 属性、SRv6 L3/L2 Service TLV 与 SID Structure，6.4 的规范依据。
- **RFC 8950**：用 IPv6 下一跳通告 IPv4 NLRI（含 VPN-IPv4），6.4.1 的强制前提。
- **RFC 8986**：SRv6 网络编程，`End.DT4/DT6/DT46`、`End.DX4/DX6` 与行为码的定义。
- **RFC 8754**：SRH，本章"为什么不需要 SRH"的反面参照。
- 交叉参考：第 3 章（locator 与 uSID 容器、End/End.X）、第 5 章（locator 的跨区可达性）、第 7 章（L2VPN/EVPN 如何复用同一套 SID 机制）、第 8 章（UPA 与 PE-CE 侧的可达性通告）、第 14 章（Bell 的 L3VPN 实网规模）、第 15 章（阿里的大规格 VRF 与 SID 压缩）。


