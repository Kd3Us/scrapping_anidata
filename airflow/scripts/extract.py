import glob
import json
import os
import pandas as pd

# Offset pour éviter les collisions avec les vrais MAL_ID (max ~56k)
SCRAPER_MAL_ID_OFFSET = 900_000


CSV_SOURCE = "/opt/airflow/data/raw"
REP_SOURCE = "/opt/airflow/data"

EXPECTED_SCHEMAS = {
    "anime": {
        "file": "anime.csv",
        "required_columns": [
            "MAL_ID", "Name", "Score", "Genres", "Type",
            "Episodes", "Studios", "Source", "Members",
            "Favorites", "Watching", "Completed", "On-Hold",
            "Dropped", "Plan to Watch"
        ],
    },
    "ratings": {
        "file": "rating_complete.csv",
        "required_columns": ["user_id", "anime_id", "rating"],
    },
    "synopsis": {
        "file": "anime_with_synopsis.csv",
        "required_columns": ["MAL_ID", "Name", "Score", "Genres", "sypnopsis"],
    },
}


# Charge un CSV et sauvegarde en parquet pour passage inter-tasks
def extract_csv(dataset_key):
    schema = EXPECTED_SCHEMAS[dataset_key]
    filepath = os.path.join(CSV_SOURCE, schema["file"])

    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Fichier introuvable : {filepath}")

    df = pd.read_csv(filepath)

    output_path = os.path.join(REP_SOURCE, f"raw_{dataset_key}.parquet")
    df.to_parquet(output_path, index=False)

    return {
        "dataset": dataset_key,
        "source_file": filepath,
        "output_path": output_path,
        "rows": len(df),
        "columns": list(df.columns),
    }


def extract_scraper_json():
    """Enrichit raw_anime et raw_synopsis avec le dernier JSON scrappé."""
    files = sorted(glob.glob(os.path.join(CSV_SOURCE, "anime_*.json")))
    if not files:
        print("Aucun fichier JSON scrappé trouvé, skip.")
        return {"source": None, "rows_added": 0, "synopsis_updated": 0}

    latest_json = files[-1]
    with open(latest_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    scraper_animes = data.get("animes", [])
    if not scraper_animes:
        return {"source": latest_json, "rows_added": 0, "synopsis_updated": 0}

    # --- Enrich raw_anime.parquet ---
    anime_path = os.path.join(REP_SOURCE, "raw_anime.parquet")
    df_anime = pd.read_parquet(anime_path)
    existing_names = set(df_anime["Name"].str.lower().str.strip())

    def to_anime_row(a):
        return {
            "MAL_ID": SCRAPER_MAL_ID_OFFSET + a["id"],
            "Name": a.get("title_en", ""),
            "Score": a.get("score"),
            "Genres": ", ".join(a["genres"]) if a.get("genres") else None,
            "Type": a.get("type"),
            "Episodes": a.get("episodes"),
            "Studios": a.get("studio"),
            "Source": None,
            "Members": None,
            "Favorites": None,
            "Watching": None,
            "Completed": None,
            "On-Hold": None,
            "Dropped": None,
            "Plan to Watch": None,
        }

    df_scraped = pd.DataFrame([to_anime_row(a) for a in scraper_animes])
    df_new_anime = df_scraped[
        ~df_scraped["Name"].str.lower().str.strip().isin(existing_names)
    ]

    rows_added = 0
    if not df_new_anime.empty:
        pd.concat([df_anime, df_new_anime], ignore_index=True).to_parquet(anime_path, index=False)
        rows_added = len(df_new_anime)
        print(f"{rows_added} nouveaux animes ajoutés depuis le scraper.")

    # --- Enrich raw_synopsis.parquet ---
    synopsis_path = os.path.join(REP_SOURCE, "raw_synopsis.parquet")
    df_syn = pd.read_parquet(synopsis_path)
    existing_mal_syn = set(df_syn["MAL_ID"])

    # Reconstruction du mapping name→MAL_ID après enrichissement anime
    df_anime_updated = pd.read_parquet(anime_path)
    name_to_mal = dict(zip(
        df_anime_updated["Name"].str.lower().str.strip(),
        df_anime_updated["MAL_ID"],
    ))

    def to_synopsis_row(a):
        name = a.get("title_en", "")
        mal_id = name_to_mal.get(name.lower().strip(), SCRAPER_MAL_ID_OFFSET + a["id"])
        return {
            "MAL_ID": mal_id,
            "Name": name,
            "Score": a.get("score"),
            "Genres": ", ".join(a["genres"]) if a.get("genres") else None,
            "sypnopsis": a.get("synopsis"),
        }

    df_syn_scraped = pd.DataFrame([
        to_synopsis_row(a) for a in scraper_animes if a.get("synopsis")
    ])
    df_new_syn = df_syn_scraped[~df_syn_scraped["MAL_ID"].isin(existing_mal_syn)]

    synopsis_updated = 0
    if not df_new_syn.empty:
        pd.concat([df_syn, df_new_syn], ignore_index=True).to_parquet(synopsis_path, index=False)
        synopsis_updated = len(df_new_syn)
        print(f"{synopsis_updated} synopsis ajoutés depuis le scraper.")

    return {"source": latest_json, "rows_added": rows_added, "synopsis_updated": synopsis_updated}


# Vérifie que les colonnes obligatoires sont présentes
def validate_schema(dataset_key, extract_result):
    schema = EXPECTED_SCHEMAS[dataset_key]
    actual_columns = set(extract_result["columns"])
    required = set(schema["required_columns"])

    missing = required - actual_columns
    if missing:
        raise ValueError(f"[{dataset_key}] Colonnes manquantes : {missing}")

    return {
        "dataset": dataset_key,
        "status": "valid",
        "rows": extract_result["rows"],
        "columns_checked": len(required),
    }
