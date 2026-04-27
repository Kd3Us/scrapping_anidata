#!/usr/bin/env python3
"""Configure un GitHub Actions self-hosted runner pour AniData."""

import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import requests

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
ENV_FILE = PROJECT_DIR / ".env"
RUNNER_DIR = Path.home() / "anidata-runner"


def load_env(path: Path) -> dict:
    env = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip()
    return env


def main() -> None:
    env = load_env(ENV_FILE)
    repo = env.get("GITHUB_REPOSITORY", "")
    if not repo:
        print("ERREUR: GITHUB_REPOSITORY non défini dans .env")
        sys.exit(1)

    repo_url = f"https://github.com/{repo}"
    token_page_url = f"{repo_url}/settings/actions/runners/new?runnerOs=win"

    RUNNER_DIR.mkdir(parents=True, exist_ok=True)
    path_file = RUNNER_DIR / "project_path.txt"
    path_file.write_text(str(PROJECT_DIR), encoding="utf-8")
    print(f"Chemin projet sauvegardé : {path_file}")

    print()
    print("Ouvre ce lien dans ton navigateur :")
    print(f"  {token_page_url}")
    print()
    print("Sélectionne : Windows x64")
    print("Repère la ligne : --token XXXXXXXXXX")
    print("Copie uniquement la valeur du token (après --token)")
    print()

    token = input("Colle le token GitHub ici : ").strip()
    if not token:
        print("ERREUR: token vide")
        sys.exit(1)

    print("Téléchargement du runner GitHub Actions...")
    release = requests.get(
        "https://api.github.com/repos/actions/runner/releases/latest",
        headers={"Accept": "application/vnd.github+json"},
        timeout=15,
    ).json()

    asset = next(
        (
            a for a in release.get("assets", [])
            if "actions-runner-win-x64-" in a["name"] and a["name"].endswith(".zip")
        ),
        None,
    )
    if not asset:
        print("ERREUR: impossible de trouver l'archive du runner")
        sys.exit(1)

    zip_path = Path(tempfile.gettempdir()) / "actions-runner.zip"
    with requests.get(asset["browser_download_url"], stream=True, timeout=120) as r:
        r.raise_for_status()
        with zip_path.open("wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

    print("Extraction...")
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(RUNNER_DIR)
    zip_path.unlink()

    print("Configuration du runner...")
    subprocess.run(
        [
            str(RUNNER_DIR / "config.cmd"),
            "--url", repo_url,
            "--token", token,
            "--name", "anidata-local",
            "--labels", "self-hosted",
            "--unattended",
        ],
        cwd=RUNNER_DIR,
        check=True,
    )

    print()
    print("Runner configuré.")
    print()
    print("Pour le démarrer (laisse ce terminal ouvert) :")
    print(f"  cd {RUNNER_DIR}")
    print(r"  .\run.cmd")
    print()
    print("Vérifie qu'il apparaît ici :")
    print(f"  {repo_url}/settings/actions/runners")


if __name__ == "__main__":
    main()
