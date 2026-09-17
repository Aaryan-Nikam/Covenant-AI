"""
Covenant AI — SLA Monitoring Models.

Tables: sla.sla_policy, sla.sla_breach
"""

import uuid
import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from engine.database.base import Base


class MetricType(str, enum.Enum):
    LATENCY_P95 = "LATENCY_P95"
    LATENCY_P99 = "LATENCY_P99"
    ERROR_RATE = "ERROR_RATE"
    BLOCK_RATE = "BLOCK_RATE"
    COST_PER_SESSION = "COST_PER_SESSION"


class SLAPolicy(Base):
    """
    Defines a performance threshold a tenant wants to monitor.
    Evaluation runs every 5 minutes via APScheduler.
    """

    __tablename__ = "sla_policy"
    __table_args__ = (
        Index("idx_sla_policy_tenant", "tenant_id"),
        Index("idx_sla_policy_active", "is_active"),
        {"schema": "sla"},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)

    name = Column(String(128), nullable=False)
    metric_type = Column(String(32), nullable=False)  # MetricType enum value
    threshold_value = Column(Float, nullable=False)
    window_minutes = Column(Integer, nullable=False, default=60)

    notification_email = Column(String(256), nullable=True)
    webhook_url = Column(String(1024), nullable=True)

    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    breaches = relationship("SLABreach", back_populates="policy", lazy="noload")


class SLABreach(Base):
    """
    Records a detected threshold violation for an SLAPolicy.
    A breach is 'open' when resolved_at is null.
    """

    __tablename__ = "sla_breach"
    __table_args__ = (
        Index("idx_sla_breach_policy", "policy_id"),
        Index("idx_sla_breach_tenant", "tenant_id"),
        Index("idx_sla_breach_resolved", "resolved_at"),
        {"schema": "sla"},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)
    policy_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sla.sla_policy.id", ondelete="CASCADE"),
        nullable=False,
    )

    breached_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    metric_value = Column(Float, nullable=False)
    threshold_value = Column(Float, nullable=False)  # Snapshot at breach time

    notification_sent_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    policy = relationship("SLAPolicy", back_populates="breaches")
