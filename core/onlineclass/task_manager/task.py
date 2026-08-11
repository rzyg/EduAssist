"""任务对象 —— 封装一个独立运行的刷课任务。

每个 ``Task`` 在后台线程中运行一个 ``CourseEngine`` 实例,对外提供
线程安全的状态查询与控制方法,供任务中心 / API 使用。

状态机::

    pending ──start()──► running ──线程结束──► finished
                       (result: success | failed | stopped)
"""
from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

from loguru import logger

from core.onlineclass.engine import CourseEngine, TaskStoppedError

# 任务状态
STATUS_PENDING = "pending"           # 等待启动
STATUS_RUNNING = "running"           # 执行中
STATUS_WAITING_CAPTCHA = "waiting_captcha"  # 暂停,等待外部提交验证码
STATUS_FINISHED = "finished"         # 正常结束(进程已退出)

# 结果(仅 status=finished 时有意义)
RESULT_SUCCESS = "success"    # 全部板块正常执行完
RESULT_FAILED = "failed"      # 执行中抛出异常
RESULT_STOPPED = "stopped"    # 被外部请求停止


class Task:
    """一个独立刷课任务的运行时封装。"""

    def __init__(
        self,
        task_id: str,
        config_path: str | Path,
        username: str,
        password: str,
        headless: bool | None = None,
        playback_rate: int = 1,
    ):
        self.task_id = task_id
        self.config_path = str(config_path)
        # 配置文件名(不带后缀),供 API / 前端展示与引用
        self.config_name = Path(self.config_path).stem
        self.username = username
        self.password = password
        # 有头/无头覆盖:None 沿用剧本 global.headless
        self.headless = headless
        # 视频播放倍速(正整数,默认 1),注入引擎上下文供剧本 ${playback_rate} 引用
        self.playback_rate = playback_rate

        self.engine = CourseEngine(self.config_path)
        # 引擎上下文的引用,实时反映任务进度(步骤间传递的数据)
        self.context: dict[str, Any] = self.engine.context
        # 引擎创建/持有的浏览器 page(任务运行中有效)
        self.page: Any = None

        self.status = STATUS_PENDING
        self.result: str | None = None
        self.error_message: str | None = None
        self.started_at: float | None = None
        self.finished_at: float | None = None

        self._stop_flag = False
        self._thread: threading.Thread | None = None
        self._lock = threading.RLock()
        # 截图请求: (目标路径, 完成事件);由运行线程在检查点执行,避免跨线程调 page
        self._shot_request: tuple[str, threading.Event] | None = None
        self._shot_error: str | None = None
        # 验证码等待: 图片 data URL + 提交事件 + 用户提交的文本
        self._captcha_event = threading.Event()
        self._captcha_image: str | None = None
        self._captcha_text: str | None = None

    # ── 控制 ────────────────────────────────────────────────────────────
    def start(self) -> None:
        """启动任务:状态置 running,在后台线程中运行引擎。"""
        with self._lock:
            if self.status != STATUS_PENDING:
                raise RuntimeError(f"任务 {self.task_id} 状态为 {self.status},无法启动")
            self._stop_flag = False
            self.status = STATUS_RUNNING
            self.started_at = time.time()
            self._thread = threading.Thread(
                target=self._run,
                name=f"task-{self.task_id}",
                daemon=True,
            )
            self._thread.start()

    def stop(self, timeout: float | None = 15.0) -> None:
        """请求停止:设置标志,引擎在下一个检查点退出。

        running 与 waiting_captcha 状态下均可停止;等待验证码时停止会
        唤醒等待线程并终止任务。线程若卡在单个 Playwright 动作上,可能
        超过 ``timeout`` 才真正结束。
        """
        with self._lock:
            if self.status not in (STATUS_RUNNING, STATUS_WAITING_CAPTCHA):
                return
            self._stop_flag = True
        if timeout and self._thread and self._thread.is_alive():
            self._thread.join(timeout)

    def wait(self, timeout: float | None = None) -> None:
        """阻塞等待任务结束。"""
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout)

    def submit_captcha(self, captcha: str) -> None:
        """提交验证码:唤醒等待中的引擎线程,继续执行。

        仅 ``waiting_captcha`` 状态可用;空串 / 重复提交会被拒绝。
        """
        with self._lock:
            if self.status != STATUS_WAITING_CAPTCHA:
                raise RuntimeError(f"任务 {self.task_id} 不在等待验证码状态,无法提交")
            if not captcha or not captcha.strip():
                raise ValueError("验证码不能为空")
            if len(captcha) > 64:
                raise ValueError("验证码过长(最多 64 字符)")
            if self._captcha_event.is_set():
                raise RuntimeError(f"任务 {self.task_id} 验证码已提交,请勿重复提交")
            self._captcha_text = captcha
            self._captcha_event.set()

    # ── 内部运行 ────────────────────────────────────────────────────────
    def _run(self) -> None:
        try:
            # 注入登录凭据与播放倍速到引擎上下文,供剧本 ${username} 等引用
            self.engine.context["username"] = self.username
            self.engine.context["password"] = self.password
            self.engine.context["playback_rate"] = self.playback_rate
            # close_browser=False:浏览器生命周期由本任务统一管理(_cleanup 关闭)
            self.page = self.engine.run(
                close_browser=False,
                stop_check=self._checkpoint,
                captcha_request=self._request_captcha_cb,
                headless=self.headless,
            )
            self.result = RESULT_STOPPED if self._stop_flag else RESULT_SUCCESS
        except TaskStoppedError:
            self.result = RESULT_STOPPED
        except Exception as exc:
            logger.exception(f"任务 {self.task_id} 执行失败")
            self.result = RESULT_FAILED
            self.error_message = str(exc)
        finally:
            self._cleanup()
            with self._lock:
                self.status = STATUS_FINISHED
                self.finished_at = time.time()

    def _request_captcha_cb(self, image: str) -> str:
        """引擎的验证码请求回调(运行线程内调用):

        保存图片 data URL、置 ``waiting_captcha`` 状态,然后阻塞等待
        前端通过 ``submit_captcha`` 提交;收到停止请求则抛 TaskStoppedError。
        """
        with self._lock:
            self._captcha_event.clear()  # 复位,支持同一任务多次 request_captcha
            self._captcha_image = image
            self._captcha_text = None
            self.status = STATUS_WAITING_CAPTCHA
        # 等待提交;期间轮询停止标志,避免 stop 请求被卡死
        while not self._captcha_event.wait(0.5):
            with self._lock:
                if self._stop_flag:
                    raise TaskStoppedError("任务在等待验证码时被停止")
        with self._lock:
            self.status = STATUS_RUNNING
            return self._captcha_text or ""

    def _checkpoint(self) -> bool:
        """引擎的停止检查回调(在运行线程内调用)。

        顺带在此处理截图请求 —— 页面对象只能在创建它的线程中操作。
        """
        req = self._shot_request
        if req is not None:
            path, done = req
            self._shot_request = None
            try:
                page = getattr(self.engine, "page", None)
                if page is None:
                    raise RuntimeError("任务页面不可用")
                page.screenshot(path=path)
                self._shot_error = None
            except Exception as exc:  # 截图失败不中断任务
                self._shot_error = str(exc)
                logger.warning(f"任务 {self.task_id} 截图失败: {exc}")
            finally:
                done.set()
        return self._stop_flag

    def _cleanup(self) -> None:
        """关闭任务持有的浏览器,并恢复被临时切换的事件循环策略。"""
        page = getattr(self.engine, "page", None) or self.page
        if page is not None:
            pw = getattr(page, "_pw", None)
            if pw is not None:
                try:
                    pw.stop()
                except Exception:
                    logger.debug(f"任务 {self.task_id} 关闭浏览器失败(可忽略)")
            # 恢复 uvicorn(Windows) 的 Selector 事件循环策略,避免影响后续任务/服务
            prev_policy = getattr(page, "_pw_prev_policy", None)
            if prev_policy is not None:
                try:
                    import asyncio

                    asyncio.set_event_loop_policy(prev_policy)
                except Exception:
                    logger.debug(f"任务 {self.task_id} 恢复事件循环策略失败(可忽略)")
            self.engine.page = None
            self.page = None

    # ── 查询 ────────────────────────────────────────────────────────────
    def to_dict(self) -> dict:
        """线程安全的状态快照,供 API / 前端使用。"""
        with self._lock:
            # 剔除敏感值,避免随快照外泄(密码 / 已提交的验证码文本)
            context_snapshot = {
                key: value
                for key, value in self.context.items()
                if key not in ("password", "captcha")
            }
            return {
                "task_id": self.task_id,
                "config_name": self.config_name,
                "config_path": self.config_path,
                "status": self.status,
                "result": self.result,
                "error_message": self.error_message,
                # 视频播放倍速(正整数,默认 1)
                "playback_rate": self.playback_rate,
                # 验证码图片仅 waiting_captcha 状态返回,避免大体积 base64 常驻快照
                "captcha_image": self._captcha_image if self.status == STATUS_WAITING_CAPTCHA else None,
                "context": context_snapshot,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
            }

    def capture_screenshot(self, path: str | Path, timeout: float = 10.0) -> str:
        """请求截取当前页面,由运行线程执行后返回保存路径。

        仅 running 状态可用;超时未完成(如任务已结束)抛 RuntimeError。
        """
        dest = Path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            if self.status != STATUS_RUNNING:
                raise RuntimeError(f"任务 {self.task_id} 不在运行中,无法截图")
            done = threading.Event()
            self._shot_request = (str(dest), done)
        if not done.wait(timeout):
            self._shot_request = None
            raise RuntimeError(f"任务 {self.task_id} 截图超时")
        if self._shot_error:
            raise RuntimeError(self._shot_error)
        return str(dest)
