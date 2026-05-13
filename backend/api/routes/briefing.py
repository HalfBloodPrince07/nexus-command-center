"""
API endpoints for Smart Daily Briefing (B1).

Routes:
- POST /api/briefing/generate — manual trigger
- GET /api/briefing/latest — today's briefing if generated
- GET /api/briefing/history?days=30 — archive
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.app.agents.proactive.smart_daily_briefing_agent import get_briefing_agent
from backend.core.database import Briefing, get_session

router = APIRouter(prefix="/api/briefing", tags=["briefing"])


# ── Pydantic models ─────────────────────────────────────────────────────────


class BriefingResponse(BaseModel):
    """Briefing response model."""

    id: str
    created_at: str
    body_md: str
    mood_summary: Optional[str]
    insights: Optional[List[dict]]
    mood_trend_direction: Optional[str]
    pending_research: Optional[List[dict]]
    new_files_count: Optional[int]
    top_3_files: Optional[List[dict]]
    predictive_patterns: Optional[List[dict]]
    goals_progress: Optional[List[dict]]
    suggested_focus: Optional[str]
    tags: str


class BriefingHistoryRequest(BaseModel):
    """Query params for briefing history."""

    days: int = Query(default=30, ge=1, le=365)


# ── Endpoints ───────────────────────────────────────────────────────────────


@router.post("/generate", response_model=BriefingResponse)
async def generate_briefing() -> BriefingResponse:
    """
    Manually trigger a briefing generation.

    Returns the newly generated briefing with all 7 sections populated.
    Persists to database and sends WebSocket notification.
    """
    try:
        agent = await get_briefing_agent()
        briefing = await agent.generate_briefing(save_to_journal=False)

        return BriefingResponse(
            id=briefing["id"],
            created_at=briefing["created_at"],
            body_md=briefing["body_md"],
            mood_summary=briefing.get("mood_summary"),
            insights=briefing.get("insights"),
            mood_trend_direction=briefing.get("mood_trend", {}).get("direction"),
            pending_research=briefing.get("pending_research"),
            new_files_count=briefing.get("new_files", {}).get("count"),
            top_3_files=briefing.get("top_3_files"),
            predictive_patterns=briefing.get("patterns"),
            goals_progress=briefing.get("goals_progress"),
            suggested_focus=briefing.get("suggested_focus"),
            tags="briefing",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate briefing: {e}")


@router.get("/latest", response_model=Optional[BriefingResponse])
async def get_latest_briefing() -> Optional[BriefingResponse]:
    """Get today's briefing if it has been generated. Returns null if not yet generated."""
    try:
        today = datetime.now(timezone.utc).date()
        async with get_session() as session:
            from sqlalchemy import select

            stmt = (
                select(Briefing)
                .where(func.date(Briefing.created_at) == today)
                .order_by(Briefing.created_at.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            briefing = result.scalar_one_or_none()

            if not briefing:
                return None

            return BriefingResponse(
                id=briefing.id,
                created_at=briefing.created_at.isoformat(),
                body_md=briefing.body_md,
                mood_summary=briefing.mood_summary,
                insights=[],  # Parse from insights_json if needed
                mood_trend_direction=briefing.mood_trend_direction,
                pending_research=[],  # Parse from pending_research_json
                new_files_count=briefing.new_files_count,
                top_3_files=[],  # Parse from top_3_files_json
                predictive_patterns=[],  # Parse from predictive_patterns_json
                goals_progress=[],  # Parse from goals_progress_json
                suggested_focus=briefing.suggested_focus,
                tags=briefing.tags,
            )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve latest briefing: {e}"
        )


@router.get("/history", response_model=List[BriefingResponse])
async def get_briefing_history(
    days: int = Query(default=30, ge=1, le=365),
) -> List[BriefingResponse]:
    """Get briefing history for the past N days."""
    try:
        async with get_session() as session:
            from sqlalchemy import select

            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            stmt = (
                select(Briefing)
                .where(Briefing.created_at >= cutoff)
                .order_by(Briefing.created_at.desc())
            )
            result = await session.execute(stmt)
            briefings = result.scalars().all()

            return [
                BriefingResponse(
                    id=b.id,
                    created_at=b.created_at.isoformat(),
                    body_md=b.body_md,
                    mood_summary=b.mood_summary,
                    insights=[],  # Parse JSON fields as needed
                    mood_trend_direction=b.mood_trend_direction,
                    pending_research=[],  # Parse from JSON
                    new_files_count=b.new_files_count,
                    top_3_files=[],  # Parse from JSON
                    predictive_patterns=[],  # Parse from JSON
                    goals_progress=[],  # Parse from JSON
                    suggested_focus=b.suggested_focus,
                    tags=b.tags,
                )
                for b in briefings
            ]
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve briefing history: {e}"
        )
