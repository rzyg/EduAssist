"""任务中心核心逻辑单元测试 —— Task 与 TaskCenter(fake engine,不启动浏览器)。"""
from __future__ import annotations

import time

import pytest

from core.onlineclass.task_manager import Task, TaskCenter
from core.onlineclass.task_manager.task import RESULT_FAILED, RESULT_STOPPED, RESULT_SUCCESS


class _FakePage:
    """模拟 Playwright Page(仅记录截图调用)"""

    _pw = None  # 无真实浏览器,清理时跳过

    def __init__(self):
        self.shots: list = []

    def screenshot(self, **kwargs):
        self.shots.append(kwargs)


class _LoopEngine:
    """模拟执行中的引擎:反复到达检查点直到收到停止请求"""

    def __init__(self, config_path):
        self.config_path = str(config_path)
        self.context: dict = {}
        self.page = _FakePage()

    def run(self, page=None, close_browser=True, stop_check=None, captcha_request=None, headless=None):
        while not stop_check():
            time.sleep(0.01)
        return self.page


class _InstantEngine(_LoopEngine):
    """模拟自然完成的引擎:立即执行完所有板块"""

    def run(self, page=None, close_browser=True, stop_check=None, captcha_request=None, headless=None):
        stop_check()
        return self.page


class _BoomEngine(_LoopEngine):
    """模拟执行中抛异常的引擎"""

    def run(self, page=None, close_browser=True, stop_check=None, captcha_request=None, headless=None):
        raise RuntimeError("boom")


class _CaptchaEngine(_InstantEngine):
    """模拟引擎: 先请求验证码,拿到文本后结束"""

    def run(self, page=None, close_browser=True, stop_check=None, captcha_request=None, headless=None):
        captcha_request("data:image/png;base64,AAA")
        return self.page


class _CaptchaThenLoopEngine(_LoopEngine):
    """模拟引擎: 请求验证码拿到文本后继续循环,等待停止"""

    def run(self, page=None, close_browser=True, stop_check=None, captcha_request=None, headless=None):
        captcha_request("data:image/png;base64,BBB")
        while not stop_check():
            time.sleep(0.01)
        return self.page


class _HeadlessRecordingEngine(_InstantEngine):
    """记录 run 收到的 headless 参数"""

    def __init__(self, config_path):
        super().__init__(config_path)
        self.received_headless = None

    def run(self, page=None, close_browser=True, stop_check=None, captcha_request=None, headless=None):
        self.received_headless = headless
        return super().run(page, close_browser, stop_check, captcha_request, headless)


@pytest.fixture
def cfg_dir(tmp_path, monkeypatch):
    """把剧本目录指向临时目录,并写入 course.yaml"""
    monkeypatch.setattr("core.onlineclass.configs.ONLINE_CLASS_DIR", tmp_path)
    (tmp_path / "course.yaml").write_text("global:\n  retry: 0\n", encoding="utf-8")
    return tmp_path


@pytest.fixture
def cfg_name(cfg_dir):
    return "course"


@pytest.fixture
def cfg_path(cfg_dir):
    return str(cfg_dir / "course.yaml")


@pytest.fixture(autouse=True)
def _patch_engine(monkeypatch):
    """默认打桩为循环引擎,各用例可按需覆盖"""
    monkeypatch.setattr("core.onlineclass.task_manager.task.CourseEngine", _LoopEngine)


# ── Task 生命周期 ──────────────────────────────────────────────────────
def test_task_initial_state(cfg_path):
    task = Task("t1", cfg_path, "user", "pass")
    assert task.status == "pending"
    assert task.result is None
    assert task.context is task.engine.context  # context 引用引擎上下文
    assert task.headless is None  # 默认不覆盖,沿用剧本配置


