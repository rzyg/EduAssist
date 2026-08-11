"""core.onlineclass.configs 单元测试 —— 在线配置列表拉取与下载(打桩网络,不发真实请求)。"""
from __future__ import annotations

import json

import pytest

from core.onlineclass.configs import download_config, list_online_configs


class _FakeResp:
    """模拟 urllib 响应对象(仅支持 read 与上下文协议)。"""

    def __init__(self, data: bytes):
        self._data = data

    def read(self) -> bytes:
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


FILELIST = json.dumps(
    {
        "filelist": [
            {"filename": "河南教师培训网.yaml", "updateTimestamp": "1787518836"},
            {"filename": "说明.txt", "updateTimestamp": "1"},  # 非 yaml,应被过滤
        ]
    }
).encode("utf-8")

YAML = b"global:\n  retry: 0\n"


# ── 在线列表 ───────────────────────────────────────────────────────────
def test_list_online_configs_parses(monkeypatch):
    monkeypatch.setattr(
        "core.onlineclass.configs._open_url",
        lambda url, timeout=20: _FakeResp(FILELIST),
    )
    result = list_online_configs()
    assert len(result) == 1  # 非 yaml 文件被过滤
    assert result[0]["name"] == "河南教师培训网"
    assert result[0]["updated_at"]  # 时间戳已转 ISO 字符串


def test_list_online_configs_uses_filelist_url(monkeypatch):
    seen: dict = {}

    def capture(url, timeout=20):
        seen["url"] = url
        return _FakeResp(FILELIST)

    monkeypatch.setattr("core.onlineclass.configs._open_url", capture)
    list_online_configs()
    assert seen["url"] == (
        "https://alist.bbts.fun/d/"
        "%E4%B8%8B%E7%8F%AD%E5%B7%A5%E5%85%B7%E7%AE%B1"
        "/.onlineclass-configs/.filelist.json"
    )


def test_list_online_configs_network_error(monkeypatch):
    def boom(url, timeout=20):
        raise OSError("connection refused")

    monkeypatch.setattr("core.onlineclass.configs._open_url", boom)
    with pytest.raises(RuntimeError, match="无法获取在线配置列表"):
        list_online_configs()


def test_list_online_configs_bad_json(monkeypatch):
    monkeypatch.setattr(
        "core.onlineclass.configs._open_url",
        lambda url, timeout=20: _FakeResp(b"not json"),
    )
    with pytest.raises(RuntimeError, match="格式异常"):
        list_online_configs()


# ── 下载 ───────────────────────────────────────────────────────────────
def test_download_config_auto_creates_dir(monkeypatch, tmp_path):
    target = tmp_path / "nested" / "onlineclass"  # 目录不存在,应自动创建
    monkeypatch.setattr("core.onlineclass.configs.ONLINE_CLASS_DIR", target)
    monkeypatch.setattr(
        "core.onlineclass.configs._open_url",
        lambda url, timeout=20: _FakeResp(YAML),
    )
    dest = download_config("demo")
    assert dest == target / "demo.yaml"
    assert dest.read_bytes() == YAML


def test_download_config_accepts_yaml_suffix(monkeypatch, tmp_path):
    monkeypatch.setattr("core.onlineclass.configs.ONLINE_CLASS_DIR", tmp_path)
    monkeypatch.setattr(
        "core.onlineclass.configs._open_url",
        lambda url, timeout=20: _FakeResp(YAML),
    )
    dest = download_config("demo.yaml")
    assert dest.name == "demo.yaml"
    assert dest.read_bytes() == YAML


def test_download_config_quotes_filename(monkeypatch, tmp_path):
    monkeypatch.setattr("core.onlineclass.configs.ONLINE_CLASS_DIR", tmp_path)
    seen: dict = {}

    def capture(url, timeout=20):
        seen["url"] = url
        return _FakeResp(YAML)

    monkeypatch.setattr("core.onlineclass.configs._open_url", capture)
    download_config("河南教师培训网")
    assert "河南教师培训网" not in seen["url"]  # 中文文件名必须百分号编码
    assert "%E6%B2%B3%E5%8D%97" in seen["url"]


@pytest.mark.parametrize("bad", ["", "../evil", "a/b", "a\\b", ".", "..", "  "])
def test_download_config_rejects_unsafe_names(monkeypatch, tmp_path, bad):
    monkeypatch.setattr("core.onlineclass.configs.ONLINE_CLASS_DIR", tmp_path)
    with pytest.raises(ValueError, match="配置名"):
        download_config(bad)


def test_download_config_network_error(monkeypatch, tmp_path):
    monkeypatch.setattr("core.onlineclass.configs.ONLINE_CLASS_DIR", tmp_path)

    def boom(url, timeout=20):
        raise OSError("404 Not Found")

    monkeypatch.setattr("core.onlineclass.configs._open_url", boom)
    with pytest.raises(RuntimeError, match="下载配置"):
        download_config("demo")
