"""
Ironpass — FastAPI application entry point.

This is the main entry point for the Ironpass compliance proxy.
Proxy router mounted at /proxy with /scan, /rulesets endpoints.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
from engine.proxy.router import router as proxy_router
app.include_router(proxy_router, tags=["proxy"])

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
