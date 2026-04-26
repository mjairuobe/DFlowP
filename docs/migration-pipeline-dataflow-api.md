# Migrations- und Zielplan: Pipeline, Dataflow, API (DFlowP)

Dieses Dokument fasst die fachlich und technisch vereinbarten Ziele, Datenmodelle, Klon-Regeln, geplante Repositories, API-Oberfläche und die **Migrations-Checkliste** zusammen. Stand der Abstimmung: April 2026.

---

## 1. Wording

| Bisher (Sinnbild) | Zielbezeichnung |
|-------------------|-----------------|
| Process | **Pipeline** |
| Subprocess (Modul, z. B. EmbedData) | **Plugin** |
| Instanz (z. B. EmbedData1) | **`plugin_worker_id`** (Knoten im Dataflow) |

Domain-**IDs** (Begriffe mit Underscore, z. B. `ds_news_002`, `fetch_embed_cluster_topic_flow_02`) bleiben explizit adressierbar, damit ein Dataflow dasselbe Plugin-**Typ**-Konzept bei mehrfacher Verwendung über **unterschiedliche** `plugin_worker_id`s abbilden kann.

**JSON-Feldnamen:** `snake_case`  
**HTTP-Pfade:** `kebab-case` (z. B. `/api/v1/dataflow-states`)

---

## 2. Architekturziele (Kurz)

- **Pipeline** hält **Referenzen**, keinen monolithischen Ballast: kein voll eingebetteter **Dataflow**-Graph und kein voller **DataflowState** im Pipeline-Dokument.
- **Dataflow** (Definition) ist in einer **eigenen Collection** (Repository), **wiederverwendbar**: mehrere Pipelines **dürfen** dieselbe `dataflow_id` referenzieren. Keine **Reference-Count-** oder **Update-Policy**-Pflicht (Dokumente werden überwiegend kopiert, nicht in-place gepflegt).
- **DataflowState** (Laufzeit) ist **eigenes** Dokument, per `dataflow_state_id` von der Pipeline referenziert, **eigener** API-Detail-Endpoint.
- **I/O-Transformation-States** sind **ausschließlich im DataflowState-Dokument eingebettet** (z. B. pro Knoten als Liste `io_transformation_states`), **keine** separate Collection, **keine** Verweise von I/O-Objekten auf **andere** DataflowState-Dokumente, **kein** `base_state` / `baseDataflowStateId`.
- **plugin_configuration** ist ausgelagert, von der Pipeline per Foreign Key referenziert. Pro **`plugin_worker_id`** (Knoten im Dataflow) steht **ein** konfigurierbarer Block; technisch „Replikas derselben `plugin_worker_id` teilen die Konfiguration“ (ein Eintrag in der Map).
- **Redundante** Angaben, die oberhalb des früheren `configuration`-Würfels im JSON lagen, entfallen dort (z. B. doppelte Softwareversion, Prozess-ID, Input-Dataset, nach Umbenennung).
- **Data / Dataset:** ein Repository über `data_items` mit Filter **`doc_type`**; **keine** zusätzlichen Endpoints ausschließlich für Datasets.
- **API:** Listen-Endpoints liefern **nur Metadaten und Identifikation**; Detail-Endpoints **volle** Inhalte (inkl. `content` bei Data, jeweils nach Projektregel).

---

## 3. Klon-Regeln (Pipeline)

| Entscheidung | Regel |
|--------------|--------|
| **Neue `dataflow_id`?** | **Ja**, wenn sich der **Dataflow-Graph** inkl. **`plugin_worker_id`** / Knoten- und Kanten-Struktur vom Klon unterscheidet. **Nein (Wiederverwendung)**, wenn nur etwas anderes (z. B. `plugin_configuration`) anders ist und der **Graph fachlich gleich** bleibt. |
| **Neue `plugin_configuration_id`?** | **Nur** wenn sich **inhaltlich** etwas an der Konfiguration ändert (z. B. anderes Embedding-Modell). Sonst: **wieder** dieselbe `plugin_configuration_id` referenzieren. |
| **Immer neu** | **`pipeline_id`**, **`dataflow_state_id`** inkl. **Kopie aller eingebetteten** `io_transformation_states`. |

