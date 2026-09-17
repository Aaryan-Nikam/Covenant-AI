"""
Ironpass — GDPR Database Models.

Schema: gdpr
Tables: pii_data_record, erasure_request
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import UUID

from engine.database.base import Base


class PiiDataRecord(Base):
    """
    Tracks instances of PII passing through the proxy.
    Used for generating Data Maps and processing Erasure Requests.
    """

    __tablename__ = "pii_data_record"
    __table_args__ = (
        Index("idx_pii_tenant", "tenant_id"),
        Index("idx_pii_subject", "data_subject_id"),
        Index("idx_pii_retention", "retention_until"),
        {"schema": "gdpr"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)
    audit_log_id = Column(BigInteger, nullable=False) # Not strict FK to allow partitioned audit logs
    
    entity_type = Column(String(64), nullable=False) # e.g. 'PERSON', 'EMAIL'
    masked_value = Column(String(256), nullable=True) # Set to null upon erasure
    processing_purpose = Column(String(256), nullable=False)
    legal_basis = Column(String(64), nullable=False)
    
    data_subject_id = Column(String(128), nullable=False) # hashed identifier
    
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )
    retention_until = Column(
        DateTime(timezone=True),
        nullable=False,
    )


class ErasureRequest(Base):
    """
    Tracks data subject deletion requests ("Right to be Forgotten").
    """

    __tablename__ = "erasure_request"
    __table_args__ = (
        Index("idx_erasure_tenant", "tenant_id"),
        Index("idx_erasure_status", "status"),
        {"schema": "gdpr"},
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id = Column(UUID(as_uuid=True), nullable=False)
    data_subject_id = Column(String(128), nullable=False) # hashed identifier
    
    status = Column(String(32), nullable=False, default="pending") # pending, processing, completed, failed
    records_deleted = Column(Integer, nullable=False, default=0)
    
    requested_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )
    completed_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )
