"""Qualitäts-Aggregation über IO-Output-Zeilen eines Plugin-Worker-Knotens."""

from __future__ import annotations

import statistics
from typing import Any, Iterator


def _iter_qualities_from_io_states(states: list[dict[str, Any]] | None) -> Iterator[float]:
    for s in states or []:
        q = s.get("quality")
        if isinstance(q, (int, float)) and not isinstance(q, bool):
            yield float(q)


def quality_min_max_avg_median(
    node: dict[str, Any],
) -> dict[str, float | None]:
    """
    Pro Plugin-Worker-Knoten: min, max, avg, median über alle numerischen
    ``quality``-Werte in ``io_transformation_states``.
    """
    vals = list(_iter_qualities_from_io_states(node.get("io_transformation_states")))
    if not vals:
        return {"min": None, "max": None, "avg": None, "median": None}
    return {
        "min": min(vals),
        "max": max(vals),
        "avg": float(statistics.fmean(vals)),
        "median": float(statistics.median(vals)),
    }
