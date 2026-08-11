from loguru import logger
import sys


def _console_format(record: dict) -> str:
    base = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>\n"
    )
    return base + "{exception}" if record["exception"] else base


def _file_format(record: dict) -> str:
    base = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function} - {message}\n"
    return base + "{exception}" if record["exception"] else base


def setup_logging():
    """配置全局日志"""
    # 移除默认的控制台输出（可选，默认是有的）
    logger.remove()

    # 控制台输出（带颜色，用于开发调试）
    logger.add(
        sys.stdout,
        format=_console_format,
        level="DEBUG",
        colorize=True,
    )

    # 文件输出（生产环境）
    from core.config import LOGS_DIR

    log_dir = LOGS_DIR / "fastapi"
    log_dir.mkdir(exist_ok=True, parents=True)

    logger.add(
        sink=log_dir / "log_{time}.log",
        format=_file_format,
        rotation="5 MB",
        retention="7 days",
        compression="zip",
        encoding="utf-8",
        level="INFO",
    )

    logger.info("日志系统已初始化")
