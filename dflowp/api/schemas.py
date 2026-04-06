"""Pydantic-Schemas für API-Requests."""

from typing import Optional

from pydantic import BaseModel, Field


class ProcessCloneRequest(BaseModel):
    """Request-Body zum Klonen eines Prozesses mit partieller Re-Execution."""

    parent_subprocess_ids: list[str] = Field(default_factory=list, min_length=1)
    new_process_id: Optional[str] = None

