from __future__ import annotations

import pytest

from backend.app.agents.supervisor import Supervisor
from backend.config import settings
from backend.core.personality import PersonalityManager


@pytest.fixture
def personality_manager() -> PersonalityManager:
    return PersonalityManager(settings.PERSONALITIES_DIR, settings.ACTIVE_PERSONALITY)


def test_each_mood_produces_configured_directive(personality_manager: PersonalityManager) -> None:
    base = "Base system prompt."
    cases = {
        "stressed": "User appears stressed.",
        "focused": "deep-work mode",
        "low": "low-energy",
        "excited": "User is energized.",
    }

    for mood, expected in cases.items():
        prompt = personality_manager.inject_tone(base, {"mood": mood, "confidence": 0.9})
        assert "## Tone & Approach" in prompt
        assert expected in prompt

    neutral = personality_manager.inject_tone(base, {"mood": "neutral", "confidence": 0.9})
    assert neutral == base


def test_low_confidence_uses_neutral(personality_manager: PersonalityManager) -> None:
    prompt = personality_manager.inject_tone(
        "Base system prompt.",
        {"mood": "stressed", "confidence": 0.39},
    )
    assert "## Tone & Approach" not in prompt


async def test_missing_mood_analyst_falls_back_gracefully() -> None:
    supervisor = Supervisor()

    async def fail(_: str):
        raise RuntimeError("mood service unavailable")

    supervisor.mood_analyst.get_current_mood = fail
    mood = await supervisor._get_mood_context("user-1")

    assert mood["mood"] == "neutral"
    assert mood["confidence"] == 0.0


def test_disabled_flag_bypasses_injection(
    personality_manager: PersonalityManager,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "dynamic_personality_enabled", False)

    prompt = personality_manager.inject_tone(
        "Base system prompt.",
        {"mood": "excited", "confidence": 0.9},
    )

    assert prompt == "Base system prompt."
