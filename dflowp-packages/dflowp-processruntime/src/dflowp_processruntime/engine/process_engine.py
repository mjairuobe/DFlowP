"""Prozessengine – Ausführung von Pipelines (Plugin-Workern) mit entkoppeltem DataflowState."""

import asyncio
from typing import Any, Callable, Optional

from dflowp_processruntime.datastructures.data import Data
from dflowp_processruntime.dataflow.dataflow_state import DataflowState
from dflowp_core.eventinterfaces.event_types import EVENT_COMPLETED, EVENT_FAILED, EVENT_STARTED
from dflowp_processruntime.engine.pipeline_config_loader import load_pipeline_configuration
from dflowp_processruntime.processes.process_configuration import (
    PipelineConfiguration,
    ProcessConfiguration,
)
from dflowp_processruntime.subprocesses.subprocess_context import SubprocessContext
from dflowp_core.utils.logger import get_logger

logger = get_logger(__name__)


def _ev_pipeline_id(event: dict[str, Any]) -> Optional[str]:
    return event.get("pipeline_id") or event.get("process_id")


def _ev_plugin_worker_id(event: dict[str, Any]) -> Optional[str]:
    return event.get("plugin_worker_id") or event.get("subprocess_id")


def _node_id(n: dict[str, Any]) -> Optional[str]:
    return n.get("plugin_worker_id") or n.get("subprocess_id")


