"""Logging helpers."""

from __future__ import annotations

import logging
import sys


class ColorFormatter(logging.Formatter):
    """Small color formatter for terminal output."""

    COLORS = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[35m",
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        copied = logging.makeLogRecord(record.__dict__)
        color = self.COLORS.get(copied.levelname)
        if color and sys.stdout.isatty():
            copied.levelname = f"{color}{copied.levelname}{self.RESET}"
        return super().format(copied)


def configure_logging(level: str) -> logging.Logger:
    """Configure and return the package logger."""
    logger = logging.getLogger("joflux")
    logger.handlers.clear()
    logger.setLevel(level)
    logger.propagate = False

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(ColorFormatter("%(asctime)s - %(levelname)s - %(message)s", "%H:%M:%S"))
    logger.addHandler(handler)
    return logger
