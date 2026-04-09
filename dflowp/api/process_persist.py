"""Hilfen zum Anlegen von Input-Daten für API-erstellte Prozesse."""

from __future__ import annotations

from typing import Any

from dflowp_core.database.data_item_repository import DataItemRepository


async def insert_data_item(
    *,
    data_item_repo: DataItemRepository,
    data_id: str,
    content: dict[str, Any],
    data_type: str = "input",
) -> str:
    """Legt ein Data-Dokument an. Gibt die logische `id` zurück."""
    await data_item_repo.insert(
        {
            "id": data_id,
            "doc_type": "data",
            "content": content,
            "type": data_type,
        }
    )
    return data_id


async def insert_dataset(
    *,
    data_item_repo: DataItemRepository,
    dataset_id: str,
    data_ids: list[str],
) -> str:
    """Legt ein Dataset-Dokument an."""
    await data_item_repo.insert(
        {
            "id": dataset_id,
            "doc_type": "dataset",
            "data_ids": data_ids,
        }
    )
    return dataset_id


async def persist_input_dataset_rows(
    *,
    data_item_repo: DataItemRepository,
    dataset_id: str,
    rows: list[dict[str, Any]],
) -> None:
    """
    Legt ein Dataset mit `id=dataset_id` und zugehörige Data-Dokumente an.
    Überschreibt ein bestehendes Dataset mit gleicher ID nicht (409 durch Aufrufer).
    """
    data_ids: list[str] = []
    for i, content in enumerate(rows):
        data_id = f"{dataset_id}_row_{i}"
        await insert_data_item(
            data_item_repo=data_item_repo,
            data_id=data_id,
            content=content,
            data_type="input",
        )
        data_ids.append(data_id)
    await insert_dataset(
        data_item_repo=data_item_repo,
        dataset_id=dataset_id,
        data_ids=data_ids,
    )
