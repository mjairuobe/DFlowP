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
        timestamps()
        timeout(time: 60, unit: 'MINUTES')
        }

        environment {
        // Docker Hub Target
        DOCKER_IMAGE_REPO = 'crwalabase/dflowp'

        // Jenkins Credential IDs (bitte in Jenkins anpassen)
        DOCKERHUB_CREDS_ID = 'dockerhub-creds'
        OPENAI_KEY_ID      = 'openai-api-key'
        GITHUB_PAT_ID      = 'github-pat'
        MONGODB_CREDS_ID   = 'mongodb-creds'

        // Compose / App Settings
        MONGODB_DATABASE = 'dflowp'
        MONGODB_TEST_DB  = 'dflowp_test'
        }

        stages {
            stage('Checkout') {
                steps {
                    checkout scm
                }
            }

        stage('Build Docker Image') {
                steps {
                    sh '''
                        set -e
                    docker --version
                    docker build -t "${DOCKER_IMAGE_REPO}:${BUILD_NUMBER}" .
                    '''
                }
            }

        stage('Compose up (MongoDB + App)') {
                steps {
                withCredentials([
                    usernamePassword(credentialsId: "${MONGODB_CREDS_ID}", usernameVariable: 'MONGODB_USERNAME', passwordVariable: 'MONGODB_PASSWORD'),
                    string(credentialsId: "${OPENAI_KEY_ID}", variable: 'OPENAI_API_KEY')
                ]) {
                    sh '''
                        set -e
                        export DOCKER_IMAGE="${DOCKER_IMAGE_REPO}:${BUILD_NUMBER}"
                        # Kein --build: Image wurde in der Stage „Build Docker Image“ gebaut.
                        # Neuere docker-compose Versionen verlangen sonst Buildx >= 0.17.0 (Bake).
                        docker-compose up -d
                        docker-compose ps
                    '''
                }
                }
            }

            stage('Tests (pytest)') {
                steps {
                withCredentials([
                    usernamePassword(credentialsId: "${MONGODB_CREDS_ID}", usernameVariable: 'MONGODB_USERNAME', passwordVariable: 'MONGODB_PASSWORD'),
                    string(credentialsId: "${OPENAI_KEY_ID}", variable: 'OPENAI_API_KEY')
                ]) {
                    sh '''
                        set -e
                        export DOCKER_IMAGE="${DOCKER_IMAGE_REPO}:${BUILD_NUMBER}"
                        # Tests laufen im App-Container und nutzen Compose-Mongo via Service-Name "mongo"
                        docker-compose run --rm \
                          -e MONGODB_TEST_DB="${MONGODB_TEST_DB}" \
                          app pytest tests/ -v --tb=short
                    '''
                }
                }
            }

        stage('Docker Hub Login & Push') {
                steps {
                withCredentials([
                    usernamePassword(credentialsId: "${DOCKERHUB_CREDS_ID}", usernameVariable: 'DOCKERHUB_USERNAME', passwordVariable: 'DOCKERHUB_PASSWORD')
                ]) {
                    sh '''
                        set -e
                        echo "${DOCKERHUB_PASSWORD}" | docker login -u "${DOCKERHUB_USERNAME}" --password-stdin
                        docker push "${DOCKER_IMAGE_REPO}:${BUILD_NUMBER}"
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
                sh '''
                    docker-compose down -v 2>/dev/null || true
                '''
            }
            success {
                echo 'Pipeline erfolgreich abgeschlossen.'
            }
        }
    }