**Prinzip `plugin_configuration`:** Konfiguration wird **nur durch Klon/Neu-Anlage** geändert, **kein** In-place-Update des bestehenden Konfiguration-Dokuments. „Änderung“ = neues Dokument + neue `plugin_configuration_id`.

**Endpunkte:** Sollen fachlich **von überall** (für integrierende Clients) **nutzbar** sein, vorbehaltlich der bestehenden **Authentisierung/Autorisierung** (z. B. API-Key).

### Entscheidungsbaum (Klon)

```
Pipeline-Klon
├─ Graph / plugin_worker_id-Satz (Dataflow) geändert?
│  ├─ Ja  → neues dataflow_id (neues dataflow-Dokument)
│  └─ Nein → dataflow_id WIEDER von der Quell-Pipeline
├─ plugin-Konfig (z. B. embedding_model) anders?
│  ├─ Ja  → neue plugin_configuration_id (KLON, kein Update)
│  └─ Nein → plugin_configuration_id WIEDER
└─ dataflow_state_id: immer NEU (voll inkl. io_transformation_states)
    pipeline_id: immer NEU
```

---

## 4. Geplante Repositories (Zielbild)

| Repository | Collection (Arbeitsname) | Zweck |
|------------|-------------------------|--------|
| PipelineRepository | `pipelines` o.ä. | Kern: `pipeline_id`, `software_version`, `input_dataset_id`, `dataflow_id`, `plugin_configuration_id`, `dataflow_state_id`, Status, Timestamps. |
| DataflowRepository | `dataflows` | Statische DAG-Definition; `dataflow_id`; mehrfach referenzierbar. |
| DataflowStateRepository | `dataflow_states` | Laufzeit-Graph, **I/O eingebettet**; kein `base_state`. |
| PluginConfigurationRepository | `plugin_configurations` | Pro `plugin_worker_id` Konfig-Blöcke; kein fachl. In-place-Update, nur neues/kopiertes Doc. |
| DataItemRepository | `data_items` | Vereinheitlicht `doc_type` (data, dataset, …), Wrapper reduzieren. |
| EventRepository | `events` | `pipeline_id`, `plugin_worker_id`, `plugin_type` statt veralteter Bezeichner. |

---

## 5. Geplante API-Endpoints (Überblick)

Pfade in **kebab-case**; JSON in **snake_case**.

- `/api/v1/pipelines` — Listen, anlegen, `GET/DELETE /{pipeline_id}`, ggf. `POST …/stop`, `POST …/clone`
- `/api/v1/dataflows` — CRUD, `…/{dataflow_id}`
- `/api/v1/dataflow-states` — CRUD, `…/{dataflow_state_id}` (List mit Filter z. B. `pipeline_id`)
- `/api/v1/plugin-configurations` — CRUD, `…/{plugin_configuration_id}` (fachl. „Update“ = neues Dokument)
- `/api/v1/data` — Listen (Filter `doc_type` multi), `GET/POST/… /{id}`; **Datasets** nur über `doc_type`, keine `GET /datasets`
- `/api/v1/events` — Listen, Detail
- Health/Root wie bisher, Auth wie `require_api_key` o.ä.

**CRUD** für die genannten Ressourcen, soweit sinnvoll; Schreib-Pfade bewusst **öffentlich** im Sinne des API-Produkts (abgesichert wie heute).

---

## 6. Beispiel-Detail-JSONs (Referenz, snake_case)

### Pipeline

```json
{
  "pipeline_id": "proc_fetch_news_01",
  "software_version": "0.1.0",
  "input_dataset_id": "ds_news_002",
  "dataflow_id": "fetch_embed_cluster_topic_flow_02",
  "plugin_configuration_id": "pcfg_fetch_01",
  "dataflow_state_id": "dfs_proc_fetch_news_01_a",
  "status": "pending",
  "created_at": "2026-04-26T10:00:00Z",
  "updated_at": "2026-04-26T10:00:00Z"
}
```

### Dataflow

```json
{
  "dataflow_id": "fetch_embed_cluster_topic_flow_02",
  "name": "fetch_embed_cluster_topic_flow",
  "nodes": [
    { "plugin_worker_id": "fetch_feed_1", "plugin_type": "FetchFeedItems" },
    { "plugin_worker_id": "embed_data_1", "plugin_type": "EmbedData" }
  ],
  "edges": [
    { "from": "fetch_feed_1", "to": "embed_data_1" }
  ],
  "created_at": "2025-12-01T00:00:00Z"
}
```

