from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.app.agents._lm_studio import complete_chat
from backend.config import settings
from backend.core import database as db

logger = logging.getLogger(__name__)

_LEXICON: list[str] | None = None


def _load_lexicon() -> list[str]:
    global _LEXICON
    if _LEXICON is not None:
        return _LEXICON
    try:
        import pathlib
        path = pathlib.Path(__file__).parent / "lexicon" / "mood_lexicon.json"
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        _LEXICON = [e for family in data.values() for e in family]
    except Exception:
        _LEXICON = []
    return _LEXICON


def _extract_json(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return {}


class MoodAnalystAgent:
    async def get_current_mood(self, user_id: str) -> dict[str, Any]:
        """Infer the user's current mood from journal entries in the last 48 hours."""
        start = datetime.now(timezone.utc) - timedelta(hours=48)
        try:
            entries = await db.list_journal_entries(limit=20, start_date=start)
        except Exception as exc:
            logger.warning("Could not read recent journal entries for mood context: %s", exc)
            return {"mood": "neutral", "confidence": 0.0, "recent_topics": []}

        if not entries:
            return {"mood": "neutral", "confidence": 0.0, "recent_topics": []}

        scores: list[int] = []
        confidences: list[float] = []
        emotions: list[str] = []
        topic_words: dict[str, int] = {}

        for entry in entries:
            full_entry = None
            try:
                full_entry = await db.get_journal_entry(str(entry["id"]))
            except Exception:
                full_entry = None

            mood = (full_entry or {}).get("mood") if full_entry else None
            if mood:
                try:
                    scores.append(int(mood.get("score", 5)))
                except (TypeError, ValueError):
                    pass
                raw_emotions = mood.get("emotions") or []
                if isinstance(raw_emotions, str):
                    try:
                        raw_emotions = json.loads(raw_emotions)
                    except json.JSONDecodeError:
                        raw_emotions = [raw_emotions]
                emotions.extend(str(e).lower() for e in raw_emotions)
                confidence = mood.get("confidence")
                if confidence is not None:
                    try:
                        confidences.append(float(confidence))
                    except (TypeError, ValueError):
                        pass

            text = f"{entry.get('title') or ''} {entry.get('body_md') or ''}".lower()
            for word in re.findall(r"[a-z][a-z0-9_-]{3,}", text):
                if word in {"this", "that", "with", "from", "have", "been", "about", "today", "journal"}:
                    continue
                topic_words[word] = topic_words.get(word, 0) + 1

        avg_score = sum(scores) / len(scores) if scores else 6.0
        emotion_set = set(emotions)
        if emotion_set & {"stressed", "stress", "anxious", "overwhelmed", "worried", "tense"}:
            mood_name = "stressed"
        elif emotion_set & {"excited", "energized", "eager", "enthusiastic"} or avg_score >= 8:
            mood_name = "excited"
        elif avg_score <= 4:
            mood_name = "low"
        elif emotion_set & {"focused", "productive", "calm"} or 6 <= avg_score < 8:
            mood_name = "focused"
        else:
            mood_name = "neutral"

        score_confidence = min(1.0, 0.45 + 0.1 * len(scores))
        confidence = sum(confidences) / len(confidences) if confidences else score_confidence
        recent_topics = [
            word for word, _ in sorted(topic_words.items(), key=lambda item: item[1], reverse=True)[:5]
        ]

        return {
            "mood": mood_name,
            "confidence": round(float(confidence), 3),
            "recent_topics": recent_topics,
        }

    async def analyze(self, entry_id: str, body: str) -> dict[str, Any]:
        lexicon = _load_lexicon()
        lexicon_str = ", ".join(lexicon[:40]) if lexicon else "happy, sad, anxious, angry, calm, excited"

        messages = [
            {"role": "system", "content": (
                "You are Lumen, a mood analyst. Given a journal entry, output ONLY valid JSON:\n"
                '{"score": <1-10>, "emotions": ["..."], "confidence": <0.0-1.0>, "reasoning": "..."}\n'
                "Score rubric: 1-3=very low mood, 4-5=low, 6=neutral, 7-8=good, 9-10=excellent.\n"
                f"Choose emotions from: {lexicon_str}\n"
                "Never diagnose clinical conditions."
            )},
            {"role": "user", "content": f"Analyze this journal entry:\n\n{body[:3000]}"},
        ]

        raw = await complete_chat(
            messages=messages,
            model=settings.lm_studio_model,
            temperature=0.3,
            max_tokens=512,
        )

        result = _extract_json(raw)
        score = max(settings.MOOD_MIN, min(settings.MOOD_MAX, int(result.get("score", 5))))
        emotions = result.get("emotions", [])
        if isinstance(emotions, str):
            emotions = [e.strip() for e in emotions.split(",")]
        confidence = float(result.get("confidence", 0.5))

        await db.upsert_mood(
            entry_id=entry_id,
            score=score,
            emotions=json.dumps(emotions),
            confidence=confidence,
            model=settings.lm_studio_model,
        )

        return {
            "entry_id": entry_id,
            "score": score,
            "emotions": emotions,
            "confidence": confidence,
            "reasoning": result.get("reasoning", ""),
        }

    async def trend(self, window_days: int = 30) -> dict[str, Any]:
        from backend.models.charts import ChartPayload, ChartSeries

        series_data = await db.get_mood_series(days=window_days)
        data_points = [
            {"x": str(d["date"].date()) if hasattr(d["date"], "date") else str(d["date"]), "y": d["score"]}
            for d in series_data
        ]

        return ChartPayload(
            id=f"mood-trend-{window_days}d",
            type="line",
            title=f"Mood Trend ({window_days}d)",
            series=[ChartSeries(name="Mood Score", data=data_points, color="#6366F1")],
            x_label="Date",
            y_label="Score (1-10)",
            meta={"window_days": window_days, "reference_line": 6},
        ).model_dump()

    async def calendar(self, year: int) -> dict[str, Any]:
        from backend.models.charts import ChartPayload, ChartSeries

        series_data = await db.get_mood_series(days=366)
        data_points = [
            {"date": str(d["date"].date()) if hasattr(d["date"], "date") else str(d["date"]), "value": d["score"]}
            for d in series_data
            if (hasattr(d["date"], "year") and d["date"].year == year)
            or str(d["date"]).startswith(str(year))
        ]

        return ChartPayload(
            id=f"mood-calendar-{year}",
            type="calendar",
            title=f"Mood Calendar {year}",
            series=[ChartSeries(name="Daily Mood", data=data_points)],
            meta={"year": year, "color_scale": ["#3b0a0a", "#b91c1c", "#f59e0b", "#84cc16", "#22c55e"]},
        ).model_dump()
