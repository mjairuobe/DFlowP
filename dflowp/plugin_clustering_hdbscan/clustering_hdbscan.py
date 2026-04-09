"""Clustering_HDBSCAN – gruppiert Embedding-Daten mit HDBSCAN (hdbscan-Paket)."""

from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Any, Optional

import numpy as np
from hdbscan import HDBSCAN

from dflowp_processruntime.subprocesses.subprocess import BaseSubprocess
from dflowp_processruntime.subprocesses.subprocess_context import SubprocessContext
from dflowp_processruntime.subprocesses.io_transformation_state import (
    IOTransformationState,
    TransformationStatus,
)
from pymongo.errors import DuplicateKeyError

from dflowp_core.utils.document_naming import build_human_readable_document_id
from dflowp_core.utils.logger import get_logger

logger = get_logger(__name__)


class ClusteringHDBSCAN(BaseSubprocess):
    """
    Erwartet Input-`Data` wie von EmbedData: `content.embedding` (Liste von float).

    Konfiguration (subprocess_config):
    - min_cluster_size: int (Standard: 5) – auch `min_samples` als Alias nutzbar
    - min_samples: optional int – Kern-Parameter von HDBSCAN (Default: wie Bibliothek)
    - cluster_selection_epsilon: float (Standard: 0.0)
    - eps: optional float – Alias für cluster_selection_epsilon (Nähe zu DBSCAN-Config)
    - metric: str (Standard: "euclidean")
    - cluster_selection_method: str (Standard: "eom")
    - algorithm: str (Standard: "best")
    - leaf_size: int (Standard: 40)
    - n_jobs: int oder None (Standard: None)
    """

    def __init__(self) -> None:
        super().__init__("Clustering_HDBSCAN")

    @staticmethod
    def _build_dataset_id(context: SubprocessContext) -> str:
        base = build_human_readable_document_id(
            domain="cluster",
            document_type="dataset",
        )
        return f"{base}_{context.process_id}_{context.subprocess_id}_{uuid.uuid4().hex[:10]}"

    async def run(
        self,
        context: SubprocessContext,
        event_emitter: Optional[Any] = None,
        state_updater: Optional[Any] = None,
        data_repository: Optional[Any] = None,
        dataset_repository: Optional[Any] = None,
    ) -> list[IOTransformationState]:
        if not dataset_repository:
            raise ValueError("dataset_repository erforderlich")

        src = f"[{context.process_id}][{context.subprocess_id}]"
        logger.info("%s Clustering_HDBSCAN gestartet", src)

        cfg = context.config
        min_cluster_size = int(
            cfg.get("min_cluster_size", cfg.get("min_samples", 5))
        )
        metric = str(cfg.get("metric", "euclidean"))
        cluster_selection_method = str(cfg.get("cluster_selection_method", "eom"))
        algorithm = str(cfg.get("algorithm", "best"))
        leaf_size = int(cfg.get("leaf_size", 40))
        n_jobs = cfg.get("n_jobs")
        cluster_selection_epsilon = float(
            cfg.get("cluster_selection_epsilon", cfg.get("eps", 0.0))
        )

        rows: list[tuple[str, list[float]]] = []
        for item in context.input_data:
            emb = item.content.get("embedding")
            if isinstance(emb, list) and emb and all(
                isinstance(x, (int, float)) for x in emb
            ):
                rows.append((item.data_id, [float(x) for x in emb]))
            else:
                logger.warning(
                    "%s Überspringe data_id=%s (kein gültiges embedding)",
                    src,
                    item.data_id,
                )

        if not rows:
            logger.warning("%s Keine gültigen Embeddings", src)
            return [
                IOTransformationState(
                    input_data_id=context.input_data[0].data_id
                    if context.input_data
                    else "none",
                    output_data_ids=[],
                    status=TransformationStatus.FINISHED,
                    quality=1.0,
                )
            ]

        data_ids = [r[0] for r in rows]
        X = np.asarray([r[1] for r in rows], dtype=np.float64)

        if X.shape[0] < min_cluster_size:
            logger.info(
                "%s Weniger Punkte (%d) als min_cluster_size (%d) → alles Noise",
                src,
                X.shape[0],
                min_cluster_size,
            )
            labels = np.full(X.shape[0], -1, dtype=int)
        else:
            hdb_kwargs: dict[str, Any] = {
                "min_cluster_size": min_cluster_size,
                "metric": metric,
                "cluster_selection_method": cluster_selection_method,
                "cluster_selection_epsilon": cluster_selection_epsilon,
                "algorithm": algorithm,
                "leaf_size": leaf_size,
            }
            if "min_samples" in cfg and cfg["min_samples"] is not None:
                hdb_kwargs["min_samples"] = int(cfg["min_samples"])
            if n_jobs is not None:
                hdb_kwargs["n_jobs"] = n_jobs

            clusterer = HDBSCAN(**hdb_kwargs)
            labels = clusterer.fit_predict(X)

        by_label: dict[int, list[str]] = defaultdict(list)
        for did, lab in zip(data_ids, labels.tolist()):
            by_label[int(lab)].append(did)

        output_dataset_ids: list[str] = []
        for lab in sorted(by_label.keys()):
            member_ids = by_label[lab]
            is_noise = lab == -1
            for attempt in range(1, 6):
                ds_id = self._build_dataset_id(context)
                try:
                    await dataset_repository.insert(
                        {
                            "dataset_id": ds_id,
                            "data_ids": member_ids,
                            "type": "cluster",
                            "cluster_label": lab,
                            "is_noise": is_noise,
                            "algorithm": "HDBSCAN",
                        }
                    )
                    output_dataset_ids.append(ds_id)
                    break
                except DuplicateKeyError:
                    logger.warning(
                        "%s DuplicateKey Dataset '%s' (%d/5)",
                        src,
                        ds_id,
                        attempt,
                    )
            else:
                raise RuntimeError("Konnte kein eindeutiges Cluster-Dataset anlegen")

        noise_only = len(by_label) == 1 and -1 in by_label
        quality = 0.1 if noise_only else 1.0

        inp_id = context.input_data[0].data_id if context.input_data else "batch"
        result = [
            IOTransformationState(
                input_data_id=inp_id,
                output_data_ids=output_dataset_ids,
                status=TransformationStatus.FINISHED,
                quality=quality,
            )
        ]
        logger.info(
            "%s Clustering_HDBSCAN fertig: %d Cluster/Noise-Datasets, quality=%s",
            src,
            len(output_dataset_ids),
            quality,
        )
        return result

    @staticmethod
    def get_plugin_info() -> dict[str, Any]:
        return {
            "name": "Clustering_HDBSCAN",
            "plugin_type": "clustering",
            "version": "1.0.0",
            "status": "ready",
        }
