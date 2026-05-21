from sqlalchemy import Column, Integer, Text, Boolean, DateTime, ForeignKey, Index, UniqueConstraint, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from engine.database.base import Base
from sqlalchemy import text
import uuid

class TenantPolicyVersion(Base):
    __tablename__ = 'tenant_policy_versions'
    __table_args__ = (
        Index(
            'uq_one_active_policy_per_tenant',
            'tenant_id',
            unique=True,
            postgresql_where=text('is_active = true')
        ),
        UniqueConstraint('tenant_id', 'version', name='uq_tenant_policy_version'),
        {'schema': 'public'}
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey('public.tenants.id'), nullable=False)
    version = Column(Integer, nullable=False)
    policy = Column(JSONB, nullable=False)
    change_summary = Column(Text, nullable=True)
    created_by = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    is_active = Column(Boolean, nullable=False, default=False)
    activated_at = Column(DateTime(timezone=True), nullable=True)
    activated_by = Column(Text, nullable=True)
    superseded_at = Column(DateTime(timezone=True), nullable=True)
