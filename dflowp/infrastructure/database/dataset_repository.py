"""Repository für Datasets - Gruppierung von Daten."""

from typing import Any, Optional

from dflowp.infrastructure.database.mongo import get_database


class DatasetRepository:
    """Repository für Datasets (Gruppierung von Daten)."""

    COLLECTION_NAME = "datasets"

    def __init__(self) -> None:
        self._db = get_database()
        self._collection = self._db[self.COLLECTION_NAME]

    async def create_indexes(self) -> None:
        """Erstellt Indizes."""
        await self._collection.create_index("dataset_id", unique=True)

    async def insert(self, dataset: dict[str, Any]) -> str:
        """Speichert ein Dataset."""
        result = await self._collection.insert_one(dataset)
        return str(result.inserted_id)

    async def find_by_id(self, dataset_id: str) -> Optional[dict[str, Any]]:
        """Findet ein Dataset anhand der dataset_id."""
        doc = await self._collection.find_one({"dataset_id": dataset_id})
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc
