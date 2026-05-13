from __future__ import annotations

import json
import logging
import re
from typing import Any

from backend.app.agents._lm_studio import complete_chat
from backend.config import settings
from backend.core import database as db

logger = logging.getLogger(__name__)


def _extract_json_array(text: str) -> list[dict[str, Any]]:
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data.get("patterns", [])
        return data
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[^{}]*\"patterns\"\s*:\s*\[.*?\]\s*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group()).get("patterns", [])
        except json.JSONDecodeError:
            pass
    return []


class PsychologyAgent:
    async def analyze_window(self, days: int = 30) -> list[dict[str, Any]]:
        entries = await db.list_journal_entries(limit=200)
        if len(entries) < settings.PSYCHOLOGY_MIN_ENTRIES:
            logger.info("Not enough entries (%d < %d) for psychology analysis", len(entries), settings.PSYCHOLOGY_MIN_ENTRIES)
            return []

        from datetime import datetime, timezone, timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        filtered = [e for e in entries if e.get("created_at") and e["created_at"] >= cutoff]
        if len(filtered) < settings.PSYCHOLOGY_MIN_ENTRIES:
            filtered = entries[:settings.PSYCHOLOGY_MIN_ENTRIES]

        entry_summaries = []
        for e in filtered[:50]:
            body = e.get("body_md", "")[:500]
            entry_summaries.append(f"[{e['id'][:8]}] {e.get('created_at', '')}: {body}")
        combined = "\n---\n".join(entry_summaries)

        if len(combined) > 8000:
            combined = combined[:8000] + "\n... (truncated)"

        messages = [
            {"role": "system", "content": (
                "You are Sage, a behavioral pattern detector. Given journal entries over a time window, identify:\n"
                "- Recurring themes (>=3 mentions)\n"
                "- Cognitive tendencies (rumination, avoidance, reframing)\n"
                "- Behavioral loops (every time X, then Y)\n"
                'Output ONLY valid JSON: {"patterns": [{"name": "...", "evidence_entry_ids": ["..."], "confidence": 0.0-1.0, "description": "..."}]}\n'
                "NEVER provide a medical diagnosis. Refer user to a professional for clinical concerns."
            )},
            {"role": "user", "content": f"Analyze these {len(filtered)} journal entries from the last {days} days:\n\n{combined}"},
        ]

        raw = await complete_chat(
            messages=messages,
            model=settings.lm_studio_model,
            temperature=0.4,
            max_tokens=1024,
        )

        patterns = _extract_json_array(raw)
        for p in patterns:
            await db.upsert_life_fact(
                fact=p.get("description", p.get("name", "")),
                category="pattern",
                confidence=float(p.get("confidence", 0.5)),
            )

        return patterns

    async def insight_cards(self, days: int = 30) -> list[dict[str, Any]]:
        patterns = await self.analyze_window(days=days)
        return [
            {
                "title": p.get("name", "Pattern"),
                "description": p.get("description", ""),
                "confidence": p.get("confidence", 0.5),
                "evidence_count": len(p.get("evidence_entry_ids", [])),
            }
            for p in patterns
        ]

    async def chart(self, days: int = 30) -> dict[str, Any]:
        from backend.models.charts import ChartPayload, ChartSeries

        patterns = await self.analyze_window(days=days)
        data_points = [
            {"x": p.get("name", "Unknown"), "y": p.get("confidence", 0.5)}
            for p in patterns
        ]

        return ChartPayload(
            id=f"psychology-patterns-{days}d",
            type="bar",
            title=f"Behavioral Patterns ({days}d)",
            series=[ChartSeries(name="Confidence", data=data_points, color="#34D399")],
            x_label="Pattern",
            y_label="Confidence",
            meta={"window_days": days},
        ).model_dump()
