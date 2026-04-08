    // DFlowP – CI/CD-Pipeline (modular-ci: modules.json + scripts/ci_*.py)
    //
    // Version & Tags: scripts/ci_resolve_version.py → .jenkins_runtime.env
    // Build-Plan: scripts/ci_build_plan.py (abhängigkeitsbasiert, kein LIB_FORCE)
    // Compose-Images: eval "$(python3.11 scripts/ci_compose_env.py)"
    // Docker: scripts/ci_docker_build.py / ci_docker_push.py

    pipeline {
        agent any

        options {
        timestamps()
        timeout(time: 60, unit: 'MINUTES')
        }

        environment {
        DOCKER_IMAGE_REPO_API = 'docker.io/crawlabase/dflowp-api'
        DOCKER_IMAGE_REPO_RUNTIME = 'docker.io/crawlabase/dflowp-runtime'
        DOCKER_IMAGE_REPO_EVENTSYSTEM = 'docker.io/crawlabase/dflowp-eventsystem'
        DOCKER_IMAGE_REPO_EVENT_BROKER = 'docker.io/crawlabase/dflowp-event-broker'
        DOCKER_IMAGE_REPO_PLUGIN_FETCHFEEDITEMS = 'docker.io/crawlabase/dflowp-plugin-fetchfeeditems'
        DOCKER_IMAGE_REPO_PLUGIN_EMBEDDATA = 'docker.io/crawlabase/dflowp-plugin-embeddata'

        DOCKERHUB_CREDS_ID = 'dockerhub-creds'
        OPENAI_KEY_ID      = 'openai-api-key'
        DFLOWP_API_KEY_ID  = 'DFlowP_API_Key'
        GITHUB_PAT_ID      = 'github-pat'
        MONGODB_CREDS_ID   = 'mongodb-creds'

        MONGODB_DATABASE = 'dflowp'
        MONGODB_TEST_DB  = 'dflowp_test'
        }

        stages {
            stage('Checkout') {
                steps {
                    checkout scm
                }
            }

            stage('Fetch git tags') {
                steps {
                    sh '''
                        set -e
                        # Tags vom Remote (bei shallow/multibranch oft nicht im Workspace)
                        git remote get-url origin >/dev/null 2>&1 && git fetch origin --tags --force || git fetch --tags --force || true
                        git tag -l 'v*' | tail -5 || true
                    '''
                }
            }

            stage('Resolve software version & tree tags') {
                steps {
                    sh '''
                        set -e
                        python3.11 scripts/ci_resolve_version.py
                        . ./.jenkins_runtime.env
                        echo "SOFTWARE_VERSION=${SOFTWARE_VERSION}"
                    '''
                }
            }

            stage('Build plan (skip / partial / full)') {
                steps {
                    sh '''
                        set -e
                        python3.11 scripts/ci_build_plan.py
                        cat .jenkins_skip_pipeline || true
                    '''
                }
            }

            stage('Cleanup old containers') {
                when {
                    expression {
                        return !fileExists('.jenkins_skip_pipeline') || readFile('.jenkins_skip_pipeline').trim() != 'true'
                    }
                }
                steps {
                    sh '''
                        set -e
                        docker container stop $(docker container ls -aq) 2>/dev/null || true
                        docker container rm $(docker container ls -aq) 2>/dev/null || true
                    '''
                }
            }

            stage('Build Docker images (selective)') {
                when {
                    expression {
                        return !fileExists('.jenkins_skip_pipeline') || readFile('.jenkins_skip_pipeline').trim() != 'true'
                    }
                }
                steps {
                    sh '''
                        set -e
                        python3.11 scripts/ci_docker_build.py
                    '''
                }
            }

            stage('Compose up (MongoDB + App)') {
                when {
                    expression {
                        return !fileExists('.jenkins_skip_pipeline') || readFile('.jenkins_skip_pipeline').trim() != 'true'
                    }
                }
                steps {
                withCredentials([
                    usernamePassword(credentialsId: "${MONGODB_CREDS_ID}", usernameVariable: 'MONGODB_USERNAME', passwordVariable: 'MONGODB_PASSWORD'),
                    string(credentialsId: "${OPENAI_KEY_ID}", variable: 'OPENAI_API_KEY'),
                    string(credentialsId: "${DFLOWP_API_KEY_ID}", variable: 'DFlowP_API_Key')
                ]) {
                    echo "MONGODB_USERNAME: ${MONGODB_USERNAME}"

                    sh '''
                        set -e
                        . ./.jenkins_runtime.env
                        set -a
                        . ./.jenkins_build_plan.env
                        eval "$(python3.11 scripts/ci_compose_env.py)"
                        set +a
                        docker-compose up -d
                        docker-compose ps
                    '''
                }
                }
            }

            stage('Tests API (pytest)') {
                when {
                    expression {
                        return !fileExists('.jenkins_skip_pipeline') || readFile('.jenkins_skip_pipeline').trim() != 'true'
                    }
                }
                steps {
                withCredentials([
                    usernamePassword(credentialsId: "${MONGODB_CREDS_ID}", usernameVariable: 'MONGODB_USERNAME', passwordVariable: 'MONGODB_PASSWORD'),
                    string(credentialsId: "${OPENAI_KEY_ID}", variable: 'OPENAI_API_KEY'),
                    string(credentialsId: "${DFLOWP_API_KEY_ID}", variable: 'DFlowP_API_Key')
                ]) {
                    sh '''
                        set -e
                        . ./.jenkins_runtime.env
                        set -a
                        . ./.jenkins_build_plan.env
                        eval "$(python3.11 scripts/ci_compose_env.py)"
                        set +a
                        docker-compose run --rm \
                          -e MONGODB_TEST_DB="${MONGODB_TEST_DB}" \
                          api pytest tests/api_test.py -v --tb=short
                    '''
                }
                }
            }

            stage('Tests Runtime (pytest)') {
                when {
                    expression {
                        return !fileExists('.jenkins_skip_pipeline') || readFile('.jenkins_skip_pipeline').trim() != 'true'
                    }
                }
                steps {
                withCredentials([
                    usernamePassword(credentialsId: "${MONGODB_CREDS_ID}", usernameVariable: 'MONGODB_USERNAME', passwordVariable: 'MONGODB_PASSWORD'),
                    string(credentialsId: "${OPENAI_KEY_ID}", variable: 'OPENAI_API_KEY'),
                    string(credentialsId: "${DFLOWP_API_KEY_ID}", variable: 'DFlowP_API_Key')
                ]) {
                    sh '''
                        set -e
                        . ./.jenkins_runtime.env
                        set -a
                        . ./.jenkins_build_plan.env
                        eval "$(python3.11 scripts/ci_compose_env.py)"
                        set +a
                        docker-compose run --rm \
                          -e MONGODB_TEST_DB="${MONGODB_TEST_DB}" \
                          worker pytest tests/process_test.py tests/runtime_event_listener_test.py tests/logging_test.py tests/database_test.py -v --tb=short
                    '''
                }
                }
            }

            stage('Tests Plugin Services (pytest)') {
                when {
                    expression {
                        return !fileExists('.jenkins_skip_pipeline') || readFile('.jenkins_skip_pipeline').trim() != 'true'
                    }
                }
                steps {
                withCredentials([
                    usernamePassword(credentialsId: "${MONGODB_CREDS_ID}", usernameVariable: 'MONGODB_USERNAME', passwordVariable: 'MONGODB_PASSWORD'),
                    string(credentialsId: "${OPENAI_KEY_ID}", variable: 'OPENAI_API_KEY'),
                    string(credentialsId: "${DFLOWP_API_KEY_ID}", variable: 'DFlowP_API_Key')
                ]) {
                    sh '''
                        set -e
                        . ./.jenkins_runtime.env
                        set -a
                        . ./.jenkins_build_plan.env
                        eval "$(python3.11 scripts/ci_compose_env.py)"
                        set +a
                        docker-compose run --rm \
                          plugin-fetchfeeditems pytest tests/plugin_services_test.py::test_plugin_directories_exist tests/plugin_services_test.py::test_fetch_plugin_info_and_health -v --tb=short
                        docker-compose run --rm \
                          plugin-embeddata pytest tests/plugin_services_test.py::test_embed_plugin_info_and_health -v --tb=short
                    '''
                }
                }
            }

            stage('Tests Event Services (pytest)') {
                when {
                    expression {
                        return !fileExists('.jenkins_skip_pipeline') || readFile('.jenkins_skip_pipeline').trim() != 'true'
                    }
                }
                steps {
                withCredentials([
                    usernamePassword(credentialsId: "${MONGODB_CREDS_ID}", usernameVariable: 'MONGODB_USERNAME', passwordVariable: 'MONGODB_PASSWORD'),
                    string(credentialsId: "${OPENAI_KEY_ID}", variable: 'OPENAI_API_KEY'),
                    string(credentialsId: "${DFLOWP_API_KEY_ID}", variable: 'DFlowP_API_Key')
                ]) {
                    sh '''
                        set -e
                        . ./.jenkins_runtime.env
                        set -a
                        . ./.jenkins_build_plan.env
                        eval "$(python3.11 scripts/ci_compose_env.py)"
                        set +a
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
                when {
                    expression {
                        return !fileExists('.jenkins_skip_pipeline') || readFile('.jenkins_skip_pipeline').trim() != 'true'
                    }
                }
                steps {
                withCredentials([
                    usernamePassword(credentialsId: "${DOCKERHUB_CREDS_ID}", usernameVariable: 'DOCKERHUB_USERNAME', passwordVariable: 'DOCKERHUB_PASSWORD')
                ]) {
                    sh '''
                        set -e
                        . ./.jenkins_runtime.env
                        . ./.jenkins_build_plan.env
                        echo "${DOCKERHUB_PASSWORD}" | docker login -u "${DOCKERHUB_USERNAME}" --password-stdin
                        python3.11 scripts/ci_docker_push.py
                        docker logout || true
                    '''
                }
                }
            }
        }

        post {
            failure {
                echo 'Pipeline fehlgeschlagen – Logs prüfen.'
            }
            success {
                script {
                    if (fileExists('.jenkins_skip_pipeline') && readFile('.jenkins_skip_pipeline').trim() == 'true') {
                        echo '=== SKIP: Stack entspricht bereits den erwarteten Images (modules.json / Build-Plan). ==='
                    } else {
                        echo 'Pipeline erfolgreich (Build/Tests/Push nach Plan).'
                    }
                }
            }
        }
    }
