# SRv6 分章精读

《Segment Routing Part III: SRv6》(Clarence Filsfils 等, 2024) 的中英对照读书笔记站点，共 17 章 + 导读，每章含原书英文节选、中文精讲、配置示例与实战案例。

## 站点结构

```
content/       Markdown 源文件（每章一个）
build.py       静态站点生成器（Markdown -> docs/*.html）
assets/        style.css / app.js
docs/          生成结果，GitHub Pages 直接服务此目录
```

## 本地构建与预览

```bash
python build.py
python -m http.server 8000 --directory docs
# 打开 http://localhost:8000
```

依赖：`markdown`（`pip install markdown`）。

## 双语写法约定

正文中英文对照用自定义块，`build.py` 会转成带 `EN` 标记的灰底块：

```
:::en
English excerpt from the book.
:::

对应的中文讲解段落。
```

## 部署

GitHub Pages：仓库 Settings → Pages → Source 选 `Deploy from a branch`，分支 `main`，目录 `/docs`。

> 内容为学习笔记，非官方译本；观点引用已标注原书章节，准确表述以 RFC 与原著为准。
