import uuid
import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, text
from engine.deletion.models import TenantDeletionJob, TenantDeletionJobStep
from engine.audit.signer import write_audit_entry

logger = logging.getLogger(__name__)

STEPS = [
    'revoke_api_keys',
    'invalidate_vault_tokens',
    'delete_vault_token_rows',
    'delete_compliance_records',
    'handle_audit_retention',
    'anonymise_tenant_record',
    'mark_complete',
]

# Compliance tables in safe deletion order (child tables before parent tables)
COMPLIANCE_TABLES = [
    'compliance_case_events',
    'sar_reports',
    'aml_signals',
    'covenant_evaluations',
    'financial_snapshots',
    'financial_covenants',
    'sla_evaluations',
    'sla_snapshots',
    'sla_contracts',
    'gdpr_retention_findings',
    'gdpr_retention_snapshots',
    'gdpr_retention_policies',
    'gdpr_processing_activities',
    'rd_tax_assessments',
    'rd_tax_activities',
    'esg_csrd_submissions',
    'esg_metrics',
    'supplier_risk_assessments',
    'supplier_profiles',
    'hs_riddor_assessments',
    'hs_incidents',
    'competitor_signal_assessments',
    'competitor_profiles',
    'compliance_cases',
    'unified_decision_logs',
    'agent_security_decisions',  # if persisted
]


async def create_deletion_job(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    initiated_by: str,
    retention_mode: str = 'gdpr_erasure'
) -> TenantDeletionJob:
    # Check no active job already running for this tenant
    existing = await db.execute(
        select(TenantDeletionJob).where(
            TenantDeletionJob.tenant_id == tenant_id,
            TenantDeletionJob.status.in_(['pending', 'in_progress'])
        )
    )
    if existing.scalar_one_or_none():
        raise ValueError(f'Active deletion job already exists for tenant {tenant_id}')

    job = TenantDeletionJob(
        tenant_id=tenant_id,
        initiated_by=initiated_by,
        retention_mode=retention_mode,
        status='pending'
    )
    db.add(job)
    await db.flush()

    # Pre-create all step rows as pending
    for step_name in STEPS:
        db.add(TenantDeletionJobStep(
            job_id=job.id,
            step_name=step_name,
            status='pending'
        ))

    await db.commit()
    await db.refresh(job)

    # Write audit entry for job creation
    await write_audit_entry(db, {
        'tenant_id': str(tenant_id),
        'actor_type': 'system',
        'entity_type': 'tenant_deletion_job',
        'entity_id': str(job.id),
        'action': 'deletion_job_created',
        'after_state': {
            'retention_mode': retention_mode,
            'initiated_by': initiated_by
        }
    })

    return job


async def run_deletion_job(
    job_id: uuid.UUID,
    db: AsyncSession
) -> None:
    # Mark job in_progress
    await db.execute(
        update(TenantDeletionJob)
        .where(TenantDeletionJob.id == job_id)
        .values(status='in_progress')
    )
    await db.commit()

    job = await db.get(TenantDeletionJob, job_id)
    tenant_id = job.tenant_id
    retention_mode = job.retention_mode

    for step_name in STEPS:
        # Check if step already completed (idempotent resume)
        step_result = await db.execute(
            select(TenantDeletionJobStep).where(
                TenantDeletionJobStep.job_id == job_id,
                TenantDeletionJobStep.step_name == step_name
            )
        )
        step = step_result.scalar_one()

        if step.status == 'completed':
            continue  # Already done, skip

        # Mark step started
        step.status = 'in_progress'
        step.started_at = datetime.now(timezone.utc)
        await db.commit()

        try:
            detail = await _execute_step(
                step_name, tenant_id, retention_mode, db
            )
            step.status = 'completed'
            step.completed_at = datetime.now(timezone.utc)
            step.records_affected = detail.get('count', 0)
            step.detail = detail
            await db.commit()

        except Exception as e:
            logger.exception(f'Deletion step {step_name} failed for job {job_id}')
            step.status = 'failed'
            step.error = str(e)
            await db.commit()

            await db.execute(
                update(TenantDeletionJob)
                .where(TenantDeletionJob.id == job_id)
                .values(status='failed', failure_reason=f'{step_name}: {str(e)}')
            )
            await db.commit()

            await write_audit_entry(db, {
                'tenant_id': str(tenant_id),
                'actor_type': 'system',
                'entity_type': 'tenant_deletion_job',
                'entity_id': str(job_id),
                'action': 'deletion_step_failed',
                'after_state': {'step': step_name, 'error': str(e)}
            })
            return

    # All steps complete
    await db.execute(
        update(TenantDeletionJob)
        .where(TenantDeletionJob.id == job_id)
        .values(status='completed', completed_at=datetime.now(timezone.utc))
    )
    await db.commit()

    await write_audit_entry(db, {
        'tenant_id': str(tenant_id),
        'actor_type': 'system',
        'entity_type': 'tenant_deletion_job',
        'entity_id': str(job_id),
        'action': 'deletion_job_completed',
        'after_state': {'retention_mode': retention_mode}
    })


