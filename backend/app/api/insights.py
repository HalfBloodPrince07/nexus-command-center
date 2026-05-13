from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from backend.core import database as db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/insights", tags=["insights"])


@router.get("")
async def list_insights(
    unread: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
):
    items = await db.list_insights(unread_only=unread, limit=limit)
    return {"insights": items, "count": len(items)}


@router.post("/{insight_id}/read")
async def mark_read(insight_id: str):
    async with db.get_session() as session:
        from backend.core.database import Insight
        row = await session.get(Insight, insight_id)
        if not row:
            raise HTTPException(status_code=404, detail="Insight not found")
        row.read_at = datetime.now(timezone.utc)
        await session.flush()
    return {"status": "read", "id": insight_id}


@router.delete("/{insight_id}")
async def dismiss_insight(insight_id: str):
    async with db.get_session() as session:
        from sqlalchemy import delete as sql_delete
        from backend.core.database import Insight
        result = await session.execute(sql_delete(Insight).where(Insight.id == insight_id))
        await session.flush()
        if not result.rowcount:
            raise HTTPException(status_code=404, detail="Insight not found")
    return {"status": "dismissed", "id": insight_id}


@router.get("/briefings/today")
async def today_briefing():
    async with db.get_session() as session:
        from sqlalchemy import select, func
        from backend.core.database import Briefing
        today = datetime.now(timezone.utc).date()
        row = (await session.execute(
            select(Briefing).where(func.date(Briefing.created_at) == str(today)).order_by(Briefing.created_at.desc()).limit(1)
        )).scalars().first()
        if not row:
            return {"briefing": None}
        return {
            "briefing": {
                "id": row.id,
                "body_md": row.body_md,
                "hero_chart": row.hero_chart_json,
                "mood_summary": row.mood_summary,
                "created_at": row.created_at,
            }
        }


@router.get("/briefings")
async def list_briefings(limit: int = Query(30, ge=1, le=100)):
    async with db.get_session() as session:
        from sqlalchemy import select
        from backend.core.database import Briefing
        rows = (await session.execute(
            select(Briefing).order_by(Briefing.created_at.desc()).limit(limit)
        )).scalars().all()
        return {"briefings": [
            {"id": b.id, "body_md": b.body_md, "created_at": b.created_at, "mood_summary": b.mood_summary}
            for b in rows
        ]}


@router.post("/scheduler/trigger/{job_name}")
async def trigger_job(job_name: str):
    try:
        from backend.app.core.scheduler import nexus_scheduler
        await nexus_scheduler.trigger(job_name)
        return {"status": "triggered", "job": job_name}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/scheduler/jobs")
async def scheduler_jobs():
    async with db.get_session() as session:
        from sqlalchemy import select
        from backend.core.database import ScheduledJob
        rows = (await session.execute(
            select(ScheduledJob).order_by(ScheduledJob.started_at.desc()).limit(50)
        )).scalars().all()
        return {"jobs": [
            {"id": j.id, "name": j.name, "started_at": j.started_at, "completed_at": j.completed_at, "status": j.status, "error": j.error}
            for j in rows
        ]}
