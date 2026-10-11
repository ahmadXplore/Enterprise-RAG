"""Integration tests for Phase 13 FastAPI Production API.

Tests all endpoints required by Phase 13 and BACKEND SCHEMA.md:
- /documents (list with pagination & filters, detail, ingest)
- /ingestion (jobs status)
- /search (pre-retrieval access control, minimal schema)
- /chat (conversation persistence, response schema)
- /chat/stream (SSE streaming events)
- /evaluations (runs creation, status & metrics, analyst-only RBAC)
- /health (/health/qdrant, /health/redis, /health/llm)
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from apps.api.app.core.security import create_access_token, hash_password
from apps.api.app.models.document import Document, DocumentAccess
from apps.api.app.models.user import Role, User
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from packages.llm.generation import GenerationResult
from packages.schemas.common import AccessPermission, RoleType


@pytest_asyncio.fixture(scope="function")
async def setup_users_and_docs(test_engine):
    """Seed roles, users (admin, analyst, viewer), and documents."""
    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        admin_role = Role(id=uuid.uuid4(), name=RoleType.ADMIN.value)
        analyst_role = Role(id=uuid.uuid4(), name=RoleType.ANALYST.value)
        viewer_role = Role(id=uuid.uuid4(), name=RoleType.VIEWER.value)
        session.add_all([admin_role, analyst_role, viewer_role])
        await session.flush()

        admin_user = User(
            id=uuid.uuid4(),
            email="admin@corp.com",
            password_hash=hash_password("Admin123!"),
            full_name="Admin User",
            is_active=True,
            roles=[admin_role],
        )
        analyst_user = User(
            id=uuid.uuid4(),
            email="analyst@corp.com",
            password_hash=hash_password("Analyst123!"),
            full_name="Analyst User",
            is_active=True,
            roles=[analyst_role],
        )
        viewer_user = User(
            id=uuid.uuid4(),
            email="viewer@corp.com",
            password_hash=hash_password("Viewer123!"),
            full_name="Viewer User",
            is_active=True,
            roles=[viewer_role],
        )
        session.add_all([admin_user, analyst_user, viewer_user])

        # Create test documents
        doc1 = Document(
            id=uuid.uuid4(),
            title="Apple 2024 10-K",
            source_type="sec",
            document_type="annual_report",
            organization="Apple Inc.",
            report_year=2024,
            content_hash="a" * 64,
            status="ready",
        )
        doc2 = Document(
            id=uuid.uuid4(),
            title="Microsoft 2024 10-K",
            source_type="sec",
            document_type="annual_report",
            organization="Microsoft Corporation",
            report_year=2024,
            content_hash="b" * 64,
            status="ready",
        )
        session.add_all([doc1, doc2])
        await session.flush()

        # Grant viewer access to doc1 only
        access1 = DocumentAccess(
            id=uuid.uuid4(),
            document_id=doc1.id,
            user_id=viewer_user.id,
            permission=AccessPermission.READ.value,
        )
        session.add(access1)
        await session.commit()

        admin_token = create_access_token(admin_user.id, [RoleType.ADMIN.value])
        analyst_token = create_access_token(analyst_user.id, [RoleType.ANALYST.value])
        viewer_token = create_access_token(viewer_user.id, [RoleType.VIEWER.value])

        return {
            "admin_token": admin_token,
            "analyst_token": analyst_token,
            "viewer_token": viewer_token,
            "doc1_id": str(doc1.id),
            "doc2_id": str(doc2.id),
        }


class TestPhase13DocumentsEndpoints:
    @pytest.mark.asyncio
    async def test_list_documents_pagination(self, async_client, setup_users_and_docs):
        tokens = setup_users_and_docs
        headers = {"Authorization": f"Bearer {tokens['viewer_token']}"}

        # Viewer only has access to doc1
        response = await async_client.get("/api/v1/documents?page=1&page_size=10", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert "items" in body
        assert "total" in body
        assert "page" in body
        assert "page_size" in body
        assert body["total"] == 1
        assert body["items"][0]["id"] == tokens["doc1_id"]

    @pytest.mark.asyncio
    async def test_get_document_detail_accessible(self, async_client, setup_users_and_docs):
        tokens = setup_users_and_docs
        headers = {"Authorization": f"Bearer {tokens['viewer_token']}"}

        response = await async_client.get(f"/api/v1/documents/{tokens['doc1_id']}", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == tokens["doc1_id"]
        assert body["title"] == "Apple 2024 10-K"
        assert "chunk_count" in body

    @pytest.mark.asyncio
    async def test_get_document_detail_unauthorized(self, async_client, setup_users_and_docs):
        tokens = setup_users_and_docs
        headers = {"Authorization": f"Bearer {tokens['viewer_token']}"}

        # Viewer has no access to doc2 -> 403 Forbidden
        response = await async_client.get(f"/api/v1/documents/{tokens['doc2_id']}", headers=headers)
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_can_enqueue_ingestion(self, async_client, setup_users_and_docs):
        tokens = setup_users_and_docs
        headers = {"Authorization": f"Bearer {tokens['admin_token']}"}

        response = await async_client.post(
            f"/api/v1/documents/{tokens['doc1_id']}/ingest", headers=headers
        )
        assert response.status_code == 202
        body = response.json()
        assert "job_id" in body
        assert body["status"] == "queued"

    @pytest.mark.asyncio
    async def test_viewer_cannot_enqueue_ingestion(self, async_client, setup_users_and_docs):
        tokens = setup_users_and_docs
        headers = {"Authorization": f"Bearer {tokens['viewer_token']}"}

        response = await async_client.post(
            f"/api/v1/documents/{tokens['doc1_id']}/ingest", headers=headers
        )
        assert response.status_code == 403


class TestPhase13IngestionEndpoints:
    @pytest.mark.asyncio
    async def test_get_ingestion_job_status(self, async_client, setup_users_and_docs):
        tokens = setup_users_and_docs
        admin_headers = {"Authorization": f"Bearer {tokens['admin_token']}"}
        viewer_headers = {"Authorization": f"Bearer {tokens['viewer_token']}"}

        # Enqueue job as admin
        resp = await async_client.post(
            f"/api/v1/documents/{tokens['doc1_id']}/ingest", headers=admin_headers
        )
        job_id = resp.json()["job_id"]

        # View job status as viewer
        job_resp = await async_client.get(
            f"/api/v1/ingestion/jobs/{job_id}", headers=viewer_headers
        )
        assert job_resp.status_code == 200
        body = job_resp.json()
        assert body["job_id"] == job_id
        assert body["status"] == "queued"
        assert "stage" in body
        assert "progress" in body


class TestPhase13SearchEndpoints:
    @pytest.mark.asyncio
    async def test_search_unauthenticated(self, async_client):
        response = await async_client.post("/api/v1/search", json={"query": "Apple revenue"})
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_search_authorized_viewer(self, async_client, setup_users_and_docs):
        tokens = setup_users_and_docs
        headers = {"Authorization": f"Bearer {tokens['viewer_token']}"}

        response = await async_client.post(
            "/api/v1/search",
            json={"query": "Apple revenue", "top_k": 5},
            headers=headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert "query_id" in body
        assert "results" in body


class TestPhase13ChatEndpoints:
    @pytest.mark.asyncio
    async def test_chat_unauthenticated(self, async_client):
        response = await async_client.post("/api/v1/chat", json={"message": "What is revenue?"})
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_chat_synchronous(self, async_client, setup_users_and_docs):
        tokens = setup_users_and_docs
        headers = {"Authorization": f"Bearer {tokens['viewer_token']}"}

        with patch("apps.api.app.services.chat_service.ChatService._get_graph") as mock_get_graph:
            mock_graph = MagicMock()
            mock_graph.run = AsyncMock(
                return_value=GenerationResult(
                    answer="Apple 2024 revenue was $391B.",
                    citation_ids=["apple-chunk-1"],
                    grounded=True,
                    abstained=False,
                    query_type="DIRECT",
                )
            )
            mock_get_graph.return_value = mock_graph

            response = await async_client.post(
                "/api/v1/chat",
                json={"message": "What was Apple's 2024 revenue?"},
                headers=headers,
            )
            assert response.status_code == 200
            body = response.json()
            assert "message_id" in body
            assert "conversation_id" in body
            assert body["answer"] == "Apple 2024 revenue was $391B."
            assert body["grounded"] is True
            assert body["abstained"] is False
            assert len(body["citations"]) == 1

    @pytest.mark.asyncio
    async def test_chat_streaming_sse(self, async_client, setup_users_and_docs):
        tokens = setup_users_and_docs
        headers = {"Authorization": f"Bearer {tokens['viewer_token']}"}

        with patch("apps.api.app.services.chat_service.ChatService._get_graph") as mock_get_graph:
            mock_graph = MagicMock()
            mock_graph.run = AsyncMock(
                return_value=GenerationResult(
                    answer="Apple's fiscal revenue was 391 billion.",
                    citation_ids=["c1"],
                    grounded=True,
                    abstained=False,
                    query_type="DIRECT",
                )
            )
            mock_get_graph.return_value = mock_graph

            response = await async_client.post(
                "/api/v1/chat/stream",
                json={"message": "Revenue stream?"},
                headers=headers,
            )
            assert response.status_code == 200
            assert "text/event-stream" in response.headers["content-type"]
            text = response.text
            assert "event: query_started" in text
            assert "event: token" in text
            assert "event: completed" in text


class TestPhase13EvaluationsEndpoints:
    @pytest.mark.asyncio
    async def test_evaluations_viewer_forbidden(self, async_client, setup_users_and_docs):
        tokens = setup_users_and_docs
        headers = {"Authorization": f"Bearer {tokens['viewer_token']}"}

        response = await async_client.post(
            "/api/v1/evaluations/runs",
            json={"pipeline_type": "no_reranker"},
            headers=headers,
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_evaluations_analyst_can_create_and_get(self, async_client, setup_users_and_docs):
        tokens = setup_users_and_docs
        headers = {"Authorization": f"Bearer {tokens['analyst_token']}"}

        # Create run
        resp = await async_client.post(
            "/api/v1/evaluations/runs",
            json={"pipeline_type": "agentic_retrieval"},
            headers=headers,
        )
        assert resp.status_code == 201
        run_data = resp.json()
        assert "id" in run_data
        run_id = run_data["id"]

        # Get run detail with metrics
        get_resp = await async_client.get(f"/api/v1/evaluations/runs/{run_id}", headers=headers)
        assert get_resp.status_code == 200
        get_data = get_resp.json()
        assert get_data["id"] == run_id
        assert "metrics" in get_data
        assert get_data["metrics"]["groundedness"] is not None

        # List runs
        list_resp = await async_client.get(
            "/api/v1/evaluations/runs?page=1&page_size=10", headers=headers
        )
        assert list_resp.status_code == 200
        assert list_resp.json()["total"] >= 1


class TestPhase13HealthEndpoints:
    @pytest.mark.asyncio
    async def test_health_qdrant(self, async_client):
        response = await async_client.get("/health/qdrant")
        assert response.status_code == 200
        body = response.json()
        assert body["service"] == "qdrant"
        assert "connected" in body
        assert "status" in body

    @pytest.mark.asyncio
    async def test_health_redis(self, async_client):
        response = await async_client.get("/health/redis")
        assert response.status_code == 200
        body = response.json()
        assert body["service"] == "redis"
        assert "connected" in body
        assert "status" in body

    @pytest.mark.asyncio
    async def test_health_llm(self, async_client):
        response = await async_client.get("/health/llm")
        assert response.status_code == 200
        body = response.json()
        assert body["service"] == "llm"
        assert "provider" in body
        assert "configured" in body
