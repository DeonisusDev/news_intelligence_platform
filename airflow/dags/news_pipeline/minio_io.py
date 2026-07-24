"""Thin wrapper over S3Hook for the MinIO raw JSON landing zone.

Bucket creation is handled idempotently here too (not only by the docker-compose
`minio-createbuckets` init container), since depends_on/healthchecks only guarantee
container *start order*, not that the init container's mc command has actually finished
before the DAG's first real run.
"""
from __future__ import annotations

import json

from airflow.providers.amazon.aws.hooks.s3 import S3Hook

MINIO_CONN_ID = "minio_s3"


def _hook() -> S3Hook:
    return S3Hook(aws_conn_id=MINIO_CONN_ID)


def ensure_bucket(bucket: str) -> None:
    hook = _hook()
    if not hook.check_for_bucket(bucket):
        hook.create_bucket(bucket_name=bucket)


def put_json(bucket: str, key: str, payload: dict | list) -> None:
    hook = _hook()
    ensure_bucket(bucket)
    hook.load_string(
        string_data=json.dumps(payload, ensure_ascii=False),
        key=key,
        bucket_name=bucket,
        replace=True,
    )


def get_json(bucket: str, key: str) -> dict | list:
    hook = _hook()
    raw = hook.read_key(key=key, bucket_name=bucket)
    return json.loads(raw)
