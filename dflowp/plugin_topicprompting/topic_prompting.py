"""
TopicPrompting – Themenbildung pro Cluster-Gruppe mit OpenAI (strukturierter Output).

Kompatibel mit der aktuellen ProcessEngine (main): Vorgänger-Outputs werden flach
als Data-IDs übergeben (z. B. nur Embedding-IDs nach EmbedData). Zusätzlich werden
IDs aus dem Prozessdokument (output_data_ids des Clustering-Knotens) ausgewertet:

- Verweist eine ID auf ein **Dataset** (Cluster): `data_ids` = Embeddings pro Gruppe.
- Verweist eine ID auf **Data** (Embedding): wird zu einer synthetischen Ein-Gruppe
  zusammengefasst (mehrere solcher IDs → eine gemeinsame Prompt-Gruppe).
- Wenn aus dem Prozess nichts Nutzbares kommt: Fallback auf **input_data** (Embeddings).
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

from dflowp_processruntime.processes.process_configuration import ProcessConfiguration
from dflowp_processruntime.subprocesses.subprocess import BaseSubprocess
from dflowp_processruntime.subprocesses.subprocess_context import SubprocessContext
from dflowp_processruntime.subprocesses.io_transformation_state import (
    IOTransformationState,
    TransformationStatus,
)

from dflowp_core.database.process_repository import ProcessRepository
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
    kept_article_numbers: list[int] = Field(
        ...,
        description="Eins-basierte Nummern der Artikel, die zum gemeinsamen Thema passen",
    )
    topic_name: str = Field(..., description="Kurzer Themenname (3–5 Worte)")
    topic_description: str = Field(..., description="Kurze Beschreibung des Themas")


class TopicPrompting(BaseSubprocess):
    """
    Konfiguration (subprocess_config):
    - cluster_subprocess_id: ID des Clustering-Knotens, Pflicht wenn mehrere Vorgänger.
      Bei nur EmbedData als Vorgänger entfällt die Clustering-Liste; Gruppierung siehe oben.
    - model: OpenAI-Chatmodell (Standard: gpt-4o-mini)
    - openai_api_key: optional
    - prompt_template: optional, Platzhalter {Input}
    - article_title_field / article_description_field: Standard title / summary
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

    def _resolve_cluster_source_subprocess_id(
        self,
        *,
        configuration: ProcessConfiguration,
        current_subprocess_id: str,
        explicit: str | None,
    ) -> str:
        preds: list[str] = []
        for e in configuration.dataflow.edges:
            if e.to_node == current_subprocess_id:
                preds.append(e.from_node)
        if explicit:
            if explicit not in preds:
                raise ValueError(
                    f"cluster_subprocess_id '{explicit}' ist kein Vorgänger von "
                    f"{current_subprocess_id} laut Dataflow."
                )
            return explicit
        if len(preds) == 1:
            return preds[0]
        if not preds:
            raise ValueError(
                "TopicPrompting: Kein Vorgänger-Knoten im Dataflow für diesen Subprozess."
            )
        raise ValueError(
            "TopicPrompting: subprocess_config['cluster_subprocess_id'] setzen "
            "(mehrere Vorgänger am Dataflow-Knoten)."
        )

    async def _cluster_dataset_ids_from_process(
        self,
        *,
        process_repo: ProcessRepository,
        process_id: str,
        cluster_subprocess_id: str,
    ) -> list[str]:
        proc = await process_repo.find_by_id(process_id)
        if not proc:
            raise ValueError(f"Prozess '{process_id}' nicht gefunden")
        seen: set[str] = set()
        out: list[str] = []
        for node in proc.get("dataflow_state", {}).get("nodes", []) or []:
            if node.get("subprocess_id") != cluster_subprocess_id:
                continue
            for s in node.get("io_transformation_states", []) or []:
                for oid in s.get("output_data_ids") or []:
                    if oid not in seen:
                        seen.add(oid)
                        out.append(oid)
        return out

    async def _resolve_cluster_batch(
        self,
        *,
        data_repository: Any,
        dataset_repository: Any,
        output_id: str,
    ) -> tuple[list[str], str | None, Any] | None:
        """
        Eine ID aus dem Vorgänger-Output: entweder Cluster-Dataset (mehrere Embeddings)
        oder einzelnes Embedding-Data.
        """
        ds_doc = await dataset_repository.find_by_id(output_id)
        if ds_doc and ds_doc.get("doc_type") == "dataset":
            emb_ids = list(ds_doc.get("data_ids") or [])
            if not emb_ids:
                return None
            return (emb_ids, output_id, ds_doc.get("cluster_label"))
        ddoc = await data_repository.find_by_id(output_id)
        if ddoc and ddoc.get("doc_type") == "data":
            content = ddoc.get("content") or {}
            emb = content.get("embedding")
            if isinstance(emb, list) and emb:
                return ([output_id], output_id, None)
        return None

    async def _batches_from_input_embeddings(
        self,
        *,
        context: SubprocessContext,
        data_repository: Any,
    ) -> list[tuple[list[str], str | None, Any]]:
        """Fallback: alle Embedding-Zeilen aus input_data zu einer Gruppe."""
        emb_ids: list[str] = []
        for item in context.input_data:
            doc = await data_repository.find_by_id(item.data_id)
            if not doc:
                continue
            c = doc.get("content") or {}
            if isinstance(c.get("embedding"), list) and c.get("embedding"):
                emb_ids.append(item.data_id)
        if not emb_ids:
            return []
        return [(emb_ids, "input_batch", None)]

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
        cfg = context.config
        model = str(cfg.get("model", self.DEFAULT_MODEL))
        api_key = cfg.get("openai_api_key")
        prompt_template = str(cfg.get("prompt_template", DEFAULT_PROMPT_TEMPLATE))
        title_field = str(cfg.get("article_title_field", "title"))
        desc_field = str(cfg.get("article_description_field", "summary"))
        explicit_cluster = cfg.get("cluster_subprocess_id")
        if explicit_cluster is not None:
            explicit_cluster = str(explicit_cluster)

        process_repo = ProcessRepository()
        proc = await process_repo.find_by_id(context.process_id)
        if not proc or not proc.get("configuration"):
            raise ValueError("TopicPrompting: Prozess oder configuration fehlt")
        configuration = ProcessConfiguration.from_dict(proc["configuration"])
        cluster_sid = self._resolve_cluster_source_subprocess_id(
            configuration=configuration,
            current_subprocess_id=context.subprocess_id,
            explicit=explicit_cluster,
        )
        cluster_output_ids = await self._cluster_dataset_ids_from_process(
            process_repo=process_repo,
            process_id=context.process_id,
            cluster_subprocess_id=cluster_sid,
        )
        batches: list[tuple[list[str], str | None, Any]] = []
        for oid in cluster_output_ids:
            resolved = await self._resolve_cluster_batch(
                data_repository=data_repository,
                dataset_repository=dataset_repository,
                output_id=oid,
            )
            if resolved:
                batches.append(resolved)
        if not batches:
            batches = await self._batches_from_input_embeddings(
                context=context,
                data_repository=data_repository,
            )
            if batches:
                logger.info(
                    "%s TopicPrompting: Fallback input_data (%d Embeddings → 1 Gruppe)",
                    src,
                    len(batches[0][0]),
                )

        logger.info(
            "%s TopicPrompting: %d Gruppe(n) aus Vorgänger %s (IDs=%d)",
            src,
            len(batches),
            cluster_sid,
            len(cluster_output_ids),
        )

        client = self._default_openai_client(api_key)
        topic_dataset_ids: list[str] = []
        inp_ref = context.input_data[0].data_id if context.input_data else "batch"

        for emb_ids, ds_id, cluster_label in batches:
            articles: list[dict[str, Any]] = []
            for emb_id in emb_ids:
                emb = await data_repository.find_by_id(emb_id)
                if not emb:
                    continue
                content = emb.get("content") or {}
                src_article_id = content.get("source_data_id")
                if not src_article_id:
                    continue
                art_doc = await data_repository.find_by_id(src_article_id)
                if not art_doc:
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
                logger.warning("%s Cluster %s: keine Artikel auflösbar", src, ds_id)
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
                logger.error("%s OpenAI-Fehler für Gruppe %s: %s", src, ds_id, exc)
                continue

            filtered_ids: list[str] = []
            for n in kept_nums:
                if 1 <= n <= len(articles):
                    did = articles[n - 1]["data_id"]
                    if did not in filtered_ids:
                        filtered_ids.append(did)

            kept_titles = [articles[n - 1]["title"] for n in kept_nums if 1 <= n <= len(articles)]
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
                            "source_cluster_dataset_id": ds_id,
                            "cluster_label": cluster_label,
                            "algorithm": "TopicPrompting",
                        }
                    )
                    topic_ds_id = candidate
                    break
                except DuplicateKeyError:
                    logger.warning("%s DuplicateKey topic dataset (%d/5)", src, attempt)
            else:
                raise RuntimeError("Konnte kein Topic-Dataset anlegen")

            topic_dataset_ids.append(topic_ds_id)
            logger.info(
                "%s Topic für Gruppe %s: %s (%d Artikel)",
                src,
                ds_id,
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
                logger.warning("%s DuplicateKey wrapper (%d/5)", src, attempt)
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
