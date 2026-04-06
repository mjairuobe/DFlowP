"""Prozesskonfiguration - komplette Konfiguration für den Prozessstart."""

import os
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

    def apply_default_openai_key_from_env(self) -> None:
        """Trägt OPENAI_API_KEY in EmbedData-Subprozess-Configs ein, falls nicht gesetzt."""
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            return
        for subprocess_id, sub_cfg in self.subprocess_config.items():
            node = self.dataflow.get_node(subprocess_id)
            if node and node.subprocess_type == "EmbedData":
                sub_cfg.setdefault("openai_api_key", key)

    def apply_software_version_from_env(self) -> None:
        """
        Überschreibt die Software-Version aus der Umgebung.

        Priorität:
        1) SOFTWARE_VERSION
        2) DFLOWP_SOFTWARE_VERSION
        """
        version = os.environ.get("SOFTWARE_VERSION") or os.environ.get("DFLOWP_SOFTWARE_VERSION")
        if version:
            self.software_version = version
