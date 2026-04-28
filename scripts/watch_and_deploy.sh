#!/usr/bin/env bash

set -e

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

die() {
    log "ERREUR : $1"
    exit 1
}

for tool in wget jq docker; do
    command -v "$tool" > /dev/null 2>&1 || die "Outil manquant : $tool"
done

docker info > /dev/null 2>&1 || die "Docker n'est pas accessible"

for f in \
    .env \
    .gitignore \
    docker-compose.yml \
    Dockerfile \
    requirements.txt \
    requirements-dev.txt \
    pyproject.toml \
    .github/workflows/ci-cd.yml \
    airflow/dags/scraper_dag.py \
    airflow/dags/etl_dag.py \
    anidata_scraper/__init__.py \
    anidata_scraper/scraper.py \
    tests/ \
    mock-site/docker-compose.yml; do
    [ -e "$f" ] || die "Fichier ou dossier manquant : $f"
done

for var in GITHUB_TOKEN GITHUB_REPOSITORY; do
    grep -q "^${var}=" .env || die "Variable manquante dans .env : $var"
done

GITHUB_TOKEN=$(grep -E '^GITHUB_TOKEN=' .env | cut -d= -f2- | tr -d '\r')
GITHUB_REPOSITORY=$(grep -E '^GITHUB_REPOSITORY=' .env | cut -d= -f2- | tr -d '\r')

docker image inspect "ghcr.io/${GITHUB_REPOSITORY}-airflow:latest" > /dev/null 2>&1 \
    || die "Image Docker ghcr.io/${GITHUB_REPOSITORY}-airflow:latest absente localement"

docker compose ps | grep -q "airflow-webserver" \
    || die "Conteneur airflow-webserver introuvable"

docker compose ps | grep -q "airflow-scheduler" \
    || die "Conteneur airflow-scheduler introuvable"

wget --quiet --output-document=- http://localhost:8080/health > /dev/null 2>&1 \
    || die "Health check Airflow échoué (http://localhost:8080/health)"

wget --quiet --output-document=- http://localhost:9200 > /dev/null 2>&1 \
    || die "Health check Elasticsearch échoué (http://localhost:9200)"

log "Preflight OK — démarrage de la surveillance"

set +e

LAST_SHA=""

trap 'log "Arrêt de la surveillance"; exit 0' INT

while true; do
    RESPONSE=$(wget --quiet --output-document=- \
        --header="Authorization: Bearer ${GITHUB_TOKEN}" \
        --header="Accept: application/vnd.github+json" \
        "https://api.github.com/repos/${GITHUB_REPOSITORY}/actions/runs?branch=master&per_page=1" 2>/dev/null)

    CONCLUSION=$(echo "$RESPONSE" | jq -r '.workflow_runs[0].conclusion // empty')
    SHA=$(echo "$RESPONSE" | jq -r '.workflow_runs[0].head_sha // empty')

    if [ "$CONCLUSION" = "success" ] && [ -n "$SHA" ] && [ "$SHA" != "$LAST_SHA" ]; then
        log "Nouveau déploiement détecté (sha: ${SHA})"

        docker compose pull
        docker compose up -d --no-deps airflow-webserver airflow-scheduler

        if wget --quiet --output-document=- http://localhost:8080/health > /dev/null 2>&1; then
            log "Health check Airflow : OK"
        else
            log "Health check Airflow : KO"
        fi

        if wget --quiet --output-document=- http://localhost:9200 > /dev/null 2>&1; then
            log "Health check Elasticsearch : OK"
        else
            log "Health check Elasticsearch : KO"
        fi

        LAST_SHA="$SHA"
    fi

    sleep 30
done
