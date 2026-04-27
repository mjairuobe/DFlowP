# DFlowP API Referenz

Diese Referenz beschreibt den aktuellen Stand der DFlowP API unter `/api/v1`.

## Grundlagen

- API-Prefix: `/api/v1`
- Authentifizierung: Header `X-API-Key: <key>`
- API-Key-Quelle: Umgebungsvariable `DFlowP_API_Key`
- Standard-Paginierung: `page=1`, `page_size=20`, `page_size <= 100`

### Fehlerstil

- Fehler werden als JSON mit `detail` zurueckgegeben.
- Typische Antworten:
  - `401`: `Ungueltiger API-Key.`
  - `500`: `Serverkonfiguration unvollstaendig: DFlowP_API_Key fehlt.`

## Endpoint-Katalog

| Methode | Pfad | Zweck |
|---|---|---|
| GET | `/api/v1/data` | Data-/Dataset-Liste |
| GET | `/api/v1/data/{item_id}` | Data-/Dataset-Detail |
| POST | `/api/v1/data` | Data- oder Dataset-Dokument anlegen |
| GET | `/api/v1/pipelines` | Pipeline-Liste |
| GET | `/api/v1/pipelines/{pipeline_id}` | Pipeline-Detail |
| POST | `/api/v1/pipelines` | Pipeline anlegen |
| POST | `/api/v1/pipelines/{pipeline_id}/stop` | Pipeline stoppen |
| POST | `/api/v1/pipelines/{pipeline_id}/clone` | Pipeline klonen |
| DELETE | `/api/v1/pipelines/{pipeline_id}` | Pipeline loeschen |
| GET | `/api/v1/pipelines/{pipeline_id}/plugin-workers/{plugin_worker_id}` | Plugin-Worker-Detail innerhalb einer Pipeline |
| GET | `/api/v1/plugin-workers` | Plugin-Worker-Liste |
| GET | `/api/v1/dataflows` | Dataflow-Liste |
| GET | `/api/v1/dataflows/{dataflow_id}` | Dataflow-Detail |
| POST | `/api/v1/dataflows` | Dataflow anlegen |
| PUT | `/api/v1/dataflows/{dataflow_id}` | Dataflow ersetzen |
| DELETE | `/api/v1/dataflows/{dataflow_id}` | Dataflow loeschen |
| GET | `/api/v1/dataflow-states` | Dataflow-State-Liste |
| GET | `/api/v1/dataflow-states/{dataflow_state_id}` | Dataflow-State-Detail |
| POST | `/api/v1/dataflow-states` | Dataflow-State anlegen |
| PATCH | `/api/v1/dataflow-states/{dataflow_state_id}` | Dataflow-State teilweise aktualisieren |
| DELETE | `/api/v1/dataflow-states/{dataflow_state_id}` | Dataflow-State loeschen |
| GET | `/api/v1/plugin-configurations` | Plugin-Configuration-Liste |
| GET | `/api/v1/plugin-configurations/{plugin_configuration_id}` | Plugin-Configuration-Detail |
| POST | `/api/v1/plugin-configurations` | Plugin-Configuration anlegen |
| DELETE | `/api/v1/plugin-configurations/{plugin_configuration_id}` | Plugin-Configuration loeschen |
| GET | `/api/v1/events` | Event-Liste |
| GET | `/api/v1/events/{event_id}` | Event-Detail |
| POST | `/api/v1/events` | Event speichern |

## Wichtige Verhaltensregeln

### Data (`/data`)

- `GET /api/v1/data`
  - unterstuetzt `doc_type` als Mehrfachparameter, z. B. `doc_type=data&doc_type=dataset`
  - entfernt in der Listenansicht top-level `content`
- `GET /api/v1/data/{item_id}`
  - liefert das vollstaendige Dokument
- `POST /api/v1/data`
  - `doc_type`: `data` oder `dataset`
  - bei `data`: `content` erforderlich
  - bei `dataset`: genau eines von `data_ids` oder `rows`

### Pipelines (`/pipelines`)

- `POST /api/v1/pipelines`
  - erwartet `pipeline_id`, `input_dataset_id`, `dataflow`
  - optional `plugin_config`, `input_data`, `start_immediately`
- `POST /api/v1/pipelines/{pipeline_id}/clone`
  - erzeugt eine neue Pipeline und ein neues Dataflow-State-Dokument
  - optional: `new_pipeline_id`, `dataflow_id`, `plugin_config`, `parent_plugin_worker_ids`
- `POST /api/v1/pipelines/{pipeline_id}/stop`
  - setzt den Pipeline-Status auf `stopped`

### Dataflows (`/dataflows`)

- `POST /api/v1/dataflows`: neues Dataflow-Dokument
- `PUT /api/v1/dataflows/{dataflow_id}`: vorhandenes Dataflow-Dokument vollstaendig ersetzen

### Dataflow-States (`/dataflow-states`)

- `GET /api/v1/dataflow-states/{dataflow_state_id}` liefert `plugin_worker_summary`.
- `PATCH /api/v1/dataflow-states/{dataflow_state_id}` akzeptiert:
  - `dataflow_state` als Objekt, oder
  - Top-Level `nodes` und/oder `edges`

### Events (`/events`)

- `GET /api/v1/events/{event_id}` erwartet `event_id` als MongoDB-ObjectId-String.
- `POST /api/v1/events` setzt `event_time` serverseitig.

## Datenquellen (MongoDB Collections)

- `pipelines`
- `dataflows`
- `dataflow_states`
- `plugin_configurations`
- `events`
- `data_items`

## Hinweise fuer API-Clients

- Listen fuer Uebersichten nutzen, Detail-Endpoints fuer Vollinhalte.
- Bei mehrwertigen Filtern wiederholte Query-Parameter senden.
- `X-API-Key` bei jedem Request mitschicken.
