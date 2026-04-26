"""DataflowState - alle Knoten-States in einem Lauf."""

from dflowp_processruntime.dataflow.dataflow import DataFlow, DataflowEdge, DataflowNodeDef
from dflowp_processruntime.dataflow.dataflow_node import DataflowNodeState
from pydantic import BaseModel, Field


class DataflowState(BaseModel):
    """
    Laufzeit-Zustand: Struktur (nodes, edges) + pro Knoten: event_status, io_transformation_states.
    """

    nodes: list[DataflowNodeState] = Field(default_factory=list)
    edges: list[DataflowEdge] = Field(default_factory=list)

    def get_node(self, plugin_worker_id: str) -> DataflowNodeState | None:
        for n in self.nodes:
            if n.plugin_worker_id == plugin_worker_id:
                return n
        return None

    def to_dict(self) -> dict:
        return {
            "nodes": [
                {
                    "plugin_worker_id": n.plugin_worker_id,
                    "plugin_type": n.plugin_type,
                    "event_status": n.event_status,
                    "io_transformation_states": [s.to_dict() for s in n.io_transformation_states],
                }
                for n in self.nodes
            ],
            "edges": [{"from": e.from_node, "to": e.to_node} for e in self.edges],
        }

    @classmethod
    def from_dataflow(cls, dataflow: DataFlow) -> "DataflowState":
        nodes = [
            DataflowNodeState(
                plugin_worker_id=n.plugin_worker_id,
                plugin_type=n.plugin_type,
                event_status="Not Started",
                io_transformation_states=[],
            )
            for n in dataflow.nodes
        ]
        return cls(nodes=nodes, edges=dataflow.edges)
