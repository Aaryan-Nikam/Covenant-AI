"""
Ironpass — Audit log signer (HMAC-SHA256 chain).

Signs each audit entry and chains it to the previous entry,
creating a tamper-evident log. If any entry is modified,
the chain breaks and tampering is detectable.

Architecture doc reference: Component 5 — Audit Logger.
Critical Rule #4: Audit log is append-only.
"""

import hashlib
import hmac
import json
import logging
from datetime import datetime

from engine.config import get_settings

logger = logging.getLogger("ironpass.audit.signer")


class AuditSigner:
    """
    HMAC-SHA256 signer for audit log entries.
    Each entry's signature includes the previous entry's hash,
    creating a blockchain-style chain for tamper detection.
    """

    def __init__(self):
        settings = get_settings()
        self._hmac_key = bytes.fromhex(settings.audit_hmac_key)

    def sign_entry(
        self,
        entry_id: str,
        timestamp: datetime,
        agent_id: str,
        request_hash: str,
        rulesets_used: list[str],
        detections: list[dict],
        actions_taken: list[dict],
        was_blocked: bool,
        target_url: str | None,
        latency_ms: int,
        outcome: str,
        prev_entry_hash: str | None,
    ) -> str:
        """
        Generate HMAC-SHA256 signature for an audit entry.
        The signature covers ALL fields including prev_entry_hash,
        creating the chain link.
        """
        # Canonical JSON representation of the entry
        payload = json.dumps(
            {
                "entry_id": str(entry_id),
                "timestamp": timestamp.isoformat(),
                "agent_id": agent_id,
                "request_hash": request_hash,
                "rulesets_used": sorted(rulesets_used),
                "detections": detections,
                "actions_taken": actions_taken,
                "was_blocked": was_blocked,
                "target_url": target_url,
                "latency_ms": latency_ms,
                "outcome": outcome,
                "prev_entry_hash": prev_entry_hash,
            },
            sort_keys=True,
            separators=(",", ":"),
        )

        signature = hmac.new(
            self._hmac_key,
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return signature

    def compute_entry_hash(self, entry_id: str, signature: str) -> str:
        """
        Compute the hash of an entry for chaining to the next entry.
        Hash = SHA-256(entry_id + signature)
        """
        content = f"{entry_id}:{signature}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def verify_chain(
        self,
        entries: list[dict],
    ) -> tuple[bool, str | None]:
        """
        Verify integrity of a sequence of audit entries.
        Returns (is_valid, error_message).
        If valid, error_message is None.
        """
        prev_hash: str | None = None

        for i, entry in enumerate(entries):
            # Verify chain link
            if entry.get("prev_entry_hash") != prev_hash:
                return False, (
                    f"Chain broken at entry {i} "
                    f"(id={entry.get('entry_id')}): "
                    f"expected prev_hash={prev_hash}, "
                    f"got {entry.get('prev_entry_hash')}"
                )

            # Recompute signature
            expected_sig = self.sign_entry(
                entry_id=entry["entry_id"],
                timestamp=datetime.fromisoformat(entry["timestamp"]),
                agent_id=entry["agent_id"],
                request_hash=entry["request_hash"],
                rulesets_used=entry["rulesets_used"],
                detections=entry["detections"],
                actions_taken=entry["actions_taken"],
                was_blocked=entry["was_blocked"],
                target_url=entry.get("target_url"),
                latency_ms=entry["latency_ms"],
                outcome=entry["outcome"],
                prev_entry_hash=entry.get("prev_entry_hash"),
            )

            if entry.get("hmac_signature") != expected_sig:
                return False, (
                    f"Signature mismatch at entry {i} "
                    f"(id={entry.get('entry_id')}): "
                    f"possible tampering detected"
                )

            # Compute hash for next entry's chain link
            prev_hash = self.compute_entry_hash(
                entry["entry_id"], entry["hmac_signature"]
            )

        return True, None
