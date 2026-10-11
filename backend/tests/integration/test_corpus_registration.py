"""Integration tests for dataset scanning, validation, and PostgreSQL registration."""
import json
import uuid

import pytest
import pytest_asyncio
from apps.api.app.core.security import create_access_token, hash_password
from apps.api.app.models.user import Role, User
from apps.api.app.repositories.document_repo import DocumentRepository
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from packages.ingestion.registry import DocumentRegistrar
from packages.ingestion.validator import CorpusValidator
from packages.schemas.common import DocumentSourceType, RoleType


@pytest_asyncio.fixture(scope="function")
async def seed_admin_and_viewer(test_engine):
    """Seed ADMIN and VIEWER roles and users for testing ingestion endpoints."""
    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        admin_role = Role(id=uuid.uuid4(), name=RoleType.ADMIN.value, description="Admin")
        viewer_role = Role(id=uuid.uuid4(), name=RoleType.VIEWER.value, description="Viewer")
        session.add_all([admin_role, viewer_role])

        admin_user = User(
            id=uuid.uuid4(),
            email="admin_ingest@corp.com",
            password_hash=hash_password("AdminSecret123!"),  # noqa: S106
            full_name="Admin Ingest",
            is_active=True,
            roles=[admin_role],
        )
        viewer_user = User(
            id=uuid.uuid4(),
            email="viewer_ingest@corp.com",
            password_hash=hash_password("ViewerSecret123!"),  # noqa: S106
            full_name="Viewer Ingest",
            is_active=True,
            roles=[viewer_role],
        )
        session.add_all([admin_user, viewer_user])
        await session.commit()
        return {"admin": admin_user, "viewer": viewer_user}


def auth_header(user: User) -> dict[str, str]:
    roles = [r.name for r in user.roles]
    token = create_access_token(subject=user.id, roles=roles)
    return {"Authorization": f"Bearer {token}"}


class TestCorpusRegistrationPipeline:
    @pytest.mark.asyncio
    async def test_register_sec_filing_in_db(self, db_session, tmp_path):
        """Verify SEC 10-K filing is registered with all required metadata preserved."""
        year_dir = tmp_path / "apple" / "2024"
        year_dir.mkdir(parents=True)
        filing_file = year_dir / "filing.html"
        filing_file.write_text(
            "<html>Sample SEC 10-K Content for Apple Inc.</html>", encoding="utf-8"
        )

        meta_file = year_dir / "metadata.json"
        meta_data = {
            "company": "Apple Inc.",
            "ticker": "AAPL",
            "cik": "0000320193",
            "year": 2024,
            "form": "10-K",
            "filing_date": "2024-11-01",
            "report_date": "2024-09-28",
            "accession_number": "0000320193-24-000123",
            "primary_document": "aapl-20240928.htm",
            "source_url": "https://www.sec.gov/Archives/edgar/data/320193/aapl.htm",
        }
        meta_file.write_text(json.dumps(meta_data), encoding="utf-8")

        validator = CorpusValidator(db_session)
        val_res = await validator.validate_file(filing_file, DocumentSourceType.SEC)
        assert val_res.status.value == "valid"

        registrar = DocumentRegistrar(db_session)
        doc, version = await registrar.register_document(val_res)
        await db_session.commit()

        # Verify Document row
        repo = DocumentRepository(db_session)
        saved_doc = await repo.get_by_hash(val_res.content_hash)
        assert saved_doc is not None
        assert saved_doc.title == "Apple Inc. FY2024 Form 10-K"
        assert saved_doc.organization == "Apple Inc."
        assert saved_doc.ticker == "AAPL"
        assert saved_doc.report_year == 2024
        assert saved_doc.source_type == "sec"
        assert saved_doc.document_type == "annual_report"
        assert saved_doc.status == "registered"

        # Verify DocumentVersion row
        doc_with_versions = await repo.get_with_versions(saved_doc.id)
        assert len(doc_with_versions.versions) == 1
        ver = doc_with_versions.versions[0]
        assert ver.file_name == "aapl-20240928.htm"
        assert ver.mime_type == "text/html"
        assert ver.checksum == val_res.content_hash
        assert ver.file_size > 0

    @pytest.mark.asyncio
    async def test_duplicate_file_rejected_and_not_registered(self, db_session, tmp_path):
        """Verify DuplicateDetector rejects duplicate reports (FR-02)."""
        f1 = tmp_path / "original.txt"
        f2 = tmp_path / "copy.txt"
        f1.write_text("Exclusive Contract Content", encoding="utf-8")
        f2.write_text("Exclusive Contract Content", encoding="utf-8")

        validator = CorpusValidator(db_session)
        report = await validator.validate_collection([f1, f2], DocumentSourceType.CUAD)

        assert report.valid_count == 1
        assert report.duplicate_count == 1
        assert len(report.duplicates) == 1
        assert "duplicate" in report.duplicates[0].error_message.lower()

    @pytest.mark.asyncio
    async def test_invalid_filing_never_silently_discarded(self, db_session, tmp_path):
        """Rule 14: Never silently discard invalid files; track in report."""
        empty_file = tmp_path / "empty.html"
        empty_file.write_text("", encoding="utf-8")

        validator = CorpusValidator(db_session)
        report = await validator.validate_collection([empty_file], DocumentSourceType.SEC)

        assert report.valid_count == 0
        assert report.invalid_count == 1
        assert len(report.invalid_files) == 1
        assert "empty" in report.invalid_files[0].error_message.lower()


class TestIngestionAPI:
    async def test_viewer_cannot_validate_or_register(self, async_client, seed_admin_and_viewer):
        viewer = seed_admin_and_viewer["viewer"]
        headers = auth_header(viewer)
        payload = {
            "directory": "sec_10k_dataset",
            "source_type": "sec",
            "limit": 5,
        }
        val_resp = await async_client.post(
            "/api/v1/ingestion/validate", json=payload, headers=headers
        )
        assert val_resp.status_code == 403

        reg_resp = await async_client.post(
            "/api/v1/ingestion/register", json=payload, headers=headers
        )
        assert reg_resp.status_code == 403

    async def test_admin_can_validate_real_sec_dataset(self, async_client, seed_admin_and_viewer):
        admin = seed_admin_and_viewer["admin"]
        headers = auth_header(admin)
        payload = {
            "directory": "sec_10k_dataset",
            "source_type": "sec",
            "limit": 5,
        }
        resp = await async_client.post("/api/v1/ingestion/validate", json=payload, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_scanned"] == 5
        assert data["valid_count"] == 5
        assert data["invalid_count"] == 0
