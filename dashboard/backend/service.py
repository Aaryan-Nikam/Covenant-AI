"""
Ironpass — Dashboard backend service.

Business logic for the dashboard API.
Provides overview stats, violation history, audit log queries,
and ruleset management.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from engine.audit.models import AuditLog
from engine.vault.models import VaultToken

logger = logging.getLogger("ironpass.dashboard.service")


class DashboardService:
    """Business logic for the dashboard."""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def get_overview(self) -> dict:
        """
        Dashboard overview stats:
        - Total requests processed
        - Total blocked
        - Total detections
        - Requests in last 24h
        - Active tokens in vault
        """
        now = datetime.now(timezone.utc)
        last_24h = now - timedelta(hours=24)

        # Total requests
        total_result = await self.db.execute(
            select(func.count(AuditLog.id))
        )
        total_requests = total_result.scalar() or 0

        # Total blocked
        blocked_result = await self.db.execute(
            select(func.count(AuditLog.id)).where(AuditLog.was_blocked == True)
        )
        total_blocked = blocked_result.scalar() or 0

        # Requests in last 24h
        recent_result = await self.db.execute(
            select(func.count(AuditLog.id)).where(
                AuditLog.timestamp >= last_24h
            )
        )
        requests_24h = recent_result.scalar() or 0

        # Active vault tokens
        active_tokens_result = await self.db.execute(
            select(func.count(VaultToken.token)).where(
                VaultToken.expires_at > now,
                VaultToken.invalidated_at.is_(None),
            )
        )
        active_tokens = active_tokens_result.scalar() or 0

        # Average latency
        avg_latency_result = await self.db.execute(
            select(func.avg(AuditLog.latency_ms))
        )
        avg_latency = avg_latency_result.scalar() or 0

        return {
            "total_requests": total_requests,
            "total_blocked": total_blocked,
            "requests_24h": requests_24h,
            "active_vault_tokens": active_tokens,
            "avg_latency_ms": round(float(avg_latency), 1),
            "block_rate": round(
                (total_blocked / total_requests * 100) if total_requests > 0 else 0, 1
            ),
        }

    async def get_violations(
        self, limit: int = 50, offset: int = 0
    ) -> dict:
        """
        Get recent violation (blocked request) entries.
        """
        result = await self.db.execute(
            select(AuditLog)
            .where(AuditLog.was_blocked == True)
            .order_by(desc(AuditLog.timestamp))
            .limit(limit)
            .offset(offset)
        )
        entries = result.scalars().all()

        count_result = await self.db.execute(
            select(func.count(AuditLog.id)).where(AuditLog.was_blocked == True)
        )
        total = count_result.scalar() or 0

        return {
            "violations": [
                {
                    "entry_id": str(e.entry_id),
                    "timestamp": e.timestamp.isoformat(),
                    "agent_id": e.agent_id,
                    "rulesets_used": e.rulesets_used,
                    "detections": e.detections,
                    "actions_taken": e.actions_taken,
                    "outcome": e.outcome,
                }
                for e in entries
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    async def get_audit_log(
        self, limit: int = 50, offset: int = 0, agent_id: str | None = None
    ) -> dict:
        """
        Get audit log entries with optional agent_id filter.
        """
        query = select(AuditLog).order_by(desc(AuditLog.timestamp))

        if agent_id:
            query = query.where(AuditLog.agent_id == agent_id)

        result = await self.db.execute(query.limit(limit).offset(offset))
        entries = result.scalars().all()

        count_query = select(func.count(AuditLog.id))
        if agent_id:
            count_query = count_query.where(AuditLog.agent_id == agent_id)
        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0

        return {
            "entries": [
                {
                    "entry_id": str(e.entry_id),
                    "timestamp": e.timestamp.isoformat(),
                    "agent_id": e.agent_id,
                    "rulesets_used": e.rulesets_used,
                    "detections_count": len(e.detections) if e.detections else 0,
                    "actions_count": len(e.actions_taken) if e.actions_taken else 0,
                    "was_blocked": e.was_blocked,
                    "outcome": e.outcome,
                    "latency_ms": e.latency_ms,
                }
                for e in entries
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    async def verify_audit_integrity(self, limit: int = 100) -> dict:
        """
        Verify audit chain integrity.
        Returns a rich, compliance-ready verification report:
        - Chain status (INTACT / BROKEN / EMPTY)
        - Entry count and time range
        - Agent and outcome breakdown
        - Clear, human-readable summary
        """
        from engine.audit.signer import AuditSigner

        # Fetch entries in chronological order
        result = await self.db.execute(
            select(AuditLog)
            .order_by(AuditLog.timestamp.asc())
            .limit(limit)
        )
        entries = result.scalars().all()

        if not entries:
            return {
                "chain_status": "EMPTY",
                "tamper_detected": False,
                "entries_verified": 0,
                "time_range": None,
                "summary": "No audit entries to verify. Chain is empty.",
                "details": {},
            }

        # Build chain data for verification
        signer = AuditSigner()
        chain_data = []
        for e in entries:
            chain_data.append({
                "entry_id": str(e.entry_id),
                "timestamp": e.timestamp.isoformat(),
                "agent_id": e.agent_id,
                "request_hash": e.request_hash,
                "rulesets_used": e.rulesets_used,
                "detections": e.detections or [],
                "actions_taken": e.actions_taken or [],
                "was_blocked": e.was_blocked,
                "target_url": e.target_url,
                "latency_ms": e.latency_ms,
                "outcome": e.outcome,
                "hmac_signature": e.hmac_signature,
                "prev_entry_hash": e.prev_entry_hash,
            })

        is_valid, error = signer.verify_chain(chain_data)

        # Compute stats
        first_ts = entries[0].timestamp
        last_ts = entries[-1].timestamp
        unique_agents = list(set(e.agent_id for e in entries))
        outcomes = {}
        total_detections = 0
        for e in entries:
            outcomes[e.outcome] = outcomes.get(e.outcome, 0) + 1
            if e.detections:
                total_detections += len(e.detections)

        time_range_seconds = (last_ts - first_ts).total_seconds()

        if is_valid:
            summary = (
                f"✅ Chain INTACT — {len(entries)} entries verified, "
                f"covering {_format_duration(time_range_seconds)}. "
                f"No tampering detected. All HMAC signatures valid."
            )
        else:
            summary = (
                f"🚨 Chain BROKEN — Tampering detected. {error}. "
                f"Checked {len(entries)} entries over "
                f"{_format_duration(time_range_seconds)}."
            )

        return {
            "chain_status": "INTACT" if is_valid else "BROKEN",
            "tamper_detected": not is_valid,
            "tamper_error": error if not is_valid else None,
            "entries_verified": len(entries),
            "time_range": {
                "first_entry": first_ts.isoformat(),
                "last_entry": last_ts.isoformat(),
                "duration_seconds": int(time_range_seconds),
                "duration_human": _format_duration(time_range_seconds),
            },
            "agents": unique_agents,
            "outcomes": outcomes,
            "total_detections": total_detections,
            "summary": summary,
        }


def _format_duration(seconds: float) -> str:
    """Format seconds into a human-readable duration string."""
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    elif seconds < 86400:
        hours = seconds // 3600
        mins = (seconds % 3600) // 60
        return f"{hours}h {mins}m"
    else:
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        return f"{days}d {hours}h"
