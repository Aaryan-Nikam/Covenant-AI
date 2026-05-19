"""
Ironpass — Audit log query API.

Tenant-scoped: each tenant can only query their own audit log entries.
Scoped by agent_id (= tenant.id).

Endpoints:
    GET /v1/logs          — paginated audit log with filters
    GET /v1/logs/{entry_id} — single entry detail

Filters:
    outcome      — "passed" | "blocked" | "error"
    ruleset      — filter to entries where this ruleset was used
    start        — ISO 8601 datetime (inclusive)
    end          — ISO 8601 datetime (inclusive)
    limit        — max 200, default 50
    offset       — for pagination

These are read-only endpoints — the audit log is append-only.
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from engine.audit.models import AuditLog
from engine.auth.models import Tenant
from engine.dependencies import get_db, verify_api_key

logger = logging.getLogger("ironpass.logs")

router = APIRouter(prefix="/v1/logs", tags=["logs"])

_MAX_LIMIT = 200
_DEFAULT_LIMIT = 50


# ---------------------------------------------------------------------------
# Response models (plain dicts — no pydantic overhead for large result sets)
# ---------------------------------------------------------------------------

def _serialize_entry(entry: AuditLog) -> dict:
    """Serialize an AuditLog row to a safe tenant-facing dict.
    Strips internal integrity fields (hmac_signature, prev_entry_hash).
    """
    return {
        "entry_id": str(entry.entry_id),
        "timestamp": entry.timestamp.isoformat() if entry.timestamp else None,
        "outcome": entry.outcome,
        "was_blocked": entry.was_blocked,
        "rulesets_used": entry.rulesets_used or [],
        "detections": entry.detections or [],
        "detections_count": len(entry.detections or []),
        "actions_taken": entry.actions_taken or [],
        "target_url": entry.target_url,
        "latency_ms": entry.latency_ms,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("")
async def list_audit_logs(
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=_DEFAULT_LIMIT, le=_MAX_LIMIT, ge=1),
    offset: int = Query(default=0, ge=0),
    outcome: Optional[str] = Query(default=None, description="passed | blocked | error"),
    ruleset: Optional[str] = Query(default=None, description="Filter by ruleset name"),
    start: Optional[datetime] = Query(default=None, description="Start datetime (ISO 8601)"),
    end: Optional[datetime] = Query(default=None, description="End datetime (ISO 8601)"),
    blocked_only: bool = Query(default=False, description="Shortcut: only show blocked requests"),
) -> dict:
    """
    Returns the paginated audit log for this tenant.

    Entries are ordered newest-first. Use limit + offset for pagination.
    """
    # Base query — scoped to this tenant
    base_query = select(AuditLog).where(AuditLog.agent_id == tenant.agent_id)

    # Filters
    if blocked_only or outcome == "blocked":
        base_query = base_query.where(AuditLog.was_blocked == True)  # noqa: E712
    elif outcome:
        base_query = base_query.where(AuditLog.outcome == outcome)

    if ruleset:
        # ARRAY contains check (PostgreSQL)
        base_query = base_query.where(AuditLog.rulesets_used.contains([ruleset]))

    if start:
        base_query = base_query.where(AuditLog.timestamp >= start)

    if end:
        base_query = base_query.where(AuditLog.timestamp <= end)

    # Count total matching rows (for pagination UI)
    count_result = await db.execute(
        select(func.count()).select_from(base_query.subquery())
    )
    total = count_result.scalar_one()

    # Fetch page
    page_query = (
        base_query
        .order_by(AuditLog.timestamp.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(page_query)
    entries = result.scalars().all()

    logger.debug(
        f"Audit log query: tenant={tenant.id}, "
        f"filters=outcome:{outcome},ruleset:{ruleset}, "
        f"returned={len(entries)}/{total}"
    )

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": (offset + limit) < total,
        "entries": [_serialize_entry(e) for e in entries],
    }


@router.get("/{entry_id}")
async def get_audit_log_entry(
    entry_id: str,
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Returns a single audit log entry by its entry_id.
    Returns 404 if not found or belongs to a different tenant.
    """
    result = await db.execute(
        select(AuditLog).where(
            AuditLog.entry_id == entry_id,
            AuditLog.agent_id == tenant.agent_id,  # Tenant isolation
        )
    )
    entry = result.scalar_one_or_none()

    if entry is None:
        raise HTTPException(status_code=404, detail="Audit log entry not found")

    return _serialize_entry(entry)
