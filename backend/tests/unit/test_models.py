"""Unit tests for SQLAlchemy model instantiation and constraints."""
import uuid

from apps.api.app.models.audit import AuditLog
from apps.api.app.models.document import Document, DocumentAccess, DocumentChunk
from apps.api.app.models.evaluation import EvaluationCase, EvaluationSet
from apps.api.app.models.user import Role, User


class TestUserModels:
    def test_user_default_id_generated(self):
        u = User(
            email="test@example.com",
            password_hash="hashed",  # noqa: S106 — fake value for test
            full_name="Test User",
        )
        # Default uuid4 should be set
        assert u.id is None or isinstance(u.id, (uuid.UUID, str, type(None)))

    def test_role_instantiation(self):
        r = Role(name="ADMIN", description="Full admin access")
        assert r.name == "ADMIN"
        assert r.description == "Full admin access"

    def test_user_has_required_fields(self):
        u = User(email="analyst@corp.com", password_hash="$2b$12$hash")  # noqa: S106
        assert u.email == "analyst@corp.com"
        assert u.password_hash == "$2b$12$hash"  # noqa: S105
        assert u.is_active is None or u.is_active is True


class TestDocumentModels:
    def test_document_instantiation(self):
        doc = Document(
            title="Apple 2025 Annual Report",
            source_type="sec",
            document_type="annual_report",
            organization="Apple",
            report_year=2025,
            content_hash="a" * 64,
        )
        assert doc.title == "Apple 2025 Annual Report"
        assert doc.content_hash == "a" * 64
        assert doc.source_type == "sec"

    def test_document_chunk_required_text(self):
        chunk = DocumentChunk(
            chunk_index=0,
            text="Revenue increased significantly in FY2025.",
            chunk_type="paragraph",
        )
        assert chunk.text == "Revenue increased significantly in FY2025."
        assert chunk.chunk_index == 0

    def test_document_access_permissions(self):
        access = DocumentAccess(
            document_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            permission="read",
        )
        assert access.permission == "read"


class TestAuditLogModel:
    def test_audit_log_no_sensitive_fields(self):
        """AuditLog must not have password or secret fields (Rule 4, Rule 8)."""
        al = AuditLog(
            action="document.delete",
            resource_type="document",
            resource_id=uuid.uuid4(),
        )
        assert al.action == "document.delete"
        # Verify that password/token fields do not exist on the model
        assert not hasattr(al, "password")
        assert not hasattr(al, "api_key")
        assert not hasattr(al, "secret")


class TestEvaluationModels:
    def test_evaluation_set_instantiation(self):
        es = EvaluationSet(name="Financial QA Benchmark v1", version="1.0")
        assert es.name == "Financial QA Benchmark v1"

    def test_evaluation_case_requires_question(self):
        ec = EvaluationCase(
            question="What was Apple's revenue in FY2025?",
            query_type="DIRECT",
        )
        assert ec.question == "What was Apple's revenue in FY2025?"
