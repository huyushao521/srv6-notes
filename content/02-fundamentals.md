# 02 · SRv6 基础：SID、uSID 与 SRH

> 对应原书第 2 章 *SRv6 Fundamentals*。这是全书地基：**SID 的格式、uSID 的位移转发、SRH 的结构、三种节点角色**。建议把 2.6 的报文示例手推一遍。

## 2.1 源路由三十秒

:::en
Segment Routing is a source routing architecture: the source node encodes an ordered list of segments in the packet header, and each transit node simply executes the instruction it is pointed at. The state of the path is carried in the packet, not stored in the network. A segment is an instruction; a SID is the identifier of a segment, expressed as an IPv6 address.
:::

SR 是源路由架构：源节点把**有序段列表**编码进报文头，每台中间节点只执行"当前指向的那条指令"。**路径状态在报文里，不在网络里**。段是一条指令，SID 是段的标识，在 SRv6 里就是一个 IPv6 地址。

| 段类型 | 指令 | SRv6 行为 | uSID 别名 | MPLS 对应 |
|---|---|---|---|---|
| Prefix Segment | 沿 ECMP 最短路径到该前缀 | End | **uN** | Node/Prefix-SID |
| Adjacency Segment | 从指定链路出去 | End.X | **uA** | Adj-SID |
| VPN Segment | 解封装 + 在 VRF 内转发 | End.DT4/6/46 | **uDT\*** | per-VRF 标签 |

## 2.2 SID 的解剖：LOC:FUNCT:ARG

:::en
A SID is structured as Locator, Function and Argument. The locator identifies the node that instantiates the SID and is advertised in the IGP; the function is an opaque identifier of a local behavior; the argument is an optional parameter used by some behaviors. The sum of the three fields cannot exceed 128 bits, and the remaining bits are padded with zeros.
:::

SID = `LOC:FUNCT:ARG`。**Locator** 标识实例化该 SID 的节点，由 IGP 通告、全网可路由；**Function** 是本地行为的不透明 ID；**Argument** 是某些行为才用的可选参数。三者之和不超过 128 bit，不够就补零。

```text
|<---- Locator (L) ---->|<-- Function (F) -->|<-- Arg (A) -->|
        fc00:0:7                    e001              (opt)
```

节点为本机 SID 建 FIB 表项；收到报文对 DA 做最长前缀匹配，命中本机 SID 就执行对应行为。

## 2.3 uSID 容器

:::en
A uSID container is a 128-bit address made of a 32-bit block followed by up to six 16-bit uSIDs. All uSIDs in one container belong to the same block. When fewer than six instructions are needed, the remaining positions are filled with zeros, marking the end of the container.
:::

一个 uSID 容器是 128 bit 地址：**32 bit Block + 最多 6 个 16 bit uSID**。同一容器内所有 uSID 必须属于同一个 Block。不足 6 条时，剩余位置填 `0000`，表示容器结束。

```text
| Block 32b |  uSID1  |  uSID2  |  uSID3  | 0000 | 0000 | 0000 |
  fc00:0000    0002      0003      0004    (End of Container)
```

## 2.4 位移转发：一条指令的全部实现

:::en
When a node receives a packet whose destination address matches its own uN, it executes a shift: the whole container after the block is shifted left by 16 bits and a zero is inserted on the right. The shifted-out uSID is discarded, because that instruction has just been executed. The result is used as the new destination address for the next lookup.
:::

节点收到报文，若目的地址命中自己的 uN，就执行一次"位移"：Block 之后的整个容器**左移 16 bit**，右侧补零。被移出的那个 uSID 直接丢弃——因为这条指令刚刚执行完。位移结果作为新的 DA 去做下一次查表。

```text
前：fc00:0000:0002:0003:0004:0000:...
后：fc00:0000:0003:0004:0000:0000:...
              ↑ 左移 16 bit，0002 已出栈
```

:::en
Because forwarding uses longest prefix match, a node can install a /64 entry that matches both its uN and the following uA, and execute both instructions with a single lookup. The same property allows 16-bit and 32-bit uSIDs to be mixed within one program, which is how very large VPWS scale is achieved.
:::

因为转发用最长前缀匹配，节点可以装一条 **/64** 表项，同时匹配"自己的 uN + 紧随其后的 uA"，**一次查表执行两条指令**。同样的性质让 16 bit 与 32 bit uSID 能在同一程序里混编——这正是超大规格 VPWS 的实现方式（见第 7 章）。

## 2.5 SRH 的格式

:::en
When more than six uSIDs are required, a Segment Routing Header is pushed. It is a routing header of type 4, and it carries a list of 16-byte container SIDs stored in reverse order: entry zero is the last segment of the path. The Segments Left field indicates how many segments are still to be processed, and it equals Last Entry when the packet is originated.
:::

超过 6 条指令时压入 SRH。它是一种 Routing Type = 4 的路由头，携带 16 字节容器 SID 列表，**倒序存放**：`Segment List[0]` 是路径的最后一跳。`Segments Left` 表示还有几段未处理，源端发出时 `SL = Last Entry = n-1`。

| 字段 | 长度 | 说明 |
|---|---|---|
| Next Header | 8b | SRH 之后紧跟的头部（如 4 = IPv4） |
| Hdr Ext Len | 8b | 以 8 字节为单位 |
| Routing Type | 8b | 固定 4 |
| Segments Left | 8b | 剩余段数 |
| Last Entry | 8b | 段列表末元素索引 |
| Flags | 8b | bit 2 = O-flag（OAM，RFC 9259） |
| Tag | 16b | 分组标记，SID 处理时不使用 |
| Segment List | 128b×n | 倒序段列表 |
| TLV | 变长 | 仅定义 HMAC/Padding，暂无实现 |

