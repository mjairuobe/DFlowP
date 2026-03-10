"""DataFlow - Beschreibt den Ablauf (z.B. Scraping -> Embedding -> Clustering)."""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class DataflowNodeDef(BaseModel):
    """Definition eines Knotens im DataFlow."""

    subprocess_id: str
    subprocess_type: str


class DataflowEdge(BaseModel):
    """Definition einer Kante im DataFlow."""

    model_config = ConfigDict(populate_by_name=True)
    from_node: str = Field(..., alias="from")
    to_node: str = Field(..., alias="to")


class DataFlow(BaseModel):
    """
    Beschreibt welche Teilprozesse wann ausgeführt werden.
    Unabhängig von einer konkreten Ausführung.
    """

    nodes: list[DataflowNodeDef] = Field(default_factory=list)
    edges: list[DataflowEdge] = Field(default_factory=list)

    def get_node(self, subprocess_id: str) -> Optional[DataflowNodeDef]:
        """Findet einen Knoten anhand der subprocess_id."""
        for n in self.nodes:
            if n.subprocess_id == subprocess_id:
                return n
        return None

    def get_successors(self, subprocess_id: str) -> list[str]:
        """Gibt die Nachfolger-Knoten einer subprocess_id zurück."""
        return [e.to_node for e in self.edges if e.from_node == subprocess_id]

    def get_predecessors(self, subprocess_id: str) -> list[str]:
        """Gibt die Vorgänger-Knoten einer subprocess_id zurück."""
        return [e.from_node for e in self.edges if e.to_node == subprocess_id]

    def get_root_nodes(self) -> list[str]:
        """Knoten ohne Vorgänger (Startknoten)."""
        all_nodes = {n.subprocess_id for n in self.nodes}
        has_predecessor = {e.to_node for e in self.edges}
        return list(all_nodes - has_predecessor)
