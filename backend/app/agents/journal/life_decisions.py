from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, AsyncGenerator

from backend.app.agents._lm_studio import complete_chat
from backend.config import settings
from backend.core import database as db

logger = logging.getLogger(__name__)


def _extract_json(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return {}


class LifeDecisionsAgent:
    async def analyze(self, question: str) -> AsyncGenerator[dict[str, Any], None]:
        decision_id = await db.create_decision(question)
        yield {"type": "decision.progress", "decision_id": decision_id, "stage": "gathering_context"}

        mood_task = db.get_mood_series(days=30)
        entries_task = db.list_journal_entries(limit=20)
        mood_data, entries = await asyncio.gather(mood_task, entries_task)

        yield {"type": "decision.progress", "decision_id": decision_id, "stage": "analyzing"}

        context_parts = []

        if mood_data:
            avg_mood = sum(d["score"] for d in mood_data) / len(mood_data)
            context_parts.append(f"User's average mood over 30 days: {avg_mood:.1f}/10")

        relevant_entries = []
        q_lower = question.lower()
        for e in entries:
            body = e.get("body_md", "")
            if any(word in body.lower() for word in q_lower.split() if len(word) > 3):
                relevant_entries.append(body[:300])
        if relevant_entries:
            context_parts.append("Relevant journal excerpts:\n" + "\n---\n".join(relevant_entries[:5]))

        try:
            from backend.core.database import get_memory_records
            memories = await get_memory_records(limit=10, category="fact")
            if memories:
                facts = [m["content"] for m in memories]
                context_parts.append("Known facts about user:\n- " + "\n- ".join(facts[:10]))
        except Exception:
            pass

        context = "\n\n".join(context_parts)
        if len(context) > settings.MAX_DECISION_CONTEXT_TOKENS * 4:
            context = context[: settings.MAX_DECISION_CONTEXT_TOKENS * 4]

        messages = [
            {"role": "system", "content": (
                "You are Compass, a decision analyst. Given a question and user context, output ONLY valid JSON:\n"
                '{"question": "...", "options": [{"name": "...", "pros": [{"text": "...", "weight": 0.0-1.0}], '
                '"cons": [{"text": "...", "weight": 0.0-1.0}], "score": 0.0-1.0, '
                '"sources": ["journal:...", "memory:..."]}], '
                '"recommendation": "...", "confidence": 0.0-1.0, "caveats": "..."}\n'
                "You NEVER decide for the user. Present balanced analysis."
            )},
            {"role": "user", "content": f"Decision question: {question}\n\nContext:\n{context}"},
        ]

        raw = await complete_chat(
            messages=messages,
            model=settings.lm_studio_model,
            temperature=0.5,
            max_tokens=1500,
        )

        analysis = _extract_json(raw)
        if not analysis:
            analysis = {"question": question, "options": [], "recommendation": raw[:500], "confidence": 0.3, "caveats": "Analysis could not be fully structured."}

        await db.update_decision_analysis(decision_id, json.dumps(analysis))

        yield {
            "type": "decision.complete",
            "decision_id": decision_id,
            "analysis": analysis,
        }

    async def record_outcome(self, decision_id: str, outcome: str) -> None:
        async with db.get_session() as session:
            from backend.core.database import Decision
            from datetime import datetime, timezone
            dec = await session.get(Decision, decision_id)
            if dec:
                dec.outcome = outcome
                dec.status = "recorded_outcome"
                dec.outcome_recorded_at = datetime.now(timezone.utc)
            await session.flush()
