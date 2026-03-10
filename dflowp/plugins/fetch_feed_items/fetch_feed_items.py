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
        if not data_repository:
            raise ValueError("data_repository erforderlich")

        results: list[IOTransformationState] = []

        for input_data in context.input_data:
            source = input_data.content
            xml_url = source.get("xmlUrl", source.get("url", ""))
            title = source.get("title", "Unknown")
            if not xml_url:
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
                for entry in parsed.entries:
                    article = self._entry_to_article(entry, source)
                    data_id = f"data_article_{context.process_id}_{uuid.uuid4().hex[:12]}"
                    await data_repository.insert({
                        "data_id": data_id,
                        "content": article,
                        "type": "output",
                    })
                    output_ids.append(data_id)

                quality = 1.0 if output_ids else 0.0
                results.append(
                    IOTransformationState(
                        input_data_id=input_data.data_id,
                        output_data_ids=output_ids,
                        status=TransformationStatus.FINISHED,
                        quality=quality,
                    )
                )
            except Exception as e:
                results.append(
                    IOTransformationState(
                        input_data_id=input_data.data_id,
                        output_data_ids=[],
                        status=TransformationStatus.FAILED,
                        quality=0.0,
                    )
                )
                raise

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
