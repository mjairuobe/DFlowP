"""Unit-Tests für Clustering_DBSCAN (ohne MongoDB)."""

from __future__ import annotations

import pytest

from dflowp.plugin_clustering_dbscan.clustering_dbscan import ClusteringDBSCAN
from dflowp_processruntime.datastructures.data import Data
from dflowp_processruntime.subprocesses.subprocess_context import SubprocessContext
from dflowp_processruntime.subprocesses.io_transformation_state import TransformationStatus


class FakeDataRepo:
    def __init__(self) -> None:
        self.inserted: list[dict] = []

    async def insert(self, data: dict) -> str:
        self.inserted.append(data)
        return "mongo_id"


class FakeDatasetRepo:
    def __init__(self) -> None:
        self.inserted: list[dict] = []

    async def insert(self, dataset: dict) -> str:
        self.inserted.append(dataset)
        return "mongo_id"


@pytest.mark.asyncio
async def test_dbscan_two_clusters() -> None:
    plugin = ClusteringDBSCAN()
    ctx = SubprocessContext(
        process_id="p1",
        subprocess_id="s1",
        subprocess_type="Clustering_DBSCAN",
        config={"eps": 0.5, "min_samples": 2, "metric": "euclidean"},
        input_data=[
            Data(data_id="a", content={"embedding": [0.0, 0.0]}, type="output"),
            Data(data_id="b", content={"embedding": [0.1, 0.0]}, type="output"),
            Data(data_id="c", content={"embedding": [10.0, 10.0]}, type="output"),
            Data(data_id="d", content={"embedding": [10.1, 10.0]}, type="output"),
        ],
    )
    data_repo = FakeDataRepo()
    ds_repo = FakeDatasetRepo()
    states = await plugin.run(
        context=ctx,
        data_repository=data_repo,
        dataset_repository=ds_repo,
    )

    assert len(states) == 1
    assert states[0].status == TransformationStatus.FINISHED
    assert states[0].quality == 1.0
    assert len(states[0].output_data_ids) == 2
    assert len(ds_repo.inserted) == 2
    assert len(data_repo.inserted) == 2
    labels = {d["cluster_label"] for d in ds_repo.inserted}
    assert labels == {0, 1}
    for d in ds_repo.inserted:
        assert d["type"] == "cluster"
        assert d["algorithm"] == "DBSCAN"
        assert len(d["data_ids"]) == 1
    for bd in data_repo.inserted:
        assert bd["content"]["cluster_bundle"] is True
        assert len(bd["content"]["embedding_data_ids"]) == 2


@pytest.mark.asyncio
async def test_all_noise_when_min_samples_not_met() -> None:
    plugin = ClusteringDBSCAN()
    ctx = SubprocessContext(
        process_id="p1",
        subprocess_id="s1",
        subprocess_type="Clustering_DBSCAN",
        config={"eps": 0.01, "min_samples": 10},
        input_data=[
            Data(data_id="a", content={"embedding": [0.0, 0.0]}, type="output"),
            Data(data_id="b", content={"embedding": [1.0, 1.0]}, type="output"),
        ],
    )
    data_repo = FakeDataRepo()
    ds_repo = FakeDatasetRepo()
    states = await plugin.run(
        context=ctx,
        data_repository=data_repo,
        dataset_repository=ds_repo,
    )

    assert states[0].quality == 0.1
    assert len(ds_repo.inserted) == 1
    assert len(data_repo.inserted) == 1
    assert ds_repo.inserted[0]["is_noise"] is True
    assert ds_repo.inserted[0]["cluster_label"] == -1
    assert set(data_repo.inserted[0]["content"]["embedding_data_ids"]) == {"a", "b"}
