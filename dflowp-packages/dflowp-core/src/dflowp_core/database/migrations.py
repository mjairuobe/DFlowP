"""Datenbankmigrations-Utilities für DFlowP."""

import logging
from typing import Optional

from dflowp_core.database.mongo import get_database

logger = logging.getLogger(__name__)


async def migrate_repositories_to_unified() -> dict[str, int]:
    """
    Migriert Daten aus den alten 'data' und 'datasets' Collections
    in die neue einheitliche 'data_items' Collection.

    Gibt ein Dict mit Migrationsergebnissen zurück:
    {
        "data_migrated": Anzahl der migrierten Data-Dokumente,
        "datasets_migrated": Anzahl der migrierten Dataset-Dokumente,
        "skipped": Anzahl der übersprungenen Dokumente (ID-Konflikte),
        "errors": Anzahl der Fehler
    }

    Diese Funktion ist idempotent und kann sicher mehrmals aufgerufen werden.
    """
    db = get_database()
    results = {
        "data_migrated": 0,
        "datasets_migrated": 0,
        "skipped": 0,
        "errors": 0,
    }

    # Stelle sicher, dass die neue Collection existiert
    target_collection = db["data_items"]

    # Migriere Data-Dokumente
    logger.info("Starte Migration von 'data' Collection...")
    data_collection = db["data"]
    data_count = await data_collection.count_documents({})

    if data_count > 0:
        async for doc in data_collection.find({}):
            try:
                # Konvertiere data_id zu id
                doc_id = doc.pop("data_id", None)
                if not doc_id:
                    logger.warning("Data-Dokument ohne data_id: %s", doc["_id"])
                    results["errors"] += 1
                    continue

                # Prüfe ob bereits migriert
                existing = await target_collection.find_one({"id": doc_id})
                if existing:
                    logger.debug("Data-Dokument mit id=%s existiert bereits, überspringe", doc_id)
                    results["skipped"] += 1
                    continue

                # Füge id und doc_type hinzu
                doc["id"] = doc_id
                doc["doc_type"] = "data"

                # Entferne alte MongoDB _id, die wird neu generiert
                doc.pop("_id", None)

                await target_collection.insert_one(doc)
                results["data_migrated"] += 1

                if results["data_migrated"] % 100 == 0:
                    logger.info("  %d Data-Dokumente migriert...", results["data_migrated"])

            except Exception as e:
                logger.error("Fehler beim Migrieren von Data-Dokument: %s", e)
                results["errors"] += 1

    logger.info("Data-Migration abgeschlossen: %d migriert", results["data_migrated"])

    # Migriere Dataset-Dokumente
    logger.info("Starte Migration von 'datasets' Collection...")
    datasets_collection = db["datasets"]
    datasets_count = await datasets_collection.count_documents({})

    if datasets_count > 0:
        async for doc in datasets_collection.find({}):
            try:
                # Konvertiere dataset_id zu id
                doc_id = doc.pop("dataset_id", None)
                if not doc_id:
                    logger.warning("Dataset-Dokument ohne dataset_id: %s", doc["_id"])
                    results["errors"] += 1
                    continue

                # Prüfe ob bereits migriert
                existing = await target_collection.find_one({"id": doc_id})
                if existing:
                    logger.debug("Dataset-Dokument mit id=%s existiert bereits, überspringe", doc_id)
                    results["skipped"] += 1
                    continue

                # Füge id und doc_type hinzu
                doc["id"] = doc_id
                doc["doc_type"] = "dataset"

                # Entferne alte MongoDB _id, die wird neu generiert
                doc.pop("_id", None)

                await target_collection.insert_one(doc)
                results["datasets_migrated"] += 1

                if results["datasets_migrated"] % 100 == 0:
                    logger.info("  %d Dataset-Dokumente migriert...", results["datasets_migrated"])

            except Exception as e:
                logger.error("Fehler beim Migrieren von Dataset-Dokument: %s", e)
                results["errors"] += 1

    logger.info("Dataset-Migration abgeschlossen: %d migriert", results["datasets_migrated"])

    # Erstelle Indizes
    logger.info("Erstelle Indizes in data_items Collection...")
    await target_collection.create_index("id", unique=True)
    await target_collection.create_index("doc_type")
    await target_collection.create_index([("doc_type", 1), ("id", 1)])

    return results


