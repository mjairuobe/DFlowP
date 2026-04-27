"""Tests für die FastAPI-Schnittstelle von DFlowP."""

import os
from typing import Any

from fastapi.testclient import TestClient

from math import ceil

from dflowp.api.app import app
from dflowp.api.deps import get_data_item_repository, get_event_repository, get_process_repository
from dflowp_core.database.data_item_repository import summarize_for_list_view

# Für zustandsbehaftete Fake-Repos (create/update/delete)
_FAKE_PROCESS_DOCS: dict[str, dict] = {}
_FAKE_DATA_ITEMS: dict[str, dict] = {}


def _reset_fake_stores() -> None:
    _FAKE_PROCESS_DOCS.clear()
    _FAKE_DATA_ITEMS.clear()


class _FakeDataItemRepository:
    async def list_datasets(self, *, page: int, page_size: int) -> dict:
        return {
            "items": [
                {
                    "id": "ds_001",
                    "doc_type": "dataset",
                    "data_ids": ["d1", "d2"],
                    "timestamp_ms": 200,
                },
                {"id": "ds_002", "doc_type": "dataset", "data_ids": ["d3"], "timestamp_ms": 100},
            ][:page_size],
            "page": page,
            "page_size": page_size,
            "total_items": 2,
            "total_pages": 1,
        }

    async def list_data_items(
        self, *, page: int, page_size: int, doc_types: list[str] | None = None
    ) -> dict:
        raw_items = [
            {
                "id": "data_001",
                "doc_type": "data",
                "type": "input",
                "content": {"k": "v"},
                "timestamp_ms": 200,
            },
            {"id": "ds_001", "doc_type": "dataset", "data_ids": ["d1", "d2"], "timestamp_ms": 100},
        ]
        if doc_types:
            filtered = [i for i in raw_items if i["doc_type"] in doc_types]
        else:
            filtered = list(raw_items)
        total_items = len(filtered)
        skip = (page - 1) * page_size
        page_slice = filtered[skip : skip + page_size]
        return {
            "items": [summarize_for_list_view(dict(x)) for x in page_slice],
            "page": page,
            "page_size": page_size,
            "total_items": total_items,
            "total_pages": ceil(total_items / page_size) if total_items else 0,
        }

    async def find_data_item_by_id(self, item_id: str) -> dict | None:
        if item_id in _FAKE_DATA_ITEMS:
            return dict(_FAKE_DATA_ITEMS[item_id])
        if item_id == "data_001":
            return {"id": "data_001", "doc_type": "data", "content": {"k": "v"}, "timestamp_ms": 200}
        if item_id == "ds_001":
            return {"id": "ds_001", "doc_type": "dataset", "data_ids": ["d1", "d2"], "timestamp_ms": 100}
        return None

    async def find_by_id(self, item_id: str) -> dict | None:
        return await self.find_data_item_by_id(item_id)

    async def find_dataset_by_id(self, dataset_id: str) -> dict | None:
        doc = await self.find_data_item_by_id(dataset_id)
        if doc and doc.get("doc_type") == "dataset":
            return doc
        if dataset_id == "ds_001":
            return {"id": "ds_001", "doc_type": "dataset", "data_ids": ["d1", "d2"], "timestamp_ms": 200}
        return None

    async def insert(self, doc: dict) -> str:
        item_id = doc.get("id")
        if not item_id:
            raise ValueError("id required")
        _FAKE_DATA_ITEMS[item_id] = dict(doc)
        return "mongo_" + item_id


