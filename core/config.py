"""项目配置 — 基于 YAML 文件，支持读写"""
from pathlib import Path
import os
import yaml

# ── 文件路径（优先环境变量，兼容 Nuitka exe CWD 偏移）────────────────────
_BASE_ENV = os.environ.get("EDUASSIST_BASE")
BASE_DIR = Path(_BASE_ENV) if _BASE_ENV else Path(__file__).resolve().parent.parent
CONFIG_FILE = BASE_DIR / "config.yaml"

# ── 默认配置 ─────────────────────────────────────────────────────────────
DEFAULT_CONFIG = {
    "server": {
        "host": "127.0.0.1",
        "port": 8000,
    },
    "paths": {
        "output": "output",
        "data": "data",
        "logs": "logs",
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    """递归合并字典，override 中的值覆盖 base"""
    merged = base.copy()
    for k, v in override.items():
        if k in merged and isinstance(merged[k], dict) and isinstance(v, dict):
            merged[k] = _deep_merge(merged[k], v)
        else:
            merged[k] = v
    return merged


def load_config() -> dict:
    """加载 YAML 配置，缺失字段用默认值补全，并写回文件"""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            user_config = yaml.safe_load(f) or {}
    else:
        user_config = {}

    # 递归合并，确保所有默认字段存在
    merged = _deep_merge(DEFAULT_CONFIG, user_config)

    # 如果用户文件缺失字段，回写补齐
    if user_config != merged:
        save_config(merged)

    return merged


def save_config(cfg: dict) -> None:
    """将配置写回 YAML 文件"""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


# ── 模块加载时自动读取配置 ──────────────────────────────────────────────
config = load_config()

# ── 派生路径（保留与旧代码的兼容性）──────────────────────────────────────
DATA_DIR   = BASE_DIR / config["paths"]["data"]
OUTPUT_DIR = BASE_DIR / config["paths"]["output"]
LOGS_DIR   = BASE_DIR / config["paths"]["logs"]
