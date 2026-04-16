"""Tests für Plugin-Microservice-APIs."""

import importlib.util
import pathlib

from fastapi.testclient import TestClient
import pytest


def _load_module(module_name: str, rel_path: str):
    path = pathlib.Path(__file__).resolve().parents[1] / rel_path
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_plugin_directories_exist() -> None:
    root = pathlib.Path(__file__).resolve().parents[1] / "dflowp"
    assert (root / "plugin_fetchfeeditems").is_dir()
    assert (root / "plugin_embeddata").is_dir()
    assert (root / "plugin_clustering_dbscan").is_dir()
    assert (root / "plugin_clustering_hdbscan").is_dir()
    assert (root / "plugin_topicprompting").is_dir()


def test_fetch_plugin_info_and_health() -> None:
    module = _load_module(
        "plugin_fetchfeeditems_app",
        "dflowp/plugin_fetchfeeditems/app.py",
    )
    client = TestClient(module.app)
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    info = client.get("/plugin/info")
    assert info.status_code == 200
    payload = info.json()
    assert payload["plugin_name"] == "FetchFeedItems"
    assert payload["status"] == "ready"


def test_embed_plugin_info_and_health() -> None:
    module = _load_module(
        "plugin_embeddata_app",
        "dflowp/plugin_embeddata/app.py",
    )
    client = TestClient(module.app)
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    info = client.get("/plugin/info")
    assert info.status_code == 200
    payload = info.json()
    assert payload["service_name"] == "plugin-embeddata"
    assert payload["plugin_name"] == "EmbedData"


def test_clustering_plugin_info_and_health() -> None:
    module = _load_module(
        "plugin_clustering_dbscan_app",
        "dflowp/plugin_clustering_dbscan/app.py",
    )
    client = TestClient(module.app)
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    info = client.get("/plugin/info")
    assert info.status_code == 200
    payload = info.json()
    assert payload["service_name"] == "plugin-clustering-dbscan"
    assert payload["plugin_name"] == "Clustering_DBSCAN"


def test_topic_prompting_plugin_info_and_health() -> None:
    module = _load_module(
        "plugin_topicprompting_app",
        "dflowp/plugin_topicprompting/app.py",
    )
    client = TestClient(module.app)
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    info = client.get("/plugin/info")
    assert info.status_code == 200
    payload = info.json()
    assert payload["service_name"] == "plugin-topicprompting"
    assert payload["plugin_name"] == "TopicPrompting"


def test_clustering_hdbscan_plugin_info_and_health() -> None:
    module = _load_module(
        "plugin_clustering_hdbscan_app",
        "dflowp/plugin_clustering_hdbscan/app.py",
    )
    client = TestClient(module.app)
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    info = client.get("/plugin/info")
    assert info.status_code == 200
    payload = info.json()
    assert payload["service_name"] == "plugin-clustering-hdbscan"
    assert payload["plugin_name"] == "Clustering_HDBSCAN"


@pytest.mark.asyncio
async def test_remote_plugin_resolve_requires_plugin_name() -> None:
    from dflowp_processruntime.plugins.remote_plugin import RemotePluginSubprocess
    from dflowp_processruntime.subprocesses.subprocess_context import SubprocessContext

    subprocess = RemotePluginSubprocess("FetchFeedItems")
    context = SubprocessContext(
        process_id="p1",
        subprocess_id="s1",
        subprocess_type="FetchFeedItems",
        config={"plugin_service_name": "fetchfeeditems"},
        input_data=[],
    )
    with pytest.raises(ValueError, match="muss 'plugin' enthalten"):
        await subprocess._resolve_service_url(context)
