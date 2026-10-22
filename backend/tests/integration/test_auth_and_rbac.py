"""Integration tests for Authentication, RBAC, and Document Access Control.

Satisfies Phase 2 build prompt and Rule 17:
- Unauthenticated access
- Invalid credentials
- Viewer restrictions (viewer cannot ingest, viewer cannot manage users)
- Analyst permissions
- Admin permissions (admin can manage documents, admin can manage users)
- Restricted document access (unauthorized user cannot access restricted document)
- Audit logging of privileged actions
"""
import uuid

import pytest_asyncio
from apps.api.app.core.security import create_access_token, hash_password
from apps.api.app.models.audit import AuditLog
from apps.api.app.models.document import Document, DocumentAccess
from apps.api.app.models.user import Role, User
from apps.api.app.repositories.document_repo import DocumentRepository
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from packages.schemas.common import AccessPermission, RoleType


@pytest_asyncio.fixture(scope="function")
async def seed_roles(test_engine):
    """Seed standard roles: ADMIN, ANALYST, VIEWER in test DB."""
    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        roles = [
            Role(id=uuid.uuid4(), name=RoleType.ADMIN.value, description="Admin access"),
            Role(id=uuid.uuid4(), name=RoleType.ANALYST.value, description="Analyst access"),
            Role(id=uuid.uuid4(), name=RoleType.VIEWER.value, description="Viewer access"),
        ]
        session.add_all(roles)
        await session.commit()


@pytest_asyncio.fixture(scope="function")
async def create_test_users(test_engine, seed_roles):
    """Create test users for each role: admin, analyst, viewer, and unauthorized."""
    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        # Fetch roles
        from sqlalchemy import select
        res = await session.execute(select(Role))
        roles_by_name = {r.name: r for r in res.scalars().all()}

        admin = User(
            id=uuid.uuid4(),
            email="admin@corp.com",
            password_hash=hash_password("AdminSecret123!"),
            full_name="Admin User",
            is_active=True,
            roles=[roles_by_name[RoleType.ADMIN.value]],
        )
        analyst = User(
            id=uuid.uuid4(),
            email="analyst@corp.com",
            password_hash=hash_password("AnalystSecret123!"),
            full_name="Analyst User",
            is_active=True,
            roles=[roles_by_name[RoleType.ANALYST.value]],
        )
        viewer = User(
            id=uuid.uuid4(),
            email="viewer@corp.com",
            password_hash=hash_password("ViewerSecret123!"),
            full_name="Viewer User",
            is_active=True,
            roles=[roles_by_name[RoleType.VIEWER.value]],
        )
        unauthorized = User(
            id=uuid.uuid4(),
            email="unauth@corp.com",
            password_hash=hash_password("UnauthSecret123!"),
            full_name="Unauthorized User",
            is_active=True,
            roles=[roles_by_name[RoleType.VIEWER.value]],
        )
        session.add_all([admin, analyst, viewer, unauthorized])
        await session.commit()

        return {
            "admin": admin,
            "analyst": analyst,
            "viewer": viewer,
            "unauthorized": unauthorized,
            "roles": roles_by_name,
        }


def auth_header(user: User) -> dict[str, str]:
    """Helper to generate Authorization header for a user."""
    roles = [r.name for r in user.roles]
    token = create_access_token(subject=user.id, roles=roles)
    return {"Authorization": f"Bearer {token}"}


class TestUnauthenticatedAccess:
    async def test_auth_me_requires_token(self, async_client):
        resp = await async_client.get("/api/v1/auth/me")
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "UNAUTHORIZED"

    async def test_users_requires_token(self, async_client):
        resp = await async_client.get("/api/v1/users")
        assert resp.status_code == 401

    async def test_documents_requires_token(self, async_client):
        doc_id = uuid.uuid4()
        resp = await async_client.get(f"/api/v1/documents/{doc_id}")
        assert resp.status_code == 401


