"""Gemeinsame Logik für Data/Dataset in einem Endpunkt (doc_type bleibt in Mongo)."""

import uuid
from typing import Any

from fastapi import HTTPException, status

from dflowp.api.process_persist import (
    insert_data_item,
    insert_dataset,
    persist_input_dataset_rows,
)
from dflowp.api.schemas import DataDocumentCreateRequest
from dflowp_core.database.data_item_repository import DataItemRepository


async def create_data_document(
    request: DataDocumentCreateRequest,
    data_item_repo: DataItemRepository,
) -> dict[str, Any]:
    """Legt je nach ``doc_type`` ein Data- oder Dataset-Dokument an."""
    if request.doc_type == "data":
        data_id = request.id or f"data_{uuid.uuid4().hex[:12]}"
        if await data_item_repo.find_by_id(data_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"DataItem mit id '{data_id}' existiert bereits.",
            )
        if not request.content:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Für doc_type=data ist 'content' erforderlich.",
            )
        await insert_data_item(
            data_item_repo=data_item_repo,
            data_id=data_id,
            content=request.content,
            data_type=request.type or "input",
        )
        doc = await data_item_repo.find_by_id(data_id)
    else:
        if not request.id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Für doc_type=dataset ist 'id' (Dataset-ID) erforderlich.",
            )
        if await data_item_repo.find_by_id(request.id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"DataItem mit id '{request.id}' existiert bereits.",
            )
        has_ids = request.data_ids is not None and len(request.data_ids) > 0
        has_rows = request.rows is not None and len(request.rows) > 0
        if has_ids == has_rows:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Für doc_type=dataset: genau eines von data_ids oder rows muss gesetzt sein (nicht leer).",
            )
        if has_ids:
            resolved: list[str] = []
            for did in request.data_ids or []:
                d = await data_item_repo.find_by_id(did)
                if not d or d.get("doc_type") != "data":
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Data-Dokument '{did}' nicht gefunden oder kein doc_type=data.",
                    )
                resolved.append(did)
            await insert_dataset(
                data_item_repo=data_item_repo,
                dataset_id=request.id,
                data_ids=resolved,
            )
        else:
            await persist_input_dataset_rows(
                data_item_repo=data_item_repo,
                dataset_id=request.id,
                rows=request.rows or [],
            )
        doc = await data_item_repo.find_dataset_by_id(request.id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Dokument konnte nach dem Anlegen nicht gelesen werden.",
        )
    return doc
