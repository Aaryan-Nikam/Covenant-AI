import logging
from datetime import datetime, timezone
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from engine.database.connection import get_session_factory
from engine.gdpr.models import PiiDataRecord

logger = logging.getLogger("ironpass.gdpr.scheduler")

async def purge_expired_pii_records():
    """Delete PiiDataRecords whose retention_until has passed."""
    logger.info("Running GDPR retention purge job...")
    session_factory = get_session_factory()
    now = datetime.now(timezone.utc)
    
    try:
        async with session_factory() as session:
            result = await session.execute(
                delete(PiiDataRecord).where(PiiDataRecord.retention_until <= now)
            )
            deleted_count = result.rowcount
            await session.commit()
            
            if deleted_count > 0:
                logger.info(f"Purged {deleted_count} expired GDPR PII records.")
            else:
                logger.info("No expired GDPR records to purge.")
    except Exception as e:
        logger.error(f"GDPR retention purge failed: {e}")

def start_gdpr_scheduler() -> AsyncIOScheduler:
    """Initialize and start the APScheduler for GDPR jobs."""
    scheduler = AsyncIOScheduler()
    # Run once a day at midnight (or every minute for testing, let's do daily)
    scheduler.add_job(
        purge_expired_pii_records, 
        'cron', 
        hour=0, 
        minute=0, 
        id="gdpr_retention_purge",
        replace_existing=True
    )
    scheduler.start()
    return scheduler
