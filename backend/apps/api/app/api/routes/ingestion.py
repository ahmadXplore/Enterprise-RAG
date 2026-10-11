"""Corpus scanning, validation, and registration routes (Admin only, Rule 4, 6, 11)."""

from pathlib import Path

from apps.api.app.api.deps import get_client_ip, get_session, require_admin, require_viewer
from apps.api.app.core.rate_limit import rate_limit_ingest
from apps.api.app.models.user import User
from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from packages.ingestion.registry import DocumentRegistrar
from packages.ingestion.scanner import scan_directory
from packages.ingestion.validator import CorpusValidator
from packages.schemas.common import DocumentSourceType
from packages.schemas.validation import CorpusValidationReport

router = APIRouter()


class IngestionScanRequest(BaseModel):
    directory: str = Field(
        ..., min_length=1, description="Path to directory containing document files"
    )
    source_type: DocumentSourceType = Field(..., description="Source type: sec, cuad, maud, acord")
    limit: int | None = Field(None, ge=1, le=1000, description="Maximum number of files to process")


class IngestionRegisterResponse(BaseModel):
    registered_count: int
    validation_report: CorpusValidationReport


@router.post(
    "/validate",
    response_model=CorpusValidationReport,
    status_code=status.HTTP_200_OK,
    summary="Validate document corpus without database registration (Admin only)",
)
async def validate_corpus(
    payload: IngestionScanRequest,
    _admin_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    _rl: None = Depends(rate_limit_ingest),
) -> CorpusValidationReport:
    """Scan configured directory and generate a validation report without persisting documents."""
    dir_path = Path(payload.directory)
    if payload.source_type == DocumentSourceType.SEC:
        extensions = {".html", ".htm"}
    elif payload.source_type == DocumentSourceType.EDUCATIONAL:
        extensions = {".pdf", ".docx", ".csv", ".xlsx", ".txt"}
    else:
        extensions = {".txt", ".pdf", ".jsonl", ".docx", ".csv", ".xlsx"}
    files = scan_directory(dir_path, allowed_extensions=extensions)
    if payload.limit:
        files = files[: payload.limit]

    validator = CorpusValidator(session)
    return await validator.validate_collection(files, payload.source_type)


@router.post(
    "/register",
    response_model=IngestionRegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Validate and register document corpus in PostgreSQL (Admin only)",
)
async def register_corpus(
    payload: IngestionScanRequest,
    request: Request,
    admin_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    _rl: None = Depends(rate_limit_ingest),
) -> IngestionRegisterResponse:
    """Scan, validate, and register valid documents and versions into PostgreSQL."""
    dir_path = Path(payload.directory)
    if payload.source_type == DocumentSourceType.SEC:
        extensions = {".html", ".htm"}
    elif payload.source_type == DocumentSourceType.EDUCATIONAL:
        extensions = {".pdf", ".docx", ".csv", ".xlsx", ".txt"}
    else:
        extensions = {".txt", ".pdf", ".jsonl", ".docx", ".csv", ".xlsx"}
    files = scan_directory(dir_path, allowed_extensions=extensions)
    if payload.limit:
        files = files[: payload.limit]

    validator = CorpusValidator(session)
    report = await validator.validate_collection(files, payload.source_type)

    registrar = DocumentRegistrar(session)
    registered_count = 0
    client_ip = get_client_ip(request)

    for valid_res in report.valid_files:
        await registrar.register_document(
            validation_result=valid_res,
            admin_user_id=admin_user.id,
            client_ip=client_ip,
        )
        registered_count += 1

    await session.commit()

    return IngestionRegisterResponse(
        registered_count=registered_count,
        validation_report=report,
    )


@router.get(
    "/jobs/{job_id}",
    status_code=status.HTTP_200_OK,
    summary="Get ingestion job status, progress, and stage",
)
async def get_job_status(
    job_id: str,
    _current_user: User = Depends(require_viewer),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Fetch ingestion job status.

    Matches BACKEND SCHEMA.md Section 6: GET /ingestion/jobs/{job_id}
    Returns: job_id, status, progress, stage
    """
    import uuid

    from apps.api.app.services.ingestion_service import IngestionService

    try:
        job_uuid = uuid.UUID(job_id)
    except (ValueError, TypeError) as err:
        from apps.api.app.core.exceptions import NotFoundException

        raise NotFoundException(f"Job {job_id} not found") from err

    service = IngestionService(session)
    return await service.get_job_status(job_uuid)


@router.get(
    "/jobs",
    status_code=status.HTTP_200_OK,
    summary="List recent ingestion jobs (Admin only)",
)
async def list_jobs(
    limit: int = 50,
    _admin_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """Fetch recent ingestion jobs for admin monitoring."""
    from apps.api.app.services.ingestion_service import IngestionService

    service = IngestionService(session)
    return await service.list_jobs(limit=limit)
