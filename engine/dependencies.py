"""
Ironpass — FastAPI dependency injection.

All shared dependencies are defined here and injected via FastAPI's
Depends() mechanism. Components never instantiate their own dependencies.
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from engine.config import Settings, get_settings
from engine.database.connection import get_session_factory


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


from dataclasses import dataclass
from fastapi import Request, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

@dataclass
class Tenant:
    id: str
    name: str
    agent_id: str
    active_rulesets: list[str]

async def verify_api_key(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> Tenant:
    """
    Verifies the Ironpass tenant API key.
    For Option B, this just checks the format or a dummy value.
    In a real system, this would look up the key hash in the DB.
    """
    token = credentials.credentials
    if not token.startswith("dbnc_live_"):
        raise HTTPException(status_code=401, detail="Invalid Ironpass API key format")
    
    # Mock tenant
    return Tenant(
        id="tenant_123", 
        name="Acme Corp", 
        agent_id="acme_main_agent", 
        active_rulesets=["pci_dss", "hipaa"]
    )


from engine.proxy.interceptor import ProxyInterceptor
from engine.detection.engine import DetectionEngine
from engine.actions.executor import ActionExecutor
from engine.rulesets.registry import RulesetRegistry
from engine.proxy.forwarder import OpenAIForwarder

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


def get_interceptor() -> ProxyInterceptor:
    """Returns a configured ProxyInterceptor (requires DB)."""
    # Note: DB session is passed per-request. Since ProxyInterceptor doesn't 
    # strictly require DB for detection, we initialize it without one and 
    # the router passes it when needed, or we adapt ProxyInterceptor.
    # Actually, ProxyInterceptor takes db_session in construct.
    from engine.database.connection import SessionLocal
    # We should actually use the Depends(get_db) pattern for this.
    pass  # We will define a Depends version

from fastapi import Depends

def get_interceptor(db: AsyncSession = Depends(get_db)) -> ProxyInterceptor:
    """Injected proxy interceptor with DB."""
    registry = _get_registry()
    detection_engine = _get_detection_engine()
    
    from engine.actions.executor import ActionExecutor
    from engine.actions.blocker import Blocker
    from engine.actions.tokenizer import Tokenizer
    from engine.actions.masker import Masker
    from engine.actions.pseudonymizer import Pseudonymizer
    from engine.vault.vault import TokenVault
    from engine.vault.key_manager import KeyManager
    
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
