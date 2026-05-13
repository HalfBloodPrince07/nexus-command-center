from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator

from backend.app.agents._lm_studio import complete_chat
from backend.app.agents.journal.mood_analyst import MoodAnalystAgent
from backend.app.agents.journal.psychology_agent import PsychologyAgent
from backend.app.agents.journal.relationship_finder import RelationshipFinderAgent
from backend.app.agents.journal.life_decisions import LifeDecisionsAgent
from backend.config import settings
from backend.core import database as db
from backend.core.personality import get_system_prompt, inject_tone
from backend.core.resilience import degraded_event

logger = logging.getLogger(__name__)


class JournalLeadAgent:
    def __init__(self):
        self.mood = MoodAnalystAgent()
        self.psychology = PsychologyAgent()
        self.relationships = RelationshipFinderAgent()
        self.decisions = LifeDecisionsAgent()

    async def on_new_entry(self, entry_id: str, body: str, title: str | None = None) -> dict[str, Any]:
        tags: list[str] = []
        await db.create_journal_entry(
            entry_id=entry_id,
            body_md=body,
            title=title,
            tags=json.dumps(tags),
        )

        journal_dir = settings.JOURNAL_DIR
        now = datetime.now(timezone.utc)
        dir_path = journal_dir / str(now.year) / f"{now.month:02d}"
        dir_path.mkdir(parents=True, exist_ok=True)
        disk_warning: dict[str, Any] | None = None
        try:
            (dir_path / f"{entry_id}.md").write_text(body, encoding="utf-8")
        except OSError as exc:
            logger.warning("Journal disk write failed", extra={"entry_id": entry_id, "error": str(exc)})
            disk_warning = degraded_event(
                "Echo",
                "disk_write_failed",
                "Journal entry was saved to the database, but the markdown file could not be written.",
            )

        mood_task = self.mood.analyze(entry_id, body)
        rel_task = self.relationships.process_entry(entry_id, body)
        mood_result, rel_result = await asyncio.gather(mood_task, rel_task, return_exceptions=True)

        if isinstance(mood_result, Exception):
            logger.error("Mood analysis failed for %s: %s", entry_id, mood_result)
            mood_result = {"score": 5, "emotions": [], "confidence": 0.0}

        if isinstance(rel_result, Exception):
            logger.error("Relationship analysis failed for %s: %s", entry_id, rel_result)
            rel_result = []

        asyncio.create_task(self._run_psychology_background())

        return {
            "entry_id": entry_id,
            "mood": mood_result,
            "people": rel_result,
            "degraded": disk_warning,
        }

    async def _run_psychology_background(self):
        try:
            await self.psychology.analyze_window(days=30)
        except Exception as exc:
            logger.warning("Background psychology analysis failed: %s", exc)

    def _classify_intent(self, message: str) -> str:
        lowered = message.lower()
        if any(k in lowered for k in ("mood", "how have i been", "how am i", "feeling", "emotions")):
            return "mood"
        if any(k in lowered for k in ("pattern", "tendency", "habit", "recurring", "theme", "behavior")):
            return "psychology"
        if any(k in lowered for k in ("who", "people", "relationship", "talked about", "mentioned", "friend", "colleague", "family")):
            return "relationships"
        if any(k in lowered for k in ("should i", "decision", "decide", "choose", "pros and cons")):
            return "decision"
        return "general"

    async def route_query(
        self,
        message: str,
        mood_context: dict[str, Any] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        intent = self._classify_intent(message)

        if intent == "mood":
            yield {"type": "thinking", "agent": "Lumen"}
            trend = await self.mood.trend(window_days=30)
            summary_messages = [
                {
                    "role": "system",
                    "content": inject_tone(get_system_prompt("mood_analyst"), mood_context),
                },
                {"role": "user", "content": f"User asked: {message}\n\nMood data: {json.dumps(trend.get('series', []))}"},
            ]
            raw = await complete_chat(messages=summary_messages, model=settings.lm_studio_model, temperature=0.5, max_tokens=300)
            yield {"type": "token", "content": raw, "agent": "Lumen"}
            yield {"type": "chart.update", "payload": trend}
            yield {"type": "done", "agent": "Lumen"}

        elif intent == "psychology":
            yield {"type": "thinking", "agent": "Sage"}
            patterns = await self.psychology.analyze_window(days=30)
            if patterns:
                summary = "\n".join(f"- **{p.get('name', '?')}**: {p.get('description', '')}" for p in patterns)
                yield {"type": "token", "content": f"Here are the patterns I've detected:\n\n{summary}", "agent": "Sage"}
                chart = await self.psychology.chart(days=30)
                yield {"type": "chart.update", "payload": chart}
            else:
                yield {"type": "token", "content": "I don't have enough journal entries yet to detect patterns. Keep journaling and I'll start spotting trends after a few more entries.", "agent": "Sage"}
            yield {"type": "done", "agent": "Sage"}

        elif intent == "relationships":
            yield {"type": "thinking", "agent": "Orbit"}
            graph = await self.relationships.graph()
            node_count = len(graph.get("nodes", [])) - 1
            if node_count > 0:
                yield {"type": "token", "content": f"I've tracked {node_count} people across your journal entries. Here's your relationship map:", "agent": "Orbit"}
                yield {"type": "chart.update", "payload": graph}
            else:
                yield {"type": "token", "content": "I haven't found any people mentioned in your journal yet. Write about your interactions and I'll start building your relationship map.", "agent": "Orbit"}
            yield {"type": "done", "agent": "Orbit"}

        elif intent == "decision":
            yield {"type": "thinking", "agent": "Compass"}
            async for event in self.decisions.analyze(message):
                if event["type"] == "decision.progress":
                    yield {"type": "token", "content": f"*{event['stage'].replace('_', ' ').title()}...*\n", "agent": "Compass"}
                elif event["type"] == "decision.complete":
                    analysis = event.get("analysis", {})
                    recommendation = analysis.get("recommendation", "Analysis complete.")
                    yield {"type": "token", "content": recommendation, "agent": "Compass"}
                    yield event
            yield {"type": "done", "agent": "Compass"}

        else:
            yield {"type": "thinking", "agent": "Echo"}
            messages = [
                {
                    "role": "system",
                    "content": inject_tone(get_system_prompt("journal_lead"), mood_context),
                },
                {"role": "user", "content": message},
            ]
            raw = await complete_chat(messages=messages, model=settings.lm_studio_model, temperature=0.6, max_tokens=500)
            yield {"type": "token", "content": raw, "agent": "Echo"}
            yield {"type": "done", "agent": "Echo"}
