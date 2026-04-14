#!/usr/bin/env python3
"""
wiki-kb watcher
监听知识库目录中所有 DOMAIN.md 文件的变化，自动触发 sync-wiki-cache.sh。

原理：每 10 秒扫描一次所有 DOMAIN.md 的 mtime，有变化则触发 sync。
不依赖 fswatch/watchdog，只用标准库。
"""

import os
import subprocess
import time
from pathlib import Path

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
SYNC_SCRIPT = Path(__file__).parent / "sync-wiki-cache.sh"
POLL_INTERVAL = 10  # 秒
LOG_FILE = Path(__file__).parent / "watcher.log"


def log(msg: str):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def get_domain_mtimes() -> dict[str, float]:
    """返回所有 DOMAIN.md 的 {路径: mtime} 字典"""
    mtimes = {}
    if not WIKI_ROOT.exists():
        return mtimes
    for domain_file in WIKI_ROOT.glob("*/DOMAIN.md"):
        try:
            mtimes[str(domain_file)] = domain_file.stat().st_mtime
        except Exception:
            pass
    # 也监听 DOMAIN.md 的新增/删除（通过监听父目录的 mtime）
    try:
        mtimes["__wiki_root__"] = WIKI_ROOT.stat().st_mtime
    except Exception:
        pass
    return mtimes


def run_sync():
    """运行 sync 脚本"""
    if not SYNC_SCRIPT.exists():
        log(f"ERROR: sync script not found: {SYNC_SCRIPT}")
        return
    try:
        result = subprocess.run(
            ["bash", str(SYNC_SCRIPT)],
            capture_output=True, text=True, timeout=30
        )
        output = result.stdout.strip()
        if output:
            log(f"sync: {output}")
        if result.returncode != 0:
            log(f"sync error: {result.stderr.strip()}")
    except Exception as e:
        log(f"sync failed: {e}")


def main():
    log(f"watcher started — watching {WIKI_ROOT}")
    log(f"poll interval: {POLL_INTERVAL}s")

    prev_mtimes = get_domain_mtimes()
    log(f"initial state: {len(prev_mtimes)} paths tracked")

    # 启动时先同步一次，确保缓存是最新的
    run_sync()

    while True:
        time.sleep(POLL_INTERVAL)
        try:
            curr_mtimes = get_domain_mtimes()

            changed = (
                set(curr_mtimes.keys()) != set(prev_mtimes.keys()) or
                any(curr_mtimes.get(k) != prev_mtimes.get(k) for k in curr_mtimes)
            )

            if changed:
                added = set(curr_mtimes) - set(prev_mtimes)
                removed = set(prev_mtimes) - set(curr_mtimes)
                modified = {k for k in curr_mtimes if k in prev_mtimes and curr_mtimes[k] != prev_mtimes[k]}

                changes = []
                if added:
                    changes.append(f"+{len(added)} domain(s)")
                if removed:
                    changes.append(f"-{len(removed)} domain(s)")
                if modified - {"__wiki_root__"}:
                    changes.append(f"~{len(modified - {'__wiki_root__'})} DOMAIN.md modified")

                log(f"change detected: {', '.join(changes) or 'directory structure'} → syncing")
                run_sync()
                prev_mtimes = curr_mtimes

        except Exception as e:
            log(f"watcher error: {e}")


if __name__ == "__main__":
    main()
