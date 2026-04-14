#!/bin/bash
# Start the wiki-kb watcher (if not already running).
# Reads WIKIMIND_ROOT from environment; falls back to ~/Documents/wiki.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Resolve wiki root (same logic as server.py)
if [[ -n "${WIKIMIND_ROOT:-}" ]]; then
    WIKI_ROOT="$WIKIMIND_ROOT"
elif [[ -d "$HOME/Documents/wiki" ]]; then
    WIKI_ROOT="$HOME/Documents/wiki"
elif [[ -d "$HOME/Documents/知识库" ]]; then
    WIKI_ROOT="$HOME/Documents/知识库"
else
    WIKI_ROOT="$HOME/Documents/wiki"
fi

PIDFILE="$SCRIPT_DIR/watcher.pid"
LOGFILE="$SCRIPT_DIR/watcher.log"

if [[ -f "$PIDFILE" ]]; then
    PID=$(cat "$PIDFILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "watcher already running (pid $PID)"
        exit 0
    fi
    rm -f "$PIDFILE"
fi

WIKIMIND_ROOT="$WIKI_ROOT" nohup python3 "$SCRIPT_DIR/watcher.py" >> "$LOGFILE" 2>&1 &
echo $! > "$PIDFILE"
echo "watcher started (pid $!) — watching $WIKI_ROOT"
