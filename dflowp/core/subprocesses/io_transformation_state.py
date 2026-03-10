"""Status der Input-Output-Transformation und Qualitätsbewertung."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class TransformationStatus(str, Enum):
    """Status einer IO-Transformation."""

    NOT_STARTED = "Not Started"
    IN_PROGRESS = "In Progress"
    FINISHED = "Finished"
    FAILED = "Failed"


class IOTransformationState(BaseModel):
    """
    Abbildung eines Input-Datensatzes zu Output-Datensätzen (1-N).
    Enthält Status und Qualitätsbewertung der Transformation.
    """

    input_data_id: str = Field(..., description="ID des Input-Datensatzes")
    output_data_ids: list[str] = Field(default_factory=list, description="IDs der Output-Datensätze (1-N)")
    status: TransformationStatus = Field(default=TransformationStatus.NOT_STARTED)
    quality: Optional[float] = Field(default=None, description="Qualität der Transformation (0.0-1.0)")

    def to_dict(self) -> dict:
        """Konvertiert zu Dict (z.B. für JSON)."""
        return {
            "input_data_id": self.input_data_id,
            "output_data_ids": self.output_data_ids,
            "status": self.status.value,
            "quality": self.quality,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "IOTransformationState":
        """Erstellt aus Dict."""
        status = d.get("status", "Not Started")
        if isinstance(status, str):
            status = TransformationStatus(status)
        return cls(
            input_data_id=d["input_data_id"],
            output_data_ids=d.get("output_data_ids", []),
            status=status,
            quality=d.get("quality"),
        )
