"""API-Ausgabe für DataflowState: Blätter zuerst, Quality-Aggregate pro Plugin-Worker."""

from __future__ import annotations

import copy
from collections import Counter, deque
from typing import Any

from dflowp_core.quality_aggregates import quality_min_max_avg_median
from dflowp_core.database.dataflow_state_repository import _node_id_key


def _order_nodes_leaves_first(
    nodes: list[dict[str, Any]], edges: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """
    Reversed topological order: Sinks (Blätter) des DAG zuerst, Wurzel zuletzt.
    """
    by_id: dict[str, dict[str, Any]] = {}
    for n in nodes:
        wid = _node_id_key(n)
        if wid:
            by_id[wid] = n
    ids = set(by_id.keys())
    if not ids:
        return []
    rev_adj: dict[str, list[str]] = {i: [] for i in ids}
    indeg = Counter({i: 0 for i in ids})
    for e in edges:
        f, t = e.get("from"), e.get("to")
        if f in ids and t in ids:
            rev_adj[str(t)].append(str(f))
            indeg[str(f)] += 1
    q: deque[str] = deque(i for i in ids if indeg[i] == 0)
    out: list[str] = []
    while q:
        u = q.popleft()
        out.append(u)
        for v in rev_adj.get(u, []):
            indeg[v] -= 1
            if indeg[v] == 0:
                q.append(v)
    for i in ids:
        if i not in out:
            out.append(i)
    return [by_id[i] for i in out if i in by_id]


def build_dataflow_state_api_view(doc: dict[str, Any]) -> dict[str, Any]:
    """
    Fügt ``plugin_worker_summary`` hinzu (Reihenfolge: Blätter zuerst) mit
    ``quality`` {min,max,avg,median} pro Plugin-Worker.
    """
    d = copy.deepcopy(doc)
    inner = d.get("dataflow_state")
    if not isinstance(inner, dict):
        inner = {
            "nodes": d.get("nodes", []),
            "edges": d.get("edges", []),
        }
    nodes = list(inner.get("nodes") or [])
    edges = list(inner.get("edges") or [])
    ordered = _order_nodes_leaves_first(nodes, edges)
    summary: list[dict[str, Any]] = []
    for n in ordered:
        wid = _node_id_key(n)
        if not wid:
            continue
        q = quality_min_max_avg_median(n)
        entry: dict[str, Any] = {
            "plugin_worker_id": wid,
            "plugin_type": n.get("plugin_type") or n.get("subprocess_type"),
            "event_status": n.get("event_status"),
            "quality": q,
        }
        summary.append(entry)
    d["plugin_worker_summary"] = summary
    return d
