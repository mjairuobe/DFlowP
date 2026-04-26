"""Repository für Dataflow-Definitionen (DAG, wiederverwendbar)."""

from math import ceil
from typing import Any, Optional

from dflowp_core.database.mongo import get_database
from dflowp_core.utils.logger import get_logger
from dflowp_core.utils.timestamps import enrich_document_timestamps

logger = get_logger(__name__)


class DataflowRepository:
    """Statische Dataflow-Definitionen in der Collection ``dataflows``."""

    COLLECTION_NAME = "dataflows"

    def __init__(self) -> None:
        self._db = get_database()
        self._collection = self._db[self.COLLECTION_NAME]

    async def create_indexes(self) -> None:
        await self._collection.create_index("dataflow_id", unique=True)
        await self._collection.create_index("name")

    @staticmethod
    def _string_id(doc: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
        if doc and "_id" in doc:
            doc["_id"] = str(doc["_id"])
        return doc

    async def insert(self, doc: dict[str, Any]) -> str:
        enrich_document_timestamps(doc)
        result = await self._collection.insert_one(doc)
        return str(result.inserted_id)

    async def find_by_id(self, dataflow_id: str) -> Optional[dict[str, Any]]:
        d = await self._collection.find_one({"dataflow_id": dataflow_id})
        return self._string_id(d)

    async def list_dataflows(
        self,
        *,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        total_items = await self._collection.count_documents({})
        skip = (page - 1) * page_size
        docs = (
            await self._collection.find({})
            .sort([("dataflow_id", 1)])
            .skip(skip)
            .limit(page_size)
            .to_list(length=page_size)
        )
        items = [self._string_id(d) for d in docs]
        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total_items": total_items,
            "total_pages": ceil(total_items / page_size) if total_items else 0,
        }

    async def replace_by_id(self, dataflow_id: str, doc: dict[str, Any]) -> bool:
        enrich_document_timestamps(doc)
        result = await self._collection.replace_one({"dataflow_id": dataflow_id}, doc, upsert=False)
        return result.matched_count > 0

    async def delete_by_id(self, dataflow_id: str) -> bool:
        result = await self._collection.delete_one({"dataflow_id": dataflow_id})
        return result.deleted_count > 0
