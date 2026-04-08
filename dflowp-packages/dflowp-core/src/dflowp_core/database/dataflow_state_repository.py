"""Repository für DataflowState - Aktualisierung des Prozess-State."""

from typing import Any, Optional

from dflowp_core.database.mongo import get_database


class DataflowStateRepository:
    """Repository für DataflowState (Teil des Process-Dokuments)."""

    COLLECTION_NAME = "processes"

    def __init__(self) -> None:
        self._db = get_database()
        self._collection = self._db[self.COLLECTION_NAME]

    async def get_dataflow_state(
        self, process_id: str
    ) -> Optional[dict[str, Any]]:
        """Liest den Dataflow-State eines Prozesses."""
        doc = await self._collection.find_one(
            {"process_id": process_id},
            {"dataflow_state": 1},
        )
        return doc.get("dataflow_state") if doc else None

    async def update_dataflow_state(
        self, process_id: str, dataflow_state: dict[str, Any]
    ) -> bool:
        """Aktualisiert den Dataflow-State."""
        result = await self._collection.update_one(
            {"process_id": process_id},
            {"$set": {"dataflow_state": dataflow_state}},
        )
        return result.matched_count > 0

    async def update_node_state(
        self,
        process_id: str,
        subprocess_id: str,
        event_status: Optional[str] = None,
        io_transformation_states: Optional[list[dict]] = None,
    ) -> bool:
        """Aktualisiert den State eines einzelnen Dataflow-Knotens."""
        doc = await self._collection.find_one({"process_id": process_id})
        if not doc or "dataflow_state" not in doc:
            return False

        nodes = doc["dataflow_state"].get("nodes", [])
        for i, n in enumerate(nodes):
            if n.get("subprocess_id") == subprocess_id:
                if event_status is not None:
                    nodes[i]["event_status"] = event_status
                if io_transformation_states is not None:
                    nodes[i]["io_transformation_states"] = io_transformation_states
                break
        else:
            return False

        return await self.update_dataflow_state(
            process_id, {**doc["dataflow_state"], "nodes": nodes}
        )
