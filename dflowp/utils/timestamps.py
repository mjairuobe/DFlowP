"""Hilfsfunktionen für einheitliche Zeitstempel in MongoDB-Dokumenten."""

from datetime import datetime, timezone
from typing import Any


def enrich_with_timestamps(document: dict[str, Any]) -> dict[str, Any]:
    """
    Ergänzt ein Dokument um:
    - timestamp_unix_ms (Unixzeit in Millisekunden)
    - timestamp_human (Format dd-mm-yy)

    Bestehende Werte werden nicht überschrieben.
    """
    doc = dict(document)
    if "timestamp_unix_ms" in doc and "timestamp_human" in doc:
        return doc

    now = datetime.now(timezone.utc)
    doc.setdefault("timestamp_unix_ms", int(now.timestamp() * 1000))
    doc.setdefault("timestamp_human", now.strftime("%d-%m-%y"))
    return doc
