from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger


def schedule_plugins(scheduler, coro_callable, seconds=1):
    scheduler.add_job(coro_callable, "interval", seconds=seconds, max_instances=1)
    logger.info({"event": "scheduler_job_added", "interval_s": seconds})

