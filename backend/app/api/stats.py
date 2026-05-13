from __future__ import annotations

import asyncio

from fastapi import APIRouter

from backend.core.database import get_today_stats, get_weekly_stats

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/conversation")
async def get_conversation_stats() -> dict:
    today, weekly = await asyncio.gather(get_today_stats(), get_weekly_stats())
    return {**today, "weekly_messages": weekly}
