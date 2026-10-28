# 25 · 速查手册：SID 行为、地址规划、RFC 与排障命令

> **本章定位**：附录。前面 24 章是读的，这一章是查的。设计评审、割接现场、故障处理时，直接翻这里。
>
> 一句话概括：**所有"我应该配哪个 SID""这个现象该看什么"的问题，答案都在这一页以内。**

## 25.1 SID 行为速查

:::en
Each SRv6 SID is associated with a behavior, which defines the processing of the packet when the SID is the Destination Address of the packet.
:::

每个 SRv6 SID 都绑定一个**行为（behavior）**，行为定义了当该 SID 作为报文目的地址时的处理方式。

| 行为 | 用途 | 关键动作 | 章节 |
|---|---|---|---|
| `End` | 节点 SID，最基础的转发 | 更新 DA，按 SL 继续 | 3 |
| `End.X` | 邻接 SID，绑定某条链路 | 更新 DA + 指定出接口 | 3 |
| `End.DT4` / `End.DT6` | L3VPN per-VRF | 剥外层，按 VRF 查表 | 6 |
| `End.DX4` / `End.DX6` | L3VPN per-CE | 剥外层，指定出接口 | 6 |
| `End.DT2M` | L2 广播/组播 | 剥外层，按 VRF 泛洪 | 7 |
| `End.DX2` / `End.DX2V` | L2 单播 | 剥外层，出二层口 | 7 |
| `End.B6.Encaps` | BSID 封装形态 | 压新 SRH 并转发 | 11 / 18 |
| `End.B6.Encaps.Red` | BSID 简化封装 | 压更短的 SRH | 11 |
| `End.MAP` | 移动网锚点重定向 | 查表换 DA，不解封装 | 20 |
| `End.M.GTP6.D` | 5G 下行入 SRv6 | 剥 GTP/UDP，压 SRv6 | 20 |
| `End.M.GTP6.D.Di` | 中间 UPF | 改 TEID + DA，不重封装 | 20 |
| `End.M.GTP6.E` | 5G 上行出 SRv6 | 压 GTP/UDP | 20 |
| `H.M.GTP4.D` | 4G 内层 IPv4 入 SRv6 | 剥 GTP，压 SRv6 | 20 |
| `uN` / `uA` | uSID 压缩段 | 移位 + 转发 | 2 / 19 |
| `End.T` | 特定表转发 | 按指定表查 | 2 |
| `End.DX2V` / `uDX2` | VLAN 映射 | 按 VLAN 出二层 | 7 |

记忆口诀：

- **`DT` 查表，`DX` 出接口**；
- **带 `2` 是二层，带 `4/6` 是三层**；
- **`B6` 是"再压一层"（BSID）**；
- **`M` 是移动（Mobile）**。

## 25.2 地址规划速查

| 项 | 建议位宽 | 说明 |
|---|---|---|
| Block | 32 bit（3216）或 48 bit（常规） | 全网唯一，跨域边界 |
| Locator | 32–48 bit | 每节点一个，进 IGP |
| Function | 16 bit | 行为编号，节点内唯一 |
| Arg | 0–32 bit | 业务参数（VPN ID、TEID、颜色） |
| BSID 池 | 独立 /64 | 不要与 locator 混放 |
| 压缩 locator | 独立 /48 | 与普通 locator 并存（19.5.1） |

**四条硬规矩**：

1. Block 不与 SRGB 混用（21.2.2）；
2. BSID 池单独规划，便于单独写 ACL（23.1.4）；
3. 业务 SID 永远 128 bit，不编进微指令（19.5.3）；
4. 汇总前确认 locator 分层，否则会隐藏 SID（第 5 章 UPA）。

## 25.3 RFC 索引

