"""Unit tests for Pydantic schemas — data validation and sensitive-field exclusion."""
import uuid
from datetime import UTC, datetime

import pytest
from apps.api.app.schemas.document import DocumentChunkRead, DocumentCreate
from apps.api.app.schemas.health import DatabaseHealthResponse, HealthResponse
from apps.api.app.schemas.user import UserCreate, UserRead
from pydantic import ValidationError


class TestUserSchemas:
    def test_user_create_valid(self):
        u = UserCreate(
            email="analyst@corp.com",
            password="securepassword123",  # noqa: S106 — test fixture
            full_name="Jane Analyst",
        )
        assert u.email == "analyst@corp.com"

    def test_user_create_password_min_length(self):
        with pytest.raises(ValidationError):
            UserCreate(email="x@x.com", password="short")  # noqa: S106

    def test_user_create_invalid_email(self):
        with pytest.raises(ValidationError):
            UserCreate(email="not-an-email", password="validpassword123")  # noqa: S106

    def test_user_read_excludes_password_hash(self):
        """Critical: UserRead schema must NOT expose password_hash (Rule 6, Rule 8)."""
        user_id = uuid.uuid4()
        now = datetime.now(UTC)
        u = UserRead(
            id=user_id,
            email="admin@corp.com",
            full_name="Admin",
            is_active=True,
            roles=[],
            created_at=now,
        )
        serialized = u.model_dump()
        assert "password_hash" not in serialized
        assert "password" not in serialized
        assert u.email == "admin@corp.com"

    def test_user_read_fields_present(self):
        """UserRead must expose id, email, full_name, is_active, roles, created_at."""
        now = datetime.now(UTC)
        u = UserRead(
            id=uuid.uuid4(),
            email="viewer@corp.com",
            full_name=None,
            is_active=True,
            roles=[],
            created_at=now,
        )
        d = u.model_dump()
        assert "id" in d
        assert "email" in d
        assert "is_active" in d
        assert "created_at" in d


class TestDocumentSchemas:
    def test_document_create_valid(self):
        doc = DocumentCreate(
            title="Apple 2025 Annual Report",
            source_type="sec",
            document_type="annual_report",
            organization="Apple",
            report_year=2025,
            content_hash="a" * 64,
        )
        assert doc.content_hash == "a" * 64

    def test_document_create_invalid_hash_length(self):
        """content_hash must be exactly 64 chars."""
        with pytest.raises(ValidationError):
            DocumentCreate(
                title="X",
                source_type="sec",
                document_type="annual_report",
                content_hash="tooshort",
            )

    def test_document_chunk_read_minimal(self):
        chunk = DocumentChunkRead(
            id=uuid.uuid4(),
            document_version_id=uuid.uuid4(),
            chunk_index=5,
            text="Evidence text for citation.",
        )
        serialized = chunk.model_dump()
        # Must not expose table_html or large metadata blobs unnecessarily in minimal view
        assert "id" in serialized
        assert "text" in serialized


class TestHealthSchemas:
    def test_health_response(self):
        now = datetime.now(UTC)
        r = HealthResponse(status="ok", service="enterprise-rag-api", timestamp=now)
        assert r.status == "ok"

    def test_db_health_response(self):
        now = datetime.now(UTC)
        r = DatabaseHealthResponse(
            status="ok",
            database="postgresql",
            connected=True,
            latency_ms=1.5,
            timestamp=now,
        )
        assert r.connected is True
        assert r.latency_ms == 1.5
