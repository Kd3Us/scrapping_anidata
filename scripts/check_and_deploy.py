import argparse
import datetime
import os
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


def log(message):
    entry = f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {message}"
    print(entry)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(entry + "\n")


def load_env(path):
    env = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip()
    return env


def get_ci_status(repo, token):
    """Appelle l'API GitHub Actions et retourne (conclusion, sha) du dernier run sur master."""
    r = requests.get(
        f"https://api.github.com/repos/{repo}/actions/runs",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
        params={"per_page": 10},
        timeout=15,
    )
    r.raise_for_status()
    runs = [r for r in r.json().get("workflow_runs", []) if r.get("head_branch") == "master"]
    if not runs:
        return "none", ""
    return runs[0].get("conclusion") or "none", runs[0].get("head_sha", "")


def get_last_sha():
    result = subprocess.run(
        ["docker", "exec", "anidata-postgres", "psql", "-U", "airflow", "-d", "airflow",
         "-t", "-c", "SELECT sha FROM cd_deployments ORDER BY deployed_at DESC LIMIT 1;"],
        capture_output=True, text=True,
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    if LAST_SHA_FILE.exists():
        return LAST_SHA_FILE.read_text(encoding="utf-8").strip()
    return ""


def save_deployment(sha):
    sql = (
        "CREATE TABLE IF NOT EXISTS cd_deployments ("
        "id SERIAL PRIMARY KEY, sha VARCHAR(40) NOT NULL, "
        "deployed_at TIMESTAMPTZ DEFAULT NOW(), status VARCHAR(20) DEFAULT 'success');"
        f"INSERT INTO cd_deployments (sha) VALUES ('{sha}');"
    )
    subprocess.run(
        ["docker", "exec", "anidata-postgres", "psql", "-U", "airflow", "-d", "airflow", "-c", sql],
        capture_output=True,
    )
    LAST_SHA_FILE.write_text(sha, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sha", default="")
    args = parser.parse_args()

    if not ENV_FILE.exists():
        log(f"ERREUR: .env introuvable dans {PROJECT_DIR}")
        sys.exit(1)

    env = load_env(ENV_FILE)

    # détection docker compose (nouvelle syntaxe vs ancienne)
    result = subprocess.run(["docker", "compose", "version"], capture_output=True)
    compose = ["docker", "compose"] if result.returncode == 0 else ["docker-compose"]

    head_sha = args.sha

    if not head_sha:
        token = env.get("GITHUB_TOKEN", "")
        repo = env.get("GITHUB_REPOSITORY", "")

        if not token or not repo:
            log("ERREUR: GITHUB_TOKEN ou GITHUB_REPOSITORY manquant dans .env")
            sys.exit(1)

        try:
            conclusion, head_sha = get_ci_status(repo, token)
        except requests.RequestException as e:
            log(f"ERREUR: API GitHub inaccessible - {e}")
            sys.exit(1)

        if conclusion != "success":
            log(f"CI pas verte ({conclusion}), pas de déploiement")
            sys.exit(0)

    last_sha = get_last_sha()

    if head_sha and head_sha == last_sha:
        log(f"Déjà à jour, rien à faire (SHA: {head_sha})")
        sys.exit(0)

    log(f"Nouvelle image détectée (SHA: {head_sha}) — déploiement en cours...")

    os.chdir(PROJECT_DIR)
    with LOG_FILE.open("a", encoding="utf-8") as lf:
        subprocess.run([*compose, "pull"], stdout=lf, stderr=lf)
        subprocess.run(
            [*compose, "up", "-d", "--no-deps", "airflow-webserver", "airflow-scheduler", "airflow-init"],
            stdout=lf, stderr=lf,
        )

    save_deployment(head_sha)
    log(f"Déploiement OK — SHA: {head_sha}")


if __name__ == "__main__":
    main()
