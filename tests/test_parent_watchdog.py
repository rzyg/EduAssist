"""
core/parent_watchdog 父进程看门狗测试

用真实子进程验证:
  1. 被监控的父进程退出后,看门狗进程(模拟后端)会自行退出
  2. 父进程存活时看门狗不退;父进程被杀后看门狗随之退出
"""
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)

_WATCHDOG_SCRIPT = (
    "from core.parent_watchdog import _watch_parent; "
    "import sys; _watch_parent(int(sys.argv[1]))"
)


def _spawn_watchdog(ppid: int) -> subprocess.Popen:
    """启动一个运行 _watch_parent(ppid) 的子进程，模拟后端"""
    return subprocess.Popen(
        [sys.executable, "-c", _WATCHDOG_SCRIPT, str(ppid)],
        cwd=PROJECT_ROOT,
    )


def _spawn_parent(sleep_seconds: int) -> subprocess.Popen:
    """启动一个 sleep 后自然退出的中间进程，模拟 Tauri 父进程"""
    return subprocess.Popen(
        [sys.executable, "-c", f"import time; time.sleep({sleep_seconds})"],
    )


def test_watchdog_exits_when_parent_dies():
    """父进程自然退出后，看门狗应自行退出"""
    parent = _spawn_parent(2)
    watchdog = _spawn_watchdog(parent.pid)
    try:
        assert parent.wait(timeout=10) == 0
        # 父进程退出后，看门狗应在短时间内自行退出
        assert watchdog.wait(timeout=5) == 0
    finally:
        if parent.poll() is None:
            parent.kill()
        if watchdog.poll() is None:
            watchdog.kill()


def test_watchdog_stays_while_parent_alive_then_exits():
    """父进程存活时看门狗不退；父进程被杀后看门狗随之退出"""
    parent = _spawn_parent(30)
    watchdog = _spawn_watchdog(parent.pid)
    try:
        time.sleep(1.5)
        assert watchdog.poll() is None, "父进程存活时看门狗不应退出"
        parent.kill()
        parent.wait(timeout=10)
        assert watchdog.wait(timeout=5) == 0, "父进程被杀后看门狗应自行退出"
    finally:
        if parent.poll() is None:
            parent.kill()
        if watchdog.poll() is None:
            watchdog.kill()
