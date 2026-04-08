#!/usr/bin/env bash
# Jenkins: Skip? Force full rebuild (Libraries)? Welche docker build Ziele?
#
# Liest .jenkins_runtime.env (von jenkins_resolve_version.sh).
# Optional .jenkins_last_trees: TREE_DFLOWP_CORE=... TREE_DFLOWP_PROCESSRUNTIME=...
#
# Schreibt: .jenkins_skip_pipeline, .jenkins_build_plan.env

set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "${ROOT}"

SKIP_FILE=".jenkins_skip_pipeline"
PLAN_FILE=".jenkins_build_plan.env"
LAST_TREES=".jenkins_last_trees"

if [ ! -f .jenkins_runtime.env ]; then
  echo "false" > "${SKIP_FILE}"
  echo "LIB_FORCE=1" > "${PLAN_FILE}"
  echo "jenkins_build_plan: keine .jenkins_runtime.env"
  exit 0
fi

# shellcheck source=/dev/null
. ./.jenkins_runtime.env

normalize_img() {
  echo "$1" | sed 's|^docker.io/||' | sed 's|^registry-1.docker.io/||'
}

# Kleinbuchstaben für Vergleich mit docker (Hex)
TREE_API_LC="$(echo "${TREE_API:?}" | tr '[:upper:]' '[:lower:]')"
TREE_WORKER_LC="$(echo "${TREE_WORKER:?}" | tr '[:upper:]' '[:lower:]')"
TREE_EVENT_BROKER_LC="$(echo "${TREE_EVENT_BROKER:?}" | tr '[:upper:]' '[:lower:]')"
TREE_EVENTSYSTEM_LC="$(echo "${TREE_EVENTSYSTEM:?}" | tr '[:upper:]' '[:lower:]')"
TREE_PLUGIN_FETCH_LC="$(echo "${TREE_PLUGIN_FETCHFEEDITEMS:?}" | tr '[:upper:]' '[:lower:]')"
TREE_PLUGIN_EMBED_LC="$(echo "${TREE_PLUGIN_EMBEDDATA:?}" | tr '[:upper:]' '[:lower:]')"

IMAGES="$(docker ps --format '{{.Image}}' 2>/dev/null || true)"

has_tag_running() {
  local want
  want="$(normalize_img "$1")"
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    local n
    n="$(normalize_img "$line")"
    if [ "$n" = "$want" ]; then
      return 0
    fi
  done <<< "$IMAGES"
  return 1
}

repo_for() {
  case "$1" in
    api) echo "crawlabase/dflowp-api" ;;
    worker) echo "crawlabase/dflowp-runtime" ;;
    eventsystem) echo "crawlabase/dflowp-eventsystem" ;;
    event-broker) echo "crawlabase/dflowp-event-broker" ;;
    plugin-fetchfeeditems) echo "crawlabase/dflowp-plugin-fetchfeeditems" ;;
    plugin-embeddata) echo "crawlabase/dflowp-plugin-embeddata" ;;
    *) echo "" ;;
  esac
}

has_mongo() {
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    local n
    n="$(normalize_img "$line")"
    case "$n" in
      mongo:*|library/mongo:*|bitnami/mongodb:*|bitnami/mongo:*) return 0 ;;
    esac
  done <<< "$IMAGES"
  return 1
}

LIB_FORCE=0
if [ -f "${LAST_TREES}" ]; then
  # shellcheck source=/dev/null
  . "${LAST_TREES}"
  LAST_CORE="${LAST_TREE_DFLOWP_CORE:-}"
  LAST_PR="${LAST_TREE_DFLOWP_PROCESSRUNTIME:-}"
  if [ "${TREE_DFLOWP_CORE}" != "${LAST_CORE}" ] || [ "${TREE_DFLOWP_PROCESSRUNTIME}" != "${LAST_PR}" ]; then
    LIB_FORCE=1
    echo "LIB_FORCE=1 (dflowp-packages geändert: core ${LAST_CORE:-∅}->${TREE_DFLOWP_CORE}, pr ${LAST_PR:-∅}->${TREE_DFLOWP_PROCESSRUNTIME})"
  fi
else
  LIB_FORCE=1
  echo "LIB_FORCE=1 (kein ${LAST_TREES} – erster Lauf / frischer Workspace)"