async def cleanup_old_collections(dry_run: bool = True) -> dict[str, int]:
    """
    Löscht die alten 'data' und 'datasets' Collections nach erfolgreicher Migration.

    Args:
        dry_run: Wenn True, werden Collections nicht wirklich gelöscht, nur gezählt

    Returns:
        Dict mit Anzahl der gelöschten Dokumente pro Collection
    """
    db = get_database()
    results = {"data": 0, "datasets": 0}

    data_collection = db["data"]
    data_count = await data_collection.count_documents({})
    results["data"] = data_count

    datasets_collection = db["datasets"]
    datasets_count = await datasets_collection.count_documents({})
    results["datasets"] = datasets_count

    if dry_run:
        logger.info(
            "DRY RUN: Würde folgende Collections löschen: data (%d docs), datasets (%d docs)",
            data_count,
            datasets_count,
        )
        return results

    if data_count > 0:
        logger.warning("Lösche 'data' Collection mit %d Dokumenten...", data_count)
        await db.drop_collection("data")
        logger.info("'data' Collection gelöscht")

    if datasets_count > 0:
        logger.warning("Lösche 'datasets' Collection mit %d Dokumenten...", datasets_count)
        await db.drop_collection("datasets")
        logger.info("'datasets' Collection gelöscht")

    return results


async def migrate_all(dry_run: bool = False) -> dict:
    """
    Führt komplette Migration durch: Kopieren + Bereinigung.

    Args:
        dry_run: Wenn True, werden Collections nicht gelöscht

    Returns:
        Dict mit Migrationsergebnissen und Bereinigungsergebnissen
    """
    logger.info("=" * 60)
    logger.info("Starte DFlowP Repository Consolidation Migration")
    logger.info("=" * 60)

    # Phase 1: Migration
    migration_results = await migrate_repositories_to_unified()
    logger.info("Migration-Ergebnisse: %s", migration_results)

    # Phase 2: Bereinigung
    cleanup_results = await cleanup_old_collections(dry_run=dry_run)
    logger.info("Bereinigungs-Ergebnisse: %s", cleanup_results)

    logger.info("=" * 60)
    logger.info("Migration abgeschlossen!")
    logger.info("=" * 60)

    return {
        "migration": migration_results,
        "cleanup": cleanup_results,
        "dry_run": dry_run,
    }


async def migrate_legacy_processes_to_pipelines() -> int:
    """
    Legt je ein Pipeline-/Dataflow-/State-/Config-Dokument für jedes Legacy-`processes`-Dokument an,
    sofern noch keine `pipeline_id` in `pipelines` existiert. Idempotent.
    """
    from dflowp_core.database.dataflow_repository import DataflowRepository
    from dflowp_core.database.dataflow_state_repository import DataflowStateRepository
    from dflowp_core.database.pipeline_repository import PipelineRepository
    from dflowp_core.database.plugin_configuration_repository import PluginConfigurationRepository

    db = get_database()
    col_old = db["processes"]
    if await col_old.count_documents({}) == 0:
        return 0

    pr = PipelineRepository()
    dfr = DataflowRepository()
    pcr = PluginConfigurationRepository()
    dsr = DataflowStateRepository()
    n = 0
    async for old in col_old.find({}):
        pid = old.get("pipeline_id")
        if not pid:
            continue
        if await pr.find_by_id(pid):
            continue
        cfg = old.get("configuration") or {}
        dataflow = cfg.get("dataflow") or {"nodes": [], "edges": []}
        df_id = f"mig_df_{pid}"
        if not await dfr.find_by_id(df_id):
            await dfr.insert(
                {
                    "dataflow_id": df_id,
                    "name": str(pid),
                    "nodes": dataflow.get("nodes", []),
                    "edges": dataflow.get("edges", []),
                }
            )
        pcfg_id = f"mig_pcfg_{pid}"
        sc = cfg.get("plugin_config") or {}
        if not await pcr.find_by_id(pcfg_id):
            await pcr.insert(
                {
                    "plugin_configuration_id": pcfg_id,
                    "by_plugin_worker_id": sc,
                }
            )
        st = old.get("dataflow_state") or {"nodes": [], "edges": []}
        dfs_id = f"mig_dfs_{pid}"
        if not await dsr.get_by_id(dfs_id):
            await dsr.insert(
                {
                    "dataflow_state_id": dfs_id,
                    "pipeline_id": pid,
                    "dataflow_id": df_id,
                    "nodes": st.get("nodes", []),
                    "edges": st.get("edges", []),
                    "dataflow_state": st,
                }
            )
        input_ds = old.get("input_dataset_id")
        if input_ds is None:
            input_ds = cfg.get("input_dataset_id", "unknown")
        pl = {
            "pipeline_id": pid,
            "software_version": old.get("software_version", cfg.get("software_version", "0.1.0")),
            "input_dataset_id": input_ds,
            "dataflow_id": df_id,
            "plugin_configuration_id": pcfg_id,
            "dataflow_state_id": dfs_id,
            "status": old.get("status", "pending"),
        }
        if old.get("timestamp_ms") is not None:
            pl["timestamp_ms"] = old["timestamp_ms"]
        await pr.insert(pl)
        n += 1
    if n:
        logger.info("migrate_legacy_processes_to_pipelines: %d migriert", n)
    return n
