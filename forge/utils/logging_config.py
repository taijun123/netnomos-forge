"""Shared logging setup for NetNomos Forge."""
from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any


class Colors:
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BOLD = "\033[1m"


LOG_COLORS = {
    logging.DEBUG: Colors.CYAN,
    logging.INFO: Colors.GREEN,
    logging.WARNING: Colors.YELLOW,
    logging.ERROR: Colors.RED,
    logging.CRITICAL: Colors.BOLD + Colors.RED,
}


def _level(value: str | int | None, default: int = logging.INFO) -> int:
    if isinstance(value, int):
        return value
    if not value:
        return default
    return getattr(logging, value.upper(), default)


class ColoredFormatter(logging.Formatter):
    """Console formatter that restores the record after coloring."""

    def format(self, record: logging.LogRecord) -> str:
        levelname = record.levelname
        name = record.name
        try:
            color = LOG_COLORS.get(record.levelno, Colors.WHITE)
            record.levelname = f"{color}{levelname}{Colors.RESET}"
            record.name = f"{Colors.BLUE}{name}{Colors.RESET}"
            return super().format(record)
        finally:
            record.levelname = levelname
            record.name = name


class JSONFormatter(logging.Formatter):
    """Formatter for structured JSON log files."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        extra_data = getattr(record, "extra_data", None)
        if extra_data is not None:
            payload["extra"] = extra_data
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(
    *,
    level: str | int = "INFO",
    log_dir: str = "logs",
    json_format: bool = False,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
    console_level: str | int | None = None,
) -> None:
    """Configure console and rotating file logging for the app."""

    file_level = _level(level)
    stdout_level = _level(console_level, file_level)
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(min(file_level, stdout_level))
    root_logger.handlers.clear()

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(stdout_level)
    console_handler.setFormatter(
        JSONFormatter()
        if json_format
        else ColoredFormatter(
            "%(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s"
        )
    )
    root_logger.addHandler(console_handler)

    file_handler = RotatingFileHandler(
        log_path / "forge.log",
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(file_level)
    file_handler.setFormatter(
        JSONFormatter()
        if json_format
        else logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s",
            "%Y-%m-%d %H:%M:%S",
        )
    )
    root_logger.addHandler(file_handler)

    for noisy_logger in ("uvicorn", "uvicorn.access", "httpx", "httpcore"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

    startup_logger = logging.getLogger("forge.logging")
    startup_logger.info("NetNomos Forge logging initialized")
    startup_logger.info("Log directory: %s", log_path.resolve())
    startup_logger.info(
        "Log levels: console=%s file=%s format=%s",
        logging.getLevelName(stdout_level),
        logging.getLevelName(file_level),
        "json" if json_format else "text",
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def get_log_level() -> str:
    return logging.getLevelName(logging.getLogger().getEffectiveLevel())


def set_log_level(level: str | int) -> None:
    parsed = _level(level)
    root_logger = logging.getLogger()
    root_logger.setLevel(parsed)
    for handler in root_logger.handlers:
        handler.setLevel(parsed)
    logging.getLogger("forge.logging").info(
        "Log level changed to %s", logging.getLevelName(parsed)
    )


__all__ = [
    "ColoredFormatter",
    "JSONFormatter",
    "get_log_level",
    "get_logger",
    "set_log_level",
    "setup_logging",
]
