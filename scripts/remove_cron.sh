#!/usr/bin/env bash
set -euo pipefail

CRON_MARKER="check_and_deploy.sh"

CURRENT_CRONTAB=$(crontab -l 2>/dev/null || true)

if ! echo "$CURRENT_CRONTAB" | grep -qF "$CRON_MARKER"; then
    echo "Aucun cron AniData trouve."
    exit 0
fi

echo "$CURRENT_CRONTAB" | grep -vF "$CRON_MARKER" | crontab -
echo "Cron AniData supprime."
