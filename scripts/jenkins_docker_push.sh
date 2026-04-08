#!/usr/bin/env bash
# Push nur gebaute Images (beide Tags: Tree-Short + SOFTWARE_VERSION).

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

push_if() {
  local flag="$1"
  local repo="$2"
  local tree_tag="$3"
  if [ "${flag}" != "1" ]; then
    return 0
  fi
  docker push "${repo}:${tree_tag}"
  docker push "${repo}:${SOFTWARE_VERSION}"
}

push_if "${BUILD_API:-0}" "${DOCKER_IMAGE_REPO_API}" "${TREE_API_LC}"
push_if "${BUILD_WORKER:-0}" "${DOCKER_IMAGE_REPO_RUNTIME}" "${TREE_WORKER_LC}"
push_if "${BUILD_EVENTSYSTEM:-0}" "${DOCKER_IMAGE_REPO_EVENTSYSTEM}" "${TREE_EVENTSYSTEM_LC}"
push_if "${BUILD_EVENT_BROKER:-0}" "${DOCKER_IMAGE_REPO_EVENT_BROKER}" "${TREE_EVENT_BROKER_LC}"
push_if "${BUILD_PLUGIN_FETCHFEEDITEMS:-0}" "${DOCKER_IMAGE_REPO_PLUGIN_FETCHFEEDITEMS}" "${TREE_PLUGIN_FETCH_LC}"
push_if "${BUILD_PLUGIN_EMBEDDATA:-0}" "${DOCKER_IMAGE_REPO_PLUGIN_EMBEDDATA}" "${TREE_PLUGIN_EMBED_LC}"
