from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.app.agents.journal.journal_lead import JournalLeadAgent
from backend.app.agents.journal.mood_analyst import MoodAnalystAgent
from backend.app.agents.journal.psychology_agent import PsychologyAgent
from backend.app.agents.journal.relationship_finder import RelationshipFinderAgent
from backend.app.agents.journal.life_decisions import LifeDecisionsAgent
from backend.core import database as db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/journal", tags=["journal"])

_journal_lead = JournalLeadAgent()
_mood = MoodAnalystAgent()
_psychology = PsychologyAgent()
_relationships = RelationshipFinderAgent()
_decisions = LifeDecisionsAgent()


class CreateEntryRequest(BaseModel):
    body_md: str
    title: str | None = None


class DecisionRequest(BaseModel):
    question: str


class OutcomeRequest(BaseModel):
    outcome: str


@router.post("")
async def create_entry(req: CreateEntryRequest):
    entry_id = str(uuid.uuid4())
    result = await _journal_lead.on_new_entry(entry_id, req.body_md, req.title)
    entry = await db.get_journal_entry(entry_id)
    return {"entry": entry, "analysis": result}


@router.get("")
async def list_entries(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    start: str | None = None,
    end: str | None = None,
):
    start_dt = datetime.fromisoformat(start) if start else None
    end_dt = datetime.fromisoformat(end) if end else None
    entries = await db.list_journal_entries(limit=limit, offset=offset, start_date=start_dt, end_date=end_dt)
    return {"entries": entries, "count": len(entries)}


@router.get("/mood/trend")
async def mood_trend(window: int = Query(30, ge=1, le=365)):
    return await _mood.trend(window_days=window)


@router.get("/mood/calendar")
async def mood_calendar(year: int = Query(default=None)):
    if year is None:
        year = datetime.now().year
    return await _mood.calendar(year)


@router.get("/insights")
async def journal_insights(window: int = Query(30, ge=1, le=365)):
    cards = await _psychology.insight_cards(days=window)
    return {"insights": cards, "window_days": window}


@router.get("/relationships")
async def relationships_graph():
    return await _relationships.graph()


@router.get("/relationships/{name}")
async def relationship_detail(name: str):
    async with db.get_session() as session:
        from sqlalchemy import select
        from backend.core.database import Relationship, Interaction
        rel = (await session.execute(select(Relationship).where(Relationship.name == name))).scalars().first()
        if not rel:
            raise HTTPException(status_code=404, detail="Person not found")
        interactions = (await session.execute(
            select(Interaction).where(Interaction.relationship_id == rel.id).order_by(Interaction.occurred_at.desc()).limit(50)
        )).scalars().all()
        return {
            "id": rel.id,
            "name": rel.name,
            "relation_type": rel.relation_type,
            "sentiment_avg": rel.sentiment_avg,
            "interaction_count": rel.interaction_count,
            "interactions": [
                {"id": i.id, "sentiment": i.sentiment, "snippet": i.snippet, "occurred_at": i.occurred_at}
                for i in interactions
            ],
        }


@router.post("/decisions")
async def start_decision(req: DecisionRequest):
    results = []
    async for event in _decisions.analyze(req.question):
        results.append(event)
    final = results[-1] if results else {}
    return final


@router.get("/decisions")
async def list_decisions():
    async with db.get_session() as session:
        from sqlalchemy import select
        from backend.core.database import Decision
        rows = (await session.execute(select(Decision).order_by(Decision.created_at.desc()).limit(50))).scalars().all()
        return {"decisions": [
            {"id": d.id, "question": d.question, "status": d.status, "created_at": d.created_at}
            for d in rows
        ]}


@router.get("/decisions/{decision_id}")
async def get_decision(decision_id: str):
    async with db.get_session() as session:
        from backend.core.database import Decision
        dec = await session.get(Decision, decision_id)
        if not dec:
            raise HTTPException(status_code=404, detail="Decision not found")
        return {
            "id": dec.id,
            "question": dec.question,
            "status": dec.status,
            "analysis": json.loads(dec.analysis_json) if dec.analysis_json else None,
            "chosen_option": dec.chosen_option,
            "outcome": dec.outcome,
            "created_at": dec.created_at,
            "completed_at": dec.completed_at,
        }


@router.post("/decisions/{decision_id}/outcome")
async def record_outcome(decision_id: str, req: OutcomeRequest):
    await _decisions.record_outcome(decision_id, req.outcome)
    return {"status": "recorded", "decision_id": decision_id}


@router.get("/{entry_id}")
async def get_entry(entry_id: str):
    entry = await db.get_journal_entry(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    return entry


@router.delete("/{entry_id}")
async def delete_entry(entry_id: str):
    deleted = await db.delete_journal_entry(entry_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"status": "deleted", "entry_id": entry_id}
