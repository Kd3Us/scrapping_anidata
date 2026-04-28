#!/usr/bin/env bash

cd "$(dirname "$0")/.."

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

GITHUB_TOKEN=$(grep -E '^GITHUB_TOKEN=' .env | cut -d= -f2- | tr -d '\r')
GITHUB_REPOSITORY=$(grep -E '^GITHUB_REPOSITORY=' .env | cut -d= -f2- | tr -d '\r')

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

        docker compose down -v
        docker compose pull
        docker compose up -d

        log "En attente du démarrage d'Airflow..."
        until wget --quiet --output-document=- http://localhost:8080/health 2>/dev/null | grep -q "healthy"; do
            sleep 10
        done
        log "Airflow prêt — activation et déclenchement des DAGs"

        for dag in 00_hello_anidata 01_extract_anime 02_transform_anime 03_load_anime 04_anomaly_detector 05_full_pipeline scraper_dag etl_dag; do
            docker compose exec -T airflow-webserver airflow dags unpause "$dag"
        done

        docker compose exec -T airflow-webserver airflow dags trigger scraper_dag
        docker compose exec -T airflow-webserver airflow dags trigger 05_full_pipeline

        LAST_SHA="$SHA"
    fi

    sleep 30
done
