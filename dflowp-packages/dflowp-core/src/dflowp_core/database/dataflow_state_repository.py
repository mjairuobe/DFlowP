"""Repository für DataflowState – eigene Collection ``dataflow_states``."""

from math import ceil
from typing import Any, Optional

from dflowp_core.database.mongo import get_database
from dflowp_core.utils.logger import get_logger
from dflowp_core.utils.timestamps import enrich_document_timestamps

logger = get_logger(__name__)


def _node_id_key(n: dict[str, Any]) -> str | None:
    return n.get("plugin_worker_id") or n.get("subprocess_id")


class DataflowStateRepository:
    """DataflowState-Dokumente inkl. eingebetteter io_transformation_states."""

    COLLECTION_NAME = "dataflow_states"

    def __init__(self) -> None:
        self._db = get_database()
        self._collection = self._db[self.COLLECTION_NAME]

    async def create_indexes(self) -> None:
        await self._collection.create_index("dataflow_state_id", unique=True)
        await self._collection.create_index("pipeline_id")
        await self._collection.create_index("dataflow_id")

    @staticmethod
    def _string_id(doc: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
        if doc and "_id" in doc:
            doc["_id"] = str(doc["_id"])
        return doc

    async def get_dataflow_state(self, dataflow_state_id: str) -> Optional[dict[str, Any]]:
        """
        Liefert die Map ``nodes``/``edges`` (ohne äußeren Schlüssel dataflow_state),
        kompatibel zur bisherigen Engine, die reine node/edge-Listen erwartet.
        """
        doc = await self._collection.find_one({"dataflow_state_id": dataflow_state_id})
        if not doc:
            return None
        inner = doc.get("dataflow_state")
        if isinstance(inner, dict) and (inner.get("nodes") is not None or inner.get("edges") is not None):
            return inner
        if doc.get("nodes") is not None or doc.get("edges") is not None:
            return {k: doc[k] for k in ("nodes", "edges") if k in doc}
        return None

    async def get_by_id(self, dataflow_state_id: str) -> Optional[dict[str, Any]]:
        """Volles State-Dokument inkl. Metadaten."""
        doc = await self._collection.find_one({"dataflow_state_id": dataflow_state_id})
        return self._string_id(doc)

    async def update_dataflow_state(
        self, dataflow_state_id: str, dataflow_state: dict[str, Any]
    ) -> bool:
        result = await self._collection.update_one(
            {"dataflow_state_id": dataflow_state_id},
            {
                "$set": {
                    "dataflow_state": dataflow_state,
                    "nodes": dataflow_state.get("nodes", []),
                    "edges": dataflow_state.get("edges", []),
                }
            },
        )
        return result.matched_count > 0

    async def update_node_state(
        self,
        dataflow_state_id: str,
        plugin_worker_id: str,
        event_status: Optional[str] = None,
        io_transformation_states: Optional[list[dict]] = None,
    ) -> bool:
        """Aktualisiert einen einzelnen Knoten (ID: plugin_worker_id, Legacy: subprocess_id)."""
        doc = await self._collection.find_one({"dataflow_state_id": dataflow_state_id})
        if not doc:
            return False

        inner = doc.get("dataflow_state")
        if not isinstance(inner, dict):
            inner = {k: doc[k] for k in ("nodes", "edges") if k in doc}
        if not inner:
            return False

        nodes = list(inner.get("nodes", []) or [])
        for i, n in enumerate(nodes):
            if _node_id_key(n) == plugin_worker_id:
                if event_status is not None:
                    nodes[i]["event_status"] = event_status
                if io_transformation_states is not None:
                    nodes[i]["io_transformation_states"] = io_transformation_states
                break
        else:
            return False

        new_state = {**inner, "nodes": nodes}
        return await self.update_dataflow_state(dataflow_state_id, new_state)

    async def insert(self, doc: dict[str, Any]) -> str:
        """Speichert ein vollständiges State-Dokument (setzt ggf. dataflow_state aus nodes/edges)."""
        enrich_document_timestamps(doc)
        if "dataflow_state" not in doc and ("nodes" in doc or "edges" in doc):
            doc["dataflow_state"] = {
                "nodes": doc.get("nodes", []),
                "edges": doc.get("edges", []),
            }
        if "dataflow_state" in doc and isinstance(doc["dataflow_state"], dict):
            doc.setdefault("nodes", doc["dataflow_state"].get("nodes", []))
            doc.setdefault("edges", doc["dataflow_state"].get("edges", []))
        result = await self._collection.insert_one(doc)
        return str(result.inserted_id)

    async def list_dataflow_states(
        self,
        *,
        page: int,
        page_size: int,
        pipeline_id: Optional[str] = None,
        dataflow_id: Optional[str] = None,
    ) -> dict[str, Any]:
        q: dict[str, Any] = {}
        if pipeline_id:
            q["pipeline_id"] = pipeline_id
        if dataflow_id:
            q["dataflow_id"] = dataflow_id
        total_items = await self._collection.count_documents(q)
        skip = (page - 1) * page_size
        cursor = self._collection.find(q).sort([("dataflow_state_id", 1)]).skip(skip).limit(page_size)
        docs = await cursor.to_list(length=page_size)
        items = [self._string_id(d) for d in docs]
        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total_items": total_items,
            "total_pages": ceil(total_items / page_size) if total_items else 0,
        }

    async def delete_by_id(self, dataflow_state_id: str) -> bool:
        result = await self._collection.delete_one({"dataflow_state_id": dataflow_state_id})
        return result.deleted_count > 0