fi

SERVICES=(api worker eventsystem event-broker plugin-fetchfeeditems plugin-embeddata)
ALL_CURRENT=1
for svc in "${SERVICES[@]}"; do
  R="$(repo_for "${svc}")"
  case "${svc}" in
    api) TAG="${TREE_API_LC}" ;;
    worker) TAG="${TREE_WORKER_LC}" ;;
    eventsystem) TAG="${TREE_EVENTSYSTEM_LC}" ;;
    event-broker) TAG="${TREE_EVENT_BROKER_LC}" ;;
    plugin-fetchfeeditems) TAG="${TREE_PLUGIN_FETCH_LC}" ;;
    plugin-embeddata) TAG="${TREE_PLUGIN_EMBED_LC}" ;;
  esac
  FULL="${R}:${TAG}"
  if ! has_tag_running "${FULL}"; then
    ALL_CURRENT=0
    echo "Nicht aktuell: ${FULL}"
  fi
done

if ! has_mongo; then
  ALL_CURRENT=0
  echo "Mongo-Container fehlt"
fi

if [ "${LIB_FORCE}" -eq 0 ] && [ "${ALL_CURRENT}" -eq 1 ]; then
  echo "true" > "${SKIP_FILE}"
  echo "SKIP: Alle Services mit Tree-Tags; Libraries unverändert."
else
  echo "false" > "${SKIP_FILE}"
fi

: > "${PLAN_FILE}"
echo "LIB_FORCE=${LIB_FORCE}" >> "${PLAN_FILE}"

BUILD_API=0
BUILD_WORKER=0
BUILD_EVENTSYSTEM=0
BUILD_EVENT_BROKER=0
BUILD_PLUGIN_FETCHFEEDITEMS=0
BUILD_PLUGIN_EMBEDDATA=0

if [ "${LIB_FORCE}" -eq 1 ]; then
  BUILD_API=1
  BUILD_WORKER=1
  BUILD_EVENTSYSTEM=1
  BUILD_EVENT_BROKER=1
  BUILD_PLUGIN_FETCHFEEDITEMS=1
  BUILD_PLUGIN_EMBEDDATA=1
else
  for svc in "${SERVICES[@]}"; do
    R="$(repo_for "${svc}")"
    case "${svc}" in
      api) TAG="${TREE_API_LC}" ;;
      worker) TAG="${TREE_WORKER_LC}" ;;
      eventsystem) TAG="${TREE_EVENTSYSTEM_LC}" ;;
      event-broker) TAG="${TREE_EVENT_BROKER_LC}" ;;
      plugin-fetchfeeditems) TAG="${TREE_PLUGIN_FETCH_LC}" ;;
      plugin-embeddata) TAG="${TREE_PLUGIN_EMBED_LC}" ;;
    esac
    if has_tag_running "${R}:${TAG}"; then
      continue
    fi
    case "${svc}" in
      api) BUILD_API=1 ;;
      worker) BUILD_WORKER=1 ;;
      eventsystem) BUILD_EVENTSYSTEM=1 ;;
      event-broker) BUILD_EVENT_BROKER=1 ;;
      plugin-fetchfeeditems) BUILD_PLUGIN_FETCHFEEDITEMS=1 ;;
      plugin-embeddata) BUILD_PLUGIN_EMBEDDATA=1 ;;
    esac
  done
fi

{
  echo "BUILD_API=${BUILD_API}"
  echo "BUILD_WORKER=${BUILD_WORKER}"
  echo "BUILD_EVENTSYSTEM=${BUILD_EVENTSYSTEM}"
  echo "BUILD_EVENT_BROKER=${BUILD_EVENT_BROKER}"
  echo "BUILD_PLUGIN_FETCHFEEDITEMS=${BUILD_PLUGIN_FETCHFEEDITEMS}"
  echo "BUILD_PLUGIN_EMBEDDATA=${BUILD_PLUGIN_EMBEDDATA}"
} >> "${PLAN_FILE}"

echo "=== ${PLAN_FILE} ==="
cat "${PLAN_FILE}"
echo "=== ${SKIP_FILE} ==="
cat "${SKIP_FILE}"
