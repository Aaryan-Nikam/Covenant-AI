"""
Covenant AI — SLA API Router.

All endpoints require tenant API key auth via verify_api_key.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from engine.dependencies import get_db, verify_api_key
from engine.sla.models import SLAPolicy, SLABreach, MetricType
from engine.auth.models import Tenant
from engine.dependencies import verify_api_key

logger = logging.getLogger("ironpass.sla")
router = APIRouter(prefix="/sla", tags=["SLA"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class SLAPolicyCreate(BaseModel):
    name: str
    metric_type: MetricType
    threshold_value: float
    window_minutes: int = 60
    notification_email: Optional[str] = None
    webhook_url: Optional[str] = None
    is_active: bool = True


class SLAPolicyUpdate(BaseModel):
    name: Optional[str] = None
    metric_type: Optional[MetricType] = None
    threshold_value: Optional[float] = None
    window_minutes: Optional[int] = None
    notification_email: Optional[str] = None
    webhook_url: Optional[str] = None
    is_active: Optional[bool] = None


# ---------------------------------------------------------------------------
# Policy endpoints
# ---------------------------------------------------------------------------

@router.get("/policies")
async def list_policies(
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SLAPolicy).where(SLAPolicy.tenant_id == tenant.id)
    )
    return {"policies": result.scalars().all()}


@router.post("/policies", status_code=201)
async def create_policy(
    body: SLAPolicyCreate,
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    policy = SLAPolicy(
        tenant_id=tenant.id,
        name=body.name,
        metric_type=body.metric_type.value,
        threshold_value=body.threshold_value,
        window_minutes=body.window_minutes,
        notification_email=body.notification_email,
        webhook_url=body.webhook_url,
        is_active=body.is_active,
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)
    return {"policy": policy}


@router.patch("/policies/{policy_id}")
async def update_policy(
    policy_id: UUID,
    body: SLAPolicyUpdate,
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SLAPolicy).where(
            SLAPolicy.id == policy_id,
            SLAPolicy.tenant_id == tenant.id,
        )
    )
    policy = result.scalars().first()
    if not policy:
        raise HTTPException(404, "Policy not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        if field == "metric_type" and value is not None:
            value = value if isinstance(value, str) else value.value
        setattr(policy, field, value)

    await db.commit()
    await db.refresh(policy)
    return {"policy": policy}


@router.delete("/policies/{policy_id}", status_code=204)
async def delete_policy(
    policy_id: UUID,
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SLAPolicy).where(
            SLAPolicy.id == policy_id,
            SLAPolicy.tenant_id == tenant.id,
        )
    )
    policy = result.scalars().first()
    if not policy:
        raise HTTPException(404, "Policy not found")

    # Block deletion if there's an open breach
    open_breach = (await db.execute(
        select(SLABreach).where(
            SLABreach.policy_id == policy_id,
            SLABreach.resolved_at.is_(None),
        )
    )).scalars().first()

    if open_breach:
        raise HTTPException(
            409,
            "Cannot delete policy with an open breach — resolve the breach first"
        )

    await db.delete(policy)
    await db.commit()


# ---------------------------------------------------------------------------
# Breach endpoints
# ---------------------------------------------------------------------------

@router.get("/breaches")
async def list_breaches(
    status: Optional[str] = None,  # "open" | "resolved"
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    query = select(SLABreach).where(SLABreach.tenant_id == tenant.id)

    if status == "open":
        query = query.where(SLABreach.resolved_at.is_(None))
    elif status == "resolved":
        query = query.where(SLABreach.resolved_at.isnot(None))

    result = await db.execute(query.order_by(SLABreach.breached_at.desc()))
    return {"breaches": result.scalars().all()}


# ---------------------------------------------------------------------------
# Live metrics endpoint
# ---------------------------------------------------------------------------

@router.get("/metrics/live")
async def live_metrics(
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    """
    For each active policy, compute the current metric value on-demand.
    Does NOT create breach records — read-only.
    """
    from engine.sla.evaluator import _compute_metric

    result = await db.execute(
        select(SLAPolicy).where(
            SLAPolicy.tenant_id == tenant.id,
            SLAPolicy.is_active == True,
        )
    )
    policies = result.scalars().all()
    now = datetime.now(timezone.utc)
    metrics = []

    for policy in policies:
        try:
            value = await _compute_metric(db, policy, now)
        except Exception as e:
            logger.warning(f"Live metric error for policy {policy.id}: {e}")
            value = None

        if value is not None:
            breached = value > policy.threshold_value
            status = "breached" if breached else "ok"
        else:
            status = "no_data"

        metrics.append({
            "policy_id": str(policy.id),
            "policy_name": policy.name,
            "metric_type": policy.metric_type,
            "current_value": value,
            "threshold_value": policy.threshold_value,
            "status": status,
            "last_evaluated": now.isoformat(),
        })

    return {"metrics": metrics}
