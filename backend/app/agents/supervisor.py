from __future__ import annotations

import logging
import uuid
import re
from typing import AsyncGenerator, Union

import httpx

from backend.app.agents._lm_studio import stream_chat_completion
from backend.app.agents.journal.journal_lead import JournalLeadAgent
from backend.app.agents.journal.mood_analyst import MoodAnalystAgent
from backend.config import settings
from backend.core import database as db_module
from backend.core.personality import get_system_prompt, get_temperature_modifier, inject_tone
from backend.core.resilience import LLMUnavailable, degraded_event

logger = logging.getLogger(__name__)

class Supervisor:
    JOURNAL_PATTERNS = [
        r"\b(journal|diary|mood|feel|feeling|emotions?|how am i)\b",
        r"\b(patterns?|tendencies|habits?|recurring|themes?)\b",
        r"\b(people|talked about|mentioned|relationships?|interaction|friends?|colleagues?|family)\b",
        r"\b(should i|decision|decide|choose|pros and cons|analysis)\b"
    ]

    def __init__(self):
        self.journal_lead = JournalLeadAgent()
        self.mood_analyst = MoodAnalystAgent()

    def classify_intent(self, message: str) -> str:
        lowered = message.lower()
        if any(re.search(p, lowered) for p in self.JOURNAL_PATTERNS):
            return "journal"
        return "general"

    async def stream_response(
        self,
        user_message: str,
        conversation_id: str,
        model: str | None = None,
        user_id: str | None = None,
    ) -> AsyncGenerator[Union[str, dict], None]:
        intent = self.classify_intent(user_message)
        mood_context = await self._get_mood_context(user_id or conversation_id)
        
        if intent == "journal":
            async for event in self.journal_lead.route_query(user_message, mood_context=mood_context):
                yield event
            return

        messages: list[dict[str, str]] = []

        if db_module.database is not None:
            try:
                history = await db_module.get_conversation_history(conversation_id, limit=20)
                for item in history:
                    messages.append(
                        {
                            "role": item["role"],
                            "content": item["content"],
                        }
                    )
            except Exception as exc:
                logger.debug("Failed to load history for %s: %s", conversation_id, exc)

        messages.append({"role": "user", "content": user_message})

        try:
            system_prompt = get_system_prompt("supervisor")
        except Exception:
            system_prompt = "You are a helpful AI assistant. Be concise and accurate."
        injected_prompt = inject_tone(system_prompt, mood_context)
        if injected_prompt != system_prompt:
            logger.debug(
                "Injected tone directive for mood=%s confidence=%s",
                (mood_context or {}).get("mood"),
                (mood_context or {}).get("confidence"),
            )
        system_prompt = injected_prompt
        payload = [{"role": "system", "content": system_prompt}] + messages
        temperature = max(0.0, min(1.0, 0.7 + get_temperature_modifier(mood_context)))

        full_response = ""
        try:
            async for token in stream_chat_completion(
                messages=payload,
                model=model or settings.lm_studio_model,
                temperature=temperature,
                max_tokens=settings.SUPERVISOR_MAX_TOKENS,
            ):
                full_response += token
                yield token
        except (LLMUnavailable, httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as exc:
            logger.warning("Supervisor degraded because LM Studio is unavailable", extra={"error": str(exc)})
            yield degraded_event(
                "Nexus",
                "llm_unavailable",
                "Supervisor could not reach LM Studio.",
            )
            yield "I can't reach the local model right now — start LM Studio and try again."
            return
        except Exception as exc:
            logger.warning("Supervisor response failed", extra={"error": str(exc)})
            yield degraded_event("Nexus", "response_failed", str(exc))
            yield "I can't complete that response right now. Please try again."
            return

        if db_module.database is not None and full_response:
            try:
                await db_module.save_message(
                    conversation_id,
                    "assistant",
                    full_response,
                    agent_id="supervisor",
                )
            except Exception as exc:
                logger.debug("Failed to persist supervisor turn for %s: %s", conversation_id, exc)

    async def _get_mood_context(self, user_id: str) -> dict:
        if not getattr(settings, "dynamic_personality_enabled", True):
            return {"mood": "neutral", "confidence": 1.0, "recent_topics": []}
        try:
            mood = await self.mood_analyst.get_current_mood(user_id)
        except Exception as exc:
            logger.warning("Mood Analyst unavailable; falling back to neutral tone: %s", exc)
            return {"mood": "neutral", "confidence": 0.0, "recent_topics": []}
        if not isinstance(mood, dict):
            logger.warning("Mood Analyst returned invalid mood context; falling back to neutral")
            return {"mood": "neutral", "confidence": 0.0, "recent_topics": []}
        if float(mood.get("confidence", 0.0) or 0.0) < 0.4:
            return {"mood": "neutral", "confidence": float(mood.get("confidence", 0.0) or 0.0), "recent_topics": mood.get("recent_topics", [])}
        return mood


supervisor = Supervisor()
