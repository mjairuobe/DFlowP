"""DataflowNodeState - enthält I/O-Transformation-States und Event-Status."""

from typing import Optional

from pydantic import BaseModel, Field

from dflowp_processruntime.subprocesses.io_transformation_state import (
    IOTransformationState,
)


class DataflowNodeState(BaseModel):
    """
    Zustand eines Dataflow-Knotens (Pro Plugin-Instanz / ``plugin_worker_id``).
    """

    plugin_worker_id: str
    plugin_type: str
    event_status: str = Field(default="Not Started")
    io_transformation_states: list[IOTransformationState] = Field(default_factory=list)

    def get_io_state(self, input_data_id: str) -> Optional[IOTransformationState]:
        for s in self.io_transformation_states:
            if s.input_data_id == input_data_id:
                return s
        return None

    def add_or_update_io_state(self, state: IOTransformationState) -> None:
        for i, s in enumerate(self.io_transformation_states):
            if s.input_data_id == state.input_data_id:
                self.io_transformation_states[i] = state
                return
        self.io_transformation_states.append(state)
