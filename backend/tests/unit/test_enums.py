"""Unit tests for shared package enums and schemas."""
from packages.schemas.common import (
    AccessPermission,
    DocumentSourceType,
    DocumentStatus,
    IngestionJobStatus,
    QueryType,
    RoleType,
)


class TestRoleType:
    def test_all_roles_defined(self):
        assert RoleType.ADMIN == "ADMIN"
        assert RoleType.ANALYST == "ANALYST"
        assert RoleType.VIEWER == "VIEWER"

    def test_role_count(self):
        """Exactly three roles per spec."""
        assert len(list(RoleType)) == 3


class TestDocumentEnums:
    def test_source_types(self):
        assert DocumentSourceType.SEC == "sec"
        assert DocumentSourceType.CUAD == "cuad"

    def test_document_statuses(self):
        statuses = [s.value for s in DocumentStatus]
        assert "registered" in statuses
        assert "ready" in statuses
        assert "failed" in statuses

    def test_ingestion_job_statuses(self):
        statuses = [s.value for s in IngestionJobStatus]
        assert "queued" in statuses
        assert "running" in statuses
        assert "completed" in statuses
        assert "failed" in statuses


class TestQueryTypes:
    def test_all_query_types(self):
        expected = {
            "DIRECT", "COMPARISON", "TEMPORAL", "NUMERICAL",
            "LEGAL", "CROSS_DOCUMENT", "UNANSWERABLE",
        }
        actual = {qt.value for qt in QueryType}
        assert expected == actual


class TestAccessPermissions:
    def test_permissions(self):
        assert AccessPermission.READ == "read"
        assert AccessPermission.MANAGE == "manage"
        assert AccessPermission.ADMIN == "admin"
