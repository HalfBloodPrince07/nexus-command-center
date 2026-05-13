"""Folder watching endpoints for background file watching."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.config import settings
from backend.core import database as db_module
from backend.core.file_watcher import get_file_watcher

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/folders", tags=["folders"])


# ── Request/Response models ───────────────────────────────────────────────────


class WatchFolderRequest(BaseModel):
    path: str
    collection: str = "files"


class WatchedFolderResponse(BaseModel):
    id: str
    path: str
    collection: str
    is_active: bool
    created_at: str


class WatchStatusResponse(BaseModel):
    is_running: bool
    is_paused: bool
    watched_folders: list[dict[str, Any]]
    total_pending_files: int


# ── Prerequisites ─────────────────────────────────────────────────────────────


def _require_database():
    if db_module.database is None:
        raise RuntimeError("Database is not initialized")
    return db_module.database


# ── Folder watching endpoints ─────────────────────────────────────────────────


@router.post("/watch", response_model=dict)
async def add_watched_folder(body: WatchFolderRequest):
    """Add a folder path for automatic file ingestion.

    The folder will be monitored recursively for new files with supported extensions.
    Files will be automatically deduplicated using SHA256 hash and ingested into the
    specified collection.
    """
    folder = Path(body.path)

    # Validate folder exists and is readable
    if not folder.exists():
        raise HTTPException(status_code=400, detail=f"Path does not exist: {body.path}")
    if not folder.is_dir():
        raise HTTPException(
            status_code=400, detail=f"Path is not a directory: {body.path}"
        )

    try:
        # Test read permission
        next(folder.iterdir(), None)
    except PermissionError:
        raise HTTPException(
            status_code=403, detail=f"No read permission for folder: {body.path}"
        )

    db = _require_database()
    watcher = await get_file_watcher()

    # Check if folder is already being watched
    existing = await db.get_watched_folder(str(folder.resolve()))
    if existing:
        if existing["is_active"]:
            raise HTTPException(
                status_code=409, detail=f"Folder is already being watched: {body.path}"
            )
        # Reactivate existing watcher
        await db.remove_watched_folder(str(folder.resolve()))

    try:
        # Add to file watcher
        watcher_id = await watcher.add_folder(str(folder), body.collection)

        logger.info("Folder added for watching: %s", str(folder.resolve()))

        return {
            "watcher_id": watcher_id,
            "path": str(folder.resolve()),
            "collection": body.collection,
            "status": "watching",
        }

    except Exception as e:
        logger.error("Failed to add folder watcher for %s: %s", body.path, e)
        raise HTTPException(
            status_code=500, detail=f"Failed to add folder watcher: {e}"
        )


@router.delete("/watch/{watcher_id}", response_model=dict)
async def remove_watched_folder(watcher_id: str):
    """Stop watching a folder and remove it from the database."""
    db = _require_database()
    watcher = await get_file_watcher()

    # Verify watcher exists
    folder = await db.get_watched_folder(watcher_id)
    if not folder:
        raise HTTPException(status_code=404, detail="Watcher not found")

    try:
        # Remove from file watcher if running
        if watcher.is_running:
            await watcher.remove_folder(watcher_id)

        # Remove from database
        await db.remove_watched_folder(watcher_id)

        logger.info("Folder watcher removed: %s", watcher_id)

        return {"watcher_id": watcher_id, "status": "stopped"}

    except Exception as e:
        logger.error("Failed to remove folder watcher %s: %s", watcher_id, e)
        raise HTTPException(
            status_code=500, detail=f"Failed to remove folder watcher: {e}"
        )


@router.get("/watch", response_model=list[WatchedFolderResponse])
async def list_watched_folders():
    """Get all active watched folders."""
    db = _require_database()
    folders = await db.get_all_watched_folders()
    return [WatchedFolderResponse(**folder) for folder in folders]


@router.get("/watch/status", response_model=WatchStatusResponse)
async def get_watcher_status():
    """Get the current status of the file watcher system."""
    watcher = await get_file_watcher()
    status = await watcher.get_status()
    return WatchStatusResponse(**status)
