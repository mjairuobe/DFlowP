"""EmbedData - Erstellt Embeddings mit OpenAI für konfigurierbare Artikelattribute."""

from typing import Any, Optional

from dflowp.core.subprocesses.subprocess import BaseSubprocess
from dflowp.core.subprocesses.subprocess_context import SubprocessContext
from dflowp.core.subprocesses.io_transformation_state import (
    IOTransformationState,
    TransformationStatus,
)
from dflowp.utils.document_naming import build_human_readable_document_id


class EmbedData(BaseSubprocess):
    """
    Erstellt Embeddings aus Artikel-Attributen (z.B. title, summary).
    Attribute werden in der Subprozess-Konfiguration angegeben (embedding_attributes).
    Nutzt OpenAI Embedding API.

    Konfigurierbare Parameter:
    - embedding_attributes: Liste der Artikel-Attribute für Embeddings (Standard: ["title", "summary"])
    - model: OpenAI Modell (Standard: "text-embedding-3-small")
    - openai_api_key: API-Schlüssel (Standard: OPENAI_API_KEY Umgebungsvariable)
    - text_template: F-String Template für Reproduzierbarkeit (Standard: "{title} {summary}")
      Beispiele: "{title}", "{title} {summary}", "{url} {title}"
    """

    DEFAULT_ATTRIBUTES = ["title", "summary"]
    DEFAULT_MODEL = "text-embedding-3-small"
    DEFAULT_TEXT_TEMPLATE = "{title} {summary}"  # F-String Template für konsistente Daten

    def __init__(self) -> None:
        super().__init__("EmbedData")

    async def run(
        self,
        context: SubprocessContext,
        event_emitter: Optional[Any] = None,
        state_updater: Optional[Any] = None,
        data_repository: Optional[Any] = None,
        dataset_repository: Optional[Any] = None,
    ) -> list[IOTransformationState]:
        if not data_repository:
            raise ValueError("data_repository erforderlich")

        attrs = context.config.get(
            "embedding_attributes", self.DEFAULT_ATTRIBUTES
        )
        model = context.config.get("model", self.DEFAULT_MODEL)
        openai_api_key = context.config.get("openai_api_key")
        text_template = context.config.get("text_template", self.DEFAULT_TEXT_TEMPLATE)

        results: list[IOTransformationState] = []

        for input_data in context.input_data:
            content = input_data.content
            text_parts = []
            for attr in attrs:
                val = content.get(attr)
                if val:
                    text_parts.append(str(val))

            text = " ".join(text_parts).strip() or "(leer)"
            if not text:
                text = "(leer)"

            try:
                embedding = await self._get_embedding(text, model, openai_api_key)
                data_id = build_human_readable_document_id(
                    domain="embedding",
                    document_type="data",
                )

                # Speichere nur das Template (die "Bauanleitung")
                # Der ursprüngliche Text kann jederzeit aus source_data_id + text_template rekonstruiert werden:
                # 1. Hole Input-Daten via source_data_id aus dem Repository
                # 2. Wende das Template "{title} {summary}" auf die Input-Daten an
                # Dies ermöglicht vollständige Reproduzierbarkeit ohne Speicherung von gekürzt/verarbeiteten Texten
                await data_repository.insert({
                    "data_id": data_id,
                    "content": {
                        "embedding": embedding,
                        "source_data_id": input_data.data_id,
                        "text_template": text_template,  # Die "Bauanleitung" - z.B. "{title} {summary}"
                    },
                    "type": "output",
                })
                results.append(
                    IOTransformationState(
                        input_data_id=input_data.data_id,
                        output_data_ids=[data_id],
                        status=TransformationStatus.FINISHED,
                        quality=1.0,
                    )
                )
            except Exception as e:
                results.append(
                    IOTransformationState(
                        input_data_id=input_data.data_id,
                        output_data_ids=[],
                        status=TransformationStatus.FAILED,
                        quality=0.0,
                    )
                )
                # Kein raise: einzelne Embedding-Fehler stoppen nicht die gesamte Verarbeitung

        return results

    async def _get_embedding(
        self, text: str, model: str, api_key: Optional[str] = None
    ) -> list[float]:
        """Holt Embedding von OpenAI."""
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise ImportError(
                "openai-Paket erforderlich: pip install openai"
            )

        import os
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise ValueError(
                "OPENAI_API_KEY in Config oder Umgebung erforderlich"
            )

        client = AsyncOpenAI(api_key=key)
        r = await client.embeddings.create(
            input=text[:8000],
            model=model,
        )
        return r.data[0].embedding
