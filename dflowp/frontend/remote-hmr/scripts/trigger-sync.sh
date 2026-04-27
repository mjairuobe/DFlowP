#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${1:-$(dirname "$0")/../.env.remote-hmr.example}"
REF_OVERRIDE="${2:-}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Env file not found: $ENV_FILE" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

: "${DFLOWP_REMOTE_HMR_SUPERVISOR_URL:?missing DFLOWP_REMOTE_HMR_SUPERVISOR_URL}"

SUPERVISOR_URL="${DFLOWP_REMOTE_HMR_SUPERVISOR_URL%/}"
REF_TO_SYNC="${REF_OVERRIDE:-${DFLOWP_REMOTE_HMR_REF:-main}}"

AUTH_ARGS=()
if [[ -n "${DFLOWP_REMOTE_HMR_SHARED_SECRET:-}" ]]; then
  AUTH_ARGS=(-H "X-Shared-Secret: ${DFLOWP_REMOTE_HMR_SHARED_SECRET}")
fi

echo "Triggering remote sync for ref: ${REF_TO_SYNC}"
RUN_ID="$(
  curl -fsS -X POST "${SUPERVISOR_URL}/sync" \
    "${AUTH_ARGS[@]}" \
    -H "Content-Type: application/json" \
    -d "{\"ref\":\"${REF_TO_SYNC}\"}" \
  | jq -r '.runId'
)"

if [[ -z "$RUN_ID" || "$RUN_ID" == "null" ]]; then
  echo "No runId returned by supervisor." >&2
  exit 1
fi

echo "runId=${RUN_ID}"
echo "Streaming events until terminal state..."

curl -fsS -N "${SUPERVISOR_URL}/events?runId=${RUN_ID}" \
  "${AUTH_ARGS[@]}" \
| awk '
  /^data:/ {
    sub(/^data:[[:space:]]*/, "", $0);
    print;
    if ($0 ~ /(READY|BUILD_ERROR|CRASHED)/) exit 0;
  }
'

FINAL_STATE="$(
  curl -fsS "${SUPERVISOR_URL}/status" \
    "${AUTH_ARGS[@]}" \
  | jq -r '.state'
)"

echo "Final state: ${FINAL_STATE}"
if [[ "${FINAL_STATE}" != "READY" ]]; then
  echo "Remote sync did not end in READY." >&2
  exit 1
fi