def test_task_headless_passthrough(cfg_path, monkeypatch):
    """Task 的 headless 覆盖应传给 engine.run"""
    monkeypatch.setattr("core.onlineclass.task_manager.task.CourseEngine", _HeadlessRecordingEngine)
    task = Task("h1", cfg_path, "user", "pass", headless=True)
    task.start()
    task.wait(3)
    assert task.engine.received_headless is True
    assert task.result == RESULT_SUCCESS


class _PlaybackRecordingEngine(_InstantEngine):
    """记录引擎上下文(验证播放倍速注入)"""

    def __init__(self, config_path):
        super().__init__(config_path)
        self.injected_context: dict | None = None

    def run(self, page=None, close_browser=True, stop_check=None, captcha_request=None, headless=None):
        self.injected_context = dict(self.context)
        return super().run(page, close_browser, stop_check, captcha_request, headless)


def test_task_playback_rate_default_one(cfg_path):
    """Task 缺省倍速为 1,并出现在状态快照中"""
    task = Task("p1", cfg_path, "user", "pass")
    assert task.playback_rate == 1
    assert task.to_dict()["playback_rate"] == 1


def test_task_playback_rate_injected_into_context(cfg_path, monkeypatch):
    """倍速应注入引擎上下文,剧本可用 ${playback_rate} 引用"""
    monkeypatch.setattr("core.onlineclass.task_manager.task.CourseEngine", _PlaybackRecordingEngine)
    task = Task("p2", cfg_path, "user", "pass", playback_rate=2)
    task.start()
    task.wait(3)
    assert task.result == RESULT_SUCCESS
    assert task.engine.injected_context["playback_rate"] == 2
    assert task.to_dict()["playback_rate"] == 2


def test_center_create_playback_rate(cfg_name, monkeypatch):
    """TaskCenter.create 接受倍速参数并传给 Task"""
    monkeypatch.setattr("core.onlineclass.task_manager.task.CourseEngine", _InstantEngine)
    center = TaskCenter()
    task = center.create(cfg_name, "user", "pass", auto_start=False, playback_rate=3)
    assert task.playback_rate == 3
    assert task.to_dict()["playback_rate"] == 3


def test_task_lifecycle_success(cfg_path, monkeypatch):
    monkeypatch.setattr("core.onlineclass.task_manager.task.CourseEngine", _InstantEngine)
    task = Task("t1", cfg_path, "user", "pass")
    task.start()
    assert task.status == "running"
    task.wait(3)
    assert task.status == "finished"
    assert task.result == RESULT_SUCCESS
    assert task.error_message is None


def test_task_stop_result_stopped(cfg_path):
    task = Task("t2", cfg_path, "user", "pass")
    task.start()
    task.stop(timeout=3)
    assert task.status == "finished"
    assert task.result == RESULT_STOPPED


def test_task_failed_with_error_message(cfg_path, monkeypatch):
    monkeypatch.setattr("core.onlineclass.task_manager.task.CourseEngine", _BoomEngine)
    task = Task("t3", cfg_path, "user", "pass")
    task.start()
    task.wait(3)
    assert task.status == "finished"
    assert task.result == RESULT_FAILED
    assert "boom" in task.error_message


def test_task_cannot_start_twice(cfg_path):
    task = Task("t4", cfg_path, "user", "pass")
    task.start()
    with pytest.raises(RuntimeError, match="无法启动"):
        task.start()
    task.stop(timeout=3)


def test_task_to_dict_snapshot(cfg_path):
    task = Task("t5", cfg_path, "user", "pass")
    snapshot = task.to_dict()
    assert snapshot["task_id"] == "t5"
    assert snapshot["status"] == "pending"
    assert snapshot["config_path"] == cfg_path
    assert snapshot["context"] == {}


