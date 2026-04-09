"""TopicPrompting – pro Cluster: Artikel via Embedding→source_data_id, OpenAI strukturierter JSON-Output."""

from __future__ import annotations

import uuid
from typing import Any, Optional

from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

from dflowp_processruntime.subprocesses.subprocess import BaseSubprocess
from dflowp_processruntime.subprocesses.subprocess_context import SubprocessContext
from dflowp_processruntime.subprocesses.io_transformation_state import (
    IOTransformationState,
    TransformationStatus,
)

from dflowp_core.utils.document_naming import build_human_readable_document_id
from dflowp_core.utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_PROMPT_TEMPLATE = """Diese Liste von Zeitungsartikel sollen zusammen ein Thema ergeben.
Bitte sortiere alle Artikel aus der Liste heraus, die nicht in ein Thema zusammen passen.

Bitte generiere einen Namen für das Thema. Das Thema soll in drei bis fünf Worten beschreibbar sein.

Themen könnten ungefähr so spezifisch sein: Internet-Sperren im Iran, Trump gewinnt die US-Wahl oder Erdbeben in Tahiti. Also in drei bis fünf Worten beschreibbar.

Wenn du weniger Worte brauchst, um einen Artikel zu beschreiben, dann passt er wahrscheinlich nicht zum Thema und ist zu Allgemein. Kein Artikel darf in unter drei Worten als Titel beschreibbar sein.

Entferne die Artikel aus dieser Gruppe, wenn sie nicht in ein Thema passen.
Bitte erhalte nur die Artikel in der Gruppe, die zusammen in ein Thema passen.

Zu jedem Artikel gebe ich dir Titel und Beschreibung. Bitte gebe mir als strukturierten JSON-Output nur die Nummern der Artikel, die im Thema bleiben, sowie das gemeinsame Thema plus Beschreibung.

Hier eine durchnummerierte Liste mit allen Artikeln:
{Input}
"""


class TopicLLMStructured(BaseModel):
    """Antwortschema für OpenAI structured output."""

    kept_article_numbers: list[int] = Field(
        ...,
        description="Eins-basierte Nummern der Artikel, die zum gemeinsamen Thema passen",
    )
    topic_name: str = Field(..., description="Kurzer Themenname (3–5 Worte)")
    topic_description: str = Field(..., description="Kurze Beschreibung des Themas")


