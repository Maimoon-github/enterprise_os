"""Application logging configuration.

Provides a single ``configure_logging`` entrypoint so log formatting and
levels are defined in exactly one place instead of being duplicated across
entrypoints and workers.
"""

from __future__ import annotations

import logging
import logging.config


def build_logging_config(level: str = "INFO") -> dict:
    """Return a ``logging.config.dictConfig``-compatible configuration dict."""

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": (
                    "%(asctime)s | %(levelname)-8s | %(name)s | "
                    "%(message)s"
                ),
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "level": level,
            },
        },
        "root": {
            "handlers": ["console"],
            "level": level,
        },
        "loggers": {
            "uvicorn": {"level": level, "propagate": True},
            "uvicorn.error": {"level": level, "propagate": True},
            "uvicorn.access": {"level": level, "propagate": True},
        },
    }


def configure_logging(level: str = "INFO") -> None:
    """Configure process-wide logging exactly once."""

    logging.config.dictConfig(build_logging_config(level=level))


def get_logger(name: str) -> logging.Logger:
    """Return a module-scoped logger."""

    return logging.getLogger(name)