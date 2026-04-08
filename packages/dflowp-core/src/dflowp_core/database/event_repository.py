"""Repository für Events - persistente Speicherung von Events in MongoDB."""

from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Optional

from dflowp_core.database.mongo import get_database
from dflowp_core.utils.timestamps import enrich_with_timestamps


class EventRepository:
    """Repository für die persistente Speicherung von Events."""

    COLLECTION_NAME = "events"

    def __init__(self) -> None:
        self._db = get_database()
        self._collection = self._db[self.COLLECTION_NAME]

    async def create_indexes(self) -> None:
        """Erstellt Indizes für effiziente Abfragen."""
        await self._collection.create_index("process_id")
        await self._collection.create_index("subprocess_id")
        await self._collection.create_index("event_time")
        await self._collection.create_index("timestamp_ms")
        await self._collection.create_index("delivered_at")
        await self._collection.create_index([("process_id", 1), ("timestamp_ms", -1)])
        await self._collection.create_index([("process_id", 1), ("event_time", 1)])
        await self._collection.create_index([("event_type", 1), ("event_time", 1)])
        await self._collection.create_index([("delivered_at", 1), ("timestamp_ms", 1)])

    async def insert(self, event: dict[str, Any]) -> str:
        """
        Speichert ein Event in der Datenbank.

        Args:
            event: Event-Dokument (mit process_id, subprocess_id, event_type, etc.)

        Returns:
            Die _id des eingefügten Dokuments als String
        """
        enriched_event = enrich_with_timestamps(event)
        enriched_event["event_time"] = enriched_event.get("event_time") or datetime.now(timezone.utc)
        result = await self._collection.insert_one(enriched_event)
        return str(result.inserted_id)

    async def list_undelivered_events(self, *, limit: int = 100) -> list[dict[str, Any]]:
        """
        Liefert Events, die noch nicht an das externe Eventsystem ausgeliefert wurden.

        Ein Event gilt als ausgeliefert, wenn das Feld ``delivered_at`` gesetzt ist.
        """
        docs = (
            await self._collection.find(
                {"$or": [{"delivered_at": {"$exists": False}}, {"delivered_at": None}]}
            )
            .sort("timestamp_ms", 1)
            .limit(limit)
            .to_list(length=limit)
        )
        items: list[dict[str, Any]] = []
        for doc in docs:
            doc["_id"] = str(doc["_id"])
            items.append(doc)
        return items

    async def mark_delivered(self, event_id: str) -> bool:
        """
        Markiert ein Event als ausgeliefert.
        """
        from bson import ObjectId

        if not ObjectId.is_valid(event_id):
            return False
        result = await self._collection.update_one(
            {"_id": ObjectId(event_id)},
            {
                "$set": {"delivered_at": datetime.now(timezone.utc), "last_delivery_error": None},
                "$inc": {"delivery_attempts": 1},
            },
        )
        return result.modified_count > 0

    async def mark_delivery_failed(self, event_id: str, error: str) -> bool:
        """
        Aktualisiert Metadaten für einen fehlgeschlagenen Delivery-Versuch.
        """
        from bson import ObjectId

        if not ObjectId.is_valid(event_id):
            return False
        result = await self._collection.update_one(
            {"_id": ObjectId(event_id)},
            {
                "$set": {"last_delivery_error": error},
                "$inc": {"delivery_attempts": 1},
            },
        )
        return result.modified_count > 0

    async def list_events(
        self,
        *,
        page: int,
        page_size: int,
        process_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Liefert paginierte Event-Dokumente."""
        query: dict[str, Any] = {}
        if process_id:
            query["process_id"] = process_id

        total_items = await self._collection.count_documents(query)
        skip = (page - 1) * page_size
        docs = (
            await self._collection.find(query)
            .sort("timestamp_ms", -1)
            .skip(skip)
            .limit(page_size)
            .to_list(length=page_size)
        )
        items: list[dict[str, Any]] = []
        for doc in docs:
            doc["_id"] = str(doc["_id"])
            items.append(doc)
        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total_items": total_items,
            "total_pages": (total_items + page_size - 1) // page_size if total_items else 0,
        }

    async def find_by_id(self, event_id: str) -> Optional[dict[str, Any]]:
        """Liest ein Event anhand der MongoDB-_id."""
        from bson import ObjectId

        if not ObjectId.is_valid(event_id):
            return None
        doc = await self._collection.find_one({"_id": ObjectId(event_id)})
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc

    async def find_by_process_id(
        self,
        process_id: str,
        event_type: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Findet alle Events für einen Prozess.

        Args:
            process_id: Die Prozess-ID
            event_type: Optional - filtert nach Event-Typ
            limit: Optional - maximale Anzahl zurückzugebender Events
        """
        query: dict[str, Any] = {"process_id": process_id}
        if event_type:
            query["event_type"] = event_type

        cursor = self._collection.find(query).sort("event_time", 1)
        if limit:
            cursor = cursor.limit(limit)

        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            yield doc

    async def find_by_subprocess_id(
        self,
        process_id: str,
        subprocess_id: str,
        event_type: Optional[str] = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Findet alle Events für einen bestimmten Teilprozess."""
        query: dict[str, Any] = {
            "process_id": process_id,
            "subprocess_id": subprocess_id,
        }
        if event_type:
            query["event_type"] = event_type

        async for doc in self._collection.find(query).sort("event_time", 1):
            doc["_id"] = str(doc["_id"])
            yield doc

    async def get_latest_event(
        self,
        process_id: str,
        subprocess_id: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Holt das neueste Event für einen Prozess (ggf. spezifischen Teilprozess)."""
        query: dict[str, Any] = {"process_id": process_id}
        if subprocess_id:
            query["subprocess_id"] = subprocess_id

        doc = await self._collection.find_one(
            query,
            sort=[("event_time", -1)],
        )
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc

    async def count_by_process(self, process_id: str) -> int:
        """Zählt alle Events eines Prozesses."""
        return await self._collection.count_documents({"process_id": process_id})
