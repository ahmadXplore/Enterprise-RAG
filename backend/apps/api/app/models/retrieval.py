"""Query diagnostics and retrieval trace models."""
import uuid
from datetime import UTC, datetime

from apps.api.app.models.base import Base
from apps.api.app.models.types import GUID, CompatibleJSONB
from sqlalchemy import DateTime, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship


class Query(Base):
    __tablename__ = "queries"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("messages.id", ondelete="CASCADE"), nullable=True, index=True
    )
    raw_query: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    query_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    filters: Mapped[dict | None] = mapped_column(CompatibleJSONB(), nullable=True)
    retrieval_config: Mapped[dict | None] = mapped_column(CompatibleJSONB(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    message: Mapped["Message | None"] = relationship("Message", back_populates="queries")  # noqa: F821
    retrieval_runs: Mapped[list["RetrievalRun"]] = relationship(
        "RetrievalRun", back_populates="query", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_queries_user", "user_id"),
    )


class RetrievalRun(Base):
    __tablename__ = "retrieval_runs"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    query_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("queries.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dense_results: Mapped[dict | list | None] = mapped_column(CompatibleJSONB(), nullable=True)
    sparse_results: Mapped[dict | list | None] = mapped_column(CompatibleJSONB(), nullable=True)
    fusion_results: Mapped[dict | list | None] = mapped_column(CompatibleJSONB(), nullable=True)
    reranked_results: Mapped[dict | list | None] = mapped_column(CompatibleJSONB(), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    query: Mapped[Query] = relationship("Query", back_populates="retrieval_runs")
