# Beispiel: pressmonitor-pipeline-clone-flow

Dieses Beispiel erstellt zuerst eine Quell-Pipeline mit `Clustering_DBSCAN` und klont sie danach.
Beim Clone wird der Clustering-Algorithmus auf `Clustering_HDBSCAN` umgestellt.

## Ziel

- eine kleine Pressmonitor-Quellpipeline mit DBSCAN anlegen
- alternativen Dataflow mit HDBSCAN anlegen
- Clone erzeugen, der auf den HDBSCAN-Dataflow zeigt

## 0) Variablen setzen

```bash
set -euo pipefail

export BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
export API_KEY="${API_KEY:-changeme}"
export API_PREFIX="/api/v1"

export EXAMPLE_ID="pressmonitor-pipeline-clone-flow"
export SOURCE_PIPELINE_ID="${EXAMPLE_ID}-src-$(date +%s)"
export CLONE_PIPELINE_ID="${EXAMPLE_ID}-clone-$(date +%s)"
export INPUT_DATASET_ID="ds-${SOURCE_PIPELINE_ID}"
export HDBSCAN_DATAFLOW_ID="df-${EXAMPLE_ID}-hdbscan-$(date +%s)"

TMP_DIR="$(mktemp -d)"
echo "Arbeitsverzeichnis: ${TMP_DIR}"
```

## 1) Quellpipeline inkl. kleinem Input erzeugen

Hier wird `input_data` direkt bei `POST /pipelines` genutzt. Die API legt dabei das Dataset automatisch an.

```bash
curl -sS -X POST \
  "${BASE_URL}${API_PREFIX}/pipelines" \
  -H "X-API-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d "{
    \"pipeline_id\": \"${SOURCE_PIPELINE_ID}\",
    \"software_version\": \"0.1.0\",
    \"input_dataset_id\": \"${INPUT_DATASET_ID}\",
    \"dataflow\": {
      \"nodes\": [
        {\"subprocess_id\": \"FetchFeedItems1\", \"subprocess_type\": \"FetchFeedItems\"},
        {\"subprocess_id\": \"EmbedData1\", \"subprocess_type\": \"EmbedData\"},
        {\"subprocess_id\": \"ClusterPress1\", \"subprocess_type\": \"Clustering_DBSCAN\"}
      ],
      \"edges\": [
        {\"from\": \"FetchFeedItems1\", \"to\": \"EmbedData1\"},
        {\"from\": \"EmbedData1\", \"to\": \"ClusterPress1\"}
      ]
    },
    \"plugin_config\": {
      \"FetchFeedItems1\": {\"max_items_per_feed\": 2},
      \"EmbedData1\": {\"model\": \"text-embedding-3-small\"},
      \"ClusterPress1\": {\"eps\": 0.5, \"min_samples\": 2, \"metric\": \"cosine\"}
    },
    \"input_data\": [
      {
        \"title\": \"Feed A\",
        \"xmlUrl\": \"https://example.org/feed-a.xml\",
        \"htmlUrl\": \"https://example.org/a\"
      },
      {
        \"title\": \"Feed B\",
        \"xmlUrl\": \"https://example.org/feed-b.xml\",
        \"htmlUrl\": \"https://example.org/b\"
      }
    ],
    \"start_immediately\": false
  }" | tee "${TMP_DIR}/source_pipeline.json"
```

## 2) Quelle lesen und Referenz-IDs merken

```bash
SOURCE_DATAFLOW_STATE_ID="$(python3 - "${TMP_DIR}/source_pipeline.json" <<'PY'
import json, sys
print(json.load(open(sys.argv[1]))["dataflow_state_id"])
PY
)"

SOURCE_DATAFLOW_ID="$(python3 - "${TMP_DIR}/source_pipeline.json" <<'PY'
import json, sys
print(json.load(open(sys.argv[1]))["dataflow_id"])
PY
)"

echo "SOURCE_DATAFLOW_STATE_ID=${SOURCE_DATAFLOW_STATE_ID}"
echo "SOURCE_DATAFLOW_ID=${SOURCE_DATAFLOW_ID}"
```

## 3) Auf Pipeline Fertigstellung warten

Der Klon soll auf fertiggestellten Daten der Quellpipeline aufbauen, weshalb auf den Status EVENT_COMPLETED.

