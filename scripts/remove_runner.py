#!/usr/bin/env python3
"""Supprime le GitHub Actions self-hosted runner AniData."""

import shutil
import subprocess
import sys
from pathlib import Path

RUNNER_DIR = Path.home() / "anidata-runner"


def main() -> None:
    if not RUNNER_DIR.exists():
        print(f"Aucun runner AniData trouvé dans {RUNNER_DIR}")
        sys.exit(0)

    token = input(
        "Token de suppression GitHub (laisse vide si tu le supprimes manuellement sur GitHub) : "
    ).strip()

    if token:
        subprocess.run(
            [str(RUNNER_DIR / "config.cmd"), "remove", "--token", token],
            cwd=RUNNER_DIR,
        )
    else:
        print("Supprime le runner manuellement sur GitHub :")
        print("  github.com/{repo}/settings/actions/runners")

    shutil.rmtree(RUNNER_DIR)

    # Supprime la variable d'environnement utilisateur Windows si elle existe
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_WRITE)
        try:
            winreg.DeleteValue(key, "ANIDATA_PROJECT_DIR")
        except FileNotFoundError:
            pass
        winreg.CloseKey(key)
    except ImportError:
        pass

    print("Runner supprimé.")


if __name__ == "__main__":
    main()
