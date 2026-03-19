"""
Ironpass — FastAPI dependency injection.

All shared dependencies are defined here and injected via FastAPI's
Depends() mechanism. Components never instantiate their own dependencies.
"""

from dataclasses import dataclass
from secrets import compare_digest
from typing import AsyncGenerator

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


security = HTTPBearer(auto_error=False)


@dataclass
class Tenant:
    id: str
    name: str
    agent_id: str
    active_rulesets: list[str]


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
    credentials: HTTPAuthorizationCredentials | None = Security(security),
    settings: Settings = Depends(get_config),
) -> Tenant:
    """
    Verifies the exact bearer token required to access proxy endpoints.
    The implementation is still single-tenant, but it now fails closed
    unless a configured token matches exactly.
    """
    token = _require_bearer_token(credentials)
    _require_configured_token(
        token,
        settings.proxy_api_key,
        missing_detail="Ironpass proxy API key is not configured",
        invalid_detail="Invalid Ironpass API key",
    )

    return Tenant(
        id="tenant_123",
        name="Acme Corp",
        agent_id="acme_main_agent",
        active_rulesets=["pci_dss", "hipaa"],
    )


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


def _get_registry() -> RulesetRegistry:
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
        _detection_engine = DetectionEngine(_get_registry())
    return _detection_engine


def get_interceptor(db: AsyncSession = Depends(get_db)) -> ProxyInterceptor:
    """Injected proxy interceptor with DB."""
    registry = _get_registry()
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
    )


def get_forwarder() -> OpenAIForwarder:
    """Returns the OpenAI transparent forwarder."""
    return OpenAIForwarder()