# ── 验证码等待与提交 ──────────────────────────────────────────────────
def test_task_waiting_captcha_then_submit(cfg_path, monkeypatch):
    monkeypatch.setattr("core.onlineclass.task_manager.task.CourseEngine", _CaptchaEngine)
    task = Task("c1", cfg_path, "user", "pass")
    task.start()
    # 等待进入 waiting_captcha
    for _ in range(100):
        if task.status == "waiting_captcha":
            break
        time.sleep(0.01)
    assert task.status == "waiting_captcha"
    snapshot = task.to_dict()
    assert snapshot["captcha_image"] == "data:image/png;base64,AAA"

    task.submit_captcha("ABC12")
    task.wait(3)
    assert task.status == "finished"
    assert task.result == RESULT_SUCCESS


def test_task_stop_during_waiting_captcha(cfg_path, monkeypatch):
    monkeypatch.setattr("core.onlineclass.task_manager.task.CourseEngine", _CaptchaThenLoopEngine)
    task = Task("c2", cfg_path, "user", "pass")
    task.start()
    for _ in range(100):
        if task.status == "waiting_captcha":
            break
        time.sleep(0.01)
    assert task.status == "waiting_captcha"
    task.stop(timeout=3)
    assert task.status == "finished"
    assert task.result == RESULT_STOPPED  # 等待验证码时被停止


def test_task_submit_captcha_not_waiting_raises(cfg_path):
    task = Task("c3", cfg_path, "user", "pass")
    with pytest.raises(RuntimeError, match="等待验证码"):
        task.submit_captcha("x")


def test_task_center_submit_captcha(cfg_path, monkeypatch):
    monkeypatch.setattr("core.onlineclass.task_manager.task.CourseEngine", _CaptchaEngine)
    center = TaskCenter()
    real = Task("c4", cfg_path, "user", "pass")
    real.start()
    for _ in range(100):
        if real.status == "waiting_captcha":
            break
        time.sleep(0.01)
    center._tasks[real.task_id] = real  # 登记进中心
    center.submit_captcha(real.task_id, "Z9")
    real.wait(3)
    assert real.result == RESULT_SUCCESS


def test_task_two_captcha_rounds(cfg_path, monkeypatch):
    """同一任务两次 request_captcha:第二次也必须等待提交(事件已复位)"""
    class _TwoCaptchaEngine(_InstantEngine):
        def run(self, page=None, close_browser=True, stop_check=None, captcha_request=None, headless=None):
            captcha_request("data:image/png;base64,IMG1")
            captcha_request("data:image/png;base64,IMG2")
            return self.page

    monkeypatch.setattr("core.onlineclass.task_manager.task.CourseEngine", _TwoCaptchaEngine)
    task = Task("c5", cfg_path, "user", "pass")
    task.start()
    for _ in range(100):
        if task.status == "waiting_captcha":
            break
        time.sleep(0.01)
    task.submit_captcha("A1")
    # 第二轮必须重新进入等待,且携带新图片
    for _ in range(100):
        if task.to_dict().get("captcha_image") == "data:image/png;base64,IMG2":
            break
        time.sleep(0.01)
    assert task.status == "waiting_captcha"
    task.submit_captcha("B2")
    task.wait(3)
    assert task.result == RESULT_SUCCESS


def test_task_remove_waiting_captcha_blocked(cfg_path, monkeypatch):
    monkeypatch.setattr("core.onlineclass.task_manager.task.CourseEngine", _CaptchaEngine)
    center = TaskCenter()
    task = Task("c6", cfg_path, "user", "pass")
    task.start()
    for _ in range(100):
        if task.status == "waiting_captcha":
            break
        time.sleep(0.01)
    center._tasks[task.task_id] = task
    with pytest.raises(RuntimeError, match="运行中"):
        center.remove(task.task_id)
    task.submit_captcha("x")
    task.wait(3)
    assert center.remove(task.task_id) is True  # 结束后可删除


def test_captcha_image_only_when_waiting(cfg_path, monkeypatch):
    monkeypatch.setattr("core.onlineclass.task_manager.task.CourseEngine", _CaptchaEngine)
    task = Task("c7", cfg_path, "user", "pass")
    task.start()
    for _ in range(100):
        if task.status == "waiting_captcha":
            break
        time.sleep(0.01)
    assert task.to_dict()["captcha_image"] is not None
    task.submit_captcha("x")
    task.wait(3)
    assert task.to_dict()["captcha_image"] is None  # 结束后不再携带


