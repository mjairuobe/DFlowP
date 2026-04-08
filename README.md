# Modular CI Template

Abstraktion des partiellen Docker/Jenkins-Builds: Tree-Short-Tags, `vMAJOR.MINOR.BUILD`, Skip-Logik und **abhängigkeitsbewusste** Neubauten (nur Services, die eine geänderte lokale Library wirklich referenzieren).

Dieses Repository ist **nur das Template** (Dateien im Root).

## Struktur

- `modules.json` – unter `dir.packages` und `dir.services` Pfade zu Ordnern; `docker.*` für Registry, Image-Namen, Container-Namen, Dockerfile-Stages und `CMD`
- `required_stack_services` – optionale Liste von **Compose-Service-Namen** (Keys unter `services:` in `docker-compose.yml`), die für „Skip“ laufen müssen (z. B. `mongo`). Kein Build für diese Einträge; der Abgleich nutzt die `image:`-Zeile aus der Compose-Datei (kein fest codiertes Image im Skript).
- `example-packages/*` – Python-Pakete mit `pyproject.toml` + `requirements.txt`
- `example-services/*` – Service-Code + `requirements.txt` (lokale Libs z. B. mit `-e ../pfad/zum/paket`)
- `scripts/ci_*.py` – Logik
- `Dockerfile` wird aus `modules.json` generiert (`ci_generate_dockerfile.py`). Pro Service werden nur die **Wheels der in `requirements.txt` referenzierten** lokalen Packages kopiert; lokale Paketzeilen werden zur Laufzeit durch ein generiertes `.docker-reqs-<service>.txt` ersetzt (ohne Duplikat-Install).

## Abhängigkeiten zwischen lokalen Packages

- `requirements.txt` pro Package kann andere lokale Packages referenzieren.
- Ändert sich ein Package-Baum, werden alle **transitiven Abhängigen** (über dieses Graph-Modell) als „betroffen“ markiert.
- Ein Service wird nur neu gebaut, wenn sein eigener Baum sich geändert hat **oder** mindestens eine in seiner `requirements.txt` referenzierte lokale Library betroffen ist.

`LIB_FORCE` gibt es nicht mehr: es wird nicht mehr „alles“ gebaut, nur noch betroffene Images.

## Voraussetzungen

- Python **3.11+** (`python3.11` auf dem Jenkins-Agenten)
- Docker und **`docker-compose`** (Standalone-CLI)
- Git-Tags `vX.Y.Z` optional (sonst `v0.1.<commit-count>`)

## Neues GitHub-Repository

1. Diesen Branch oder das Repo als Vorlage nehmen (Root = Template).
2. `modules.json` anpassen (Pfade, `docker.registry`, `images`, `containers`, `stage_targets`, `cmd`, ggf. `required_stack_services`).
3. `python3.11 scripts/ci_generate_dockerfile.py` ausführen und `Dockerfile` committen (generierte `.docker-reqs-*.txt` bleiben ignoriert).
4. `docker-compose.yml` anpassen (Service-Namen, `DOCKER_IMAGE_*`, ggf. Infrastruktur wie `mongo`).

## Lokales Ausprobieren

```bash
python3.11 scripts/ci_resolve_version.py
python3.11 scripts/ci_build_plan.py
python3.11 scripts/ci_generate_dockerfile.py
python3.11 scripts/ci_docker_build.py
```

## Monorepo vs. eigenes Repo

- **Eigenes Repo** (dieses Template): `git rev-parse HEAD:<pfad>` und `docker build .` im Root.
- **Monorepo** (Template liegt unter einem Unterordner): Tree-Hashes nutzen Pfade relativ zum Git-Root; `ci_docker_build.py` baut mit Kontext auf dem Git-Root und `-f <unterordner>/Dockerfile`. Das `Jenkinsfile` in diesem Branch geht davon aus, dass das Template **das Repo-Root** ist.

## Hinweise

- **Erster Lauf:** alle `BUILDSVC_*=1`, bis `.jenkins_last_trees` nach `ci_docker_build` gefüllt ist.
- **Jenkins:** Artefakt `.jenkins_last_trees` zwischen Builds archivieren, wenn der Workspace immer „frisch“ ist.
- **Teil-Build:** Nicht neu gebaute Services nutzen weiter den Tag aus dem laufenden Container (`ci_compose_env.py`).
- **`require_mongo`:** entfernt – stattdessen `required_stack_services` + `mongo` (oder anderes DB-Image) in `docker-compose.yml`; die Skip-Prüfung orientiert sich an der Compose-`image:`-Zeile.
