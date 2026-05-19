"""
Ironpass — Admin API router.

Secured by IRONPASS_ADMIN_SECRET env var (Bearer token).
This is YOUR key — never given to customers.

Endpoints:
    POST   /v1/admin/tenants              — create tenant
    GET    /v1/admin/tenants              — list all tenants
    DELETE /v1/admin/tenants/{id}         — tenant deletion cascade
    POST   /v1/admin/tenants/{id}/keys    — issue new API key
    POST   /v1/admin/tenants/{id}/keys/{key_id}/revoke — revoke a key

Usage (3 curl commands to provision a customer):
    # 1. Create tenant
    curl -X POST https://api.ironpass.io/v1/admin/tenants \\
         -H "Authorization: Bearer $IRONPASS_ADMIN_SECRET" \\
         -H "Content-Type: application/json" \\
         -d '{"name": "Acme Corp", "active_rulesets": ["pci_dss", "hipaa"]}'

    # 2. Issue API key (returns raw key ONCE — store it securely)
    curl -X POST https://api.ironpass.io/v1/admin/tenants/{id}/keys \\
         -H "Authorization: Bearer $IRONPASS_ADMIN_SECRET"

    # 3. Give the raw key to the customer — they set base_url and use it.
"""

import logging
from datetime import datetime, timezone

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from engine.auth.models import (
    Tenant,
    TenantAPIKey,
    generate_api_key,
)
from engine.config import get_settings
from engine.dependencies import get_db
from engine.vault.key_manager import KeyManager
from engine.vault.vault import TokenVault

logger = logging.getLogger("ironpass.admin")

router = APIRouter(prefix="/v1/admin", tags=["admin"])


# ---------------------------------------------------------------------------
# Admin auth dependency
# ---------------------------------------------------------------------------

def verify_admin(authorization: str = Header(...)) -> None:
    """
    Verifies the admin master key.
    Separate from tenant key auth — uses IRONPASS_ADMIN_SECRET env var.
    """
    settings = get_settings()
    expected = f"Bearer {settings.ironpass_admin_secret}"

    if not settings.ironpass_admin_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin API not configured (IRONPASS_ADMIN_SECRET not set)",
        )

    if authorization != expected:
        logger.warning("Admin auth rejected: invalid secret")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials",
        )


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------

class CreateTenantRequest(BaseModel):
    name: str
    active_rulesets: list[str] = ["pci_dss"]


class TenantResponse(BaseModel):
    id: str
    name: str
    active_rulesets: list[str]
    is_active: bool
    created_at: str

    model_config = {"from_attributes": True}


class UpdateTenantRequest(BaseModel):
    name: Optional[str] = None
    active_rulesets: Optional[list[str]] = None


class IssueKeyResponse(BaseModel):
    key_id: str
    raw_key: str        # Returned ONCE — not stored anywhere
    key_prefix: str
    tenant_id: str
    message: str = "Store this key securely. It will not be shown again."


class RevokeKeyRequest(BaseModel):
    reason: str = "manual_revocation"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/tenants", dependencies=[Depends(verify_admin)])
async def create_tenant(
    body: CreateTenantRequest,
    db: AsyncSession = Depends(get_db),
) -> TenantResponse:
    """Create a new tenant. Returns the tenant record."""
    tenant = Tenant(
        name=body.name,
        active_rulesets=body.active_rulesets,
    )
    db.add(tenant)
    await db.flush()  # Get the generated ID before commit
    await db.refresh(tenant)

    logger.info(f"Created tenant: '{tenant.name}' (id={tenant.id})")

    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        active_rulesets=tenant.active_rulesets,
        is_active=tenant.is_active,
        created_at=tenant.created_at.isoformat(),
    )


@router.get("/tenants", dependencies=[Depends(verify_admin)])
async def list_tenants(
    db: AsyncSession = Depends(get_db),
) -> list[TenantResponse]:
    """List all tenants (active and inactive)."""
    result = await db.execute(select(Tenant).order_by(Tenant.created_at.desc()))
    tenants = result.scalars().all()

    return [
        TenantResponse(
            id=t.id,
            name=t.name,
            active_rulesets=t.active_rulesets,
            is_active=t.is_active,
            created_at=t.created_at.isoformat(),
        )
        for t in tenants
    ]


@router.patch("/tenants/{tenant_id}", dependencies=[Depends(verify_admin)])
async def update_tenant(
    tenant_id: str,
    body: UpdateTenantRequest,
    db: AsyncSession = Depends(get_db),
) -> TenantResponse:
    """
    Update a tenant's name and/or active_rulesets in place.
    Vault tokens are preserved — no deletion required.
    """
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()

    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")

    if body.name is not None:
        tenant.name = body.name
    if body.active_rulesets is not None:
        tenant.active_rulesets = body.active_rulesets

    await db.flush()
    await db.refresh(tenant)

    logger.info(
        f"Updated tenant: '{tenant.name}' (id={tenant_id}), "
        f"rulesets={tenant.active_rulesets}"
    )

    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        active_rulesets=tenant.active_rulesets,
        is_active=tenant.is_active,
        created_at=tenant.created_at.isoformat(),
    )


