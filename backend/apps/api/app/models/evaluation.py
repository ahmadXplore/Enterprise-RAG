"""Evaluation sets, cases, references, runs, and results models."""
import uuid
from datetime import UTC, datetime

from apps.api.app.models.base import Base
from apps.api.app.models.types import GUID, CompatibleJSONB
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship


class EvaluationSet(Base):
    __tablename__ = "evaluation_sets"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[str | None] = mapped_column(String(50), default="1.0", nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    cases: Mapped[list["EvaluationCase"]] = relationship(
        "EvaluationCase", back_populates="evaluation_set", cascade="all, delete-orphan"
    )
    runs: Mapped[list["EvaluationRun"]] = relationship(
        "EvaluationRun", back_populates="evaluation_set", cascade="all, delete-orphan"
    )


class EvaluationCase(Base):
    __tablename__ = "evaluation_cases"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    evaluation_set_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("evaluation_sets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    expected_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    query_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", CompatibleJSONB(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    evaluation_set: Mapped[EvaluationSet] = relationship("EvaluationSet", back_populates="cases")
    references: Mapped[list["EvaluationReference"]] = relationship(
        "EvaluationReference", back_populates="evaluation_case", cascade="all, delete-orphan"
    )


class EvaluationReference(Base):
    __tablename__ = "evaluation_references"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    evaluation_case_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("evaluation_cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("document_chunks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    relevance_grade: Mapped[int] = mapped_column(Integer, default=1, nullable=False)  # 0, 1, 2
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    evaluation_case: Mapped[EvaluationCase] = relationship(
        "EvaluationCase", back_populates="references"
    )


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    evaluation_set_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("evaluation_sets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    configuration: Mapped[dict | None] = mapped_column(CompatibleJSONB(), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="queued", nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    evaluation_set: Mapped[EvaluationSet] = relationship("EvaluationSet", back_populates="runs")
    results: Mapped[list["EvaluationRunResult"]] = relationship(
        "EvaluationRunResult", back_populates="evaluation_run", cascade="all, delete-orphan"
    )


class EvaluationRunResult(Base):
    __tablename__ = "evaluation_run_results"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    evaluation_run_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("evaluation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    evaluation_case_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("evaluation_cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    retrieved_chunk_ids: Mapped[list | dict | None] = mapped_column(
        CompatibleJSONB(), nullable=True
    )
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    recall_at_k: Mapped[dict | None] = mapped_column(CompatibleJSONB(), nullable=True)
    mrr: Mapped[float | None] = mapped_column(Float, nullable=True)
    ndcg_at_k: Mapped[dict | None] = mapped_column(CompatibleJSONB(), nullable=True)
    answer_relevance: Mapped[float | None] = mapped_column(Float, nullable=True)
    groundedness: Mapped[float | None] = mapped_column(Float, nullable=True)
    citation_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    abstention_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    evaluation_run: Mapped[EvaluationRun] = relationship("EvaluationRun", back_populates="results")
