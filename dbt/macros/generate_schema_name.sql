{#
    dbt's default macro concatenates <target_schema>_<custom_schema>. This project instead
    uses one ClickHouse database per layer (raw/stage/ods/mart, created in
    sql/clickhouse/001_create_databases.sql) - so a model's `schema:` config should map
    directly onto a database name, with no target-schema prefix.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
