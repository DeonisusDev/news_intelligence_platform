-- One ClickHouse database per dbt layer. dbt's generate_schema_name macro is overridden
-- (see dbt/macros/generate_schema_name.sql) to map a model's `schema:` config directly onto
-- one of these databases, ignoring the target/profile schema prefix dbt uses by default.
CREATE DATABASE IF NOT EXISTS raw;
CREATE DATABASE IF NOT EXISTS stage;
CREATE DATABASE IF NOT EXISTS ods;
CREATE DATABASE IF NOT EXISTS mart;
