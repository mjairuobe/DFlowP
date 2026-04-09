"""Tests für die FastAPI-Schnittstelle von DFlowP."""

import os

from fastapi.testclient import TestClient

from dflowp.api.app import app, get_data_item_repository, get_process_repository

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

    async def list_data_items(self, *, page: int, page_size: int) -> dict:
        return {
            "items": [
                {"id": "data_001", "doc_type": "data", "content": {"k": "v"}, "timestamp_ms": 200},
                {"id": "ds_001", "doc_type": "dataset", "data_ids": ["d1", "d2"], "timestamp_ms": 100},
            ][:page_size],
            "page": page,
            "page_size": page_size,
            "total_items": 2,
            "total_pages": 1,
        }

    async def find_data_item_by_id(self, item_id: str) -> dict | None:
        if item_id in _FAKE_DATA_ITEMS:
            return dict(_FAKE_DATA_ITEMS[item_id])
        if item_id == "data_001":
            return {"id": "data_001", "doc_type": "data", "content": {"k": "v"}, "timestamp_ms": 200}
        if item_id == "ds_001":
            return {"id": "ds_001", "doc_type": "dataset", "data_ids": ["d1", "d2"], "timestamp_ms": 100}
        return None

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
    async def list_processes(self, *, page: int, page_size: int) -> dict:
        return {
            "items": [
                {"process_id": "proc_001", "status": "running", "timestamp_ms": 200},
                {"process_id": "proc_002", "status": "completed", "timestamp_ms": 100},
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
            return {"process_id": "proc_001", "status": "running", "timestamp_ms": 200}
        return None

    async def insert(self, process: dict) -> str:
        pid = process["process_id"]
        doc = dict(process)
        doc["_id"] = "mongo_" + pid
        _FAKE_PROCESS_DOCS[pid] = doc
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
                    "process_id": "proc_001",
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
                "process_id": "proc_001",
                "subprocess_id": "sub_001",
                "subprocess_type": "FetchFeedItems",
                "event_status": "EVENT_COMPLETED",
                "io_transformation_states": [],
                "timestamp_ms": 200,
            }
        return None

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
        return {
            "process_id": target_process_id,
            "status": "pending",
            "configuration": cfg,
            "dataflow_state": {
                "nodes": [
                    {
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
    async def list_events(self, *, page: int, page_size: int, process_id: str | None = None) -> dict:
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
    from dflowp.api.app import get_event_repository

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
    response = client.get("/api/v1/datasets")
    assert response.status_code == 401


def test_list_datasets_with_pagination() -> None:
    client = _create_client()
    response = client.get("/api/v1/datasets?page=1&page_size=2", headers=_auth_headers())
    assert response.status_code == 200
    payload = response.json()
    assert payload["page"] == 1
    assert payload["page_size"] == 2
    assert payload["total_items"] == 2
    assert len(payload["items"]) == 2
    assert payload["items"][0]["timestamp_ms"] > payload["items"][1]["timestamp_ms"]
    assert str(response.request.url).startswith("http://127.0.0.1:8000/")


def test_get_dataset_detail() -> None:
    client = _create_client()
    response = client.get("/api/v1/datasets/ds_001", headers=_auth_headers())
    assert response.status_code == 200
    assert response.json()["id"] == "ds_001"


def test_get_dataset_detail_not_found() -> None:
    client = _create_client()
    response = client.get("/api/v1/datasets/not_found", headers=_auth_headers())
    assert response.status_code == 404


def test_list_processes_with_pagination() -> None:
    client = _create_client()
    response = client.get("/api/v1/processes?page=1&page_size=2", headers=_auth_headers())
    assert response.status_code == 200
    payload = response.json()
    assert payload["page"] == 1
    assert payload["page_size"] == 2
    assert payload["total_items"] == 2
    assert len(payload["items"]) == 2
    assert payload["items"][0]["timestamp_ms"] > payload["items"][1]["timestamp_ms"]


def test_get_process_detail() -> None:
    client = _create_client()
    response = client.get("/api/v1/processes/proc_001", headers=_auth_headers())
    assert response.status_code == 200
    assert response.json()["process_id"] == "proc_001"


def test_get_process_detail_not_found() -> None:
    client = _create_client()
    response = client.get("/api/v1/processes/not_found", headers=_auth_headers())
    assert response.status_code == 404


def test_list_subprocesses_with_pagination() -> None:
    client = _create_client()
    response = client.get("/api/v1/subprocesses?page=1&page_size=1", headers=_auth_headers())
    assert response.status_code == 200
    payload = response.json()
    assert payload["page"] == 1
    assert payload["page_size"] == 1
    assert payload["total_items"] == 1
    assert len(payload["items"]) == 1
    assert payload["items"][0]["timestamp_ms"] == 200


def test_get_subprocess_detail() -> None:
    client = _create_client()
    response = client.get("/api/v1/subprocesses/sub_001", headers=_auth_headers())
    assert response.status_code == 200
    assert response.json()["subprocess_id"] == "sub_001"


def test_get_subprocess_detail_not_found() -> None:
    client = _create_client()
    response = client.get("/api/v1/subprocesses/not_found", headers=_auth_headers())
    assert response.status_code == 404


def test_list_data_items_with_pagination() -> None:
    client = _create_client()
    response = client.get("/api/v1/data-items?page=1&page_size=2", headers=_auth_headers())
    assert response.status_code == 200
    payload = response.json()
    assert payload["page"] == 1
    assert payload["page_size"] == 2
    assert payload["total_items"] == 2
    assert len(payload["items"]) == 2
    assert payload["items"][0]["timestamp_ms"] > payload["items"][1]["timestamp_ms"]


def test_get_data_item_detail() -> None:
    client = _create_client()
    response = client.get("/api/v1/data-items/data_001", headers=_auth_headers())
    assert response.status_code == 200
    assert response.json()["id"] == "data_001"


def test_get_data_item_detail_not_found() -> None:
    client = _create_client()
    response = client.get("/api/v1/data-items/not_found", headers=_auth_headers())
    assert response.status_code == 404


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
        "/api/v1/processes/proc_001/clone",
        headers=_auth_headers(),
        json={
            "parent_subprocess_ids": ["sub_001"],
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["process_id"].startswith("proc_001_copy")
    assert payload["status"] == "pending"
    node = payload["dataflow_state"]["nodes"][0]
    assert node["event_status"] == "Not Started"
    assert node["io_transformation_states"] == []


def test_clone_process_source_not_found() -> None:
    client = _create_client()
    response = client.post(
        "/api/v1/processes/proc_404/clone",
        headers=_auth_headers(),
        json={
            "parent_subprocess_ids": ["sub_001"],
        },
    )
    assert response.status_code == 404


def test_create_process_pending_with_input_data() -> None:
    client = _create_client()
    response = client.post(
        "/api/v1/processes",
        headers=_auth_headers(),
        json={
            "process_id": "proc_api_create_1",
            "software_version": "0.1.0",
            "input_dataset_id": "ds_api_feed",
            "dataflow": {
                "nodes": [
                    {"subprocess_id": "F1", "subprocess_type": "FetchFeedItems"},
                    {"subprocess_id": "E1", "subprocess_type": "EmbedData"},
                ],
                "edges": [{"from": "F1", "to": "E1"}],
            },
            "subprocess_config": {"F1": {}, "E1": {"model": "text-embedding-3-small"}},
            "input_data": [{"title": "A", "summary": "B", "url": "https://example.com"}],
            "start_immediately": False,
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["process_id"] == "proc_api_create_1"
    assert body["status"] == "pending"
    assert body["configuration"]["input_dataset_id"] == "ds_api_feed"
    assert "dataflow_state" in body
    assert "ds_api_feed" in _FAKE_DATA_ITEMS


def test_create_process_conflict_existing_id() -> None:
    client = _create_client()
    r1 = client.post(
        "/api/v1/processes",
        headers=_auth_headers(),
        json={
            "process_id": "proc_dup",
            "input_dataset_id": "ds_x",
            "dataflow": {
                "nodes": [{"subprocess_id": "F1", "subprocess_type": "FetchFeedItems"}],
                "edges": [],
            },
            "subprocess_config": {},
        },
    )
    assert r1.status_code == 201
    r2 = client.post(
        "/api/v1/processes",
        headers=_auth_headers(),
        json={
            "process_id": "proc_dup",
            "input_dataset_id": "ds_y",
            "dataflow": {
                "nodes": [{"subprocess_id": "F1", "subprocess_type": "FetchFeedItems"}],
                "edges": [],
            },
            "subprocess_config": {},
        },
    )
    assert r2.status_code == 409


def test_stop_process() -> None:
    client = _create_client()
    client.post(
        "/api/v1/processes",
        headers=_auth_headers(),
        json={
            "process_id": "proc_stop_me",
            "input_dataset_id": "ds_z",
            "dataflow": {
                "nodes": [{"subprocess_id": "F1", "subprocess_type": "FetchFeedItems"}],
                "edges": [],
            },
            "subprocess_config": {},
        },
    )
    r = client.post(
        "/api/v1/processes/proc_stop_me/stop",
        headers=_auth_headers(),
        json={"reason": "test"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "stopped"
    assert r.json().get("cancelled_reason") == "test"


def test_delete_process() -> None:
    client = _create_client()
    client.post(
        "/api/v1/processes",
        headers=_auth_headers(),
        json={
            "process_id": "proc_del",
            "input_dataset_id": "ds_z",
            "dataflow": {
                "nodes": [{"subprocess_id": "F1", "subprocess_type": "FetchFeedItems"}],
                "edges": [],
            },
            "subprocess_config": {},
        },
    )
    r = client.delete("/api/v1/processes/proc_del", headers=_auth_headers())
    assert r.status_code == 204
    assert "proc_del" not in _FAKE_PROCESS_DOCS


def test_clone_with_subprocess_config_override() -> None:
    client = _create_client()
    response = client.post(
        "/api/v1/processes/proc_001/clone",
        headers=_auth_headers(),
        json={
            "parent_subprocess_ids": ["sub_001"],
            "new_process_id": "proc_cloned_cfg",
            "subprocess_config": {"EmbedData1": {"model": "text-embedding-3-large"}},
        },
    )
    assert response.status_code == 201
    cfg = response.json()["configuration"]
    assert cfg["subprocess_config"]["EmbedData1"]["model"] == "text-embedding-3-large"
