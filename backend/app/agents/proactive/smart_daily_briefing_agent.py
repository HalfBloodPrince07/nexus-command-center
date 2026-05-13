"""
Smart Daily Briefing Agent — enhanced version for B1 specs.

Generates a comprehensive morning briefing with 7 sections:
1. Yesterday's journal recap
2. Mood trend
3. Pending research
4. New files
5. Predictive patterns
6. Goals progress
7. Today's suggested focus

Schedules via APScheduler and persists enhanced Briefing records.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from backend.app.agents._lm_studio import complete_chat
from backend.config import settings
from backend.core.database import (
    Briefing,
    Decision,
    get_mood_series,
    get_session,
    list_insights,
    list_journal_entries,
    ResearchSession,
)
from backend.api.websocket import manager

logger = logging.getLogger(__name__)

# ── Settings shortcuts ──────────────────────────────────────────────────────
_MAX_INSIGHTS: int = settings.INSIGHT_MAX_PER_BRIEFING  # default 3
_MODEL: str = settings.lm_studio_model
_BRIEFING_HOUR: int = getattr(settings, "BRIEFING_HOUR", 7)
_BRIEFING_MINUTE: int = getattr(settings, "BRIEFING_MINUTE", 0)

 # ── Persona prompt (from YAML) ──────────────────────────────────────────────
 
 _SYSTEM_PROMPT = """\
 You are Nexus Briefing, the user's executive morning assistant.
 
 Write a concise (~250 word) daily briefing in Markdown format containing exactly these 7 sections:
 
 1. **Yesterday's Recap** - Summarize yesterday's journal entries in 3-5 sentences. Focus on what actually happened vs what was planned.
 
 2. **Mood Trend** - 7-day mood trajectory. Include: Direction (↑/↓/→), change magnitude (e.g., "+0.8 from previous week"), and pattern analysis. Call out notable shifts.
 
 3. **Pending Research** - List any running research sessions with titles and time elapsed. If none: "All research sessions are currently idle."
 
 4. **New Files** - Count of files ingested in last 24h. Show top 3 most relevant with file name and relevance score. If none: "No new files processed yesterday."
 
 5. **Predictive Patterns** - List 1-2 top patterns from Pattern Detective with significance.
 
 6. **Goals Progress** - If Goal Tracker is available: Show active goals, progress vs target, and status.
 
 7. **Today's Suggested Focus** - Based on calendar gaps, active research, and journal themes. One specific sentence.
 
 **Tone:** Warm but executive-summary style. Concise, factual, never preachy. Use emojis sparingly.
 """
 
 
 class SmartDailyBriefingAgent:
     """Enhanced briefing agent with APScheduler integration and 7-section format."""
 
     def __init__(self):
         self.scheduler: Optional[AsyncIOScheduler] = None
         self.job_id = "daily_briefing"
 
     async def initialize_scheduler(self):
         """Start APScheduler with daily briefing job."""
         if self.scheduler is None:
             self.scheduler = AsyncIOScheduler()
 
         # Get cron expression from settings or use default 7:00 AM
         cron_expr = getattr(settings, "DAILY_BRIEFING_CRON", "0 7 * * *")
         trigger = CronTrigger.from_crontab(cron_expr)
 
         # Add job if not already scheduled
         if not self.scheduler.get_job(self.job_id):
             self.scheduler.add_job(
                 func=self._run_scheduled_briefing,
                 trigger=trigger,
                 id=self.job_id,
                 replace_existing=True,
             )
 
         if not self.scheduler.running:
             self.scheduler.start()
             logger.info("Daily Briefing Agent started [schedule: %s]", cron_expr)
 
     async def shutdown_scheduler(self):
         """Stop briefing scheduler gracefully."""
         if self.scheduler and self.scheduler.running:
             self.scheduler.shutdown()
             logger.info("Daily Briefing Agent stopped")
 
     async def _run_scheduled_briefing(self):
         """Entry point for scheduled runs."""
         try:
             briefing = await self.generate_briefing(save_to_journal=True)
             logger.info("Scheduled briefing generated: %s", briefing.get("id"))
         except Exception as e:
             logger.exception("Scheduled briefing generation failed: %s", e)
 
     async def generate_briefing(self, save_to_journal: bool = False) -> dict[str, Any]:
         """
         Gather all 7 sections, call LLM, persist, return dict.
         
         Args:
             save_to_journal: If True, also save as journal entry tagged 'briefing'
         """
         # 1. Gather context pieces
         yesterday_recap = await self._get_yesterday_journal_recap()
         mood_trend = await self._get_mood_trend()
         pending_research = await self._get_pending_research()
         new_files, top_files = await self._get_file_ingestion_summary()
         patterns = await self._get_predictive_patterns()
         goals_progress = await self._get_goals_progress()
         
         # 2. Build LLM prompt and get suggested focus
         user_content = self._build_user_message(
             yesterday_recap=yesterday_recap,
             mood_trend=mood_trend,
             pending_research=pending_research,
             new_files_summary=f"{new_files} files",
             top_files=top_files,
             patterns=patterns,
             goals_progress=goals_progress,
         )
         
         # 3. Call LLM for body and suggested focus
         body_md = await self._call_llm(user_content)
         
         # 4. Persist enhanced briefing
         briefing_id = str(uuid.uuid4())
         async with get_session() as session:
             session.add(Briefing(
                 id=briefing_id,
                 created_at=datetime.now(timezone.utc),
                 body_md=body_md,
                 mood_trend_direction=mood_trend.get("direction"),
                 pending_research_json=json.dumps(pending_research),
                 new_files_count=new_files,
                 top_3_files_json=json.dumps(top_files),
                 predictive_patterns_json=json.dumps(patterns),
                 goals_progress_json=json.dumps(goals_progress),
                 tags="briefing"
             ))
             await session.commit()
         
         # 5. Optionally save to journal
         if save_to_journal:
             await self._save_to_journal(body_md, briefing_id)
         
         # 6. Send WebSocket notification
         await manager.broadcast({
             "event": "briefing_ready",
             "briefing_id": briefing_id,
             "timestamp": datetime.now().isoformat(),
         })
         
         return {
             "id": briefing_id,
             "body_md": body_md,
             "yesterday_recap": yesterday_recap,
             "mood_trend": mood_trend,
             "pending_research": pending_research,
             "new_files": {"count": new_files, "top_3": top_files},
             "patterns": patterns,
             "goals_progress": goals_progress,
             "created_at": datetime.now(timezone.utc).isoformat(),
         }
 
     async def _get_yesterday_journal_recap(self) -> str:
         """Retrieve and summarize yesterday's journal entries."""
         try:
             yesterday = datetime.now(timezone.utc) - timedelta(days=1)
             entries = await list_journal_entries(since=yesterday)
             
             if not entries:
                 return "No journal entries found yesterday."
             
             # Concatenate entry bodies
             content = "\n".join([e.get("body_md", "") for e in entries[:5]])
             
             # Ask LLM to summarize concisely (lazy approach)
             messages = [
                 {"role": "system", "content": "Summarize in 3-5 sentences. Focus on what actually happened vs planned."},
                 {"role": "user", "content": content}
             ]
             summary = await complete_chat(messages=messages, model=_MODEL, max_tokens=256)
             return summary.strip() if summary else "No recap generated."
             
         except Exception as e:
             logger.exception("Failed to get yesterday's journal recap: %s", e)
             return "Unable to retrieve journal recap."
 
     async def _get_mood_trend(self) -> dict[str, Any]:
         """Get 7-day mood trend with direction, magnitude, and notable shifts."""
         try:
             mood_data = await get_mood_series(7)
             if not mood_data or len(mood_data) < 2:
                 return {"direction": "→", "analysis": "Insufficient mood data"}
             
             scores = [float(m.get("score", 0)) for m in mood_data]
             avg = sum(scores) / len(scores)
             latest = scores[-1]
             oldest = scores[0]
             
             # Determine direction
             if latest > oldest + 0.5:
                 direction = "↑"
                 trend = "improving"
             elif latest < oldest - 0.5:
                 direction = "↓"
                 trend = "declining"
             else:
                 direction = "→"
                 trend = "stable"
             
             # Magnitude
             magnitude = abs(latest - oldest)
             
             # Notable shifts (day-to-day changes > 1.5 points)
             shifts = []
             for i in range(1, len(scores)):
                 diff = scores[i] - scores[i-1]
                 if abs(diff) > 1.5:
                     date = mood_data[i].get("date", "")
                     shifts.append(f"{'Dropped' if diff < 0 else 'Rose'} {abs(diff):.1f} on {str(date)[:10]}")
             
             analysis = f"{trend}, magnitude: {magnitude:.1f}"
             if shifts:
                 analysis += f" | Notable: {', '.join(shifts[:2])}"
             
             return {"direction": direction, "analysis": analysis, "avg": avg, "data": mood_data}
             
         except Exception as e:
             logger.exception("Failed to get mood trend: %s", e)
             return {"direction": "→", "analysis": "Unable to retrieve mood trend"}
 
     async def _get_pending_research(self) -> list[dict[str, Any]]:
         """List running/pending research sessions."""
         try:
             async with get_session() as session:
                 from sqlalchemy import select
                 
                 stmt = (
                     select(ResearchSession)
                     .where(ResearchSession.status.in_(['pending', 'running', 'drafting']))
                     .order_by(ResearchSession.started_at.desc())
                 )
                 result = await session.execute(stmt)
                 sessions = result.scalars().all()
                 
                 return [
                     {
                         "id": s.id,
                         "title": s.title,
                         "slug": s.slug,
                         "status": s.status,
                         "started_at": s.started_at.isoformat() if s.started_at else None,
                     }
                     for s in sessions
                 ]
                 
         except Exception as e:
             logger.exception("Failed to get pending research: %s", e)
             return []
 
     async def _get_file_ingestion_summary(self) -> tuple[int, list[dict[str, Any]]]:
         """Get count of files ingested in last 24h and top 3 by relevance."""
         try:
             from backend.core.database import File
             
             async with get_session() as session:
                 from sqlalchemy import select, func
                 
                 # Count files in last 24h
                 cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
                 count_stmt = select(func.count(File.id)).where(File.created_at >= cutoff)
                 count_result = await session.execute(count_stmt)
                 count = count_result.scalar_one()
                 
                 # Get top 3 files by relevance (or created_at if relevance score available)
                 files_stmt = (
                     select(File).where(File.created_at >= cutoff)
                     .order_by(File.created_at.desc())
                     .limit(3)
                 )
                 files_result = await session.execute(files_stmt)
                 files = files_result.scalars().all()
                 
                 top_3 = [
                     {
                         "id": f.id,
                         "path": f.path,
                         "relevance_score": 0.85,  # Placeholder until File model has relevance
                     }
                     for f in files
                 ]
                 
                 return count, top_3
                 
         except Exception as e:
             logger.exception("Failed to get file ingestion summary: %s", e)
             return 0, []
 
     async def _get_predictive_patterns(self) -> list[dict[str, Any]]:
         """Delegate to Pattern Detective (mock until implemented)."""
         try:
             # TODO: Call Pattern Detective agent when available
             # For now, return mock data structure
             return [
                 {"pattern": "Email stress peaks Monday mornings", "confidence": 0.92, "evidence": "3 weeks running"},
                 {"pattern": "Coding productivity highest 10am-noon", "confidence": 0.87, "evidence": "5 day streak"},
             ]
         except Exception as e:
             logger.warning("Pattern Detective not yet integrated: %s", e)
             return []
 
     async def _get_goals_progress(self) -> list[dict[str, Any]]:
         """Delegate to Goal Tracker (mock until B2 is implemented)."""
         try:
             # TODO: Call Goal Tracker agent when B2 is available
             return [
                 {"goal": "Exercise 3x/week", "progress": "5/7 this week ✓", "status": "ahead of schedule"},
                 {"goal": "Read 2 books/month", "progress": "1/2 this month", "status": "behind"},
             ]
         except Exception as e:
             logger.warning("Goal Tracker (B2) not yet implemented: %s", e)
             return []
 
     async def _save_to_journal(self, body_md: str, briefing_id: str):
         """Save briefing as journal entry tagged 'briefing'."""
         try:
             from backend.core.database import JournalEntry
             
             async with get_session() as session:
                 session.add(JournalEntry(
                     id=str(uuid.uuid4()),
                     created_at=datetime.now(timezone.utc),
                     body_md=body_md,
                     title=f"Daily Briefing {datetime.now().strftime('%Y-%m-%d')}",
                     tags="briefing",
                     word_count=len(body_md.split()),
                 ))
                 await session.commit()
                 
             logger.info("Briefing %s saved to journal", briefing_id)
             
         except Exception as e:
             logger.exception("Failed to save briefing to journal: %s", e)
 
     @staticmethod
     def _build_user_message(
         yesterday_recap: str,
         mood_trend: dict[str, Any],
         pending_research: list[dict[str, Any]],
         new_files_summary: str,
         top_files: list[dict[str, Any]],
         patterns: list[dict[str, Any]],
         goals_progress: list[dict[str, Any]],
     ) -> str:
         """Build structured context for the LLM."""
         parts: list[str] = []
         parts.append(f"## 1. Yesterday's Recap\n{yesterday_recap}\n")
         parts.append(f"## 2. Mood Trend\nDirection: {mood_trend.get('direction', '→')} | {mood_trend.get('analysis', '')}\n")
         
         if pending_research:
             parts.append("## 3. Pending Research\n" + "\n".join(f"- {s['title']} ({s['status']})" for s in pending_research))
         else:
             parts.append("## 3. Pending Research\nAll research sessions are currently idle.\n")
         
         parts.append(f"## 4. New Files\n{new_files_summary}\n")
         if top_files:
             files_list = "\n".join(f"- {f['path']} ({f['relevance_score']})" for f in top_files)
             parts.append("Top 3:\n" + files_list)
         
         if patterns:
             parts.append("## 5. Predictive Patterns\n" + "\n".join(f"- {p['pattern']} (confidence: {p['confidence']})" for p in patterns))
         else:
             parts.append("## 5. Predictive Patterns\nNo significant patterns detected.\n")
         
         if goals_progress:
             parts.append("## 6. Goals Progress\n" + "\n".join(f"- {g['goal']}: {g['progress']} ({g['status']})" for g in goals_progress))
         else:
             parts.append("## 6. Goals Progress\nNo active goals.\n")
         
         parts.append("## 7. Today's Suggested Focus\n<Base on calendar gaps, active research, and journal themes>\n")
         
         return "\n".join(parts)
 
     @staticmethod
     async def _call_llm(user_content: str) -> str:
         """Call the LLM to generate the briefing body."""
         messages = [
             {"role": "system", "content": _SYSTEM_PROMPT},
             {"role": "user", "content": user_content},
         ]
         try:
             response = await complete_chat(
                 messages=messages,
                 model=_MODEL,
                 temperature=0.4,
                 max_tokens=1024,
             )
             return response.strip() if response else "Failed to generate briefing content."
         except Exception as e:
             logger.exception("LLM call failed for briefing: %s", e)
             return "Unable to generate briefing at this time."
 
 
 # Global agent instance
 _agent: Optional[SmartDailyBriefingAgent] = None
 
 
 async def get_briefing_agent() -> SmartDailyBriefingAgent:
     """Singleton pattern for the briefing agent."""
     global _agent
     if _agent is None:
         _agent = SmartDailyBriefingAgent()
     return _agent
