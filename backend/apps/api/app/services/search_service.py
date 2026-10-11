"""Search service with strict Pre-Retrieval Authorization enforcement.

BACKEND SCHEMA.md Section 7 & 25:
- User -> Authentication (JWT) -> Authorization (resolved allowed document IDs from DB)
- Injects authorized_document_ids into retrieval filters before querying vector store.
- Returns only minimal required fields in SearchResponse.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from apps.api.app.config import get_settings
from apps.api.app.models.user import User
from apps.api.app.repositories.document_repo import DocumentRepository
from apps.api.app.schemas.search import (
    SearchRequest,
    SearchResponse,
    SearchResultItem,
)
from sqlalchemy.ext.asyncio import AsyncSession

from packages.retrieval.hybrid import HybridRetriever
from packages.retrieval.models import RetrievalResult
from packages.schemas.common import RoleType

logger = logging.getLogger("enterprise_rag")


class SearchService:
    """Executes authorized search queries against the hybrid retrieval system."""

    def __init__(
        self,
        session: AsyncSession,
        retriever: HybridRetriever | None = None,
    ) -> None:
        self.session = session
        self.doc_repo = DocumentRepository(session)
        self._retriever = retriever

    def _get_retriever(self) -> HybridRetriever:
        """Resolve or lazily construct the HybridRetriever."""
        if self._retriever is not None:
            return self._retriever

        settings = get_settings()
        from packages.retrieval.dense import DenseRetriever
        from packages.retrieval.qdrant_client import create_qdrant_client
        from packages.retrieval.sparse import SparseRetriever

        client = create_qdrant_client(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)
        try:
            from packages.retrieval.embeddings import BM25SparseEmbedder, FastEmbedDenseEmbedder

            dense_emb = FastEmbedDenseEmbedder()
            sparse_emb = BM25SparseEmbedder()
        except Exception:
            from packages.retrieval.embeddings import DeterministicMockEmbedder

            dense_emb = DeterministicMockEmbedder()
            sparse_emb = dense_emb

        try:
            from packages.retrieval.reranker import FastEmbedReranker

            reranker = FastEmbedReranker()
        except Exception:
            from packages.retrieval.reranker import LexicalSemanticMockReranker

            reranker = LexicalSemanticMockReranker()

        dense = DenseRetriever(client=client, embedder=dense_emb)
        sparse = SparseRetriever(client=client, embedder=sparse_emb)

        self._retriever = HybridRetriever(
            dense_retriever=dense,
            sparse_retriever=sparse,
            reranker=reranker,
        )
        return self._retriever

    async def _resolve_company_names(self, company_inputs: list[str]) -> list[str]:
        """Resolve user-provided institution/company names (e.g. 'Stanford' -> 'Stanford University') against the database."""
        from apps.api.app.models.document import Document
        from sqlalchemy import or_, select

        alias_map = {
            "stanford": "Stanford University",
            "stanford university": "Stanford University",
            "harvard": "Harvard University",
            "harvard university": "Harvard University",
            "mit": "MIT",
            "mit eecs": "MIT EECS",
            "cmu": "Carnegie Mellon University",
            "carnegie mellon": "Carnegie Mellon University",
            "berkeley": "UC Berkeley",
            "uc berkeley": "UC Berkeley",
            "oxford": "University of Oxford",
            "cambridge": "University of Cambridge",
            "unesco": "UNESCO",
            "oecd": "OECD",
            "world bank": "World Bank",
            "worldbank": "World Bank",
            "wb": "World Bank",
            "nsf": "National Science Foundation",
            "nces": "NCES",
            "nber": "NBER",
            "eric": "ERIC Education Database",
            "kaggle": "Kaggle Academic Research",
            "uci": "UCI Machine Learning Repository",
            "owid": "Our World in Data",
            "our world in data": "Our World in Data",
        }

        resolved: set[str] = set()
        for raw in company_inputs:
            trimmed = raw.strip()
            if not trimmed:
                continue

            lower_clean = trimmed.lower()
            if lower_clean in alias_map:
                resolved.add(alias_map[lower_clean])

            stmt = select(Document.organization).where(
                or_(
                    Document.organization.ilike(f"%{trimmed}%"),
                    Document.ticker.ilike(trimmed),
                )
            ).distinct()
            res = await self.session.execute(stmt)
            matches = [row[0] for row in res.fetchall() if row[0]]
            if matches:
                resolved.update(matches)
            elif lower_clean not in alias_map:
                resolved.add(trimmed)

        return list(resolved)

    def _infer_document_type_from_query(self, query: str) -> list[str] | None:
        """Infer target document type if user query explicitly refers to a document category."""
        q_lower = query.lower()
        if any(term in q_lower for term in [
            "academic paper", "academic papers", "research paper", "research papers",
            "journal article", "scientific paper", "scientific study", "empirical study"
        ]):
            return ["research_paper"]
        if any(term in q_lower for term in [
            "syllabus", "syllabi", "course syllabus", "course guide", "course outline", "curriculum"
        ]):
            return ["syllabus"]
        if any(term in q_lower for term in [
            "dataset", "datasets", "survey data", "raw data", "data collection", "csv"
        ]):
            return ["dataset"]
        if any(term in q_lower for term in [
            "spreadsheet", "spreadsheets", "excel", "workbook", "gradebook", "assessment matrix", "data table"
        ]):
            return ["spreadsheet"]
        if any(term in q_lower for term in [
            "doctoral defense", "dissertation protocol", "defense protocol", "standard procedure"
        ]):
            return ["educational"]
        return None

    async def search(
        self,
        request: SearchRequest,
        current_user: User,
    ) -> SearchResponse:
        """Execute search with pre-retrieval access control, intent validation, and helpful fallback messages."""
        query_id = str(uuid.uuid4())
        is_admin = any(
            r.name == RoleType.ADMIN.value or r.name == RoleType.ADMIN for r in current_user.roles
        )
        role_ids = [r.id for r in current_user.roles]

        # 1. Resolve allowed document IDs from database before any vector call
        allowed_uuids = await self.doc_repo.get_allowed_document_ids(
            user_id=current_user.id,
            role_ids=role_ids,
            is_admin=is_admin,
        )
        allowed_id_strings = [str(uid) for uid in allowed_uuids]

        if not allowed_id_strings:
            return SearchResponse(
                query_id=query_id,
                results=[],
                message="You do not have access permissions to any documents in the database.",
            )

        # 2. Build retrieval filters & detect target document types
        filters: dict[str, Any] = {
            "authorized_document_ids": allowed_id_strings,
        }
        resolved_companies: list[str] = []
        target_doc_types: list[str] | None = None

        if request.filters:
            f = request.filters
            if f.companies:
                resolved_companies = await self._resolve_company_names(f.companies)
                filters["company"] = resolved_companies
                filters["companies"] = resolved_companies
            if f.years:
                filters["year"] = f.years
                filters["years"] = f.years
            if f.document_type:
                from packages.llm.graph import resolve_document_type
                resolved_dt = resolve_document_type(f.document_type)
                target_doc_types = resolved_dt or [f.document_type]
            if f.extra:
                filters.update(f.extra)

        # Infer document type from query text if not explicitly selected
        if not target_doc_types:
            target_doc_types = self._infer_document_type_from_query(request.query)

        # 3. Availability check against repository when constraints are provided
        if resolved_companies:
            from apps.api.app.models.document import Document
            from sqlalchemy import select

            stmt = select(Document.document_type, Document.title).where(
                Document.organization.in_(resolved_companies),
                Document.id.in_(allowed_uuids),
            )
            res = await self.session.execute(stmt)
            org_docs = res.fetchall()

            org_display = ", ".join(resolved_companies)

            if not org_docs:
                return SearchResponse(
                    query_id=query_id,
                    results=[],
                    message=f"No documents from {org_display} are currently available in the database.",
                )

            # Check if user specifically requested a document type that does not exist for this organization
            if target_doc_types:
                matching_docs = [d for d in org_docs if d[0] in target_doc_types]
                if not matching_docs:
                    type_display_map = {
                        "research_paper": "Research Papers",
                        "syllabus": "Course Syllabi",
                        "dataset": "Academic Datasets",
                        "spreadsheet": "Spreadsheets & Gradebooks",
                        "educational": "Educational Guidelines & Protocols",
                    }
                    available_types = sorted(list(set(d[0] for d in org_docs)))
                    avail_strs = [type_display_map.get(t, t.replace("_", " ").title()) for t in available_types]
                    req_name = type_display_map.get(target_doc_types[0], target_doc_types[0].replace("_", " ").title())
                    
                    sample_titles = [d[1] for d in org_docs[:3]]
                    return SearchResponse(
                        query_id=query_id,
                        results=[],
                        message=(
                            f"No {req_name.lower()} from {org_display} are available in the repository. "
                            f"Available materials for {org_display} include: {', '.join(avail_strs)}."
                        ),
                        available_resources=sample_titles,
                    )

        if target_doc_types:
            filters["document_type"] = target_doc_types
            filters["document_types"] = target_doc_types

        # 4. Retrieve candidate chunks
        retriever = self._get_retriever()
        chunks: list[RetrievalResult] = []
        try:
            raw_chunks, _ = retriever.retrieve(
                query=request.query,
                filters=filters,
            )
            chunks = raw_chunks[: request.top_k]
        except Exception as exc:
            logger.warning(
                "Search retrieval encountered error; returning empty results",
                extra={"extra": {"error": str(exc), "query_id": query_id}},
            )
            chunks = []

        # 5. Look up document titles and types from database
        from apps.api.app.models.document import Document
        from sqlalchemy import select

        doc_ids = list(set(c.document_id for c in chunks if c.document_id))
        doc_info: dict[str, tuple[str, str]] = {}
        if doc_ids:
            try:
                # Convert string UUIDs to UUID objects for Postgres/SQLite compatibility
                parsed_uuids = [uuid.UUID(did) for did in doc_ids]
                stmt = select(Document.id, Document.title, Document.document_type).where(
                    Document.id.in_(parsed_uuids)
                )
                res = await self.session.execute(stmt)
                doc_info = {str(row[0]): (row[1], row[2]) for row in res.fetchall()}
            except Exception as e:
                logger.warning("Failed to batch load document titles: %s", e)

        # 6. Map to response schema
        results: list[SearchResultItem] = []
        for c in chunks:
            score_val = c.score
            if score_val < 0.0 or score_val > 1.0:
                import math
                try:
                    score_val = 1.0 / (1.0 + math.exp(-score_val))
                except OverflowError:
                    score_val = 0.0 if score_val < 0 else 1.0

            # Filter out extremely low-confidence chunks (< 0.05)
            if score_val < 0.05:
                continue

            doc_title, doc_type = doc_info.get(
                c.document_id,
                (c.company or "Corpus Document", c.document_type or "document")
            )

            results.append(
                SearchResultItem(
                    chunk_id=c.chunk_id,
                    document_id=c.document_id,
                    score=round(score_val, 4),
                    text=c.text,
                    company=c.company,
                    year=c.year,
                    page=c.page_start,
                    document_title=doc_title,
                    document_type=doc_type,
                )
            )

        # 7. Formulate feedback message if no results found
        message: str | None = None
        if not results:
            if resolved_companies and target_doc_types:
                org_display = ", ".join(resolved_companies)
                message = f"No documents matching '{request.query}' found for {org_display} in the database."
            elif resolved_companies:
                org_display = ", ".join(resolved_companies)
                message = f"No matching passages found for '{request.query}' in {org_display} records."
            else:
                message = f"This information ('{request.query}') is not available in the database under your current search criteria."

        return SearchResponse(query_id=query_id, results=results, message=message)