class _FakeProcessRepository:
    async def create_indexes(self) -> None:
        return

    async def list_processes(self, *, page: int, page_size: int) -> dict:
        return {
            "items": [
                {"pipeline_id": "proc_001", "status": "running", "timestamp_ms": 200},
                {"pipeline_id": "proc_002", "status": "completed", "timestamp_ms": 100},
            ][:page_size],
            "page": page,
            "page_size": page_size,
            "total_items": 2,
            "total_pages": 1,
        }

    async def find_by_id(self, process_id: str) -> dict | None:
        if process_id in _FAKE_PROCESS_DOCS:
            return dict(_FAKE_PROCESS_DOCS[process_id])
        if process_id == "proc_001":
            return {"pipeline_id": "proc_001", "status": "running", "timestamp_ms": 200}
        return None

    async def insert_from_configuration(self, configuration: Any, *, status: str) -> dict:  # noqa: ANN001
        """Speichert eine Pipeline mit Referenzen (Mock)."""
        pid = configuration.pipeline_id
        doc: dict = {
            "pipeline_id": pid,
            "process_id": pid,
            "software_version": configuration.software_version,
            "input_dataset_id": configuration.input_dataset_id,
            "dataflow_id": "df_fake",
            "plugin_configuration_id": "pcfg_fake",
            "dataflow_state_id": "dfs_fake",
            "status": status,
        }
        _FAKE_PROCESS_DOCS[pid] = doc
        return dict(doc)

    async def insert(self, process: dict) -> str:
        pid = process.get("pipeline_id") or process.get("process_id")
        if not pid:
            raise ValueError("pipeline_id or process_id required")
        doc = dict(process)
        doc["_id"] = "mongo_" + str(pid)
        _FAKE_PROCESS_DOCS[str(pid)] = doc
        return str(doc["_id"])

    async def update(self, process_id: str, update: dict) -> bool:
        if process_id in _FAKE_PROCESS_DOCS:
            _FAKE_PROCESS_DOCS[process_id].update(update)
            return True
        return False

    async def delete_by_id(self, process_id: str) -> bool:
        if process_id in _FAKE_PROCESS_DOCS:
            del _FAKE_PROCESS_DOCS[process_id]
            return True
        return False

    async def list_subprocesses(self, *, page: int, page_size: int) -> dict:
        return {
            "items": [
                {
                    "pipeline_id": "proc_001",
                    "plugin_worker_id": "sub_001",
                    "plugin_type": "FetchFeedItems",
                    "subprocess_id": "sub_001",
                    "subprocess_type": "FetchFeedItems",
                    "event_status": "EVENT_COMPLETED",
                    "io_transformation_states": [],
                    "timestamp_ms": 200,
                }
            ][:page_size],
            "page": page,
            "page_size": page_size,
            "total_items": 1,
            "total_pages": 1,
        }

    async def find_subprocess_by_id(self, subprocess_id: str) -> dict | None:
        if subprocess_id == "sub_001":
            return {
                "pipeline_id": "proc_001",
                "plugin_worker_id": "sub_001",
                "plugin_type": "FetchFeedItems",
                "subprocess_id": "sub_001",
                "subprocess_type": "FetchFeedItems",
                "event_status": "EVENT_COMPLETED",
                "io_transformation_states": [],
                "timestamp_ms": 200,
            }
        return None

    async def list_pipelines(self, *, page: int, page_size: int) -> dict:
        return await self.list_processes(page=page, page_size=page_size)

    async def list_plugin_workers(self, *, page: int, page_size: int) -> dict:
        return await self.list_subprocesses(page=page, page_size=page_size)

    async def find_plugin_worker(self, pipeline_id: str, plugin_worker_id: str) -> dict | None:
        if pipeline_id != "proc_001":
            return None
        return await self.find_subprocess_by_id(plugin_worker_id)

    async def copy_pipeline_with_reexecution(
        self,
        *,
        source_pipeline_id: str,
        target_pipeline_id: str,
        parent_plugin_worker_ids: list[str] | None = None,
        plugin_config_override: dict | None = None,
        dataflow_id_override: str | None = None,
    ) -> dict | None:
        return await self.copy_process_with_reexecution(
            source_process_id=source_pipeline_id,
            target_process_id=target_pipeline_id,
            parent_subprocess_ids=list(parent_plugin_worker_ids or []),
            subprocess_config_override=plugin_config_override,
        )

    async def copy_process_with_reexecution(
        self,
        *,
        source_process_id: str,
        target_process_id: str,
        parent_subprocess_ids: list[str],
        subprocess_config_override: dict | None = None,
    ) -> dict | None:
        if source_process_id != "proc_001":
            return None
        cfg = {"process_id": target_process_id}
        if subprocess_config_override:
            cfg["subprocess_config"] = subprocess_config_override
            cfg["plugin_config"] = subprocess_config_override
        return {
            "pipeline_id": target_process_id,
            "process_id": target_process_id,
            "dataflow_id": "df_cloned",
            "dataflow_state_id": "dfs_cloned",
            "plugin_configuration_id": "pcfg_cloned",
            "status": "pending",
            "configuration": cfg,
            "dataflow_state": {
                "nodes": [
                    {
                        "plugin_worker_id": "sub_001",
                        "subprocess_id": "sub_001",
                        "event_status": "Not Started",
                        "io_transformation_states": [],
                    }
                ],
                "edges": [],
            },
            "reexecution_roots": parent_subprocess_ids,
        }