@router.post("/tenants/{tenant_id}/keys", dependencies=[Depends(verify_admin)])
async def issue_api_key(
    tenant_id: str,
    db: AsyncSession = Depends(get_db),
) -> IssueKeyResponse:
    """
    Issue a new API key for a tenant.
    The raw key is returned ONCE — it is not stored anywhere.
    """
    # Verify tenant exists and is active
    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id)
    )
    tenant = result.scalar_one_or_none()

    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    if not tenant.is_active:
        raise HTTPException(status_code=400, detail="Tenant is deactivated")

    raw_key, key_hash, key_prefix = generate_api_key()

    api_key = TenantAPIKey(
        tenant_id=tenant_id,
        key_hash=key_hash,
        key_prefix=key_prefix,
        scope="proxy",
    )
    db.add(api_key)
    await db.flush()
    await db.refresh(api_key)

    logger.info(
        f"Issued API key: prefix={key_prefix}, tenant='{tenant.name}' (id={tenant_id})"
    )

    return IssueKeyResponse(
        key_id=api_key.id,
        raw_key=raw_key,
        key_prefix=key_prefix,
        tenant_id=tenant_id,
    )


@router.post(
    "/tenants/{tenant_id}/keys/{key_id}/revoke",
    dependencies=[Depends(verify_admin)],
)
async def revoke_api_key(
    tenant_id: str,
    key_id: str,
    body: RevokeKeyRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Revoke a specific API key. Key stops working immediately."""
    result = await db.execute(
        select(TenantAPIKey).where(
            TenantAPIKey.id == key_id,
            TenantAPIKey.tenant_id == tenant_id,
        )
    )
    api_key = result.scalar_one_or_none()

    if api_key is None:
        raise HTTPException(status_code=404, detail="Key not found")
    if api_key.revoked_at is not None:
        raise HTTPException(status_code=400, detail="Key already revoked")

    api_key.revoked_at = datetime.now(timezone.utc)
    api_key.is_active = False
    api_key.revoke_reason = body.reason
    await db.flush()

    logger.info(
        f"Revoked key: prefix={api_key.key_prefix}, "
        f"reason='{body.reason}', tenant_id={tenant_id}"
    )
    return {"status": "revoked", "key_id": key_id, "reason": body.reason}


@router.delete("/tenants/{tenant_id}", dependencies=[Depends(verify_admin)])
async def delete_tenant(
    tenant_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Tenant deletion cascade — GDPR Article 17 compliant.

    Order (matters — prevents race conditions):
    1. Revoke all active API keys first (stops new requests immediately)
    2. Vault tokens invalidated separately via TokenVault.invalidate_by_tenant()
       (called by the consumer of this endpoint or as a follow-up step)
    3. Soft-delete audit records (retain chain integrity — just mark deleted)
    4. Mark tenant inactive

    All steps wrapped in the request's DB transaction.
    """
    result = await db.execute(
        select(Tenant)
        .options(selectinload(Tenant.api_keys))
        .where(Tenant.id == tenant_id)
    )
    tenant = result.scalar_one_or_none()

    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")

    now = datetime.now(timezone.utc)

    # Step 1: Revoke all active API keys (stops new requests immediately)
    await db.execute(
        sa_update(TenantAPIKey)
        .where(
            TenantAPIKey.tenant_id == tenant_id,
            TenantAPIKey.revoked_at.is_(None),
        )
        .values(
            revoked_at=now,
            is_active=False,
            revoke_reason="tenant_deleted",
        )
    )

    # Step 2: Invalidate all vault tokens for this tenant
    # Wipes all encrypted PII from the vault — no dangling tokens after offboarding
    try:
        key_manager = KeyManager()
        vault = TokenVault(db_session=db, key_manager=key_manager)
        invalidated_count = await vault.invalidate_by_tenant(
            tenant_id, reason="tenant_deleted"
        )
        logger.info(
            f"Invalidated {invalidated_count} vault tokens for tenant {tenant_id}"
        )
    except Exception as e:
        # Log but don't block the deletion — keys are already revoked
        logger.error(
            f"Vault token invalidation failed for tenant {tenant_id}: {e}. "
            f"Manual cleanup may be required."
        )
        invalidated_count = -1  # -1 signals partial completion

    # Step 3: Mark tenant inactive
    tenant.is_active = False
    tenant.deactivated_at = now
    await db.flush()

    keys_revoked = len([k for k in tenant.api_keys])

    logger.info(
        f"Deleted tenant: '{tenant.name}' (id={tenant_id}), "
        f"revoked {keys_revoked} API keys, "
        f"invalidated {invalidated_count} vault tokens"
    )

    return {
        "status": "deleted",
        "tenant_id": tenant_id,
        "api_keys_revoked": keys_revoked,
        "vault_tokens_invalidated": invalidated_count,
    }
