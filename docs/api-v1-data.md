# API v1: Data- und Dataset-Dokumente (`/api/v1/data`)

Einheitliche Endpunkte für Dokumente in der Collection `data_items` (`doc_type`: `data` oder `dataset`).

## Endpunkte

| Methode | Pfad | Beschreibung |
|--------|------|----------------|
| GET | `/api/v1/data` | Paginierte Liste (Metadaten, **ohne** top-level `content`) |
| GET | `/api/v1/data/{item_id}` | Einzelnes Dokument **vollständig** (inkl. `content` bei `data`) |
| POST | `/api/v1/data` | Neues Data-Dokument anlegen (`doc_type=data`) |

Auth: Header `X-API-Key` wie bei allen v1-Routen.

## Liste (GET)

Query-Parameter:

- `page` (Standard 1), `page_size` (Standard 20, max. 100)
- `doc_type` **mehrfach** möglich: z. B. `?doc_type=data&doc_type=dataset` filtert auf die genannten Typen. Ohne Parameter: alle Typen.

Ungültige `doc_type`-Werte führen zu **422** mit deutscher Fehlermeldung (`detail`).

Antwort: wie andere paginierte Listen (`items`, `page`, `page_size`, `total_items`, `total_pages`). Jedes Element enthält u. a. `id`, `doc_type`, `_id`, Zeitstempel, bei Datasets `data_ids`, bei Data ggf. `type` — **kein** `content`.

## Detail (GET)

Liefert das gespeicherte Dokument unverändert (inkl. `content` für `doc_type=data`).

## Anlegen (POST)

Body wie `DataItemCreateRequest`: mindestens `content`, optional `id` und `type`. Antwort **201** mit vollständigem Dokument.

## OpenAPI / Hoppscotch

Siehe `hoppscotch/dflowp-api-openapi.json` (Pfade `/api/v1/data` und `/api/v1/data/{item_id}`).
