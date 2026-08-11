"""任务中心模块:管理刷课任务的运行、查询与控制。

- ``task.py``: Task,单个任务的运行时封装(后台线程运行 CourseEngine)
- ``manager.py``: TaskCenter,线程安全的任务注册表 + 全局单例
"""
from core.onlineclass.task_manager.manager import TaskCenter, task_center
from core.onlineclass.task_manager.task import (
    RESULT_FAILED,
    RESULT_STOPPED,
    RESULT_SUCCESS,
    STATUS_FINISHED,
    STATUS_PENDING,
    STATUS_RUNNING,
    STATUS_WAITING_CAPTCHA,
    Task,
)

__all__ = [
    "Task",
    "TaskCenter",
    "task_center",
    "STATUS_PENDING",
    "STATUS_RUNNING",
    "STATUS_WAITING_CAPTCHA",
    "STATUS_FINISHED",
    "RESULT_SUCCESS",
    "RESULT_FAILED",
    "RESULT_STOPPED",
]
