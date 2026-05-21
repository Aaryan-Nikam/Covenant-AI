from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from engine.dependencies import get_db
from engine.admin.router import verify_admin
from engine.deletion import service
from engine.deletion.models import TenantDeletionJob, TenantDeletionJobStep
from engine.deletion.schemas import DeletionJobCreate, DeletionJobOut
import uuid

router = APIRouter(prefix='/v1/admin/tenants', tags=['deletion'])


@router.post('/{tenant_id}/delete', status_code=202)
async def initiate_tenant_deletion(
    tenant_id: uuid.UUID,
    body: DeletionJobCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_admin)
) -> dict:
    try:
        job = await service.create_deletion_job(
            db=db,
            tenant_id=tenant_id,
            initiated_by='admin',
            retention_mode=body.retention_mode
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    background_tasks.add_task(
        service.run_deletion_job,
        job_id=job.id,
        db=db
    )

    return {
        'deletion_job_id': str(job.id),
        'status': 'pending',
        'message': 'Deletion job queued. Poll status endpoint for progress.'
    }


@router.get('/{tenant_id}/delete/{job_id}', response_model=DeletionJobOut)
async def get_deletion_job_status(
    tenant_id: uuid.UUID,
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_admin)
) -> DeletionJobOut:
    job = await db.get(TenantDeletionJob, job_id)
    if not job or job.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail='Deletion job not found')

    steps_result = await db.execute(
        select(TenantDeletionJobStep)
        .where(TenantDeletionJobStep.job_id == job_id)
        .order_by(TenantDeletionJobStep.id)
    )
    steps = steps_result.scalars().all()

    return DeletionJobOut(
        id=job.id,
        tenant_id=job.tenant_id,
        status=job.status,
        current_step=job.current_step,
        retention_mode=job.retention_mode,
        initiated_at=job.initiated_at,
        completed_at=job.completed_at,
        failure_reason=job.failure_reason,
        steps=[s for s in steps]
    )
