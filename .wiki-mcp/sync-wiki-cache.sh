#!/bin/bash
# sync-wiki-cache.sh
# 从 wiki-mcp server 拉取最新工具描述，更新 CatDesk 缓存文件。
# 触发时机：
#   1. wiki_ingest_note 写入后自动调用
#   2. launchd 监听知识库目录变化后调用
#   3. 手动运行：bash sync-wiki-cache.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVER_PY="$SCRIPT_DIR/server.py"
CACHE_DIR="$HOME/.catpaw/projects/Users-liuxiangmian-.openclaw-agency-agents-hal/mcps/sdk-wiki-kb/tools"
LOG_FILE="$SCRIPT_DIR/sync.log"
TMP_OUT=$(mktemp /tmp/wiki-sync-XXXXXX.json)
trap 'rm -f "$TMP_OUT"' EXIT

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# ── 1. 确认 server 和缓存目录存在 ─────────────────────────────────────────────
if [[ ! -f "$SERVER_PY" ]]; then
    log "ERROR: server.py 不存在: $SERVER_PY"
    exit 1
fi

if [[ ! -d "$CACHE_DIR" ]]; then
    log "ERROR: CatDesk 缓存目录不存在: $CACHE_DIR"
    log "  可能原因：wiki-kb MCP server 尚未注册，或项目路径已变化"
    exit 1
fi

# ── 2. 向 server 发送 tools/list 请求，获取最新工具描述 ───────────────────────
printf '%s\n%s\n' \
    '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"sync","version":"1.0"}}}' \
    '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' \
    | python3 "$SERVER_PY" 2>/dev/null \
    | tail -1 > "$TMP_OUT"

if [[ ! -s "$TMP_OUT" ]]; then
    log "ERROR: server 无响应或输出为空"
    exit 1
fi

# ── 3. 解析并写入各工具的缓存文件 ─────────────────────────────────────────────
python3 - "$TMP_OUT" "$CACHE_DIR" <<'PYEOF'
import json, sys
from pathlib import Path

tmp_file = Path(sys.argv[1])
cache_dir = Path(sys.argv[2])

try:
    resp = json.loads(tmp_file.read_text(encoding="utf-8"))
    tools = resp["result"]["tools"]
except Exception as e:
    print(f"PARSE_ERROR: {e}", file=sys.stderr)
    sys.exit(1)

updated = 0
for tool in tools:
    name = tool["name"]
    target = cache_dir / f"{name}.json"
    new_content = json.dumps(tool, ensure_ascii=False, indent=2)

    # 只在内容有变化时写入
    if target.exists() and target.read_text(encoding="utf-8") == new_content:
        continue

    target.write_text(new_content, encoding="utf-8")
    print(f"  UPDATED: {name}.json")
    updated += 1

# 删除 server 已不再提供的旧工具缓存
current_names = {t["name"] for t in tools}
for f in cache_dir.glob("*.json"):
    if f.stem not in current_names:
        f.unlink()
        print(f"  REMOVED: {f.name}")

print(f"DONE: {updated} files updated, {len(tools)} tools total")
PYEOF

log "sync complete"
