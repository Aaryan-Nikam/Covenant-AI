from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import uuid

class PolicyVersionOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    version: int
    policy: dict
    change_summary: Optional[str]
    created_by: str
    created_at: datetime
    is_active: bool
    activated_at: Optional[datetime]
    activated_by: Optional[str]
    superseded_at: Optional[datetime]

    class Config:
        from_attributes = True

class PolicyVersionListItem(BaseModel):
    id: uuid.UUID
    version: int
    change_summary: Optional[str]
    created_by: str
    created_at: datetime
    is_active: bool
    activated_at: Optional[datetime]

    class Config:
        from_attributes = True

class PolicyUpdateRequest(BaseModel):
    policy: dict
    change_summary: Optional[str] = None
