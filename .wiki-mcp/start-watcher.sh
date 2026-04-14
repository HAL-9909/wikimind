#!/bin/bash
# 启动 wiki-kb watcher（如果还没在运行）
PIDFILE="$HOME/.wiki-mcp/watcher.pid"
LOGFILE="$HOME/.wiki-mcp/watcher.log"

if [[ -f "$PIDFILE" ]]; then
    PID=$(cat "$PIDFILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "watcher already running (pid $PID)"
        exit 0
    fi
fi

nohup python3 "$HOME/.wiki-mcp/watcher.py" >> "$LOGFILE" 2>&1 &
echo $! > "$PIDFILE"
echo "watcher started (pid $!)"
