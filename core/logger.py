from loguru import logger
import sys
from pathlib import Path


def setup_logging():
    """配置全局日志"""
    # 移除默认的控制台输出（可选，默认是有的）
    logger.remove()

    # 控制台输出（带颜色，用于开发调试）
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level="DEBUG",
        colorize=True,
    )

    # 文件输出（生产环境）
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    logger.add(
        sink=log_dir / "log_{time}.log",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function} - {message}",
        rotation="5 MB",
        retention="7 days",
        compression="zip",
        encoding="utf-8",
        level="INFO",
    )

    logger.info("日志系统已初始化")
