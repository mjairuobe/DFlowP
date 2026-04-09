"""Unit-Tests für Clustering_HDBSCAN (ohne MongoDB)."""

from __future__ import annotations

import pytest

from dflowp.plugin_clustering_hdbscan.clustering_hdbscan import ClusteringHDBSCAN
from dflowp_processruntime.datastructures.data import Data
from dflowp_processruntime.subprocesses.subprocess_context import SubprocessContext
from dflowp_processruntime.subprocesses.io_transformation_state import TransformationStatus


class FakeDatasetRepo:
    def __init__(self) -> None:
        self.inserted: list[dict] = []

    async def insert(self, dataset: dict) -> str:
        self.inserted.append(dataset)
        return "mongo_id"


@pytest.mark.asyncio
async def test_hdbscan_two_clusters() -> None:
    plugin = ClusteringHDBSCAN()
    ctx = SubprocessContext(
        process_id="p1",
        subprocess_id="s1",
        subprocess_type="Clustering_HDBSCAN",
        config={
            "min_cluster_size": 2,
            "min_samples": 1,
            "metric": "euclidean",
        },
        input_data=[
            Data(data_id="a", content={"embedding": [0.0, 0.0]}, type="output"),
            Data(data_id="b", content={"embedding": [0.05, 0.0]}, type="output"),
            Data(data_id="c", content={"embedding": [50.0, 50.0]}, type="output"),
            Data(data_id="d", content={"embedding": [50.05, 50.0]}, type="output"),
        ],
    )
    repo = FakeDatasetRepo()
    states = await plugin.run(context=ctx, dataset_repository=repo)

    assert len(states) == 1
    assert states[0].status == TransformationStatus.FINISHED
    assert states[0].quality == 1.0
    assert len(states[0].output_data_ids) == 2
    assert len(repo.inserted) == 2
    labels = {d["cluster_label"] for d in repo.inserted}
    assert labels == {0, 1}
    for d in repo.inserted:
        assert d["type"] == "cluster"
        assert d["algorithm"] == "HDBSCAN"
        assert len(d["data_ids"]) == 2


@pytest.mark.asyncio
async def test_hdbscan_all_noise_when_min_cluster_size_not_met() -> None:
    plugin = ClusteringHDBSCAN()
    ctx = SubprocessContext(
        process_id="p1",
        subprocess_id="s1",
        subprocess_type="Clustering_HDBSCAN",
        config={"min_cluster_size": 10, "metric": "euclidean"},
        input_data=[
            Data(data_id="a", content={"embedding": [0.0, 0.0]}, type="output"),
            Data(data_id="b", content={"embedding": [1.0, 1.0]}, type="output"),
        ],
    )
    repo = FakeDatasetRepo()
    states = await plugin.run(context=ctx, dataset_repository=repo)

    assert states[0].quality == 0.1
    assert len(repo.inserted) == 1
    assert repo.inserted[0]["is_noise"] is True
    assert repo.inserted[0]["cluster_label"] == -1
    assert set(repo.inserted[0]["data_ids"]) == {"a", "b"}
