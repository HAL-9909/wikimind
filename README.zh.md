<div align="center">

# 🧠 WikiMind

**Karpathy LLM Wiki 方法的生产级实现。**

[![GitHub Stars](https://img.shields.io/github/stars/HAL-9909/llm-wikimind?style=flat-square)](https://github.com/HAL-9909/llm-wikimind/stargazers)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg?style=flat-square)](https://python.org)
[![MCP](https://img.shields.io/badge/MCP-compatible-green.svg?style=flat-square)](https://modelcontextprotocol.io)

[English](README.md) | **中文**

*基于 [这篇方法论](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) 构建 — 48 小时内获得 1700 万次浏览、88K 收藏。*

</div>

---

## RAG 的问题

每次你向 AI 提问，RAG 都会检索原始文档，然后寄希望于 LLM 自己搞清楚。这很慢、很贵，而且 LLM 每次都要重新理解同样的概念。

2026 年 4 月，Andrej Karpathy 提出了一种更好的方式：

> *"与其对原始文档做 RAG，不如让 LLM 把它们编译成一个活的 Wiki —— 结构化、精心整理、持续改进。你几乎不需要自己写 Wiki，那是 LLM 的工作。"*
>
> — [@karpathy](https://x.com/karpathy/status/2039805659525644595)，1700 万次浏览

WikiMind 就是这个想法的完整实现。**Markdown 文件 + BM25 搜索 + MCP Server。无需 Embedding，无需向量数据库，无需云服务。**

```bash
pip3 install qmd   # 唯一的依赖
```

---

## 工作原理

```
你的笔记 / 文章 / 文档
         │
         ▼
   wiki_ingest_note()          ← AI 写入结构化 Markdown 页面
         │
         ▼
~/Documents/wiki/
  ├── my-domain/
  │   ├── concepts/            ← 原理解释（How/Why）
  │   ├── entities/            ← API 对象、类、组件
  │   ├── comparisons/         ← 横向对比分析
  │   └── sources/             ← 文章摘要
         │
         ▼
      qmd index                ← BM25 搜索索引（即时，本地）
         │
         ▼
   wiki_search("query")        ← AI 回答前先搜索 Wiki
```

AI 构建 Wiki，AI 搜索 Wiki，你只需要提问。

---

## 快速开始

**1. 安装**

```bash
pip3 install qmd
git clone https://github.com/HAL-9909/llm-wikimind
cd llm-wikimind
```

**2. 初始化知识库**

WikiMind 提供两种初始化方式：

```bash
# 方式 A — 全新创建（交互式，会询问存放位置）
./wikimind init

# 方式 B — 接管已有的 Markdown 目录
./wikimind init ~/my-existing-notes --adopt
```

`init` 会自动完成：
- 创建标准知识库目录结构
- 将 MCP Server 和 Watcher 复制到你的知识库
- 构建初始 BM25 搜索索引
- 打印出可直接粘贴到 AI 客户端的配置代码

`--adopt` 模式还会额外扫描每个子目录，为没有 `DOMAIN.md` 的目录自动生成一个（关键词从文件夹名称推导），让你的现有笔记立即可搜索。

**3. 注册 MCP Server**

`init` 命令会打印完整配置。参考如下：

*Claude Desktop* — 添加到 `~/Library/Application Support/Claude/claude_desktop_config.json`：

```json
{
  "mcpServers": {
    "wiki-kb": {
      "command": "python3",
      "args": ["/你的路径/wiki/.wiki-mcp/server.py"],
      "env": { "WIKIMIND_ROOT": "/你的路径/wiki" }
    }
  }
}
```

*CatDesk / OpenClaw：*

```bash
catdesk mcp add --name wiki-kb --json '{
  "command": "python3",
  "args": ["/你的路径/wiki/.wiki-mcp/server.py"],
  "env": {"WIKIMIND_ROOT": "/你的路径/wiki"}
}'
```

**4. 启动 Watcher**

```bash
./wikimind start
```

登录时自动启动：

```bash
echo '/path/to/wikimind/wikimind start > /dev/null 2>&1' >> ~/.zshrc
```

打开新对话，向 AI 提问，它会优先搜索你的 Wiki。

---

## 自动更新：始终保持同步

WikiMind 内置一个轻量级后台 Watcher，安装后全程自动运行，无需任何手动操作。

```
你新建了一个领域文件夹
         │
         ▼（10 秒内）
   Watcher 检测到 DOMAIN.md 变化
         │
         ▼
   sync-wiki-cache.sh 自动运行
         │
         ▼
   MCP 工具描述更新
         │
         ▼
   下次对话：AI 已感知新领域，无需重启
```

以下操作会自动触发同步：

- 新建带 `DOMAIN.md` 的领域目录
- 编辑已有 `DOMAIN.md`（增删关键词）
- 删除某个领域
- AI 调用 `wiki_ingest_note()` 写入新页面

同步会做什么：

- 重新扫描所有领域及其关键词
- 重建 BM25 搜索索引（`qmd update`）
- 更新 MCP 工具描述，让 AI 知道哪些领域存在、哪些关键词触发哪个领域

随时查看 Watcher 状态：

```bash
./wikimind status
```

查看实时日志：

```bash
tail -f /你的路径/wiki/.wiki-mcp/watcher.log
```

---

## 为什么不用 RAG？

| | WikiMind（BM25） | 典型 RAG |
|--|--|--|
| **安装** | `pip install qmd` + `wikimind init` | 向量数据库 + Embedding 模型 + 分块流水线 |
| **费用** | 免费，本地运行 | API 费用或 GPU |
| **延迟** | ~50ms | 200ms–2s |
| **透明度** | 精确关键词匹配，可审计 | 黑盒余弦相似度 |
| **知识质量** | 精心整理、结构化、持续改进 | 原始文档，静态 |
| **索引更新** | 自动（Watcher 后台运行） | 重新 Embed 所有内容 |
| **隐私** | 100% 本地 | 取决于 Embedding 提供商 |

真正的优势不在于搜索算法，而在于 **Wiki 结构**。Karpathy 的洞见：精心整理的结构化知识，永远胜过原始检索。

---

## Wiki 结构

WikiMind 实现了 Karpathy 的四层知识模型：

```
<domain>/
├── DOMAIN.md          ← 领域范围 + 关键词（MCP 自动检测）
├── concepts/          ← "X 是怎么工作的？" — LLM 的理解层
├── entities/          ← "X 是什么？" — API 对象、类、组件
├── comparisons/       ← "X vs Y？" — 横向对比分析
├── sources/           ← "这篇文章说了什么？" — 摘要
└── refs/              ← 原始参考文档（批量导入，只读）
```

每个页面使用标准 frontmatter 格式：

```yaml
---
title: "executeAsModal 模式"
type: concept
domain: adobe-uxp
summary: "所有 Photoshop 文档变更必须包裹在 executeAsModal 中"
tags: ["photoshop", "uxp", "modal"]
confidence: high   # high | medium | low
---
```

---

## CLI 命令

```
wikimind init [PATH]           创建新知识库（不填 PATH 则交互式询问）
wikimind init [PATH] --adopt   接管已有 Markdown 目录
wikimind start                 启动自动同步 Watcher
wikimind stop                  停止 Watcher
wikimind status                查看知识库和 Watcher 状态
wikimind index                 重建完整搜索索引
```

---

## MCP 工具

向任何兼容 MCP 的 AI 客户端暴露 5 个工具：

| 工具 | 功能 |
|------|------|
| `wiki_search` | 跨所有领域的 BM25 搜索 |
| `wiki_get` | 读取指定页面的完整内容 |
| `wiki_list` | 按领域和类型列出页面 |
| `wiki_ingest_note` | 写入新页面 + 更新索引 + 同步缓存 |
| `wiki_domains` | 列出所有已注册领域及其关键词 |

### 零配置领域检测

创建一个带 `keywords` 字段的 `DOMAIN.md`：

```yaml
---
title: "React"
keywords: [react, hooks, nextjs, typescript, jsx]
---
```

10 秒内，Watcher 检测到变化并更新 MCP 工具描述。你的 AI 现在知道 React 相关问题要搜索这个领域。**无需修改配置，无需重启。**

---

## 添加知识

### 通过 AI（推荐）

安装 [wikimind-ingest skill](https://github.com/HAL-9909/llm-wikimind-skill) 后，直接说：

> "把这篇文章加到我的知识库：[粘贴内容或 URL]"

### 通过 MCP 工具

```python
wiki_ingest_note(
  title="React Server Components",
  content="# React Server Components\n\n...",
  domain="frontend",
  page_type="concept",
  source="https://react.dev/blog/2023/03/22/react-labs",
  tags=["react", "rsc"]
)
```

### 批量导入现有文档

```bash
cp -r /你的文档路径 ~/Documents/wiki/my-domain/refs/
wikimind index
```

---

## 配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `WIKIMIND_ROOT` | `~/Documents/wiki` | Wiki 目录路径 |

自动检测旧路径 `~/Documents/知识库`，现有用户无需迁移。

---

## 致谢

WikiMind 是 **Andrej Karpathy** 所描述方法的生产级实现：

- 📝 [LLM Knowledge Bases — GitHub Gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) — 原始方法论
- 🐦 [原始 X 帖子](https://x.com/karpathy/status/2039805659525644595) — 1700 万次浏览，2026 年 4 月

> *"LLM Wiki 不是 RAG 系统。它是一个 LLM 维护和查询的活文档。LLM 是作者，你是编辑。"*

同时基于 [qmd](https://github.com/qmd-project/qmd) 和 [Model Context Protocol](https://modelcontextprotocol.io) 构建。

---

## 贡献

欢迎 PR。重点方向：更多 AI 客户端支持（Cursor、Zed）、Obsidian vault 集成、Web UI。

---

<div align="center">

**如果这让你省去了又一次搭建向量数据库的麻烦，请给个 ⭐**

</div>
