"""Structured observability for queries, retrieval, LLM generation, and ingestion.

Phase 16 requirement:
Track:
- query ID
- request ID
- retrieval latency
- reranking latency
- LLM latency
- total latency
- retrieved candidates
- citation count
- abstention
- provider
- model
- token usage
- errors

Record timing for:
- preprocessing
- retrieval
- fusion
- reranking
- generation
- validation
- total request

Rule 4 & 8: Never log API keys, passwords, or full sensitive prompts.
"""

from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass, field

from apps.api.app.core.logging import logger


@dataclass
class QueryTimings:
    preprocessing_ms: float = 0.0
    retrieval_ms: float = 0.0
    fusion_ms: float = 0.0
    reranking_ms: float = 0.0
    generation_ms: float = 0.0
    validation_ms: float = 0.0
    total_ms: float = 0.0


@dataclass
class QueryMetrics:
    query_id: str
    request_id: str
    user_id: str
    provider: str = ""
    model: str = ""
    retrieval_latency_ms: float = 0.0
    reranking_latency_ms: float = 0.0
    llm_latency_ms: float = 0.0
    total_latency_ms: float = 0.0
    retrieved_candidates: int = 0
    citation_count: int = 0
    grounded: bool = False
    abstained: bool = False
    token_usage: dict[str, int] = field(default_factory=dict)
    timings: QueryTimings = field(default_factory=QueryTimings)
    error: str | None = None

    def log(self, log_level: int = logging.INFO) -> None:
        """Emit structured JSON log record with full diagnostics (Phase 16)."""
        data = asdict(self)
        logger.log(
            log_level,
            f"Query observability metrics [query_id={self.query_id}]",
            extra={"extra": {"event": "query_observability", **data}},
        )


class QueryTimer:
    """Context manager / stopwatch for tracking sub-stage latencies in the query pipeline."""

    def __init__(self, query_id: str, request_id: str, user_id: str) -> None:
        self.query_id = query_id
        self.request_id = request_id
        self.user_id = user_id
        self.timings = QueryTimings()
        self._start_total = time.perf_counter()
        self._stage_starts: dict[str, float] = {}

    def start_stage(self, stage_name: str) -> None:
        self._stage_starts[stage_name] = time.perf_counter()

    def end_stage(self, stage_name: str) -> float:
        start = self._stage_starts.get(stage_name)
        if start is None:
            return 0.0
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        if hasattr(self.timings, f"{stage_name}_ms"):
            setattr(self.timings, f"{stage_name}_ms", elapsed_ms)
        return elapsed_ms

    def finish(
        self,
        provider: str = "",
        model: str = "",
        retrieved_candidates: int = 0,
        citation_count: int = 0,
        grounded: bool = False,
        abstained: bool = False,
        token_usage: dict[str, int] | None = None,
        error: str | None = None,
    ) -> QueryMetrics:
        self.timings.total_ms = (time.perf_counter() - self._start_total) * 1000.0
        metrics = QueryMetrics(
            query_id=self.query_id,
            request_id=self.request_id,
            user_id=self.user_id,
            provider=provider,
            model=model,
            retrieval_latency_ms=self.timings.retrieval_ms,
            reranking_latency_ms=self.timings.reranking_ms,
            llm_latency_ms=self.timings.generation_ms,
            total_latency_ms=self.timings.total_ms,
            retrieved_candidates=retrieved_candidates,
            citation_count=citation_count,
            grounded=grounded,
            abstained=abstained,
            token_usage=token_usage or {},
            timings=self.timings,
            error=error,
        )
        metrics.log()
        return metrics


def log_ingestion_metric(
    job_id: str,
    document_id: str,
    stage: str,
    duration_ms: float,
    status: str = "success",
    error: str | None = None,
) -> None:
    """Structured logging for ingestion pipeline stages (Phase 16)."""
    logger.info(
        f"Ingestion stage {stage} completed [job_id={job_id}]",
        extra={
            "extra": {
                "event": "ingestion_observability",
                "job_id": job_id,
                "document_id": document_id,
                "stage": stage,
                "duration_ms": duration_ms,
                "status": status,
                "error": error,
            }
        },
    )