class TopicPrompting(BaseSubprocess):
    """
    Erwartet pro Input-`Data` ein Cluster-Dataset-Kontext (von ProcessEngine aufbereitet):
    `content.embedding_data_ids`, `content.cluster_dataset_id`, optional `cluster_label`.

    Lädt Embeddings, folgt `source_data_id` zu Feed-Artikeln, ruft OpenAI (strukturierter Output) auf.
    Output: ein Dataset pro Cluster mit Topic-Metadaten und gefilterten Artikel-IDs.
    """

    DEFAULT_MODEL = "gpt-4o-mini"

    def __init__(self) -> None:
        super().__init__("TopicPrompting")

    @staticmethod
    def _build_topic_dataset_id(context: SubprocessContext) -> str:
        base = build_human_readable_document_id(
            domain="topic",
            document_type="dataset",
        )
        return f"{base}_{context.process_id}_{context.subprocess_id}_{uuid.uuid4().hex[:10]}"

    @staticmethod
    def _default_openai_client(api_key: str | None) -> AsyncOpenAI:
        import os

        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise ValueError("OPENAI_API_KEY erforderlich (Config oder Umgebung)")
        return AsyncOpenAI(api_key=key)

    async def run(
        self,
        context: SubprocessContext,
        event_emitter: Optional[Any] = None,
        state_updater: Optional[Any] = None,
        data_repository: Optional[Any] = None,
        dataset_repository: Optional[Any] = None,
    ) -> list[IOTransformationState]:
        if not data_repository or not dataset_repository:
            raise ValueError("data_repository und dataset_repository erforderlich")

        src = f"[{context.process_id}][{context.subprocess_id}]"
        logger.info("%s TopicPrompting gestartet (%d Cluster-Inputs)", src, len(context.input_data))

        cfg = context.config
        model = str(cfg.get("model", self.DEFAULT_MODEL))
        api_key = cfg.get("openai_api_key")
        prompt_template = str(cfg.get("prompt_template", DEFAULT_PROMPT_TEMPLATE))
        title_field = str(cfg.get("article_title_field", "title"))
        desc_field = str(cfg.get("article_description_field", "summary"))

        client = self._default_openai_client(api_key)

        topic_dataset_ids: list[str] = []
        inp_ref = "batch"

        for item in context.input_data:
            cluster_ds_id = item.content.get("cluster_dataset_id") or item.data_id
            emb_ids: list[str] = list(item.content.get("embedding_data_ids") or [])
            cluster_label = item.content.get("cluster_label")

            if inp_ref == "batch":
                inp_ref = item.data_id

            if not emb_ids:
                logger.warning("%s Leerer Cluster %s – übersprungen", src, cluster_ds_id)
                continue

            articles: list[dict[str, Any]] = []
            for emb_id in emb_ids:
                emb = await data_repository.find_by_id(emb_id)
                if not emb:
                    logger.warning("%s Embedding %s nicht gefunden", src, emb_id)
                    continue
                content = emb.get("content") or {}
                src_article_id = content.get("source_data_id")
                if not src_article_id:
                    logger.warning("%s Embedding %s ohne source_data_id", src, emb_id)
                    continue
                art_doc = await data_repository.find_by_id(src_article_id)
                if not art_doc:
                    logger.warning("%s Artikel %s nicht gefunden", src, src_article_id)
                    continue
                ac = art_doc.get("content") or {}
                articles.append(
                    {
                        "data_id": art_doc["data_id"],
                        "title": str(ac.get(title_field, "") or ""),
                        "description": str(ac.get(desc_field, "") or ""),
                    }
                )

            if not articles:
                logger.warning("%s Cluster %s: keine Artikel auflösbar", src, cluster_ds_id)
                continue

            numbered_lines = []
            for i, a in enumerate(articles, start=1):
                numbered_lines.append(
                    f"{i}. Titel: {a['title']}\n   Beschreibung: {a['description']}"
                )
            input_block = "\n\n".join(numbered_lines)

            if "{Input}" in prompt_template:
                user_prompt = prompt_template.replace("{Input}", input_block)
            else:
                user_prompt = prompt_template + "\n\n" + input_block

            try:
                completion = await client.chat.completions.parse(
                    model=model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "Du hilfst bei der Themenbildung für Gruppen von "
                                "Zeitungsartikeln. Antworte nur im vorgegebenen JSON-Schema."
                            ),
                        },
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format=TopicLLMStructured,
                )
                parsed = completion.choices[0].message.parsed
                if parsed is None:
                    raise RuntimeError("OpenAI lieferte kein geparstes Ergebnis")
                kept_nums = [n for n in parsed.kept_article_numbers if isinstance(n, int)]
                topic_name = (parsed.topic_name or "").strip()
                topic_description = (parsed.topic_description or "").strip()
            except Exception as exc:
                logger.error("%s OpenAI-Fehler für Cluster %s: %s", src, cluster_ds_id, exc)
                continue

            # 1-basierte Indizes → data_ids
            filtered_ids: list[str] = []
            for n in kept_nums:
                if 1 <= n <= len(articles):
                    did = articles[n - 1]["data_id"]
                    if did not in filtered_ids:
                        filtered_ids.append(did)

            kept_titles = []
            for n in kept_nums:
                if 1 <= n <= len(articles):
                    kept_titles.append(articles[n - 1]["title"])
            titlelist_str = "\n".join(f"- {t}" for t in kept_titles if t)

            topic_ds_id: str | None = None
            for attempt in range(1, 6):
                candidate = self._build_topic_dataset_id(context)
                try:
                    await dataset_repository.insert(
                        {
                            "dataset_id": candidate,
                            "data_ids": filtered_ids,
                            "type": "topic",
                            "topic": topic_name,
                            "description": topic_description,
                            "titlelist_str": titlelist_str,
                            "source_cluster_dataset_id": cluster_ds_id,
                            "cluster_label": cluster_label,
                            "algorithm": "TopicPrompting",
                        }
                    )
                    topic_ds_id = candidate
                    break
                except DuplicateKeyError:
                    logger.warning("%s DuplicateKey topic dataset %s (%d/5)", src, candidate, attempt)
            else:
                raise RuntimeError("Konnte kein Topic-Dataset anlegen")

            topic_dataset_ids.append(topic_ds_id)
            logger.info(
                "%s Topic für Cluster %s: %s (%d Artikel)",
                src,
                cluster_ds_id,
                topic_name[:80],
                len(filtered_ids),
            )

        if not topic_dataset_ids:
            return [
                IOTransformationState(
                    input_data_id=inp_ref,
                    output_data_ids=[],
                    status=TransformationStatus.FINISHED,
                    quality=0.2,
                )
            ]

        wrapper_id: str | None = None
        for attempt in range(1, 6):
            candidate = self._build_topic_dataset_id(context)
            try:
                await dataset_repository.insert(
                    {
                        "dataset_id": candidate,
                        "data_ids": topic_dataset_ids,
                        "type": "topic_collection",
                        "algorithm": "TopicPrompting",
                        "child_count": len(topic_dataset_ids),
                    }
                )
                wrapper_id = candidate
                break
            except DuplicateKeyError:
                logger.warning("%s DuplicateKey wrapper %s (%d/5)", src, candidate, attempt)
        else:
            raise RuntimeError("Konnte kein Topic-Collection-Dataset anlegen")

        return [
            IOTransformationState(
                input_data_id=inp_ref,
                output_data_ids=[wrapper_id] if wrapper_id else [],
                status=TransformationStatus.FINISHED,
                quality=1.0,
            )
        ]

    @staticmethod
    def get_plugin_info() -> dict[str, Any]:
        return {
            "name": "TopicPrompting",
            "plugin_type": "llm_topic",
            "version": "1.0.0",
            "status": "ready",
        }
