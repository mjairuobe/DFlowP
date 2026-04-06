"""Hilfsfunktionen für einheitliche Zeitstempel in MongoDB-Dokumenten."""

from datetime import datetime, timezone
from typing import Any


def enrich_with_timestamps(document: dict[str, Any]) -> dict[str, Any]:
    """
    Ergänzt ein Dokument um:
    - timestamp_ms (Unixzeit in Millisekunden)
    - timestamp_dd_mm_yy (Format dd-mm-yy)

    Bestehende Werte werden nicht überschrieben.
    """
    doc = dict(document)
    if "timestamp_ms" in doc and "timestamp_dd_mm_yy" in doc:
        return doc

    now = datetime.now(timezone.utc)
    doc.setdefault("timestamp_ms", int(now.timestamp() * 1000))
    doc.setdefault("timestamp_dd_mm_yy", now.strftime("%d-%m-%y"))
    return doc


def add_timestamps(document: dict[str, Any]) -> dict[str, Any]:
    """Kompatibilitätsalias für bestehende Aufrufer."""
    return enrich_with_timestamps(document)


def enrich_document_timestamps(document: dict[str, Any]) -> dict[str, Any]:
    """Mutiert das übergebene Dict und ergänzt Timestamp-Felder."""
    enriched = enrich_with_timestamps(document)
    document.update(enriched)
    return document
