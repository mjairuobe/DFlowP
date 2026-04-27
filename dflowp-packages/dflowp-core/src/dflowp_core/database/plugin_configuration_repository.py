"""Repository für plugin_configuration-Dokumente (by_plugin_worker_id)."""

from math import ceil
from typing import Any, Optional

from dflowp_core.database.mongo import get_database
from dflowp_core.utils.logger import get_logger
from dflowp_core.utils.timestamps import enrich_document_timestamps

logger = get_logger(__name__)


class PluginConfigurationRepository:
    """Collection ``plugin_configurations`` – Konfig pro ``plugin_worker_id``."""

    COLLECTION_NAME = "plugin_configurations"

    def __init__(self) -> None:
        self._db = get_database()
        self._collection = self._db[self.COLLECTION_NAME]

    async def create_indexes(self) -> None:
        await self._collection.create_index("plugin_configuration_id", unique=True)

    @staticmethod
    def _string_id(doc: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
        if doc and "_id" in doc:
            doc["_id"] = str(doc["_id"])
        return doc

    async def insert(self, doc: dict[str, Any]) -> str:
        enrich_document_timestamps(doc)
        result = await self._collection.insert_one(doc)
        return str(result.inserted_id)

    async def find_by_id(self, plugin_configuration_id: str) -> Optional[dict[str, Any]]:
        d = await self._collection.find_one({"plugin_configuration_id": plugin_configuration_id})
        return self._string_id(d)

    async def list_configurations(
        self,
        *,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        total_items = await self._collection.count_documents({})
        skip = (page - 1) * page_size
        docs = (
            await self._collection.find({})
            .sort([("plugin_configuration_id", 1)])
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

    async def delete_by_id(self, plugin_configuration_id: str) -> bool:
        result = await self._collection.delete_one(
            {"plugin_configuration_id": plugin_configuration_id}
        )
        return result.deleted_count > 0
