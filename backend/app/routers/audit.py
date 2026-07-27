"""Audit log routes (admin only).

Lets an admin review the append-only trail of who asked what and which
ACL-filtered documents were returned — the evidence that the access boundary
held for every query.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import auth
from app.database import get_db
from app.models import AuditLog
from app.schemas import AuditLogOut

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("", response_model=list[AuditLogOut])
def list_audit(
    action: str | None = Query(None, description="Filter by action type."),
    actor_email: str | None = Query(None, description="Filter by who acted."),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _: auth.CurrentUser = Depends(auth.require_admin),
    db: Session = Depends(get_db),
):
    """Return audit entries, newest first, with optional filtering."""
    q = db.query(AuditLog)
    if action:
        q = q.filter(AuditLog.action == action)
    if actor_email:
        q = q.filter(AuditLog.actor_email == actor_email)
    return (
        q.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()
    )
