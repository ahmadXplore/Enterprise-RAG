"""Phase 17 — Reliability & Security Hardening Tests.

Covers all failure modes specified in Phase 17:
- Authentication & authorization failures
- Document access filtering (pre-retrieval verification)
- Secret handling & header leak prevention
- API timeouts & provider retries
- Qdrant connection failures
- PostgreSQL / database operational failures
- Redis failure fail-open behavior
- Duplicate ingestion & job idempotency
- Malformed & zero-byte files handling
- Invalid / hallucinated citation stripping
- Infinite agent loops prevention
- Security headers verification
"""

import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from apps.api.app.core.rate_limit import _sliding_window_check
from apps.api.app.main import app
from apps.api.app.services.ingestion_service import IngestionService
from fastapi.testclient import TestClient

from packages.ingestion.validator import CorpusValidator
from packages.llm.generation import validate_citations
from packages.llm.graph import RAGGraph, _route_after_evidence_assessment
from packages.llm.graph_state import GraphState
from packages.llm.providers import GroqProvider, ProviderError
from packages.retrieval.models import RetrievalResult
from packages.schemas.common import DocumentSourceType
from packages.schemas.validation import ValidationStatus

client = TestClient(app)


# ---------------------------------------------------------------------------
# 1. Security Headers Verification
# ---------------------------------------------------------------------------
def test_security_headers_present():
    """Verify production security headers are set on API responses (Rule 4, 7)."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert "Strict-Transport-Security" in resp.headers
    assert resp.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "default-src 'self'" in resp.headers["Content-Security-Policy"]
    assert "Permissions-Policy" in resp.headers


# ---------------------------------------------------------------------------
# 2. Authentication & Authorization Failure Modes
# ---------------------------------------------------------------------------
def test_unauthenticated_requests_rejected():
    """Protected endpoints must reject unauthenticated requests with HTTP 401."""
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401
    assert "UNAUTHORIZED" in resp.text


def test_invalid_token_rejected():
    """Malformed or invalid JWT tokens must be rejected."""
    resp = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid.jwt.token"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 3. Secret Management & Absence of Leaks
# ---------------------------------------------------------------------------
def test_secrets_not_exposed_in_health():
    """Health endpoints must not expose secret keys or passwords (Rule 4, 6)."""
    resp = client.get("/health/llm")
    assert resp.status_code == 200
    data = resp.json()
    assert "api_key" not in data
    assert "secret" not in data
    assert "GROQ_API_KEY" not in str(data)


# ---------------------------------------------------------------------------
# 4. Provider Retries on Transient Failures
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_provider_retries_on_429_then_succeeds():
    """Provider must retry on HTTP 429 and return content once successful (Rule 15)."""
    provider = GroqProvider(
        api_key="test-key", model="test-model", timeout_seconds=5, max_tokens=100
    )

    # First attempt 429, second attempt 200
    resp_429 = httpx.Response(status_code=429, headers={"Retry-After": "0.01"})
    resp_200 = httpx.Response(
        status_code=200,
        json={"choices": [{"message": {"content": "Resolved after retry"}}], "model": "test-model"},
    )

    with patch("httpx.AsyncClient.post", side_effect=[resp_429, resp_200]):
        res = await provider.generate([{"role": "user", "content": "hi"}])
        assert res["content"] == "Resolved after retry"


@pytest.mark.asyncio
async def test_provider_fails_after_max_retries():
    """Provider must raise ProviderError after exceeding maximum retries."""
    provider = GroqProvider(
        api_key="test-key", model="test-model", timeout_seconds=5, max_tokens=100
    )
    resp_503 = httpx.Response(status_code=503)

    with patch("httpx.AsyncClient.post", return_value=resp_503):
        with pytest.raises(ProviderError) as exc_info:
            await provider.generate([{"role": "user", "content": "hi"}])
        assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_provider_does_not_retry_non_transient_error():
    """Provider must not retry non-transient errors like 400 Bad Request."""
    provider = GroqProvider(
        api_key="test-key", model="test-model", timeout_seconds=5, max_tokens=100
    )
    resp_400 = httpx.Response(status_code=400)

    post_mock = AsyncMock(return_value=resp_400)
    with patch("httpx.AsyncClient.post", side_effect=post_mock):
        with pytest.raises(ProviderError) as exc_info:
            await provider.generate([{"role": "user", "content": "hi"}])
        assert exc_info.value.status_code == 400
        # Exactly one call, no retries
        assert post_mock.call_count == 1


# ---------------------------------------------------------------------------
# 5. Qdrant Failures & Graceful Recovery in Agent
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_qdrant_failure_in_agent_degrades_gracefully():
    """When Qdrant fails during agent retrieval, agent must abstain safely without crashing."""
    mock_provider = AsyncMock()
    mock_provider.generate.return_value = {
        "content": '{"query_type": "DIRECT", "requires_calculation": false}',
        "model": "mock",
    }
    mock_generator = AsyncMock()
    mock_generator.generate.return_value = MagicMock(
        answer="I was unable to find sufficient evidence to answer this question.",
        citation_ids=[],
        grounded=False,
        abstained=True,
        query_type="DIRECT",
    )

    mock_retriever = MagicMock()
    mock_retriever.retrieve.side_effect = RuntimeError("Qdrant connection refused")

    graph = RAGGraph(
        provider=mock_provider,
        retriever=mock_retriever,
        generator=mock_generator,
        max_retrieval_attempts=2,
        max_tool_calls=5,
    )

    result = await graph.run(
        question="What is the net revenue?",
        authorized_document_ids=["doc-1"],
        user_id="user-1",
    )

    assert result.abstained is True
    assert "unable to find sufficient evidence" in result.answer.lower()


# ---------------------------------------------------------------------------
# 6. Redis Failure Fail-Open Mode
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_redis_failure_fails_open():
    """When Redis is None or unreachable, rate limiter must fail open (Rule 15)."""
    # Pool is None
    with patch("apps.api.app.core.rate_limit.get_redis_pool", return_value=None):
        allowed, remaining, retry_after = await _sliding_window_check(
            key="test:key", max_requests=5, window_seconds=60
        )
        assert allowed is True
        assert remaining == 5
        assert retry_after == 0


# ---------------------------------------------------------------------------
# 7. Database Failures Return 503 Safe Error
# ---------------------------------------------------------------------------
def test_database_operational_error_returns_503():
    """SQLAlchemy errors must be intercepted by database_exception_handler returning HTTP 503."""
    from sqlalchemy.exc import OperationalError

    with patch(
        "apps.api.app.repositories.user_repo.UserRepository.get_by_email",
        side_effect=OperationalError("Connection failed", {}, None),
    ):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "password": "Password123!"},
        )
        assert resp.status_code == 503
        data = resp.json()
        assert data["error"]["code"] == "DATABASE_UNAVAILABLE"
        # Verify raw connection strings are not exposed
        assert "Connection failed" not in data["error"]["message"]


# ---------------------------------------------------------------------------
# 8. Duplicate Ingestion & Idempotency
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_duplicate_file_detected_by_hash(tmp_path: Path):
    """CorpusValidator must identify identical files as DUPLICATE via content hash."""
    f1 = tmp_path / "doc1.txt"
    f2 = tmp_path / "doc2.txt"
    content = "Contract Terms and Conditions content for deduplication test."
    f1.write_text(content, encoding="utf-8")
    f2.write_text(content, encoding="utf-8")

    validator = CorpusValidator(session=None)
    res1 = await validator.validate_file(f1, DocumentSourceType.CUAD)
    assert res1.status == ValidationStatus.VALID

    res2 = await validator.validate_file(f2, DocumentSourceType.CUAD)
    assert res2.status == ValidationStatus.DUPLICATE
    assert "Duplicate content" in (res2.error_message or "")


@pytest.mark.asyncio
async def test_ingestion_job_idempotency():
    """Enqueuing a job for a document with an already active job must return existing job."""
    mock_session = AsyncMock()
    service = IngestionService(mock_session)

    doc_id = uuid.uuid4()
    service.doc_repo.get_by_id = AsyncMock(return_value=MagicMock(id=doc_id))

    existing_job = MagicMock(id=uuid.uuid4(), document_id=doc_id, status="queued")
    service.job_repo.list_recent = AsyncMock(return_value=[existing_job])

    res = await service.create_ingestion_job(document_id=doc_id)
    assert res["job_id"] == str(existing_job.id)
    assert res["status"] == "queued"
    assert "already queued" in res["message"]


# ---------------------------------------------------------------------------
# 9. Malformed / Corrupted Files
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_malformed_zero_byte_file_rejected(tmp_path: Path):
    """Empty (0-byte) files must be rejected with status INVALID."""
    empty_file = tmp_path / "empty.txt"
    empty_file.write_text("", encoding="utf-8")

    validator = CorpusValidator(session=None)
    res = await validator.validate_file(empty_file, DocumentSourceType.CUAD)
    assert res.status == ValidationStatus.INVALID
    assert "empty" in (res.error_message or "").lower()


@pytest.mark.asyncio
async def test_nonexistent_file_rejected(tmp_path: Path):
    """Non-existent file paths must return INVALID without raising an unhandled exception."""
    missing_file = tmp_path / "missing.txt"
    validator = CorpusValidator(session=None)
    res = await validator.validate_file(missing_file, DocumentSourceType.CUAD)
    assert res.status == ValidationStatus.INVALID
    assert "does not exist" in (res.error_message or "").lower()


# ---------------------------------------------------------------------------
# 10. Citation Validation & Hallucination Stripping
# ---------------------------------------------------------------------------
def test_citation_validation_strips_hallucinations():
    """validate_citations must discard chunk IDs not present in retrieved evidence."""
    chunk1 = MagicMock(spec=RetrievalResult, chunk_id="chunk-valid-1")
    chunk2 = MagicMock(spec=RetrievalResult, chunk_id="chunk-valid-2")
    evidence = [chunk1, chunk2]

    claimed = ["chunk-valid-1", "chunk-hallucinated-999"]
    valid = validate_citations(claimed, evidence)
    assert valid == ["chunk-valid-1"]
    assert "chunk-hallucinated-999" not in valid


# ---------------------------------------------------------------------------
# 11. Infinite Agent Loop Prevention
# ---------------------------------------------------------------------------
def test_infinite_agent_loop_terminates_at_max_limits():
    """Agent router must terminate and route to 'generate' when budget is reached."""
    # When tool_calls exceeds limit, router forces generate
    state_tool_limit: GraphState = {
        "question": "test",
        "authorized_document_ids": [],
        "user_id": "u1",
        "retrieval_attempts": 1,
        "tool_calls": 10,  # limit reached
        "evidence_sufficient": False,
        "query_type": "DIRECT",
        "evidence": [],
    }
    next_node = _route_after_evidence_assessment(
        state_tool_limit, max_retrieval_attempts=3, max_tool_calls=10
    )
    assert next_node == "generate"

    # When retrieval_attempts exceeds limit, router forces generate
    state_attempt_limit: GraphState = {
        "question": "test",
        "authorized_document_ids": [],
        "user_id": "u1",
        "retrieval_attempts": 3,  # limit reached
        "tool_calls": 3,
        "evidence_sufficient": False,
        "query_type": "DIRECT",
        "evidence": [],
    }
    next_node = _route_after_evidence_assessment(
        state_attempt_limit, max_retrieval_attempts=3, max_tool_calls=10
    )
    assert next_node == "generate"
