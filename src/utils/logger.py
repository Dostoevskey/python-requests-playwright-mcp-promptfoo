"""Central logging utilities for the automation stack."""
from __future__ import annotations

import logging
import os
from typing import Optional

_LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"


def configure_logging(force: bool = False, level: Optional[int] = None) -> None:
    """Configure root logging, honouring LOG_LEVEL when provided."""
    log_level = level or getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO)
    logging.basicConfig(level=log_level, format=_LOG_FORMAT, force=force)


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Return a configured logger with a sensible default handler."""
    logger = logging.getLogger(name or "automation")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(_LOG_FORMAT))
        logger.addHandler(handler)
    logger.setLevel(logging.getLogger().level or logging.INFO)
    logger.propagate = False
    return logger


__all__ = ["configure_logging", "get_logger"]
