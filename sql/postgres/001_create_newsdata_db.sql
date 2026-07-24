-- Runs once against the default POSTGRES_DB (airflow) on first container init.
-- Creates the separate application database used for raw ingestion + audit tables,
-- kept apart from Airflow's own metadata DB.
CREATE DATABASE newsdata;
