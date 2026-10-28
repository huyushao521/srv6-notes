# -*- coding: utf-8 -*-
"""把 content/ 下的 Markdown 渲染成静态站点到 docs/（GitHub Pages 直接可服务）。"""
import os
import re
import shutil
import markdown

ROOT = os.path.dirname(os.path.abspath(__file__))
CONTENT = os.path.join(ROOT, "content")
OUT = os.path.join(ROOT, "docs")

PAGES = [
    ("index", "导读", "如何读这本书", "start"),
    ("01-introduction", "01", "SRv6 导论：为什么是 SRv6", "start"),
    ("02-fundamentals", "02", "SRv6 基础：SID、uSID 与 SRH", "start"),
    ("03-underlay", "03", "Underlay 指令：Locator、End/End.X 与 TI-LFA", "underlay"),
    ("04-flex-algo", "04", "灵活算法 Flex-Algo", "underlay"),
    ("05-isis-locator", "05", "IS-IS 中 Locator 的泄露、重分发与汇总", "underlay"),
    ("06-l3vpn", "06", "SRv6 L3VPN 业务", "service"),
    ("07-l2vpn", "07", "SRv6 L2VPN（EVPN）业务", "service"),
    ("08-upa", "08", "不可达前缀通告 UPA", "service"),
    ("09-oam", "09", "SRv6 Ping 与 Traceroute", "service"),
    ("10-deployment", "10", "SRv6 网络部署：地址规划、MTU 与安全", "deploy"),
    ("11-service-programming", "11", "服务编程 Service Programming", "deploy"),
    ("12-sr-aware", "12", "SR-aware 服务与内层报文暴露", "deploy"),
    ("13-sr-proxy", "13", "遗留应用的 SR Proxy", "deploy"),
    ("14-case-bell", "14", "案例：Bell Canada 的 SRv6 地址规划", "case"),
    ("15-case-alibaba", "15", "案例：阿里巴巴核心网 SRv6 设计", "case"),
    ("16-case-bell-sp", "16", "案例：Bell Canada 服务编程落地", "case"),
    ("17-ipv6-essentials", "17", "IPv6 必备知识", "appendix"),
]

GROUPS = [
    ("start", "入门"),
    ("underlay", "Underlay 路由"),
    ("service", "业务与运维"),
    ("deploy", "规划与落地"),
    ("case", "真实案例"),
    ("appendix", "附录"),
]

TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · SRv6 精读</title>
<meta name="description" content="{desc}">
<link rel="stylesheet" href="{root}assets/style.css">
</head>
<body>
<header class="topbar">
  <button class="nav-toggle" aria-label="目录">☰</button>
  <a class="brand" href="{root}index.html">SRv6 精读<span>Segment Routing over IPv6 · Part III</span></a>
  <input id="q" class="search" type="search" placeholder="搜索章节…" autocomplete="off">
</header>
<div class="layout">
  <aside class="sidebar">
    {nav}
  </aside>
  <main class="content">
    <article class="md">
{body}
    </article>
    <nav class="pager">{pager}</nav>
    <footer class="foot">
      <p>内容基于《Segment Routing Part III: SRv6》（Clarence Filsfils 等，2024）整理与讲解，配以工程实践案例。仅供学习交流。</p>
    </footer>
  </main>
  <aside class="toc">{toc}</aside>
</div>
<script src="{root}assets/app.js"></script>
</body>
</html>
"""


EN_RE = re.compile(r"^:::en[ \t]*\r?\n(.*?)^:::[ \t]*$", re.S | re.M)


def preprocess(text):
    """把 :::en ... ::: 块转成可内嵌 Markdown 的 div，形成"一段英文 + 一段中文"对照。"""

    def repl(m):
        return '<div class="en" markdown="1">\n\n%s\n\n</div>\n' % m.group(1).strip()

    return EN_RE.sub(repl, text)


def build_nav(active):
    out = []
    for key, label in GROUPS:
        items = [p for p in PAGES if p[3] == key]
        if not items:
            continue
        out.append('<div class="nav-group"><div class="nav-title">%s</div><ul>' % label)
        for slug, num, title, _ in items:
            cls = ' class="active"' if slug == active else ""
            out.append('<li><a href="%s.html"%s><b>%s</b> %s</a></li>' % (slug, cls, num, title))
        out.append("</ul></div>")
    return "\n".join(out)


def render(active, prev_page, next_page):
    src = os.path.join(CONTENT, active + ".md")
    with open(src, encoding="utf-8") as f:
        text = f.read()

    md = markdown.Markdown(
        extensions=["fenced_code", "tables", "toc", "attr_list", "sane_lists", "md_in_html"],
        extension_configs={"toc": {"toc_depth": "2-3", "anchorlink": False}},
    )
    body = md.convert(preprocess(text))
    toc = md.toc
    if toc:
        toc = '<div class="toc-title">本页目录</div>' + toc

    pager = []
    if prev_page:
        pager.append('<a class="prev" href="%s.html">← %s</a>' % (prev_page[0], prev_page[2]))
    else:
        pager.append("<span></span>")
    if next_page:
        pager.append('<a class="next" href="%s.html">%s →</a>' % (next_page[0], next_page[2]))

    title = next(p[2] for p in PAGES if p[0] == active)
    desc = "%s · SRv6 分章精读（基于 Segment Routing Part III）" % title

    html = TEMPLATE.format(
        title=title,
        desc=desc,
        root="",
        nav=build_nav(active),
        body=body,
        toc=toc,
        pager="".join(p for p in pager if isinstance(p, str)),
    )
    with open(os.path.join(OUT, active + ".html"), "w", encoding="utf-8") as f:
        f.write(html)
    return len(body)


def main():
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    os.makedirs(os.path.join(OUT, "assets"), exist_ok=True)
    shutil.copy(os.path.join(ROOT, "assets", "style.css"), os.path.join(OUT, "assets", "style.css"))
    shutil.copy(os.path.join(ROOT, "assets", "app.js"), os.path.join(OUT, "assets", "app.js"))

    for i, (slug, num, title, _) in enumerate(PAGES):
        prev_page = PAGES[i - 1] if i > 0 else None
        next_page = PAGES[i + 1] if i + 1 < len(PAGES) else None
        size = render(slug, prev_page, next_page)
        print("%-24s %6d bytes body" % (slug, size))

    open(os.path.join(OUT, ".nojekyll"), "w").close()
    print("done ->", OUT)


if __name__ == "__main__":
    main()
