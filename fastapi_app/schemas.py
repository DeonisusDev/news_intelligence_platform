"""Pydantic response models. Named around the Discovery-feed shape: one summary card per
story-cluster, expandable into its individual source articles - not a flat article list.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field


class SummaryCard(BaseModel):
    cluster_id: str
    summary: str
    topic: str
    sentiment: str
    sentiment_score: float | None
    keywords: list[str]
    article_count: int
    enriched_at: datetime
    first_published_at: datetime
    image_url: str | None


class SourceArticle(BaseModel):
    source_name: str | None
    source_provider: str | None
    title: str | None
    url: str
    url_to_image: str | None
    published_at: datetime | None
    category: str | None
    # Phase 6.1: "what this outlet focused on," matched by url_hash server-side - not present
    # on every source (e.g. the model omitted it, or a single-source cluster has none at all).
    source_summary: str | None = None


class KeyFacts(BaseModel):
    organizations: list[str]
    locations: list[str]
    people: list[str]


class SummaryDetail(SummaryCard):
    sources: list[SourceArticle]
    # Phase 6.1 - detail-view-only fields, never selected by the /discover list endpoint.
    key_facts: KeyFacts
    why_it_matters: str
    before_state: str | None
    after_state: str | None
    consensus_points: list[str]
    disagreement_points: list[str]


class DailyStat(BaseModel):
    published_date: date
    source_name: str | None
    article_count: int


class TopicStat(BaseModel):
    topic: str
    cluster_count: int


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserPublic(BaseModel):
    id: int
    email: str
    created_at: datetime


class PipelineRun(BaseModel):
    run_id: str
    dag_id: str
    task_id: str
    try_number: int
    status: str
    started_at: datetime
    finished_at: datetime | None
    rows_fetched: int
    rows_new: int
    rows_duplicate: int
    rows_failed: int
    error_message: str | None
