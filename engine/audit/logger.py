"""
Ironpass — Audit Logger.

Append-only, cryptographically signed audit trail.
Every proxy request generates an entry regardless of outcome.

Critical Rule #4: Append-only — INSERT and SELECT only. No UPDATE. No DELETE.
Critical Rule #6: Audit writes are background tasks — never block proxy response.

Architecture doc reference: Component 5 — Audit Logger.
"""

import hashlib
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from engine.audit.models import AuditLog
from engine.audit.signer import AuditSigner
from engine.detection.models import ActionTaken, Detection

logger = logging.getLogger("ironpass.audit")


class AuditLogger:
    """
    Append-only audit logger with HMAC-SHA256 chain integrity.
    Every request is logged regardless of outcome.
    Audit writes are background tasks — never block the proxy response.
    """

    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.signer = AuditSigner()

    async def log_request(
        self,
        agent_id: str,
        request_content: str,
        rulesets_used: list[str],
        detections: list[Detection],
        actions_taken: list[ActionTaken],
        was_blocked: bool,
        target_url: str | None,
        latency_ms: int,
        outcome: str,
    ) -> str:
        """
        Log a proxy request to the audit trail.
        Returns the entry_id.

        Flow:
        1. Hash the request content (SHA-256)
        2. Strip raw values from detections (store type + position only)
        3. Get previous entry hash for chaining
        4. Sign the entry with HMAC-SHA256
        5. INSERT into audit_log
        """
        entry_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        # Hash the sanitized request content
        request_hash = hashlib.sha256(
            request_content.encode("utf-8")
        ).hexdigest()

        # Strip raw values from detections for audit
        # (we log data_type + position, NEVER the raw value)
        audit_detections = [
            {
                "detector_id": d.detector_id,
                "data_type": d.data_type,
                "position": list(d.position),
                "confidence": d.confidence,
                "layer": d.layer,
                "ruleset_id": d.ruleset_id,
            }
            for d in detections
        ]

        # Convert actions to dicts
        audit_actions = [
            {
                "detector_id": a.detector_id,
                "data_type": a.data_type,
                "action": a.action,
                "original_position": list(a.original_position),
                "ruleset_id": a.ruleset_id,
                "log_level": a.log_level,
            }
            for a in actions_taken
        ]

        # Get previous entry hash for chain
        prev_entry_hash = await self._get_last_entry_hash()

        # Sign the entry
        signature = self.signer.sign_entry(
            entry_id=str(entry_id),
            timestamp=now,
            agent_id=agent_id,
            request_hash=request_hash,
            rulesets_used=rulesets_used,
            detections=audit_detections,
            actions_taken=audit_actions,
            was_blocked=was_blocked,
            target_url=target_url,
            latency_ms=latency_ms,
            outcome=outcome,
            prev_entry_hash=prev_entry_hash,
        )

        # Create the audit entry
        entry = AuditLog(
            entry_id=entry_id,
            timestamp=now,
            agent_id=agent_id,
            request_hash=request_hash,
            rulesets_used=rulesets_used,
            detections=audit_detections,
            actions_taken=audit_actions,
            was_blocked=was_blocked,
            target_url=target_url,
            latency_ms=latency_ms,
            outcome=outcome,
            hmac_signature=signature,
            prev_entry_hash=prev_entry_hash,
            created_at=now,
        )

        self.db.add(entry)
        await self.db.flush()

        logger.info(
            f"Audit logged: {entry_id} | agent={agent_id} | "
            f"outcome={outcome} | detections={len(detections)} | "
            f"latency={latency_ms}ms"
        )

        return str(entry_id)

    async def _get_last_entry_hash(self) -> str | None:
        """
        Get the hash of the most recent audit entry for chaining.
        Returns None if this is the first entry (genesis).
        """
        result = await self.db.execute(
            select(AuditLog.entry_id, AuditLog.hmac_signature)
            .order_by(desc(AuditLog.id))
            .limit(1)
        )
        row = result.first()

        if row is None:
            return None

        return self.signer.compute_entry_hash(
            str(row.entry_id), row.hmac_signature
        )

    async def verify_chain_integrity(
        self, limit: int = 100
    ) -> tuple[bool, str | None]:
        """
        Verify the integrity of the last N audit entries.
        Returns (is_valid, error_message).
        """
        result = await self.db.execute(
            select(AuditLog)
            .order_by(AuditLog.id.asc())
            .limit(limit)
        )
        entries = result.scalars().all()

        if not entries:
            return True, None

        entry_dicts = [
            {
                "entry_id": str(e.entry_id),
                "timestamp": e.timestamp.isoformat(),
                "agent_id": e.agent_id,
                "request_hash": e.request_hash,
                "rulesets_used": e.rulesets_used,
                "detections": e.detections,
                "actions_taken": e.actions_taken,
                "was_blocked": e.was_blocked,
                "target_url": e.target_url,
                "latency_ms": e.latency_ms,
                "outcome": e.outcome,
                "hmac_signature": e.hmac_signature,
                "prev_entry_hash": e.prev_entry_hash,
            }
            for e in entries
        ]

        return self.signer.verify_chain(entry_dicts)
