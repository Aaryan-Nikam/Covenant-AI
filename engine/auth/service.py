"""
Ironpass — Authentication service.

Authenticates incoming API requests by:
1. Hashing the bearer token (SHA-256)
2. Looking up the hash in tenant_api_keys
3. Verifying not revoked, not expired, tenant is active
4. Returning the associated Tenant

Background task updates last_used_at non-blocking.
"""

import logging
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from engine.auth.models import Tenant, TenantAPIKey, hash_api_key

logger = logging.getLogger("ironpass.auth")


async def authenticate_request(
    raw_key: str,
    db: AsyncSession,
) -> Tenant:
    """
    Authenticate a request by its raw API key.

    Raises HTTP 401 for any failure — never reveals the specific reason
    to the caller (prevents oracle attacks).

    Returns the Tenant on success.
    """
    if not raw_key.startswith("dbnc_live_"):
        logger.warning("Auth rejected: invalid key format")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    key_hash = hash_api_key(raw_key)

    # Load the API key and its associated tenant in one query
    result = await db.execute(
        select(TenantAPIKey)
        .options(selectinload(TenantAPIKey.tenant))
        .where(TenantAPIKey.key_hash == key_hash)
    )
    api_key = result.scalar_one_or_none()

    if api_key is None:
        logger.warning(f"Auth rejected: key hash not found (prefix={raw_key[:16]})")
        _raise_401()

    # Check revocation
    if api_key.revoked_at is not None:
        logger.warning(
            f"Auth rejected: key revoked (prefix={api_key.key_prefix}, "
            f"tenant={api_key.tenant_id})"
        )
        _raise_401()

    # Check active flag
    if not api_key.is_active:
        logger.warning(
            f"Auth rejected: key inactive (prefix={api_key.key_prefix})"
        )
        _raise_401()

    # Check expiry
    if api_key.expires_at is not None:
        now = datetime.now(timezone.utc)
        expires = (
            api_key.expires_at.replace(tzinfo=timezone.utc)
            if api_key.expires_at.tzinfo is None
            else api_key.expires_at
        )
        if now > expires:
            logger.warning(
                f"Auth rejected: key expired (prefix={api_key.key_prefix})"
            )
            _raise_401()

    # Check tenant is active
    tenant = api_key.tenant
    if tenant is None or not tenant.is_active:
        logger.warning(f"Auth rejected: tenant inactive (id={api_key.tenant_id})")
        _raise_401()

    logger.debug(
        f"Auth OK: tenant='{tenant.name}' (id={tenant.id}), "
        f"key_prefix={api_key.key_prefix}"
    )

    # Update last_used_at — fire and forget, does not block response
    # We do a simple update without await blocking via background_tasks
    # For simplicity here, we do it inline but with a raw UPDATE (no ORM tracking)
    try:
        await db.execute(
            update(TenantAPIKey)
            .where(TenantAPIKey.id == api_key.id)
            .values(last_used_at=datetime.now(timezone.utc))
        )
        # Flush without commit — the session commits at end of request
    except Exception as e:
        # Never block auth on last_used_at update failure
        logger.warning(f"last_used_at update failed (non-blocking): {e}")

    return tenant


def _raise_401() -> None:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API key",
        headers={"WWW-Authenticate": "Bearer"},
    )
