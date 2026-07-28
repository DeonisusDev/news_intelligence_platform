# Architecture

```mermaid
flowchart LR
    A1[NewsAPI.org top-headlines] -->|daily fetch| B[Airflow DAG]
    A2[GNews.io top-headlines] -->|daily fetch| B
    B --> C[(MinIO raw JSON)]
    C --> D[(Postgres raw_articles)]
    D -->|postgresql table function| E[(ClickHouse raw)]
    E --> F[dbt: stage]
    F --> G[dbt: ods]
    G --> H[dbt: mart]
    H --> M[article clustering]
    M --> N[(ClickHouse article_clusters)]
    N --> I[LLM enrichment task]
    I --> J[(ClickHouse summary_clusters)]
    H --> K[FastAPI /discover, /stats]
    N --> K
    J --> K
    D --> L[(Postgres pipeline_run_log)]
    L --> K
```

This file is kept short deliberately during initial build-out; it should be filled in with a full narrative (data flow rationale, layer responsibilities, scaling notes) once the pipeline is complete (Phase 5). See `docs/adr/` for the reasoning behind individual architectural decisions.
