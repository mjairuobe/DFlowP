#!/usr/bin/env bash
# Jenkins: Prüft laufende Container – wenn alle DFlowP-Services + Mongo mit IMAGE_TAG
# laufen, Pipeline überspringen (Datei .jenkins_skip_pipeline: true|false).
#
# Voraussetzung: .jenkins_runtime.env (IMAGE_TAG) existiert im Repo-Root.

set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "${ROOT}"

if [ ! -f .jenkins_runtime.env ]; then
  echo "false" > .jenkins_skip_pipeline
  echo "jenkins_check_skip_deploy: keine .jenkins_runtime.env – kein Skip"
  exit 0
fi

# shellcheck source=/dev/null
. ./.jenkins_runtime.env

TAG="${IMAGE_TAG:?IMAGE_TAG fehlt}"
SKIP_FILE=".jenkins_skip_pipeline"

normalize_img() {
  echo "$1" | sed 's|^docker.io/||' | sed 's|^registry-1.docker.io/||'
}

IMAGES="$(docker ps --format '{{.Image}}' 2>/dev/null || true)"

has_exact_image() {
  # $1 = crawlabase/dflowp-api:TAG (ohne docker.io)
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

has_mongo_container() {
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

# Gleiche Repos wie Jenkinsfile DOCKER_IMAGE_REPO_* (ohne Registry-Host, nur crawlabase/…)
REQUIRED=(
  "crawlabase/dflowp-api:${TAG}"
  "crawlabase/dflowp-runtime:${TAG}"
  "crawlabase/dflowp-eventsystem:${TAG}"
  "crawlabase/dflowp-event-broker:${TAG}"
  "crawlabase/dflowp-plugin-fetchfeeditems:${TAG}"
  "crawlabase/dflowp-plugin-embeddata:${TAG}"
)

echo "=== Laufende Container-Images (docker ps) ==="
echo "$IMAGES" | sed '/^$/d' || true
echo "=== Prüfung gegen SOFTWARE_VERSION / IMAGE_TAG=${TAG} ==="

MISSING=()
for img in "${REQUIRED[@]}"; do
  if ! has_exact_image "$img"; then
    MISSING+=("$img")
  fi
done

if ! has_mongo_container; then
  MISSING+=("(kein Mongo-Container mit Image mongo:* o. Ä.)")
fi

if [ ${#MISSING[@]} -eq 0 ]; then
  echo "true" > "${SKIP_FILE}"
  echo "SKIP: Alle DFlowP-Services laufen bereits mit Tag ${TAG} (entspricht SOFTWARE_VERSION). Pipeline wird übersprungen."
else
  echo "false" > "${SKIP_FILE}"
  echo "Kein Skip – fehlend oder falsche Version:"
  for m in "${MISSING[@]}"; do
    echo "  - $m"
  done
fi
