<div align="center">

# 🧠 WikiMind

**The production-ready implementation of Karpathy's LLM Wiki pattern.**

[![GitHub Stars](https://img.shields.io/github/stars/HAL-9909/llm-wikimind?style=flat-square)](https://github.com/HAL-9909/llm-wikimind/stargazers)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg?style=flat-square)](https://python.org)
[![MCP](https://img.shields.io/badge/MCP-compatible-green.svg?style=flat-square)](https://modelcontextprotocol.io)

**English** | [中文](README.zh.md)

*Built on [the methodology](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) that got 17M views and 88K bookmarks in 48 hours.*

</div>

---

## The problem with RAG

Every time you ask your AI a question, RAG retrieves raw documents and hopes the LLM figures it out. It's slow, expensive, and the LLM has to re-understand the same concepts over and over.

In April 2026, Andrej Karpathy proposed a better way:

> *"Instead of RAG over raw docs, have the LLM compile them into a living Wiki — structured, curated, always improving. You almost never have to write the Wiki yourself. That's the LLM's job."*
>
> — [@karpathy](https://x.com/karpathy/status/2039805659525644595), 17M views

WikiMind is that idea, fully implemented. **Markdown files + BM25 search + MCP server. No embeddings. No vector DB. No cloud.**

```bash
pip3 install qmd   # that's the only dependency
```

---

## How it works

```
Your notes / articles / docs
         │
         ▼
   wiki_ingest_note()          ← AI writes structured Markdown pages
         │
         ▼
~/Documents/wiki/
  ├── my-domain/
  │   ├── concepts/            ← How/why explanations
  │   ├── entities/            ← API objects, classes
  │   ├── comparisons/         ← Side-by-side analysis
  │   └── sources/             ← Article summaries
         │
         ▼
      qmd index                ← BM25 search index (instant, local)
         │
         ▼
   wiki_search("query")        ← AI searches before answering
```

Your AI builds the Wiki. Your AI searches the Wiki. You just ask questions.

---

## Quick Start

**1. Install**

```bash
pip3 install qmd
git clone https://github.com/HAL-9909/llm-wikimind
cd llm-wikimind
```

**2. Initialize your wiki**

WikiMind gives you two paths:

```bash
# Option A — Create a fresh wiki (interactive, asks where to put it)
./wikimind init

# Option B — Adopt an existing Markdown directory
./wikimind init ~/my-existing-notes --adopt
```

`init` will:
- Create the standard wiki directory structure
- Copy the MCP server and watcher into your wiki
- Build the initial BM25 search index
- Print the exact config snippet to paste into your AI client

`--adopt` will additionally scan every subdirectory and auto-generate a `DOMAIN.md` for each one (with keywords derived from the folder name), so your existing notes are immediately searchable.

**3. Register the MCP server**

The `init` command prints the exact snippet. For reference:

*Claude Desktop* — add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "wiki-kb": {
      "command": "python3",
      "args": ["/YOUR/PATH/wiki/.wiki-mcp/server.py"],
      "env": { "WIKIMIND_ROOT": "/YOUR/PATH/wiki" }
    }
  }
}
```

*CatDesk / OpenClaw:*

```bash
catdesk mcp add --name wiki-kb --json '{
  "command": "python3",
  "args": ["/YOUR/PATH/wiki/.wiki-mcp/server.py"],
  "env": {"WIKIMIND_ROOT": "/YOUR/PATH/wiki"}
}'
```

**4. Start the watcher**

```bash
./wikimind start
```

Auto-start on login:

```bash
echo '/path/to/wikimind/wikimind start > /dev/null 2>&1' >> ~/.zshrc
```

Open a new conversation. Ask your AI anything. It will search your wiki first.

---

## Auto-update: always in sync

WikiMind runs a lightweight background watcher that keeps everything in sync automatically — no manual steps required after setup.

```
You add a new domain folder
         │
         ▼ (within 10 seconds)
   watcher detects DOMAIN.md change
         │
         ▼
   sync-wiki-cache.sh runs
         │
         ▼
   MCP tool descriptions updated
         │
         ▼
   Next conversation: AI already knows the new domain
```

What triggers an automatic sync:

- You create a new domain folder with a `DOMAIN.md`
- You edit an existing `DOMAIN.md` (add/remove keywords)
- You delete a domain
- The AI calls `wiki_ingest_note()` to write a new page

What the sync does:

- Re-scans all domains and their keywords
- Rebuilds the BM25 search index (`qmd update`)
- Updates the MCP tool descriptions so the AI knows which domains exist and what keywords trigger each one

You can check the watcher status at any time:

```bash
./wikimind status
```

And view the live log:

```bash
tail -f /path/to/wiki/.wiki-mcp/watcher.log
```

---

## Why not RAG?

| | WikiMind (BM25) | Typical RAG |
|--|--|--|
| **Setup** | `pip install qmd` + `wikimind init` | Vector DB + embedding model + chunking pipeline |
| **Cost** | Free, runs locally | API costs or GPU required |
| **Latency** | ~50ms | 200ms–2s |
| **Transparency** | Exact keyword match, auditable | Black-box cosine similarity |
| **Knowledge quality** | Curated, structured, always improving | Raw docs, static |
| **Index update** | Automatic (watcher) | Re-embed everything |
| **Privacy** | 100% local | Depends on your embedding provider |

The real advantage isn't the search algorithm — it's the **Wiki structure**. Karpathy's insight: curated, structured knowledge beats raw retrieval every time.

---

## The Wiki structure

WikiMind implements Karpathy's four-layer knowledge model:

```
<domain>/
├── DOMAIN.md          ← Domain scope + keywords (auto-detected by MCP)
├── concepts/          ← "How does X work?" — the LLM's understanding layer
├── entities/          ← "What is X?" — API objects, classes, components
├── comparisons/       ← "X vs Y?" — side-by-side analysis
├── sources/           ← "What did this article say?" — summaries
└── refs/              ← Raw reference docs (bulk import, read-only)
```

Every page uses a standard frontmatter schema:

```yaml
---
title: "executeAsModal Pattern"
type: concept
domain: adobe-uxp
summary: "All Photoshop document mutations must be wrapped in executeAsModal"
tags: ["photoshop", "uxp", "modal"]
confidence: high   # high | medium | low
---
```

---

## MCP Tools

5 tools exposed to any MCP-compatible AI client:

| Tool | What it does |
|------|-------------|
| `wiki_search` | BM25 search across all domains |
| `wiki_get` | Read a specific page in full |
| `wiki_list` | List pages by domain and type |
| `wiki_ingest_note` | Write a new page + update index + sync cache |
| `wiki_domains` | List all registered domains and their keywords |

### Zero-config domain detection

Create a `DOMAIN.md` with a `keywords` field:

```yaml
---
title: "React"
keywords: [react, hooks, nextjs, typescript, jsx]
---
```

Within 10 seconds, the watcher detects the change and updates the MCP tool descriptions. Your AI now knows to search this domain for React questions. **No config changes. No restarts.**

---

## CLI reference

```
wikimind init [PATH]           Create a new wiki (interactive if PATH omitted)
wikimind init [PATH] --adopt   Adopt an existing Markdown directory
wikimind start                 Start the auto-sync watcher
wikimind stop                  Stop the watcher
wikimind status                Show wiki and watcher status
wikimind index                 Rebuild the full search index
```

---

## Adding knowledge

### Via AI (recommended)

With the [wikimind-ingest skill](https://github.com/HAL-9909/llm-wikimind-skill) installed in CatDesk/OpenClaw:

> "Add this article to my knowledge base: [paste content or URL]"

### Via MCP tool

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

### Bulk import existing docs

```bash
cp -r /path/to/your/docs ~/Documents/wiki/my-domain/refs/
wikimind index
```

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `WIKIMIND_ROOT` | `~/Documents/wiki` | Path to your wiki directory |

Auto-detects legacy path `~/Documents/知识库` for existing users.

---

## Acknowledgements

WikiMind is a production implementation of the pattern described by **Andrej Karpathy**:

- 📝 [LLM Knowledge Bases — GitHub Gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) — the original methodology
- 🐦 [Original X thread](https://x.com/karpathy/status/2039805659525644595) — 17M views, April 2026

> *"The LLM Wiki is not a RAG system. It's a living document that the LLM maintains and queries. The LLM is the author, you are the editor."*

Also built on [qmd](https://github.com/qmd-project/qmd) and [Model Context Protocol](https://modelcontextprotocol.io).

---

## Contributing

PRs welcome. Key areas: more AI client support (Cursor, Zed), Obsidian vault integration, web UI.

---

<div align="center">

**If this saves you from setting up yet another vector database, give it a ⭐**

</div>
