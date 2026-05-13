from __future__ import annotations

import asyncio
import logging

from backend.app.memory.episodic import EpisodicMemory
from backend.app.memory.procedural import ProceduralMemory
from backend.app.memory.semantic import SemanticMemory

logger = logging.getLogger(__name__)


class MemoryManager:
    def __init__(self) -> None:
        self.episodic = EpisodicMemory()
        self.semantic = SemanticMemory()
        self.procedural = ProceduralMemory()

    async def remember_interaction(
        self,
        session_id: str,
        user_msg: str,
        assistant_msg: str,
    ) -> None:
        try:
            summary = f"{user_msg} -> {(assistant_msg or '')[:200]}"
            await self.episodic.store(
                session_id=session_id,
                event_type="interaction",
                content=summary,
                metadata={"user_len": len(user_msg or ""), "assistant_len": len(assistant_msg or "")},
            )
        except Exception as e:
            logger.warning("remember_interaction episodic failed: %s", e)

        try:
            await self.semantic.extract_and_store(session_id, user_msg, assistant_msg)
        except Exception as e:
            logger.warning("remember_interaction semantic failed: %s", e)

    async def get_full_stats(self) -> dict:
        try:
            episodic, semantic, procedural = await asyncio.gather(
                self.episodic.get_stats(),
                self.semantic.get_stats(),
                self.procedural.get_stats(),
                return_exceptions=True,
            )

            def _safe(val, fallback):
                if isinstance(val, Exception):
                    logger.warning("Stats subsystem failed: %s", val)
                    return fallback
                return val

            return {
                "episodic": _safe(episodic, {"total": 0, "available": False}),
                "semantic": _safe(semantic, {"total": 0, "available": False}),
                "procedural": _safe(procedural, {"total": 0, "by_type": {}}),
            }
        except Exception as e:
            logger.warning("get_full_stats failed: %s", e)
            return {
                "episodic": {"total": 0, "available": False},
                "semantic": {"total": 0, "available": False},
                "procedural": {"total": 0, "by_type": {}},
            }

    async def close(self) -> None:
        try:
            await self.episodic.close()
        except Exception:
            pass


memory_manager = MemoryManager()
