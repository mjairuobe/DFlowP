"""Lädt :class:`PipelineConfiguration` aus referenzierten Repository-Dokumenten."""

from typing import Any

from dflowp_core.database.dataflow_repository import DataflowRepository
from dflowp_core.database.plugin_configuration_repository import PluginConfigurationRepository
from dflowp_processruntime.dataflow.dataflow_parser import parse_dataflow
from dflowp_processruntime.processes.process_configuration import PipelineConfiguration


async def load_pipeline_configuration(pipeline_doc: dict[str, Any]) -> PipelineConfiguration:
    df_id = pipeline_doc.get("dataflow_id")
    pc_id = pipeline_doc.get("plugin_configuration_id")
    if not df_id or not pc_id:
        raise ValueError("dataflow_id und plugin_configuration_id erforderlich")
    dfr = DataflowRepository()
    pcr = PluginConfigurationRepository()
    dfd = await dfr.find_by_id(df_id)
    pcd = await pcr.find_by_id(pc_id)
    if not dfd or not pcd:
        raise ValueError("Dataflow oder Plugin-Konfiguration nicht gefunden")
    nodes_edges = {k: dfd[k] for k in ("nodes", "edges") if k in dfd}
    dataflow = parse_dataflow(nodes_edges)
    by_pw = pcd.get("by_plugin_worker_id") or {}
    return PipelineConfiguration(
        pipeline_id=pipeline_doc["pipeline_id"],
        software_version=pipeline_doc.get("software_version", "0.1.0"),
        input_dataset_id=pipeline_doc["input_dataset_id"],
        dataflow=dataflow,
        plugin_config=dict(by_pw) if isinstance(by_pw, dict) else {},
    )
