"""Audit logging model for privileged and security-sensitive operations."""
import uuid
from datetime import UTC, datetime

from apps.api.app.models.base import Base
from apps.api.app.models.types import GUID, CompatibleJSONB
from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship


class AuditLog(Base):
    """Audit log table.

    Rule 4 & Rule 6: Never store raw passwords, API keys, or access tokens.
    """
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True, index=True)
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", CompatibleJSONB(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    user: Mapped["User | None"] = relationship("User", back_populates="audit_logs")  # noqa: F821

    __table_args__ = (
        Index("idx_audit_created", "created_at"),
    )
