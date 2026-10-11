"""Logging configuration for the air-alerts-forecast project."""
from __future__ import annotations

import logging
import sys


def get_logger(name: str = "air_alerts", level: str = "INFO") -> logging.Logger:
    """Return a configured logger with console output.

    Args:
        name: Logger name.
        level: Logging level string.

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False
    return logger


def set_level(level: str) -> None:
    """Set the logging level on the root project logger."""
    get_logger().setLevel(getattr(logging, level.upper(), logging.INFO))
