"""
Ironpass — Audit log database models.

Schema: audit
Table: audit_log

Append-only, cryptographically signed audit trail. Every proxy request
generates an entry regardless of outcome. Entries are chained via
HMAC-SHA256 for tamper detection.

Architecture doc reference: Component 5 — Audit Logger, Database Schema.

Critical Rules:
  #4: Audit log is append-only — INSERT and SELECT only, no UPDATE/DELETE
  #6: Audit writes are background tasks — never block proxy response
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

from engine.database.base import Base


class AuditLog(Base):
    """
    Immutable audit log entry.
    
    Permissions (enforced at DB level):
    - App user: INSERT, SELECT only
    - REVOKE UPDATE, DELETE — enforced by DB role, not just application code
    
    Chain integrity:
    - hmac_signature: HMAC-SHA256 of this entry's content
    - prev_entry_hash: Hash of the previous entry (blockchain-style chain)
    - Tampering with any entry breaks the chain and is detectable
    """

    __tablename__ = "audit_log"
    __table_args__ = (
        Index("idx_audit_agent", "agent_id", "timestamp"),
        Index("idx_audit_outcome", "outcome", "timestamp"),
        # GIN index for array column (rulesets_used)
        Index("idx_audit_rulesets", "rulesets_used", postgresql_using="gin"),
        {"schema": "audit"},
    )

    # Auto-incrementing primary key
    id = Column(BigInteger, primary_key=True, autoincrement=True)

    # Unique entry identifier
    entry_id = Column(
        UUID(as_uuid=True),
        unique=True,
        nullable=False,
        default=uuid.uuid4,
    )

    # When this entry was created
    timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )

    # Which agent made the request
    agent_id = Column(String(128), nullable=False)

    # SHA-256 hash of the sanitized request content
    request_hash = Column(String(64), nullable=False)

    # Which rulesets were applied — e.g., ["pci_dss", "hipaa"]
    rulesets_used = Column(ARRAY(Text), nullable=False)

    # List of Detection objects (stripped of raw values — type + position only)
    detections = Column(JSONB, nullable=False)

    # List of ActionTaken objects
    actions_taken = Column(JSONB, nullable=False)

    # Whether the request was blocked
    was_blocked = Column(Boolean, nullable=False, default=False)

    # Target URL the request was forwarded to (None if blocked)
    target_url = Column(String(512), nullable=True)

    # Pipeline latency in milliseconds
    latency_ms = Column(Integer, nullable=False)

    # Outcome: "passed", "blocked", or "error"
    outcome = Column(String(32), nullable=False)

    # HMAC-SHA256 signature of this entry's content
    hmac_signature = Column(String(128), nullable=False)

    # Hash of the previous audit entry (chain link)
    prev_entry_hash = Column(String(128), nullable=True)

    # Record creation timestamp (separate from request timestamp)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog(entry_id='{self.entry_id}', "
            f"agent_id='{self.agent_id}', "
            f"outcome='{self.outcome}')>"
        )
