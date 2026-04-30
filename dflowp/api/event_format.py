"""Einheitliche API-Ausgabe für Event-Dokumente (keine Legacy-Schlüssel)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def format_event_for_api(doc: dict[str, Any]) -> dict[str, Any]:
    """
    Baut ein Event-Dokument mit nur den gewünschten, snake_case-Feldern.
    Es werden nur Pipeline-/Plugin-Worker-Felder ausgegeben.
    """
    out: dict[str, Any] = {}
    if "_id" in doc:
        out["_id"] = str(doc["_id"])
    for key in (
        "pipeline_id",
        "plugin_worker_id",
        "event_type",
        "event_time",
        "timestamp_ms",
        "timestamp_human",
        "delivered_at",
        "payload",
    ):
        if key in doc and doc[key] is not None:
            out[key] = doc[key]
    rep = doc.get("plugin_worker_replica_id", 1)
    out["plugin_worker_replica_id"] = int(rep) if rep is not None else 1
    return out


def format_event_page(page: dict[str, Any]) -> dict[str, Any]:
    p = deepcopy(page)
    p["items"] = [format_event_for_api(x) for x in p.get("items", [])]
    return p
