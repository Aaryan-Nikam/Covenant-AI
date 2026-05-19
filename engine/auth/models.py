"""
Ironpass — Tenant and TenantAPIKey database models.

Schema: public
Tables: tenants, tenant_api_keys

API keys: raw key is issued ONCE and never stored.
          Only the SHA-256 hash is persisted in this table.
"""

import hashlib
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
)
from sqlalchemy.orm import relationship

from engine.database.base import Base


class Tenant(Base):
    """
    A single customer tenant.

    active_rulesets: JSON list of ruleset IDs active for this tenant.
                     e.g. ["pci_dss", "hipaa"]
    """

    __tablename__ = "tenants"
    __table_args__ = {"schema": "public"}

    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    name = Column(String(255), nullable=False)
    active_rulesets = Column(JSON, nullable=False, default=lambda: ["pci_dss"])
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )
    # Set on DELETE /v1/admin/tenants/{id}
    deactivated_at = Column(DateTime(timezone=True), nullable=True)

    api_keys = relationship(
        "TenantAPIKey",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )

    @property
    def agent_id(self) -> str:
        """
        The agent identifier used for vault token scoping.
        Equal to tenant.id — each tenant is treated as a single agent
        at this stage. Stays consistent with vault isolation.
        """
        return self.id

    def __repr__(self) -> str:
        return f"<Tenant(id='{self.id}', name='{self.name}')>"


class TenantAPIKey(Base):
    """
    A single API key issued to a tenant.

    Raw key is NEVER stored here. Only the SHA-256 hash is persisted.
    key_prefix stores the first 16 chars (e.g. 'dbnc_live_a4f2b8')
    for human identification without exposing the full key.

    Supports:
        - Multiple active keys per tenant (key rotation)
        - Per-key expiry
        - Explicit revocation with reason
        - last_used_at tracking (non-blocking background update)
    """

    __tablename__ = "tenant_api_keys"
    __table_args__ = (
        Index("idx_apikey_hash", "key_hash", unique=True),
        Index("idx_apikey_tenant", "tenant_id"),
        {"schema": "public"},
    )

    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    tenant_id = Column(
        String(36),
        ForeignKey("public.tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    # SHA-256 of the raw key — used for lookup on every request
    key_hash = Column(String(64), nullable=False)
    # Human-readable prefix for identification (first 16 chars of raw key)
    key_prefix = Column(String(20), nullable=False)

    # Scope reserved for future use ("proxy", "read_only", "admin")
    scope = Column(String(64), nullable=False, default="proxy")
    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    # None = never expires
    expires_at = Column(DateTime(timezone=True), nullable=True)
    # Updated as background task on each authenticated request
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    # Revocation
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revoke_reason = Column(String(255), nullable=True)

    tenant = relationship("Tenant", back_populates="api_keys")

    def __repr__(self) -> str:
        return (
            f"<TenantAPIKey(prefix='{self.key_prefix}', "
            f"tenant_id='{self.tenant_id}', active={self.is_active})>"
        )


def generate_api_key() -> tuple[str, str, str]:
    """
    Generate a new raw API key.

    Returns:
        (raw_key, key_hash, key_prefix)

    raw_key   — returned to the caller ONCE, never stored
    key_hash  — SHA-256 hex, stored in DB
    key_prefix — first 16 chars, stored for human identification
    """
    raw_key = "dbnc_live_" + uuid.uuid4().hex + uuid.uuid4().hex[:6]
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    key_prefix = raw_key[:16]
    return raw_key, key_hash, key_prefix


def hash_api_key(raw_key: str) -> str:
    """Hash a raw API key for DB lookup."""
    return hashlib.sha256(raw_key.encode()).hexdigest()
