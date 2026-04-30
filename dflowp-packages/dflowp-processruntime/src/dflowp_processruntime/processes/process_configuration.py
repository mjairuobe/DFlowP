"""Pipeline-Konfiguration – vollständiger Startkontext."""

import os
from typing import Any

from pydantic import BaseModel, Field

from dflowp_processruntime.dataflow.dataflow import DataFlow
from dflowp_processruntime.dataflow.dataflow_parser import parse_dataflow
from dflowp_processruntime.processes.software_version import build_semantic_software_version


class PipelineConfiguration(BaseModel):
    """
    Vollständige Konfiguration für den Pipeline-Start.
    ``plugin_config`` mappt ``plugin_worker_id`` → optionale Parameter (API-Keys, Modelle, …).
    """

    pipeline_id: str
    software_version: str = "0.1.0"
    input_dataset_id: str = Field(..., description="ID des Input-Datasets")
    dataflow: DataFlow = Field(...)
    plugin_config: dict[str, dict[str, Any]] = Field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "PipelineConfiguration":
        dataflow = d.get("dataflow")
        if isinstance(dataflow, dict):
            dataflow = parse_dataflow(dataflow)
        pipeline_id = d.get("pipeline_id")
        if not pipeline_id:
            raise KeyError("pipeline_id erforderlich")
        raw_cfg = d.get("plugin_config") or {}
        return cls(
            pipeline_id=pipeline_id,
            software_version=d.get("software_version", "0.1.0"),
            input_dataset_id=d["input_dataset_id"],
            dataflow=dataflow,
            plugin_config=dict(raw_cfg) if isinstance(raw_cfg, dict) else {},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "pipeline_id": self.pipeline_id,
            "software_version": self.software_version,
            "input_dataset_id": self.input_dataset_id,
            "dataflow": {
                "nodes": [
                    {
                        "plugin_worker_id": n.plugin_worker_id,
                        "plugin_type": n.plugin_type,
                    }
                    for n in self.dataflow.nodes
                ],
                "edges": [{"from": e.from_node, "to": e.to_node} for e in self.dataflow.edges],
            },
            "plugin_config": self.plugin_config,
        }

    def apply_default_openai_key_from_env(self) -> None:
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            return
        for w_id, sub_cfg in self.plugin_config.items():
            node = self.dataflow.get_node(w_id)
            if node and node.plugin_type == "EmbedData":
                sub_cfg.setdefault("openai_api_key", key)

    def apply_software_version_from_env(self) -> None:
        raw_version = os.environ.get("SOFTWARE_VERSION") or os.environ.get("DFLOWP_SOFTWARE_VERSION")
        if raw_version:
            self.software_version = build_semantic_software_version(raw_version)

