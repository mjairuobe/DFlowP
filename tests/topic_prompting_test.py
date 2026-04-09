"""Tests für TopicPrompting (ohne echte OpenAI-Calls)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dflowp.plugin_topic_prompting.topic_prompting import TopicLLMStructured, TopicPrompting
from dflowp_processruntime.datastructures.data import Data
from dflowp_processruntime.subprocesses.subprocess_context import SubprocessContext
from dflowp_processruntime.subprocesses.io_transformation_state import TransformationStatus


class FakeDataRepo:
    def __init__(self) -> None:
        self.docs: dict[str, dict] = {}

    async def find_by_id(self, data_id: str) -> dict | None:
        return self.docs.get(data_id)


class FakeDatasetRepo:
    def __init__(self) -> None:
        self.inserted: list[dict] = []

    async def insert(self, dataset: dict) -> str:
        self.inserted.append(dataset)
        did = dataset.get("dataset_id", "ds")
        return did


@pytest.mark.asyncio
async def test_topic_prompting_creates_wrapper_and_topic_datasets() -> None:
    data_repo = FakeDataRepo()
    data_repo.docs["emb1"] = {
        "data_id": "emb1",
        "content": {"embedding": [0.1], "source_data_id": "art1"},
    }
    data_repo.docs["art1"] = {
        "data_id": "art1",
        "content": {"title": "A", "summary": "Sa"},
    }

    ds_repo = FakeDatasetRepo()

    ctx = SubprocessContext(
        process_id="p1",
        subprocess_id="T1",
        subprocess_type="TopicPrompting",
        config={"model": "gpt-4o-mini"},
        input_data=[
            Data(
                data_id="bundle_x",
                content={
                    "cluster_bundle": True,
                    "cluster_dataset_id": "cluster_ds_x",
                    "embedding_data_ids": ["emb1"],
                    "cluster_label": 0,
                },
                type="cluster_bundle",
            )
        ],
    )

    parsed = TopicLLMStructured(
        kept_article_numbers=[1],
        topic_name="Test Thema hier",
        topic_description="Beschreibung",
    )
    mock_completion = MagicMock()
    mock_completion.choices = [MagicMock(message=MagicMock(parsed=parsed))]

    mock_client = MagicMock()
    mock_client.chat.completions.parse = AsyncMock(return_value=mock_completion)

    with patch.object(
        TopicPrompting,
        "_default_openai_client",
        return_value=mock_client,
    ):
        plugin = TopicPrompting()
        states = await plugin.run(
            context=ctx,
            data_repository=data_repo,
            dataset_repository=ds_repo,
        )

    assert len(states) == 1
    assert states[0].status == TransformationStatus.FINISHED
    assert len(states[0].output_data_ids) == 1

    topic_ds = [d for d in ds_repo.inserted if d.get("type") == "topic"]
    wrap = [d for d in ds_repo.inserted if d.get("type") == "topic_collection"]
    assert len(topic_ds) == 1
    assert topic_ds[0]["topic"] == "Test Thema hier"
    assert topic_ds[0]["data_ids"] == ["art1"]
    assert topic_ds[0]["source_cluster_dataset_id"] == "cluster_ds_x"
    assert "A" in topic_ds[0]["titlelist_str"]
    assert len(wrap) == 1
    assert wrap[0]["data_ids"] == [topic_ds[0]["dataset_id"]]