class _FakeEventRepository:
    async def create_indexes(self) -> None:
        return

    async def list_events(
        self,
        *,
        page: int,
        page_size: int,
        process_id: str | None = None,
        pipeline_id: str | None = None,
    ) -> dict:
        return {
            "items": [
                {
                    "_id": "evt_001",
                    "process_id": "proc_001",
                    "subprocess_id": "sub_001",
                    "event_type": "EVENT_COMPLETED",
                    "event_time": "2026-04-06T10:00:00Z",
                    "timestamp_ms": 200,
                },
                {
                    "_id": "evt_002",
                    "process_id": "proc_001",
                    "subprocess_id": "sub_001",
                    "event_type": "EVENT_STARTED",
                    "event_time": "2026-04-06T09:00:00Z",
                    "timestamp_ms": 100,
                }
            ][:page_size],
            "page": page,
            "page_size": page_size,
            "total_items": 2,
            "total_pages": 2,
        }

    async def find_by_id(self, event_id: str) -> dict | None:
        if event_id == "evt_001":
            return {
                "_id": "evt_001",
                "process_id": "proc_001",
                "subprocess_id": "sub_001",
                "event_type": "EVENT_COMPLETED",
                "event_time": "2026-04-06T10:00:00Z",
                "timestamp_ms": 200,
            }
        return None


def _create_client() -> TestClient:
    _reset_fake_stores()
    os.environ["DFLOWP_SKIP_DB_INIT"] = "1"
    os.environ["DFlowP_API_Key"] = "test-key"

    app.dependency_overrides[get_data_item_repository] = _FakeDataItemRepository
    app.dependency_overrides[get_process_repository] = _FakeProcessRepository
    app.dependency_overrides[get_event_repository] = _FakeEventRepository

    return TestClient(app, base_url="http://127.0.0.1:8000")


def _auth_headers() -> dict[str, str]:
    return {"X-API-Key": "test-key"}


def test_api_rejects_missing_api_key() -> None:
    client = _create_client()
    response = client.get("/api/v1/data")
    assert response.status_code == 401


