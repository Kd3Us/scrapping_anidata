#!/usr/bin/env python3
"""Affiche les derniers runs GitHub Actions pour diagnostiquer l'état de la CI."""

import sys
from pathlib import Path

import requests

PROJECT_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_DIR / ".env"

env = {}
for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip()

token = env.get("GITHUB_TOKEN", "")
repo = env.get("GITHUB_REPOSITORY", "")

if not token or not repo:
    print("ERREUR: GITHUB_TOKEN ou GITHUB_REPOSITORY manquant dans .env")
    sys.exit(1)

r = requests.get(
    f"https://api.github.com/repos/{repo}/actions/runs",
    headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
    params={"branch": "master", "per_page": 5},
    timeout=15,
)
r.raise_for_status()

runs = r.json().get("workflow_runs", [])
print(f"{'ID':<12} {'Conclusion':<12} {'SHA':<8} {'Date':<22} Nom")
print("-" * 75)
for run in runs:
    print(
        f"{run['id']:<12} {str(run['conclusion']):<12} {run['head_sha'][:7]:<8}"
        f" {run['created_at']:<22} {run['name']}"
    )
