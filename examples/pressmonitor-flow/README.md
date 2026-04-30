# Beispiel: pressmonitor-flow

Dieses Beispiel zeigt einen kleinen Pressmonitor-Flow mit zwei Feeds, Datensatz-Anlage und Pipeline-Start.
Der Flow besteht aus `FetchFeedItems`, `EmbedData` und `Clustering_DBSCAN`.

## Ziel

- kleine Input-Daten in DFlowP anlegen
- Pipeline `pressmonitor-flow` erstellen
- Ausfuehrung nachvollziehen (mit Worker oder API-Alternative)

## 0) Variablen setzen

```bash
set -euo pipefail

export BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
export API_KEY="${API_KEY:-changeme}"
export API_PREFIX="/api/v1"

export EXAMPLE_ID="pressmonitor-flow"
export PIPELINE_ID="${EXAMPLE_ID}-$(date +%s)"
export INPUT_DATASET_ID="ds-${PIPELINE_ID}"

TMP_DIR="$(mktemp -d)"
echo "Arbeitsverzeichnis: ${TMP_DIR}"
```

## 1) API-Zugriff pruefen

```bash
curl -sS -X GET \
  "${BASE_URL}${API_PREFIX}/data?page=1&page_size=1" \
  -H "X-API-Key: ${API_KEY}" \
  -H "Accept: application/json"
```

## 2) Input-Dataset mit wenigen Feeds anlegen

Wichtig: Fuer `doc_type=dataset` wird hier `rows` genutzt (kleiner Testdatensatz).
Die beiden Feeds stammen aus `examples/example_feeds/inputdata_set_big.json` und sind reale RSS-Quellen.

```bash
curl -sS -X POST \
  "${BASE_URL}${API_PREFIX}/data" \
  -H "X-API-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d "{
    \"doc_type\": \"dataset\",
    \"id\": \"${INPUT_DATASET_ID}\",
    \"rows\": [
      {
        \"title\": \"tagesschau.de\",
        \"xmlUrl\": \"https://www.tagesschau.de/index~rss2.xml\",
        \"htmlUrl\": \"https://www.tagesschau.de/\",
        \"topic\": \"news\"
      },
      {
        \"title\": \"DER SPIEGEL - Schlagzeilen\",
        \"xmlUrl\": \"https://www.spiegel.de/schlagzeilen/index.rss\",
        \"htmlUrl\": \"https://www.spiegel.de/\",
        \"topic\": \"news\"
      }
    ]
  }" | tee "${TMP_DIR}/dataset.json"
```

## 3) Pipeline erstellen (`pressmonitor-flow`)

Die API akzeptiert im `dataflow` `plugin_worker_id/plugin_type` (empfohlen).

```bash
curl -sS -X POST \
  "${BASE_URL}${API_PREFIX}/pipelines" \
  -H "X-API-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d "{
    \"pipeline_id\": \"${PIPELINE_ID}\",
    \"software_version\": \"0.1.0\",
    \"input_dataset_id\": \"${INPUT_DATASET_ID}\",
    \"dataflow\": {
      \"nodes\": [
        {\"plugin_worker_id\": \"FetchFeedItems1\", \"plugin_type\": \"FetchFeedItems\"},
        {\"plugin_worker_id\": \"EmbedData1\", \"plugin_type\": \"EmbedData\"},
        {\"plugin_worker_id\": \"ClusterPress1\", \"plugin_type\": \"Clustering_DBSCAN\"}
      ],
      \"edges\": [
        {\"from\": \"FetchFeedItems1\", \"to\": \"EmbedData1\"},
        {\"from\": \"EmbedData1\", \"to\": \"ClusterPress1\"}
      ]
    },
    \"plugin_config\": {
      \"FetchFeedItems1\": {\"max_items_per_feed\": 3},
      \"EmbedData1\": {\"model\": \"text-embedding-3-small\"},
      \"ClusterPress1\": {\"eps\": 0.45, \"min_samples\": 2, \"metric\": \"cosine\"}
    },
    \"start_immediately\": true
  }" | tee "${TMP_DIR}/pipeline.json"
```

## 4) Referenzen aus Pipeline lesen

```bash
DATAFLOW_ID="$(python3 - "${TMP_DIR}/pipeline.json" <<'PY'
import json, sys
print(json.load(open(sys.argv[1]))["dataflow_id"])
PY
)"

PLUGIN_CONFIGURATION_ID="$(python3 - "${TMP_DIR}/pipeline.json" <<'PY'
import json, sys
print(json.load(open(sys.argv[1]))["plugin_configuration_id"])
PY
)"

DATAFLOW_STATE_ID="$(python3 - "${TMP_DIR}/pipeline.json" <<'PY'
import json, sys
print(json.load(open(sys.argv[1]))["dataflow_state_id"])
PY
)"

echo "DATAFLOW_ID=${DATAFLOW_ID}"
echo "PLUGIN_CONFIGURATION_ID=${PLUGIN_CONFIGURATION_ID}"
echo "DATAFLOW_STATE_ID=${DATAFLOW_STATE_ID}"
```

## 5) Detail-Requests zur Kontrolle

```bash
curl -sS -X GET \
  "${BASE_URL}${API_PREFIX}/pipelines/${PIPELINE_ID}" \
  -H "X-API-Key: ${API_KEY}" \
  -H "Accept: application/json"

curl -sS -X GET \
  "${BASE_URL}${API_PREFIX}/dataflow-states/${DATAFLOW_STATE_ID}" \
  -H "X-API-Key: ${API_KEY}" \
  -H "Accept: application/json"

curl -sS -X GET \
  "${BASE_URL}${API_PREFIX}/events?pipeline_id=${PIPELINE_ID}&page=1&page_size=20" \
  -H "X-API-Key: ${API_KEY}" \
  -H "Accept: application/json"
```

## 6) Ausfuehrung: zwei Wege

### Weg A (empfohlen): Worker laeuft bereits

Wenn ein Worker aktiv ist, verarbeitet er `pending`/`running` Pipelines und schreibt Events/Dataflow-State.

```bash
for i in $(seq 1 10); do
  echo "Polling #${i}"
  curl -sS -X GET \
    "${BASE_URL}${API_PREFIX}/events?pipeline_id=${PIPELINE_ID}&page=1&page_size=5" \
    -H "X-API-Key: ${API_KEY}" \
    -H "Accept: application/json"
  sleep 2
done
```