## 2.6 三种节点角色

:::en
A source node originates the packet with a segment list. A transit node receives a packet whose destination address does not match any local segment: it forwards the packet as a normal IPv6 packet and must not inspect the SRH — per RFC 8200 only the node addressed by the destination may process a routing header. A segment endpoint receives a packet whose destination matches a local SID, executes that behavior, and moves the active segment to the next one.
:::

源节点负责生成带段列表的报文；**转发节点**收到 DA 不匹配任何本地段的报文时，按普通 IPv6 转发，**不得检查 SRH**（RFC 8200：只有被目的地址寻址到的节点才能处理路由头）；**端点节点**收到 DA 命中本地 SID 的报文时，执行该行为并把活动段推进到下一条。

> 这条规则有一个非常重要的推论：**P 路由器不需要支持 SRv6**，只要会转发 IPv6。这就是"无缝演进"的技术根源。

## 2.7 完整报文走一遍

拓扑 `1-2-3-4-5`，要求路径 `1→2→3→4→5`，节点 5 上有 L3VPN 业务 SID `fc00:0:5:eeee::`。

**Node1（源）构造：**

```text
IPv6:  SA = fc00:0:1::1        DA = fc00:0:2::     NH = 43
SRH :  Routing Type = 4, Segments Left = 3, Last Entry = 3
       SL[0] = fc00:0:5:eeee::   ← 最后一段
       SL[1] = fc00:0:4::
       SL[2] = fc00:0:3::
       SL[3] = fc00:0:2::        ← 第一段
```

:::en
An endpoint executing the End behavior follows a simple pseudo-code: if Segments Left is zero, stop processing the SRH and proceed to the next header; otherwise decrement the hop limit, decrement Segments Left, copy the segment list entry at the new index into the destination address, and submit the packet to the FIB for the new destination.
:::

端点执行 End 行为的伪代码极简：若 `Segments Left == 0` 就不再处理 SRH，直接进入下一头部；否则跳数减一、`Segments Left` 减一、把新索引处的段拷进 DA，然后按新目的地址交给 FIB。

```text
Node2: SL 3→2, DA = fc00:0:3::
Node3: SL 2→1, DA = fc00:0:4::
Node4: SL 1→0, DA = fc00:0:5:eeee::
Node5: SL==0 → 按 End.DT4 解封装，在 VRF 内查表转发
```

> 这个例子故意做了三件"不真实"的事：本不需要 SRH、用了非压缩 SRH、没开 PSP。作者是为了一次把 SRH 处理讲全。读完第 3 章要能自己解释为什么真实部署里这三件事通常都不发生。

## 2.8 Flow Label：硬件友好的熵

:::en
The ingress PE hashes the customer packet — five-tuple, plus the GTP-U TEID in mobile networks — and writes the result into the 20-bit IPv6 Flow Label of the outer header. Transit nodes then load-balance on the source address, destination address and flow label, optionally with local factors such as router-id and incoming interface to avoid polarization. Unlike MPLS, no deep packet inspection and no entropy label are needed.
:::

入口 PE 对客户报文做哈希（五元组；移动网再加 GTP-U TEID），结果写进外层 IPv6 头部的 **20 bit Flow Label**。中间节点按 `(SA, DA, FlowLabel)` 做负载分担，可再加入 router-id、入接口等本地因子防止极化。与 MPLS 不同，**既不需要 DPI，也不需要熵标签**。

## 实战案例：一个卡顿现象，四个知识点

**现象**：某省网城域出口改 SRv6 后，A 局到 B 局的视频业务偶发 200~800 ms 卡顿，普通 HTTP 正常。

**逐层定位**：

1. **看封装形态**。该业务只需 2 条指令（uN + uDT4），理论上不应有 SRH。抓包发现带 SRH——说明引流用了非压缩策略，包头变大；链路 MTU 恰好 1500，大包被丢，视频分片重传造成卡顿。改用 uSID 压缩（如 `ub6-insert-reduced`）后消失。
2. **验 Flow Label**。同一条视频流的所有包 Flow Label 应一致；若某个 ECMP 成员完全没流量，说明 P 节点仍在按内层哈希，或哈希因子过多导致极化。
3. **验 Transit 不越权**。抓包确认 P 节点没有修改 `Segments Left`；若有，说明某台 P 误配了相同 SID，发生了"越界执行"。
4. **验最后一跳**。开 `psp-usd` 后，倒数第二跳应已删除 SRH，最后一跳只看到裸内层报文（对末端隐藏 SID list）。

一个现象，对应 `2.4 压缩收益`、`2.5 SRH 字段`、`2.6 Transit 只按 DA 转发`、`2.8 Flow Label 熵` 四个知识点——这就是手推报文的价值。

## 本章小结

1. SID = `LOC:FUNCT:ARG`；Locator 全网路由，Function 本地解释。
2. uSID 容器 = `32b Block + 6×16b`，核心指令只有一条：shift-and-forward。
3. SRH 仅在 >6 条指令或需要 flag/TLV 时出现，段列表倒序。
4. 三种角色：Source 造程序、Transit 只看 DA、Endpoint 执行并推进指针。
5. Flow Label 是"删掉 DPI 与熵标签"的技术前提。
