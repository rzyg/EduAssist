"""任务中心 API 路由测试 —— TestClient + fake engine(不启动浏览器)。"""
from __future__ import annotations

import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


class _FakePage:
    _pw = None

    def __init__(self):
        self.shots: list = []

    def screenshot(self, **kwargs):
        self.shots.append(kwargs)


class _LoopEngine:
    def __init__(self, config_path):
        self.config_path = str(config_path)
        self.context: dict = {}
        self.page = _FakePage()

    def run(self, page=None, close_browser=True, stop_check=None, captcha_request=None, headless=None):
        while not stop_check():
            time.sleep(0.01)
        return self.page


class _InstantEngine(_LoopEngine):
    def run(self, page=None, close_browser=True, stop_check=None, captcha_request=None, headless=None):
        stop_check()
        return self.page


class _CaptchaEngine(_InstantEngine):
    """模拟引擎: 先请求验证码,拿到文本后结束"""

    def run(self, page=None, close_browser=True, stop_check=None, captcha_request=None, headless=None):
        captcha_request("data:image/png;base64,AAA")
        stop_check()
        return self.page


@pytest.fixture
def cfg_path(tmp_path):
    p = tmp_path / "task.yaml"
    p.write_text("global:\n  retry: 0\n", encoding="utf-8")
    return str(p)


@pytest.fixture
def client(monkeypatch, tmp_path):
    """独立 task_center + fake 引擎 + 临时剧本目录,隔离全局单例,不启动真实浏览器"""
    monkeypatch.setattr("core.onlineclass.task_manager.task.CourseEngine", _InstantEngine)
    monkeypatch.setattr("core.onlineclass.configs.ONLINE_CLASS_DIR", tmp_path)
    (tmp_path / "course.yaml").write_text("global:\n  retry: 0\n", encoding="utf-8")
    from core.onlineclass.task_manager import TaskCenter
    from core.route.onlineclass import config_router, router

    monkeypatch.setattr("core.route.onlineclass.task_center", TaskCenter())
    app = FastAPI()
    app.include_router(router)
    app.include_router(config_router)
    return TestClient(app)


def _payload():
    return {"config_name": "course", "username": "user", "password": "pass"}


def test_create_and_get_task(client):
    resp = client.post("/api/v1/tasks", json=_payload())
    assert resp.status_code == 200
    data = resp.json()
    assert data["config_name"] == "course"
    assert data["status"] == "running" or data["status"] == "finished"
    task_id = data["task_id"]
    assert task_id.startswith("task_")

    detail = client.get(f"/api/v1/tasks/{task_id}")
    assert detail.status_code == 200
    assert detail.json()["task_id"] == task_id


def test_create_task_config_not_found(client):
    payload = _payload()
    payload["config_name"] = "no_such"
    resp = client.post("/api/v1/tasks", json=payload)
    assert resp.status_code == 404
    assert "配置不存在" in resp.json()["detail"]


def test_create_task_with_headless(client):
    """创建任务接口接受 headless 布尔参数(True=无头 / False=有头 / 缺省=None)"""
    payload = _payload()
    payload["headless"] = True
    resp = client.post("/api/v1/tasks", json=payload)
    assert resp.status_code == 200
    assert resp.json()["status"] in ("running", "finished")

    payload2 = _payload()
    payload2["headless"] = False
    assert client.post("/api/v1/tasks", json=payload2).status_code == 200


def test_create_task_playback_rate_default_one(client):
    """创建任务接口缺省倍速为 1"""
    resp = client.post("/api/v1/tasks", json=_payload())
    assert resp.status_code == 200
    assert resp.json()["playback_rate"] == 1


def test_create_task_with_playback_rate(client):
    """创建任务接口接受 playbackRate 正整数参数并回显"""
    payload = _payload()
    payload["playbackRate"] = 2
    resp = client.post("/api/v1/tasks", json=payload)
    assert resp.status_code == 200
    assert resp.json()["playback_rate"] == 2


def test_create_task_playback_rate_invalid(client):
    """playbackRate 必须为正整数,0 / 负数 / 非整数均拒绝(422)"""
    for bad in (0, -1, 2.5, "fast"):
        payload = _payload()
        payload["playbackRate"] = bad
        resp = client.post("/api/v1/tasks", json=payload)
        assert resp.status_code == 422, f"playbackRate={bad!r} 应被拒绝"


def test_get_task_not_found(client):
    resp = client.get("/api/v1/tasks/no_such")
    assert resp.status_code == 404
    assert "任务不存在" in resp.json()["detail"]


