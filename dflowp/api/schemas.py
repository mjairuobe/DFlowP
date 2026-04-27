"""Pydantic-Schemas für API-Requests."""

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator


class PipelineCloneRequest(BaseModel):
    """
    Pipeline klonen: optional neues dataflow-Definition-Dokument, optionale
    ``plugin_config``-Ergänzung (erzeugt neues plugin_configuration-Dokument), optional
    explizite Plugin-Worker-Knoten; sonst Auto-Logik (fehlgeschlagen/voll).
    """

    new_pipeline_id: Optional[str] = None
    dataflow_id: Optional[str] = Field(
        default=None,
        description="Anderes Dataflow-Dokument (ID) statt des Quelldatenflusses verwenden.",
    )
    plugin_config: Optional[dict[str, dict[str, Any]]] = Field(
        default=None,
        description="Pro plugin_worker_id überschreiben/mergen; betroffene Work und Nachfolger werden neu aufgesetzt.",
    )
    parent_plugin_worker_ids: Optional[list[str]] = Field(
        default=None,
        description="Wenn gesetzt: genau diese Plugin-Worker und alle transitiven Nachfolger neu. "
        "Wenn weggelassen: automatisch (fehlgeschlagene Worker, sonst vollständiger Re-Run).",
    )


class PipelineCreateRequest(BaseModel):
    """Pipeline anlegen; Primärschlüssel: ``pipeline_id``."""

    pipeline_id: str = Field(..., min_length=1)
    software_version: str = "0.1.0"
    input_dataset_id: str = Field(..., min_length=1)
    dataflow: dict[str, Any]
    plugin_config: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="Pro plugin_worker_id Parameter (Plugin-Konfiguration).",
    )
    input_data: Optional[list[dict[str, Any]]] = Field(
        default=None,
        description="Optional: Input-Zeilen als neues Dataset unter input_dataset_id.",
    )
    start_immediately: bool = Field(
        default=False,
        description="true: status=running; false: pending für Worker.",
    )


class ProcessStopRequest(BaseModel):
    """Optionaler Grund für Stopp."""

    reason: Optional[str] = None


class DataDocumentCreateRequest(BaseModel):
    """POST /data: entweder Data-Zeile oder Dataset (``doc_type`` in Mongo unverändert)."""

    doc_type: Literal["data", "dataset"] = "data"
    id: Optional[str] = None
    content: Optional[dict[str, Any]] = None
    type: str = Field(default="input", description="Nur für doc_type=data: Typ-Label.")
    data_ids: Optional[list[str]] = None
    rows: Optional[list[dict[str, Any]]] = None

    @model_validator(mode="after")
    def _check_dataset_id(self) -> "DataDocumentCreateRequest":
        if self.doc_type == "dataset" and not self.id:
            raise ValueError("Für doc_type=dataset ist id erforderlich.")
        if self.doc_type == "data" and self.data_ids is not None and self.rows is not None:
            raise ValueError("doc_type=data darf data_ids/rows nicht setzen (nur content).")
        return self


class DataflowCreateRequest(BaseModel):
    """Dataflow-Definition; nur graph-strukturierende Inhalte (kein reiner Pipeline-Name)."""

    dataflow_id: str = Field(..., min_length=1)
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)


class DataflowStateCreateRequest(BaseModel):
    """DataflowState-Dokument (Nodes inkl. io_transformation_states möglich)."""

    dataflow_state_id: str = Field(..., min_length=1)
    pipeline_id: str = Field(..., min_length=1)
    dataflow_id: str = Field(..., min_length=1)
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)


class PluginConfigurationCreateRequest(BaseModel):
    """Plugin-Konfiguration (kein in-place-Update; immer eigenes Dokument)."""

    plugin_configuration_id: str = Field(..., min_length=1)
    by_plugin_worker_id: dict[str, dict[str, Any]] = Field(default_factory=dict)


class EventCreateRequest(BaseModel):
    """Event manuell speichern (i. d. R. nutzt die Engine den EventService)."""

    pipeline_id: str = Field(..., min_length=1)
    plugin_worker_id: str = Field(..., min_length=1)
    event_type: str = Field(..., min_length=1)
    plugin_worker_replica_id: int = Field(default=1, ge=0)
    payload: Optional[dict[str, Any]] = None
