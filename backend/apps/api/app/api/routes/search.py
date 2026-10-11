"""POST /api/v1/search endpoint.

Matches BACKEND SCHEMA.md Section 7.
Rule 4: require_viewer role required.
Rule 6: Minimum data exposure.
Rule 12 & 25: Pre-retrieval authorization enforced before vector store search.
"""

from __future__ import annotations

from apps.api.app.api.deps import get_session, require_viewer
from apps.api.app.core.rate_limit import rate_limit_search
from apps.api.app.models.user import User
from apps.api.app.schemas.search import SearchRequest, SearchResponse
from apps.api.app.services.search_service import SearchService
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.post(
    "",
    response_model=SearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Hybrid search with backend pre-retrieval authorization",
)
async def search(
    request: SearchRequest,
    current_user: User = Depends(require_viewer),
    session: AsyncSession = Depends(get_session),
    _rl: None = Depends(rate_limit_search),
) -> SearchResponse:
    """Execute hybrid search scoped strictly to documents the user is authorized to view."""
    service = SearchService(session)
    return await service.search(request=request, current_user=current_user)
