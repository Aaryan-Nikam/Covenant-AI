"""
Covenant AI — SLA APScheduler Job.

Evaluates all active SLA policies every 5 minutes.
Each job run creates its own fresh DB session.
"""

import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger("ironpass.sla.scheduler")


async def _run_evaluation() -> None:
    """Wrapper that creates its own DB session per run."""
    from engine.database.connection import get_session_factory
    from engine.sla.evaluator import evaluate_all_policies

    session_factory = get_session_factory()
    try:
        async with session_factory() as session:
            await evaluate_all_policies(session)
    except Exception as e:
        logger.error(f"SLA scheduler job failed: {e}", exc_info=True)


def start_sla_scheduler() -> AsyncIOScheduler:
    """Initialize and start the APScheduler for SLA evaluation."""
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        _run_evaluation,
        "interval",
        minutes=5,
        id="sla_policy_evaluation",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("SLA evaluation scheduler started (every 5 minutes)")
    return scheduler