### plugin_configuration

```json
{
  "plugin_configuration_id": "pcfg_fetch_01",
  "by_plugin_worker_id": {
    "embed_data_1": { "openai_model": "text-embedding-3-small" },
    "fetch_feed_1": { "max_items": 50 }
  },
  "created_at": "2026-01-10T00:00:00Z"
}
```

### DataflowState (I/O eingebettet, keine fremden State-Refs in I/O)

```json
{
  "dataflow_state_id": "dfs_proc_fetch_news_01_a",
  "pipeline_id": "proc_fetch_news_01",
  "dataflow_id": "fetch_embed_cluster_topic_flow_02",
  "nodes": [
    {
      "plugin_worker_id": "embed_data_1",
      "plugin_type": "EmbedData",
      "event_status": "not_started",
      "io_transformation_states": [
        {
          "input_data_id": "data_row_12",
          "output_data_ids": ["data_out_3", "data_out_4"],
          "status": "not_started",
          "quality": null
        }
      ]
    }
  ],
  "edges": [
    { "from": "fetch_feed_1", "to": "embed_data_1" }
  ],
  "updated_at": "2026-04-26T10:00:00Z"
}
```

### data (Beispiel)

```json
{
  "id": "data_row_12",
  "doc_type": "data",
  "type": "input",
  "content": { "url": "https://example.com/…" },
  "timestamp_ms": 1714123456789
}
```

### dataset (Beispiel, gleicher Endpunkt `/data/{id}`)

```json
{
  "id": "ds_news_002",
  "doc_type": "dataset",
  "data_ids": ["data_row_10", "data_row_12"],
  "timestamp_ms": 1714123000000
}
```

### event (Wording)

```json
{
  "id": "507f1f77bcf86cd799439011",
  "pipeline_id": "proc_fetch_news_01",
  "plugin_worker_id": "embed_data_1",
  "plugin_type": "EmbedData",
  "event_type": "EVENT_COMPLETED",
  "event_time": "2026-04-26T10:01:00Z",
  "timestamp_ms": 1714123460000
}
```

---

## 7. Operation → betroffene Ids / Dokumente (Referenztabelle)

**Legende:** NEU = neues Dokument; WIEDER = Referenz beibehalten; KLON = neues Dokument, Inhalt von Quelle; — = trifft nicht zu.

### Pipeline-Klon

| Objekt | NEU / KLON | WIEDER | Hinweis |
|--------|------------|--------|--------|
| `pipeline` | **immer** NEU | — | Jeder Klon = neue `pipeline_id`. |
| `dataflow` | NEU, wenn **Graph** / `plugin_worker_id` anders | **WIEDER** `dataflow_id`, wenn **nur** z. B. `plugin_configuration` anders, Graph unverändert | Siehe Klon-Regeln. |
| `plugin_configuration` | **KLON** + neue `plugin_configuration_id`, wenn **irgendein** Param anders | **WIEDER** bei identischer Config | Niemals bestehendes Config-Doc **updaten**. |
| `dataflow_state` | **immer** NEU / KLON (voll, inkl. I/O) | — | Kein `base_state`. |
| `data` / `data_items` | situativ (je nach Klon, ob Daten dupliziert) | ggf. gleiche `id` | fachlich festlegen. |
| `event` | NEU für neue Lauf-Events; Alte hängen an alter `pipeline_id` | — | |

### Manuell: neue Pipeline

| Objekt | Typisch |
|--------|---------|
| `pipeline` | NEU |
| `dataflow` | WIEDER (existierend) oder NEU |
| `plugin_configuration` | NEU oder WIEDER |
| `dataflow_state` | NEU (Startzustand) |

### `plugin_configuration` (Fachregel)

| Situation | Aktion |
|----------|--------|
| Parameterwechsel | **KLON** → neue `plugin_configuration_id` |
| unveränderter Klon | `plugin_configuration_id` **WIEDER** |
| „Update“-Wunsch | Verbot: stattdessen neues Doc + Umhängen der Referenz |

### `dataflow_state` (I/O)

| Situation | Verhalten |
|-----------|-----------|
| Klon | NEU, **eingebettete** I/O, volle Kopie |
| Lauf/Engine | Updates nur auf **dieses** `dataflow_state` |

