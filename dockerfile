FROM apache/airflow:2.9.2

USER root
RUN mkdir -p /opt/airflow/data/raw

USER airflow
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY anidata_scraper/ /opt/airflow/anidata_scraper/
COPY dags/ /opt/airflow/dags/