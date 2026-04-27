#!/usr/bin/env python3
"""CD agent : vérifie si la CI GitHub est verte et déploie la nouvelle image Docker."""

import argparse
import datetime
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import requests

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
LOG_FILE = Path(tempfile.gettempdir()) / "anidata_deploy.log"
LAST_SHA_FILE = PROJECT_DIR / ".last_deployed_sha"
ENV_FILE = PROJECT_DIR / ".env"


def log(message: str) -> None:
    entry = f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {message}"
    print(entry)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(entry + "\n")


def load_env(path: Path) -> dict:
    env = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip()
    return env


def detect_compose() -> list:
    """Retourne la commande docker compose disponible sous forme de liste."""
    result = subprocess.run(["docker", "compose", "version"], capture_output=True)
    if result.returncode == 0:
        return ["docker", "compose"]
    result = subprocess.run(["docker-compose", "version"], capture_output=True)
    if result.returncode == 0:
        return ["docker-compose"]
    raise RuntimeError("docker compose introuvable")


def get_last_sha() -> str:
    """Récupère le dernier SHA déployé depuis Postgres, avec fallback sur fichier."""
    result = subprocess.run(
        [
            "docker", "exec", "anidata-postgres",
            "psql", "-U", "airflow", "-d", "airflow", "-t", "-c",
            "SELECT sha FROM cd_deployments ORDER BY deployed_at DESC LIMIT 1;",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        sha = result.stdout.strip()
        if sha:
            return sha
    if LAST_SHA_FILE.exists():
        return LAST_SHA_FILE.read_text(encoding="utf-8").strip()
    return ""


def validate_sha(sha: str) -> str:
    """Valide que le SHA ne contient que des caractères hexadécimaux (protection injection SQL)."""
    if not re.fullmatch(r"[0-9a-fA-F]{7,40}", sha):
        raise ValueError(f"SHA invalide : {sha!r}")
    return sha


def save_deployment(sha: str) -> None:
    """Enregistre le SHA déployé dans Postgres et dans le fichier de fallback."""
    sql = (
        "CREATE TABLE IF NOT EXISTS cd_deployments ("
        "id SERIAL PRIMARY KEY, "
        "sha VARCHAR(40) NOT NULL, "
        "deployed_at TIMESTAMPTZ DEFAULT NOW(), "
        "status VARCHAR(20) NOT NULL DEFAULT 'success'"
        "); "
        f"INSERT INTO cd_deployments (sha) VALUES ('{sha}');"
    )
    subprocess.run(
        ["docker", "exec", "anidata-postgres", "psql", "-U", "airflow", "-d", "airflow", "-c", sql],
        capture_output=True,
    )
    LAST_SHA_FILE.write_text(sha, encoding="utf-8")


def get_latest_run(repo: str, token: str) -> tuple:
    """Retourne (conclusion, head_sha) du dernier workflow run sur master."""
    response = requests.get(
        f"https://api.github.com/repos/{repo}/actions/runs",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        },
        params={"per_page": 10},
        timeout=15,
    )
    response.raise_for_status()
    runs = response.json().get("workflow_runs", [])
    master_runs = [r for r in runs if r.get("head_branch") == "master"]
    if not master_runs:
        return "none", ""
    run = master_runs[0]
    return run.get("conclusion") or "none", run.get("head_sha", "")


def main() -> None:
    parser = argparse.ArgumentParser(description="AniData CD agent")
    parser.add_argument("--sha", default="", help="Commit SHA (passé par GitHub Actions)")
    args = parser.parse_args()

    if not ENV_FILE.exists():
        log(f"ERREUR: fichier .env introuvable dans {PROJECT_DIR}")
        sys.exit(1)

    env = load_env(ENV_FILE)

    try:
        compose = detect_compose()
    except RuntimeError as exc:
        log(f"ERREUR: {exc}")
        sys.exit(1)

    head_sha = args.sha

    if not head_sha:
        token = env.get("GITHUB_TOKEN", "")
        repo = env.get("GITHUB_REPOSITORY", "")

        if not token:
            log("ERREUR: GITHUB_TOKEN non défini dans .env")
            sys.exit(1)
        if not repo:
            log("ERREUR: GITHUB_REPOSITORY non défini dans .env")
            sys.exit(1)

        try:
            conclusion, head_sha = get_latest_run(repo, token)
        except requests.RequestException as exc:
            log(f"ERREUR: impossible de joindre l'API GitHub - {exc}")
            sys.exit(1)

        if conclusion != "success":
            log(f"CI pas verte ({conclusion}), pas de déploiement")
            sys.exit(0)

    try:
        head_sha = validate_sha(head_sha)
    except ValueError as exc:
        log(f"ERREUR: {exc}")
        sys.exit(1)

    last_sha = get_last_sha()

    if head_sha and head_sha == last_sha:
        log(f"Déjà à jour, rien à faire (SHA: {head_sha})")
        sys.exit(0)

    log(f"Nouvelle image détectée (SHA: {head_sha}) — déploiement en cours...")

    os.chdir(PROJECT_DIR)

    with LOG_FILE.open("a", encoding="utf-8") as log_f:
        subprocess.run([*compose, "pull"], stdout=log_f, stderr=log_f)
        subprocess.run(
            [*compose, "up", "-d", "--no-deps", "airflow-webserver", "airflow-scheduler", "airflow-init"],
            stdout=log_f,
            stderr=log_f,
        )

    save_deployment(head_sha)
    log(f"Déploiement OK — SHA: {head_sha}")


if __name__ == "__main__":
    main()
