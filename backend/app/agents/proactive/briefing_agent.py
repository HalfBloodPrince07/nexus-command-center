"""
BriefingAgent -- generates a daily (or on-demand) briefing that summarises
the user's mood trend, top insights, and pending decisions, then persists
it as a Briefing row with an optional hero chart.

Designed to run at BRIEFING_HOUR via the scheduler, or be invoked manually.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from backend.app.agents._lm_studio import complete_chat
from backend.config import settings
from backend.core.database import (
    Briefing,
    Decision,
    get_mood_series,
    get_session,
    list_insights,
    list_journal_entries,
)
from backend.models.charts import ChartPayload, ChartSeries

logger = logging.getLogger(__name__)

# ── Settings shortcuts ──────────────────────────────────────────────────────
_MAX_INSIGHTS: int = settings.INSIGHT_MAX_PER_BRIEFING  # default 3
_MODEL: str = settings.lm_studio_model

_SYSTEM_PROMPT = """\
You are NEXUS, the user's personal AI operating system.
Write a concise morning briefing in Markdown.  Include:
1. **Mood snapshot** -- summarise the trend in one sentence.
2. **Top insights** -- bullet each insight with its severity (emoji scale).
3. **Pending decisions** -- list any unresolved decisions the user should revisit.
4. **Suggested focus** -- one actionable suggestion for the day.
Keep the tone warm but direct.  No filler, no greetings longer than one line.
"""


class BriefingAgent:
    """Assembles context, calls the LLM, and persists a Briefing row."""

    async def generate_briefing(self) -> dict[str, Any]:
        """Gather data, call the LLM, persist, and return the briefing dict."""

        # -- 1. Gather context pieces ----------------------------------------
        mood_data = await self._safe_mood_series()
        top_insights = await self._safe_insights()
        recent_entries = await self._safe_journal_entries()
        pending_decisions = await self._safe_pending_decisions()

        # -- 2. Build a mood summary string ----------------------------------
        mood_summary = self._build_mood_summary(mood_data)

        # -- 3. Build the user-message for the LLM ---------------------------
        user_content = self._build_user_message(
            mood_summary=mood_summary,
            insights=top_insights,
            decisions=pending_decisions,
            entries=recent_entries,
        )

        # -- 4. Call the LLM -------------------------------------------------
        body_md = await self._call_llm(user_content)

        # -- 5. Build optional hero chart ------------------------------------
        hero_chart = self._build_hero_chart(mood_data)
        hero_chart_json = (
            hero_chart.model_dump_json() if hero_chart is not None else None
        )

        # -- 6. Persist the Briefing -----------------------------------------
        briefing_id = str(uuid.uuid4())
        insights_json = json.dumps(
            [self._slim_insight(i) for i in top_insights],
            default=str,
        )

        try:
            async with get_session() as session:
                session.add(Briefing(
                    id=briefing_id,
                    created_at=datetime.now(timezone.utc),
                    body_md=body_md,
                    hero_chart_json=hero_chart_json,
                    mood_summary=mood_summary,
                    insights_json=insights_json,
                ))
        except Exception:
            logger.exception("Failed to persist briefing %s", briefing_id[:8])
            # Still return whatever we generated so the caller can surface it
            pass

        result = {
            "id": briefing_id,
            "body_md": body_md,
            "mood_summary": mood_summary,
            "insights": top_insights,
            "pending_decisions": pending_decisions,
            "hero_chart": hero_chart.model_dump() if hero_chart else None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        logger.info("Briefing %s generated (%d chars)", briefing_id[:8], len(body_md))
        return result

    # ------------------------------------------------------------------
    # Data-gathering helpers (each wrapped in try/except)
    # ------------------------------------------------------------------

    async def _safe_mood_series(self) -> list[dict[str, Any]]:
        try:
            return await get_mood_series(7)
        except Exception:
            logger.exception("Failed to fetch mood series for briefing")
            return []

    async def _safe_insights(self) -> list[dict[str, Any]]:
        try:
            return await list_insights(limit=_MAX_INSIGHTS)
        except Exception:
            logger.exception("Failed to fetch insights for briefing")
            return []

    async def _safe_journal_entries(self) -> list[dict[str, Any]]:
        try:
            return await list_journal_entries(limit=5)
        except Exception:
            logger.exception("Failed to fetch journal entries for briefing")
            return []

    async def _safe_pending_decisions(self) -> list[dict[str, Any]]:
        """Query the Decision table for rows whose status is neither
        'complete' nor 'recorded_outcome'."""
        try:
            from sqlalchemy import select

            async with get_session() as session:
                stmt = (
                    select(Decision)
                    .where(Decision.status.notin_(["complete", "recorded_outcome"]))
                    .order_by(Decision.created_at.desc())
                    .limit(10)
                )
                result = await session.execute(stmt)
                rows = result.scalars().all()
                return [
                    {
                        "id": d.id,
                        "question": d.question,
                        "status": d.status,
                        "created_at": d.created_at.isoformat() if d.created_at else None,
                    }
                    for d in rows
                ]
        except Exception:
            logger.exception("Failed to fetch pending decisions for briefing")
            return []

    # ------------------------------------------------------------------
    # LLM call
    # ------------------------------------------------------------------

    async def _call_llm(self, user_content: str) -> str:
        """Send the assembled context to LM Studio and return the response."""
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
            if not response or not response.strip():
                logger.warning("LLM returned empty briefing; using fallback")
                return self._fallback_briefing(user_content)
            return response.strip()
        except Exception:
            logger.exception("LLM call failed for briefing generation")
            return self._fallback_briefing(user_content)

    # ------------------------------------------------------------------
    # Message / chart builders
    # ------------------------------------------------------------------

    @staticmethod
    def _build_mood_summary(mood_data: list[dict[str, Any]]) -> str:
        if not mood_data:
            return "No mood data available for the past 7 days."

        scores = [float(m.get("score", 0)) for m in mood_data]
        avg = sum(scores) / len(scores)
        latest = scores[-1]
        trend = "stable"
        if len(scores) >= 2:
            if scores[-1] > scores[0]:
                trend = "improving"
            elif scores[-1] < scores[0]:
                trend = "declining"

        return (
            f"7-day average mood: {avg:.1f}/10 | latest: {latest:.0f}/10 | "
            f"trend: {trend} ({len(scores)} data points)"
        )

    @staticmethod
    def _build_user_message(
        mood_summary: str,
        insights: list[dict[str, Any]],
        decisions: list[dict[str, Any]],
        entries: list[dict[str, Any]],
    ) -> str:
        parts: list[str] = []

        parts.append(f"## Mood\n{mood_summary}\n")

        if insights:
            bullets = "\n".join(
                f"- [{i.get('category', '?')}] (severity {i.get('severity', '?')}) "
                f"{i.get('title', 'untitled')}"
                for i in insights
            )
            parts.append(f"## Top Insights\n{bullets}\n")
        else:
            parts.append("## Top Insights\nNo new insights.\n")

        if decisions:
            bullets = "\n".join(
                f"- {d.get('question', '(no question)')}  (status: {d.get('status', '?')})"
                for d in decisions
            )
            parts.append(f"## Pending Decisions\n{bullets}\n")
        else:
            parts.append("## Pending Decisions\nNone pending.\n")

        if entries:
            summaries = "\n".join(
                f"- {e.get('title') or '(untitled)'} ({str(e.get('created_at', ''))[:10]})"
                for e in entries[:5]
            )
            parts.append(f"## Recent Journal Entries\n{summaries}\n")

        return "\n".join(parts)

    @staticmethod
    def _build_hero_chart(mood_data: list[dict[str, Any]]) -> ChartPayload | None:
        """Build a 7-day mood line chart for the briefing hero slot."""
        if len(mood_data) < 2:
            return None

        data_points = []
        for m in mood_data:
            dt = m.get("date")
            label = (
                dt.strftime("%Y-%m-%d") if isinstance(dt, datetime) else str(dt)[:10]
            )
            data_points.append({"x": label, "y": float(m.get("score", 0))})

        try:
            return ChartPayload(
                id=str(uuid.uuid4()),
                type="line",
                title="Mood -- Last 7 Days",
                series=[
                    ChartSeries(name="Mood Score", data=data_points, color="#6366f1"),
                ],
                x_label="Date",
                y_label="Score",
            )
        except Exception:
            logger.exception("Failed to build hero chart")
            return None

    # ------------------------------------------------------------------
    # Fallback / utility
    # ------------------------------------------------------------------

    @staticmethod
    def _fallback_briefing(user_content: str) -> str:
        """Return a plain-text briefing when the LLM is unreachable."""
        return (
            "# Daily Briefing (offline mode)\n\n"
            "The LLM was unavailable so this briefing is auto-generated from raw data.\n\n"
            + user_content
        )

    @staticmethod
    def _slim_insight(insight: dict[str, Any]) -> dict[str, Any]:
        """Return only the fields worth serialising into insights_json."""
        return {
            "id": insight.get("id"),
            "category": insight.get("category"),
            "severity": insight.get("severity"),
            "title": insight.get("title"),
        }
