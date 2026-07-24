.PHONY: up down logs ps psql ch-client dbt-run restart-airflow

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f --tail=200

ps:
	docker compose ps

psql:
	docker compose exec postgres psql -U $${POSTGRES_USER:-airflow} -d $${NEWSDATA_DB:-newsdata}

ch-client:
	docker compose exec clickhouse clickhouse-client

dbt-run:
	docker compose exec airflow-scheduler /opt/airflow/dbt_venv/bin/dbt build --profiles-dir /opt/airflow/dbt --project-dir /opt/airflow/dbt

restart-airflow:
	docker compose restart airflow-apiserver airflow-scheduler airflow-dag-processor airflow-triggerer
