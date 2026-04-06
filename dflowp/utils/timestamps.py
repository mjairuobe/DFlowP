"""Hilfsfunktionen für einheitliche Zeitstempel in MongoDB-Dokumenten."""

from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

BERLIN_TIMEZONE = ZoneInfo("Europe/Berlin")


def _format_timestamp_human_from_ms(timestamp_ms: int) -> str:
    """Formatiert Timestamp als ddmmyyyyHHMMUTC+n in Europe/Berlin."""
    dt_berlin = datetime.fromtimestamp(
        timestamp_ms / 1000,
        tz=timezone.utc,
    ).astimezone(BERLIN_TIMEZONE)
    utc_offset_hours = int((dt_berlin.utcoffset() or 0).total_seconds() // 3600)
    return f"{dt_berlin.strftime('%d%m%Y%H%M')}UTC{utc_offset_hours:+d}"


def enrich_with_timestamps(document: dict[str, Any]) -> dict[str, Any]:
    """
    Ergänzt ein Dokument um:
    - timestamp_ms (Unixzeit in Millisekunden)
    - timestamp_human (Format ddmmyyyyHHMMUTC+n, Europe/Berlin)

    Bestehende Werte werden nicht überschrieben.
    """
    doc = dict(document)
    if "timestamp_ms" in doc and "timestamp_human" in doc:
        return doc

    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    timestamp_ms = int(doc.get("timestamp_ms", now_ms))
    doc.setdefault("timestamp_ms", timestamp_ms)
    doc.setdefault("timestamp_human", _format_timestamp_human_from_ms(timestamp_ms))
    # Alte Feldbezeichnung nicht mehr in neue Dokumente übernehmen.
    doc.pop("timestamp_dd_mm_yy", None)
    return doc


def add_timestamps(document: dict[str, Any]) -> dict[str, Any]:
    """Kompatibilitätsalias für bestehende Aufrufer."""
    return enrich_with_timestamps(document)


def enrich_document_timestamps(document: dict[str, Any]) -> dict[str, Any]:
    """Mutiert das übergebene Dict und ergänzt Timestamp-Felder."""
    enriched = enrich_with_timestamps(document)
    document.update(enriched)
    return document
