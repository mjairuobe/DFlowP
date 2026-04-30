"""Parser für DataFlow und DataflowState aus JSON."""

from typing import Any

from dflowp_processruntime.dataflow.dataflow import DataFlow, DataflowEdge, DataflowNodeDef
from dflowp_processruntime.dataflow.dataflow_state import DataflowState
from dflowp_processruntime.dataflow.dataflow_node import DataflowNodeState
from dflowp_processruntime.subprocesses.io_transformation_state import IOTransformationState


def _node_id(n: dict[str, Any]) -> str:
    return str(n.get("plugin_worker_id") or "")


def _node_type(n: dict[str, Any]) -> str:
    return str(n.get("plugin_type") or "")


def parse_dataflow(obj: dict[str, Any]) -> DataFlow:
    """Parst DataFlow mit ``plugin_worker_id``/``plugin_type``."""
    nodes = [
        DataflowNodeDef(plugin_worker_id=_node_id(n), plugin_type=_node_type(n))
        for n in obj.get("nodes", [])
    ]
    edges = [
        DataflowEdge(**e) if isinstance(e, dict) else DataflowEdge(from_node=e["from"], to_node=e["to"])
        for e in obj.get("edges", [])
    ]
    return DataFlow(nodes=nodes, edges=edges)


def parse_dataflow_state(obj: dict[str, Any]) -> DataflowState:
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
                plugin_worker_id=_node_id(n),
                plugin_type=_node_type(n),
                event_status=n.get("event_status", "Not Started"),
                io_transformation_states=io_states,
            )
        )

    edges = [
        DataflowEdge(from_node=e["from"], to_node=e["to"])
        for e in dataflow.get("edges", [])
    ]
    return DataflowState(nodes=nodes, edges=edges)
