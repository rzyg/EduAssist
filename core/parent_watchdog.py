"""父进程看门狗：父进程（Tauri 壳）消失后自动结束后端进程。

背景：Tauri 正常退出时会主动杀掉后端；但若 Tauri 被强杀（NSIS 安装器弹窗
确认关闭、任务管理器结束、进程崩溃），其后端子进程会残留并继续占用
core/main.exe 等文件，导致安装器无法替换文件而失败。

本模块让后端监控父进程 PID：父进程无论以何种方式退出，看门狗都立即
结束后端进程（毫秒级），释放文件句柄。

Windows 使用 OpenProcess + WaitForSingleObject 阻塞等待（父进程退出时
句柄 signaled 立即返回，零轮询开销）；非 Windows 使用轮询。
"""

import ctypes
import os
import sys
import threading
import time

_PARENT_PID_ENV = "EDUASSIST_PARENT_PID"
_POLL_INTERVAL = 0.1  # 非 Windows 轮询间隔（秒）

# Windows API 常量
_SYNCHRONIZE = 0x00100000
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_INFINITE = 0xFFFFFFFF


def _win_wait_parent_exit(ppid: int) -> bool:
    """Windows：阻塞等待父进程退出。

    返回 True 表示成功建立监控（句柄可打开）；False 表示句柄打开失败
    （进程不存在或权限不足），调用方应降级为轮询。
    """
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(
        _SYNCHRONIZE | _PROCESS_QUERY_LIMITED_INFORMATION,
        False,
        ppid,
    )
    if not handle:
        return False
    try:
        # 阻塞等待：父进程退出时句柄 signaled，立即返回
        kernel32.WaitForSingleObject(handle, _INFINITE)
        return True
    finally:
        kernel32.CloseHandle(handle)


def _poll_parent(ppid: int) -> None:
    """非 Windows（或 Windows 句柄打开失败时）：轮询父进程是否存活。"""
    while True:
        try:
            os.kill(ppid, 0)
        except ProcessLookupError:
            break
        except PermissionError:
            pass  # 进程存在但无权限查看，继续等待
        except OSError:
            break
        time.sleep(_POLL_INTERVAL)


def _watch_parent(ppid: int) -> None:
    """监控线程主体：父进程退出后以 os._exit 结束整个进程。"""
    try:
        if os.name == "nt":
            if _win_wait_parent_exit(ppid):
                return
        # 非 Windows 或 Windows 句柄打开失败 → 轮询
        _poll_parent(ppid)
    finally:
        # 父进程已消失 → 立即结束后端，释放文件句柄。
        # 父进程死亡时没有人在等待优雅关闭，os._exit 可确保端口与文件立即释放。
        os._exit(0)


def start_parent_watchdog(ppid: int | None = None) -> None:
    """启动父进程看门狗（守护线程，不阻塞主流程）。

    ppid 缺省时优先取环境变量 EDUASSIST_PARENT_PID（由 Tauri 启动后端时传入，
    避免 dev 模式下 conda 等中间进程干扰），否则回退 os.getppid()。
    """
    if ppid is None:
        env = os.environ.get(_PARENT_PID_ENV)
        ppid = int(env) if env else os.getppid()
    if ppid <= 0:
        return
    threading.Thread(target=_watch_parent, args=(ppid,), daemon=True).start()
