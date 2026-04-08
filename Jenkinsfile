    // DFlowP – CI/CD-Pipeline
    //
    // Voraussetzungen auf dem Jenkins-Agenten:
    //   - Docker (zum Starten von MongoDB)
    //   - Python 3.11+ (python3.11, venv)
    //   - build-Modul für Wheel-Builds (wird in der Pipeline installiert)
    //
    // Optional – Stage „Projekt ausführen (main.py)“:
    //   - OPENAI_API_KEY als Umgebungsvariable oder Jenkins „Secret text“ einbinden
    //     (Pipeline: „Bind credentials“ → Variable OPENAI_API_KEY)
    //   - Oder Parameter RUN_MAIN=true setzen und OPENAI_API_KEY bereitstellen
    // Ohne Key: Pipeline führt nur Tests aus; main.py wird übersprungen.

    pipeline {
        agent any

        options {
        timestamps()
        timeout(time: 60, unit: 'MINUTES')
        }

        environment {
        // Docker Hub Targets
        DOCKER_IMAGE_REPO_API = 'docker.io/crawlabase/dflowp-api'
        DOCKER_IMAGE_REPO_RUNTIME = 'docker.io/crawlabase/dflowp-runtime'
        DOCKER_IMAGE_REPO_EVENTSYSTEM = 'docker.io/crawlabase/dflowp-eventsystem'
        DOCKER_IMAGE_REPO_EVENT_BROKER = 'docker.io/crawlabase/dflowp-event-broker'
        DOCKER_IMAGE_REPO_PLUGIN_FETCHFEEDITEMS = 'docker.io/crawlabase/dflowp-plugin-fetchfeeditems'
        DOCKER_IMAGE_REPO_PLUGIN_EMBEDDATA = 'docker.io/crawlabase/dflowp-plugin-embeddata'

        // Jenkins Credential IDs (bitte in Jenkins anpassen)
        DOCKERHUB_CREDS_ID = 'dockerhub-creds'
        OPENAI_KEY_ID      = 'openai-api-key'
        DFLOWP_API_KEY_ID  = 'DFlowP_API_Key'
        GITHUB_PAT_ID      = 'github-pat'
        MONGODB_CREDS_ID   = 'mongodb-creds'

        // Compose / App Settings
        MONGODB_DATABASE = 'dflowp'
        MONGODB_TEST_DB  = 'dflowp_test'
        }

        stages {
            stage('Cleanup old containers') {
                steps {
                    sh '''
                        set -e
                        # Stoppt und entfernt nur Container, Volumes bleiben erhalten.
                        docker container stop $(docker container ls -aq) 2>/dev/null || true
                        docker container rm $(docker container ls -aq) 2>/dev/null || true
                    '''
                }
            }

            stage('Checkout') {
                steps {
                    checkout scm
                }
            }

        stage('Build and install libraries') {
                steps {
                    sh '''
                        set -e
                        python3.11 -m ensurepip --upgrade
                        ./scripts/build_and_install_libraries.sh
                    '''
                }
            }

        stage('Build Docker Images') {
                steps {
                    sh '''
                        set -e
                    docker --version
                    # Build libraries and install from wheels before image build.
                    python3.11 -m ensurepip --upgrade
                    python3.11 -m pip install --upgrade pip build
                    python3.11 -m build packages/dflowp-core
                    python3.11 -m build packages/dflowp-processruntime
                    python3.11 -m pip install --force-reinstall packages/dflowp-core/dist/*.whl
                    python3.11 -m pip install --force-reinstall --no-deps packages/dflowp-processruntime/dist/*.whl
                    docker build --target api -t "${DOCKER_IMAGE_REPO_API}:${BUILD_NUMBER}" .
                    docker build --target runtime -t "${DOCKER_IMAGE_REPO_RUNTIME}:${BUILD_NUMBER}" .
                    docker build --target eventsystem -t "${DOCKER_IMAGE_REPO_EVENTSYSTEM}:${BUILD_NUMBER}" .
                    docker build --target event-broker -t "${DOCKER_IMAGE_REPO_EVENT_BROKER}:${BUILD_NUMBER}" .
                    docker build --target plugin-fetchfeeditems -t "${DOCKER_IMAGE_REPO_PLUGIN_FETCHFEEDITEMS}:${BUILD_NUMBER}" .
                    docker build --target plugin-embeddata -t "${DOCKER_IMAGE_REPO_PLUGIN_EMBEDDATA}:${BUILD_NUMBER}" .
                    '''
                }
            }

        stage('Resolve Software Version') {
                steps {
                withCredentials([
                    usernamePassword(credentialsId: "${DOCKERHUB_CREDS_ID}", usernameVariable: 'DOCKERHUB_USERNAME', passwordVariable: 'DOCKERHUB_PASSWORD')
                ]) {
                sh '''
                    set -e

                    echo "${DOCKERHUB_PASSWORD}" | docker login -u "${DOCKERHUB_USERNAME}" --password-stdin index.docker.io

                    # Nutzt docker-browse (authentifiziertes Docker-Setup) via npx zum Tag-Auslesen.
                    TAGS_RAW="$(npx docker-browse tags crawlabase/dflowp-api || true)"
                    PREV_VERSION="$(printf "%s\n" "${TAGS_RAW}" \
                      | python3.11 -c 'import re,sys; tags=[line.strip() for line in sys.stdin if line.strip()]; sem=[t for t in tags if re.match(r"^\\d+\\.\\d+\\.\\d+$", t)]; sem.sort(key=lambda s: tuple(map(int,s.split(".")))); print(sem[-1] if sem else "latest")')"
                    export PREV_VERSION

                    if [ "$PREV_VERSION" = "latest" ]; then
                      SOFTWARE_VERSION="${BUILD_NUMBER}"
                    else
                      SOFTWARE_VERSION="$(python3.11 - "$PREV_VERSION" <<'PY'
import sys
v = sys.argv[1]
try:
    parts = v.split(".")
    if len(parts) == 3 and all(p.isdigit() for p in parts):
        print(int(parts[2]) + 1)
    elif v.isdigit():
        print(int(v) + 1)
    else:
        print("1")
except Exception:
    print("1")
PY
)"
                    fi

                    echo "Resolved SOFTWARE_VERSION=${SOFTWARE_VERSION}"
                    printf "SOFTWARE_VERSION=%s\n" "${SOFTWARE_VERSION}" > .jenkins_runtime.env
                '''
                }
                }
            }

        stage('Compose up (MongoDB + App)') {
                steps {
                withCredentials([
                    usernamePassword(credentialsId: "${MONGODB_CREDS_ID}", usernameVariable: 'MONGODB_USERNAME', passwordVariable: 'MONGODB_PASSWORD'),
                    string(credentialsId: "${OPENAI_KEY_ID}", variable: 'OPENAI_API_KEY'),
                    string(credentialsId: "${DFLOWP_API_KEY_ID}", variable: 'DFlowP_API_Key')
                ]) {
                    echo "MONGODB_USERNAME: ${MONGODB_USERNAME}"

                    sh '''
                        set -e
                        export DOCKER_IMAGE_API="${DOCKER_IMAGE_REPO_API}:${BUILD_NUMBER}"
                        export DOCKER_IMAGE_RUNTIME="${DOCKER_IMAGE_REPO_RUNTIME}:${BUILD_NUMBER}"
                        export DOCKER_IMAGE_EVENTSYSTEM="${DOCKER_IMAGE_REPO_EVENTSYSTEM}:${BUILD_NUMBER}"
                        export DOCKER_IMAGE_EVENT_BROKER="${DOCKER_IMAGE_REPO_EVENT_BROKER}:${BUILD_NUMBER}"
                        export DOCKER_IMAGE_PLUGIN_FETCHFEEDITEMS="${DOCKER_IMAGE_REPO_PLUGIN_FETCHFEEDITEMS}:${BUILD_NUMBER}"
                        export DOCKER_IMAGE_PLUGIN_EMBEDDATA="${DOCKER_IMAGE_REPO_PLUGIN_EMBEDDATA}:${BUILD_NUMBER}"
                        . ./.jenkins_runtime.env
                        export SOFTWARE_VERSION
                        # Kein --build: Image wurde in der Stage „Build Docker Image“ gebaut.
                        # Neuere docker-compose Versionen verlangen sonst Buildx >= 0.17.0 (Bake).
                        docker-compose up -d
                        docker-compose ps
                    '''
                }
                }
            }

            stage('Tests API (pytest)') {
                steps {
                withCredentials([
                    usernamePassword(credentialsId: "${MONGODB_CREDS_ID}", usernameVariable: 'MONGODB_USERNAME', passwordVariable: 'MONGODB_PASSWORD'),
                    string(credentialsId: "${OPENAI_KEY_ID}", variable: 'OPENAI_API_KEY'),
                    string(credentialsId: "${DFLOWP_API_KEY_ID}", variable: 'DFlowP_API_Key')
                ]) {
                    sh '''
                        set -e
                        export DOCKER_IMAGE_API="${DOCKER_IMAGE_REPO_API}:${BUILD_NUMBER}"
                        export DOCKER_IMAGE_RUNTIME="${DOCKER_IMAGE_REPO_RUNTIME}:${BUILD_NUMBER}"
                        export DOCKER_IMAGE_EVENTSYSTEM="${DOCKER_IMAGE_REPO_EVENTSYSTEM}:${BUILD_NUMBER}"
                        export DOCKER_IMAGE_EVENT_BROKER="${DOCKER_IMAGE_REPO_EVENT_BROKER}:${BUILD_NUMBER}"
                        export DOCKER_IMAGE_PLUGIN_FETCHFEEDITEMS="${DOCKER_IMAGE_REPO_PLUGIN_FETCHFEEDITEMS}:${BUILD_NUMBER}"
                        export DOCKER_IMAGE_PLUGIN_EMBEDDATA="${DOCKER_IMAGE_REPO_PLUGIN_EMBEDDATA}:${BUILD_NUMBER}"
                        . ./.jenkins_runtime.env
                        export SOFTWARE_VERSION
                        # API-Tests laufen im API-Container und nutzen Compose-Mongo via Service-Name "mongo"
                        docker-compose run --rm \
                          -e MONGODB_TEST_DB="${MONGODB_TEST_DB}" \
                          api pytest tests/api_test.py -v --tb=short
                    '''
                }
                }
            }

            stage('Tests Runtime (pytest)') {
                steps {
                withCredentials([
                    usernamePassword(credentialsId: "${MONGODB_CREDS_ID}", usernameVariable: 'MONGODB_USERNAME', passwordVariable: 'MONGODB_PASSWORD'),
                    string(credentialsId: "${OPENAI_KEY_ID}", variable: 'OPENAI_API_KEY'),
                    string(credentialsId: "${DFLOWP_API_KEY_ID}", variable: 'DFlowP_API_Key')
                ]) {
                    sh '''
                        set -e
                        export DOCKER_IMAGE_API="${DOCKER_IMAGE_REPO_API}:${BUILD_NUMBER}"
                        export DOCKER_IMAGE_RUNTIME="${DOCKER_IMAGE_REPO_RUNTIME}:${BUILD_NUMBER}"
                        export DOCKER_IMAGE_EVENTSYSTEM="${DOCKER_IMAGE_REPO_EVENTSYSTEM}:${BUILD_NUMBER}"
                        export DOCKER_IMAGE_EVENT_BROKER="${DOCKER_IMAGE_REPO_EVENT_BROKER}:${BUILD_NUMBER}"
                        export DOCKER_IMAGE_PLUGIN_FETCHFEEDITEMS="${DOCKER_IMAGE_REPO_PLUGIN_FETCHFEEDITEMS}:${BUILD_NUMBER}"
                        export DOCKER_IMAGE_PLUGIN_EMBEDDATA="${DOCKER_IMAGE_REPO_PLUGIN_EMBEDDATA}:${BUILD_NUMBER}"
                        . ./.jenkins_runtime.env
                        export SOFTWARE_VERSION
                        # Runtime-/Core-Tests laufen im Worker-Container.
                        docker-compose run --rm \
                          -e MONGODB_TEST_DB="${MONGODB_TEST_DB}" \
                          worker pytest tests/process_test.py tests/runtime_event_listener_test.py tests/logging_test.py tests/database_test.py -v --tb=short
                    '''
                }
                }
            }

            stage('Tests Plugin Services (pytest)') {
                steps {
                withCredentials([
                    usernamePassword(credentialsId: "${MONGODB_CREDS_ID}", usernameVariable: 'MONGODB_USERNAME', passwordVariable: 'MONGODB_PASSWORD'),
                    string(credentialsId: "${OPENAI_KEY_ID}", variable: 'OPENAI_API_KEY'),
                    string(credentialsId: "${DFLOWP_API_KEY_ID}", variable: 'DFlowP_API_Key')
                ]) {
                    sh '''
                        set -e
                        export DOCKER_IMAGE_API="${DOCKER_IMAGE_REPO_API}:${BUILD_NUMBER}"
                        export DOCKER_IMAGE_RUNTIME="${DOCKER_IMAGE_REPO_RUNTIME}:${BUILD_NUMBER}"
                        export DOCKER_IMAGE_EVENTSYSTEM="${DOCKER_IMAGE_REPO_EVENTSYSTEM}:${BUILD_NUMBER}"
                        export DOCKER_IMAGE_EVENT_BROKER="${DOCKER_IMAGE_REPO_EVENT_BROKER}:${BUILD_NUMBER}"
                        export DOCKER_IMAGE_PLUGIN_FETCHFEEDITEMS="${DOCKER_IMAGE_REPO_PLUGIN_FETCHFEEDITEMS}:${BUILD_NUMBER}"
                        export DOCKER_IMAGE_PLUGIN_EMBEDDATA="${DOCKER_IMAGE_REPO_PLUGIN_EMBEDDATA}:${BUILD_NUMBER}"
                        . ./.jenkins_runtime.env
                        export SOFTWARE_VERSION
                        docker-compose run --rm \
                          plugin-fetchfeeditems pytest tests/plugin_services_test.py::test_plugin_directories_exist tests/plugin_services_test.py::test_fetch_plugin_info_and_health -v --tb=short
                        docker-compose run --rm \
                          plugin-embeddata pytest tests/plugin_services_test.py::test_embed_plugin_info_and_health -v --tb=short
                    '''
                }
                }
            }

            stage('Tests Event Services (pytest)') {
                steps {
                withCredentials([
                    usernamePassword(credentialsId: "${MONGODB_CREDS_ID}", usernameVariable: 'MONGODB_USERNAME', passwordVariable: 'MONGODB_PASSWORD'),
                    string(credentialsId: "${OPENAI_KEY_ID}", variable: 'OPENAI_API_KEY'),
                    string(credentialsId: "${DFLOWP_API_KEY_ID}", variable: 'DFlowP_API_Key')
                ]) {
                    sh '''
                        set -e
                        export DOCKER_IMAGE_API="${DOCKER_IMAGE_REPO_API}:${BUILD_NUMBER}"
                        export DOCKER_IMAGE_RUNTIME="${DOCKER_IMAGE_REPO_RUNTIME}:${BUILD_NUMBER}"
                        export DOCKER_IMAGE_EVENTSYSTEM="${DOCKER_IMAGE_REPO_EVENTSYSTEM}:${BUILD_NUMBER}"
                        export DOCKER_IMAGE_EVENT_BROKER="${DOCKER_IMAGE_REPO_EVENT_BROKER}:${BUILD_NUMBER}"
                        export DOCKER_IMAGE_PLUGIN_FETCHFEEDITEMS="${DOCKER_IMAGE_REPO_PLUGIN_FETCHFEEDITEMS}:${BUILD_NUMBER}"
                        export DOCKER_IMAGE_PLUGIN_EMBEDDATA="${DOCKER_IMAGE_REPO_PLUGIN_EMBEDDATA}:${BUILD_NUMBER}"
                        . ./.jenkins_runtime.env
                        export SOFTWARE_VERSION
                        docker-compose run --rm \
                          -e MONGODB_TEST_DB="${MONGODB_TEST_DB}" \
                          event-broker pytest tests/event_broker_test.py -v --tb=short
                        docker-compose run --rm \
                          -e MONGODB_TEST_DB="${MONGODB_TEST_DB}" \
                          eventsystem pytest tests/eventsystem_test.py -k "not with_persistence" -v --tb=short
                    '''
                }
                }
            }

        stage('Docker Hub Login & Push Images') {
                steps {
                withCredentials([
                    usernamePassword(credentialsId: "${DOCKERHUB_CREDS_ID}", usernameVariable: 'DOCKERHUB_USERNAME', passwordVariable: 'DOCKERHUB_PASSWORD')
                ]) {
                    sh '''
                        set -e
                        echo "${DOCKERHUB_PASSWORD}" | docker login -u "${DOCKERHUB_USERNAME}" --password-stdin
                        docker push "${DOCKER_IMAGE_REPO_API}:${BUILD_NUMBER}"
                        docker push "${DOCKER_IMAGE_REPO_RUNTIME}:${BUILD_NUMBER}"
                        docker push "${DOCKER_IMAGE_REPO_EVENTSYSTEM}:${BUILD_NUMBER}"
                        docker push "${DOCKER_IMAGE_REPO_EVENT_BROKER}:${BUILD_NUMBER}"
                        docker push "${DOCKER_IMAGE_REPO_PLUGIN_FETCHFEEDITEMS}:${BUILD_NUMBER}"
                        docker push "${DOCKER_IMAGE_REPO_PLUGIN_EMBEDDATA}:${BUILD_NUMBER}"
                        docker logout || true
                    '''
                }
                }
            }
        }

        post {
            failure {
                echo 'Pipeline fehlgeschlagen – Logs prüfen.'
                echo 'Deleting containers, volumes and networks...'

            }
            success {
                echo 'Pipeline erfolgreich abgeschlossen.'
            }
        }
    }
