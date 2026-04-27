from datetime import datetime
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator

import sys
sys.path.insert(0, "/opt/airflow")

from anidata_scraper import scrape_to_file

with DAG(
    dag_id="scraper_dag",
    schedule="@daily",
    start_date=datetime(2026, 4, 27),
    catchup=False,
    tags=["anidata", "scraping"],
) as dag:

    scrape = PythonOperator(
        task_id="scrape_anidex",
        python_callable=scrape_to_file,
        op_kwargs={
            "output_dir": "/opt/airflow/data/raw",
            "base_url": "http://mock-site",
            "enrich": True,
        },
    )

    trigger_etl = TriggerDagRunOperator(
        task_id="trigger_etl_dag",
        trigger_dag_id="etl_dag",
        conf={"filepath": "{{ ti.xcom_pull(task_ids='scrape_anidex') }}"},
        wait_for_completion=False,
    )

    scrape >> trigger_etl