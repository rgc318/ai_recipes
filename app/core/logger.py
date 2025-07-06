# app/logger.py
from loguru import logger
import sys
import os
from pathlib import Path

# 获取运行环境
ENV = os.getenv("ENV", "development").lower()

# 日志目录
log_dir = Path("logs")
log_dir.mkdir(parents=True, exist_ok=True)

# 日志文件路径
log_file_path = log_dir / "app.log"
log_json_path = log_dir / "app.json"

# 清除默认 handler
logger.remove()

# 控制台输出
logger.add(
    sys.stderr,
    level="DEBUG" if ENV == "development" else "INFO",
    colorize=True,
    enqueue=True,
    backtrace=True,
    diagnose=True,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
           "<level>{level: <8}</level> | "
           "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
           "<level>{message}</level>"
)

# 普通文本日志输出到文件
logger.add(
    log_file_path,
    level="DEBUG",
    rotation="10 MB",
    retention="7 days",
    encoding="utf-8",
    enqueue=True,
    backtrace=True,
    diagnose=True
)

# JSON 结构化日志输出
logger.add(
    log_json_path,
    level="WARNING",  # 只记录警告及以上
    rotation="1 day",
    retention="7 days",
    serialize=True,
    encoding="utf-8",
    enqueue=True
)

#打印当前日志环境
logger.debug(f"Log system initialized in {ENV} mode.")
