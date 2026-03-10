"""Abstrakte Implementation eines Prozesses."""

from abc import ABC
from typing import Any, Optional

from dflowp.core.processes.process_configuration import ProcessConfiguration
from dflowp.core.processes.process_state import ProcessState
from dflowp.core.dataflow.dataflow_state import DataflowState


class Process(ABC):
    """
    Abstrakte Basis eines Prozesses.
    Zugriff auf DB ausschließlich über Repositories (Dependency Injection).
    """

    def __init__(
        self,
        configuration: ProcessConfiguration,
        state: Optional[ProcessState] = None,
    ) -> None:
        self.configuration = configuration
        self.state = state or ProcessState(
            process_id=configuration.process_id,
            dataflow_state=DataflowState.from_dataflow(configuration.dataflow),
        )

    @property
    def process_id(self) -> str:
        return self.configuration.process_id

    @property
    def dataflow_state(self) -> DataflowState:
        if self.state.dataflow_state is None:
            self.state.dataflow_state = DataflowState.from_dataflow(
                self.configuration.dataflow
            )
        return self.state.dataflow_state
