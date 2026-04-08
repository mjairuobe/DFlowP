"""Abstrakte Implementation eines Subprozesses."""

from abc import ABC, abstractmethod
from typing import Any, Optional

from dflowp_processruntime.subprocesses.subprocess_context import SubprocessContext
from dflowp_processruntime.subprocesses.io_transformation_state import IOTransformationState


class BaseSubprocess(ABC):
    """
    Abstrakte Basis eines Subprozesses.
    - Emittiert EVENT_STARTED automatisch beim Start
    - Emittiert EVENT_COMPLETED bei Fertigstellung
    - Kein direkter DB-Zugriff - nutzt Repositories via Context/Callbacks
    """

    def __init__(self, subprocess_type: str) -> None:
        self.subprocess_type = subprocess_type

    @abstractmethod
    async def run(
        self,
        context: SubprocessContext,
        event_emitter: Optional[Any] = None,
        state_updater: Optional[Any] = None,
        data_repository: Optional[Any] = None,
        dataset_repository: Optional[Any] = None,
    ) -> list[IOTransformationState]:
        """
        Führt den Subprozess aus.

        Args:
            context: SubprocessContext mit Input-Daten und Config
            event_emitter: Callback zum Emittieren von Events (emit_started, emit_completed, emit_failed)
            state_updater: Callback zum Aktualisieren des dataflow_node_state
            data_repository: Repository zum Speichern von Output-Daten
            dataset_repository: Repository für Datasets

        Returns:
            Liste der IOTransformationState für jeden verarbeiteten Input
        """
        pass
