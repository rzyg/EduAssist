"""任务中心 —— 管理所有刷课任务(创建 / 查询 / 控制 / 清理)。

线程安全:内部使用 ``RLock`` 保护注册表,对外方法可被 FastAPI 等并发调用。
"""
from __future__ import annotations

import threading
import time
from typing import Any

from loguru import logger

from core.onlineclass.task_manager.task import (
    STATUS_RUNNING,
    STATUS_WAITING_CAPTCHA,
    Task,
)


class TaskCenter:
    """刷课任务注册表,通过 ``task_id`` 管理任务实例。"""

    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}
        self._lock = threading.RLock()
        self._seq = 0

    # ── 创建与启动 ──────────────────────────────────────────────────────
    def create(
        self,
        config_name: str,
        username: str,
        password: str,
        auto_start: bool = True,
        headless: bool | None = None,
        playback_rate: int = 1,
    ) -> Task:
        """按配置文件**文件名(不带后缀)**创建任务并登记。

        ``auto_start=True`` 时立即在后台启动;配置不存在抛 FileNotFoundError。
        ``headless`` 覆盖浏览器有头/无头模式(None 沿用剧本 global.headless)。
        ``playback_rate`` 为视频播放倍速(正整数,默认 1),注入引擎上下文,
        剧本中可用 ``${playback_rate}`` 引用。
        """
        from core.onlineclass.configs import resolve_config_path

        config_path = resolve_config_path(config_name)
        task = Task(
            self._next_id(),
            config_path,
            username,
            password,
            headless,
            playback_rate,
        )
        with self._lock:
            self._tasks[task.task_id] = task
        if auto_start:
            task.start()
        logger.info(f"任务中心: 创建任务 {task.task_id} (配置: {config_name})")
        return task

    def start(self, task_id: str) -> Task:
        """启动一个 pending 任务。"""
        task = self._require(task_id)
        task.start()
        return task

    # ── 查询 ────────────────────────────────────────────────────────────
    def get(self, task_id: str) -> Task | None:
        """按 id 获取任务对象(未找到返回 None)。"""
        with self._lock:
            return self._tasks.get(task_id)

    def get_dict(self, task_id: str) -> dict | None:
        """按 id 获取任务状态快照(未找到返回 None)。"""
        task = self.get(task_id)
        return task.to_dict() if task else None

    def list(self) -> list[dict]:
        """返回全部任务的状态快照列表。"""
        with self._lock:
            return [task.to_dict() for task in self._tasks.values()]

    # ── 控制 ────────────────────────────────────────────────────────────
    def stop(self, task_id: str, timeout: float | None = 15.0) -> Task:
        """请求停止任务(等待线程退出,最长 ``timeout`` 秒)。"""
        task = self._require(task_id)
        task.stop(timeout)
        return task

    def submit_captcha(self, task_id: str, captcha: str) -> Task:
        """提交验证码,唤醒等待中的任务继续执行。"""
        task = self._require(task_id)
        task.submit_captcha(captcha)
        return task

    # ── 清理 ────────────────────────────────────────────────────────────
    def remove(self, task_id: str) -> bool:
        """移除一个已结束任务;运行中或等待验证码的任务拒绝移除。"""
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return False
            if task.status in (STATUS_RUNNING, STATUS_WAITING_CAPTCHA):
                raise RuntimeError(f"任务 {task_id} 运行中,不能删除")
            del self._tasks[task_id]
            logger.info(f"任务中心: 移除任务 {task_id}")
            return True

    # ── 内部 ────────────────────────────────────────────────────────────
    def _require(self, task_id: str) -> Task:
        task = self.get(task_id)
        if task is None:
            raise KeyError(f"任务不存在: {task_id}")
        return task

    def _next_id(self) -> str:
        import secrets

        with self._lock:
            self._seq += 1
            token = secrets.token_hex(8)  # 64 位随机段,避免 task_id 被猜测
            return f"task_{int(time.time())}_{self._seq:03d}_{token}"


# 全局单例,供 FastAPI 路由使用
task_center: Any = TaskCenter()
