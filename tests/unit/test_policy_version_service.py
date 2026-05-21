import pytest
import uuid
from datetime import datetime, timezone
from sqlalchemy import select, text
from engine.agent_security.policy_version_model import TenantPolicyVersion
from engine.agent_security.policy_version_service import (
    create_policy_version,
    activate_policy_version,
    rollback_to_version
)
from engine.database.connection import init_db, get_session_factory, close_db
import pytest_asyncio


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_database():
    await init_db()
    yield
    await close_db()

@pytest_asyncio.fixture
async def db_session():
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session

@pytest_asyncio.fixture
async def setup_test_tenant(db_session):
    from sqlalchemy import text
    from engine.auth.models import Tenant
    tenant_id = str(uuid.uuid4())
    await db_session.execute(
        text("INSERT INTO public.tenants (id, name, active_rulesets, is_active, created_at) VALUES (:id, 'Test Tenant', '[]'::json, true, now()) ON CONFLICT DO NOTHING"),
        {"id": tenant_id}
    )
    await db_session.commit()
    from types import SimpleNamespace
    return SimpleNamespace(id=tenant_id)

@pytest.mark.asyncio
async def test_create_policy_version_increments_version_number(db_session, setup_test_tenant):
    tenant_id = setup_test_tenant.id
    
    # Create v1
    v1 = await create_policy_version(
        db=db_session,
        tenant_id=tenant_id,
        policy={"rules": ["v1"]},
        created_by="admin1"
    )
    assert v1.version == 1
    
    # Create v2
    v2 = await create_policy_version(
        db=db_session,
        tenant_id=tenant_id,
        policy={"rules": ["v2"]},
        created_by="admin2"
    )
    assert v2.version == 2

@pytest.mark.asyncio
async def test_only_one_active_version_per_tenant(db_session, setup_test_tenant):
    tenant_id = setup_test_tenant.id
    
    # Create v1 (active)
    v1 = await create_policy_version(
        db=db_session,
        tenant_id=tenant_id,
        policy={"rules": ["v1"]},
        created_by="admin1",
        activate_immediately=True
    )
    
    # Create v2 (active)
    v2 = await create_policy_version(
        db=db_session,
        tenant_id=tenant_id,
        policy={"rules": ["v2"]},
        created_by="admin1",
        activate_immediately=True
    )
    
    # Refresh v1
    await db_session.refresh(v1)
    
    assert v1.is_active is False
    assert v1.superseded_at is not None
    assert v2.is_active is True

@pytest.mark.asyncio
async def test_rollback_creates_new_version(db_session, setup_test_tenant):
    tenant_id = setup_test_tenant.id
    
    # Create v1
    v1 = await create_policy_version(
        db=db_session, tenant_id=tenant_id, policy={"p": "v1"}, created_by="admin", activate_immediately=True
    )
    # Create v2
    v2 = await create_policy_version(
        db=db_session, tenant_id=tenant_id, policy={"p": "v2"}, created_by="admin", activate_immediately=True
    )
    # Create v3
    v3 = await create_policy_version(
        db=db_session, tenant_id=tenant_id, policy={"p": "v3"}, created_by="admin", activate_immediately=True
    )
    
    # Rollback to v1
    v4 = await rollback_to_version(
        db=db_session,
        tenant_id=tenant_id,
        version_id=v1.id,
        rolled_back_by="admin2"
    )
    
    assert v4.version == 4
    assert v4.policy == {"p": "v1"}
    assert "Rollback to version 1" in v4.change_summary
    assert v4.is_active is True
    
    await db_session.refresh(v3)
    assert v3.is_active is False

@pytest.mark.asyncio
async def test_activate_already_active_is_idempotent(db_session, setup_test_tenant):
    tenant_id = setup_test_tenant.id
    
    # Create v1 (active)
    v1 = await create_policy_version(
        db=db_session, tenant_id=tenant_id, policy={"p": "v1"}, created_by="admin", activate_immediately=True
    )
    assert v1.is_active is True
    
    # Call activate again
    v1_re = await activate_policy_version(
        db=db_session, tenant_id=tenant_id, version_id=v1.id, activated_by="admin2"
    )
    assert v1_re.is_active is True

@pytest.mark.asyncio
async def test_database_enforces_single_active_policy(db_session, setup_test_tenant):
    import sqlalchemy.exc
    tenant_id = setup_test_tenant.id
    
    # Insert first active policy
    await db_session.execute(
        text("INSERT INTO public.tenant_policy_versions (id, tenant_id, version, policy, created_by, is_active) VALUES (:id, :t, 1, '{}', 'a', true)"),
        {"id": str(uuid.uuid4()), "t": tenant_id}
    )
    await db_session.commit()
    
    # Attempt to directly INSERT a second row with is_active=True
    with pytest.raises(sqlalchemy.exc.IntegrityError):
        await db_session.execute(
            text("INSERT INTO public.tenant_policy_versions (id, tenant_id, version, policy, created_by, is_active) VALUES (:id2, :t, 2, '{}', 'a', true)"),
            {"id2": str(uuid.uuid4()), "t": tenant_id}
        )
        await db_session.commit()
    await db_session.rollback()
