"""Repository für Prozesse - Speicherung von Prozess-Konfigurationen und -Status."""

from typing import Any, Optional

from pymongo import ReturnDocument

from dflowp.infrastructure.database.mongo import get_database


class ProcessRepository:
    """Repository für alle Prozesse inkl. Konfigurationen."""

    COLLECTION_NAME = "processes"

    def __init__(self) -> None:
        self._db = get_database()
        self._collection = self._db[self.COLLECTION_NAME]

    async def create_indexes(self) -> None:
        """Erstellt Indizes für effiziente Abfragen."""
        await self._collection.create_index("process_id", unique=True)
        await self._collection.create_index("status")

    async def insert(self, process: dict[str, Any]) -> str:
        """Speichert einen Prozess. Gibt die _id zurück."""
        result = await self._collection.insert_one(process)
        return str(result.inserted_id)

    async def find_by_id(self, process_id: str) -> Optional[dict[str, Any]]:
        """Findet einen Prozess anhand der process_id."""
        doc = await self._collection.find_one({"process_id": process_id})
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc

    async def update(
        self,
        process_id: str,
        update: dict[str, Any],
    ) -> bool:
        """Aktualisiert einen Prozess. Gibt True zurück wenn gefunden."""
        result = await self._collection.update_one(
            {"process_id": process_id},
            {"$set": update},
        )
        return result.matched_count > 0

    async def claim_next_pending(self) -> Optional[dict[str, Any]]:
        """
        Übernimmt atomisch den ältesten Prozess mit status 'pending' (status -> 'running').
        Das Dokument muss wie bei insert die Felder process_id und configuration enthalten
        (optional dataflow_state; wird bei Bedarf ergänzt).
        """
        doc = await self._collection.find_one_and_update(
            {"status": "pending"},
            {"$set": {"status": "running"}},
            sort=[("_id", 1)],
            return_document=ReturnDocument.AFTER,
        )
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc
