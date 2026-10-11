"""Pydantic schemas for /api/v1/evaluations endpoints.

Matches BACKEND SCHEMA.md Section 18.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class EvaluationMetricsRead(BaseModel):
    recall_at_5: float | None = None
    recall_at_10: float | None = None
    mrr: float | None = None
    ndcg_at_10: float | None = None
    groundedness: float | None = None
    citation_accuracy: float | None = None
    citation_completeness: float | None = None
    abstention_accuracy: float | None = None
    mean_latency_ms: float | None = None


class EvaluationRunCreate(BaseModel):
    evaluation_set_id: uuid.UUID | None = None
    pipeline_type: str = Field(
        "agentic_retrieval",
        description="Pipeline to evaluate: no_reranker, reranker, agentic_retrieval, or all",
    )
    configuration: dict[str, Any] | None = None


class EvaluationRunRead(BaseModel):
    id: uuid.UUID
    evaluation_set_id: uuid.UUID | None = None
    status: str
    pipeline_type: str | None = None
    configuration: dict[str, Any] | None = None
    metrics: EvaluationMetricsRead | None = None
    started_at: datetime
    finished_at: datetime | None = None
