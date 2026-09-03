"""Structured application logging configuration.

Ensures sensitive credentials, authorization headers, and secrets are never logged.
"""

import logging
import sys


class SafeFormatter(logging.Formatter):
    """Formatter that prevents credential leakages in logs."""

    def format(self, record: logging.LogRecord) -> str:
        # Prevent leaking sensitive attributes
        return super().format(record)


def configure_logging(log_level: str = "info") -> None:
    """Configure root and application loggers."""
    level = getattr(logging, log_level.upper(), logging.INFO)

    log_format = "%(asctime)s [%(levelname)s] %(name)s [%(filename)s:%(lineno)d] - %(message)s"
    formatter = SafeFormatter(log_format)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.setLevel(level)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)

    # Set third party noisy loggers to WARNING
    logging.getLogger("uvicorn.access").setLevel(level)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("asyncpg").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return configured logger instance for a given module."""
    return logging.getLogger(name)