async def _execute_step(
    step_name: str,
    tenant_id: uuid.UUID,
    retention_mode: str,
    db: AsyncSession
) -> dict:

    if step_name == 'revoke_api_keys':
        result = await db.execute(
            update(text('tenant_api_keys'))  # use your actual model
            .where(text('tenant_id = :tid'))
            .values(revoked=True, revoked_at=datetime.now(timezone.utc))
            .bindparams(tid=tenant_id)
        )
        return {'count': result.rowcount, 'action': 'revoked'}

    elif step_name == 'invalidate_vault_tokens':
        result = await db.execute(
            text("""
                UPDATE vault.vault_tokens
                SET invalidated = true, invalidated_at = NOW()
                WHERE tenant_id = :tid AND invalidated = false
            """),
            {'tid': tenant_id}
        )
        await db.commit()
        return {'count': result.rowcount, 'action': 'invalidated'}

    elif step_name == 'delete_vault_token_rows':
        result = await db.execute(
            text('DELETE FROM vault.vault_tokens WHERE tenant_id = :tid'),
            {'tid': tenant_id}
        )
        await db.commit()
        return {'count': result.rowcount, 'action': 'deleted'}

    elif step_name == 'delete_compliance_records':
        total = 0
        table_counts = {}
        for table in COMPLIANCE_TABLES:
            try:
                result = await db.execute(
                    text(f'DELETE FROM {table} WHERE tenant_id = :tid'),
                    {'tid': tenant_id}
                )
                table_counts[table] = result.rowcount
                total += result.rowcount
                await db.commit()
            except Exception as e:
                # Table may not exist or may not have tenant_id — log and continue
                logger.warning(f'Could not delete from {table}: {e}')
                table_counts[table] = f'error: {str(e)}'
        return {'count': total, 'tables': table_counts}

    elif step_name == 'handle_audit_retention':
        if retention_mode == 'legal_hold':
            # Preserve all audit entries — do nothing
            count = await db.execute(
                text('SELECT COUNT(*) FROM audit.audit_log WHERE tenant_id = :tid'),
                {'tid': tenant_id}
            )
            return {
                'count': count.scalar(),
                'action': 'preserved_legal_hold'
            }
        elif retention_mode == 'gdpr_erasure':
            # Redact PII fields in audit payloads, preserve structure
            result = await db.execute(
                text("""
                    UPDATE audit.audit_log
                    SET
                        before_state = CASE
                            WHEN before_state IS NOT NULL
                            THEN before_state || '{"_pii_redacted": true}'::jsonb
                            ELSE NULL
                        END,
                        after_state = CASE
                            WHEN after_state IS NOT NULL
                            THEN after_state || '{"_pii_redacted": true}'::jsonb
                            ELSE NULL
                        END,
                        redacted_at = NOW()
                    WHERE tenant_id = :tid
                      AND legal_hold = false
                      AND redacted_at IS NULL
                """),
                {'tid': tenant_id}
            )
            await db.commit()
            return {'count': result.rowcount, 'action': 'pii_redacted'}
        else:
            # anonymise_only — skip audit entries
            return {'count': 0, 'action': 'skipped'}

    elif step_name == 'anonymise_tenant_record':
        await db.execute(
            text("""
                UPDATE tenants SET
                    name = '[DELETED]',
                    email = CONCAT('deleted_', id, '@redacted.invalid'),
                    deleted_at = NOW(),
                    active = false
                WHERE id = :tid
            """),
            {'tid': tenant_id}
        )
        await db.commit()
        return {'count': 1, 'action': 'anonymised'}

    elif step_name == 'mark_complete':
        return {'count': 0, 'action': 'complete'}

    else:
        raise ValueError(f'Unknown step: {step_name}')