| 主题 | RFC / 草案 | 本站章节 |
|---|---|---|
| SR 架构 | RFC 8402 | 1 / 21 |
| SRH | RFC 8754 | 2 / 19 |
| SRv6 行为 | RFC 8986 | 3 / 6 / 19 |
| SRv6 压缩 | draft-ietf-spring-srv6-srh-compression | 19 |
| SRv6 L3VPN | RFC 9252 | 6 |
| EVPN over SRv6 | RFC 9252 及 EVPN 相关 RFC | 7 |
| IGP Flex-Algo | RFC 9350 | 4 / 22 |
| IS-IS 扩展 | RFC 8667 / RFC 9352 | 5 |
| BGP-LS | RFC 7752 / RFC 9085 | 18 |
| PCEP | RFC 5440 / RFC 8231 | 18 |
| SR Policy | RFC 9256 | 18 / 22 |
| SRv6 移动承载 | RFC 9433 | 20 |
| IOAM | RFC 9197 / RFC 9326 | 24 |
| DetNet | RFC 8655 | 22 |
| IPv6 基础 | RFC 8200 / RFC 8201 | 17 |
| BFD / SBFD | RFC 5880 / RFC 7880 | 18 / 24 |
| SR-MPLS 互通 | draft-ietf-spring-srv6-mpls-interworking | 21 |

## 25.4 排障命令速查（IOS XR 风格）

| 想确认什么 | 命令方向 |
|---|---|
| Locator 有没有起来 | `show segment-routing srv6 locator` |
| SID 有没有被 IGP 通告 | `show isis database verbose` / BGP-LS 拓扑 |
| SID 转发是否命中 | `show cef ipv6 <SID> detail` |
| Policy 状态 | `show segment-routing traffic-eng policy name X detail` |
| Policy 的段列表 | 同上，看 candidate path 的 segment list |
| BSID 计数 | 同上，看 binding SID 统计 |
| PCEP 会话 | `show pcep session` |
| BGP-LS 邻居 | `show bgp link-state` |
| SBFD | `show bfd session`（SBFD 特定关键字随版本） |
| 端到端路径探测 | SRv6 ping/traceroute 带 SID 列表（第 9 章） |
| 压缩是否生效 | 看 locator 格式 + 抓包看是否带 SRH（19.6） |

## 25.5 术语对照

| 英文 | 中文 | 一句话 |
|---|---|---|
| SID | 段标识 | 128 bit 的"指令 + 地址" |
| uSID / CSID | 微段 | 16 bit 压缩段 |
| SRH | 段路由头 | 装 SID 列表的扩展头 |
| Locator | 定位符 | 节点的 SID 前缀 |
| BSID | 绑定 SID | 一条策略的"名字" |
| Candidate Path | 候选路径 | 策略的一种实现方式 |
| Segment List | 段列表 | 真正的转发路径 |
| Color | 颜色 | 业务与隧道的绑定标记 |
| BGP-LS | BGP 链路状态 | 控制器看拓扑的眼睛 |
| PCEP | 路径计算通信协议 | 控制器下路径的手 |
| SBFD | 无缝 BFD | 端到端检测，不需对端配置 |
| TI-LFA | 拓扑无关无环备份 | 50 ms 内保护 |
| Flex-Algo | 灵活算法 | 按约束切分拓扑 |
| MSD | 最大 SID 深度 | 设备能压多少段 |
| UPA | 不可达前缀通告 | 防汇总黑洞 |
| IOAM | 带内运行管理 | 报文自带测量数据 |

## 25.6 症状 → 章节 索引

| 症状 | 先看 |
|---|---|
| 业务不通，Policy 是 up | 18.8 / 24.2 |
| 能 ping 通 PE，业务不通 | 6 / 8 |
| 跨区绕行 | 5 |
| 汇总后部分前缀黑洞 | 8（UPA） |
| 只有部分用户慢 | 24.5（ECMP 哈希） |
| 时延达标但抖动超标 | 22.4 |
| 切片压测时低优先级饿死 | 22.6 |
| 迁移后单向通 | 21 案例 B（MTU / 路径不对称） |
| traceroute 看不到中间跳 | 19.5.2 |
| UE 切换基站断 3 秒 | 20 案例 A |
| 下行 0 包 | 20 案例 B（SID 结构不一致） |
| 边界流量异常放大 | 23.1.1 |
| 策略集体偏离 | 23.3（PCEP 被冒用） |

## 本章小结

| 记住这一条 | 为什么 |
|---|---|
| 行为表是设计的起点 | 先定"要干什么"，再定地址 |
| 四条地址硬规矩不可破 | 破了会在半年后炸 |
| RFC 索引按主题查，不按编号背 | 现场要的是"哪本管这事" |
| 症状索引比命令清单更快 | 先定位层，再敲命令 |

## 延伸阅读

- 全部 24 章：本章是它们的索引，不新增知识点
- IETF Datatracker：所有草案与 RFC 的最新版本（以官方为准）
- 交叉章节：见 25.6 症状索引