def test_submit_captcha_empty_rejected(cfg_path, monkeypatch):
    monkeypatch.setattr("core.onlineclass.task_manager.task.CourseEngine", _CaptchaEngine)
    task = Task("c8", cfg_path, "user", "pass")
    task.start()
    for _ in range(100):
        if task.status == "waiting_captcha":
            break
        time.sleep(0.01)
    with pytest.raises(ValueError, match="不能为空"):
        task.submit_captcha("   ")
    task.submit_captcha("ok")
    task.wait(3)
    assert task.result == RESULT_SUCCESS


def test_submit_captcha_duplicate_guard(cfg_path):
    """重复提交守卫:事件已置位时拒绝(白盒:不启动线程,直接模拟等待中+已提交)"""
    task = Task("c9", cfg_path, "user", "pass")
    task.status = "waiting_captcha"  # 模拟等待验证码状态
    task._captcha_event.set()  # 模拟首次提交已唤醒
    with pytest.raises(RuntimeError, match="重复提交"):
        task.submit_captcha("again")


# ── Task 截图(经检查点线程执行) ────────────────────────────────────────
def test_task_capture_screenshot(cfg_path, tmp_path):
    task = Task("t6", cfg_path, "user", "pass")
    task.start()
    time.sleep(0.05)  # 确保运行线程已进入检查点循环
    shot = str(tmp_path / "shots" / "evidence.png")
    task.capture_screenshot(shot, timeout=3)
    assert task.engine.page.shots[0]["path"] == shot
    task.stop(timeout=3)


def test_task_screenshot_requires_running(cfg_path):
    task = Task("t7", cfg_path, "user", "pass")
    with pytest.raises(RuntimeError, match="不在运行中"):
        task.capture_screenshot(str(cfg_path) + "_x.png")


# ── TaskCenter 注册表 ──────────────────────────────────────────────────
def test_center_create_get_list_remove(cfg_name, monkeypatch):
    monkeypatch.setattr("core.onlineclass.task_manager.task.CourseEngine", _InstantEngine)
    center = TaskCenter()
    task = center.create(cfg_name, "user", "pass", auto_start=False)
    assert task.status == "pending"
    assert task.config_name == cfg_name
    assert center.get(task.task_id) is task
    assert center.get_dict(task.task_id)["status"] == "pending"
    assert len(center.list()) == 1
    task.start()
    task.wait(3)
    assert center.remove(task.task_id) is True
    assert center.remove(task.task_id) is False  # 已删除


def test_center_create_missing_config(cfg_dir):
    center = TaskCenter()
    with pytest.raises(FileNotFoundError, match="配置不存在"):
        center.create("no_such_config", "user", "pass")


def test_center_remove_running_blocked(cfg_name):
    center = TaskCenter()
    task = center.create(cfg_name, "user", "pass", auto_start=False)
    task.start()
    with pytest.raises(RuntimeError, match="运行中"):
        center.remove(task.task_id)
    task.stop(timeout=3)


def test_center_unknown_id_raises(cfg_path):
    center = TaskCenter()
    with pytest.raises(KeyError, match="任务不存在"):
        center.start("no_such")
    with pytest.raises(KeyError, match="任务不存在"):
        center.stop("no_such")
    assert center.remove("no_such") is False  # remove 对不存在任务幂等返回 False


def test_center_task_id_unique_and_format(cfg_name):
    center = TaskCenter()
    t1 = center.create(cfg_name, "u", "p", auto_start=False)
    t2 = center.create(cfg_name, "u", "p", auto_start=False)
    assert t1.task_id != t2.task_id
    assert t1.task_id.startswith("task_")