def test_list_tasks(client):
    client.post("/api/v1/tasks", json=_payload())
    resp = client.get("/api/v1/tasks")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_stop_task(client, monkeypatch):
    # 换成循环引擎,任务保持运行,可被停止
    monkeypatch.setattr("core.onlineclass.task_manager.task.CourseEngine", _LoopEngine)
    created = client.post("/api/v1/tasks", json=_payload()).json()
    task_id = created["task_id"]
    time.sleep(0.05)
    resp = client.post(f"/api/v1/tasks/{task_id}/stop")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "finished"
    assert data["result"] == "stopped"


def test_stop_task_not_found(client):
    resp = client.post("/api/v1/tasks/no_such/stop")
    assert resp.status_code == 404


# ── 验证码提交 ─────────────────────────────────────────────────────────
def test_submit_captcha_wakes_task(client, monkeypatch):
    monkeypatch.setattr("core.onlineclass.task_manager.task.CourseEngine", _CaptchaEngine)
    created = client.post("/api/v1/tasks", json=_payload()).json()
    task_id = created["task_id"]
    # 等待任务进入 waiting_captcha
    for _ in range(200):
        if client.get(f"/api/v1/tasks/{task_id}").json()["status"] == "waiting_captcha":
            break
        time.sleep(0.01)
    detail = client.get(f"/api/v1/tasks/{task_id}").json()
    assert detail["status"] == "waiting_captcha"
    assert detail["captcha_image"].startswith("data:image/png;base64,")

    resp = client.post(f"/api/v1/tasks/{task_id}/captcha", json={"captcha": "ABC12"})
    assert resp.status_code == 200
    # 提交唤醒线程,轮询等待任务完成
    for _ in range(200):
        if client.get(f"/api/v1/tasks/{task_id}").json()["status"] == "finished":
            break
        time.sleep(0.01)
    data = client.get(f"/api/v1/tasks/{task_id}").json()
    assert data["status"] == "finished"
    assert data["result"] == "success"


def test_submit_captcha_task_not_found(client):
    resp = client.post("/api/v1/tasks/no_such/captcha", json={"captcha": "x"})
    assert resp.status_code == 404


def test_submit_captcha_empty_rejected(client, monkeypatch):
    monkeypatch.setattr("core.onlineclass.task_manager.task.CourseEngine", _CaptchaEngine)
    created = client.post("/api/v1/tasks", json=_payload()).json()
    task_id = created["task_id"]
    for _ in range(200):
        if client.get(f"/api/v1/tasks/{task_id}").json()["status"] == "waiting_captcha":
            break
        time.sleep(0.01)
    resp = client.post(f"/api/v1/tasks/{task_id}/captcha", json={"captcha": "  "})
    assert resp.status_code == 400
    assert "不能为空" in resp.json()["detail"]
    # 提交合法值收尾
    client.post(f"/api/v1/tasks/{task_id}/captcha", json={"captcha": "ok"})


def test_submit_captcha_not_waiting(client, monkeypatch):
    # 使用不请求验证码的引擎,任务直接结束 -> 提交返回 409
    created = client.post("/api/v1/tasks", json=_payload()).json()
    task_id = created["task_id"]
    for _ in range(100):
        if client.get(f"/api/v1/tasks/{task_id}").json()["status"] == "finished":
            break
        time.sleep(0.01)
    resp = client.post(f"/api/v1/tasks/{task_id}/captcha", json={"captcha": "x"})
    assert resp.status_code == 409
    assert "等待验证码" in resp.json()["detail"]


def test_start_finished_task_conflict(client):
    # 路由创建的任务总是自动启动;已结束的任务再次 start 应返回 409
    created = client.post("/api/v1/tasks", json=_payload()).json()
    task_id = created["task_id"]
    for _ in range(100):
        if client.get(f"/api/v1/tasks/{task_id}").json()["status"] == "finished":
            break
        time.sleep(0.01)
    resp = client.post(f"/api/v1/tasks/{task_id}/start")
    assert resp.status_code == 409


def test_remove_task(client):
    created = client.post("/api/v1/tasks", json=_payload()).json()
    task_id = created["task_id"]
    # 等待任务结束(auto_start + InstantEngine)
    for _ in range(100):
        if client.get(f"/api/v1/tasks/{task_id}").json()["status"] == "finished":
            break
        time.sleep(0.01)
    resp = client.delete(f"/api/v1/tasks/{task_id}")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    # 再次删除 -> 404
    assert client.delete(f"/api/v1/tasks/{task_id}").status_code == 404


