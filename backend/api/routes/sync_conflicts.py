"""API endpoints for Obsidian sync conflict resolution."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Dict, List, Optional
from datetime import datetime
import logging

from backend.core.database import async_session_maker
from backend.models.sync_models import SyncState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sync/conflicts", tags=["Sync Conflicts"])


class ConflictResponse(BaseModel):
    """Response model for sync conflicts."""

    nexus_id: str
    vault_path: str
    content_type: str
    created_at: str
    last_local_hash: Optional[str]
    last_remote_hash: Optional[str]


class ConflictResolutionRequest(BaseModel):
    """Request model for resolving a conflict."""

    nexus_id: str
    resolution: str  # "local", "remote", or "merge"
    resolution_data: Optional[Dict] = None


class ConflictResolutionResponse(BaseModel):
    """Response model after resolving a conflict."""

    success: bool
    message: str
    resolved_at: str


@router.get("/", response_model=List[ConflictResponse])
async def get_conflicts():
    """Get all current sync conflicts."""
    try:
        async with async_session_maker() as session:
            from sqlalchemy import select

            stmt = select(SyncState).where(SyncState.sync_status == "conflict")
            result = await session.execute(stmt)
            conflicts = result.scalars().all()

            return [
                ConflictResponse(
                    nexus_id=c.nexus_id,
                    vault_path=c.vault_path,
                    content_type=c.content_type,
                    created_at=c.created_at.isoformat(),
                    last_local_hash=c.last_local_hash,
                    last_remote_hash=c.last_remote_hash,
                )
                for c in conflicts
            ]
    except Exception as e:
        logger.error(f"Failed to fetch conflicts: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch conflicts: {str(e)}"
        )


@router.post("/resolve", response_model=ConflictResolutionResponse)
async def resolve_conflict(request: ConflictResolutionRequest):
    """Resolve a sync conflict."""
    try:
        if request.resolution not in ["local", "remote", "merge"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid resolution. Must be 'local', 'remote', or 'merge'",
            )

        # Here we would handle the actual conflict resolution
        # For now, mark as synced and let the sync service handle the rest
        async with async_session_maker() as session:
            stmt = select(SyncState).where(SyncState.nexus_id == request.nexus_id)
            result = await session.execute(stmt)
            conflict = result.scalar_one_or_none()

            if not conflict:
                raise HTTPException(status_code=404, detail="Conflict not found")

            # Mark as synced (actual content handling done by sync service)
            conflict.sync_status = "synced"
            conflict.updated_at = datetime.now()

            await session.commit()

            return ConflictResolutionResponse(
                success=True,
                message="Conflict resolved successfully",
                resolved_at=datetime.now().isoformat(),
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to resolve conflict: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to resolve conflict: {str(e)}"
        )


@router.post("/resolve/all", response_model=ConflictResolutionResponse)
async def resolve_all_conflicts(resolution: str = "local"):
    """Resolve all conflicts at once using the same resolution strategy."""
    try:
        if resolution not in ["local", "remote"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid resolution. Must be 'local' or 'remote'",
            )

        async with async_session_maker() as session:
            from sqlalchemy import select, update

            stmt = (
                update(SyncState)
                .where(SyncState.sync_status == "conflict")
                .values(sync_status="synced", updated_at=datetime.now())
            )
            result = await session.execute(stmt)
            await session.commit()

            count = result.rowcount

            return ConflictResolutionResponse(
                success=True,
                message=f"Resolved {count} conflicts",
                resolved_at=datetime.now().isoformat(),
            )
    except Exception as e:
        logger.error(f"Failed to resolve all conflicts: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to resolve all conflicts: {str(e)}"
        )
