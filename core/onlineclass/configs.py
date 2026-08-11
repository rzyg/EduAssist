"""自动化流程配置管理 —— data/onlineclass 目录的扫描与路径解析。

所有刷课剧本统一存放在 ``data/onlineclass/*.yaml``,对外以**文件名(不带后缀)**
引用,内部解析为完整路径;另支持从在线配置仓库(AList 直链)拉取列表与下载。
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from core.config import DATA_DIR

# 剧本目录(测试中可整体替换为临时目录)
ONLINE_CLASS_DIR = Path(DATA_DIR) / "onlineclass"

# 在线配置仓库(AList 直链):目录路径 + 文件列表地址
ONLINE_CONFIGS_DIR = "下班工具箱/.onlineclass-configs"
# 目录路径已整体百分号编码(仅保留 /),BASE 本身即以编码后的目录路径结尾
ONLINE_CONFIGS_BASE = "https://alist.bbts.fun/d/" + urllib.parse.quote(
    ONLINE_CONFIGS_DIR, safe="/"
)
# 文件列表直接挂在 BASE 末尾,不能再拼接未编码的目录(否则 URL 出现裸中文,
# urllib 底层按 ascii 编码请求行会抛 UnicodeEncodeError)
ONLINE_CONFIGS_FILELIST_URL = ONLINE_CONFIGS_BASE + "/.filelist.json"


def list_local_configs() -> list[dict]:
    """扫描本地剧本目录,返回 ``[{name, created_at}]`` 列表。

    - ``name``: 文件名不带后缀(如 ``example``)
    - ``created_at``: 文件创建时间(ISO 8601 字符串)
    """
    results = []
    config_dir = Path(ONLINE_CLASS_DIR)
    if not config_dir.is_dir():
        logger.warning(f"剧本目录不存在: {config_dir}")
        return results
    for path in sorted(config_dir.glob("*.yaml")):
        results.append(
            {
                "name": path.stem,
                "created_at": _iso_time(path.stat().st_ctime),
            }
        )
    return results


def resolve_config_path(config_name: str) -> Path:
    """按文件名(不带后缀)解析剧本完整路径,不存在则抛 FileNotFoundError。

    同时兼容带后缀的写法(``"example"`` 与 ``"example.yaml"`` 均接受)。
    """
    name = str(config_name).strip()
    if name.endswith(".yaml"):
        name = name[: -len(".yaml")]
    path = Path(ONLINE_CLASS_DIR) / f"{name}.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"配置不存在: {config_name}")
    return path


# ── 在线配置仓库(AList 直链) ───────────────────────────────────────────
def _make_ssl_context() -> Any:
    """构造带 CA 校验的 TLS 上下文。

    显式使用 certifi 的 CA 包(cacert.pem),避开 Windows 证书存储:本机证书库
    存在损坏条目时(与 schannel 异常同源),Python 3.11 的 ``create_default_context``
    加载默认证书会报 ``[ASN1: NOT_ENOUGH_DATA] not enough data``。
    传入 ``cafile`` 后 CPython 不会再去读系统证书存储。
    """
    import ssl

    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        # 极端兜底:certifi 不可用且证书库损坏时,放弃校验以恢复可用性
        logger.warning("certifi 不可用,在线配置请求将跳过证书校验")
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx


# 禁用环境代理:urllib 默认读取 HTTP(S)_PROXY / ALL_PROXY,若后端进程继承了
# 代理设置,TLS 请求会被发给代理导致握手异常;AList 直链可直连,无需代理
_OPENER = urllib.request.build_opener(
    urllib.request.ProxyHandler({}),
    urllib.request.HTTPSHandler(context=_make_ssl_context()),
)


def _open_url(url: str, timeout: int = 20) -> Any:
    """打开远程 URL 返回文件对象(独立函数便于测试打桩)。

    兜底:URL 中若残留非 ASCII 字符(如拼接漏了编码的中文),先百分号编码,
    否则 urllib 底层按 ascii 编码 HTTP 请求行会抛 UnicodeEncodeError。
    """
    if any(ord(ch) > 127 for ch in url):
        url = urllib.parse.quote(url, safe="%/:=&?~#+!$,;'@()*[]|")
    return _OPENER.open(url, timeout=timeout)


def list_online_configs() -> list[dict]:
    """拉取在线配置列表,返回 ``[{name, updated_at}]``。

    - ``name``: 文件名不带后缀(与本地列表 ``list_local_configs`` 一致)
    - ``updated_at``: 远端更新时间(ISO 8601 字符串,缺失时为 None)
    网络 / 解析异常抛 RuntimeError(由路由映射为 502)。
    """
    try:
        with _open_url(ONLINE_CONFIGS_FILELIST_URL) as resp:
            raw = resp.read().decode("utf-8")
    except Exception as exc:
        raise RuntimeError(f"无法获取在线配置列表: {exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"在线配置列表格式异常: {exc}") from exc
    results = []
    for item in data.get("filelist") or []:
        filename = str(item.get("filename") or "").strip()
        if not filename.endswith(".yaml"):
            continue  # 只认 YAML 剧本,忽略其他文件
        updated_at = None
        ts = item.get("updateTimestamp")
        if ts:
            try:
                updated_at = _iso_time(int(ts))
            except (TypeError, ValueError):
                updated_at = None
        results.append({"name": filename[: -len(".yaml")], "updated_at": updated_at})
    return results


def download_config(name: str) -> Path:
    """下载在线配置到本地剧本目录(自动创建目录),返回保存路径。

    - ``name``: 配置文件名(带或不带 .yaml 后缀均可)
    - 文件名含路径分隔符等非法字符抛 ValueError
    - 网络 / 下载异常抛 RuntimeError
    """
    filename = str(name).strip()
    if not filename:
        raise ValueError("配置名不能为空")
    # 防路径穿越:仅允许纯文件名,拒绝分隔符与 . / ..(须在拼 .yaml 后缀前校验)
    if filename in (".", "..") or "/" in filename or "\\" in filename:
        raise ValueError(f"非法的配置名: {name!r}")
    filename = filename if filename.endswith(".yaml") else f"{filename}.yaml"
    url = ONLINE_CONFIGS_BASE + "/" + urllib.parse.quote(filename)
    try:
        with _open_url(url, timeout=30) as resp:
            content = resp.read()
    except Exception as exc:
        raise RuntimeError(f"下载配置 {name!r} 失败: {exc}") from exc
    dest_dir = Path(ONLINE_CLASS_DIR)
    dest_dir.mkdir(parents=True, exist_ok=True)  # 自动创建剧本目录
    dest = dest_dir / filename
    dest.write_bytes(content)
    logger.info(f"在线配置已下载: {filename} -> {dest}")
    return dest


def _iso_time(timestamp: float) -> str:
    """时间戳转 ISO 8601 字符串(本地时区)。"""
    return datetime.fromtimestamp(timestamp).isoformat()
