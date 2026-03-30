"""Unified Repository für Data und Dataset Dokumente.

Speichert beide Typen in einer Collection `data_items` mit Discriminator `doc_type`.
"""

from typing import Any, Optional

from dflowp.infrastructure.database.mongo import get_database


class DataItemRepository:
    """Unified Repository für Data und Dataset Dokumente."""

    COLLECTION_NAME = "data_items"

    def __init__(self) -> None:
        self._db = get_database()
        self._collection = self._db[self.COLLECTION_NAME]

    async def create_indexes(self) -> None:
        await self._collection.create_index("id", unique=True)
        await self._collection.create_index("doc_type")

    def _validate(self, doc: dict[str, Any]) -> None:
        doc_type = doc.get("doc_type")
        if not doc_type:
            raise ValueError("doc_type field is required")
        if doc_type not in ("data", "dataset"):
            raise ValueError("Invalid doc_type")

        if "id" not in doc:
            raise ValueError("id field is required")

        if doc_type == "data":
            if "content" not in doc:
                raise ValueError("content field is required")
        if doc_type == "dataset":
            if "data_ids" not in doc:
                raise ValueError("data_ids field is required")

    async def insert(self, doc: dict[str, Any]) -> str:
        """Fügt ein Dokument ein und gibt die Mongo _id als String zurück."""
        self._validate(doc)
        result = await self._collection.insert_one(doc)
        return str(result.inserted_id)

    async def find_by_id(self, id: str) -> Optional[dict[str, Any]]:
        """Findet ein Dokument anhand des unified `id` Feldes."""
        doc = await self._collection.find_one({"id": id})
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc

"""Einheitliches Repository für Daten und Datasets."""

from typing import Any, Optional, Literal

from dflowp.infrastructure.database.mongo import get_database


class DataItemRepository:
    """
    Einheitliches Repository für sowohl Data als auch Dataset Dokumente.

    Ein einzelnes MongoDB-Dokument kann eine von zwei Arten sein:
    - doc_type: "data" - Enthält tatsächliche Daten mit content-Feld
    - doc_type: "dataset" - Enthält Referenzen auf andere Data-Dokumente

    Das "id"-Feld speichert entweder data_id oder dataset_id.
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

    async def insert(self, doc: dict[str, Any]) -> str:
        """
        Speichert ein Dokument (Data oder Dataset).

        Das Dokument muss folgende Felder haben:
        - doc_type: "data" oder "dataset"
        - Wenn doc_type="data": id (data_id), content, type
        - Wenn doc_type="dataset": id (dataset_id), data_ids

        Gibt die MongoDB _id zurück.
        """
        # Validiere, dass doc_type und id vorhanden sind
        if "doc_type" not in doc:
            raise ValueError("doc_type field is required")
        if "id" not in doc:
            raise ValueError("id field is required")

        doc_type = doc["doc_type"]
        if doc_type not in ("data", "dataset"):
            raise ValueError(f"Invalid doc_type: {doc_type}. Must be 'data' or 'dataset'")

        # Validiere erforderliche Felder basierend auf doc_type
        if doc_type == "data":
            if "content" not in doc:
                raise ValueError("content field is required for data documents")
        elif doc_type == "dataset":
            if "data_ids" not in doc:
                raise ValueError("data_ids field is required for dataset documents")

        result = await self._collection.insert_one(doc)
        return str(result.inserted_id)

    async def find_by_id(self, item_id: str) -> Optional[dict[str, Any]]:
        """
        Findet ein Dokument anhand seiner ID.

        Args:
            item_id: Die ID (data_id oder dataset_id)

        Returns:
            Das Dokument oder None, wenn nicht gefunden
        """
        doc = await self._collection.find_one({"id": item_id})
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc
