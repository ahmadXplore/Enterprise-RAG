"""Unit tests for structured logging — redaction of sensitive fields."""
from apps.api.app.core.logging import redact_sensitive_data


class TestSensitiveDataRedaction:
    def test_password_redacted(self):
        data = {"username": "alice", "password": "s3cr3t"}
        result = redact_sensitive_data(data)
        assert result["password"] == "[REDACTED]"  # noqa: S105 — testing redaction, not a real password
        assert result["username"] == "alice"

    def test_api_key_redacted(self):
        data = {"api_key": "gsk_abc123", "model": "llama-3"}
        result = redact_sensitive_data(data)
        assert result["api_key"] == "[REDACTED]"
        assert result["model"] == "llama-3"

    def test_token_redacted(self):
        data = {"access_token": "eyJhbGc...", "user_id": "123"}
        result = redact_sensitive_data(data)
        assert result["access_token"] == "[REDACTED]"  # noqa: S105 — testing redaction
        assert result["user_id"] == "123"

    def test_nested_secret_redacted(self):
        data = {"config": {"jwt_secret": "mysecret", "app": "rag"}}
        result = redact_sensitive_data(data)
        assert result["config"]["jwt_secret"] == "[REDACTED]"  # noqa: S105 — testing redaction
        assert result["config"]["app"] == "rag"

    def test_list_passthrough(self):
        data = [{"name": "alice"}, {"name": "bob"}]
        result = redact_sensitive_data(data)
        assert result[0]["name"] == "alice"

    def test_non_sensitive_preserved(self):
        data = {"document_id": "abc-123", "status": "ready"}
        result = redact_sensitive_data(data)
        assert result == data

    def test_authorization_header_redacted(self):
        data = {"Authorization": "Bearer eyJhbGc..."}
        result = redact_sensitive_data(data)
        assert result["Authorization"] == "[REDACTED]"
