#!/usr/bin/env python3
"""
Wiki MCP Server — 动态多领域版
启动时扫描知识库目录，自动感知所有领域，动态生成工具描述。
新增领域只需创建 DOMAIN.md，重启 server 即可生效。

工具：
  - wiki_search      : 关键词搜索知识库（优先于网络搜索）
  - wiki_get         : 读取指定页面完整内容
  - wiki_list        : 列出某个领域的页面
  - wiki_ingest_note : 将笔记/文章摘要写入知识库
  - wiki_domains     : 列出所有已注册领域及其关键词
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path
import datetime

# WIKI_ROOT 优先读环境变量 WIKIMIND_ROOT，fallback 到 ~/Documents/wiki
# 兼容旧路径：如果 ~/Documents/wiki 不存在但 ~/Documents/知识库 存在，自动使用后者
def _resolve_wiki_root() -> Path:
    env = os.environ.get("WIKIMIND_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    default = Path.home() / "Documents" / "wiki"
    legacy = Path.home() / "Documents" / "知识库"
    if not default.exists() and legacy.exists():
        return legacy
    return default

WIKI_ROOT = _resolve_wiki_root()

# ── 动态领域感知 ───────────────────────────────────────────────────────────────

def scan_domains() -> list[dict]:
    """
    扫描知识库目录，读取每个领域的 DOMAIN.md。
    返回领域列表，每项包含：
      - name       : 目录名，如 "adobe-uxp"
      - title      : 领域标题
      - keywords   : 触发关键词列表（从 DOMAIN.md 的 keywords: 字段读取）
      - doc_count  : 文档数（粗略统计）
    """
    domains = []
    if not WIKI_ROOT.exists():
        return domains

    for d in sorted(WIKI_ROOT.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        domain_file = d / "DOMAIN.md"
        if not domain_file.exists():
            continue

        info = {"name": d.name, "title": d.name, "keywords": [], "doc_count": 0}

        try:
            text = domain_file.read_text(encoding="utf-8")

            # 提取 frontmatter（如果有）
            if text.startswith("---"):
                parts = text.split("---", 2)
                if len(parts) >= 3:
                    fm = parts[1]
                    for line in fm.splitlines():
                        if line.startswith("title:"):
                            info["title"] = line.split(":", 1)[1].strip().strip('"')
                        elif line.startswith("keywords:"):
                            # 支持 keywords: [a, b, c] 或 keywords: a, b, c
                            raw = line.split(":", 1)[1].strip()
                            raw = raw.strip("[]")
                            info["keywords"] = [k.strip().strip('"\'') for k in raw.split(",") if k.strip()]

            # 如果 frontmatter 没有 keywords，从正文的 ## 关键词 / keywords 段落提取
            if not info["keywords"]:
                info["keywords"] = _extract_keywords_from_body(text, d.name)

            # 统计文档数（只数 md 文件，排除 refs/）
            info["doc_count"] = sum(
                1 for f in d.rglob("*.md")
                if "refs" not in f.relative_to(d).parts
            )

        except Exception:
            pass

        domains.append(info)

    return domains


def _extract_keywords_from_body(text: str, domain_name: str) -> list[str]:
    """
    从 DOMAIN.md 正文中提取关键词。
    策略：
    1. 找 "## 关键词" 或 "## Keywords" 段落，提取列表项
    2. 找 "| 概念 |" 表格第一列
    3. fallback：用领域目录名拆分
    """
    keywords = set()

    lines = text.splitlines()
    in_keywords_section = False
    in_table = False

    for line in lines:
        # 检测关键词段落
        if re.match(r"^#{1,3}\s*(关键词|keywords|Keywords|触发词)", line, re.I):
            in_keywords_section = True
            continue
        if in_keywords_section:
            if line.startswith("#"):
                in_keywords_section = False
            elif line.strip().startswith("-") or line.strip().startswith("*"):
                kw = re.sub(r"^[-*]\s*`?([^`\n]+)`?.*", r"\1", line.strip())
                if kw and len(kw) < 40:
                    keywords.add(kw.strip())

        # 从概念速览表格提取第一列（概念名）
        if "| 概念 |" in line or "| Concept |" in line:
            in_table = True
            continue
        if in_table:
            if not line.startswith("|"):
                in_table = False
            elif line.startswith("|--") or line.startswith("| --"):
                continue
            else:
                cols = [c.strip() for c in line.split("|") if c.strip()]
                if cols:
                    kw = cols[0].strip("`")
                    if kw and len(kw) < 40 and kw not in ("概念", "Concept"):
                        keywords.add(kw)

    # fallback：用领域名本身
    if not keywords:
        keywords.update(domain_name.replace("-", " ").split())

    return sorted(keywords)[:20]  # 最多 20 个关键词


def build_search_description(domains: list[dict]) -> str:
    """
    根据扫描到的领域动态生成 wiki_search 工具描述。
    """
    if not domains:
        return "搜索个人本地知识库。"

    domain_lines = []
    all_keywords = []
    for d in domains:
        kws = "、".join(d["keywords"][:8]) if d["keywords"] else d["name"]
        domain_lines.append(f"  • {d['title']}（{d['name']}）：{kws}")
        all_keywords.extend(d["keywords"][:5])

    domains_str = "\n".join(domain_lines)
    total_docs = sum(d["doc_count"] for d in domains)

    return (
        f"【优先使用】搜索个人本地知识库，包含 {total_docs}+ 精选文档。\n\n"
        f"已收录领域：\n{domains_str}\n\n"
        f"当用户询问以上任何领域的相关问题时，必须先调用此工具，而不是网络搜索。"
        f"只有本工具返回空结果时，才 fallback 到网络搜索。"
    )


# 启动时扫描一次，缓存结果
_DOMAINS: list[dict] = []
_SEARCH_DESC: str = ""

def _init_domains():
    global _DOMAINS, _SEARCH_DESC
    _DOMAINS = scan_domains()
    _SEARCH_DESC = build_search_description(_DOMAINS)

_init_domains()


# ── MCP 协议实现 ──────────────────────────────────────────────────────────────

def send(obj: dict):
    line = json.dumps(obj, ensure_ascii=False)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()

def recv() -> dict | None:
    line = sys.stdin.readline()
    if not line:
        return None
    return json.loads(line.strip())


# ── 工具实现 ──────────────────────────────────────────────────────────────────

def wiki_search(query: str, domain: str = None, limit: int = 10) -> str:
    """使用 qmd 搜索知识库，fallback 到 grep"""
    try:
        cmd = ["qmd", "search", query, "--limit", str(limit)]
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            cwd=str(WIKI_ROOT), timeout=15
        )
        output = result.stdout.strip()
        if not output or "找到 0 个结果" in output:
            return grep_search(query, domain, limit)

        # 过滤指定领域
        if domain:
            blocks = _split_qmd_blocks(output)
            filtered = [b for b in blocks if domain in b]
            return "\n\n".join(filtered) if filtered else grep_search(query, domain, limit)

        return output
    except Exception:
        return grep_search(query, domain, limit)


def _split_qmd_blocks(output: str) -> list[str]:
    """将 qmd 输出按结果编号分割成 block 列表"""
    blocks = []
    current = []
    for line in output.split("\n"):
        if re.match(r"^\d+\.", line):
            if current:
                blocks.append("\n".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        blocks.append("\n".join(current))
    return blocks


def grep_search(query: str, domain: str = None, limit: int = 10) -> str:
    """grep fallback 搜索"""
    search_dir = WIKI_ROOT / domain if domain else WIKI_ROOT
    if not search_dir.exists():
        available = [d["name"] for d in _DOMAINS]
        return f"领域 '{domain}' 不存在。可用领域: {', '.join(available)}"
    try:
        result = subprocess.run(
            ["grep", "-r", "-l", "-i", query, str(search_dir), "--include=*.md"],
            capture_output=True, text=True, timeout=10
        )
        files = [f for f in result.stdout.strip().split("\n") if f][:limit]
        if not files:
            return f"知识库中未找到 '{query}' 的相关内容。"

        results = []
        for fp in files:
            path = Path(fp)
            try:
                content = path.read_text(encoding="utf-8")
                title, summary = path.stem, ""
                for line in content.split("\n")[:15]:
                    if line.startswith("title:"):
                        title = line.split(":", 1)[1].strip().strip('"')
                    elif line.startswith("summary:"):
                        summary = line.split(":", 1)[1].strip().strip('"')[:120]
                rel = path.relative_to(WIKI_ROOT)
                results.append(f"• {title}\n  路径: {rel}\n  摘要: {summary}")
            except Exception:
                results.append(f"• {path.name}")

        return f"找到 {len(results)} 个结果:\n\n" + "\n\n".join(results)
    except Exception as e:
        return f"搜索失败: {e}"


def wiki_get(path: str) -> str:
    """读取指定 wiki 页面，支持模糊匹配"""
    target = WIKI_ROOT / path
    if not target.exists():
        name = Path(path).name
        matches = list(WIKI_ROOT.rglob(f"*{name}*"))
        if not matches:
            matches = list(WIKI_ROOT.rglob(f"*{name.lower()}*"))
        if matches:
            target = matches[0]
        else:
            return f"页面不存在: {path}\n\n提示：使用 wiki_search 先搜索页面路径"
    try:
        content = target.read_text(encoding="utf-8")
        rel = target.relative_to(WIKI_ROOT)
        return f"# 文件路径: {rel}\n\n{content}"
    except Exception as e:
        return f"读取失败: {e}"


def wiki_list(domain: str = None, page_type: str = None) -> str:
    """列出知识库页面，可按领域和类型过滤"""
    search_dir = WIKI_ROOT / domain if domain else WIKI_ROOT
    if not search_dir.exists():
        available = [d["name"] for d in _DOMAINS]
        return f"领域 '{domain}' 不存在\n\n可用领域: {', '.join(available)}"

    results = []
    for md_file in sorted(search_dir.rglob("*.md")):
        parts = md_file.relative_to(search_dir).parts
        if "refs" in parts and page_type != "refs":
            continue
        try:
            content = md_file.read_text(encoding="utf-8")
            title, ftype, summary = md_file.stem, "", ""
            for line in content.split("\n")[:15]:
                if line.startswith("title:"):
                    title = line.split(":", 1)[1].strip().strip('"')
                elif line.startswith("type:"):
                    ftype = line.split(":", 1)[1].strip()
                elif line.startswith("summary:"):
                    summary = line.split(":", 1)[1].strip().strip('"')[:100]
            if page_type and ftype != page_type:
                continue
            rel = md_file.relative_to(WIKI_ROOT)
            results.append(f"[{ftype or '?'}] {title}\n  {rel}\n  {summary}")
        except Exception:
            pass

    if not results:
        return f"没有找到页面（领域: {domain}, 类型: {page_type}）"

    header = "知识库页面列表"
    if domain:
        header += f" — {domain}"
    if page_type:
        header += f" ({page_type})"
    return f"{header}\n共 {len(results)} 个页面\n\n" + "\n\n".join(results[:50])


def wiki_domains() -> str:
    """列出所有已注册领域及其关键词（实时重新扫描）"""
    _init_domains()  # 重新扫描，确保最新
    if not _DOMAINS:
        return f"知识库目录为空: {WIKI_ROOT}"

    lines = [f"知识库路径: {WIKI_ROOT}", f"共 {len(_DOMAINS)} 个领域\n"]
    for d in _DOMAINS:
        kws = ", ".join(d["keywords"]) if d["keywords"] else "（无关键词）"
        lines.append(f"## {d['title']} ({d['name']})")
        lines.append(f"  文档数: {d['doc_count']}")
        lines.append(f"  关键词: {kws}")
        lines.append("")

    return "\n".join(lines)


def wiki_ingest_note(title: str, content: str, domain: str,
                     page_type: str = "source-summary",
                     source: str = "", summary: str = "",
                     tags: list = None) -> str:
    """将笔记写入知识库，自动生成 frontmatter 并更新索引"""
    today = datetime.date.today().isoformat()
    tags_str = json.dumps(tags or [], ensure_ascii=False)

    if not summary:
        clean = content.replace("#", "").replace("*", "").strip()
        summary = clean[:120].replace("\n", " ")

    filename = re.sub(r"[^\w\s-]", "", title.lower())
    filename = re.sub(r"[\s_]+", "-", filename)
    filename = filename[:60] + ".md"

    type_dir_map = {
        "concept": "concepts",
        "entity": "entities",
        "comparison": "comparisons",
        "source-summary": "sources",
    }
    subdir = type_dir_map.get(page_type, "sources")
    target_dir = WIKI_ROOT / domain / subdir
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / filename

    frontmatter = (
        f'---\ntitle: "{title}"\ntype: {page_type}\ndomain: {domain}\n'
        f'source: "{source}"\nsummary: "{summary}"\ntags: {tags_str}\n'
        f'related: []\ncreated: {today}\nupdated: {today}\nconfidence: medium\n---\n\n'
    )
    target_file.write_text(frontmatter + content, encoding="utf-8")

    # 更新 qmd 索引
    try:
        subprocess.run(["qmd", "update"], cwd=str(WIKI_ROOT), timeout=30, capture_output=True)
    except Exception:
        pass

    # 追加 log.md
    log_file = WIKI_ROOT / domain / "log.md"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"\n## [{today}] ingest | {title} | {domain}\n")

    # 重新扫描领域（文档数可能变化）
    _init_domains()

    # 异步更新 CatDesk 缓存（不阻塞响应）
    sync_script = Path(__file__).parent / "sync-wiki-cache.sh"
    if sync_script.exists():
        try:
            subprocess.Popen(
                ["bash", str(sync_script)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
        except Exception:
            pass

    return f"已写入知识库: {target_file.relative_to(WIKI_ROOT)}\n搜索索引已更新。"


# ── 动态工具列表 ──────────────────────────────────────────────────────────────

def get_tools() -> list[dict]:
    """每次 tools/list 请求时动态生成，确保描述反映最新领域状态"""
    return [
        {
            "name": "wiki_search",
            "description": _SEARCH_DESC,
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词，支持中英文"},
                    "domain": {
                        "type": "string",
                        "description": f"限定搜索领域（可选）。可用值: {', '.join(d['name'] for d in _DOMAINS)}。不填则搜索全库"
                    },
                    "limit": {"type": "integer", "description": "返回结果数量，默认 10", "default": 10}
                },
                "required": ["query"]
            }
        },
        {
            "name": "wiki_get",
            "description": "读取知识库中指定页面的完整内容。支持相对路径或页面名称模糊匹配。",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "页面路径（相对于知识库根目录）或页面名称"}
                },
                "required": ["path"]
            }
        },
        {
            "name": "wiki_list",
            "description": "列出知识库中的页面，可按领域和类型过滤。不包含 refs/ 下的原始参考文档。",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": f"领域名称。可用值: {', '.join(d['name'] for d in _DOMAINS)}"
                    },
                    "page_type": {"type": "string", "description": "页面类型：concept / entity / comparison / source-summary / refs"}
                }
            }
        },
        {
            "name": "wiki_domains",
            "description": "列出知识库中所有已注册的领域及其关键词。新增领域后可调用此工具确认是否已被感知。",
            "inputSchema": {"type": "object", "properties": {}}
        },
        {
            "name": "wiki_ingest_note",
            "description": "将笔记、文章摘要或新知识写入知识库，自动生成 frontmatter 并更新搜索索引。",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "页面标题"},
                    "content": {"type": "string", "description": "页面正文内容（Markdown 格式）"},
                    "domain": {
                        "type": "string",
                        "description": f"所属领域。已有领域: {', '.join(d['name'] for d in _DOMAINS)}。填新名称可自动创建新领域目录"
                    },
                    "page_type": {"type": "string", "description": "页面类型：concept / entity / comparison / source-summary", "default": "source-summary"},
                    "source": {"type": "string", "description": "原始来源 URL 或描述"},
                    "summary": {"type": "string", "description": "一句话摘要（可选，不填自动生成）"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "标签列表"}
                },
                "required": ["title", "content", "domain"]
            }
        }
    ]


# ── MCP 协议处理 ──────────────────────────────────────────────────────────────

def handle_request(req: dict) -> dict | None:
    method = req.get("method", "")
    req_id = req.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0", "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "wiki-mcp", "version": "2.0.0"}
            }
        }

    elif method == "tools/list":
        return {
            "jsonrpc": "2.0", "id": req_id,
            "result": {"tools": get_tools()}
        }

    elif method == "tools/call":
        tool_name = req.get("params", {}).get("name", "")
        args = req.get("params", {}).get("arguments", {})
        try:
            if tool_name == "wiki_search":
                result = wiki_search(args["query"], args.get("domain"), args.get("limit", 10))
            elif tool_name == "wiki_get":
                result = wiki_get(args["path"])
            elif tool_name == "wiki_list":
                result = wiki_list(args.get("domain"), args.get("page_type"))
            elif tool_name == "wiki_domains":
                result = wiki_domains()
            elif tool_name == "wiki_ingest_note":
                result = wiki_ingest_note(
                    args["title"], args["content"], args["domain"],
                    args.get("page_type", "source-summary"),
                    args.get("source", ""), args.get("summary", ""),
                    args.get("tags", [])
                )
            else:
                result = f"未知工具: {tool_name}"

            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {"content": [{"type": "text", "text": result}]}
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {"content": [{"type": "text", "text": f"工具执行失败: {e}"}]}
            }

    elif method == "notifications/initialized":
        return None

    else:
        return {
            "jsonrpc": "2.0", "id": req_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"}
        }


def main():
    while True:
        try:
            req = recv()
            if req is None:
                break
            resp = handle_request(req)
            if resp is not None:
                send(resp)
        except KeyboardInterrupt:
            break
        except Exception as e:
            send({"jsonrpc": "2.0", "id": None,
                  "error": {"code": -32700, "message": f"Parse error: {e}"}})


if __name__ == "__main__":
    main()
