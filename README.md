# AniData Lab

Pipeline de scraping, transformation, visualisation de données anime, déployé via CI/CD GitHub Actions sur une stack Docker Airflow + Elasticsearch + Grafana.

---

## Architecture

```
Dev
 |
 | git push / git tag
 v
GitHub Actions
 ├── lint   (ruff)
 ├── tests  (pytest 3.10 + 3.11)
 └── build-and-push → GHCR (ghcr.io/Kd3Us/scrapping_anidata-airflow:latest)
                          |
                          | docker compose pull
                          v
                      Airflow (webserver + scheduler)
                          |
                 ┌────────┴────────┐
                 v                 v
           scraper_dag         (trigger)
           [scrape_to_file]        |
                 |                 v
                 └──────→    etl_dag
                          [load_to_elasticsearch]
                                   |
                                   v
                           Elasticsearch :9200
                           (index: anidex_animes)
                                   |
                                   v
                              Grafana :3000
```

---

## Prerequis

- Docker Desktop >= 4.0
- Python 3.10+
- Compte GitHub avec accès au repo `Kd3Us/scrapping_anidata`

---

## Installation

```bash
cp .env.example .env
docker compose up -d
```

Le premier `up` telecharge l'image depuis GHCR, initialise la base Airflow et demarre tous les services.

---

## Lancement

| Service       | URL                      | Identifiants  |
|---------------|--------------------------|---------------|
| Airflow       | http://localhost:8080    | admin / admin |
| Grafana       | http://localhost:3000    | admin / anidata |
| Elasticsearch | http://localhost:9200    | sans auth     |
| Mock-site     | http://localhost:8088    | —             |

Pour demarrer le scraping manuellement, activer le DAG `scraper_dag` dans l'interface Airflow puis le declencher.

---

## DAGs

### scraper_dag

Scrape l'ensemble du catalogue du mock-site (pagination automatique, enrichissement via pages detail, retry exponentiel) et ecrit un fichier `anime_YYYYMMDD_HHMMSS.json` dans `/opt/airflow/data/raw/`. Declenche ensuite `etl_dag` en lui passant le chemin du fichier via XCom.

Schedule : `@daily` — catchup desactive.

### etl_dag

Lit le fichier JSON produit par `scraper_dag` (chemin recupère depuis `dag_run.conf` ou XCom), cree l'index `anidex_animes` dans Elasticsearch si absent (avec mapping complet), puis indexe en masse tous les animes via `helpers.bulk`.

Schedule : `None` (declenche uniquement par `scraper_dag`).

---

## Chaine CI/CD

**Job `lint`** — Execute `ruff check` sur `anidata_scraper/` et `tests/`. Bloque le pipeline si le code ne respecte pas le style defini dans `pyproject.toml`.

**Job `tests`** — Execute `pytest --cov` en parallele sur Python 3.10 et 3.11 (`fail-fast: false`). Valide que les tests passent et que la couverture est disponible avant tout build.

**Job `build-and-push`** — Se declenche uniquement apres `lint` et `tests`, et seulement sur push vers `master` ou tag semver. Construit l'image Docker et la pousse sur GHCR avec les tags `latest`, `sha-<court>` et `vX.Y.Z`.

---

## Deploiement

Apres un merge sur `master` et une CI verte, l'image est publiee automatiquement sur GHCR. Pour mettre a jour un environnement existant :

```bash
docker compose pull
docker compose up -d
```

---

## Developpement local (sans Docker)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

pytest --cov=anidata_scraper --cov-report=term-missing
ruff check anidata_scraper/ tests/

python -m anidata_scraper.scraper --base-url http://localhost:8088 --output-dir ./data/raw
```

---

## Declencher le pipeline de versioning

Pour publier une version taguee sur GHCR :

```bash
git tag v1.0.0
git push origin v1.0.0
```
test2