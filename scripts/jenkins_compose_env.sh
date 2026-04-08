#!/usr/bin/env bash
# Exportiert DOCKER_IMAGE_* für docker-compose: Tree-Tag pro Service; bei nicht neu gebauten
# Images wird der Tag aus dem laufenden Container gelesen (sonst erwarteter Tree).

set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "${ROOT}"

# shellcheck source=/dev/null
. ./.jenkins_runtime.env
# shellcheck source=/dev/null
. ./.jenkins_build_plan.env

TREE_API_LC="$(echo "${TREE_API:?}" | tr '[:upper:]' '[:lower:]')"
TREE_WORKER_LC="$(echo "${TREE_WORKER:?}" | tr '[:upper:]' '[:lower:]')"
TREE_EVENT_BROKER_LC="$(echo "${TREE_EVENT_BROKER:?}" | tr '[:upper:]' '[:lower:]')"
TREE_EVENTSYSTEM_LC="$(echo "${TREE_EVENTSYSTEM:?}" | tr '[:upper:]' '[:lower:]')"
TREE_PLUGIN_FETCH_LC="$(echo "${TREE_PLUGIN_FETCHFEEDITEMS:?}" | tr '[:upper:]' '[:lower:]')"
TREE_PLUGIN_EMBED_LC="$(echo "${TREE_PLUGIN_EMBEDDATA:?}" | tr '[:upper:]' '[:lower:]')"

DOCKER_IMAGE_REPO_API="${DOCKER_IMAGE_REPO_API:-docker.io/crawlabase/dflowp-api}"
DOCKER_IMAGE_REPO_RUNTIME="${DOCKER_IMAGE_REPO_RUNTIME:-docker.io/crawlabase/dflowp-runtime}"
DOCKER_IMAGE_REPO_EVENTSYSTEM="${DOCKER_IMAGE_REPO_EVENTSYSTEM:-docker.io/crawlabase/dflowp-eventsystem}"
DOCKER_IMAGE_REPO_EVENT_BROKER="${DOCKER_IMAGE_REPO_EVENT_BROKER:-docker.io/crawlabase/dflowp-event-broker}"
DOCKER_IMAGE_REPO_PLUGIN_FETCHFEEDITEMS="${DOCKER_IMAGE_REPO_PLUGIN_FETCHFEEDITEMS:-docker.io/crawlabase/dflowp-plugin-fetchfeeditems}"
DOCKER_IMAGE_REPO_PLUGIN_EMBEDDATA="${DOCKER_IMAGE_REPO_PLUGIN_EMBEDDATA:-docker.io/crawlabase/dflowp-plugin-embeddata}"

tag_from_container() {
  local cname="$1"
  local fallback="$2"
  local img
  img="$(docker inspect -f '{{.Config.Image}}' "${cname}" 2>/dev/null || true)"
  if [[ -n "${img}" ]]; then
    echo "${img##*:}"
  else
    echo "${fallback}"
  fi
}

# Kanonischer Tag für Compose: neu gebaut = erwarteter Tree; sonst laufender Container
if [[ "${BUILD_API:-0}" = "1" ]]; then TAG_API="${TREE_API_LC}"; else TAG_API="$(tag_from_container dflowp-api "${TREE_API_LC}")"; fi
if [[ "${BUILD_WORKER:-0}" = "1" ]]; then TAG_WORKER="${TREE_WORKER_LC}"; else TAG_WORKER="$(tag_from_container dflowp-worker "${TREE_WORKER_LC}")"; fi
if [[ "${BUILD_EVENTSYSTEM:-0}" = "1" ]]; then TAG_EVENTSYSTEM="${TREE_EVENTSYSTEM_LC}"; else TAG_EVENTSYSTEM="$(tag_from_container dflowp-eventsystem "${TREE_EVENTSYSTEM_LC}")"; fi
if [[ "${BUILD_EVENT_BROKER:-0}" = "1" ]]; then TAG_EVENT_BROKER="${TREE_EVENT_BROKER_LC}"; else TAG_EVENT_BROKER="$(tag_from_container dflowp-event-broker "${TREE_EVENT_BROKER_LC}")"; fi
if [[ "${BUILD_PLUGIN_FETCHFEEDITEMS:-0}" = "1" ]]; then TAG_PF="${TREE_PLUGIN_FETCH_LC}"; else TAG_PF="$(tag_from_container dflowp-plugin-fetchfeeditems "${TREE_PLUGIN_FETCH_LC}")"; fi
if [[ "${BUILD_PLUGIN_EMBEDDATA:-0}" = "1" ]]; then TAG_PE="${TREE_PLUGIN_EMBED_LC}"; else TAG_PE="$(tag_from_container dflowp-plugin-embeddata "${TREE_PLUGIN_EMBED_LC}")"; fi

export DOCKER_IMAGE_API="${DOCKER_IMAGE_REPO_API}:${TAG_API}"
export DOCKER_IMAGE_RUNTIME="${DOCKER_IMAGE_REPO_RUNTIME}:${TAG_WORKER}"
export DOCKER_IMAGE_EVENTSYSTEM="${DOCKER_IMAGE_REPO_EVENTSYSTEM}:${TAG_EVENTSYSTEM}"
export DOCKER_IMAGE_EVENT_BROKER="${DOCKER_IMAGE_REPO_EVENT_BROKER}:${TAG_EVENT_BROKER}"
export DOCKER_IMAGE_PLUGIN_FETCHFEEDITEMS="${DOCKER_IMAGE_REPO_PLUGIN_FETCHFEEDITEMS}:${TAG_PF}"
export DOCKER_IMAGE_PLUGIN_EMBEDDATA="${DOCKER_IMAGE_REPO_PLUGIN_EMBEDDATA}:${TAG_PE}"
export SOFTWARE_VERSION

echo "Compose images:"
echo "  DOCKER_IMAGE_API=${DOCKER_IMAGE_API}"
echo "  DOCKER_IMAGE_RUNTIME=${DOCKER_IMAGE_RUNTIME}"
echo "  DOCKER_IMAGE_EVENTSYSTEM=${DOCKER_IMAGE_EVENTSYSTEM}"
echo "  DOCKER_IMAGE_EVENT_BROKER=${DOCKER_IMAGE_EVENT_BROKER}"
echo "  DOCKER_IMAGE_PLUGIN_FETCHFEEDITEMS=${DOCKER_IMAGE_PLUGIN_FETCHFEEDITEMS}"
echo "  DOCKER_IMAGE_PLUGIN_EMBEDDATA=${DOCKER_IMAGE_PLUGIN_EMBEDDATA}"
echo "  SOFTWARE_VERSION=${SOFTWARE_VERSION}"
