#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_SCRIPT="$SCRIPT_DIR/check_and_deploy.sh"
LOG_FILE="/tmp/anidata_deploy.log"
CRON_MARKER="check_and_deploy.sh"
CRON_LINE="*/5 * * * * bash $DEPLOY_SCRIPT"

if [ ! -f "$DEPLOY_SCRIPT" ]; then
    echo "ERREUR: $DEPLOY_SCRIPT introuvable"
    exit 1
fi

chmod +x "$DEPLOY_SCRIPT"

CURRENT_CRONTAB=$(crontab -l 2>/dev/null || true)

if echo "$CURRENT_CRONTAB" | grep -qF "$CRON_MARKER"; then
    echo "Le cron AniData est deja installe."
    exit 0
fi

(echo "$CURRENT_CRONTAB"; echo "$CRON_LINE") | crontab -
echo "Cron installe : $CRON_LINE"
echo "Logs dans     : $LOG_FILE"
