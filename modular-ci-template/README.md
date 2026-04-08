# Modular CI Template

Abstraktion des partiellen Docker/Jenkins-Builds (Tree-Short-Tags, `vMAJOR.MINOR.BUILD`, Skip, LIB_FORCE).

## Struktur

- `modules.json` – unter `dir.packages` und `dir.services` Pfade zu Ordnern; `docker.*` für Registry, Image-Namen, Container-Namen, Dockerfile-Stages und `CMD`
- `example-packages/*` – Python-Pakete mit `pyproject.toml` + `requirements.txt`
- `example-services/*` – Service-Code + `requirements.txt`
- `scripts/ci_*.py` – Logik
- `Dockerfile` wird aus `modules.json` generiert (`ci_generate_dockerfile.py`)

## Voraussetzungen

- Python **3.11+** (`python3.11` auf dem Jenkins-Agenten)
- Docker + Docker Compose
- Git-Tags `vX.Y.Z` optional (sonst `v0.1.<commit-count>`)

## Neues GitHub-Repository

1. Ordner `modular-ci-template/` als Root eines neuen Repos kopieren oder diesen Repo-Subtree pushen.
2. `modules.json` anpassen (Pfade, `docker.registry`, `images`, `containers`, `stage_targets`, `cmd`).
3. `python3.11 scripts/ci_generate_dockerfile.py` ausführen und `Dockerfile` committen.
4. `docker-compose.yml` anpassen (Service-Namen, `DOCKER_IMAGE_*`).

## Lokales Ausprobieren

```bash
python3.11 scripts/ci_resolve_version.py
python3.11 scripts/ci_build_plan.py
python3.11 scripts/ci_generate_dockerfile.py
python3.11 scripts/ci_docker_build.py
```

## Hinweise

- **Erster Lauf:** `LIB_FORCE=1` bis `.jenkins_last_trees` existiert (nach erstem erfolgreichen `ci_docker_build`).
- **Jenkins:** Artefakt `.jenkins_last_trees` zwischen Builds archivieren, wenn der Workspace immer „frisch“ ist.
- **Teil-Build:** Nicht neu gebaute Services nutzen weiter den Tag aus dem laufenden Container (`ci_compose_env.py`).
