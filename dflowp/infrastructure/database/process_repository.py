"""Repository für Prozesse - Speicherung von Prozess-Konfigurationen und -Status."""

from math import ceil
from typing import Any, Optional

from pymongo import ReturnDocument

from dflowp.infrastructure.database.mongo import get_database
from dflowp.utils.timestamps import enrich_document_timestamps
from dflowp.utils.logger import get_logger

logger = get_logger(__name__)


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
        await self._collection.create_index([("timestamp_ms", -1), ("process_id", 1)])
        await self._collection.create_index([("timestamp_ms", -1), ("dataflow_state.nodes.subprocess_id", 1)])

    @staticmethod
    def _with_string_id(doc: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
        if doc and "_id" in doc:
            doc["_id"] = str(doc["_id"])
        return doc

    async def insert(self, process: dict[str, Any]) -> str:
        """Speichert einen Prozess. Gibt die _id zurück."""
        enrich_document_timestamps(process)
        result = await self._collection.insert_one(process)
        return str(result.inserted_id)

    async def find_by_id(self, process_id: str) -> Optional[dict[str, Any]]:
        """Findet einen Prozess anhand der process_id."""
        doc = await self._collection.find_one({"process_id": process_id})
        return self._with_string_id(doc)

    async def list_processes(
        self,
        *,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        """Liefert paginierte Prozesse."""
        total_items = await self._collection.count_documents({})
        skip = (page - 1) * page_size
        docs = (
            await self._collection.find({})
            .sort([("timestamp_ms", -1), ("process_id", 1)])
            .skip(skip)
            .limit(page_size)
            .to_list(length=page_size)
        )
        items = [self._with_string_id(doc) for doc in docs]
        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total_items": total_items,
            "total_pages": ceil(total_items / page_size) if total_items else 0,
        }

    async def list_subprocesses(
        self,
        *,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        """Liefert alle Subprozesse aus dataflow_state aller Prozesse, paginiert."""
        pipeline = [
            {"$match": {"dataflow_state.nodes": {"$exists": True, "$ne": []}}},
            {"$unwind": "$dataflow_state.nodes"},
            {
                "$project": {
                    "_id": 0,
                    "process_id": 1,
                    "subprocess_id": "$dataflow_state.nodes.subprocess_id",
                    "subprocess_type": "$dataflow_state.nodes.subprocess_type",
                    "event_status": "$dataflow_state.nodes.event_status",
                    "io_transformation_states": "$dataflow_state.nodes.io_transformation_states",
                }
            },
            {"$sort": {"timestamp_ms": -1, "process_id": 1, "subprocess_id": 1}},
        ]

        count_pipeline = pipeline + [{"$count": "count"}]
        count_result = await self._collection.aggregate(count_pipeline).to_list(length=1)
        total_items = count_result[0]["count"] if count_result else 0

        skip = (page - 1) * page_size
        paginated_pipeline = pipeline + [{"$skip": skip}, {"$limit": page_size}]
        items = await self._collection.aggregate(paginated_pipeline).to_list(length=page_size)

        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total_items": total_items,
            "total_pages": ceil(total_items / page_size) if total_items else 0,
        }

    async def find_subprocess_by_id(self, subprocess_id: str) -> Optional[dict[str, Any]]:
        """Findet den ersten Subprozess mit gegebener subprocess_id über alle Prozesse."""
        pipeline = [
            {"$match": {"dataflow_state.nodes.subprocess_id": subprocess_id}},
            {"$unwind": "$dataflow_state.nodes"},
            {"$match": {"dataflow_state.nodes.subprocess_id": subprocess_id}},
            {
                "$project": {
                    "_id": 0,
                    "process_id": 1,
                    "subprocess_id": "$dataflow_state.nodes.subprocess_id",
                    "subprocess_type": "$dataflow_state.nodes.subprocess_type",
                    "event_status": "$dataflow_state.nodes.event_status",
                    "io_transformation_states": "$dataflow_state.nodes.io_transformation_states",
                }
            },
            {"$sort": {"process_id": 1}},
            {"$limit": 1},
        ]
        result = await self._collection.aggregate(pipeline).to_list(length=1)
        return result[0] if result else None

    async def find_subprocess(
        self,
        process_id: str,
        subprocess_id: str,
    ) -> Optional[dict[str, Any]]:
        """Findet einen Subprozess für eine spezifische Prozess-ID."""
        pipeline = [
            {"$match": {"process_id": process_id, "dataflow_state.nodes.subprocess_id": subprocess_id}},
            {"$unwind": "$dataflow_state.nodes"},
            {"$match": {"dataflow_state.nodes.subprocess_id": subprocess_id}},
            {
                "$project": {
                    "_id": 0,
                    "process_id": 1,
                    "subprocess_id": "$dataflow_state.nodes.subprocess_id",
                    "subprocess_type": "$dataflow_state.nodes.subprocess_type",
                    "event_status": "$dataflow_state.nodes.event_status",
                    "io_transformation_states": "$dataflow_state.nodes.io_transformation_states",
                }
            },
            {"$limit": 1},
        ]
        result = await self._collection.aggregate(pipeline).to_list(length=1)
        return result[0] if result else None

    async def copy_process_with_reexecution(
        self,
        *,
        source_process_id: str,
        target_process_id: str,
        parent_subprocess_ids: list[str],
    ) -> Optional[dict[str, Any]]:
        """
        Kopiert einen Prozess und entfernt IO-States für Re-Execution-Teilgraphen.

        - Alle unveränderten Knoten behalten ihre IO-Transformation-States.
        - Für alle angegebenen Parent-Knoten und deren Nachfolger werden
          io_transformation_states geleert und event_status auf "Not Started" gesetzt.
        """
        source = await self.find_by_id(source_process_id)
        if not source:
            return None

        copied = dict(source)
        copied.pop("_id", None)
        copied["process_id"] = target_process_id
        copied["status"] = "pending"

        cfg = copied.get("configuration", {})
        if isinstance(cfg, dict):
            cfg["process_id"] = target_process_id
            copied["configuration"] = cfg

        nodes = copied.get("dataflow_state", {}).get("nodes", []) or []
        edges = copied.get("dataflow_state", {}).get("edges", []) or []
        successors: dict[str, list[str]] = {}
        for edge in edges:
            from_node = edge.get("from")
            to_node = edge.get("to")
            if not from_node or not to_node:
                continue
            successors.setdefault(from_node, []).append(to_node)

        to_reset: set[str] = set()
        stack = list(parent_subprocess_ids)
        while stack:
            node_id = stack.pop()
            if node_id in to_reset:
                continue
            to_reset.add(node_id)
            stack.extend(successors.get(node_id, []))

        for node in nodes:
            node_id = node.get("subprocess_id")
            if node_id in to_reset:
                node["io_transformation_states"] = []
                node["event_status"] = "Not Started"

        enrich_document_timestamps(copied)
        result = await self._collection.insert_one(copied)
        copied["_id"] = str(result.inserted_id)
        logger.info("[ProcessRepository] Geklonter Prozess gespeichert: %s", copied)
        return copied

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
