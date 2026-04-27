"""DataFlow - beschreibt den Ablauf (DAG) über Plugin-Knoten."""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class DataflowNodeDef(BaseModel):
    """Knotendefinition: ``plugin_worker_id`` + Plugin-Typ (Klasse/Remote-Name)."""

    plugin_worker_id: str
    plugin_type: str


class DataflowEdge(BaseModel):
    """Kante im Dataflow."""

    model_config = ConfigDict(populate_by_name=True)
    from_node: str = Field(..., alias="from")
    to_node: str = Field(..., alias="to")


class DataFlow(BaseModel):
    """
    Statische Graph-Struktur (Knoten + Kanten), unabhängig von Laufzeit-State.
    """

    nodes: list[DataflowNodeDef] = Field(default_factory=list)
    edges: list[DataflowEdge] = Field(default_factory=list)

    def get_node(self, plugin_worker_id: str) -> Optional[DataflowNodeDef]:
        for n in self.nodes:
            if n.plugin_worker_id == plugin_worker_id:
                return n
        return None

    def get_successors(self, plugin_worker_id: str) -> list[str]:
        return [e.to_node for e in self.edges if e.from_node == plugin_worker_id]

    def get_predecessors(self, plugin_worker_id: str) -> list[str]:
        return [e.from_node for e in self.edges if e.to_node == plugin_worker_id]

    def get_root_nodes(self) -> list[str]:
        all_nodes = {n.plugin_worker_id for n in self.nodes}
        has_predecessor = {e.to_node for e in self.edges}
        return list(all_nodes - has_predecessor)

    def get_descendants(self, plugin_worker_id: str) -> list[str]:
        descendants: set[str] = set()
        queue = list(self.get_successors(plugin_worker_id))
        while queue:
            node_id = queue.pop(0)
            if node_id in descendants:
                continue
            descendants.add(node_id)
            queue.extend(self.get_successors(node_id))
        return list(descendants)

    def get_descendants_including_self(self, plugin_worker_id: str) -> set[str]:
        visited: set[str] = set()
        stack = [plugin_worker_id]
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            stack.extend(self.get_successors(current))
        return visited
