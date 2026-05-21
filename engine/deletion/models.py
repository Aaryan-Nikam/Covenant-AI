from sqlalchemy import Column, Text, DateTime, Integer, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from engine.database.base import Base
import uuid

class TenantDeletionJob(Base):
    __tablename__ = 'tenant_deletion_jobs'
    __table_args__ = {'schema': 'public'}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey('public.tenants.id'), nullable=False)
    initiated_by = Column(Text, nullable=False)
    initiated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    status = Column(Text, nullable=False, default='pending')
    current_step = Column(Text, nullable=True)
    failure_reason = Column(Text, nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    retention_mode = Column(Text, nullable=False, default='gdpr_erasure')


class TenantDeletionJobStep(Base):
    __tablename__ = 'tenant_deletion_job_steps'
    __table_args__ = {'schema': 'public'}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String(36),
                    ForeignKey('public.tenant_deletion_jobs.id'), nullable=False)
    step_name = Column(Text, nullable=False)
    status = Column(Text, nullable=False, default='pending')
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    records_affected = Column(Integer, nullable=True)
    detail = Column(JSONB, nullable=True)
    error = Column(Text, nullable=True)
