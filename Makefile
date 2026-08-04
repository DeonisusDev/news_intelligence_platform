.PHONY: up down logs ps psql ch-client dbt-run dbt-docs restart-airflow

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

# --target-path/--log-path point at /tmp: dbt/ is bind-mounted from the host (host-owned), but
# the container runs as AIRFLOW_UID (50000) and can't mkdir under a host-owned directory (same
# constraint as the DAG's dbt_run task - see dbt_project.yml's comment). The generated docs are
# then copied out to dbt/target/ (gitignored) for serving on the host.
dbt-docs:
	docker compose exec airflow-scheduler /opt/airflow/dbt_venv/bin/dbt docs generate --profiles-dir /opt/airflow/dbt --project-dir /opt/airflow/dbt --target prod --log-path /tmp/dbt_logs --target-path /tmp/dbt_target
	rm -rf dbt/target
	docker compose cp airflow-scheduler:/tmp/dbt_target dbt/target
	@echo "Docs generated at dbt/target/index.html - serve with: python3 -m http.server 8180 --directory dbt/target"

restart-airflow:
	docker compose restart airflow-apiserver airflow-scheduler airflow-dag-processor airflow-triggerer
