"""Hilfen zum Anlegen von Input-Daten für API-erstellte Prozesse."""

from __future__ import annotations

from typing import Any

from dflowp_core.database.data_item_repository import DataItemRepository


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
        await data_item_repo.insert(
            {
                "id": data_id,
                "doc_type": "data",
                "content": content,
                "type": "input",
            }
        )
        data_ids.append(data_id)
    await data_item_repo.insert(
        {
            "id": dataset_id,
            "doc_type": "dataset",
            "data_ids": data_ids,
        }
    )
