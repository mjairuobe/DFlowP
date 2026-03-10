"""Parser für DataFlow und DataflowState aus JSON."""

from typing import Any

from dflowp.core.dataflow.dataflow import DataFlow, DataflowEdge, DataflowNodeDef
from dflowp.core.dataflow.dataflow_state import DataflowState
from dflowp.core.dataflow.dataflow_node import DataflowNodeState
from dflowp.core.subprocesses.io_transformation_state import IOTransformationState


def parse_dataflow(obj: dict[str, Any]) -> DataFlow:
    """Parst DataFlow aus JSON-ähnlichem Dict."""
    nodes = [
        DataflowNodeDef(subprocess_id=n["subprocess_id"], subprocess_type=n["subprocess_type"])
        for n in obj.get("nodes", [])
    ]
    edges = [
        DataflowEdge(**e) if isinstance(e, dict) else DataflowEdge(from_node=e["from"], to_node=e["to"])
        for e in obj.get("edges", [])
    ]
    return DataFlow(nodes=nodes, edges=edges)


def parse_dataflow_state(obj: dict[str, Any]) -> DataflowState:
    """Parst DataflowState aus JSON-ähnlichem Dict."""
    dataflow = obj.get("dataflow", obj)
    nodes_raw = dataflow.get("nodes", [])

    nodes = []
    for n in nodes_raw:
        io_states = [
            IOTransformationState.from_dict(s)
            for s in n.get("io_transformation_states", [])
        ]
        nodes.append(
            DataflowNodeState(
                subprocess_id=n["subprocess_id"],
                subprocess_type=n["subprocess_type"],
                event_status=n.get("event_status", "Not Started"),
                io_transformation_states=io_states,
            )
        )

    edges = [
        DataflowEdge(from_node=e["from"], to_node=e["to"])
        for e in dataflow.get("edges", [])
    ]
    return DataflowState(nodes=nodes, edges=edges)
