#!/usr/bin/env bash
# Jenkins: SOFTWARE_VERSION (vMAJOR.MINOR.BUILD), Tree-Short-Hashes (5 Hex) pro Subdir.
#
# SOFTWARE_VERSION: höchster vX.Y.Z Tag → vX.Y.<BUILDNUM>, BUILDNUM = git rev-list seit Tag (branch-unabhängig).
# Ohne Tag: v0.1.<BUILDNUM> mit BUILDNUM = rev-list --all --count.
#
# Schreibt .jenkins_runtime.env

set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "${ROOT}"

# Jenkins: shallow clone / Checkout ohne Tag-Refs → Tags existieren auf GitHub, lokal fehlen sie.
# Tags sind repo-weit; Branch des Tags ist irrelevant, solange der Tag auf origin liegt.
if git rev-parse --git-dir >/dev/null 2>&1; then
  if git remote get-url origin >/dev/null 2>&1; then
    git fetch origin --tags --force 2>/dev/null || true
  else
    git fetch --tags --force 2>/dev/null || true
  fi
fi

tree_short_5() {
  local path="$1"
  local full
  if ! full="$(git rev-parse "HEAD:${path}" 2>/dev/null)"; then
    echo "00000"
    return
  fi
  # 40-stelliger Hex-String → erste 5 Zeichen (klein, wie docker tags)
  echo "${full:0:5}" | tr '[:upper:]' '[:lower:]'
}

LATEST_TAG="$(git tag -l 'v[0-9]*.[0-9]*.[0-9]*' 2>/dev/null | sort -V | tail -1)"

if [[ -n "${LATEST_TAG}" ]]; then
  if [[ "${LATEST_TAG}" =~ ^v([0-9]+)\.([0-9]+)\.([0-9]+)$ ]]; then
    VMAJOR="${BASH_REMATCH[1]}"
    VMINOR="${BASH_REMATCH[2]}"
  else
    VMAJOR="0"
    VMINOR="1"
  fi
  BUILD_NUM="$(git rev-list --count --all "${LATEST_TAG}..HEAD" 2>/dev/null || echo "0")"
else
  VMAJOR="0"
  VMINOR="1"
  BUILD_NUM="$(git rev-list --all --count 2>/dev/null || echo "0")"
fi

SOFTWARE_VERSION="v${VMAJOR}.${VMINOR}.${BUILD_NUM}"

# Pro Image/Package (Pfade relativ zum Repo-Root)
TREE_API="$(tree_short_5 "dflowp/api")"
TREE_WORKER="$(tree_short_5 "dflowp/worker")"
TREE_EVENT_BROKER="$(tree_short_5 "dflowp/event_broker")"
TREE_EVENTSYSTEM="$(tree_short_5 "dflowp/eventsystem")"
TREE_PLUGIN_EMBEDDATA="$(tree_short_5 "dflowp/plugin_embeddata")"
TREE_PLUGIN_FETCHFEEDITEMS="$(tree_short_5 "dflowp/plugin_fetchfeeditems")"
TREE_DFLOWP_CORE="$(tree_short_5 "dflowp-packages/dflowp-core")"
TREE_DFLOWP_PROCESSRUNTIME="$(tree_short_5 "dflowp-packages/dflowp-processruntime")"

# Kanonisches Image-Tag für „sichtbar“ / Vergleich = Tree-Hash (pro Service unterschiedlich).
# IMAGE_TAG bleibt für Abwärtskompatibilität = SOFTWARE_VERSION (z. B. für Logs).
IMAGE_TAG="${SOFTWARE_VERSION}"

echo "LATEST_TAG=${LATEST_TAG:-<keiner>}"
echo "SOFTWARE_VERSION=${SOFTWARE_VERSION} (BUILD_NUM=${BUILD_NUM})"
echo "Tree shorts: api=${TREE_API} worker=${TREE_WORKER} eventsystem=${TREE_EVENTSYSTEM} event_broker=${TREE_EVENT_BROKER} plugin_fetch=${TREE_PLUGIN_FETCHFEEDITEMS} plugin_embed=${TREE_PLUGIN_EMBEDDATA} core=${TREE_DFLOWP_CORE} pr=${TREE_DFLOWP_PROCESSRUNTIME}"

{
  printf 'SOFTWARE_VERSION=%s\n' "${SOFTWARE_VERSION}"
  printf 'BUILD_NUM=%s\n' "${BUILD_NUM}"
  printf 'LATEST_TAG=%s\n' "${LATEST_TAG:-}"
  printf 'IMAGE_TAG=%s\n' "${IMAGE_TAG}"
  printf 'TREE_API=%s\n' "${TREE_API}"
  printf 'TREE_WORKER=%s\n' "${TREE_WORKER}"
  printf 'TREE_EVENT_BROKER=%s\n' "${TREE_EVENT_BROKER}"
  printf 'TREE_EVENTSYSTEM=%s\n' "${TREE_EVENTSYSTEM}"
  printf 'TREE_PLUGIN_EMBEDDATA=%s\n' "${TREE_PLUGIN_EMBEDDATA}"
  printf 'TREE_PLUGIN_FETCHFEEDITEMS=%s\n' "${TREE_PLUGIN_FETCHFEEDITEMS}"
  printf 'TREE_DFLOWP_CORE=%s\n' "${TREE_DFLOWP_CORE}"
  printf 'TREE_DFLOWP_PROCESSRUNTIME=%s\n' "${TREE_DFLOWP_PROCESSRUNTIME}"
} > .jenkins_runtime.env
