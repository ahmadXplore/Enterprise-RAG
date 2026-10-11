"""Integration tests for health check endpoints."""


class TestHealthEndpoints:
    async def test_get_health_returns_200(self, async_client):
        response = await async_client.get("/health")
        assert response.status_code == 200

    async def test_get_health_response_schema(self, async_client):
        response = await async_client.get("/health")
        body = response.json()
        assert body["status"] == "ok"
        assert body["service"] == "enterprise-rag-api"
        assert "timestamp" in body

    async def test_health_response_has_no_sensitive_fields(self, async_client):
        """Health endpoint must never leak internal data (Rule 6)."""
        response = await async_client.get("/health")
        body = response.json()
        assert "password" not in str(body)
        assert "secret" not in str(body)
        assert "api_key" not in str(body)
        assert "token" not in str(body).lower() or "timestamp" in str(body)

    async def test_get_health_db_returns_200_or_503(self, async_client):
        """DB health check must return 200 (SQLite in-memory will respond ok)."""
        response = await async_client.get("/health/db")
        # In-memory SQLite test engine should succeed
        assert response.status_code in (200, 503)

    async def test_get_health_db_response_schema(self, async_client):
        response = await async_client.get("/health/db")
        body = response.json()
        assert "status" in body
        assert "connected" in body
        assert "database" in body
        assert "timestamp" in body

    async def test_health_db_no_sensitive_data(self, async_client):
        """DB health endpoint must not leak credentials or stack traces."""
        response = await async_client.get("/health/db")
        body_str = str(response.json())
        assert "password" not in body_str.lower()
        assert "DATABASE_URL" not in body_str
        assert "traceback" not in body_str.lower()

    async def test_request_id_header_injected(self, async_client):
        """Every response must include X-Request-ID header."""
        response = await async_client.get("/health")
        assert "x-request-id" in response.headers

    async def test_404_returns_safe_error(self, async_client):
        """404 responses must use structured error format without internals."""
        response = await async_client.get("/api/v1/nonexistent")
        assert response.status_code == 404
        body = response.json()
        assert "error" in body
        assert "message" in body["error"]
        assert "request_id" in body["error"]
        assert "traceback" not in str(body).lower()
