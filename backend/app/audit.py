"""Audit logging — records who asked what and which documents were returned.

Every retrieval, upload, delete, and role change is written to the `audit_logs`
table so an admin can later prove the ACL boundary held: a query only ever
returned documents the asking user's roles permit.

Audit writes are **best-effort**. If the insert fails we log it and roll back the
audit row, but never propagate the error — auditing must never break the user's
actual request.
"""
import logging

from sqlalchemy.orm import Session

from app.models import AuditLog

logger = logging.getLogger(__name__)

# Action types stored in AuditLog.action. Kept as constants so callers and
# queries agree on the exact strings.
ACTION_QUERY = "query"
ACTION_UPLOAD = "upload"
ACTION_DELETE = "delete"
ACTION_RETAG = "retag"
ACTION_ROLE_CHANGE = "role_change"


def record_audit(
    db: Session,
    *,
    actor_email: str,
    actor_roles: list[str],
    action: str,
    detail: str = "",
    query: str | None = None,
    document_ids: list[int] | None = None,
    document_names: list[str] | None = None,
    num_results: int | None = None,
) -> AuditLog:
    """Write a single audit entry. Swallows DB errors so it can't break callers."""
    entry = AuditLog(
        actor_email=actor_email,
        actor_roles=list(actor_roles or []),
        action=action,
        detail=detail,
        query=query,
        document_ids=list(document_ids or []),
        document_names=list(document_names or []),
        num_results=num_results,
    )
    try:
        db.add(entry)
        db.commit()
    except Exception:
        logger.exception("Failed to write audit log entry (action=%s)", action)
        db.rollback()
    return entry
