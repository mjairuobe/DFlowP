"""Einheitliches Repository für Data- und Dataset-Dokumente."""

from math import ceil
from typing import Any, Optional

from dflowp.infrastructure.database.mongo import get_database


class DataItemRepository:
    """
    Einheitliches Repository für Data- und Dataset-Dokumente.

    Ein Dokument wird über das Feld ``doc_type`` unterschieden:
    - ``data``: enthält Dateninhalt (content)
    - ``dataset``: enthält Referenzen auf Daten (data_ids)
    """

    COLLECTION_NAME = "data_items"

    def __init__(self) -> None:
        self._db = get_database()
        self._collection = self._db[self.COLLECTION_NAME]

    async def create_indexes(self) -> None:
        """Erstellt Indizes für optimierte Abfragen."""
        await self._collection.create_index("id", unique=True)
        await self._collection.create_index("doc_type")
        await self._collection.create_index([("doc_type", 1), ("id", 1)])

    def _validate(self, doc: dict[str, Any]) -> None:
        if "doc_type" not in doc:
            raise ValueError("doc_type field is required")
        if "id" not in doc:
            raise ValueError("id field is required")

        doc_type = doc["doc_type"]
        if doc_type not in ("data", "dataset"):
            raise ValueError("Invalid doc_type")

        if doc_type == "data" and "content" not in doc:
            raise ValueError("content field is required")
        if doc_type == "dataset" and "data_ids" not in doc:
            raise ValueError("data_ids field is required")

    @staticmethod
    def _with_string_id(doc: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
        if doc and "_id" in doc:
            doc["_id"] = str(doc["_id"])
        return doc

    async def insert(self, doc: dict[str, Any]) -> str:
        """Speichert ein Dokument (Data oder Dataset) und gibt die MongoDB-_id zurück."""
        self._validate(doc)
        result = await self._collection.insert_one(doc)
        return str(result.inserted_id)

    async def find_by_id(self, item_id: str) -> Optional[dict[str, Any]]:
        """Findet ein Dokument anhand der ID (data_id oder dataset_id)."""
        doc = await self._collection.find_one({"id": item_id})
        return self._with_string_id(doc)

    async def find_dataset_by_id(self, dataset_id: str) -> Optional[dict[str, Any]]:
        """Findet ein Dataset-Dokument anhand der ID."""
        doc = await self._collection.find_one({"id": dataset_id, "doc_type": "dataset"})
        return self._with_string_id(doc)

    async def list_datasets(
        self,
        *,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        """Liefert paginierte Dataset-Dokumente."""
        query = {"doc_type": "dataset"}
        total_items = await self._collection.count_documents(query)
        skip = (page - 1) * page_size
        docs = await self._collection.find(query).sort("id", 1).skip(skip).limit(page_size).to_list(length=page_size)
        items = [self._with_string_id(doc) for doc in docs]
        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total_items": total_items,
            "total_pages": ceil(total_items / page_size) if total_items else 0,
        }
