"""
Ironpass — FastAPI dependency injection.

All shared dependencies are defined here and injected via FastAPI's
Depends() mechanism. Components never instantiate their own dependencies.
"""

from dataclasses import dataclass
from secrets import compare_digest
from typing import AsyncGenerator

import httpx
from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from engine.config import Settings, get_settings
from engine.database.connection import get_session_factory
from engine.detection.engine import DetectionEngine
from engine.proxy.forwarder import OpenAIForwarder
from engine.proxy.interceptor import ProxyInterceptor
from engine.rulesets.registry import RulesetRegistry


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Yields an async database session.
    Auto-commits on success, rolls back on exception.
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_config() -> Settings:
    """Returns the cached settings singleton."""
    return get_settings()


from fastapi import Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from engine.auth.models import Tenant
from engine.auth.service import authenticate_request

security = HTTPBearer()

def _require_bearer_token(
    credentials: HTTPAuthorizationCredentials | None,
) -> str:
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Missing bearer token")

    return credentials.credentials


def _require_configured_token(
    provided_token: str,
    configured_token: str | None,
    *,
    missing_detail: str,
    invalid_detail: str,
) -> None:
    if not configured_token:
        raise HTTPException(status_code=503, detail=missing_detail)

    if not compare_digest(provided_token, configured_token):
        raise HTTPException(status_code=401, detail=invalid_detail)


async def verify_api_key(
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: AsyncSession = Depends(get_db),
) -> Tenant:
    """
    Authenticates the request by hashing the bearer token and looking
    it up in the tenant_api_keys table. Returns the associated Tenant.

    Raises HTTP 401 for any invalid/expired/revoked key.
    """
    return await authenticate_request(raw_key=credentials.credentials, db=db)


async def verify_dashboard_api_key(
    credentials: HTTPAuthorizationCredentials | None = Security(security),
    settings: Settings = Depends(get_config),
) -> None:
    """Verifies the exact bearer token required for dashboard access."""
    token = _require_bearer_token(credentials)
    _require_configured_token(
        token,
        settings.dashboard_api_key,
        missing_detail="Ironpass dashboard API key is not configured",
        invalid_detail="Invalid dashboard API key",
    )


# Module-level singletons (initialized on first request)
_ruleset_registry: RulesetRegistry | None = None
_detection_engine: DetectionEngine | None = None

# Shared HTTP client — one persistent TCP/TLS connection pool for the
# entire process lifetime. Eliminates per-request handshake overhead.
# Limits: 100 connections total, 20 per host (OpenAI + Anthropic + Google).
_http_client: httpx.AsyncClient | None = None


def get_http_client() -> httpx.AsyncClient:
    """Returns the process-level shared HTTP client."""
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=5.0),
            limits=httpx.Limits(
                max_connections=100,
                max_keepalive_connections=20,
                keepalive_expiry=30,
            ),
            http2=True,  # OpenAI and Anthropic both support HTTP/2
        )
    return _http_client


async def close_http_client() -> None:
    """Called at app shutdown to cleanly drain the connection pool."""
    global _http_client
    if _http_client and not _http_client.is_closed:
        await _http_client.aclose()
        _http_client = None

def get_registry() -> RulesetRegistry:
    global _ruleset_registry
    if _ruleset_registry is None:
        from engine.rulesets.loader import RulesetLoader

        loader = RulesetLoader()
        rulesets = loader.load_all()
        _ruleset_registry = RulesetRegistry()
        _ruleset_registry.register_all(rulesets)
    return _ruleset_registry


def _get_detection_engine() -> DetectionEngine:
    global _detection_engine
    if _detection_engine is None:
        _detection_engine = DetectionEngine(get_registry())
    return _detection_engine


def get_interceptor(db: AsyncSession = Depends(get_db)) -> ProxyInterceptor:
    """Injected proxy interceptor with DB and shared HTTP client."""
    registry = get_registry()
    detection_engine = _get_detection_engine()

    from engine.actions.executor import ActionExecutor
    from engine.vault.key_manager import KeyManager
    from engine.vault.vault import TokenVault

    key_manager = KeyManager()
    vault = TokenVault(db_session=db, key_manager=key_manager)

    executor = ActionExecutor(vault)

    return ProxyInterceptor(
        detection_engine=detection_engine,
        action_executor=executor,
        ruleset_registry=registry,
        db_session=db,
        http_client=get_http_client(),
    )


def get_forwarder() -> OpenAIForwarder:
    """Returns the OpenAI transparent forwarder."""
    return OpenAIForwarder()
