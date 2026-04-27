# CI-Optimierungsplan: Registry-Cache mit Fallback (Branch -> main)

## 1) Ziel / Problem

Die Build-Zeit der Stack-Pipeline soll sinken, ohne die Build-Deterministik zu verlieren. Aktuell wird ein Registry-Cache pro Service genutzt, aber ohne Branch-Bezug. Dadurch entstehen zwei Probleme:

- Feature-Branches koennen sich gegenseitig Cache-Layer "ueberschreiben" (Cache-Noise).
- Ein sauberer Fallback auf einen stabilen `main`-Cache ist nicht explizit modelliert.

Ziel ist ein **Branch-spezifischer Cache mit automatischem Fallback auf `main`**, damit neue Branches schnell starten und zugleich von bereits aufgebauten `main`-Layern profitieren.

## 2) Ist-Zustand (kurz)

Im `Jenkinsfile.stack` wird im Stage `Build images (buildx parallel + registry cache/push)` aktuell pro Service ein einzelner Cache-Ref verwendet:

- `--cache-from type=registry,ref=${DOCKERHUB_CACHE_REPO}:${svc}`
- `--cache-to type=registry,ref=${DOCKERHUB_CACHE_REPO}:${svc},mode=max`

Das ist funktional, trennt aber Branches nicht voneinander und hat keinen expliziten Branch->main-Fallback.

## 3) Soll-Zustand / Design

### Design-Prinzip

Pro Service werden zwei Cache-Quellen genutzt:

1. **Branch-Cache (bevorzugt)**: `${DOCKERHUB_CACHE_REPO}:${svc}-branch-${CACHE_BRANCH_SLUG}`
2. **main-Cache (Fallback)**: `${DOCKERHUB_CACHE_REPO}:${svc}-main`

Beim Build gilt:

- Immer zuerst Branch-Cache lesen (`cache-from #1`).
- Danach `main`-Cache lesen (`cache-from #2`).
- Immer in den Branch-Cache schreiben (`cache-to branch`).
- Nur auf `main` zusaetzlich den `main`-Cache aktualisieren (`cache-to main`).

### Erwarteter Effekt

- Feature-Branches profitieren direkt vom warmen `main`-Cache.
- Branch-spezifische Layer bleiben isoliert.
- Auf `main` wird der "goldene" Fallback-Cache kontinuierlich erneuert.

## 4) Konkrete Jenkinsfile-Aenderungen (inkl. Beispiel-Snippets)

### A) Stage `Prepare version & image env`: Cache-Scopes ergaenzen

In `Jenkinsfile.stack` im Shell-Block der Stage `Prepare version & image env`:

```bash
# Branch-Name fuer Cache bestimmen (PR-Branch bevorzugen)
RAW_BRANCH="${CHANGE_BRANCH:-${BRANCH_NAME:-detached}}"
# Sanitize: lowercase, nur [a-z0-9_.-], Trennzeichen vereinheitlichen
CACHE_BRANCH_SLUG=$(printf '%s' "${RAW_BRANCH}" \
  | tr '[:upper:]' '[:lower:]' \
  | tr -cs 'a-z0-9_.-' '-' \
  | sed 's/^-*//; s/-*$//' \
  | cut -c1-40)
[ -n "${CACHE_BRANCH_SLUG}" ] || CACHE_BRANCH_SLUG="detached"

CACHE_MAIN_SLUG="main"
IS_MAIN_BRANCH=0
[ "${CACHE_BRANCH_SLUG}" = "${CACHE_MAIN_SLUG}" ] && IS_MAIN_BRANCH=1

cat >> .jenkins_runtime.env <<EOF
CACHE_BRANCH_SLUG=${CACHE_BRANCH_SLUG}
CACHE_MAIN_SLUG=${CACHE_MAIN_SLUG}
IS_MAIN_BRANCH=${IS_MAIN_BRANCH}
EOF
```

### B) Stage `Build images (buildx parallel + registry cache/push)`: dual `cache-from`

Im `build_target()`-Block:

```bash
build_target() {
  IFS='|' read -r svc dockerfile image <<< "$1"

  cache_branch_ref="${DOCKERHUB_CACHE_REPO}:${svc}-branch-${CACHE_BRANCH_SLUG}"
  cache_main_ref="${DOCKERHUB_CACHE_REPO}:${svc}-${CACHE_MAIN_SLUG}"

  echo "=== buildx ${svc} (${dockerfile} -> ${image}) ==="
  echo "cache-from: ${cache_branch_ref} (primary), ${cache_main_ref} (fallback)"

  cache_to_args=(--cache-to "type=registry,ref=${cache_branch_ref},mode=max")
  if [ "${IS_MAIN_BRANCH}" = "1" ]; then
    cache_to_args+=(--cache-to "type=registry,ref=${cache_main_ref},mode=max")
  fi

  docker buildx build \
    --builder "${BUILDER_NAME}" \
    --file "${dockerfile}" \
    --tag "${image}" \
    --push \
    --cache-from "type=registry,ref=${cache_branch_ref}" \
    --cache-from "type=registry,ref=${cache_main_ref}" \
    "${cache_to_args[@]}" \
    --label "org.opencontainers.image.version=${SOFTWARE_VERSION}" \
    --label "org.opencontainers.image.revision=${GIT_REV}" \
    .
}
```

