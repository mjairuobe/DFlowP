#!/usr/bin/env python3
"""
Migrationsscript für DataRepository → DataItemRepository Consolidation.

Verwendung:
    # Dry-run (zeigt was gelöscht werden würde):
    python migrate_repositories.py

    # Tatsächliche Migration (kopiert Daten + löscht alte Collections):
    python migrate_repositories.py --force
"""

import asyncio
import logging
import sys

from dflowp_core.database.migrations import migrate_all
from dflowp_core.database.mongo import (
    close_mongodb_connection,
    connect_to_mongodb,
    resolve_mongodb_uri,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    force_delete = "--force" in sys.argv

    if not force_delete:
        logger.info("Starting in DRY-RUN mode (keine Daten werden gelöscht)")
        logger.info("Verwende --force um tatsächlich alte Collections zu löschen")
        print()

    # Verbinde mit MongoDB
    await connect_to_mongodb(
        uri=resolve_mongodb_uri(),
        database_name="dflowp"
    )

    try:
        # Führe Migration durch
        results = await migrate_all(dry_run=not force_delete)

        # Zeige Ergebnisse
        print()
        print("=" * 60)
        print("MIGRATION ERGEBNISSE")
        print("=" * 60)
        print(f"Data-Dokumente migriert:   {results['migration']['data_migrated']}")
        print(f"Dataset-Dokumente migriert: {results['migration']['datasets_migrated']}")
        print(f"Übersprungene Dokumente:   {results['migration']['skipped']}")
        print(f"Fehler:                     {results['migration']['errors']}")
        print()

        if force_delete:
            print("BEREINIGUNG")
            print("-" * 60)
            print(f"'data' Collection gelöscht:     {results['cleanup']['data']} docs")
            print(f"'datasets' Collection gelöscht: {results['cleanup']['datasets']} docs")
        else:
            print("DRY-RUN: Keine Collections gelöscht")
            print(f"Würde löschen: {results['cleanup']['data']} Data + {results['cleanup']['datasets']} Dataset Dokumente")

        print("=" * 60)

        if results['migration']['errors'] > 0:
            logger.error("Migration mit %d Fehlern abgeschlossen", results['migration']['errors'])
            sys.exit(1)

        logger.info("Migration erfolgreich abgeschlossen!")

    finally:
        await close_mongodb_connection()


if __name__ == "__main__":
    asyncio.run(main())
