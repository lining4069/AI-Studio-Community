# app/core/logger.py（改进版）
import sys

from loguru import logger

from app.core.settings import get_settings

app_settings = get_settings()
LOG_DIR = app_settings.BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

# 使用内部标记防止重复配置
_is_configured = False

logger.remove()  # 清除默认 handler

LOG_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level>"
)


def setup_logger(retention_days: int = 14):
    global _is_configured

    if _is_configured:
        return logger  # 已配置，直接返回，避免重复添加 handler

    # 1. 标准输出
    logger.add(
        sys.stdout,
        format=LOG_FORMAT,
        level="INFO",
        colorize=True,
    )

    # 2. 文件日志
    logger.add(
        LOG_DIR / "app_{time:YYYY-MM-DD}.log",
        format=LOG_FORMAT,
        level="DEBUG",
        rotation="00:00",
        retention=f"{retention_days} days",
        encoding="utf-8",
        enqueue=True,
        backtrace=True,
        diagnose=True,
    )

    # 3. 错误日志
    logger.add(
        LOG_DIR / "error_{time:YYYY-MM-DD}.log",
        format=LOG_FORMAT,
        level="ERROR",
        rotation="00:00",
        retention=f"{retention_days} days",
        encoding="utf-8",
        enqueue=True,
    )

    _is_configured = True
    return logger


# 导出配置好的 logger
__all__ = ["logger", "setup_logger"]