### C) Optional: Logging fuer spaetere Metriken

```bash
echo "CACHE_BRANCH_SLUG=${CACHE_BRANCH_SLUG}"
echo "IS_MAIN_BRANCH=${IS_MAIN_BRANCH}"
```

Damit kann in Jenkins-Logs leicht geprueft werden, welcher Cache-Pfad aktiv war.

## 5) Cache-Tagging-Strategie (Branch + main Fallback)

Empfohlene Tags im oeffentlichen DockerHub-Cache-Repo (z. B. `docker.io/crawlabase/dflowp-buildcache`):

- Branch-Cache je Service: `${svc}-branch-${CACHE_BRANCH_SLUG}`
- Fallback-Cache je Service: `${svc}-main`

Beispiele:

- `docker.io/crawlabase/dflowp-buildcache:api-branch-feature-jenkins-cache`
- `docker.io/crawlabase/dflowp-buildcache:api-main`
- `docker.io/crawlabase/dflowp-buildcache:worker-branch-bugfix-timeout`
- `docker.io/crawlabase/dflowp-buildcache:worker-main`

Regeln:

- `feature/*` und `bugfix/*` schreiben nur in ihren Branch-Tag.
- `main` schreibt in Branch-Tag (`main`) und in `${svc}-main`.
- Lesen immer in der Reihenfolge: Branch, dann `main`.

## 6) Rollout-Plan in Schritten

1. **Vorbereitung**: DockerHub-Cache-Repo pruefen/erstellen (`dflowp-buildcache`, public).  
2. **Jenkinsfile-Anpassung**: `Jenkinsfile.stack` wie oben erweitern.  
3. **Testlauf auf Feature-Branch**: Ein erster Lauf fuellt Branch-Cache; zweiter Lauf muss schneller sein.  
4. **Fallback-Test**: Neuen Test-Branch ohne eigenen Cache starten; Build sollte aus `*-main` Layer ziehen.  
5. **Main-Aktivierung**: Merge nach `main`; danach einen Lauf auf `main` zur Aktualisierung der `*-main`-Tags.  
6. **Beobachtung 1-2 Wochen**: Laufzeiten und Cache-Hit-Verhalten vergleichen.  

## 7) Metriken / Erfolgskriterien

Primäre Metriken (Jenkins):

- Dauer der Stage `Build images (buildx parallel + registry cache/push)`.
- Gesamtdauer der Pipeline.
- Anzahl Services mit deutlichem Layer-Reuse (aus Buildx-Log ableitbar).

Konkrete Erfolgskriterien:

- Mindestens **20-30% kuerzere** Build-Stage bei wiederholten Branch-Builds.
- Erster Build eines neuen Branches ist schneller als komplett kalter Build durch `main`-Fallback.
- Keine Zunahme von Build-Fehlern durch Cache-Miss/Cache-Corruption.

## 8) Risiken + Gegenmassnahmen

- **Risiko: Cache-Vergiftung durch fehlerhafte Layer auf Branches**  
  Gegenmassnahme: Branch-Isolation + `main` als stabile Referenz; bei Bedarf Branch-Tag loeschen.

- **Risiko: Unbegrenzt wachsende Anzahl Branch-Tags**  
  Gegenmassnahme: periodische Cleanup-Policy fuer alte Branch-Cache-Tags (z. B. >30 Tage).

- **Risiko: API/Rate-Limits bei oeffentlichem DockerHub**  
  Gegenmassnahme: weiter mit `dockerhub-creds` einloggen; ggf. Pull-Raten monitoren.

- **Risiko: Falsche Branch-Namen erzeugen ungueltige Tags**  
  Gegenmassnahme: strikt sanitizen und kuerzen (`cut -c1-40`).

## 9) ToDo-Checklist

- [ ] `Jenkinsfile.stack`: `CACHE_BRANCH_SLUG`, `CACHE_MAIN_SLUG`, `IS_MAIN_BRANCH` in `.jenkins_runtime.env` aufnehmen.
- [ ] `Jenkinsfile.stack`: `build_target()` auf duales `--cache-from` (Branch + main) umstellen.
- [ ] `Jenkinsfile.stack`: `--cache-to` fuer Branch immer, fuer `main` zusaetzlich `*-main`.
- [ ] Jenkins-Run auf Feature-Branch durchfuehren und Buildzeit baseline vs. warm cache dokumentieren.
- [ ] Jenkins-Run auf neuem Branch ohne Cache durchfuehren und Fallback-Hit pruefen.
- [ ] Nach Merge: `main`-Run verifizieren (Pflege der `*-main`-Tags).
- [ ] Monitoring-Notiz erstellen: Stage-Dauer und beobachtete Cache-Hits pro Woche.