def test_remove_running_task_conflict(client, monkeypatch):
    monkeypatch.setattr("core.onlineclass.task_manager.task.CourseEngine", _LoopEngine)
    created = client.post("/api/v1/tasks", json=_payload()).json()
    task_id = created["task_id"]
    resp = client.delete(f"/api/v1/tasks/{task_id}")
    assert resp.status_code == 409
    assert "运行中" in resp.json()["detail"]
    client.post(f"/api/v1/tasks/{task_id}/stop")


# ── 配置接口 ────────────────────────────────────────────────────────────
def test_list_local_configs(client, tmp_path):
    (tmp_path / "another.yaml").write_text("global: {}\n", encoding="utf-8")
    resp = client.get("/api/v1/configs/local")
    assert resp.status_code == 200
    data = resp.json()
    names = {c["name"] for c in data}
    assert names == {"course", "another"}
    for c in data:
        assert "created_at" in c and c["created_at"]


class _FakeResp:
    """模拟 urllib 响应对象(打桩网络,不发真实请求)"""

    def __init__(self, data: bytes):
        self._data = data

    def read(self) -> bytes:
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_list_online_configs(client, monkeypatch):
    """在线配置列表:解析远端 filelist JSON,返回 [{name, updated_at}]"""
    import json as _json

    payload = _json.dumps(
        {"filelist": [{"filename": "河南教师培训网.yaml", "updateTimestamp": "1787518836"}]}
    ).encode("utf-8")
    monkeypatch.setattr(
        "core.onlineclass.configs._open_url",
        lambda url, timeout=20: _FakeResp(payload),
    )
    resp = client.get("/api/v1/configs/online")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "河南教师培训网"
    assert data[0]["updated_at"]


def test_list_online_configs_error_502(client, monkeypatch):
    """在线配置列表获取失败(网络异常)时返回 502"""
    def boom(url, timeout=20):
        raise OSError("connection refused")

    monkeypatch.setattr("core.onlineclass.configs._open_url", boom)
    resp = client.get("/api/v1/configs/online")
    assert resp.status_code == 502
    assert "无法获取在线配置列表" in resp.json()["detail"]


def test_download_configs_api(client, monkeypatch, tmp_path):
    """批量下载:配置保存到 data/onlineclass(目录自动创建)"""
    monkeypatch.setattr(
        "core.onlineclass.configs._open_url",
        lambda url, timeout=20: _FakeResp(b"global:\n  retry: 0\n"),
    )
    resp = client.post("/api/v1/configs/download", json={"names": ["course"]})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["downloaded"]) == 1
    assert data["failed"] == []
    assert data["downloaded"][0]["name"] == "course"
    saved = tmp_path / "course.yaml"
    assert saved.read_text(encoding="utf-8").startswith("global:")


def test_download_configs_api_partial_failure(client, monkeypatch, tmp_path):
    """单个配置下载失败不阻塞其余,逐项返回 failed 明细"""
    def fake(url, timeout=20):
        if "course" in url:
            return _FakeResp(b"global:\n  retry: 0\n")
        raise OSError("404 Not Found")

    monkeypatch.setattr("core.onlineclass.configs._open_url", fake)
    resp = client.post("/api/v1/configs/download", json={"names": ["course", "ghost"]})
    assert resp.status_code == 200
    data = resp.json()
    assert [d["name"] for d in data["downloaded"]] == ["course"]
    assert len(data["failed"]) == 1
    assert data["failed"][0]["name"] == "ghost"
    assert "下载配置" in data["failed"][0]["error"]


def test_download_configs_api_rejects_unsafe_name(client, monkeypatch, tmp_path):
    """含路径分隔符的配置名拒绝下载(记入 failed,不落盘)"""
    monkeypatch.setattr(
        "core.onlineclass.configs._open_url",
        lambda url, timeout=20: _FakeResp(b"x"),
    )
    resp = client.post("/api/v1/configs/download", json={"names": ["../evil"]})
    assert resp.status_code == 200
    data = resp.json()
    assert data["downloaded"] == []
    assert len(data["failed"]) == 1
    assert "配置名" in data["failed"][0]["error"]
    assert not (tmp_path / ".." / "evil.yaml").exists()


def test_download_configs_api_empty_names(client, monkeypatch):
    resp = client.post("/api/v1/configs/download", json={"names": []})
    assert resp.status_code == 200
    assert resp.json() == {"downloaded": [], "failed": []}