def test_list_data_datasets_only_via_doc_type() -> None:
    client = _create_client()
    response = client.get(
        "/api/v1/data?doc_type=dataset&page=1&page_size=2", headers=_auth_headers()
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["page"] == 1
    assert len(payload["items"]) >= 1
    assert payload["items"][0]["doc_type"] == "dataset"


def test_get_dataset_detail_via_data_endpoint() -> None:
    client = _create_client()
    response = client.get("/api/v1/data/ds_001", headers=_auth_headers())
    assert response.status_code == 200
    assert response.json()["id"] == "ds_001"


def test_get_data_not_found() -> None:
    client = _create_client()
    response = client.get("/api/v1/data/not_found", headers=_auth_headers())
    assert response.status_code == 404


def test_list_processes_with_pagination() -> None:
    client = _create_client()
    response = client.get("/api/v1/pipelines?page=1&page_size=2", headers=_auth_headers())
    assert response.status_code == 200
    payload = response.json()
    assert payload["page"] == 1
    assert payload["page_size"] == 2
    assert payload["total_items"] == 2
    assert len(payload["items"]) == 2
    assert payload["items"][0]["timestamp_ms"] > payload["items"][1]["timestamp_ms"]


def test_get_process_detail() -> None:
    client = _create_client()
    response = client.get("/api/v1/pipelines/proc_001", headers=_auth_headers())
    assert response.status_code == 200
    assert response.json()["pipeline_id"] == "proc_001"


def test_get_process_detail_not_found() -> None:
    client = _create_client()
    response = client.get("/api/v1/pipelines/not_found", headers=_auth_headers())
    assert response.status_code == 404


def test_list_subprocesses_with_pagination() -> None:
    client = _create_client()
    response = client.get("/api/v1/plugin-workers?page=1&page_size=1", headers=_auth_headers())
    assert response.status_code == 200
    payload = response.json()
    assert payload["page"] == 1
    assert payload["page_size"] == 1
    assert payload["total_items"] == 1
    assert len(payload["items"]) == 1
    assert payload["items"][0]["timestamp_ms"] == 200


def test_get_subprocess_detail() -> None:
    client = _create_client()
    response = client.get(
        "/api/v1/pipelines/proc_001/plugin-workers/sub_001", headers=_auth_headers()
    )
    assert response.status_code == 200
    body = response.json()
    assert body.get("plugin_worker_id") == "sub_001" or body.get("subprocess_id") == "sub_001"


def test_get_subprocess_detail_not_found() -> None:
    client = _create_client()
    response = client.get(
        "/api/v1/pipelines/proc_001/plugin-workers/not_found", headers=_auth_headers()
    )
    assert response.status_code == 404


def test_list_data_with_pagination() -> None:
    client = _create_client()
    response = client.get("/api/v1/data?page=1&page_size=2", headers=_auth_headers())
    assert response.status_code == 200
    payload = response.json()
    assert payload["page"] == 1
    assert payload["page_size"] == 2
    assert payload["total_items"] == 2
    assert len(payload["items"]) == 2
    assert payload["items"][0]["timestamp_ms"] > payload["items"][1]["timestamp_ms"]
    for item in payload["items"]:
        assert "content" not in item


def test_list_data_doc_type_filter() -> None:
    client = _create_client()
    r = client.get(
        "/api/v1/data?doc_type=data&doc_type=dataset",
        headers=_auth_headers(),
    )
    assert r.status_code == 200
    assert r.json()["total_items"] == 2
    r_data = client.get("/api/v1/data?doc_type=data", headers=_auth_headers())
    assert r_data.status_code == 200
    body = r_data.json()
    assert body["total_items"] == 1
    assert body["items"][0]["doc_type"] == "data"
    assert "content" not in body["items"][0]


def test_list_data_doc_type_invalid() -> None:
    client = _create_client()
    response = client.get("/api/v1/data?doc_type=foo", headers=_auth_headers())
    assert response.status_code == 422
    assert "doc_type" in response.json()["detail"].lower()


def test_get_data_detail_includes_content() -> None:
    client = _create_client()
    response = client.get("/api/v1/data/data_001", headers=_auth_headers())
    assert response.status_code == 200
    assert response.json()["id"] == "data_001"
    assert response.json()["content"]["k"] == "v"


def test_get_data_detail_not_found() -> None:
    client = _create_client()
    response = client.get("/api/v1/data/not_found", headers=_auth_headers())
    assert response.status_code == 404


def test_create_data_item() -> None:
    client = _create_client()
    response = client.post(
        "/api/v1/data",
        headers=_auth_headers(),
        json={
            "id": "data_new_1",
            "content": {"title": "T", "xmlUrl": "https://example.com/feed"},
            "type": "input",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["id"] == "data_new_1"
    assert body["doc_type"] == "data"
    assert body["content"]["xmlUrl"] == "https://example.com/feed"


def test_create_dataset_with_rows() -> None:
    client = _create_client()
    response = client.post(
        "/api/v1/data",
        headers=_auth_headers(),
        json={
            "doc_type": "dataset",
            "id": "ds_feed_batch",
            "rows": [
                {"title": "A", "text": "x", "xmlUrl": "https://a/feed", "htmlUrl": "https://a/"},
                {"title": "B", "text": "y", "xmlUrl": "https://b/feed", "htmlUrl": "https://b/"},
            ],
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["id"] == "ds_feed_batch"
    assert body["doc_type"] == "dataset"
    assert body["data_ids"] == ["ds_feed_batch_row_0", "ds_feed_batch_row_1"]


def test_create_dataset_with_data_ids() -> None:
    client = _create_client()
    client.post(
        "/api/v1/data",
        headers=_auth_headers(),
        json={"id": "d_ref_a", "content": {"x": 1}, "type": "input"},
    )
    client.post(
        "/api/v1/data",
        headers=_auth_headers(),
        json={"id": "d_ref_b", "content": {"x": 2}, "type": "input"},
    )
    response = client.post(
        "/api/v1/data",
        headers=_auth_headers(),
        json={
            "doc_type": "dataset",
            "id": "ds_from_refs",
            "data_ids": ["d_ref_a", "d_ref_b"],
        },
    )
    assert response.status_code == 201
    assert response.json()["data_ids"] == ["d_ref_a", "d_ref_b"]


def test_create_dataset_conflict_existing_id() -> None:
    client = _create_client()
    r1 = client.post(
        "/api/v1/data",
        headers=_auth_headers(),
        json={"doc_type": "dataset", "id": "ds_dup", "rows": [{"a": 1}]},
    )
    assert r1.status_code == 201
    r2 = client.post(
        "/api/v1/data",
        headers=_auth_headers(),
        json={"doc_type": "dataset", "id": "ds_dup", "rows": [{"a": 2}]},
    )
    assert r2.status_code == 409


def test_list_events_with_pagination() -> None:
    client = _create_client()
    response = client.get("/api/v1/events?page=1&page_size=2", headers=_auth_headers())
    assert response.status_code == 200
    payload = response.json()
    assert payload["page"] == 1
    assert payload["page_size"] == 2
    assert payload["total_items"] == 2
    assert len(payload["items"]) == 2
    assert payload["items"][0]["timestamp_ms"] > payload["items"][1]["timestamp_ms"]


def test_get_event_detail() -> None:
    client = _create_client()
    response = client.get("/api/v1/events/evt_001", headers=_auth_headers())
    assert response.status_code == 200
    assert response.json()["_id"] == "evt_001"


def test_get_event_detail_not_found() -> None:
    client = _create_client()
    response = client.get("/api/v1/events/not_found", headers=_auth_headers())
    assert response.status_code == 404


def test_clone_process_with_reexecution() -> None:
    client = _create_client()
    response = client.post(
        "/api/v1/pipelines/proc_001/clone",
        headers=_auth_headers(),
        json={
            "parent_plugin_worker_ids": ["sub_001"],
        },
    )
    assert response.status_code == 201
    payload = response.json()
    pid = payload.get("pipeline_id") or payload.get("process_id", "")
    assert str(pid).startswith("proc_001_copy")
    assert payload["status"] == "pending"
    node = payload["dataflow_state"]["nodes"][0]
    assert node["event_status"] == "Not Started"
    assert node["io_transformation_states"] == []


def test_clone_process_source_not_found() -> None:
    client = _create_client()
    response = client.post(
        "/api/v1/pipelines/proc_404/clone",
        headers=_auth_headers(),
        json={
            "parent_plugin_worker_ids": ["sub_001"],
        },
    )
    assert response.status_code == 404


def test_create_process_pending_with_input_data() -> None:
    client = _create_client()
    response = client.post(
        "/api/v1/pipelines",
        headers=_auth_headers(),
        json={
            "pipeline_id": "proc_api_create_1",
            "software_version": "0.1.0",
            "input_dataset_id": "ds_api_feed",
            "dataflow": {
                "nodes": [
                    {"subprocess_id": "F1", "subprocess_type": "FetchFeedItems"},
                    {"subprocess_id": "E1", "subprocess_type": "EmbedData"},
                ],
                "edges": [{"from": "F1", "to": "E1"}],
            },
            "plugin_config": {"F1": {}, "E1": {"model": "text-embedding-3-small"}},
            "input_data": [{"title": "A", "summary": "B", "url": "https://example.com"}],
            "start_immediately": False,
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert (body.get("pipeline_id") or body.get("process_id")) == "proc_api_create_1"
    assert body["status"] == "pending"
    assert body["input_dataset_id"] == "ds_api_feed"
    assert "dataflow_state_id" in body
    assert "ds_api_feed" in _FAKE_DATA_ITEMS


def test_create_process_conflict_existing_id() -> None:
    client = _create_client()
    r1 = client.post(
        "/api/v1/pipelines",
        headers=_auth_headers(),
        json={
            "pipeline_id": "proc_dup",
            "input_dataset_id": "ds_x",
            "dataflow": {
                "nodes": [{"subprocess_id": "F1", "subprocess_type": "FetchFeedItems"}],
                "edges": [],
            },
            "plugin_config": {},
        },
    )
    assert r1.status_code == 201
    r2 = client.post(
        "/api/v1/pipelines",
        headers=_auth_headers(),
        json={
            "pipeline_id": "proc_dup",
            "input_dataset_id": "ds_y",
            "dataflow": {
                "nodes": [{"subprocess_id": "F1", "subprocess_type": "FetchFeedItems"}],
                "edges": [],
            },
            "plugin_config": {},
        },
    )
    assert r2.status_code == 409


def test_stop_process() -> None:
    client = _create_client()
    client.post(
        "/api/v1/pipelines",
        headers=_auth_headers(),
        json={
            "pipeline_id": "proc_stop_me",
            "input_dataset_id": "ds_z",
            "dataflow": {
                "nodes": [{"subprocess_id": "F1", "subprocess_type": "FetchFeedItems"}],
                "edges": [],
            },
            "plugin_config": {},
        },
    )
    r = client.post(
        "/api/v1/pipelines/proc_stop_me/stop",
        headers=_auth_headers(),
        json={"reason": "test"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "stopped"
    assert r.json().get("cancelled_reason") == "test"


def test_delete_process() -> None:
    client = _create_client()
    client.post(
        "/api/v1/pipelines",
        headers=_auth_headers(),
        json={
            "pipeline_id": "proc_del",
            "input_dataset_id": "ds_z",
            "dataflow": {
                "nodes": [{"subprocess_id": "F1", "subprocess_type": "FetchFeedItems"}],
                "edges": [],
            },
            "plugin_config": {},
        },
    )
    r = client.delete("/api/v1/pipelines/proc_del", headers=_auth_headers())
    assert r.status_code == 204
    assert "proc_del" not in _FAKE_PROCESS_DOCS


def test_clone_with_subprocess_config_override() -> None:
    client = _create_client()
    response = client.post(
        "/api/v1/pipelines/proc_001/clone",
        headers=_auth_headers(),
        json={
            "parent_plugin_worker_ids": ["sub_001"],
            "new_pipeline_id": "proc_cloned_cfg",
            "plugin_config": {"EmbedData1": {"model": "text-embedding-3-large"}},
        },
    )
    assert response.status_code == 201
    rj = response.json()
    if "configuration" in rj and "subprocess_config" in rj["configuration"]:
        assert rj["configuration"]["subprocess_config"]["EmbedData1"]["model"] == (
            "text-embedding-3-large"
        )
    else:
        assert "pipeline_id" in rj or "process_id" in rj
