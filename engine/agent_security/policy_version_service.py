import uuid
import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from engine.agent_security.policy_version_model import TenantPolicyVersion
from engine.audit.signer import write_audit_entry

logger = logging.getLogger(__name__)


async def get_next_version_number(
    db: AsyncSession,
    tenant_id: uuid.UUID
) -> int:
    result = await db.execute(
        select(func.max(TenantPolicyVersion.version))
        .where(TenantPolicyVersion.tenant_id == str(tenant_id))
    )
    current_max = result.scalar_one_or_none()
    return (current_max or 0) + 1


async def create_policy_version(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    policy: dict,
    created_by: str,
    change_summary: str | None = None,
    activate_immediately: bool = True
) -> TenantPolicyVersion:
    now = datetime.now(timezone.utc)
    next_version = await get_next_version_number(db, tenant_id)

    new_version = TenantPolicyVersion(
        tenant_id=str(tenant_id),
        version=next_version,
        policy=policy,
        change_summary=change_summary,
        created_by=created_by,
        is_active=False  # always start inactive; activate in separate step
    )
    db.add(new_version)
    await db.flush()  # get the id before activation

    if activate_immediately:
        await _activate_version(db, tenant_id, new_version.id, activated_by=created_by, now=now)

    await db.commit()
    await db.refresh(new_version)

    await write_audit_entry(db, {
        'tenant_id': str(tenant_id),
        'actor_type': 'system',
        'entity_type': 'tenant_policy_version',
        'entity_id': str(new_version.id),
        'action': 'policy_version_created',
        'after_state': {
            'version': next_version,
            'activated': activate_immediately,
            'change_summary': change_summary
        }
    })

    return new_version


async def activate_policy_version(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    version_id: uuid.UUID,
    activated_by: str
) -> TenantPolicyVersion:
    # Verify version belongs to this tenant
    version = await db.get(TenantPolicyVersion, str(version_id))
    if not version or str(version.tenant_id) != str(tenant_id):
        raise ValueError('Policy version not found')
    if version.is_active:
        return version  # Already active — idempotent

    now = datetime.now(timezone.utc)
    await _activate_version(db, tenant_id, version_id, activated_by=activated_by, now=now)
    await db.commit()
    await db.refresh(version)

    await write_audit_entry(db, {
        'tenant_id': str(tenant_id),
        'actor_type': 'system',
        'entity_type': 'tenant_policy_version',
        'entity_id': str(version_id),
        'action': 'policy_version_activated',
        'after_state': {
            'version': version.version,
            'activated_by': activated_by
        }
    })

    return version


async def _activate_version(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    version_id: uuid.UUID,
    activated_by: str,
    now: datetime
) -> None:
    # Supersede the currently active version
    await db.execute(
        update(TenantPolicyVersion)
        .where(
            TenantPolicyVersion.tenant_id == str(tenant_id),
            TenantPolicyVersion.is_active == True
        )
        .values(
            is_active=False,
            superseded_at=now
        )
    )

    # Activate the new version
    await db.execute(
        update(TenantPolicyVersion)
        .where(TenantPolicyVersion.id == str(version_id))
        .values(
            is_active=True,
            activated_at=now,
            activated_by=activated_by
        )
    )


async def _get_legacy_policy(db: AsyncSession, tenant_id: uuid.UUID) -> dict | None:
    from engine.agent_security.models import AgentSecurityPolicy
    result = await db.execute(
        select(AgentSecurityPolicy)
        .where(AgentSecurityPolicy.tenant_id == str(tenant_id))
    )
    legacy = result.scalar_one_or_none()
    return legacy.policy_config if legacy else None


async def get_active_policy(
    db: AsyncSession,
    tenant_id: uuid.UUID
) -> TenantPolicyVersion | None:
    result = await db.execute(
        select(TenantPolicyVersion)
        .where(
            TenantPolicyVersion.tenant_id == str(tenant_id),
            TenantPolicyVersion.is_active == True
        )
    )
    version = result.scalar_one_or_none()

    if not version:
        # Fallback: seed from existing policy model
        existing = await _get_legacy_policy(db, tenant_id)
        if existing:
            version = await create_policy_version(
                db=db,
                tenant_id=tenant_id,
                policy=existing,
                created_by='system_migration',
                change_summary='Auto-seeded from legacy policy on first access',
                activate_immediately=True
            )

    return version


async def list_policy_versions(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    limit: int = 20
) -> list[TenantPolicyVersion]:
    result = await db.execute(
        select(TenantPolicyVersion)
        .where(TenantPolicyVersion.tenant_id == str(tenant_id))
        .order_by(TenantPolicyVersion.version.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def rollback_to_version(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    version_id: uuid.UUID,
    rolled_back_by: str
) -> TenantPolicyVersion:
    target = await db.get(TenantPolicyVersion, str(version_id))
    if not target or str(target.tenant_id) != str(tenant_id):
        raise ValueError('Policy version not found')
    if target.is_active:
        raise ValueError('Version is already active')

    # Create a new version with the old policy content
    # Don't just re-activate the old version — preserve the linear history
    rolled_back = await create_policy_version(
        db=db,
        tenant_id=tenant_id,
        policy=target.policy,
        created_by=rolled_back_by,
        change_summary=f'Rollback to version {target.version}',
        activate_immediately=True
    )

    await write_audit_entry(db, {
        'tenant_id': str(tenant_id),
        'actor_type': 'system',
        'entity_type': 'tenant_policy_version',
        'entity_id': str(rolled_back.id),
        'action': 'policy_version_rollback',
        'after_state': {
            'new_version': rolled_back.version,
            'rolled_back_from_version': target.version,
            'rolled_back_by': rolled_back_by
        }
    })

    return rolled_back
