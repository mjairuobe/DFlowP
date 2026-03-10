"""Repository für Input- und Output-Daten."""

from typing import Any, Optional

from dflowp.infrastructure.database.mongo import get_database


class DataRepository:
    """Repository für alle Input- und Output-Daten."""

    COLLECTION_NAME = "data"

    def __init__(self) -> None:
        self._db = get_database()
        self._collection = self._db[self.COLLECTION_NAME]

    async def create_indexes(self) -> None:
        """Erstellt Indizes."""
        await self._collection.create_index("data_id", unique=True)

    async def insert(self, data: dict[str, Any]) -> str:
        """Speichert Daten. Gibt die _id zurück."""
        result = await self._collection.insert_one(data)
        return str(result.inserted_id)

    async def find_by_id(self, data_id: str) -> Optional[dict[str, Any]]:
        """Findet Daten anhand der data_id."""
        doc = await self._collection.find_one({"data_id": data_id})
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc
