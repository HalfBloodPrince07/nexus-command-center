"""
API endpoints for Goal Tracker (B2).

Routes:
- POST /api/goals - create goal
- GET /api/goals - list goals with computed progress
- PATCH /api/goals/{id} - update/pause/complete goal
- DELETE /api/goals/{id} - soft delete goal
- GET /api/goals/{id}/events - audit trail
- POST /api/goals/{id}/events - manual event entry
- GET /api/goals/pending-review - events with mid-confidence (0.4-0.7) for user review
- POST /api/goals/events/{event_id}/confirm - confirm detected event
- POST /api/goals/events/{event_id}/reject - reject detected event
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel

from backend.app.agents.proactive.goal_tracker import get_goal_tracker
from backend.core.database import Goal, GoalEvent, get_session

router = APIRouter(prefix="/api/goals", tags=["goals"])


# ── Pydantic models ──────────────────────────────────────────────────────────


class GoalCreateRequest(BaseModel):
    title: str
    description: Optional[str] = None
    metric_type: str
    target_value: float
    target_period: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class GoalUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class GoalResponse(BaseModel):
    id: str
    user_id: str
    title: str
    description: Optional[str]
    metric_type: str
    target_value: float
    target_period: str
    status: str
    progress_percent: float
    created_at: str


class GoalEventCreateRequest(BaseModel):
    value: float
    notes: Optional[str] = None
    confidence: float


class GoalEventResponse(BaseModel):
    id: str
    goal_id: str
    detected_from: str
    value: float
    timestamp: str
    notes: Optional[str]
    confidence: float


# ── Endpoints ───────────────────────────────────────────────────────────────


@router.post("", response_model=GoalResponse)
async def create_goal(body: GoalCreateRequest) -> GoalResponse:
    """Create a new goal."""
    try:
        async with get_session() as session:
            goal = Goal(
                id=str(uuid.uuid4()),
                user_id="user",  # TODO: Get from auth
                title=body.title,
                description=body.description,
                metric_type=body.metric_type,
                target_value=body.target_value,
                target_period=body.target_period,
                status="active",
            )
            session.add(goal)
            await session.commit()
            await session.refresh(goal)

            return GoalResponse(
                id=goal.id,
                user_id=goal.user_id,
                title=goal.title,
                description=goal.description,
                metric_type=goal.metric_type,
                target_value=goal.target_value,
                target_period=goal.target_period,
                status=goal.status,
                progress_percent=0.0,
                created_at=goal.created_at.isoformat(),
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create goal: {e}")


@router.get("", response_model=List[GoalResponse])
async def list_goals(status: Optional[str] = None) -> List[GoalResponse]:
    """List goals with computed progress."""
    try:
        async with get_session() as session:
            from sqlalchemy import select

            stmt = select(Goal)
            if status:
                stmt = stmt.where(Goal.status == status)
            stmt = stmt.order_by(Goal.created_at.desc())

            result = await session.execute(stmt)
            goals = result.scalars().all()

            # Compute progress for each goal
            responses = []
            for goal in goals:
                # Count events for this goal
                events_stmt = select(GoalEvent).where(GoalEvent.goal_id == goal.id)
                events_result = await session.execute(events_stmt)
                events = events_result.scalars().all()

                # Calculate progress percentage
                total_value = sum(event.value for event in events if event.value)
                progress_percent = (
                    (total_value / goal.target_value * 100)
                    if goal.target_value > 0
                    else 0.0
                )

                responses.append(
                    GoalResponse(
                        id=goal.id,
                        user_id=goal.user_id,
                        title=goal.title,
                        description=goal.description,
                        metric_type=goal.metric_type,
                        target_value=goal.target_value,
                        target_period=goal.target_period,
                        status=goal.status,
                        progress_percent=min(progress_percent, 100.0),
                        created_at=goal.created_at.isoformat(),
                    )
                )

            return responses
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list goals: {e}")


@router.patch("/{goal_id}", response_model=GoalResponse)
async def update_goal(
    goal_id: str = Path(...), body: GoalUpdateRequest = None
) -> GoalResponse:
    """Update a goal (can pause, resume, or complete it)."""
    try:
        async with get_session() as session:
            goal = await session.get(Goal, goal_id)
            if not goal:
                raise HTTPException(status_code=404, detail="Goal not found")

            if body.title is not None:
                goal.title = body.title
            if body.description is not None:
                goal.description = body.description
            if body.status in ["active", "paused", "completed", "abandoned"]:
                goal.status = body.status

            await session.commit()
            await session.refresh(goal)

            return GoalResponse(
                id=goal.id,
                user_id=goal.user_id,
                title=goal.title,
                description=goal.description,
                metric_type=goal.metric_type,
                target_value=goal.target_value,
                target_period=goal.target_period,
                status=goal.status,
                progress_percent=0.0,  # TODO: Compute actual progress
                created_at=goal.created_at.isoformat(),
            )
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update goal: {e}")


@router.delete("/{goal_id}")
async def delete_goal(goal_id: str = Path(...)) -> dict:
    """Soft delete a goal (keeps data but marks as deleted)."""
    try:
        async with get_session() as session:
            goal = await session.get(Goal, goal_id)
            if not goal:
                raise HTTPException(status_code=404, detail="Goal not found")

            # Soft delete by changing status
            goal.status = "abandoned"
            await session.commit()

            return {"id": goal_id, "status": "deleted"}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete goal: {e}")


@router.get("/{goal_id}/events", response_model=List[GoalEventResponse])
async def list_goal_events(goal_id: str = Path(...)) -> List[GoalEventResponse]:
    """Get audit trail of events for a goal."""
    try:
        async with get_session() as session:
            from sqlalchemy import select

            stmt = (
                select(GoalEvent)
                .where(GoalEvent.goal_id == goal_id)
                .order_by(GoalEvent.timestamp.desc())
            )
            result = await session.execute(stmt)
            events = result.scalars().all()

            return [
                GoalEventResponse(
                    id=event.id,
                    goal_id=event.goal_id,
                    detected_from=event.detected_from,
                    value=event.value or 0.0,
                    timestamp=event.timestamp.isoformat(),
                    notes=event.notes,
                    confidence=event.confidence or 0.0,
                )
                for event in events
            ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list goal events: {e}")


@router.post("/{goal_id}/events", response_model=GoalEventResponse)
async def create_goal_event(
    goal_id: str = Path(...), body: GoalEventCreateRequest = None
) -> GoalEventResponse:
    """Manually add a goal event."""
    try:
        async with get_session() as session:
            # Verify goal exists
            goal = await session.get(Goal, goal_id)
            if not goal:
                raise HTTPException(status_code=404, detail="Goal not found")

            event = GoalEvent(
                id=str(uuid.uuid4()),
                goal_id=goal_id,
                detected_from="manual",
                value=body.value,
                notes=body.notes,
                confidence=body.confidence,
            )
            session.add(event)
            await session.commit()
            await session.refresh(event)

            return GoalEventResponse(
                id=event.id,
                goal_id=event.goal_id,
                detected_from=event.detected_from,
                value=event.value or 0.0,
                timestamp=event.timestamp.isoformat(),
                notes=event.notes,
                confidence=event.confidence or 0.0,
            )
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create goal event: {e}")


@router.get("/pending-review", response_model=List[GoalEventResponse])
async def get_pending_review_events() -> List[GoalEventResponse]:
    """Get auto-detected events with mid-confidence (0.4-0.7) for user review."""
    try:
        async with get_session() as session:
            from sqlalchemy import select

            # Get events with confidence between 0.4 and 0.7 (mid-confidence range)
            stmt = (
                select(GoalEvent)
                .where(GoalEvent.confidence >= 0.4)
                .where(GoalEvent.confidence < 0.7)
                .where(GoalEvent.detected_from != "manual")
                .order_by(GoalEvent.timestamp.desc())
            )
            result = await session.execute(stmt)
            events = result.scalars().all()

            return [
                GoalEventResponse(
                    id=event.id,
                    goal_id=event.goal_id,
                    detected_from=event.detected_from,
                    value=event.value or 0.0,
                    timestamp=event.timestamp.isoformat(),
                    notes=event.notes,
                    confidence=event.confidence or 0.0,
                )
                for event in events
            ]
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch pending events: {e}"
        )


@router.post("/events/{event_id}/confirm", response_model=dict)
async def confirm_goal_event(event_id: str = Path(...)) -> dict:
    """Confirm a detected goal event (confidence promotion)."""
    try:
        from sqlalchemy import update

        async with get_session() as session:
            stmt = select(GoalEvent).where(GoalEvent.id == event_id)
            result = await session.execute(stmt)
            event = result.scalar_one_or_none()

            if not event:
                raise HTTPException(status_code=404, detail="Event not found")

            # Promote confidence to 0.8 (high confidence range)
            event.confidence = 0.8
            await session.commit()

            return {"id": event_id, "status": "confirmed", "confidence": 0.8}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to confirm goal event: {e}"
        )


@router.post("/events/{event_id}/reject", response_model=dict)
async def reject_goal_event(event_id: str = Path(...)) -> dict:
    """Reject a detected goal event (confidence demotion)."""
    try:
        from sqlalchemy import delete

        async with get_session() as session:
            stmt = select(GoalEvent).where(GoalEvent.id == event_id)
            result = await session.execute(stmt)
            event = result.scalar_one_or_none()

            if not event:
                raise HTTPException(status_code=404, detail="Event not found")

            # Delete the event instead of just lowering confidence
            # Alternative: could mark as rejected instead of delete
            await session.delete(event)
            await session.commit()

            return {"id": event_id, "status": "rejected"}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reject goal event: {e}")
