"""
Ironpass — FastAPI application entry point.

This is the main entry point for the Ironpass compliance proxy.
Proxy router mounted at /proxy with /scan, /rulesets endpoints.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from engine.config import get_settings
from engine.database.connection import init_db, close_db

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ironpass")

# ---------------------------------------------------------------------------
# Rate Limiter
# ---------------------------------------------------------------------------
# Redis-backed so limits persist across Railway restarts/deployments.
# Falls back to in-memory if Redis is unreachable at startup.
# Key: real client IP (Railway X-Forwarded-For respected).
_redis_url = settings.redis_url or "memory://"
try:
    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=["100/minute"],
        storage_uri=_redis_url,
        headers_enabled=True,
    )
except Exception:
    logger.warning("Redis unavailable — rate limiter falling back to in-memory")
    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=["100/minute"],
        headers_enabled=True,
    )


# ---------------------------------------------------------------------------
# Application Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup and shutdown lifecycle.

    Startup:
      1. Initialize database (create tables if needed)
      2. Log environment info

    Shutdown:
      1. Close database connection pool
    """
    # ---- Startup ----
    logger.info("Ironpass starting up...")
    logger.info(f"Environment: {settings.app_env}")
    logger.info(f"Key backend: {settings.key_backend}")

    try:
        await init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.warning(f"Database not available at startup: {e}")
        logger.warning("Health check will work, but proxy features require the database")

    # Pre-warm the shared HTTP client so the first request doesn't pay init cost
    try:
        from engine.dependencies import get_http_client
        get_http_client()
        logger.info("Shared HTTP client pool initialized (HTTP/2 enabled)")
    except Exception as e:
        logger.warning(f"HTTP client pre-warm failed: {e}")

    # Load rulesets from YAML at startup
    try:
        from engine.rulesets.loader import RulesetLoader
        loader = RulesetLoader()
        rulesets = loader.load_all()
        logger.info(f"Loaded {len(rulesets)} rulesets at startup")
    except Exception as e:
        logger.warning(f"Ruleset loading failed: {e}")

    logger.info("Ironpass is ready")
    yield

    # ---- Shutdown ----
    logger.info("Ironpass shutting down...")
    await close_db()
    logger.info("Database connections closed")

    # Drain the shared HTTP connection pool
    try:
        from engine.dependencies import close_http_client
        await close_http_client()
        logger.info("HTTP client pool drained")
    except Exception as e:
        logger.warning(f"HTTP client shutdown error: {e}")


# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Ironpass",
    description=(
        "Modular compliance proxy for AI agents. "
        "Intercepts requests, detects sensitive data, applies ruleset-defined "
        "actions, and logs everything immutably."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# Rate limiter state and 429 handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Prometheus metrics — /metrics endpoint
# Instruments all endpoints automatically:
#   ironpass_http_requests_total (by method, path, status)
#   ironpass_http_request_duration_seconds (p50, p95, p99 histograms)
#   ironpass_http_requests_in_progress
from prometheus_fastapi_instrumentator import Instrumentator  # noqa: E402
Instrumentator(
    excluded_handlers=["/metrics", "/health"],  # Don’t instrument these
).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

# CORS — restrict in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.is_development else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health endpoint is now managed by the proxy router

# ---------------------------------------------------------------------------
# Router Mounting (phased)
# ---------------------------------------------------------------------------

# Proxy router (includes /openai/* and /proxy/* endpoints)
from engine.proxy.router import router as proxy_router  # noqa: E402
app.include_router(proxy_router, tags=["proxy"])

# Admin router (tenant provisioning — secured by IRONPASS_ADMIN_SECRET)
from engine.admin.router import router as admin_router  # noqa: E402
app.include_router(admin_router, tags=["admin"])

# Logs router (tenant audit log query — secured by tenant API key)
from engine.logs.router import router as logs_router  # noqa: E402
app.include_router(logs_router, tags=["logs"])

# Compliance operations router (AML/SAR + obligations workflows)
from engine.compliance.router import router as compliance_router  # noqa: E402
app.include_router(compliance_router, tags=["compliance"])

# Agent Security Suite router
from engine.agent_security.router import router as agent_security_router  # noqa: E402
app.include_router(agent_security_router, tags=["agent-security"])

# Dashboard router
try:
    from dashboard.backend.router import router as dashboard_router
    app.include_router(dashboard_router, prefix="/dashboard", tags=["dashboard"])
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Run with uvicorn (development)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "engine.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.is_development,
        log_level=settings.log_level.lower(),
    )
