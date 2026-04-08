"""DataflowState - Alle Knoten-States im gesamten Prozess."""

from pydantic import BaseModel, Field

from dflowp_processruntime.dataflow.dataflow import DataFlow, DataflowEdge, DataflowNodeDef
from dflowp_processruntime.dataflow.dataflow_node import DataflowNodeState


class DataflowState(BaseModel):
    """
    Enthält den vollständigen State des DataFlows:
    - Struktur (nodes, edges)
    - Pro Node: event_status und io_transformation_states
    """

    nodes: list[DataflowNodeState] = Field(default_factory=list)
    edges: list[DataflowEdge] = Field(default_factory=list)

    def get_node(self, subprocess_id: str) -> DataflowNodeState | None:
        """Findet einen Knoten-State anhand der subprocess_id."""
        for n in self.nodes:
            if n.subprocess_id == subprocess_id:
                return n
        return None

    def to_dict(self) -> dict:
        """Konvertiert zu Dict für JSON/DB."""
        return {
            "nodes": [
                {
                    "subprocess_id": n.subprocess_id,
                    "subprocess_type": n.subprocess_type,
                    "event_status": n.event_status,
                    "io_transformation_states": [s.to_dict() for s in n.io_transformation_states],
                }
                for n in self.nodes
            ],
            "edges": [{"from": e.from_node, "to": e.to_node} for e in self.edges],
        }

    @classmethod
    def from_dataflow(cls, dataflow: DataFlow) -> "DataflowState":
        """Erstellt leeren DataflowState aus DataFlow-Definition."""
        nodes = [
            DataflowNodeState(
                subprocess_id=n.subprocess_id,
                subprocess_type=n.subprocess_type,
                event_status="Not Started",
                io_transformation_states=[],
            )
            for n in dataflow.nodes
        ]
        return cls(nodes=nodes, edges=dataflow.edges)
