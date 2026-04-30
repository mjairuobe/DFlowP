# Beispiel: pressmonitor-pipeline-testconf-clone-flow

Dieses Beispiel zeigt einen Clone fuer Testkonfigurationen.
Die Pipeline bleibt beim Algorithmus `Clustering_DBSCAN`, aber die Plugin-Konfiguration wird angepasst (z. B. `eps`).

## Ziel

- Quellpipeline mit DBSCAN anlegen
- Clone mit geaenderter DBSCAN-Konfiguration erstellen
- neue Referenzen (`plugin_configuration_id`, `dataflow_state_id`) verifizieren

## 0) Variablen setzen

```bash
set -euo pipefail

export BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
export API_KEY="${API_KEY:-changeme}"
export API_PREFIX="/api/v1"

export EXAMPLE_ID="pressmonitor-pipeline-testconf-clone-flow"
export SOURCE_PIPELINE_ID="${EXAMPLE_ID}-src-$(date +%s)"
export TESTCLONE_PIPELINE_ID="${EXAMPLE_ID}-testclone-$(date +%s)"
export INPUT_DATASET_ID="ds-${SOURCE_PIPELINE_ID}"

TMP_DIR="$(mktemp -d)"
echo "Arbeitsverzeichnis: ${TMP_DIR}"
```

## 1) Quellpipeline anlegen

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
      {\"title\": \"Feed Test 1\", \"xmlUrl\": \"https://example.org/feed1.xml\"},
      {\"title\": \"Feed Test 2\", \"xmlUrl\": \"https://example.org/feed2.xml\"}
    ],
    \"start_immediately\": false
  }" | tee "${TMP_DIR}/source_pipeline.json"
```

## 2) Auf Pipeline Fertigstellung warten

Der Klon soll auf fertiggestellten Daten der Quellpipeline aufbauen, weshalb auf den Status EVENT_COMPLETED. Liegt der Status bei EVENT_FAILED, ist ein Fehler mit der Software vorhanden.

## 3) Test-Clone mit Config-Override erstellen

`plugin_config` wird auf die bestehende Konfiguration gemerged.

```bash
curl -sS -X POST \
  "${BASE_URL}${API_PREFIX}/pipelines/${SOURCE_PIPELINE_ID}/clone" \
  -H "X-API-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d "{
    \"new_pipeline_id\": \"${TESTCLONE_PIPELINE_ID}\",
    \"plugin_config\": {
      \"ClusterPress1\": {\"eps\": 0.35, \"min_samples\": 3, \"metric\": \"cosine\"}
    },
    \"parent_plugin_worker_ids\": [\"ClusterPress1\"]
  }" | tee "${TMP_DIR}/testclone_pipeline.json"
```

## 4) Referenzen aus Quelle und Clone vergleichen

```bash
SOURCE_PLUGIN_CONFIGURATION_ID="$(python3 - "${TMP_DIR}/source_pipeline.json" <<'PY'
import json, sys
print(json.load(open(sys.argv[1]))["plugin_configuration_id"])
PY
)"

CLONE_PLUGIN_CONFIGURATION_ID="$(python3 - "${TMP_DIR}/testclone_pipeline.json" <<'PY'
import json, sys
print(json.load(open(sys.argv[1]))["plugin_configuration_id"])
PY
)"

CLONE_DATAFLOW_ID="$(python3 - "${TMP_DIR}/testclone_pipeline.json" <<'PY'
import json, sys
print(json.load(open(sys.argv[1]))["dataflow_id"])
PY
)"

CLONE_DATAFLOW_STATE_ID="$(python3 - "${TMP_DIR}/testclone_pipeline.json" <<'PY'
import json, sys
print(json.load(open(sys.argv[1]))["dataflow_state_id"])
PY
)"

echo "SOURCE_PLUGIN_CONFIGURATION_ID=${SOURCE_PLUGIN_CONFIGURATION_ID}"
echo "CLONE_PLUGIN_CONFIGURATION_ID=${CLONE_PLUGIN_CONFIGURATION_ID}"
echo "CLONE_DATAFLOW_ID=${CLONE_DATAFLOW_ID}"
echo "CLONE_DATAFLOW_STATE_ID=${CLONE_DATAFLOW_STATE_ID}"

SOURCE_DATAFLOW_ID="$(python3 - "${TMP_DIR}/source_pipeline.json" <<'PY'
import json, sys
print(json.load(open(sys.argv[1]))["dataflow_id"])
PY
)"

test "${CLONE_DATAFLOW_ID}" = "${SOURCE_DATAFLOW_ID}" && echo "OK: Clone nutzt denselben DBSCAN-Dataflow"
test "${SOURCE_PLUGIN_CONFIGURATION_ID}" != "${CLONE_PLUGIN_CONFIGURATION_ID}" && echo "OK: neue Plugin-Konfiguration erzeugt"
```

## 5) Effektive Clone-Konfiguration lesen

```bash
curl -sS -X GET \
  "${BASE_URL}${API_PREFIX}/plugin-configurations/${CLONE_PLUGIN_CONFIGURATION_ID}" \
  -H "X-API-Key: ${API_KEY}" \
  -H "Accept: application/json"
```

## 6) Auf Pipeline Fertigstellung warten

Auf den Status EVENT_COMPLETED warten, um die Daten auszuwerten. Liegt der Status bei EVENT_FAILED, ist ein Fehler mit der Software vorhanden.

## 7) Clone-Dataflow-State lesen

```bash
curl -sS -X GET \
  "${BASE_URL}${API_PREFIX}/dataflow-states/${CLONE_DATAFLOW_STATE_ID}" \
  -H "X-API-Key: ${API_KEY}" \
  -H "Accept: application/json"
```

Erwartung:

- Nodes entsprechen weiterhin dem DBSCAN-Dataflow (inkl. `ClusterPress1`)
- Nodes, die neu angestossen werden, sind auf `Not Started`
- `io_transformation_states` der neu zu berechnenden Nodes sind leer

## 6) Hinweis zur realen Ausfuehrung

Das Clone-Setup ist per API vollstaendig. Die tatsaechliche Berechnung erfolgt erst, wenn der Worker laeuft.
Falls kein Worker verfuegbar ist, kann der Ablauf wie im Beispiel `pressmonitor-flow` ueber `POST /events` plus optionales `PATCH /dataflow-states/{id}` nachvollziehbar simuliert werden.
