"""
Ironpass — Dashboard backend API routes.

Provides REST endpoints for the dashboard frontend.
All routes require a database session.
"""

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from dashboard.backend.service import DashboardService
from engine.dependencies import get_db, verify_api_key
from engine.auth.models import Tenant

logger = logging.getLogger("ironpass.dashboard.router")

router = APIRouter()


@router.get("/overview", summary="Dashboard overview stats")
async def overview(
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Get overview statistics for the dashboard."""
    service = DashboardService(db)
    return await service.get_overview()


@router.get("/violations", summary="Recent violations (blocked requests)")
async def violations(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Get recent blocked request entries."""
    service = DashboardService(db)
    return await service.get_violations(limit=limit, offset=offset)


@router.get("/audit", summary="Audit log entries")
async def audit_log(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    agent_id: str | None = Query(default=None),
    outcome: str | None = Query(default=None, description="passed, blocked, error"),
    ruleset: str | None = Query(default=None),
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Get audit log entries with optional agent_id filter."""
    service = DashboardService(db)
    return await service.get_audit_log(
        limit=limit, offset=offset, agent_id=agent_id,
        outcome=outcome, ruleset=ruleset
    )


@router.get("/audit/verify", summary="Verify audit chain integrity")
async def verify_audit(
    limit: int = Query(default=100, ge=1, le=1000),
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Verify the integrity of the audit chain."""
    service = DashboardService(db)
    return await service.verify_audit_integrity(limit=limit)