## 4) Alternativen HDBSCAN-Dataflow anlegen

```bash
curl -sS -X POST \
  "${BASE_URL}${API_PREFIX}/dataflows" \
  -H "X-API-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d "{
    \"dataflow_id\": \"${HDBSCAN_DATAFLOW_ID}\",
    \"nodes\": [
      {\"plugin_worker_id\": \"FetchFeedItems1\", \"plugin_type\": \"FetchFeedItems\"},
      {\"plugin_worker_id\": \"EmbedData1\", \"plugin_type\": \"EmbedData\"},
      {\"plugin_worker_id\": \"ClusterPress1\", \"plugin_type\": \"Clustering_HDBSCAN\"}
    ],
    \"edges\": [
      {\"from\": \"FetchFeedItems1\", \"to\": \"EmbedData1\"},
      {\"from\": \"EmbedData1\", \"to\": \"ClusterPress1\"}
    ]
  }" | tee "${TMP_DIR}/hdbscan_dataflow.json"
```

## 5) Clone ausfuehren (DBSCAN -> HDBSCAN)

`parent_plugin_worker_ids` steuert, ab welchen Nodes und Nachfolgern der Re-Run-Reset passiert.

```bash
curl -sS -X POST \
  "${BASE_URL}${API_PREFIX}/pipelines/${SOURCE_PIPELINE_ID}/clone" \
  -H "X-API-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d "{
    \"new_pipeline_id\": \"${CLONE_PIPELINE_ID}\",
    \"dataflow_id\": \"${HDBSCAN_DATAFLOW_ID}\",
    \"plugin_config\": {
      \"ClusterPress1\": {\"min_cluster_size\": 2, \"min_samples\": 1, \"eps\": 0.0}
    },
    \"parent_plugin_worker_ids\": [\"EmbedData1\"]
  }" | tee "${TMP_DIR}/clone_pipeline.json"
```

## 6) Clone pruefen

```bash
CLONE_DATAFLOW_STATE_ID="$(python3 - "${TMP_DIR}/clone_pipeline.json" <<'PY'
import json, sys
print(json.load(open(sys.argv[1]))["dataflow_state_id"])
PY
)"

CLONE_DATAFLOW_ID="$(python3 - "${TMP_DIR}/clone_pipeline.json" <<'PY'
import json, sys
print(json.load(open(sys.argv[1]))["dataflow_id"])
PY
)"

echo "CLONE_DATAFLOW_STATE_ID=${CLONE_DATAFLOW_STATE_ID}"
echo "CLONE_DATAFLOW_ID=${CLONE_DATAFLOW_ID}"
```

`dataflow_state_id` muss neu sein, `dataflow_id` muss auf den HDBSCAN-Dataflow zeigen:

```bash
test "${SOURCE_DATAFLOW_STATE_ID}" != "${CLONE_DATAFLOW_STATE_ID}" && echo "OK: neuer State fuer Clone"
test "${CLONE_DATAFLOW_ID}" = "${HDBSCAN_DATAFLOW_ID}" && echo "OK: Clone nutzt HDBSCAN-Dataflow"
```

## 7) Dataflow-State des Clones ansehen

```bash
curl -sS -X GET \
  "${BASE_URL}${API_PREFIX}/dataflow-states/${CLONE_DATAFLOW_STATE_ID}" \
  -H "X-API-Key: ${API_KEY}" \
  -H "Accept: application/json"
```

Erwartung: mindestens die durch `parent_plugin_worker_ids` adressierten Nodes stehen auf `Not Started` und haben leere `io_transformation_states`.
Zusatzcheck: Der verwendete Dataflow enthaelt `ClusterPress1` mit `plugin_type` = `Clustering_HDBSCAN`.

## 8) Optional: Events fuer Quelle/Clone vergleichen

```bash
curl -sS -X GET \
  "${BASE_URL}${API_PREFIX}/events?pipeline_id=${SOURCE_PIPELINE_ID}&page=1&page_size=10" \
  -H "X-API-Key: ${API_KEY}" \
  -H "Accept: application/json"

curl -sS -X GET \
  "${BASE_URL}${API_PREFIX}/events?pipeline_id=${CLONE_PIPELINE_ID}&page=1&page_size=10" \
  -H "X-API-Key: ${API_KEY}" \
  -H "Accept: application/json"
```
