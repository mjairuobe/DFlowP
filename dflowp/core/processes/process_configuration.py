"""Prozesskonfiguration - komplette Konfiguration für den Prozessstart."""

from typing import Any

from pydantic import BaseModel, Field

from dflowp.core.dataflow.dataflow import DataFlow
from dflowp.core.dataflow.dataflow_parser import parse_dataflow


class ProcessConfiguration(BaseModel):
    """
    Komplette Konfiguration, die ein Prozess beim Starten benötigt.
    Entspricht der Struktur aus processconfig_example.json.
    """

    process_id: str
    software_version: str = "1.0.0"
    input_dataset_id: str = Field(..., description="ID des Input-Datasets")
    dataflow: DataFlow = Field(...)
    subprocess_config: dict[str, dict[str, Any]] = Field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ProcessConfiguration":
        """Erstellt aus Dict (z.B. aus JSON)."""
        dataflow = d.get("dataflow")
        if isinstance(dataflow, dict):
            dataflow = parse_dataflow(dataflow)
        return cls(
            process_id=d["process_id"],
            software_version=d.get("software_version", "1.0.0"),
            input_dataset_id=d["input_dataset_id"],
            dataflow=dataflow,
            subprocess_config=d.get("subprocess_config", {}),
        )

    def to_dict(self) -> dict[str, Any]:
        """Konvertiert zu Dict für JSON/DB."""
        return {
            "process_id": self.process_id,
            "software_version": self.software_version,
            "input_dataset_id": self.input_dataset_id,
            "dataflow": {
                "nodes": [{"subprocess_id": n.subprocess_id, "subprocess_type": n.subprocess_type} for n in self.dataflow.nodes],
                "edges": [{"from": e.from_node, "to": e.to_node} for e in self.dataflow.edges],
            },
            "subprocess_config": self.subprocess_config,
        }
