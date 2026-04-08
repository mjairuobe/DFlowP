"""ProcessState - Metadaten zum Prozess-Status und Dataflow-State."""

from typing import Optional

from pydantic import BaseModel, Field

from dflowp_processruntime.dataflow.dataflow_state import DataflowState


class ProcessState(BaseModel):
    """
    Enthält Metadaten zum Prozess-Status und den kompletten Dataflow-State.
    """

    process_id: str
    status: str = Field(default="running", description="running, completed, failed")
    dataflow_state: Optional[DataflowState] = Field(default=None)

    def to_dict(self) -> dict:
        """Konvertiert zu Dict für DB/JSON."""
        return {
            "process_id": self.process_id,
            "status": self.status,
            "dataflow_state": self.dataflow_state.to_dict() if self.dataflow_state else None,
        }
