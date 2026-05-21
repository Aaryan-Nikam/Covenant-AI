"""
Ironpass — Async database connection.

Uses SQLAlchemy async engine + async sessionmaker.
Connection pool configured for production workloads.
"""

from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from engine.config import get_settings

# Module-level engine and session factory — initialized on first import
_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """
    Get or create the async SQLAlchemy engine.
    Uses the async database URL from settings.
    """
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.async_database_url,
            echo=settings.is_development,
            pool_size=20,
            max_overflow=10,
            pool_pre_ping=True,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get or create the async session factory."""
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_session_factory


def _get_alembic_config() -> Config:
    engine_dir = Path(__file__).resolve().parents[1]
    alembic_cfg = Config(str(engine_dir / "alembic.ini"))
    alembic_cfg.set_main_option(
        "script_location",
        str(engine_dir / "database" / "migrations"),
    )
    return alembic_cfg


async def verify_migration_head(engine: AsyncEngine | None = None) -> None:
    """
    Refuse startup when the database is not at the Alembic head revision.

    Schema is managed exclusively by migrations. This check catches deployments
    where code was shipped before `alembic upgrade head` was run.
    """
    alembic_cfg = _get_alembic_config()
    script = ScriptDirectory.from_config(alembic_cfg)
    expected_head = script.get_current_head()
    engine = engine or get_engine()

    async with engine.connect() as conn:
        current_revision = await conn.run_sync(
            lambda sync_conn: MigrationContext.configure(sync_conn).get_current_revision()
        )

    if current_revision != expected_head:
        raise RuntimeError(
            "Database migration mismatch. "
            f"Expected head: {expected_head}, current: {current_revision}. "
            "Run `alembic upgrade head` before starting the application."
        )


async def get_db_session() -> AsyncSession:
    """
    FastAPI dependency — yields an async session.
    Commits on success, rolls back on exception.
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """
    Verify database schema is ready for application startup.

    Schema is managed exclusively by Alembic migrations.
    """
    await verify_migration_head()


async def close_db() -> None:
    """Dispose of the engine connection pool. Called at application shutdown."""
    global _engine, _async_session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _async_session_factory = None
