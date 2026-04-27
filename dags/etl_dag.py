import json
from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator
from elasticsearch import Elasticsearch, helpers

INDEX_NAME = "anidex_animes"

MAPPING = {
    "mappings": {
        "properties": {
            "id":         {"type": "integer"},
            "title_en":   {"type": "text"},
            "title_jp":   {"type": "text"},
            "year":       {"type": "integer"},
            "studio":     {"type": "keyword"},
            "score":      {"type": "float"},
            "genres":     {"type": "keyword"},
            "type":       {"type": "keyword"},
            "episodes":   {"type": "integer"},
            "status":     {"type": "keyword"},
            "synopsis":   {"type": "text"},
            "scraped_at": {"type": "date"},
        }
    }
}


def load_to_elasticsearch(**context):
    filepath = context["dag_run"].conf.get("filepath")
    if not filepath:
        filepath = context["ti"].xcom_pull(
            dag_id="scraper_dag", task_ids="scrape_anidex"
        )

    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)

    es = Elasticsearch("http://elasticsearch:9200")

    if not es.indices.exists(index=INDEX_NAME):
        es.indices.create(index=INDEX_NAME, body=MAPPING)

    actions = [
        {
            "_index": INDEX_NAME,
            "_id": anime["id"],
            "_source": {**anime, "scraped_at": data["scraped_at"]},
        }
        for anime in data["animes"]
    ]

    success, errors = helpers.bulk(es, actions, raise_on_error=False)
    print(f"Indexés : {success} | Erreurs : {len(errors)}")
    if errors:
        for err in errors:
            print(f"  -> {err}")


with DAG(
    dag_id="etl_dag",
    schedule=None,
    start_date=datetime(2026, 4, 27),
    catchup=False,
    tags=["anidata", "etl"],
) as dag:

    load = PythonOperator(
        task_id="load_to_elasticsearch",
        python_callable=load_to_elasticsearch,
    )