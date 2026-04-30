"""Logging für DFlowP mit farbigen Loglevels und Quellenkontext."""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

PROGRESS_LEVEL = 25
SUCCESS_LEVEL = 35

logging.addLevelName(PROGRESS_LEVEL, "PROGRESS")
logging.addLevelName(SUCCESS_LEVEL, "SUCCESS")


class _SourceFieldFilter(logging.Filter):
    """Sorgt dafür, dass jedes Log-Record ein `source` Feld enthält."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "source"):
            record.source = record.name
        return True


class _ColorFormatter(logging.Formatter):
    """Formatter mit ANSI-Farben für Loglevel."""

    RESET = "\033[0m"
    LEVEL_COLORS = {
        "DEBUG": "\033[90m",
        "INFO": "\033[34m",
        "PROGRESS": "\033[36m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[41m",
        "SUCCESS": "\033[32m",
    }

    def format(self, record: logging.LogRecord) -> str:
        levelname = record.levelname
        color = self.LEVEL_COLORS.get(levelname, "")
        record.levelname = f"{color}{levelname}{self.RESET}" if color else levelname
        try:
            return super().format(record)
        finally:
            record.levelname = levelname


def _progress(self: logging.Logger, message: str, *args: Any, **kwargs: Any) -> None:
    if self.isEnabledFor(PROGRESS_LEVEL):
        self._log(PROGRESS_LEVEL, message, args, **kwargs)


def _success(self: logging.Logger, message: str, *args: Any, **kwargs: Any) -> None:
    if self.isEnabledFor(SUCCESS_LEVEL):
        self._log(SUCCESS_LEVEL, message, args, **kwargs)


if not hasattr(logging.Logger, "progress"):
    logging.Logger.progress = _progress  # type: ignore[attr-defined]
if not hasattr(logging.Logger, "success"):
    logging.Logger.success = _success  # type: ignore[attr-defined]


def _resolve_level(default_level: int | str) -> int:
    env_level = os.environ.get("DFLOWP_LOG_LEVEL")
    level_value: int | str = env_level if env_level else default_level
    if isinstance(level_value, int):
        return level_value
    normalized = str(level_value).strip().upper()
    return logging._nameToLevel.get(normalized, logging.INFO)


def get_logger(name: str, level: int | str = logging.INFO) -> logging.Logger:
    """Erstellt und konfiguriert einen farbigen Logger für stdout."""
    logger = logging.getLogger(name)
    logger.setLevel(_resolve_level(level))
    logger.propagate = False

    has_dflowp_handler = any(
        isinstance(handler, logging.StreamHandler) and getattr(handler, "_dflowp_handler", False)
        for handler in logger.handlers
    )
    if not has_dflowp_handler:
        handler = logging.StreamHandler(sys.stdout)
        handler._dflowp_handler = True  # type: ignore[attr-defined]
        handler.addFilter(_SourceFieldFilter())
        handler.setFormatter(
            _ColorFormatter("%(asctime)s | %(levelname)s | [%(source)s] %(message)s")
        )
        logger.addHandler(handler)

    return logger


def get_component_logger(component: str, level: int | str = logging.INFO) -> logging.LoggerAdapter:
    """LoggerAdapter mit fixer Quellenangabe (z. B. Eventsystem, PipelineEngine)."""
    base_logger = get_logger(component, level=level)
    return logging.LoggerAdapter(base_logger, extra={"source": component})


def get_pipeline_plugin_worker_logger(
    pipeline_id: str,
    plugin_worker_id: str,
    level: int | str = logging.INFO,
) -> logging.LoggerAdapter:
    """LoggerAdapter mit Quelle im Format [pipeline_id][plugin_worker_id]."""
    source = f"[{pipeline_id}][{plugin_worker_id}]"
    base_logger = get_logger(f"dflowp.{source}", level=level)
    return logging.LoggerAdapter(base_logger, extra={"source": source})
