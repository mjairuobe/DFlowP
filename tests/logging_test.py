"""Tests für strukturierte und farbige Logging-Hilfen."""

from __future__ import annotations

import io
import logging

from dflowp_core.utils.logger import (
    _ColorFormatter,
    get_component_logger,
    get_process_subprocess_logger,
)


def test_color_formatter_renders_colored_levels() -> None:
    formatter = _ColorFormatter("%(levelname)s %(message)s")
    record = logging.LogRecord(
        name="test",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="kaputt",
        args=(),
        exc_info=None,
    )
    rendered = formatter.format(record)
    assert "\x1b[" in rendered
    assert "ERROR" in rendered
    assert "kaputt" in rendered


def test_component_logger_prefix_and_methods() -> None:
    logger = get_component_logger("Eventsystem")
    assert logger.extra["source"] == "Eventsystem"
    assert logger.logger.name == "Eventsystem"
    assert hasattr(logger.logger, "progress")
    assert hasattr(logger.logger, "success")


def test_process_subprocess_logger_name_contains_ids() -> None:
    logger = get_process_subprocess_logger(
        process_id="proc_alpha",
        subprocess_id="EmbedData1",
    )
    assert logger.extra["source"] == "[proc_alpha][EmbedData1]"
    assert logger.logger.name == "dflowp.[proc_alpha][EmbedData1]"
