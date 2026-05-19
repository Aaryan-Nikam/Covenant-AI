"""Database models for enterprise Agent Security controls."""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB

from engine.database.base import Base


class AgentSecurityPolicy(Base):
    """Tenant-specific policy profile for the agent security suite."""

    __tablename__ = "agent_security_policies"
    __table_args__ = (
        Index("idx_agent_sec_policy_tenant", "tenant_id", unique=True),
        {"schema": "public"},
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    policy_config = Column("config", JSONB, nullable=False, default=dict)
    updated_by = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class AgentSecurityDecisionLog(Base):
    """Tamper-evident decision record for security evaluations."""

    __tablename__ = "agent_security_decision_logs"
    __table_args__ = (
        Index("idx_agent_sec_decision_tenant_created", "tenant_id", "created_at"),
        Index("idx_agent_sec_decision_tenant_request", "tenant_id", "request_id", unique=True),
        Index("idx_agent_sec_decision_tenant_action", "tenant_id", "action"),
        {"schema": "public"},
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), nullable=False)
    request_id = Column(String(128), nullable=False)
    action = Column(String(32), nullable=False)
    overall_risk_score = Column(Integer, nullable=False, default=0)
    decision_payload = Column(JSONB, nullable=False, default=dict)
    signature = Column(String(128), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
