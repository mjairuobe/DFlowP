"""Abstrakte Implementation eines Plugin-Workers."""

from abc import ABC, abstractmethod
from typing import Any, Optional

from dflowp_processruntime.subprocesses.subprocess_context import PluginWorkerContext
from dflowp_processruntime.subprocesses.io_transformation_state import IOTransformationState


class BasePluginWorker(ABC):
    """
    Abstrakte Basis eines Plugin-Workers.
    - Emittiert EVENT_STARTED automatisch beim Start
    - Emittiert EVENT_COMPLETED bei Fertigstellung
    - Kein direkter DB-Zugriff - nutzt Repositories via Context/Callbacks
    """

    def __init__(self, plugin_type: str) -> None:
        self.plugin_type = plugin_type

    @abstractmethod
    async def run(
        self,
        context: PluginWorkerContext,
        event_emitter: Optional[Any] = None,
        state_updater: Optional[Any] = None,
        data_repository: Optional[Any] = None,
        dataset_repository: Optional[Any] = None,
    ) -> list[IOTransformationState]:
        """
        Führt den Plugin-Worker aus.

        Args:
            context: PluginWorkerContext mit Input-Daten und Config
            event_emitter: Callback zum Emittieren von Events (emit_started, emit_completed, emit_failed)
            state_updater: Callback zum Aktualisieren des dataflow_node_state
            data_repository: Repository zum Speichern von Output-Daten
            dataset_repository: Repository für Datasets

        Returns:
            Liste der IOTransformationState für jeden verarbeiteten Input
        """
        pass
