"""
backend/config/logging_config.py

Structured logging setup for ERPSight backend.
Call setup_logging() once at application startup (api/main.py or scripts).
"""

import logging
import sys


def setup_logging(log_level: str = "INFO") -> None:
    """Configure root logger with a human-readable structured format."""
    fmt = "%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s"
    formatter = logging.Formatter(fmt=fmt, datefmt="%Y-%m-%d %H:%M:%S")

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Silence noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
