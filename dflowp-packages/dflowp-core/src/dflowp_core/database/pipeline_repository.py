"""Repository für Pipelines (ersetzt Prozesse mit Referenzen auf Dataflow, Config, State)."""

import copy
import json
import uuid
from math import ceil
from typing import Any, Optional

from pymongo import ReturnDocument

from dflowp_core.database.dataflow_repository import DataflowRepository
from dflowp_core.database.dataflow_state_repository import DataflowStateRepository, _node_id_key
from dflowp_core.database.mongo import get_database
from dflowp_core.database.plugin_configuration_repository import PluginConfigurationRepository
from dflowp_core.eventinterfaces.event_types import EVENT_FAILED
from dflowp_core.utils.logger import get_logger
from dflowp_core.utils.timestamps import enrich_document_timestamps

logger = get_logger(__name__)


def _canon_dataflow_id_from_doc(df: dict[str, Any]) -> str:
    """Stabiler Fingerabdruck des Graphen (nodes/edges) für Wiederverwendungsentscheidung."""
    nodes = df.get("nodes") or []
    edges = df.get("edges") or []
    norm_nodes = sorted(
        [
            {
                "plugin_worker_id": n.get("plugin_worker_id") or n.get("subprocess_id"),
                "plugin_type": n.get("plugin_type") or n.get("subprocess_type"),
            }
            for n in nodes
        ],
        key=lambda x: (x["plugin_worker_id"] or "", x["plugin_type"] or ""),
    )
    norm_edges = sorted(
        [{"from": e.get("from"), "to": e.get("to")} for e in edges],
        key=lambda x: (x["from"] or "", x["to"] or ""),
    )
    return json.dumps({"nodes": norm_nodes, "edges": norm_edges}, sort_keys=True)


def _plugin_config_fingerprint(pcfg: dict[str, Any]) -> str:
    by = pcfg.get("by_plugin_worker_id") or pcfg
    if isinstance(by, dict) and "by_plugin_worker_id" not in pcfg:
        m = pcfg
    else:
        m = pcfg.get("by_plugin_worker_id", {})
    return json.dumps(m, sort_keys=True)


