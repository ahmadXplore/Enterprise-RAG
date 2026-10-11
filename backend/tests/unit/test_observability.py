"""Unit tests for Phase 16 structured observability metrics and timing tracking."""
import logging
import uuid

from apps.api.app.core.observability import QueryTimer, log_ingestion_metric


class TestObservabilityMetrics:
    def test_query_timer_tracks_stages_and_latency(self):
        query_id = str(uuid.uuid4())
        request_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        timer = QueryTimer(query_id=query_id, request_id=request_id, user_id=user_id)
        timer.start_stage("preprocessing")
        timer.end_stage("preprocessing")

        timer.start_stage("retrieval")
        timer.end_stage("retrieval")

        timer.start_stage("reranking")
        timer.end_stage("reranking")

        timer.start_stage("generation")
        timer.end_stage("generation")

        timer.start_stage("validation")
        timer.end_stage("validation")

        metrics = timer.finish(
            provider="gemini",
            model="gemini-1.5-pro",
            retrieved_candidates=20,
            citation_count=3,
            grounded=True,
            abstained=False,
            token_usage={"prompt_tokens": 150, "completion_tokens": 50},
        )

        assert metrics.query_id == query_id
        assert metrics.request_id == request_id
        assert metrics.user_id == user_id
        assert metrics.provider == "gemini"
        assert metrics.model == "gemini-1.5-pro"
        assert metrics.retrieved_candidates == 20
        assert metrics.citation_count == 3
        assert metrics.grounded is True
        assert metrics.abstained is False
        assert metrics.total_latency_ms >= 0.0
        assert metrics.timings.total_ms >= 0.0

    def test_log_ingestion_metric_executes_without_error(self, caplog):
        with caplog.at_level(logging.INFO):
            log_ingestion_metric(
                job_id="job-123",
                document_id="doc-456",
                stage="embedding",
                duration_ms=45.2,
                status="success",
            )
        assert any("embedding" in record.message for record in caplog.records)
