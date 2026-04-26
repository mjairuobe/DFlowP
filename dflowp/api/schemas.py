"""Pydantic-Schemas für API-Requests."""

from typing import Any, Optional

from pydantic import BaseModel, Field


class ProcessCloneRequest(BaseModel):
    """Request-Body zum Klonen eines Prozesses mit partieller Re-Execution."""

    parent_subprocess_ids: list[str] = Field(default_factory=list, min_length=1)
    new_process_id: Optional[str] = None
    subprocess_config: Optional[dict[str, dict[str, Any]]] = Field(
        default=None,
        description="Optional: Subprozess-Konfiguration überschreiben/ergänzen (pro subprocess_id).",
    )


class ProcessCreateRequest(BaseModel):
    """Prozess anlegen: Konfiguration wie processconfig + optional Input-Zeilen."""

    process_id: str = Field(..., min_length=1)
    software_version: str = "0.1.0"
    input_dataset_id: str = Field(..., min_length=1)
    dataflow: dict[str, Any]
    subprocess_config: dict[str, dict[str, Any]] = Field(default_factory=dict)
    input_data: Optional[list[dict[str, Any]]] = Field(
        default=None,
        description="Optional: Liste von Input-Data-Objekten (content), wird als Dataset unter input_dataset_id gespeichert.",
    )
    start_immediately: bool = Field(
        default=False,
        description="Wenn true: status=running wie bei engine.start_process; sonst pending für Worker-Polling.",
    )


class ProcessStopRequest(BaseModel):
    """Optionaler Grund für Stopp."""

    reason: Optional[str] = None


class DataItemCreateRequest(BaseModel):
    """Einzelnes Data-Dokument (data_items, doc_type=data)."""

    id: Optional[str] = Field(
        default=None,
        description="Optionale feste ID; sonst wird eine UUID vergeben.",
    )
    content: dict[str, Any] = Field(..., description="Nutzdaten (z. B. Feed-Zeile für FetchFeedItems).")
    type: str = Field(default="input", description="Typ-Label (z. B. input, output).")


class PipelineCreateRequest(BaseModel):
    """Pipeline anlegen (entspricht Prozess; Primärschlüssel: ``pipeline_id``)."""

    pipeline_id: str = Field(..., min_length=1)
    software_version: str = "0.1.0"
    input_dataset_id: str = Field(..., min_length=1)
    dataflow: dict[str, Any]
    plugin_config: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="Pro plugin_worker_id Parameter (vormals subprocess_config).",
    )
    input_data: Optional[list[dict[str, Any]]] = Field(
        default=None,
        description="Optional: Input-Zeilen als neues Dataset unter input_dataset_id.",
    )
    start_immediately: bool = Field(
        default=False,
        description="true: status=running; false: pending für Worker.",
    )


class DataflowCreateRequest(BaseModel):
    """Neues Dataflow-Definition-Dokument."""

    dataflow_id: str = Field(..., min_length=1)
    name: str = "dataflow"
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)


class DataflowStateCreateRequest(BaseModel):
    """Neues DataflowState-Dokument (Nodes inkl. io_transformation_states möglich)."""

    dataflow_state_id: str = Field(..., min_length=1)
    pipeline_id: str = Field(..., min_length=1)
    dataflow_id: str = Field(..., min_length=1)
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)


class PluginConfigurationCreateRequest(BaseModel):
    """Neue Plugin-Konfiguration (kein Update bestehender Id – immer neues Dokument)."""

    plugin_configuration_id: str = Field(..., min_length=1)
    by_plugin_worker_id: dict[str, dict[str, Any]] = Field(default_factory=dict)


class EventCreateRequest(BaseModel):
    """Event persistieren (i. d. R. nutzt die Engine den EventService; für Integrationstests / Admin)."""

    pipeline_id: str = Field(..., min_length=1)
    plugin_worker_id: str = Field(..., min_length=1)
    event_type: str = Field(..., min_length=1)
    payload: Optional[dict[str, Any]] = None


class DatasetCreateRequest(BaseModel):
    """Dataset mit referenzierten Data-IDs oder eingebetteten Zeilen."""

    id: str = Field(..., min_length=1, description="Eindeutige Dataset-ID.")
    data_ids: Optional[list[str]] = Field(
        default=None,
        description="Bestehende Data-IDs; alternativ rows setzen.",
    )
    rows: Optional[list[dict[str, Any]]] = Field(
        default=None,
        description="Neue Data-Zeilen (pro Zeile ein Data-Dokument); IDs werden automatisch vergeben.",
    )

