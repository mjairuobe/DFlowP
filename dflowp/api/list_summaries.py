"""Listen-Antworten: nur Metadaten / Identifikation (ohne große eingebettete Inhalte)."""

from __future__ import annotations

from typing import Any


def summarize_pipeline_list_item(doc: dict[str, Any]) -> dict[str, Any]:
    pid = doc.get("pipeline_id") or doc.get("process_id")
    return {
        "pipeline_id": pid,
        "software_version": doc.get("software_version"),
        "input_dataset_id": doc.get("input_dataset_id"),
        "dataflow_id": doc.get("dataflow_id"),
        "plugin_configuration_id": doc.get("plugin_configuration_id"),
        "dataflow_state_id": doc.get("dataflow_state_id"),
        "status": doc.get("status"),
        "timestamp_ms": doc.get("timestamp_ms"),
    }


def summarize_dataflow_list_item(doc: dict[str, Any]) -> dict[str, Any]:
    nodes = doc.get("nodes") or []
    edges = doc.get("edges") or []
    return {
        "dataflow_id": doc.get("dataflow_id"),
        "name": doc.get("name"),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "timestamp_ms": doc.get("timestamp_ms"),
    }


def summarize_dataflow_state_list_item(doc: dict[str, Any]) -> dict[str, Any]:
    inner = doc.get("dataflow_state")
    if isinstance(inner, dict):
        nodes = inner.get("nodes") or doc.get("nodes") or []
    else:
        nodes = doc.get("nodes") or []
    return {
        "dataflow_state_id": doc.get("dataflow_state_id"),
        "pipeline_id": doc.get("pipeline_id"),
        "dataflow_id": doc.get("dataflow_id"),
        "node_count": len(nodes),
        "timestamp_ms": doc.get("timestamp_ms"),
    }


def summarize_plugin_configuration_list_item(doc: dict[str, Any]) -> dict[str, Any]:
    bym = doc.get("by_plugin_worker_id") or {}
    keys: list[str] = list(bym.keys()) if isinstance(bym, dict) else []
    return {
        "plugin_configuration_id": doc.get("plugin_configuration_id"),
        "plugin_worker_ids": keys,
        "plugin_worker_count": len(keys),
        "timestamp_ms": doc.get("timestamp_ms"),
    }


def apply_summary_to_page(page: dict[str, Any], fn: Any) -> dict[str, Any]:
    out = dict(page)
    out["items"] = [fn(x) for x in out.get("items", [])]
    return out
