"""Central logging utilities for the automation stack."""
from __future__ import annotations

import logging
import os
from logging import Logger
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Final


_ROOT_LOGGER_NAME: Final[str] = "automation"
_CONFIGURED: bool = False


def _string_to_level(level_name: str) -> int:
    level = getattr(logging, level_name.upper(), None)
    if isinstance(level, int):
        return level
    return logging.INFO


def configure_logging(force: bool = False) -> Logger:
    """Configure the shared automation logger based on environment variables."""
    global _CONFIGURED
    logger = logging.getLogger(_ROOT_LOGGER_NAME)
    if _CONFIGURED and not force:
        return logger

    level_name = os.getenv("LOG_LEVEL", "INFO")
    level = _string_to_level(level_name)
    log_format = os.getenv(
        "LOG_FORMAT",
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    )
    date_format = os.getenv("LOG_DATE_FORMAT", "%Y-%m-%d %H:%M:%S")

    # Reset handlers to avoid duplicates when reconfiguring.
    for handler in list(logger.handlers):
        logger.removeHandler(handler)

    logger.setLevel(level)
    logger.propagate = False

    formatter = logging.Formatter(log_format, datefmt=date_format)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    if os.getenv("LOG_FILE", "false").lower() in {"1", "true", "yes"}:
        log_dir = Path(os.getenv("LOG_DIR", "logs"))
        log_dir.mkdir(parents=True, exist_ok=True)
        file_name = os.getenv("LOG_FILE_NAME", "test.log")
        file_path = log_dir / file_name
        try:
            max_bytes = int(os.getenv("LOG_MAX_BYTES", str(10 * 1024 * 1024)))
        except ValueError:
            max_bytes = 10 * 1024 * 1024
        try:
            backup_count = int(os.getenv("LOG_BACKUP_COUNT", "3"))
        except ValueError:
            backup_count = 3

        file_handler = RotatingFileHandler(
            file_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    _CONFIGURED = True
    return logger


def get_logger(name: str | None = None) -> Logger:
    """Return a child logger with the shared configuration."""
    configure_logging()
    if not name:
        return logging.getLogger(_ROOT_LOGGER_NAME)
    return logging.getLogger(f"{_ROOT_LOGGER_NAME}.{name}")


__all__ = ["configure_logging", "get_logger"]
