"""Abstrakte Pipeline (Prozess) – fachlich eine ausführbare Pipeline-Instanz."""

from abc import ABC
from typing import Any, Optional

from dflowp_processruntime.dataflow.dataflow_state import DataflowState
from dflowp_processruntime.processes.process_configuration import PipelineConfiguration
from dflowp_processruntime.processes.process_state import ProcessState


class Process(ABC):
    """Abstrakte Basis: Konfiguration + optionaler Laufzustand."""

    def __init__(
        self,
        configuration: PipelineConfiguration,
        state: Optional[ProcessState] = None,
    ) -> None:
        self.configuration = configuration
        self.state = state or ProcessState(
            pipeline_id=configuration.pipeline_id,
            dataflow_state=DataflowState.from_dataflow(configuration.dataflow),
        )

    @property
    def pipeline_id(self) -> str:
        return self.configuration.pipeline_id

    @property
    def dataflow_state(self) -> DataflowState:
        if self.state.dataflow_state is None:
            self.state.dataflow_state = DataflowState.from_dataflow(
                self.configuration.dataflow
            )
        return self.state.dataflow_state
