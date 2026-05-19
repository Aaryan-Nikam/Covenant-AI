"""
Ironpass — Vault database models.

Schema: vault
Table: vault_tokens

Stores encrypted token-to-value mappings. Every value is AES-256-GCM
encrypted before storage. Encryption keys NEVER stored in this database.

Architecture doc reference: Component 4 — Token Vault, Database Schema.
"""

from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Index,
    LargeBinary,
    String,
)

from engine.database.base import Base


class VaultToken(Base):
    """
    Vault token storage.
    
    Each row maps a token (e.g., TOK_CARD_a4f2b891) to its encrypted value.
    The plaintext is NEVER stored — only the AES-256-GCM ciphertext + nonce.
    
    Permissions (enforced at DB level):
    - App user: SELECT, INSERT only
    - No UPDATE, no DELETE via application code
    - Cleanup of expired tokens via scheduled job only
    """

    __tablename__ = "vault_tokens"
    __table_args__ = (
        Index("idx_vault_expires", "expires_at"),
        Index("idx_vault_agent", "agent_id"),
        # Compound index — all token lookups are scoped to tenant_id.
        # Cross-tenant token access is structurally impossible at the DB layer.
        Index("idx_vault_tenant_token", "tenant_id", "token", unique=True),
        {"schema": "vault"},
    )

    # TOK_{TYPE}_{8_CHAR_HEX} — e.g., TOK_CARD_a4f2b891
    # token is unique WITHIN a tenant, not globally. Two tenants can have
    # the same token string — they will never collide because all lookups
    # are scoped by tenant_id.
    token = Column(String(64), primary_key=True, nullable=False)

    # Tenant that owns this token. All retrieval is scoped to this value.
    # A token belonging to tenant_A cannot be retrieved under tenant_B.
    tenant_id = Column(String(128), primary_key=True, nullable=False, index=True)

    # AES-256-GCM encrypted value (ciphertext + authentication tag)
    ciphertext = Column(LargeBinary, nullable=False)

    # GCM nonce — unique per encryption operation (96 bits / 12 bytes)
    # Critical Rule #12: Fresh os.urandom(12) every call, never reuse
    nonce = Column(LargeBinary, nullable=False)

    # Data classification — credit_card, ssn, person_name, etc.
    data_type = Column(String(64), nullable=False)

    # Agent that created this token — used for authorization on retrieval
    agent_id = Column(String(128), nullable=False)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )
    expires_at = Column(
        DateTime(timezone=True),
        nullable=False,
    )
    invalidated_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Which encryption key version was used — for key rotation support
    key_version = Column(String(32), nullable=False)

    def __repr__(self) -> str:
        return (
            f"<VaultToken(token='{self.token}', "
            f"data_type='{self.data_type}', "
            f"agent_id='{self.agent_id}')>"
        )
