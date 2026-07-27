{{ config(
    materialized='incremental',
    engine='ReplacingMergeTree(fetched_at)',
    order_by='(url_hash)',
    unique_key='url_hash',
    incremental_strategy='delete+insert'
) }}

select * from {{ ref('stg_articles') }}
{% if is_incremental() %}
where fetched_at > (select max(fetched_at) from {{ this }})
{% endif %}
