from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from engine.dependencies import get_db
from engine.dependencies import verify_api_key
from engine.auth.models import Tenant
from engine.agent_security import policy_version_service as svc
from engine.agent_security.policy_version_schemas import (
    PolicyVersionOut, PolicyVersionListItem, PolicyUpdateRequest
)
import uuid

router = APIRouter(prefix='/v1/agent-security/policy', tags=['policy-versions'])


@router.put('', response_model=PolicyVersionOut)
async def update_policy(
    body: PolicyUpdateRequest,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(verify_api_key)
) -> PolicyVersionOut:
    """Create a new policy version and activate it immediately."""
    version = await svc.create_policy_version(
        db=db,
        tenant_id=tenant.id,
        policy=body.policy,
        created_by=str(tenant.id),
        change_summary=body.change_summary,
        activate_immediately=True
    )
    return version


@router.get('', response_model=PolicyVersionOut)
async def get_active_policy(
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(verify_api_key)
) -> PolicyVersionOut:
    """Get the currently active policy version."""
    version = await svc.get_active_policy(db, tenant.id)
    if not version:
        raise HTTPException(status_code=404, detail='No active policy found')
    return version


@router.get('/history', response_model=List[PolicyVersionListItem])
async def list_policy_history(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(verify_api_key)
) -> List[PolicyVersionListItem]:
    """List all policy versions for this tenant, newest first."""
    return await svc.list_policy_versions(db, tenant.id, limit=limit)


@router.get('/{version_id}', response_model=PolicyVersionOut)
async def get_policy_version(
    version_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(verify_api_key)
) -> PolicyVersionOut:
    """Get a specific policy version by ID."""
    from sqlalchemy import select
    from engine.agent_security.policy_version_model import TenantPolicyVersion
    result = await db.execute(
        select(TenantPolicyVersion).where(
            TenantPolicyVersion.id == str(version_id),
            TenantPolicyVersion.tenant_id == str(tenant.id)
        )
    )
    version = result.scalar_one_or_none()
    if not version:
        raise HTTPException(status_code=404, detail='Policy version not found')
    return version


@router.post('/{version_id}/activate', response_model=PolicyVersionOut)
async def activate_policy_version(
    version_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(verify_api_key)
) -> PolicyVersionOut:
    """Activate a specific policy version."""
    try:
        return await svc.activate_policy_version(
            db, tenant.id, version_id, activated_by=str(tenant.id)
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post('/{version_id}/rollback', response_model=PolicyVersionOut)
async def rollback_policy(
    version_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(verify_api_key)
) -> PolicyVersionOut:
    """Roll back to a previous policy version (creates new version with old content)."""
    try:
        return await svc.rollback_to_version(
            db, tenant.id, version_id, rolled_back_by=str(tenant.id)
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
