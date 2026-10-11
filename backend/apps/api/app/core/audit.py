"""Audit logging helper for privileged operations (Rule 4 & Rule 6 compliant)."""
import uuid
from typing import Any

from apps.api.app.core.security import hash_ip
from apps.api.app.models.audit import AuditLog
from apps.api.app.repositories.audit_repo import AuditLogRepository
from sqlalchemy.ext.asyncio import AsyncSession


async def record_audit_log(
    session: AsyncSession,
    action: str,
    resource_type: str,
    user_id: uuid.UUID | None = None,
    resource_id: uuid.UUID | None = None,
    client_ip: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditLog:
    """Record a privileged or security-sensitive action to the audit_logs table.

    Rule 4 & 6: Never store raw passwords, API keys, access tokens, or raw IP addresses.
    """
    clean_metadata = None
    if metadata:
        clean_metadata = {
            k: v for k, v in metadata.items()
            if k not in {"password", "password_hash", "token", "access_token", "secret", "api_key"}
        }

    ip_hashed = hash_ip(client_ip) if client_ip else None

    audit_entry = AuditLog(
        id=uuid.uuid4(),
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_hash=ip_hashed,
        metadata_=clean_metadata,
    )

    repo = AuditLogRepository(session)
    return await repo.create(audit_entry)