class TestRegistrationAndLogin:
    async def test_register_creates_user_with_viewer_role(self, async_client, seed_roles):
        payload = {
            "email": "newuser@corp.com",
            "password": "StrongPassword123!",
            "full_name": "New Employee",
        }
        resp = await async_client.post("/api/v1/auth/register", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "newuser@corp.com"
        assert data["full_name"] == "New Employee"
        assert "password_hash" not in data  # Rule 6: never expose password hash
        assert any(r["name"] == "VIEWER" for r in data["roles"])

    async def test_register_duplicate_email_conflict(self, async_client, seed_roles):
        payload = {
            "email": "duplicate@corp.com",
            "password": "StrongPassword123!",
            "full_name": "First User",
        }
        resp1 = await async_client.post("/api/v1/auth/register", json=payload)
        assert resp1.status_code == 201

        resp2 = await async_client.post("/api/v1/auth/register", json=payload)
        assert resp2.status_code == 409
        assert resp2.json()["error"]["code"] == "CONFLICT"

    async def test_register_short_password_rejected(self, async_client, seed_roles):
        payload = {
            "email": "short@corp.com",
            "password": "short",  # < 8 chars
        }
        resp = await async_client.post("/api/v1/auth/register", json=payload)
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "VALIDATION_ERROR"

    async def test_login_success(self, async_client, create_test_users):
        payload = {
            "email": "viewer@corp.com",
            "password": "ViewerSecret123!",
        }
        resp = await async_client.post("/api/v1/auth/login", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"  # noqa: S105
        assert data["expires_in"] > 0

    async def test_login_invalid_password(self, async_client, create_test_users):
        payload = {
            "email": "viewer@corp.com",
            "password": "WrongPassword999!",
        }
        resp = await async_client.post("/api/v1/auth/login", json=payload)
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "UNAUTHORIZED"
        # Rule 5: generic message to prevent email enumeration
        assert "Invalid email or password" in resp.json()["error"]["message"]

    async def test_login_nonexistent_email(self, async_client, create_test_users):
        payload = {
            "email": "nobody@corp.com",
            "password": "AnyPassword123!",
        }
        resp = await async_client.post("/api/v1/auth/login", json=payload)
        assert resp.status_code == 401
        assert "Invalid email or password" in resp.json()["error"]["message"]

    async def test_auth_me_returns_profile(self, async_client, create_test_users):
        viewer = create_test_users["viewer"]
        headers = auth_header(viewer)
        resp = await async_client.get("/api/v1/auth/me", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "viewer@corp.com"
        assert "password_hash" not in data


class TestRBACPermissions:
    async def test_viewer_cannot_ingest(self, async_client, create_test_users):
        """Rule: viewer cannot ingest."""
        viewer = create_test_users["viewer"]
        headers = auth_header(viewer)
        payload = {
            "title": "Secret Filing",
            "source_type": "sec",
            "document_type": "annual_report",
            "content_hash": "a" * 64,
        }
        resp = await async_client.post("/api/v1/documents", json=payload, headers=headers)
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "FORBIDDEN"

    async def test_viewer_cannot_manage_users(self, async_client, create_test_users):
        """Rule: viewer cannot manage users."""
        viewer = create_test_users["viewer"]
        headers = auth_header(viewer)
        resp = await async_client.get("/api/v1/users", headers=headers)
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "FORBIDDEN"

    async def test_analyst_cannot_ingest(self, async_client, create_test_users):
        """Analyst role cannot ingest documents."""
        analyst = create_test_users["analyst"]
        headers = auth_header(analyst)
        payload = {
            "title": "Analyst Ingestion Attempt",
            "source_type": "sec",
            "document_type": "annual_report",
            "content_hash": "b" * 64,
        }
        resp = await async_client.post("/api/v1/documents", json=payload, headers=headers)
        assert resp.status_code == 403

    async def test_analyst_cannot_manage_users(self, async_client, create_test_users):
        """Analyst role cannot manage users."""
        analyst = create_test_users["analyst"]
        headers = auth_header(analyst)
        resp = await async_client.get("/api/v1/users", headers=headers)
        assert resp.status_code == 403

    async def test_admin_can_manage_users(self, async_client, create_test_users):
        """Admin can list and manage users."""
        admin = create_test_users["admin"]
        headers = auth_header(admin)
        resp = await async_client.get("/api/v1/users", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 4
        assert all("password_hash" not in u for u in data)

    async def test_admin_can_manage_documents(self, async_client, create_test_users):
        """Rule: admin can manage documents (ingest and delete)."""
        admin = create_test_users["admin"]
        headers = auth_header(admin)
        doc_hash = "c" * 64
        payload = {
            "title": "2024 Form 10-K Apple Inc.",
            "source_type": "sec",
            "document_type": "annual_report",
            "organization": "Apple Inc.",
            "ticker": "AAPL",
            "report_year": 2024,
            "content_hash": doc_hash,
        }
        # Ingest
        create_resp = await async_client.post("/api/v1/documents", json=payload, headers=headers)
        assert create_resp.status_code == 201
        doc_id = create_resp.json()["id"]

        # Admin can access document
        get_resp = await async_client.get(f"/api/v1/documents/{doc_id}", headers=headers)
        assert get_resp.status_code == 200
        assert get_resp.json()["title"] == "2024 Form 10-K Apple Inc."

        # Admin can delete document
        del_resp = await async_client.delete(f"/api/v1/documents/{doc_id}", headers=headers)
        assert del_resp.status_code == 200


class TestDocumentAccessControl:
    @pytest_asyncio.fixture(scope="function")
    async def restricted_document(self, test_engine, create_test_users):
        """Create a restricted document with an explicit access grant only for Analyst."""
        session_factory = async_sessionmaker(
            bind=test_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        async with session_factory() as session:
            doc = Document(
                id=uuid.uuid4(),
                title="Confidential Merger Agreement",
                source_type="cuad",
                document_type="legal_contract",
                content_hash="d" * 64,
                status="ready",
            )
            session.add(doc)

            # Grant explicit read access ONLY to Analyst user
            analyst_user = create_test_users["analyst"]
            access_rule = DocumentAccess(
                id=uuid.uuid4(),
                document_id=doc.id,
                user_id=analyst_user.id,
                permission=AccessPermission.READ.value,
            )
            session.add(access_rule)
            await session.commit()
            return doc

    async def test_unauthorized_user_cannot_access_restricted_document(
        self, async_client, create_test_users, restricted_document
    ):
        """Rule: unauthorized user cannot access restricted document."""
        unauthorized_user = create_test_users["unauthorized"]
        headers = auth_header(unauthorized_user)

        resp = await async_client.get(
            f"/api/v1/documents/{restricted_document.id}", headers=headers
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "FORBIDDEN"

    async def test_authorized_user_can_access_document(
        self, async_client, create_test_users, restricted_document
    ):
        """Authorized user (Analyst) with explicit grant can read document."""
        analyst_user = create_test_users["analyst"]
        headers = auth_header(analyst_user)

        resp = await async_client.get(
            f"/api/v1/documents/{restricted_document.id}", headers=headers
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "Confidential Merger Agreement"

    async def test_admin_has_universal_document_access(
        self, async_client, create_test_users, restricted_document
    ):
        """Admin has universal access even without explicit DocumentAccess rule."""
        admin_user = create_test_users["admin"]
        headers = auth_header(admin_user)

        resp = await async_client.get(
            f"/api/v1/documents/{restricted_document.id}", headers=headers
        )
        assert resp.status_code == 200

    async def test_pre_retrieval_scope_resolution(
        self, test_engine, create_test_users, restricted_document
    ):
        """Verify DocumentRepository.get_allowed_document_ids enforces pre-retrieval security.

        TRD Section 16.1: Pre-retrieval authorization logic must resolve exact allowed document IDs
        so the retriever/Qdrant strictly filters chunks before LLM context.
        """
        session_factory = async_sessionmaker(
            bind=test_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        async with session_factory() as session:
            repo = DocumentRepository(session)
            analyst = create_test_users["analyst"]
            unauthorized = create_test_users["unauthorized"]
            admin = create_test_users["admin"]

            # Analyst gets restricted_document ID
            analyst_allowed = await repo.get_allowed_document_ids(
                user_id=analyst.id,
                role_ids=[r.id for r in analyst.roles],
                is_admin=False,
            )
            assert restricted_document.id in analyst_allowed

            # Unauthorized user gets empty list
            unauth_allowed = await repo.get_allowed_document_ids(
                user_id=unauthorized.id,
                role_ids=[r.id for r in unauthorized.roles],
                is_admin=False,
            )
            assert restricted_document.id not in unauth_allowed

            # Admin gets all documents
            admin_allowed = await repo.get_allowed_document_ids(
                user_id=admin.id,
                role_ids=[r.id for r in admin.roles],
                is_admin=True,
            )
            assert restricted_document.id in admin_allowed


class TestAuditLogging:
    async def test_privileged_actions_create_audit_logs(
        self, async_client, create_test_users, test_engine
    ):
        """Rule 4 & 6: Privileged actions record audit logs with hashed IP and no credentials."""
        admin = create_test_users["admin"]
        headers = auth_header(admin)

        # 1. Ingest document
        doc_hash = "e" * 64
        payload = {
            "title": "Audit Test Document",
            "source_type": "sec",
            "document_type": "annual_report",
            "content_hash": doc_hash,
        }
        create_resp = await async_client.post(
            "/api/v1/documents", json=payload, headers=headers
        )
        assert create_resp.status_code == 201
        doc_id = uuid.UUID(create_resp.json()["id"])

        # 2. Inspect users list
        await async_client.get("/api/v1/users", headers=headers)

        # 3. Verify audit log records in database
        session_factory = async_sessionmaker(
            bind=test_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        async with session_factory() as session:
            from sqlalchemy import select
            res = await session.execute(
                select(AuditLog).order_by(AuditLog.created_at.desc())
            )
            logs = list(res.scalars().all())

            actions = [log.action for log in logs]
            assert "document:create" in actions
            assert "user:list" in actions

            # Verify no sensitive fields in metadata and ip_hash is hashed
            doc_create_log = next(log for log in logs if log.action == "document:create")
            assert doc_create_log.resource_id == doc_id
            assert doc_create_log.user_id == admin.id
            assert doc_create_log.ip_hash is not None
            assert len(doc_create_log.ip_hash) == 64
            if doc_create_log.metadata_:
                assert "password" not in doc_create_log.metadata_
                assert "token" not in doc_create_log.metadata_


class TestAdminUserManagement:
    async def test_admin_create_block_reinstate_and_delete_user(
        self, async_client, create_test_users
    ):
        """Admin can create, block, reinstate, and delete user accounts."""
        admin = create_test_users["admin"]
        viewer = create_test_users["viewer"]
        admin_headers = auth_header(admin)
        viewer_headers = auth_header(viewer)

        # 1. Non-admin (viewer) forbidden from creating user
        create_payload = {
            "email": "newuser@corp.com",
            "password": "Password123!",
            "full_name": "New Test User",
            "role": "ANALYST",
        }
        resp = await async_client.post("/api/v1/users", json=create_payload, headers=viewer_headers)
        assert resp.status_code == 403

        # 2. Admin successfully creates new user
        resp = await async_client.post("/api/v1/users", json=create_payload, headers=admin_headers)
        assert resp.status_code == 201
        created_user = resp.json()
        assert created_user["email"] == "newuser@corp.com"
        assert created_user["is_active"] is True
        assert any(r["name"].upper() == "ANALYST" for r in created_user["roles"])
        user_id = created_user["id"]

        # 3. Block user
        block_resp = await async_client.patch(
            f"/api/v1/users/{user_id}/status",
            json={"is_active": False},
            headers=admin_headers,
        )
        assert block_resp.status_code == 200
        assert block_resp.json()["is_active"] is False

        # 4. Blocked user cannot log in
        login_resp = await async_client.post(
            "/api/v1/auth/login",
            json={"email": "newuser@corp.com", "password": "Password123!"},
        )
        assert login_resp.status_code == 401
        err_msg = login_resp.json().get("error", {}).get("message", "") or login_resp.json().get("detail", "")
        assert "inactive" in err_msg.lower()

        # 5. Reinstate user
        reinstate_resp = await async_client.patch(
            f"/api/v1/users/{user_id}/status",
            json={"is_active": True},
            headers=admin_headers,
        )
        assert reinstate_resp.status_code == 200
        assert reinstate_resp.json()["is_active"] is True

        # 6. Admin cannot block or delete self
        self_block_resp = await async_client.patch(
            f"/api/v1/users/{admin.id}/status",
            json={"is_active": False},
            headers=admin_headers,
        )
        assert self_block_resp.status_code == 400

        self_delete_resp = await async_client.delete(
            f"/api/v1/users/{admin.id}",
            headers=admin_headers,
        )
        assert self_delete_resp.status_code == 400

        # 7. Delete user
        del_resp = await async_client.delete(f"/api/v1/users/{user_id}", headers=admin_headers)
        assert del_resp.status_code == 200

