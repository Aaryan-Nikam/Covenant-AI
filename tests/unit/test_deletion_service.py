import pytest
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

from engine.deletion.models import TenantDeletionJob, TenantDeletionJobStep
from engine.deletion.service import create_deletion_job, run_deletion_job, STEPS

@pytest.fixture
def mock_db():
    db = AsyncMock()
    # Mock execute result
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    
    # For idempotency test
    mock_step_result = MagicMock()
    mock_step = MagicMock()
    mock_step.status = 'completed'
    mock_step_result.scalar_one.return_value = mock_step
    
    db.execute.return_value = mock_result
    return db

@pytest.mark.asyncio
async def test_deletion_job_creates_all_steps(mock_db):
    tenant_id = uuid.uuid4()
    
    job = await create_deletion_job(
        db=mock_db,
        tenant_id=str(tenant_id),
        initiated_by='admin',
        retention_mode='gdpr_erasure'
    )
    
    assert job.tenant_id == str(tenant_id)
    assert job.status == 'pending'
    
    # Assert adds were called
    assert mock_db.add.call_count == 1 + len(STEPS) + 1  # 1 job + 7 steps + 1 audit log
    
@pytest.mark.asyncio
async def test_deletion_job_idempotent_resume(mock_db):
    job_id = uuid.uuid4()
    tenant_id = str(uuid.uuid4())
    
    # Mock db.get for job
    mock_job = MagicMock()
    mock_job.id = job_id
    mock_job.tenant_id = tenant_id
    mock_job.retention_mode = 'gdpr_erasure'
    mock_db.get.return_value = mock_job
    
    # Mock execute to return steps that are already 'completed'
    mock_result = MagicMock()
    mock_step = MagicMock()
    mock_step.status = 'completed'
    mock_result.scalar_one.return_value = mock_step
    mock_db.execute.return_value = mock_result
    
    with patch('engine.deletion.service._execute_step', new_callable=AsyncMock) as mock_exec:
        await run_deletion_job(job_id, mock_db)
        
        # If all steps are already completed, _execute_step shouldn't be called
        assert mock_exec.call_count == 0

@pytest.mark.asyncio
async def test_deletion_job_conflict_rejected(mock_db):
    tenant_id = uuid.uuid4()
    
    # Mock db to return an existing job
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = TenantDeletionJob()
    mock_db.execute.return_value = mock_result
    
    # Attempt to create a second job for same tenant
    with pytest.raises(ValueError, match="Active deletion job already exists"):
        await create_deletion_job(
            db=mock_db,
            tenant_id=str(tenant_id),
            initiated_by='admin',
            retention_mode='gdpr_erasure'
        )
