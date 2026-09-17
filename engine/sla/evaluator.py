"""
Covenant AI — SLA Evaluation Engine.

Runs every 5 minutes via APScheduler.
For each active SLAPolicy:
  - Computes the metric over the policy's window
  - Creates SLABreach if threshold exceeded and no open breach exists
  - Resolves open breaches that are back in compliance
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from engine.sla.models import SLAPolicy, SLABreach, MetricType
from engine.audit.models import AuditLog

logger = logging.getLogger("ironpass.sla.evaluator")

# Per 1K tokens, USD — hardcoded v1
MODEL_PRICING: dict[str, float] = {
    "gpt-4o": 0.005,
    "gpt-4o-mini": 0.00015,
    "claude-3-5-sonnet": 0.003,
    "claude-3-haiku": 0.00025,
    "gemini-1.5-pro": 0.0035,
}

DEFAULT_PRICE_PER_1K = 0.002  # Fallback for unrecognised models


def _model_price(model_name: Optional[str]) -> float:
    if not model_name:
        return DEFAULT_PRICE_PER_1K
    lower = model_name.lower()
    for key, price in MODEL_PRICING.items():
        if key in lower:
            return price
    return DEFAULT_PRICE_PER_1K


async def _compute_metric(
    db: AsyncSession,
    policy: SLAPolicy,
    now: datetime,
) -> Optional[float]:
    """
    Compute the current metric value for a policy over its window.
    Returns None if there is insufficient data.
    """
    window_start = now - timedelta(minutes=policy.window_minutes)
    # Fetch the agent_ids for this tenant (tenants can have multiple agents)
    from engine.auth.models import Tenant
    agent_result = await db.execute(
        select(Tenant.agent_id).where(Tenant.id == policy.tenant_id)
    )
    agent_ids = [row[0] for row in agent_result.all()]
    if not agent_ids:
        return None

    base_filter = and_(
        AuditLog.agent_id.in_(agent_ids),
        AuditLog.timestamp >= window_start,
    )

    metric = policy.metric_type

    if metric in (MetricType.LATENCY_P95, MetricType.LATENCY_P99):
        percentile = 0.95 if metric == MetricType.LATENCY_P95 else 0.99
        result = await db.execute(
            select(
                func.percentile_cont(percentile)
                .within_group(AuditLog.latency_ms)
            ).where(base_filter)
        )
        return result.scalar_one_or_none()

    elif metric == MetricType.ERROR_RATE:
        total_result = await db.execute(
            select(func.count(AuditLog.id)).where(base_filter)
        )
        total = total_result.scalar_one() or 0
        if total == 0:
            return None

        error_result = await db.execute(
            select(func.count(AuditLog.id)).where(
                and_(base_filter, AuditLog.outcome == "error")
            )
        )
        errors = error_result.scalar_one() or 0
        return (errors / total) * 100

    elif metric == MetricType.BLOCK_RATE:
        total_result = await db.execute(
            select(func.count(AuditLog.id)).where(base_filter)
        )
        total = total_result.scalar_one() or 0
        if total == 0:
            return None

        blocked_result = await db.execute(
            select(func.count(AuditLog.id)).where(
                and_(base_filter, AuditLog.was_blocked == True)
            )
        )
        blocked = blocked_result.scalar_one() or 0
        return (blocked / total) * 100

    elif metric == MetricType.COST_PER_SESSION:
        # Fetch rows with token data in window
        rows = (await db.execute(
            select(AuditLog.total_tokens, AuditLog.model)
            .where(and_(base_filter, AuditLog.total_tokens.isnot(None)))
        )).all()

        if not rows:
            return None

        total_cost = sum(
            (row.total_tokens / 1000) * _model_price(row.model)
            for row in rows
        )
        # Average cost per "session" (row = one proxy call)
        return total_cost / len(rows)

    return None


async def evaluate_all_policies(db: AsyncSession) -> None:
    """
    Main evaluation loop. Called by APScheduler every 5 minutes.
    """
    now = datetime.now(timezone.utc)
    logger.info("SLA evaluation run starting...")

    policies_result = await db.execute(
        select(SLAPolicy).where(SLAPolicy.is_active == True)
    )
    policies = policies_result.scalars().all()

    for policy in policies:
        try:
            metric_value = await _compute_metric(db, policy, now)

            if metric_value is None:
                logger.debug(f"SLA policy {policy.id} ({policy.name}): no data in window, skipping")
                continue

            is_breached = metric_value > policy.threshold_value

            # Find any open (unresolved) breach for this policy
            open_breach_result = await db.execute(
                select(SLABreach).where(
                    and_(
                        SLABreach.policy_id == policy.id,
                        SLABreach.resolved_at.is_(None),
                    )
                )
            )
            open_breach = open_breach_result.scalars().first()

            if is_breached and open_breach is None:
                # New breach — create record and notify
                breach = SLABreach(
                    tenant_id=policy.tenant_id,
                    policy_id=policy.id,
                    breached_at=now,
                    metric_value=metric_value,
                    threshold_value=policy.threshold_value,
                )
                db.add(breach)
                await db.flush()  # Get breach.id before notifier needs it

                logger.warning(
                    f"SLA BREACH: policy={policy.name} metric={policy.metric_type} "
                    f"value={metric_value:.4f} threshold={policy.threshold_value}"
                )

                # Notify (import here to avoid circular)
                from engine.sla.notifier import send_breach_notification
                await send_breach_notification(policy=policy, breach=breach, db=db)

            elif not is_breached and open_breach is not None:
                # Back in compliance — resolve the open breach
                open_breach.resolved_at = now
                logger.info(
                    f"SLA resolved: policy={policy.name} metric={policy.metric_type} "
                    f"value={metric_value:.4f} (was breaching)"
                )

        except Exception as e:
            logger.error(f"SLA evaluation error for policy {policy.id}: {e}", exc_info=True)

    await db.commit()
    logger.info(f"SLA evaluation run complete — evaluated {len(policies)} policies")
