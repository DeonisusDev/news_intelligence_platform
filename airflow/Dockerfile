FROM apache/airflow:3.0.2-python3.12

COPY airflow/requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt

# dbt lives in its own venv: dbt-core's pinned deps regularly conflict with
# Airflow's constraints file, so we keep it fully isolated from Airflow's env.
COPY airflow/dbt-requirements.txt /dbt-requirements.txt
RUN python -m venv /opt/airflow/dbt_venv \
    && /opt/airflow/dbt_venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/airflow/dbt_venv/bin/pip install --no-cache-dir -r /dbt-requirements.txt
