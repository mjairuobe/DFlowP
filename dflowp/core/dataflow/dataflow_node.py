"""DataflowNode - Enthält IO-Transformation-States und Event-Status."""

from typing import Optional

from pydantic import BaseModel, Field

from dflowp.core.subprocesses.io_transformation_state import (
    IOTransformationState,
    TransformationStatus,
)


class DataflowNodeState(BaseModel):
    """
    State eines Knotens im DataFlow.
    Enthält Event-Status des Subprozesses und io_transformation_states.
    """

    subprocess_id: str
    subprocess_type: str
    event_status: str = Field(default="Not Started")
    io_transformation_states: list[IOTransformationState] = Field(default_factory=list)

    def get_io_state(self, input_data_id: str) -> Optional[IOTransformationState]:
        """Findet IO-Transformation-State für eine Input-Data-ID."""
        for s in self.io_transformation_states:
            if s.input_data_id == input_data_id:
                return s
        return None

    def add_or_update_io_state(self, state: IOTransformationState) -> None:
        """Fügt hinzu oder aktualisiert einen IO-Transformation-State."""
        for i, s in enumerate(self.io_transformation_states):
            if s.input_data_id == state.input_data_id:
                self.io_transformation_states[i] = state
                return
        self.io_transformation_states.append(state)
