# -*- coding: utf-8 -*-
"""forge.utils.logging_config — NetNomos Forge 统一日志配置模块.

提供统一的日志系统配置，支持：
- 控制台 + 文件双输出
- 日志轮转（按大小）
- 彩色控制台输出
- JSON 格式输出（可选）
- 环境变量控制

使用方式：
    from forge.utils.logging_config import setup_logging, get_logger

    # 在应用启动时调用
    setup_logging(
        level="INFO",
        log_dir="logs",
        json_format=False
    )

    # 在模块中获取logger
    log = get_logger("my.module")
    log.info("Hello, NetNomos Forge!")
"""
from __future__ import annotations

import json
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any


# ANSI 颜色代码
class Colors:
    """ANSI 颜色代码."""
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BOLD = "\033[1m"


# 日志级别颜色映射
LOG_COLORS = {
    logging.DEBUG: Colors.CYAN,
    logging.INFO: Colors.GREEN,
    logging.WARNING: Colors.YELLOW,
    logging.ERROR: Colors.RED,
    logging.CRITICAL: Colors.BOLD + Colors.RED,
}


class ColoredFormatter(logging.Formatter):
    """彩色控制台日志格式化器."""

    def __init__(self, fmt: str | None = None, datefmt: str | None = None, style: str = "%") -> None:
        """初始化彩色格式化器."""
        super().__init__(fmt, datefmt, style)
        self._base_fmt = fmt or "%(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s"

    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录，添加颜色."""
        level_color = LOG_COLORS.get(record.levelno, Colors.WHITE)
        record.levelname = f"{level_color}{record.levelname}{Colors.RESET}"
        record.name = f"{Colors.BLUE}{record.name}{Colors.RESET}"

        return super().format(record)


class JSONFormatter(logging.Formatter):
    """JSON 格式日志格式化器."""

    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录为 JSON."""
        log_data = {
            "timestamp": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
        }

        # 添加异常信息
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # 添加额外字段
        if hasattr(record, "extra_data"):
            log_data["extra"] = record.extra_data

        return json.dumps(log_data, ensure_ascii=False)


def setup_logging(
    level: str = "INFO",
    log_dir: str = "logs",
    json_format: bool = False,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
    console_level: str | None = None,
) -> None:
    """配置统一的日志系统.

    Args:
        level: 日志级别（DEBUG/INFO/WARNING/ERROR/CRITICAL），默认 INFO
        log_dir: 日志文件目录，默认 "logs"
        json_format: 是否输出 JSON 格式日志（仅文件），默认 False
        max_bytes: 单个日志文件最大大小，默认 10MB
        backup_count: 保留的日志文件数量，默认 5
        console_level: 控制台日志级别（独立控制），默认与 level 相同
    """
    # 解析日志级别
    log_level = getattr(logging, level.upper(), logging.INFO)
    console_log_level = getattr(logging, console_level.upper() if console_level else level.upper(), logging.INFO)

    # 创建日志目录
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # 获取根 logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # 清除现有 handlers（避免重复配置）
    root_logger.handlers.clear()

    # ========== 控制台 Handler ==========
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_log_level)

    if json_format:
        # JSON 格式（控制台也用 JSON，便于开发调试）
        console_formatter = JSONFormatter()
    else:
        # 彩色格式
        console_formatter = ColoredFormatter(
            fmt="%(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s",
            datefmt="%H:%M:%S",
        )

    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # ========== 文件 Handler ==========
    file_handler = RotatingFileHandler(
        log_path / "forge.log",
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)

    if json_format:
        # JSON 格式
        file_formatter = JSONFormatter()
    else:
        # 标准格式
        file_formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    # ========== 第三方库日志级别控制 ==========
    # 降低一些 noisy 库的日志级别
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    # 记录启动信息
    startup_logger = logging.getLogger("forge.logging")
    startup_logger.info("=" * 60)
    startup_logger.info("🚀 NetNomos Forge 日志系统已初始化")
    startup_logger.info("📁 日志目录: %s", log_path.absolute())
    startup_logger.info("📊 日志级别: %s (控制台: %s, 文件: %s)", level.upper(), console_level.upper() if console_level else level.upper(), level.upper())
    startup_logger.info("📝 日志格式: %s", "JSON" if json_format else "彩色文本")
    startup_logger.info("🔄 日志轮转: 最大 %d MB, 保留 %d 个文件", max_bytes // (1024 * 1024), backup_count)
    startup_logger.info("=" * 60)


def get_logger(name: str) -> logging.Logger:
    """获取模块专用 logger.

    Args:
        name: logger 名称，通常使用模块名（如 "forge.core.llm"）

    Returns:
        logging.Logger 实例

    Example:
        >>> from forge.utils.logging_config import get_logger
        >>> log = get_logger("my.module")
        >>> log.info("Hello, world!")
    """
    return logging.getLogger(name)


# 便捷函数
def get_log_level() -> str:
    """获取当前日志级别."""
    return logging.getLogger().getEffectiveLevel()


def set_log_level(level: str | int) -> None:
    """动态设置日志级别.

    Args:
        level: 日志级别（字符串或整数）
    """
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)

    logging.getLogger().setLevel(level)
    logging.getLogger("forge.logging").info("🎚️ 日志级别已动态调整为: %s", logging.getLevelName(level))


# 模块初始化时导出的符号
__all__ = [
    "setup_logging",
    "get_logger",
    "get_log_level",
    "set_log_level",
    "ColoredFormatter",
    "JSONFormatter",
]
