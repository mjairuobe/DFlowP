"""FetchFeedItems - Holt Artikel aus RSS-Feeds. 1 Feed -> N Artikel."""

import uuid
from typing import Any, Optional

import feedparser
import httpx

from dflowp.core.subprocesses.subprocess import BaseSubprocess
from dflowp.core.subprocesses.subprocess_context import SubprocessContext
from dflowp.core.subprocesses.io_transformation_state import (
    IOTransformationState,
    TransformationStatus,
)
from dflowp.core.datastructures.data import Data
from dflowp.utils.document_naming import build_human_readable_document_id
from dflowp.utils.logger import get_logger

logger = get_logger(__name__)


class FetchFeedItems(BaseSubprocess):
    """
    Nimmt eine Liste von RSS-Feeds (aus Dataset/JSON) und fetched alle Feeds.
    Output: Einzelne Artikel mit Quelle (1 Feed -> N Artikel).
    """

    def __init__(self) -> None:
        super().__init__("FetchFeedItems")

    async def run(
        self,
        context: SubprocessContext,
        event_emitter: Optional[Any] = None,
        state_updater: Optional[Any] = None,
        data_repository: Optional[Any] = None,
        dataset_repository: Optional[Any] = None,
    ) -> list[IOTransformationState]:
        source = f"[{context.process_id}][{context.subprocess_id}]"
        if not data_repository:
            raise ValueError("data_repository erforderlich")

        results: list[IOTransformationState] = []
        logger.info("%s starte Feed-Verarbeitung für %d Inputs", source, len(context.input_data))

        for input_data in context.input_data:
            source = input_data.content
            xml_url = source.get("xmlUrl", source.get("url", ""))
            title = source.get("title", "Unknown")
            if not xml_url:
                logger.warning("%s fehlende xmlUrl für Input '%s'", source, title)
                results.append(
                    IOTransformationState(
                        input_data_id=input_data.data_id,
                        output_data_ids=[],
                        status=TransformationStatus.FAILED,
                        quality=0.0,
                    )
                )
                continue

            output_ids: list[str] = []
            try:
                parsed = await self._fetch_feed(xml_url)
                logger.progress("%s Feed geladen: %s (%d entries)", source, xml_url, len(parsed.entries))
                for entry in parsed.entries:
                    # TODO: Set quality of article based on entry attributes
                    article = self._entry_to_article(entry, source)
                    data_id = build_human_readable_document_id(
                        domain="news",
                        document_type="data",
                    )
                    await data_repository.insert({
                        "data_id": data_id,
                        "content": article,
                        "type": "output",
                    })
                    output_ids.append(data_id)

                quality = 1.0 if output_ids else 0.0
                logger.success(
                    "%s Feed '%s' verarbeitet, %d Artikel gespeichert",
                    source,
                    title,
                    len(output_ids),
                )
                results.append(
                    IOTransformationState(
                        input_data_id=input_data.data_id,
                        output_data_ids=output_ids,
                        status=TransformationStatus.FINISHED,
                        quality=quality,
                    )
                )
            except Exception as e:
                logger.error("%s Fehler beim Feed '%s': %s", source, title, e)
                results.append(
                    IOTransformationState(
                        input_data_id=input_data.data_id,
                        output_data_ids=[],
                        status=TransformationStatus.FAILED,
                        quality=0.0,
                    )
                )
                # Kein raise: einzelne Feed-Fehler stoppen nicht die gesamte Verarbeitung

        return results

    async def _fetch_feed(self, url: str) -> Any:
        """Lädt RSS-Feed (async)."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(url)
            r.raise_for_status()
            return feedparser.parse(r.text)

    def _entry_to_article(self, entry: Any, source: dict) -> dict:
        """Konvertiert Feed-Entry zu Artikel mit Quelle."""
        return {
            "title": getattr(entry, "title", ""),
            "link": getattr(entry, "link", ""),
            "summary": getattr(entry, "summary", getattr(entry, "description", "")),
            "published": getattr(entry, "published", ""),
            "source": {
                "title": source.get("title", ""),
                "xmlUrl": source.get("xmlUrl", source.get("url", "")),
                "htmlUrl": source.get("htmlUrl", ""),
            },
        }
