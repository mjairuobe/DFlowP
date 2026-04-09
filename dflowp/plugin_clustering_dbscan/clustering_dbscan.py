"""Clustering_DBSCAN – gruppiert Embedding-Daten mit scikit-learn DBSCAN."""

from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Any, Optional

import numpy as np
from sklearn.cluster import DBSCAN

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


class ClusteringDBSCAN(BaseSubprocess):
    """
    Erwartet Input-`Data` wie von EmbedData: `content.embedding` (Liste von float).

    Konfiguration (subprocess_config):
    - eps: float (Standard: 0.5)
    - min_samples: int (Standard: 5)
    - metric: str (Standard: "euclidean"), siehe sklearn DBSCAN
    - algorithm: str (Standard: "auto")
    - leaf_size: int (Standard: 30)
    - n_jobs: int oder None (Standard: None)
    - p: float (Standard: 2.0, für Minkowski)
    """

    def __init__(self) -> None:
        super().__init__("Clustering_DBSCAN")

    @staticmethod
    def _build_dataset_id(context: SubprocessContext) -> str:
        base = build_human_readable_document_id(
            domain="cluster",
            document_type="dataset",
        )
        return f"{base}_{context.process_id}_{context.subprocess_id}_{uuid.uuid4().hex[:10]}"

    @staticmethod
    def _build_cluster_bundle_data_id(context: SubprocessContext) -> str:
        base = build_human_readable_document_id(
            domain="cluster",
            document_type="data",
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
        if not data_repository or not dataset_repository:
            raise ValueError("data_repository und dataset_repository erforderlich")

        src = f"[{context.process_id}][{context.subprocess_id}]"
        logger.info("%s Clustering_DBSCAN gestartet", src)

        cfg = context.config
        eps = float(cfg.get("eps", 0.5))
        min_samples = int(cfg.get("min_samples", 5))
        metric = str(cfg.get("metric", "euclidean"))
        algorithm = str(cfg.get("algorithm", "auto"))
        leaf_size = int(cfg.get("leaf_size", 30))
        n_jobs = cfg.get("n_jobs")
        p = float(cfg.get("p", 2.0))

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

        if X.shape[0] < min_samples:
            logger.info(
                "%s Weniger Punkte (%d) als min_samples (%d) → alles Noise",
                src,
                X.shape[0],
                min_samples,
            )
            labels = np.full(X.shape[0], -1, dtype=int)
        else:
            db = DBSCAN(
                eps=eps,
                min_samples=min_samples,
                metric=metric,
                algorithm=algorithm,
                leaf_size=leaf_size,
                n_jobs=n_jobs,
                p=p,
            )
            labels = db.fit_predict(X)

        by_label: dict[int, list[str]] = defaultdict(list)
        for did, lab in zip(data_ids, labels.tolist()):
            by_label[int(lab)].append(did)

        # Pro Cluster: ein Data-Dokument (cluster_bundle) mit embedding_data_ids + ein Dataset
        # mit data_ids=[bundle_id]. Die ProcessEngine expandiert das Dataset zu genau einem
        # Data-Input für Nachfolger (z. B. TopicPrompting) – ohne Sonderlogik in der Engine.
        output_dataset_ids: list[str] = []
        for lab in sorted(by_label.keys()):
            member_ids = by_label[lab]
            is_noise = lab == -1
            for attempt in range(1, 6):
                ds_id = self._build_dataset_id(context)
                bundle_id = self._build_cluster_bundle_data_id(context)
                bundle_content = {
                    "cluster_bundle": True,
                    "cluster_dataset_id": ds_id,
                    "embedding_data_ids": member_ids,
                    "cluster_label": lab,
                    "is_noise": is_noise,
                    "algorithm": "DBSCAN",
                }
                try:
                    await data_repository.insert(
                        {
                            "data_id": bundle_id,
                            "content": bundle_content,
                            "type": "cluster_bundle",
                        }
                    )
                    await dataset_repository.insert(
                        {
                            "dataset_id": ds_id,
                            "data_ids": [bundle_id],
                            "type": "cluster",
                            "cluster_label": lab,
                            "is_noise": is_noise,
                            "algorithm": "DBSCAN",
                        }
                    )
                    output_dataset_ids.append(ds_id)
                    break
                except DuplicateKeyError:
                    logger.warning(
                        "%s DuplicateKey Cluster bundle/dataset (%d/5)",
                        src,
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
            "%s Clustering_DBSCAN fertig: %d Cluster/Noise-Datasets, quality=%s",
            src,
            len(output_dataset_ids),
            quality,
        )
        return result

    @staticmethod
    def get_plugin_info() -> dict[str, Any]:
        return {
            "name": "Clustering_DBSCAN",
            "plugin_type": "clustering",
            "version": "1.0.0",
            "status": "ready",
        }
