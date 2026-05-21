"""Database models for unified decision logs."""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB

from engine.database.base import Base


class UnifiedDecisionLog(Base):
    """Idempotent decision log for /v1/decisions/evaluate."""

    __tablename__ = "unified_decision_logs"
    __table_args__ = (
        Index("idx_unified_decision_tenant_created", "tenant_id", "created_at"),
        Index("idx_unified_decision_tenant_request", "tenant_id", "request_id", unique=True),
        Index("idx_unified_decision_tenant_outcome", "tenant_id", "outcome"),
        {"schema": "public"},
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), nullable=False)
    request_id = Column(String(128), nullable=False)
    decision_id = Column(String(36), nullable=False)
    outcome = Column(String(32), nullable=False)
    overall_risk_score = Column(Integer, nullable=False, default=0)
    decision_payload = Column(JSONB, nullable=False, default=dict)
    signature = Column(String(128), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