class ProcessEngine:
    """
    Führt Pipelines aus, aktualisiert DataflowState in der Collection ``dataflow_states``,
    emittiert Events (pipeline_id / plugin_worker_id).
    """

    def __init__(
        self,
        event_service: Any,
        process_repository: Any,
        dataflow_state_repository: Any,
        data_repository: Any,
        dataset_repository: Any,
        get_subprocess: Callable[[str], Any],
        enable_local_event_subscriptions: bool = True,
    ) -> None:
        self._event_service = event_service
        self._process_repo = process_repository
        self._dataflow_state_repo = dataflow_state_repository
        self._data_repo = data_repository
        self._dataset_repo = dataset_repository
        self._get_subprocess = get_subprocess
        self._active_subprocess_count: int = 0
        self._enable_local_event_subscriptions = enable_local_event_subscriptions

    @staticmethod
    def _source(pipeline_id: str, plugin_worker_id: str) -> str:
        return f"[{pipeline_id}][{plugin_worker_id}]"

    def start(self) -> None:
        if self._enable_local_event_subscriptions:
            self._event_service.subscribe(EVENT_COMPLETED, self._on_subprocess_completed)
            self._event_service.subscribe(EVENT_FAILED, self._on_subprocess_failed)
            logger.info("[ProcessEngine] gestartet, lokale Events subscribed")
            return
        logger.info("[ProcessEngine] gestartet, erwartet externe Event-Notifications")

    async def handle_event_notification(self, event: dict[str, Any]) -> None:
        event_type = event.get("event_type")
        if event_type == EVENT_COMPLETED:
            await self._on_subprocess_completed(event)
        elif event_type == EVENT_FAILED:
            await self._on_subprocess_failed(event)

    async def wait_until_idle(
        self,
        *,
        shutdown: Optional[asyncio.Event] = None,
        poll_seconds: float = 0.5,
    ) -> None:
        while self._active_subprocess_count > 0:
            if shutdown is not None and shutdown.is_set():
                return
            await asyncio.sleep(poll_seconds)

    async def _load_configuration(
        self, doc: dict[str, Any]
    ) -> Optional[PipelineConfiguration]:
        pdoc = dict(doc)
        if not pdoc.get("pipeline_id") and pdoc.get("process_id"):
            pdoc["pipeline_id"] = pdoc["process_id"]
        try:
            if pdoc.get("dataflow_id") and pdoc.get("plugin_configuration_id"):
                return await load_pipeline_configuration(pdoc)
            if pdoc.get("configuration"):
                return ProcessConfiguration.from_dict(pdoc["configuration"])
        except Exception as exc:  # noqa: BLE001
            logger.error("Pipeline-Konfiguration konnte nicht geladen werden: %s", exc)
        return None

    async def activate_pending_process(self, pipeline_id: str) -> bool:
        """Aktiviert startbereite Root-Plugin-Worker (nach claim, status=running)."""
        doc = await self._process_repo.find_by_id(pipeline_id)
        if not doc:
            logger.error(
                "[ProcessEngine] Pipeline %s nicht in der Datenbank", pipeline_id
            )
            return False

        configuration = await self._load_configuration(doc)
        if not configuration:
            logger.error(
                "[ProcessEngine] Pipeline %s: keine auflösbare Konfiguration (Referenzen oder `configuration`)",
                pipeline_id,
            )
            await self._process_repo.update(pipeline_id, {"status": "failed"})
            return False

        configuration.apply_default_openai_key_from_env()
        configuration.apply_software_version_from_env()

        pid = configuration.pipeline_id
        dfs_id = doc.get("dataflow_state_id")
        if not dfs_id:
            msg = (
                "eingebetteter dataflow_state – bitte Migration ausführen"
                if doc.get("dataflow_state")
                else "kein dataflow_state_id"
            )
            logger.error("[ProcessEngine] Pipeline %s: %s", pipeline_id, msg)
            await self._process_repo.update(pid, {"status": "failed"})
            return False

        if not await self._dataflow_state_repo.get_dataflow_state(dfs_id):
            dataflow_state = DataflowState.from_dataflow(configuration.dataflow)
            await self._dataflow_state_repo.update_dataflow_state(
                dfs_id, dataflow_state.to_dict()
            )
            await self._process_repo.update(
                pid,
                {
                    "software_version": configuration.software_version,
                    "input_dataset_id": configuration.input_dataset_id,
                },
            )
        dataflow_doc = await self._dataflow_state_repo.get_dataflow_state(dfs_id)
        if not dataflow_doc:
            logger.error("[ProcessEngine] DataflowState %s fehlt in der DB", dfs_id)
            await self._process_repo.update(pid, {"status": "failed"})
            return False

        nodes = dataflow_doc.get("nodes", []) or []
        status_by_id: dict[str, Any] = {
            str(_node_id(node)): node.get("event_status")
            for node in nodes
            if _node_id(node)
        }

        def is_ready_to_start(wid: str) -> bool:
            status = status_by_id.get(wid)
            if status not in (None, "Not Started"):
                return False
            predecessors = configuration.dataflow.get_predecessors(wid)
            return all(status_by_id.get(str(pred)) == EVENT_COMPLETED for pred in predecessors)

        runnable = [
            n.plugin_worker_id
            for n in configuration.dataflow.nodes
            if is_ready_to_start(n.plugin_worker_id)
        ]

        for wid in runnable:
            logger.progress(
                "%s Ready-Plugin-Worker wird gestartet", self._source(pid, wid)
            )
            await self._start_subprocess(pid, wid, configuration, dfs_id)

        if not runnable:
            logger.info(
                "[ProcessEngine] Keine startbaren Plugin-Worker für Pipeline %s", pid
            )
        return True

    async def start_process(self, configuration: ProcessConfiguration) -> bool:
        """Legt vollständige Pipeline in Mongo an und startet Root-Plugin-Worker."""
        configuration.apply_default_openai_key_from_env()
        configuration.apply_software_version_from_env()
        pipeline_id = configuration.pipeline_id
        logger.info("[ProcessEngine] Starte Pipeline %s", pipeline_id)

        doc = await self._process_repo.insert_from_configuration(
            configuration, status="running"
        )
        dfs_id = doc["dataflow_state_id"]
        for wid in configuration.dataflow.get_root_nodes():
            logger.progress(
                "%s Root-Plugin-Worker wird gestartet", self._source(pipeline_id, wid)
            )
            await self._start_subprocess(pipeline_id, wid, configuration, dfs_id)
        return True

    async def _start_subprocess(
        self,
        pipeline_id: str,
        plugin_worker_id: str,
        configuration: PipelineConfiguration,
        dataflow_state_id: str,
    ) -> None:
        node_def = configuration.dataflow.get_node(plugin_worker_id)
        if not node_def:
            logger.error(
                "%s nicht in Dataflow gefunden", self._source(pipeline_id, plugin_worker_id)
            )
            return

        logger.info(
            "%s Starte Plugin-Typ %s",
            self._source(pipeline_id, plugin_worker_id),
            node_def.plugin_type,
        )

        await self._dataflow_state_repo.update_node_state(
            dataflow_state_id, plugin_worker_id, event_status=EVENT_STARTED
        )
        await self._event_service.emit_started(
            pipeline_id=pipeline_id, plugin_worker_id=plugin_worker_id
        )

        context = await self._build_context(
            pipeline_id,
            plugin_worker_id,
            node_def.plugin_type,
            configuration,
            dataflow_state_id,
        )
        if not context:
            await self._dataflow_state_repo.update_node_state(
                dataflow_state_id, plugin_worker_id, event_status=EVENT_FAILED
            )
            await self._event_service.emit_failed(
                pipeline_id=pipeline_id,
                plugin_worker_id=plugin_worker_id,
                error="Kontext konnte nicht erstellt werden",
            )
            return

        sp = self._get_subprocess(node_def.plugin_type)
        if not sp:
            await self._dataflow_state_repo.update_node_state(
                dataflow_state_id, plugin_worker_id, event_status=EVENT_FAILED
            )
            await self._event_service.emit_failed(
                pipeline_id=pipeline_id,
                plugin_worker_id=plugin_worker_id,
                error=f"Plugin-Typ {node_def.plugin_type} nicht gefunden",
            )
            return

        self._active_subprocess_count += 1

        async def run_wrapper() -> None:
            try:
                io_states = await sp.run(
                    context=context,
                    event_emitter=self._event_service,
                    data_repository=self._data_repo,
                    dataset_repository=self._dataset_repo,
                )
                await self._dataflow_state_repo.update_node_state(
                    dataflow_state_id,
                    plugin_worker_id,
                    event_status=EVENT_COMPLETED,
                    io_transformation_states=[s.to_dict() for s in io_states],
                )
                await self._event_service.emit_completed(
                    pipeline_id=pipeline_id, plugin_worker_id=plugin_worker_id
                )
            except Exception as e:
                logger.exception(
                    "%s fehlgeschlagen: %s", self._source(pipeline_id, plugin_worker_id), e
                )
                await self._dataflow_state_repo.update_node_state(
                    dataflow_state_id, plugin_worker_id, event_status=EVENT_FAILED
                )
                await self._event_service.emit_failed(
                    pipeline_id=pipeline_id,
                    plugin_worker_id=plugin_worker_id,
                    error=str(e),
                )
            finally:
                self._active_subprocess_count -= 1
                logger.debug(
                    "%s beendet, aktive Plugin-Worker=%d",
                    self._source(pipeline_id, plugin_worker_id),
                    self._active_subprocess_count,
                )

        asyncio.create_task(run_wrapper())

    async def _build_context(
        self,
        pipeline_id: str,
        plugin_worker_id: str,
        plugin_type: str,
        configuration: PipelineConfiguration,
        dataflow_state_id: str,
    ) -> Optional[SubprocessContext]:
        config = configuration.plugin_config.get(plugin_worker_id, {})
        root_ids = configuration.dataflow.get_root_nodes()

        if plugin_worker_id in root_ids:
            dataset_doc = await self._dataset_repo.find_by_id(
                configuration.input_dataset_id
            )
            if not dataset_doc:
                logger.error(
                    "%s Input-Dataset %s nicht gefunden",
                    self._source(pipeline_id, plugin_worker_id),
                    configuration.input_dataset_id,
                )
                return None
            data_ids = dataset_doc.get("data_ids", [])
            input_data = []
            for did in data_ids:
                d = await self._data_repo.find_by_id(did)
                if d:
                    input_data.append(
                        Data(
                            data_id=d.get("data_id") or d.get("id", did),
                            content=d.get("content", {}),
                            type=d.get("type", "input"),
                        )
                    )
            return SubprocessContext(
                pipeline_id=pipeline_id,
                plugin_worker_id=plugin_worker_id,
                plugin_type=plugin_type,
                config=config,
                input_data=input_data,
            )

        predecessors = configuration.dataflow.get_predecessors(plugin_worker_id)
        dataflow_doc = await self._dataflow_state_repo.get_dataflow_state(
            dataflow_state_id
        )
        if not dataflow_doc:
            return None

        all_output_ids: list[str] = []
        for pred in predecessors:
            for n in dataflow_doc.get("nodes", []):
                if str(_node_id(n)) == str(pred):
                    for s in n.get("io_transformation_states", []):
                        all_output_ids.extend(s.get("output_data_ids", []))
                    break

        input_data = await self._resolve_predecessor_outputs_to_data(all_output_ids)
        return SubprocessContext(
            pipeline_id=pipeline_id,
            plugin_worker_id=plugin_worker_id,
            plugin_type=plugin_type,
            config=config,
            input_data=input_data,
        )

    async def _resolve_predecessor_outputs_to_data(
        self, output_ids: list[str]
    ) -> list[Data]:
        input_data: list[Data] = []
        for oid in output_ids:
            d = await self._data_repo.find_by_id(oid)
            if not d:
                continue
            if d.get("doc_type") == "dataset":
                for cid in d.get("data_ids", []):
                    child = await self._data_repo.find_by_id(cid)
                    if child and child.get("content") is not None:
                        data_id = child.get("data_id") or child.get("id", cid)
                        input_data.append(
                            Data(
                                data_id=data_id,
                                content=child.get("content", {}),
                                type=child.get("type", "output"),
                            )
                        )
                continue
            if d.get("content") is not None:
                data_id = d.get("data_id") or d.get("id", oid)
                input_data.append(
                    Data(
                        data_id=data_id,
                        content=d.get("content", {}),
                        type=d.get("type", "output"),
                    )
                )
        return input_data

    async def _on_subprocess_completed(self, event: dict) -> None:
        pipeline_id = _ev_pipeline_id(event)
        plugin_worker_id = _ev_plugin_worker_id(event)
        if not pipeline_id or not plugin_worker_id:
            return

        logger.success(
            "%s EVENT_COMPLETED empfangen", self._source(pipeline_id, plugin_worker_id)
        )
        if plugin_worker_id == "0":
            return

        pl_doc = await self._process_repo.find_by_id(pipeline_id)
        if not pl_doc:
            return

        configuration = await self._load_configuration(pl_doc)
        if not configuration:
            return

        dfs_id = pl_doc.get("dataflow_state_id")
        if not dfs_id:
            return

        for succ in configuration.dataflow.get_successors(plugin_worker_id):
            logger.progress(
                "%s Trigger Nachfolger %s",
                self._source(pipeline_id, plugin_worker_id),
                succ,
            )
            await self._start_subprocess(
                pipeline_id, succ, configuration, dfs_id
            )

        if not configuration.dataflow.get_successors(plugin_worker_id):
            all_ok = await self._check_all_completed(dfs_id)
            if all_ok:
                await self._process_repo.update(pipeline_id, {"status": "completed"})
                logger.success(
                    "[ProcessEngine] Pipeline %s vollständig abgeschlossen", pipeline_id
                )
                await self._event_service.emit_completed(
                    pipeline_id=pipeline_id, plugin_worker_id="0"
                )

    async def _on_subprocess_failed(self, event: dict) -> None:
        pipeline_id = _ev_pipeline_id(event)
        if pipeline_id:
            logger.error(
                "%s EVENT_FAILED empfangen",
                self._source(pipeline_id, str(_ev_plugin_worker_id(event) or "?")),
            )
            await self._process_repo.update(pipeline_id, {"status": "failed"})

    async def _check_all_completed(self, dataflow_state_id: str) -> bool:
        doc = await self._dataflow_state_repo.get_dataflow_state(dataflow_state_id)
        if not doc:
            return False
        for n in doc.get("nodes", []):
            if n.get("event_status") != EVENT_COMPLETED:
                return False
        return True