class PipelineRepository:
    """Pipelines: Referenzen auf ``dataflow_id``, ``plugin_configuration_id``, ``dataflow_state_id``."""

    COLLECTION_NAME = "pipelines"

    def __init__(self) -> None:
        self._db = get_database()
        self._collection = self._db[self.COLLECTION_NAME]
        self._dataflows = DataflowRepository()
        self._pcfgs = PluginConfigurationRepository()
        self._states = DataflowStateRepository()

    async def create_indexes(self) -> None:
        await self._collection.create_index("pipeline_id", unique=True)
        await self._collection.create_index("status")
        await self._collection.create_index("dataflow_id")
        await self._collection.create_index("dataflow_state_id")
        await self._collection.create_index(
            [("timestamp_ms", -1), ("pipeline_id", 1)]
        )
        await self._dataflows.create_indexes()
        await self._pcfgs.create_indexes()
        await self._states.create_indexes()

    @staticmethod
    def _string_id(doc: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
        if doc and "_id" in doc:
            doc["_id"] = str(doc["_id"])
        return doc

    async def insert(self, pipeline: dict[str, Any]) -> str:
        enrich_document_timestamps(pipeline)
        result = await self._collection.insert_one(pipeline)
        return str(result.inserted_id)

    async def find_by_id(self, pipeline_id: str) -> Optional[dict[str, Any]]:
        doc = await self._collection.find_one({"pipeline_id": pipeline_id})
        return self._string_id(doc)

    async def list_pipelines(
        self,
        *,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        total_items = await self._collection.count_documents({})
        skip = (page - 1) * page_size
        docs = (
            await self._collection.find({})
            .sort([("timestamp_ms", -1), ("pipeline_id", 1)])
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

    async def list_plugin_workers(
        self,
        *,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        """Einträge aus entbundelten DataflowState-Knoten (Metadaten pro Plugin-Worker)."""
        pipeline: list[dict[str, Any]] = [
            {"$match": {"nodes": {"$exists": True, "$ne": []}}},
            {"$unwind": "$nodes"},
            {
                "$project": {
                    "_id": 0,
                    "producer_pipeline_id": "$pipeline_id",
                    "plugin_worker_id": {
                        "$ifNull": ["$nodes.plugin_worker_id", "$nodes.subprocess_id"],
                    },
                    "plugin_type": {
                        "$ifNull": ["$nodes.plugin_type", "$nodes.subprocess_type"],
                    },
                    "event_status": "$nodes.event_status",
                    "io_transformation_states": "$nodes.io_transformation_states",
                }
            },
            {"$sort": {"producer_pipeline_id": 1, "plugin_worker_id": 1}},
        ]
        col = self._db[DataflowStateRepository.COLLECTION_NAME]
        count_pipeline = pipeline + [{"$count": "count"}]
        count_result = await col.aggregate(count_pipeline).to_list(length=1)
        total_items = count_result[0]["count"] if count_result else 0
        skip = (page - 1) * page_size
        items = await col.aggregate(pipeline + [{"$skip": skip}, {"$limit": page_size}]).to_list(
            length=page_size
        )
        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total_items": total_items,
            "total_pages": ceil(total_items / page_size) if total_items else 0,
        }

    async def find_plugin_worker_by_id(self, plugin_worker_id: str) -> Optional[dict[str, Any]]:
        col = self._db[DataflowStateRepository.COLLECTION_NAME]
        pl = [
            {
                "$match": {
                    "$or": [
                        {"nodes.plugin_worker_id": plugin_worker_id},
                        {"nodes.subprocess_id": plugin_worker_id},
                    ]
                }
            },
            {"$unwind": "$nodes"},
            {
                "$match": {
                    "$or": [
                        {"nodes.plugin_worker_id": plugin_worker_id},
                        {"nodes.subprocess_id": plugin_worker_id},
                    ]
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "producer_pipeline_id": "$pipeline_id",
                    "plugin_worker_id": {
                        "$ifNull": ["$nodes.plugin_worker_id", "$nodes.subprocess_id"],
                    },
                    "plugin_type": {
                        "$ifNull": ["$nodes.plugin_type", "$nodes.subprocess_type"],
                    },
                    "event_status": "$nodes.event_status",
                    "io_transformation_states": "$nodes.io_transformation_states",
                }
            },
            {"$limit": 1},
        ]
        r = await col.aggregate(pl).to_list(length=1)
        return r[0] if r else None

    async def find_plugin_worker(
        self,
        pipeline_id: str,
        plugin_worker_id: str,
    ) -> Optional[dict[str, Any]]:
        p = await self.find_by_id(pipeline_id)
        if not p or not p.get("dataflow_state_id"):
            return None
        inner = await self._states.get_dataflow_state(p["dataflow_state_id"])
        if not inner:
            return None
        for n in inner.get("nodes", []) or []:
            if _node_id_key(n) == plugin_worker_id:
                return {
                    "producer_pipeline_id": pipeline_id,
                    "plugin_worker_id": _node_id_key(n),
                    "plugin_type": n.get("plugin_type") or n.get("subprocess_type"),
                    "event_status": n.get("event_status"),
                    "io_transformation_states": n.get("io_transformation_states", []),
                }
        return None

    async def copy_pipeline_with_reexecution(
        self,
        *,
        source_pipeline_id: str,
        target_pipeline_id: str,
        parent_plugin_worker_ids: Optional[list[str]] = None,
        plugin_config_override: Optional[dict[str, dict[str, Any]]] = None,
        dataflow_id_override: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """
        Klont eine Pipeline. Optional: anderes Dataflow-Definition-Dokument,
        zusammengeführte ``plugin_config`` (neues pcfg-Dokument bei Inhalts-Änderung),
        explizite Plugin-Worker-Seeds oder Auto (fehlgeschlagen → Nachfolger; sonst voll).
        """
        source = await self.find_by_id(source_pipeline_id)
        if not source:
            return None

        s_df_id = source.get("dataflow_id")
        s_pc_id = source.get("plugin_configuration_id")
        s_st_id = source.get("dataflow_state_id")
        if not s_df_id or not s_pc_id or not s_st_id:
            logger.error("Quell-Pipeline unvollständig (Referenzen fehlen).")
            return None

        df_src = await self._dataflows.find_by_id(s_df_id)
        pcfg_src = await self._pcfgs.find_by_id(s_pc_id)
        st_src = await self._states.get_by_id(s_st_id) if s_st_id else None
        if not df_src or not pcfg_src or not st_src:
            return None

        by_src = (pcfg_src.get("by_plugin_worker_id") or {})
        merged_cfg: dict[str, Any] = {**by_src}
        if plugin_config_override:
            for wid, ovr in plugin_config_override.items():
                merged_cfg[wid] = {**(merged_cfg.get(wid) or {}), **ovr}

        new_df_id = dataflow_id_override or s_df_id
        df_effective = await self._dataflows.find_by_id(new_df_id) if new_df_id else None
        if not df_effective:
            return None

        new_pc_id = s_pc_id
        if _plugin_config_fingerprint({"by_plugin_worker_id": merged_cfg}) != _plugin_config_fingerprint(
            pcfg_src
        ):
            new_pc_id = f"pcfg_{uuid.uuid4().hex[:12]}"
            await self._pcfgs.insert(
                {
                    "plugin_configuration_id": new_pc_id,
                    "by_plugin_worker_id": merged_cfg,
                }
            )

        st_inner_0 = st_src.get("dataflow_state") or {
            "nodes": st_src.get("nodes", []),
            "edges": st_src.get("edges", []),
        }
        if new_df_id != s_df_id:
            st_copy = self._state_template_from_dataflow_doc(df_effective)
        else:
            st_copy = copy.deepcopy(
                st_inner_0
                if st_inner_0
                else {"nodes": [], "edges": []}
            )
        nodes = st_copy.get("nodes", []) or []
        edges = st_copy.get("edges", []) or []
        successors: dict[str, list[str]] = {}
        for edge in edges:
            fn = edge.get("from")
            tn = edge.get("to")
            if not fn or not tn:
                continue
            successors.setdefault(str(fn), []).append(str(tn))
        all_wids = {str(w) for w in (_node_id_key(n) for n in nodes) if w}

        to_reset: set[str] = set()
        if parent_plugin_worker_ids is not None and len(parent_plugin_worker_ids) > 0:
            stack = list(parent_plugin_worker_ids)
        elif plugin_config_override and new_df_id == s_df_id:
            stack = list(plugin_config_override.keys())
        else:
            failed: list[str] = []
            for n in st_inner_0.get("nodes", []) or []:
                wid = _node_id_key(n)
                if not wid:
                    continue
                ev = n.get("event_status") or ""
                if ev in (EVENT_FAILED, "EVENT_FAILED", "Failed") or "FAIL" in str(ev).upper():
                    failed.append(wid)
            if failed:
                stack = list(failed)
            else:
                stack = list(all_wids)
        while stack:
            nid = stack.pop()
            if nid in to_reset:
                continue
            to_reset.add(nid)
            stack.extend(successors.get(nid, []))
        for n in nodes:
            wid = _node_id_key(n)
            if wid and wid in to_reset:
                n["io_transformation_states"] = []
                n["event_status"] = "Not Started"

        new_state_id = f"dfs_{uuid.uuid4().hex[:12]}"
        st_payload = {
            "dataflow_state_id": new_state_id,
            "pipeline_id": target_pipeline_id,
            "dataflow_id": new_df_id,
            "nodes": st_copy.get("nodes", []),
            "edges": st_copy.get("edges", []),
            "dataflow_state": st_copy,
        }
        await self._states.insert(st_payload)

        new_pl = {
            "pipeline_id": target_pipeline_id,
            "software_version": source.get("software_version", "0.1.0"),
            "input_dataset_id": source.get("input_dataset_id"),
            "dataflow_id": new_df_id,
            "plugin_configuration_id": new_pc_id,
            "dataflow_state_id": new_state_id,
            "status": "pending",
        }
        enrich_document_timestamps(new_pl)
        await self.insert(new_pl)
        return await self.find_by_id(target_pipeline_id)

    @staticmethod
    def _state_template_from_dataflow_doc(df: dict[str, Any]) -> dict[str, Any]:
        """Neuer Lauf-Graph (leere IO-States) aus Dataflow-Definition-Dokument."""
        out_nodes: list[dict[str, Any]] = []
        for n in df.get("nodes", []) or []:
            wid = n.get("plugin_worker_id") or n.get("subprocess_id")
            ptype = n.get("plugin_type") or n.get("subprocess_type")
            if not wid:
                continue
            out_nodes.append(
                {
                    "plugin_worker_id": wid,
                    "plugin_type": ptype,
                    "event_status": "Not Started",
                    "io_transformation_states": [],
                }
            )
        return {"nodes": out_nodes, "edges": list(df.get("edges") or [])}

    async def update(
        self,
        pipeline_id: str,
        update: dict[str, Any],
    ) -> bool:
        result = await self._collection.update_one(
            {"pipeline_id": pipeline_id},
            {"$set": update},
        )
        return result.matched_count > 0

    async def delete_by_id(self, pipeline_id: str) -> bool:
        p = await self.find_by_id(pipeline_id)
        if not p:
            return False
        st_id = p.get("dataflow_state_id")
        result = await self._collection.delete_one({"pipeline_id": pipeline_id})
        if st_id:
            await self._states.delete_by_id(st_id)
        return result.deleted_count > 0

    async def insert_from_configuration(
        self,
        configuration: Any,
        *,
        status: str = "running",
    ) -> dict[str, Any]:
        """
        Legt dataflow, plugin_configuration, dataflow_state und pipeline-Referenzen an
        (``configuration``: Objekt mit ``pipeline_id``, ``dataflow``, ``plugin_config`` …).
        """
        dataflow_id = f"df_{uuid.uuid4().hex[:12]}"
        pcfg_id = f"pcfg_{uuid.uuid4().hex[:12]}"
        dfs_id = f"dfs_{uuid.uuid4().hex[:12]}"
        cfg = configuration
        dfd: dict[str, Any] = {
            "dataflow_id": dataflow_id,
            "nodes": [
                {"plugin_worker_id": n.plugin_worker_id, "plugin_type": n.plugin_type}
                for n in cfg.dataflow.nodes
            ],
            "edges": [{"from": e.from_node, "to": e.to_node} for e in cfg.dataflow.edges],
        }
        await self._dataflows.insert(dfd)
        await self._pcfgs.insert(
            {
                "plugin_configuration_id": pcfg_id,
                "by_plugin_worker_id": dict(cfg.plugin_config),
            }
        )
        st_d = {
            "nodes": [
                {
                    "plugin_worker_id": n.plugin_worker_id,
                    "plugin_type": n.plugin_type,
                    "event_status": "Not Started",
                    "io_transformation_states": [],
                }
                for n in cfg.dataflow.nodes
            ],
            "edges": [{"from": e.from_node, "to": e.to_node} for e in cfg.dataflow.edges],
        }
        await self._states.insert(
            {
                "dataflow_state_id": dfs_id,
                "pipeline_id": cfg.pipeline_id,
                "dataflow_id": dataflow_id,
                "nodes": st_d.get("nodes", []),
                "edges": st_d.get("edges", []),
                "dataflow_state": st_d,
            }
        )
        pl_doc: dict[str, Any] = {
            "pipeline_id": cfg.pipeline_id,
            "software_version": cfg.software_version,
            "input_dataset_id": cfg.input_dataset_id,
            "dataflow_id": dataflow_id,
            "plugin_configuration_id": pcfg_id,
            "dataflow_state_id": dfs_id,
            "status": status,
        }
        await self.insert(pl_doc)
        out = await self.find_by_id(cfg.pipeline_id)
        if not out:
            raise RuntimeError("Pipeline nach insert_from_configuration nicht lesbar")
        return out

    async def claim_next_pending(self) -> Optional[dict[str, Any]]:
        doc = await self._collection.find_one_and_update(
            {"status": "pending"},
            {"$set": {"status": "running"}},
            sort=[("_id", 1)],
            return_document=ReturnDocument.AFTER,
        )
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc

    # --- API-/Legacy-Aliase (Prozess/Subprozess-Benennung) ---
    async def list_processes(
        self,
        *,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        return await self.list_pipelines(page=page, page_size=page_size)

    async def list_subprocesses(
        self,
        *,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        return await self.list_plugin_workers(page=page, page_size=page_size)

    async def find_subprocess_by_id(self, subprocess_id: str) -> Optional[dict[str, Any]]:
        return await self.find_plugin_worker_by_id(subprocess_id)

    async def copy_process_with_reexecution(
        self,
        *,
        source_process_id: str,
        target_process_id: str,
        parent_subprocess_ids: list[str],
        subprocess_config_override: Optional[dict[str, dict[str, Any]]] = None,
    ) -> Optional[dict[str, Any]]:
        return await self.copy_pipeline_with_reexecution(
            source_pipeline_id=source_process_id,
            target_pipeline_id=target_process_id,
            parent_plugin_worker_ids=parent_subprocess_ids,
            plugin_config_override=subprocess_config_override,
        )


# Rückwärtskompatibler Name für bestehende Importe während der Migration
ProcessRepository = PipelineRepository
