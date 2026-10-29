"""Forensic audit trail.

Every mutating endpoint records who did what to which artifact, with a
before/after snapshot of the fields that changed. Rows are added to the
caller's session so they commit atomically with the change they describe.
"""

from typing import Any

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import AuditLog, iso
from backend.db.session import get_db

router = APIRouter(prefix="/audit", tags=["audit"])


def actor_header(x_visentra_actor: str | None = Header(default=None)) -> str:
    return (x_visentra_actor or "api").strip()[:128] or "api"


def log_audit(
    db: AsyncSession,
    *,
    actor: str,
    action: str,
    artifact_type: str,
    artifact_id: str,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor=actor,
        action=action,
        artifact_type=artifact_type,
        artifact_id=artifact_id,
        before=before or {},
        after=after or {},
    )
    db.add(entry)
    return entry


class AuditOut(BaseModel):
    id: str
    actor: str | None
    action: str | None
    artifact_type: str | None
    artifact_id: str | None
    before: dict | None
    after: dict | None
    timestamp: str


@router.get("", response_model=list[AuditOut])
async def list_audit(
    artifact_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit)
    if artifact_id:
        stmt = stmt.where(AuditLog.artifact_id == artifact_id)
    rows = (await db.execute(stmt)).scalars().all()
    return [
        AuditOut(
            id=r.id,
            actor=r.actor,
            action=r.action,
            artifact_type=r.artifact_type,
            artifact_id=r.artifact_id,
            before=r.before,
            after=r.after,
            timestamp=iso(r.timestamp),
        )
        for r in rows
    ]
