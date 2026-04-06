"""Prozessengine - Ausführung, Verwaltung und Überwachung aller Prozesse."""

import asyncio
from typing import Any, Callable, Optional

from dflowp.core.dataflow.dataflow_state import DataflowState
from dflowp.core.events.event_types import EVENT_COMPLETED, EVENT_FAILED, EVENT_STARTED
from dflowp.core.processes.process_configuration import ProcessConfiguration
from dflowp.core.subprocesses.subprocess_context import SubprocessContext
from dflowp.utils.logger import get_logger

logger = get_logger(__name__)


class ProcessEngine:
    """
    Prozessengine zur Ausführung, Verwaltung und Überwachung aller Prozesse.
    - Subscribt Events beim EventService
    - Erstellt Kontext für Subprozesse
    - Startet Subprozesse und aktualisiert DataflowState
    - Nutzt Repositories (kein direkter DB-Zugriff)
    """

    def __init__(
        self,
        event_service: Any,
        process_repository: Any,
        dataflow_state_repository: Any,
        data_repository: Any,
        dataset_repository: Any,
        get_subprocess: Callable[[str], Any],
    ) -> None:
        self._event_service = event_service
        self._process_repo = process_repository
        self._dataflow_state_repo = dataflow_state_repository
        self._data_repo = data_repository
        self._dataset_repo = dataset_repository
        self._get_subprocess = get_subprocess
        self._running: dict[str, asyncio.Task] = {}
        self._active_subprocess_count: int = 0

    def start(self) -> None:
        """Registriert Event-Handler."""
        self._event_service.subscribe(EVENT_COMPLETED, self._on_subprocess_completed)
        self._event_service.subscribe(EVENT_FAILED, self._on_subprocess_failed)
        logger.info("ProcessEngine gestartet, Events subscrit")

    async def wait_until_idle(
        self,
        *,
        shutdown: Optional[asyncio.Event] = None,
        poll_seconds: float = 0.5,
    ) -> None:
        """Wartet bis alle Subprozess-Tasks beendet sind (oder shutdown gesetzt)."""
        while self._active_subprocess_count > 0:
            if shutdown is not None and shutdown.is_set():
                return
            await asyncio.sleep(poll_seconds)

    async def activate_pending_process(self, process_id: str) -> bool:
        """
        Startet Root-Subprozesse für ein bereits in der DB übernommenes Dokument
        (status wurde z. B. per claim_next_pending auf 'running' gesetzt).
        """
        doc = await self._process_repo.find_by_id(process_id)
        if not doc:
            logger.error("Prozess %s nicht in der Datenbank", process_id)
            return False

        cfg_dict = doc.get("configuration")
        if not cfg_dict:
            logger.error("Prozess %s enthält kein Feld 'configuration'", process_id)
            await self._process_repo.update(process_id, {"status": "failed"})
            return False

        configuration = ProcessConfiguration.from_dict(cfg_dict)
        configuration.apply_default_openai_key_from_env()
        configuration.apply_software_version_from_env()

        if not doc.get("dataflow_state"):
            dataflow_state = DataflowState.from_dataflow(configuration.dataflow)
            await self._process_repo.update(
                process_id,
                {
                    "dataflow_state": dataflow_state.to_dict(),
                    "software_version": configuration.software_version,
                    "input_dataset_id": configuration.input_dataset_id,
                },
            )

        root_ids = configuration.dataflow.get_root_nodes()
        for subprocess_id in root_ids:
            await self._start_subprocess(process_id, subprocess_id, configuration)
        return True

    async def start_process(
        self, configuration: ProcessConfiguration
    ) -> bool:
        """
        Startet einen Prozess mit der gegebenen Konfiguration.
        Erstellt Process-Dokument, DataflowState und startet Root-Subprozesse.
        """
        configuration.apply_default_openai_key_from_env()
        configuration.apply_software_version_from_env()
        process_id = configuration.process_id

        # Process und initialen DataflowState speichern
        dataflow_state = DataflowState.from_dataflow(configuration.dataflow)
        process_doc = {
            "process_id": process_id,
            "software_version": configuration.software_version,
            "input_dataset_id": configuration.input_dataset_id,
            "configuration": configuration.to_dict(),
            "dataflow_state": dataflow_state.to_dict(),
            "status": "running",
        }
        await self._process_repo.insert(process_doc)

        # Root-Nodes starten
        root_ids = configuration.dataflow.get_root_nodes()
        for subprocess_id in root_ids:
            await self._start_subprocess(process_id, subprocess_id, configuration)

        return True

    async def _start_subprocess(
        self,
        process_id: str,
        subprocess_id: str,
        configuration: ProcessConfiguration,
    ) -> None:
        """Startet einen Subprozess."""
        node_def = configuration.dataflow.get_node(subprocess_id)
        if not node_def:
            logger.error("Subprocess %s nicht in DataFlow gefunden", subprocess_id)
            return

        # Event-Status aktualisieren
        await self._dataflow_state_repo.update_node_state(
            process_id, subprocess_id, event_status=EVENT_STARTED
        )

        await self._event_service.emit_started(
            process_id=process_id, subprocess_id=subprocess_id
        )

        context = await self._build_context(
            process_id, subprocess_id, node_def.subprocess_type, configuration
        )
        if not context:
            await self._dataflow_state_repo.update_node_state(
                process_id, subprocess_id, event_status=EVENT_FAILED
            )
            await self._event_service.emit_failed(
                process_id=process_id,
                subprocess_id=subprocess_id,
                error="Kontext konnte nicht erstellt werden",
            )
            return

        subprocess = self._get_subprocess(node_def.subprocess_type)
        if not subprocess:
            await self._dataflow_state_repo.update_node_state(
                process_id, subprocess_id, event_status=EVENT_FAILED
            )
            await self._event_service.emit_failed(
                process_id=process_id,
                subprocess_id=subprocess_id,
                error=f"Subprocess-Typ {node_def.subprocess_type} nicht gefunden",
            )
            return

        self._active_subprocess_count += 1

        async def run_wrapper() -> None:
            try:
                io_states = await subprocess.run(
                    context=context,
                    event_emitter=self._event_service,
                    data_repository=self._data_repo,
                    dataset_repository=self._dataset_repo,
                )
                await self._dataflow_state_repo.update_node_state(
                    process_id,
                    subprocess_id,
                    event_status=EVENT_COMPLETED,
                    io_transformation_states=[s.to_dict() for s in io_states],
                )
                await self._event_service.emit_completed(
                    process_id=process_id, subprocess_id=subprocess_id
                )
            except Exception as e:
                logger.exception("Subprocess %s fehlgeschlagen: %s", subprocess_id, e)
                await self._dataflow_state_repo.update_node_state(
                    process_id, subprocess_id, event_status=EVENT_FAILED
                )
                await self._event_service.emit_failed(
                    process_id=process_id,
                    subprocess_id=subprocess_id,
                    error=str(e),
                )
            finally:
                self._active_subprocess_count -= 1

        asyncio.create_task(run_wrapper())

    async def _build_context(
        self,
        process_id: str,
        subprocess_id: str,
        subprocess_type: str,
        configuration: ProcessConfiguration,
    ) -> Optional[SubprocessContext]:
        """Baut den SubprocessContext aus Konfiguration und Input-Daten."""
        config = configuration.subprocess_config.get(subprocess_id, {})
        root_ids = configuration.dataflow.get_root_nodes()

        if subprocess_id in root_ids:
            dataset_doc = await self._dataset_repo.find_by_id(
                configuration.input_dataset_id
            )
            if not dataset_doc:
                return None
            data_ids = dataset_doc.get("data_ids", [])
            input_data = []
            for did in data_ids:
                d = await self._data_repo.find_by_id(did)
                if d:
                    from dflowp.core.datastructures.data import Data

                    input_data.append(
                        Data(data_id=d["data_id"], content=d.get("content", {}), type=d.get("type", "input"))
                    )
            return SubprocessContext(
                process_id=process_id,
                subprocess_id=subprocess_id,
                subprocess_type=subprocess_type,
                config=config,
                input_data=input_data,
            )

        predecessors = configuration.dataflow.get_predecessors(subprocess_id)
        dataflow_doc = await self._dataflow_state_repo.get_dataflow_state(process_id)
        if not dataflow_doc:
            return None

        all_output_ids = []
        for pred in predecessors:
            for n in dataflow_doc.get("nodes", []):
                if n.get("subprocess_id") == pred:
                    for s in n.get("io_transformation_states", []):
                        all_output_ids.extend(s.get("output_data_ids", []))
                    break

        input_data = []
        for did in all_output_ids:
            d = await self._data_repo.find_by_id(did)
            if d:
                from dflowp.core.datastructures.data import Data

                input_data.append(
                    Data(data_id=d["data_id"], content=d.get("content", {}), type=d.get("type", "output"))
                )

        return SubprocessContext(
            process_id=process_id,
            subprocess_id=subprocess_id,
            subprocess_type=subprocess_type,
            config=config,
            input_data=input_data,
        )

    async def _on_subprocess_completed(self, event: dict) -> None:
        """Handler für EVENT_COMPLETED - startet Nachfolger-Subprozesse."""
        process_id = event.get("process_id")
        subprocess_id = event.get("subprocess_id")
        if not process_id or not subprocess_id:
            return

        # Prozess-Level-Events (subprocess_id="0") nicht rekursiv verarbeiten
        if subprocess_id == "0":
            return

        proc_doc = await self._process_repo.find_by_id(process_id)
        if not proc_doc:
            return

        config_doc = proc_doc.get("configuration", proc_doc)
        configuration = ProcessConfiguration.from_dict(config_doc)
        successors = configuration.dataflow.get_successors(subprocess_id)

        for succ_id in successors:
            await self._start_subprocess(process_id, succ_id, configuration)

        if not successors:
            all_completed = await self._check_all_completed(process_id, configuration)
            if all_completed:
                await self._process_repo.update(process_id, {"status": "completed"})
                await self._event_service.emit_completed(
                    process_id=process_id, subprocess_id="0"
                )

    async def _on_subprocess_failed(self, event: dict) -> None:
        """Handler für EVENT_FAILED."""
        process_id = event.get("process_id")
        if process_id:
            await self._process_repo.update(process_id, {"status": "failed"})

    async def _check_all_completed(
        self, process_id: str, configuration: ProcessConfiguration
    ) -> bool:
        """Prüft ob alle Subprozesse completed sind."""
        doc = await self._dataflow_state_repo.get_dataflow_state(process_id)
        if not doc:
            return False
        for n in doc.get("nodes", []):
            if n.get("event_status") != EVENT_COMPLETED:
                return False
        return True
