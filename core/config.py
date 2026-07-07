"""项目路径配置"""
from pathlib import Path

# 项目根目录（core/ 的上一级），等价于软件根目录
BASE_DIR = Path(__file__).resolve().parent.parent

# 常用子目录（按需引用）
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
LOGS_DIR = BASE_DIR / "logs"