---

## 8. Migrations-Checkliste (Umsetzung)

### Phase 0 – Scope

- [ ] Wording-Referenz (`README`/Team) abgleichen: Pipeline, Dataflow, DataflowState, `plugin_type` / `plugin_worker_id`, `plugin_configuration`
- [ ] API-Versionierung: bleibt alles unter `/api/v1` mit neuen Pfaden, oder harter Bruch `/api/v2`?
- [ ] Abstimmung mit **Processruntime**: gemeinsame Milestones (Lesen/Schreiben, Klon, Events)

### Phase 1 – MongoDB: Collections & Indizes

- [ ] Collections/Schema: `pipelines`, `dataflows`, `dataflow_states` (I/O **eingebettet**), `plugin_configurations`, `data_items` (unverändert ggf. nur Indizes), `events`
- [ ] Indizes: `pipeline_id` (unique wo sinnvoll), `dataflow_id` auf Pipelines/States, `dataflow_state_id` auf Pipelines, `plugin_configuration_id` auf Pipelines, `data_items` (`id`, `doc_type`, …), `events` (Pipeline, `plugin_worker_id`, Zeiten, …)
- [ ] Eingebetteter alter `dataflow_state` in Prozess-Dokument: Quell-Struktur für Migrationstools dokumentieren

### Phase 2 – Datenmigration

- [ ] Inventar Bestandsdokumente
- [ ] idempotentes Migrations-Skript (dry-run, Resume): Prozess → Pipeline, Auslagerung `dataflow`, `dataflow_state` + I/O, Entredundantisierung `configuration`, Events-Backfill
- [ ] Validierung (Stichproben, Invarianten)
- [ ] Rollback-Strategie (Snapshot, Wiederanlauf)

### Phase 3 – dflowp_core Repositories

- [ ] Repositories oben: CRUD, Listen-Detail-Trennung, Klon-Helper mit festen Klon-Regeln
- [ ] `DataItemRepository` vereinheitlichen; alte schmale Wrapper entfernen/deprecated markieren
- [ ] `EventRepository` an neue Feldnamen

### Phase 4 – FastAPI

- [ ] Routen, Pydantic, kebab-paths, `snake_case` Body
- [ ] `process_persist` & Co. an neues Layout
- [ ] alte Pfade: Entfernen oder Deprecation (Zeitbox)
- [ ] kein `GET` nur für Datasets; nur `/data` + `doc_type`

### Phase 5 – Processruntime

- [ ] Lauf: Auflösen aller Ids, Schreiben nur in `dataflow_states` (ggf. Transaktionen)
- [ ] Begriffsumstellung im sichtbaren Lauf-Code: `subprocess` → Plugin / `plugin_worker_id` wo sinnvoll
- [ ] E2E-Test: Start → State → Event

### Phase 6 – Tests

- [ ] Unit (Repos, Klon, `doc_type` Filter)
- [ ] API (Listen/Detail, 422-Filterstil)
- [ ] Migrations-Test auf Staging-Daten
- [ ] Security-Sanity: Schreib-Endpoints + vorhandene Auth

### Phase 7 – Inbetriebnahme

- [ ] Staging, Smoke, dann Produktion (Wartungsfenster o. blau-grün)
- [ ] Log-/Metrik-Queries auf neue Feldnamen anpassen
- [ ] Breaking-Changes-Note für API-Konsumenten
- [ ] alte Indizes/Dead Code nach Cutover entfernen (optional, Phase 8)

---

## 9. Abgrenzung Runtime (Kurz)

Diese Migrations-API-Schicht ersetzt **nicht** automatisch jede Prozessengine-Detailänderung: **Laden** der Pipeline, **Auflösen** `dataflow_id` + `plugin_configuration_id` + `dataflow_state_id`, **Zusammenführen** der Laufzeitsicht und **Zustands-Updates** (nur in `dataflow_states` bzw. transaktional) obliegen `dflowp_processruntime` und müssen in denselben Release-Zügen geprüft werden.

---

## 10. Offene Projektkonfiguration (optional)

- Soll alles unter **einer** API-Version bleiben (`/api/v1/…` mit Bruch) oder bewusst `v2`?
- Soll Migrations-Release **phasiert** (Read-First) oder **Big Bang** erfolgen?

Diese Punkte in Phase 0 klären.
