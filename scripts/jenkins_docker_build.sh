#!/usr/bin/env bash
# Jenkins: Selektive docker build mit Tree-Tag (sichtbar) + SOFTWARE_VERSION-Tag.

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

LABEL_VER="org.opencontainers.image.version=${SOFTWARE_VERSION:?}"

build_if() {
  local flag="$1"
  local repo="$2"
  local target="$3"
  local tree_tag="$4"
  if [ "${flag}" != "1" ]; then
    echo "Überspringe docker build: target=${target}"
    return 0
  fi
  echo "docker build --target ${target} -> ${repo}:${tree_tag} und ${repo}:${SOFTWARE_VERSION}"
  docker build --target "${target}" \
    -t "${repo}:${tree_tag}" \
    -t "${repo}:${SOFTWARE_VERSION}" \
    --label "${LABEL_VER}" \
    .
}

build_if "${BUILD_API:-0}" "${DOCKER_IMAGE_REPO_API}" "api" "${TREE_API_LC}"
build_if "${BUILD_WORKER:-0}" "${DOCKER_IMAGE_REPO_RUNTIME}" "runtime" "${TREE_WORKER_LC}"
build_if "${BUILD_EVENTSYSTEM:-0}" "${DOCKER_IMAGE_REPO_EVENTSYSTEM}" "eventsystem" "${TREE_EVENTSYSTEM_LC}"
build_if "${BUILD_EVENT_BROKER:-0}" "${DOCKER_IMAGE_REPO_EVENT_BROKER}" "event-broker" "${TREE_EVENT_BROKER_LC}"
build_if "${BUILD_PLUGIN_FETCHFEEDITEMS:-0}" "${DOCKER_IMAGE_REPO_PLUGIN_FETCHFEEDITEMS}" "plugin-fetchfeeditems" "${TREE_PLUGIN_FETCH_LC}"
build_if "${BUILD_PLUGIN_EMBEDDATA:-0}" "${DOCKER_IMAGE_REPO_PLUGIN_EMBEDDATA}" "plugin-embeddata" "${TREE_PLUGIN_EMBED_LC}"

# Nächster Lauf: Library-Änderung erkennen (eigene Keys, kein Überschreiben beim Sourcen)
printf 'LAST_TREE_DFLOWP_CORE=%s\nLAST_TREE_DFLOWP_PROCESSRUNTIME=%s\n' \
  "${TREE_DFLOWP_CORE}" "${TREE_DFLOWP_PROCESSRUNTIME}" > .jenkins_last_trees
echo "Gespeichert: .jenkins_last_trees (für LIB_FORCE-Vergleich beim nächsten Lauf)"
