# DataRepository Consolidation - Migrationsleitfaden

Skripte und dieses Dokument liegen im Ordner **`migrations/`** (Repository-Root).

Diese Datei dokumentiert die Migration von zwei separaten Repositories (`DataRepository` und `DatasetRepository`) zu einem einheitlichen `DataItemRepository`.

## Überblick

### Was hat sich geändert?

**Alte Struktur:**
- Zwei separate MongoDB Collections: `data` und `datasets`
- `DataRepository` speichert einzelne Datensätze mit `data_id`
- `DatasetRepository` speichert Datengruppen mit `dataset_id`

**Neue Struktur:**
- Eine einheitliche Collection: `data_items`
- Ein `doc_type`-Feld unterscheidet zwischen "data" und "dataset"
- Ein einheitliches `id`-Feld für beide Dokumenttypen
- Wrapper-Klassen für Rückwärtskompatibilität

### Warum die Änderung?

- Eliminiert Code-Duplikation zwischen zwei identischen Repository-Klassen
- Vereinfacht die Wartung und Erweiterung
- Bessere Typ-Sicherheit durch explizite Unterscheidung

## Migrationsprozess

### Schritt 1: Backup erstellen (Empfohlen)

```bash
# MongoDB-Datenbank sichern
mongodump --uri="mongodb://localhost:27017/dflowp" --out=./backup_before_migration
```

### Schritt 2: Dry-Run durchführen (Test)

```bash
# Zeigt, was migriert werden würde, ohne Daten zu löschen
python migrations/migrate_repositories.py
```

Dies zeigt:
- Anzahl der zu migrierenden Data-Dokumente
- Anzahl der zu migrierenden Dataset-Dokumente
- Anzahl der übersprungenen Dokumente (falls ID-Konflikte existieren)
- Fehler bei der Migration

### Schritt 3: Tatsächliche Migration durchführen

```bash
# Migriert Daten und löscht alte Collections
python migrations/migrate_repositories.py --force
```

**Vorsicht:** Dieser Befehl löscht die alten `data` und `datasets` Collections nach erfolgreicher Migration!

### Schritt 4: Verifizierung

```bash
mongosh dflowp

# Neue Collection überprüfen
db.data_items.count()
db.data_items.find({doc_type: "data"}).count()
db.data_items.find({doc_type: "dataset"}).count()

# Alte Collections sollten nicht mehr existieren
db.getCollectionNames()  # sollte "data" und "datasets" nicht enthalten
```

## Datenstruktur (Vor und Nach)

### Data-Dokumente

**Vorher:**
```json
{
  "_id": ObjectId(...),
  "data_id": "data_article_001",
  "content": {"title": "...", "url": "..."},
  "type": "output"
}
```

**Nachher:**
```json
{
  "_id": ObjectId(...),
  "id": "data_article_001",
  "doc_type": "data",
  "content": {"title": "...", "url": "..."},
  "type": "output"
}
```

### Dataset-Dokumente

**Vorher:**
```json
{
  "_id": ObjectId(...),
  "dataset_id": "ds_articles_batch_001",
  "data_ids": ["data_1", "data_2", "data_3"]
}
```

**Nachher:**
```json
{
  "_id": ObjectId(...),
  "id": "ds_articles_batch_001",
  "doc_type": "dataset",
  "data_ids": ["data_1", "data_2", "data_3"]
}
```

## Rückwärtskompatibilität

Die alten `DataRepository` und `DatasetRepository` Klassen funktionieren weiterhin:

```python
# Alte API (funktioniert immer noch)
data_repo = DataRepository()
found = await data_repo.find_by_id("data_123")
# → gibt Dokument mit "data_id" zurück (Wrapper-Konversion)

dataset_repo = DatasetRepository()
found = await dataset_repo.find_by_id("ds_001")
# → gibt Dokument mit "dataset_id" zurück (Wrapper-Konversion)
```

Die Wrapper-Klassen führen automatisch die Feldkonvertierung durch:
- `id` ↔ `data_id` / `dataset_id`
- Hinzufügen/Entfernen von `doc_type`

## Fehlerbehebung

### Fehler: "ID bereits vorhanden"

Wenn die Migration meldet, dass Dokumente übersprungen wurden:

```bash
# Überprüfe für ID-Konflikte
mongosh dflowp
db.data_items.find({id: "data_123"})  # Suche nach der ID
```

**Ursachen:**
- Migration wurde bereits teilweise durchgeführt
- Manuelle Duplikate in den alten Collections

**Lösung:**
- Wenn die Migration bereits läuft: Skript erneut mit `--force` ausführen (idempotent)
- Wenn manuelle Duplikate: Diese bereinigen und erneut migrieren

### Fehler: "Mongosh nicht gefunden"

Installiere MongoDB Shell:
```bash
# macOS
brew install mongodb-community-shell

# Ubuntu/Debian
sudo apt-get install mongodb-mongosh

# oder Docker
docker run -it --network host mongo:latest mongosh mongodb://localhost:27017
```

### Migration schlägt fehl

Falls die Migration mit Fehlern abbricht:

1. Überprüfe die Logs auf spezifische Fehler
2. Stelle sicher, dass MongoDB läuft: `mongosh localhost:27017/admin`
3. Überprüfe auf Datenbankzugriff und Speicherplatz
4. Falls nötig: Backup wiederherstellen und nochmal versuchen

```bash
# Backup zurückrestellen
mongorestore --uri="mongodb://localhost:27017/dflowp" ./backup_before_migration/dflowp
```

## Nach der Migration

### Code-Updates (Optional)

Die Wrapper-Klassen bleiben erhalten, aber für neue Code kannst du das neue einheitliche Repository verwenden:

```python
from dflowp_core.database.data_item_repository import DataItemRepository

repo = DataItemRepository()

# Data-Dokument
await repo.insert({
    "id": "data_123",
    "doc_type": "data",
    "content": {...},
    "type": "output"
})

# Dataset-Dokument
await repo.insert({
    "id": "ds_456",
    "doc_type": "dataset",
    "data_ids": ["data_1", "data_2"]
})
```

### Alte Code entfernen (Später)

Nach ein oder zwei Releases können die alten Wrapper-Klassen entfernt werden:
- Alle Imports von `DataRepository` und `DatasetRepository` auf `DataItemRepository` umstellen
- Die Wrapper-Klassen-Dateien löschen

## Zusätzliche Ressourcen

- **CLAUDE.md**: Architektur-Dokumentation
- **`dflowp-packages/dflowp-core/src/dflowp_core/database/migrations.py`**: Migrations-Implementierung
- **tests/database_test.py**: Tests für beide Repositories
