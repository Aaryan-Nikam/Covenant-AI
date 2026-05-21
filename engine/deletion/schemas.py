from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import uuid

class DeletionJobCreate(BaseModel):
    retention_mode: str = 'gdpr_erasure'
    # gdpr_erasure: delete everything, redact audit PII
    # legal_hold: delete operational data, preserve audit in full
    # anonymise_only: anonymise tenant record only, retain all data

class DeletionJobStepOut(BaseModel):
    step_name: str
    status: str
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    records_affected: Optional[int]
    detail: Optional[dict]
    error: Optional[str]

    class Config:
        from_attributes = True

class DeletionJobOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    status: str
    current_step: Optional[str]
    retention_mode: str
    initiated_at: datetime
    completed_at: Optional[datetime]
    failure_reason: Optional[str]
    steps: List[DeletionJobStepOut] = []

    class Config:
        from_attributes = True
