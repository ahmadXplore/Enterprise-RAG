"""Evaluation routes: POST /runs, GET /runs/{id}, GET /runs.

Matches BACKEND SCHEMA.md Section 18.
Rule 4: require_analyst role required for evaluation management.
Rule 6: Minimum data exposure and explicit pagination.
Rule 24: Business logic delegates to EvaluationService.
"""

from __future__ import annotations

import uuid

from apps.api.app.api.deps import get_session, require_analyst
from apps.api.app.models.user import User
from apps.api.app.schemas.evaluation import EvaluationRunCreate, EvaluationRunRead
from apps.api.app.schemas.pagination import PaginatedResponse
from apps.api.app.services.evaluation_service import EvaluationService
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.post(
    "/runs",
    response_model=EvaluationRunRead,
    status_code=status.HTTP_201_CREATED,
    summary="Start / execute an evaluation run (Analyst only)",
)
async def create_evaluation_run(
    payload: EvaluationRunCreate,
    _current_user: User = Depends(require_analyst),
    session: AsyncSession = Depends(get_session),
) -> EvaluationRunRead:
    """Trigger an evaluation run on the benchmark dataset."""
    service = EvaluationService(session)
    return await service.create_run(payload)


@router.get(
    "/runs/{run_id}",
    response_model=EvaluationRunRead,
    status_code=status.HTTP_200_OK,
    summary="Get evaluation run status and metrics (Analyst only)",
)
async def get_evaluation_run(
    run_id: uuid.UUID,
    _current_user: User = Depends(require_analyst),
    session: AsyncSession = Depends(get_session),
) -> EvaluationRunRead:
    """Fetch status and aggregated IR and generation metrics for an evaluation run."""
    service = EvaluationService(session)
    return await service.get_run(run_id)


@router.get(
    "/runs",
    response_model=PaginatedResponse[EvaluationRunRead],
    status_code=status.HTTP_200_OK,
    summary="List evaluation runs with pagination (Analyst only)",
)
async def list_evaluation_runs(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    _current_user: User = Depends(require_analyst),
    session: AsyncSession = Depends(get_session),
) -> PaginatedResponse[EvaluationRunRead]:
    """Fetch paginated evaluation runs."""
    service = EvaluationService(session)
    return await service.list_runs(page=page, page_size=page_size)
