#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="/tmp/anidata_deploy.log"
LAST_SHA_FILE="$PROJECT_DIR/.last_deployed_sha"
ENV_FILE="$PROJECT_DIR/.env"

log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo "$msg" >> "$LOG_FILE"
    [ -t 1 ] && echo "$msg" || true
}

if [ ! -f "$ENV_FILE" ]; then
    log "ERREUR: fichier .env introuvable dans $PROJECT_DIR"
    exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

if [ -z "${GITHUB_TOKEN:-}" ]; then
    log "ERREUR: GITHUB_TOKEN non defini dans .env"
    exit 1
fi

if [ -z "${GITHUB_REPOSITORY:-}" ]; then
    log "ERREUR: GITHUB_REPOSITORY non defini dans .env"
    exit 1
fi

if docker compose version > /dev/null 2>&1; then
    DOCKER_COMPOSE="docker compose"
elif command -v docker-compose > /dev/null 2>&1; then
    DOCKER_COMPOSE="docker-compose"
else
    log "ERREUR: docker compose introuvable"
    exit 1
fi

RESPONSE=$(curl -s \
    -H "Authorization: Bearer ${GITHUB_TOKEN}" \
    -H "Accept: application/vnd.github+json" \
    "https://api.github.com/repos/${GITHUB_REPOSITORY}/actions/runs?branch=master&per_page=1") || {
    log "ERREUR: impossible de joindre l'API GitHub"
    exit 1
}

PARSED=$(echo "$RESPONSE" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
except json.JSONDecodeError:
    print('none')
    print('')
    sys.exit(0)
runs = data.get('workflow_runs', [])
if runs:
    print(runs[0].get('conclusion') or 'none')
    print(runs[0].get('head_sha') or '')
else:
    print('none')
    print('')
")

CONCLUSION=$(echo "$PARSED" | sed -n '1p')
HEAD_SHA=$(echo "$PARSED" | sed -n '2p')

if [ "$CONCLUSION" != "success" ]; then
    log "CI pas verte ($CONCLUSION), pas de deploiement"
    exit 0
fi

LAST_SHA=""
if [ -f "$LAST_SHA_FILE" ]; then
    LAST_SHA=$(cat "$LAST_SHA_FILE")
fi

if [ -n "$HEAD_SHA" ] && [ "$HEAD_SHA" = "$LAST_SHA" ]; then
    log "Deja a jour, rien a faire"
    exit 0
fi

log "Nouvelle image detectee (SHA: $HEAD_SHA) - deploiement en cours..."

cd "$PROJECT_DIR"
$DOCKER_COMPOSE pull >> "$LOG_FILE" 2>&1
$DOCKER_COMPOSE up -d --no-deps airflow-webserver airflow-scheduler airflow-init >> "$LOG_FILE" 2>&1

echo "$HEAD_SHA" > "$LAST_SHA_FILE"
log "Deploiement OK - SHA: $HEAD_SHA"
