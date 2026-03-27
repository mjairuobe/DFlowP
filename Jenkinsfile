    // DFlowP – CI/CD-Pipeline
    //
    // Voraussetzungen auf dem Jenkins-Agenten:
    //   - Docker (zum Starten von MongoDB)
    //   - Python 3.10+ (python3, venv)
    //
    // Optional – Stage „Projekt ausführen (main.py)“:
    //   - OPENAI_API_KEY als Umgebungsvariable oder Jenkins „Secret text“ einbinden
    //     (Pipeline: „Bind credentials“ → Variable OPENAI_API_KEY)
    //   - Oder Parameter RUN_MAIN=true setzen und OPENAI_API_KEY bereitstellen
    // Ohne Key: Pipeline führt nur Tests aus; main.py wird übersprungen.

    pipeline {
        agent any

        options {
            timeout(time: 60, unit: 'MINUTES')
        }

        environment {
            // MongoDB aus dem Docker-Container (Port auf dem Host)
            MONGODB_URI       = 'mongodb://127.0.0.1:27017'
            MONGODB_DATABASE  = 'dflowp'
            MONGODB_TEST_DB   = 'dflowp_test'
            PYTHONUNBUFFERED  = '1'
            VENV_DIR          = "${WORKSPACE}/venv-jenkins"
            MONGO_CONTAINER   = "dflowp-mongo-${env.BUILD_TAG.replaceAll('[^a-zA-Z0-9_.-]', '-')}"
        }

        stages {
            stage('Checkout') {
                steps {
                    checkout scm
                }
            }

            stage('MongoDB (Docker)') {
                steps {
                    sh '''
                        set -e
                        echo "Starte MongoDB-Container: ${MONGO_CONTAINER}"
                        docker pull mongo:7
                        docker rm -f "${MONGO_CONTAINER}" 2>/dev/null || true
                        docker run -d \
                        --name "${MONGO_CONTAINER}" \
                        -p 27017:27017 \
                        mongo:7

                        echo "Warte auf MongoDB …"
                        for i in $(seq 1 60); do
                        if docker exec "${MONGO_CONTAINER}" mongosh --quiet --eval "db.adminCommand({ ping: 1 }).ok" 2>/dev/null | grep -q 1; then
                            echo "MongoDB ist erreichbar."
                            exit 0
                        fi
                        sleep 1
                        done
                        echo "Timeout: MongoDB nicht bereit."
                        exit 1
                    '''
                }
            }

            stage('Python venv & Abhängigkeiten') {
                steps {
                    sh '''
                        set -e
                        python3.11 --version
                        python3.11 -m ensurepip --upgrade
                        python3.11 -m venv "${VENV_DIR}"
                        . "${VENV_DIR}/bin/activate"
                        pip install --upgrade pip setuptools wheel
                        pip install -r requirements.txt
                        pip install -e ".[dev]"
                    '''
                }
            }

            stage('Tests (pytest)') {
                steps {
                    sh '''
                        set -e
                        . "${VENV_DIR}/bin/activate"
                        export MONGODB_URI="${MONGODB_URI}"
                        export MONGODB_TEST_DB="${MONGODB_TEST_DB}"
                        pytest tests/ -v --tb=short
                    '''
                }
            }

            stage('Projekt ausführen (main.py)') {
                when {
                    anyOf {
                        environment name: 'RUN_MAIN', value: 'true'
                        expression {
                            def k = env.OPENAI_API_KEY
                            return k != null && !k.trim().isEmpty()
                        }
                    }
                }
                options {
                    timeout(time: 45, unit: 'MINUTES')
                }
                steps {
                    sh '''
                        set -e
                        . "${VENV_DIR}/bin/activate"
                        export MONGODB_URI="${MONGODB_URI}"
                        export MONGODB_DATABASE="${MONGODB_DATABASE}"

                        if [ -z "${OPENAI_API_KEY:-}" ]; then
                        echo "OPENAI_API_KEY fehlt – main.py wird nicht gestartet (Job-Parameter RUN_MAIN oder Secret setzen)."
                        exit 0
                        fi

                        python main.py
                    '''
                }
            }
        }

        post {
            always {
                sh '''
                    docker rm -f "${MONGO_CONTAINER}" 2>/dev/null || true
                '''
            }
            success {
                echo 'Pipeline erfolgreich abgeschlossen.'
            }
            failure {
                echo 'Pipeline fehlgeschlagen – Logs prüfen.'
            }
        }
    }
