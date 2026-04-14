# 个人知识库 — LLM Wiki

> 基于 Andrej Karpathy 的 LLM Wiki 方法。
> **LLM 是这个 wiki 的作者，你是主编。**
> 每次对话开始时，先读本文件，再读 `index.md`，再按需深入具体领域。

---

## 知识库路径

```
~/Documents/知识库/
```

## 领域目录

| 领域 | 路径 | 说明 |
|------|------|------|
| Adobe UXP 插件开发 | `adobe-uxp/` | Photoshop/InDesign UXP 插件全栈知识 |

> 新增领域时，在此表格添加一行，并创建对应目录和 `DOMAIN.md`。

---

## 新增领域步骤

1. 在 `~/Documents/知识库/` 下创建新目录，如 `my-domain/`
2. 创建 `DOMAIN.md`，**必须包含 frontmatter 的 `keywords` 字段**（MCP server 靠它自动感知触发词）：

```yaml
---
title: "领域名称"
keywords: [关键词1, 关键词2, 关键词3, ...]
---
```

3. 在上方领域目录表格中添加一行
4. MCP server 会在下次 `tools/list` 请求时自动感知新领域，无需重启或修改任何配置

---

## 每个领域的目录结构

```
<domain>/
├── DOMAIN.md          ← 领域说明、范围、关键概念速览（含 keywords frontmatter）
├── index.md           ← 领域内页面索引（每次 ingest 后更新）
├── log.md             ← 操作日志（追加式）
│
├── concepts/          ← 核心概念综合页（LLM 理解层）
│   └── *.md           ← 如：executeAsModal-pattern.md
│
├── entities/          ← 关键实体页（API 类、组件、工具等）
│   └── *.md           ← 如：Document.md、Layer.md
│
├── comparisons/       ← 对比分析页
│   └── *.md           ← 如：uxp-vs-browser.md
│
├── sources/           ← 原始资料摘要页（每个来源一个文件）
│   └── *.md
│
└── refs/              ← 参考文档（批量抓取的原始 wiki，只读）
    └── **/*.md
```

---

## Wiki 页面规范

所有 wiki 页面（concepts/entities/comparisons/sources）必须包含：

```yaml
---
title: "页面标题"
type: concept | entity | comparison | source-summary
domain: adobe-uxp | <其他领域>
source: "原始 URL 或文件路径（多个用列表）"
summary: "一句话摘要（≤150字，中文）"
related: ["[[相关页面1]]", "[[相关页面2]]"]
created: YYYY-MM-DD
updated: YYYY-MM-DD
confidence: high | medium | low
---
```

refs/ 下的参考文档使用独立的 frontmatter（见各领域 DOMAIN.md）。

---

## 三大核心操作

### Ingest（摄入新知识）

```
用户说：「把这篇文章加入知识库」或「ingest 这个 URL」
```

执行步骤：
1. 读取原始资料（URL/文件/粘贴内容）
2. 在 `sources/` 创建摘要页
3. 扫描 `concepts/` 和 `entities/`，更新所有相关页面
4. 如果涉及新概念，在 `concepts/` 创建新页面
5. 更新 `index.md`，追加 `log.md`
6. 运行 `qmd update` 更新搜索索引

### Query（查询）

```
用户问：「UXP 里怎么创建图层？」
```

执行步骤：
1. 先读 `index.md` 定位相关页面
2. 优先读 `concepts/` 和 `entities/`（理解层）
3. 按需深入 `refs/`（细节层）
4. 综合回答，用 `[[wikilinks]]` 引用来源
5. 有价值的回答可回存为新 wiki 页面

### Lint（健康检查）

```
用户说：「lint 知识库」
```

检查项：
- 孤立页面（无入链）
- 空 related 字段的 concepts 页
- 被提及但未创建的概念
- 过时内容（source URL 已更新）
- 矛盾的描述

---

## 搜索工具（qmd）

```bash
# 在知识库根目录运行
cd ~/Documents/知识库
qmd search "关键词"
qmd status
qmd update   # 内容更新后重建索引
```

---

## 日志格式

```markdown
## [YYYY-MM-DD] ingest | <来源描述> | <领域>
## [YYYY-MM-DD] concept | <新建概念页名称> | <领域>
## [YYYY-MM-DD] lint | <发现问题数> issues
```
