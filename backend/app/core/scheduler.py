from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from backend.config import settings
from backend.core import database as db

logger = logging.getLogger(__name__)

_apscheduler_available = False
try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger
    _apscheduler_available = True
except ImportError:
    logger.warning("apscheduler not installed — scheduler will operate in no-op mode")


class NexusScheduler:
    def __init__(self):
        self._scheduler = None
        self._started = False

    async def start(self):
        if not _apscheduler_available:
            logger.info("Scheduler skipped — apscheduler not installed")
            return

        try:
            self._scheduler = AsyncIOScheduler()

            self._scheduler.add_job(
                self._morning_briefing,
                CronTrigger(hour=settings.BRIEFING_HOUR, minute=0),
                id="morning_briefing",
                name="morning_briefing",
                replace_existing=True,
            )

            self._scheduler.add_job(
                self._nightly_analysis,
                CronTrigger(hour=settings.NIGHTLY_HOUR, minute=0),
                id="nightly_analysis",
                name="nightly_analysis",
                replace_existing=True,
            )

            self._scheduler.add_job(
                self._periodic_check,
                IntervalTrigger(hours=settings.PERIODIC_INTERVAL_HOURS),
                id="periodic_check",
                name="periodic_check",
                replace_existing=True,
            )

            self._scheduler.start()
            self._started = True
            logger.info("Scheduler started with 3 jobs: morning(%dh), nightly(%dh), periodic(%dh interval)",
                        settings.BRIEFING_HOUR, settings.NIGHTLY_HOUR, settings.PERIODIC_INTERVAL_HOURS)
        except Exception as exc:
            logger.error("Scheduler failed to start: %s", exc)

    async def shutdown(self):
        if self._scheduler and self._started:
            self._scheduler.shutdown(wait=False)
            self._started = False
            logger.info("Scheduler shut down")

    async def trigger(self, job_name: str):
        dispatch = {
            "morning": self._morning_briefing,
            "nightly": self._nightly_analysis,
            "periodic": self._periodic_check,
        }
        fn = dispatch.get(job_name)
        if fn is None:
            raise ValueError(f"Unknown job: {job_name}. Available: {list(dispatch.keys())}")
        await fn()

    async def _record_job(self, name: str):
        job_id = str(uuid.uuid4())
        await db.start_job_record(job_id, name)
        return job_id

    async def _morning_briefing(self):
        job_id = await self._record_job("morning_briefing")
        try:
            from backend.app.agents.proactive.briefing_agent import BriefingAgent
            agent = BriefingAgent()
            await agent.generate_briefing()
            await db.complete_job_record(job_id, "done")
            logger.info("Morning briefing completed")
        except Exception as exc:
            logger.error("Morning briefing failed: %s", exc)
            await db.complete_job_record(job_id, "failed", str(exc))

    async def _nightly_analysis(self):
        job_id = await self._record_job("nightly_analysis")
        try:
            from backend.app.agents.proactive.pattern_detective import PatternDetective
            detective = PatternDetective()
            insights = await detective.run_full_scan()
            await db.complete_job_record(job_id, "done")
            logger.info("Nightly analysis found %d insights", len(insights))
        except Exception as exc:
            logger.error("Nightly analysis failed: %s", exc)
            await db.complete_job_record(job_id, "failed", str(exc))

    async def _periodic_check(self):
        job_id = await self._record_job("periodic_check")
        try:
            from backend.app.agents.proactive.pattern_detective import PatternDetective
            detective = PatternDetective()
            insights = await detective.anomaly_scan()
            severe = [i for i in insights if i.get("severity", 0) >= settings.INSIGHT_MIN_SEVERITY]
            if severe:
                logger.info("Periodic check found %d severe insights", len(severe))
            await db.complete_job_record(job_id, "done")
        except Exception as exc:
            logger.error("Periodic check failed: %s", exc)
            await db.complete_job_record(job_id, "failed", str(exc))


nexus_scheduler = NexusScheduler()
