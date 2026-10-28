<div class="hero">
<h1>SRv6 分章精读</h1>
<p>以《Segment Routing Part III: SRv6》(Clarence Filsfils 等，2024，370 页) 为主线，逐章拆解原理、报文、配置与真实运营商落地案例。</p>
</div>

## 这本书讲什么

《Segment Routing Part III》是 SR 三部曲的第三部，专注 **SRv6（Segment Routing over IPv6）**。它的核心主张只有一句话：

> IP 本来就应该是自足的。IPv4 时代我们不得不用 MPLS 做 VPN/TE、用 VXLAN 做二层延伸、用熵标签解决负载分担；IPv6 + SRv6 把这些"补丁层"全部收回到 IP 自身。

全书 17 章可以分成五块：

| 板块 | 章节 | 你要拿到的东西 |
|---|---|---|
| 观念与基础 | 1–2 | 为什么 SRv6 值得替换 MPLS；SID/uSID/SRH 到底怎么处理 |
| Underlay 路由 | 3–5 | Locator、End/End.X、TI-LFA、Flex-Algo、IS-IS 多区域与汇总 |
| 业务与运维 | 6–9 | L3VPN、L2VPN(EVPN)、UPA、Ping/Traceroute |
| 规划与落地 | 10–13 | 地址规划、MTU、安全、服务编程、SR-aware 与 SR Proxy |
| 真实案例 | 14–17 | Bell Canada 两张网、阿里巴巴核心网，以及 IPv6 必备知识 |

## 三条阅读路线

**① 零基础通读（推荐）**
`01 → 02 → 03 → 06 → 10` 先建立"地址 + 报文 + 业务 + 规划"闭环，再回头补 04/05/07/08/09。

**② 运维排障视角**
`02（报文处理）→ 09（Ping/Traceroute）→ 08（UPA）→ 05（多区域泄露/汇总）`，专治"能 ping 通 PE 但业务不通""跨区绕行""汇总后黑洞"。

**③ 架构设计与投标视角**
`01 → 06 → 10 → 14 → 15 → 16`，直接看两家运营商怎么把地址切成 Block/Set/Node，怎么算容量、怎么降 OPEX。

## 章节地图

> 带 <span class="done">已精读</span> 标记的章节，已按原书段落**逐段中英对照**重写：英文块是原文摘录，中文是完整翻译，书中的图按原描述用 ASCII 重绘，并补充了可直接落地的实战案例与排障命令。

<div class="cards">
<div class="card"><a href="01-introduction.html">01 SRv6 导论</a><p>Walled Garden、网络程序、3216、免重新编址、规模账本</p></div>
<div class="card"><a href="02-fundamentals.html">02 SRv6 基础 <span class="done">已精读</span></a><p>LOC:FUNCT:ARG、shift-and-forward、SRH 格式与三种节点角色</p></div>
<div class="card"><a href="03-underlay.html">03 Underlay 指令 <span class="done">已精读</span></a><p>Locator 配置/通告、End 与 flavor、End.X、TI-LFA 保护</p></div>
<div class="card"><a href="04-flex-algo.html">04 Flex-Algo <span class="done">已精读</span></a><p>按算法分片：min-cost / min-delay / 排除链路，独立地址块</p></div>
<div class="card"><a href="05-isis-locator.html">05 IS-IS 泄露与汇总 <span class="done">已精读</span></a><p>Level-1/2 泄露与 down 位、多实例重分发、summary-prefix 与分层保护</p></div>
<div class="card"><a href="06-l3vpn.html">06 SRv6 L3VPN <span class="done">已精读</span></a><p>End.DT/DX 行为族、per-VRF 与 per-CE、RFC 9252 Prefix-SID、uSID 单指令、转置与 MTU</p></div>
<div class="card"><a href="07-l2vpn.html">07 SRv6 L2VPN</a><p>uDX2/uDX2V/uDT2M、E-Line/E-LAN、多归、WLIB</p></div>
<div class="card"><a href="08-upa.html">08 UPA</a><p>汇总 + BGP PIC 场景下的静默丢包问题与解法</p></div>
<div class="card"><a href="09-oam.html">09 Ping/Traceroute</a><p>带 SID list 的探测、O-flag、ECMP 下的路径校验</p></div>
<div class="card"><a href="10-deployment.html">10 部署规划</a><p>地址层级、Set/Node 分配、MTU、SR Domain 加固、无缝演进</p></div>
<div class="card"><a href="11-service-programming.html">11 服务编程</a><p>Service SID、SR Service Policy、BSID、BGP-LS SC/OM TLV</p></div>
<div class="card"><a href="12-sr-aware.html">12 SR-aware 服务</a><p>内层报文暴露、SERA 防火墙、SR-Snort、Metadata</p></div>
<div class="card"><a href="13-sr-proxy.html">13 SR Proxy</a><p>静态/动态/伪装三种代理，让老设备进链</p></div>
<div class="card"><a href="14-case-bell.html">14 案例 Bell</a><p>19,000 节点、81 个区域、ULA 地址怎么切</p></div>
<div class="card"><a href="15-case-alibaba.html">15 案例阿里</a><p>UNI/NNI 双块、Anycast、两级 TE、WLIB</p></div>
<div class="card"><a href="16-case-bell-sp.html">16 案例 Bell SP</a><p>生产环境 DDOS 服务链，真实 IOS XR 配置</p></div>
<div class="card"><a href="17-ipv6-essentials.html">17 IPv6 必备</a><p>扩展头、Flow Label、MTU/PMTUD，读 SRv6 的底子</p></div>
</div>

## 阅读约定

- 章节页里的地址沿用书中约定：`fc00:0:N::/48` 表示节点 N 的 Locator，`::X::`、`::eeee::` 表示 Function。
- uSID 容器写作 `fc00:0000:NNNN:MMMM::`，一个 16 bit 段 = 一条微指令。
- 每个章节末尾都有 **实战案例** 小节：要么是书中运营商原案，要么是对应的工程落地场景（含排障要点）。
- 书中伪代码引用 RFC 8986 / RFC 8754 / RFC 9252 / RFC 9256 / draft-ietf-spring-srv6-srh-compression。

> 本站是学习笔记，非官方译本。引用原书观点已标注章节号，便于对照阅读。发现疑义以 RFC 原文为准。
