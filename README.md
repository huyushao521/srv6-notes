# SRv6 Notes · SRv6 精读

**English** | [中文](#中文)

Reading notes for *Segment Routing Part III: SRv6* — 17 chapters + a reading guide, each chapter pairing selected English excerpts from the book with Chinese commentary, configuration snippets and real-world case studies.

**Live site:** <https://huyushao521.github.io/srv6-notes/>

---

## English

### About

This repository is a static site of structured, hands-on reading notes for *Segment Routing Part III: SRv6* (Clarence Filsfils et al., 2024). It is not a translation of the book: every chapter alternates between **a short excerpt of the original English text** and **a Chinese walkthrough** (design intent, control-plane mechanics, pitfalls, verification commands). Roughly 40% of the material is engineering practice — Cisco IOS XR style configuration, packet walks, and operator deployments — which does not appear in the book.

### Chapters

| # | Chapter | Focus |
|---|---------|-------|
| — | Reading guide | How the chapters fit together, how to use the site |
| 01 | Introduction | Why SRv6: MPLS limitations, SRv6 value proposition |
| 02 | Fundamentals | SID, Locator, uSID, SRH, End/End.X behaviours |
| 03 | Underlay | Locator advertisement, End / End.X, TI-LFA, microloops |
| 04 | Flexible Algorithm | Flex-Algo definitions, affinity, SRv6 locator participation |
| 05 | IS-IS Locators | Leaking, redistribution and summarization of locators |
| 06 | L3VPN | VPNv4/VPNv6 over SRv6, per-VRF SID, RD/RT |
| 07 | L2VPN (EVPN) | EVPN route types 2/5 carried over SRv6 |
| 08 | UPA | Unreachable Prefix Advertisement for SRv6 VPNs |
| 09 | OAM | SRv6 Ping and Traceroute, O-flag, SRH handling |
| 10 | Deployment | Addressing plan, MTU/AMT, security hardening |
| 11 | Service Programming | Encoding service chains in the SID list |
| 12 | SR-aware services | Exposing the inner packet to SR-aware applications |
| 13 | SR Proxy | Interconnecting legacy (non-SRv6) nodes |
| 14 | Case: Bell Canada | SRv6 addressing plan in a large SP network |
| 15 | Case: Alibaba | SRv6 design for a cloud backbone |
| 16 | Case: Bell Canada SP | Service programming in production |
| 17 | Appendix | IPv6 essentials you actually need |

### Repository layout

```
content/    Markdown sources, one file per chapter
build.py    Static site generator (Markdown -> docs/*.html)
assets/     style.css, app.js (search, sidebar, TOC)
docs/       Generated output, served directly by GitHub Pages
```

### Build and preview locally

```bash
pip install markdown
python build.py
python -m http.server 8000 --directory docs
# open http://localhost:8000
```

`build.py` writes `docs/` from scratch on every run, so never edit files under `docs/` by hand — change `content/*.md` or `build.py` instead.

### Bilingual convention

Alternating excerpts use a custom `:::en` block. The generator turns it into a shaded panel tagged `EN`:

```
:::en
English excerpt from the book.
:::

The Chinese commentary for the same idea.
```

Headings come from the source Markdown (`##`/`###`), which also drives the right-hand table of contents.

### Deployment

GitHub Pages serves the `docs/` directory on `main`:

1. Push to `main`.
2. Settings → Pages → Source: `Deploy from a branch`, branch `main`, folder `/docs`.
3. `docs/.nojekyll` is committed, so files starting with `_` are served as-is.

### Comments and errata

Every page ends with a feedback panel that opens a pre-filled GitHub Discussion (`[勘误/留言] <chapter>`) in this repository — title, chapter URL and a report template are filled in for you. Posting requires a GitHub account; the site loads no third-party comment widget or tracking script.

If you prefer an embedded comment box, the repository is ready for giscus: install the giscus app, then swap the panel in `build.py` (`build_feedback`) for the giscus `<script>` tag using your `repo`, `repoId` and `category`.

### Disclaimer

Notes for study and discussion only, not an official translation. Quoted passages remain copyright of their authors and publisher and are reproduced briefly for commentary. For authoritative behaviour, always check the relevant RFCs and the original book.

---

## 中文

### 这是什么

《Segment Routing Part III: SRv6》（Clarence Filsfils 等，2024）的中英对照精读笔记站点，共 17 章 + 1 篇导读。正文严格采用「**一段英文原文节选 + 一段中文讲解**」的对照形式：英文段保留原书表述与术语，中文段负责讲清设计动机、控制面细节、常见坑与验证命令。全书约 40% 的内容是工程实践（IOS XR 风格配置、报文逐跳分析、运营商落地经验），属于原书之外的补充。

### 章节一览

| 编号 | 章节 | 重点 |
|------|------|------|
| — | 导读 | 各章之间的关系与阅读路线 |
| 01 | SRv6 导论 | 为什么需要 SRv6：MPLS 的局限与 SRv6 的取舍 |
| 02 | SRv6 基础 | SID、Locator、uSID、SRH 与 End/End.X 行为 |
| 03 | Underlay 指令 | Locator 通告、End / End.X、TI-LFA 与微环 |
| 04 | 灵活算法 | Flex-Algo 定义、亲和属性、SRv6 locator 参与 |
| 05 | IS-IS Locator | Locator 的泄露、重分发与汇总 |
| 06 | L3VPN | SRv6 承载 VPNv4/VPNv6、per-VRF SID、RD/RT |
| 07 | L2VPN（EVPN） | EVPN 2/5 类路由跑在 SRv6 上 |
| 08 | UPA | 不可达前缀通告，解决 VPN 黑洞问题 |
| 09 | OAM | SRv6 Ping / Traceroute、O-flag 与 SRH 处理 |
| 10 | 网络部署 | 地址规划、MTU/AMT、安全加固 |
| 11 | 服务编程 | 把服务链编码进 SID 列表 |
| 12 | SR-aware 服务 | 向感知 SR 的应用暴露内层报文 |
| 13 | SR Proxy | 与不支持 SRv6 的遗留设备互通 |
| 14 | 案例：Bell Canada | 大型运营商网络的 SRv6 地址规划 |
| 15 | 案例：阿里巴巴 | 云骨干的 SRv6 设计 |
| 16 | 案例：Bell Canada | 服务编程的生产落地 |
| 17 | 附录 | 真正用得上的 IPv6 必备知识 |

### 站点结构

```
content/    正文 Markdown 源文件（每章一个）
build.py    静态站点生成器（Markdown -> docs/*.html）
assets/     style.css、app.js（搜索、侧边栏、本页目录）
docs/       生成结果，GitHub Pages 直接服务此目录
```

### 本地构建与预览

```bash
pip install markdown
python build.py
python -m http.server 8000 --directory docs
# 打开 http://localhost:8000
```

每次运行 `build.py` 都会重新生成整个 `docs/`，不要手改 `docs/` 下的文件，改 `content/*.md` 或 `build.py`。

### 双语写法约定

中英对照用自定义 `:::en` 块，生成器会渲染成带 `EN` 标记的灰底块：

```
:::en
English excerpt from the book.
:::

同一段意思的中文讲解。
```

标题层级由 Markdown 的 `##` / `###` 决定，同时驱动右侧「本页目录」。

### 部署

GitHub Pages 直接发布 `docs/` 目录：

1. 推送到 `main`。
2. Settings → Pages → Source 选 `Deploy from a branch`，分支 `main`，目录 `/docs`。
3. 仓库已提交 `docs/.nojekyll`，下划线开头的文件也能正常访问。

### 留言与勘误

每页页脚都有「留言与勘误」面板，点一下就跳到本仓库 Discussions 并新建一条**预填好**的讨论：标题为 `[勘误/留言] 章节号 章节名`，正文已包含章节链接、位置、问题类型和参考依据的填写模板。发帖需要 GitHub 账号；站点不加载任何第三方评论组件或追踪脚本。

想要页面内嵌评论区也很容易：仓库已适配 giscus。装上 giscus App 后，把 `build.py` 里的 `build_feedback` 换成 giscus 的 `<script>` 片段，填入 `repo`、`repoId`、`category` 即可，其余样式与深色模式会自动跟随。

### 声明

内容为学习交流笔记，非官方译本。引用的原文段落版权归作者与出版方所有，此处仅作简短引用与评论。协议行为与准确表述请以 RFC 及原著为准。
