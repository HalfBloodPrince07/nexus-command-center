"""Obsidian bi-directional sync API endpoints."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel

from backend.core.obsidian_sync import get_obsidian_sync
from backend.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sync", tags=["Sync"])

# --- Response Models ---


class SyncConfig(BaseModel):
    """Sync configuration settings."""

    vault_path: str
    auto_sync: bool
    sync_interval: int
    sync_types: list[str]
    conflict_resolution: str = "last_write_wins"


class SyncResponse(BaseModel):
    """Generic sync operation response."""

    status: str
    message: str
    details: Optional[Dict[str, Any]] = None


class SyncStatus(BaseModel):
    """Current sync service status."""

    is_watching: bool
    vault_path: Optional[str]
    last_sync: Optional[str]
    pending_changes: int
    sync_errors: int
    conflict_count: int


class SyncRequest(BaseModel):
    """Request to trigger sync."""

    dry_run: bool = False
    scopes: list[str] = ["all"]


# --- API Routes ---


@router.get("/obsidian/status", response_model=SyncStatus)
async def get_obsidian_sync_status():
    """Get the current sync service status."""
    sync_service = await get_obsidian_sync()
    if not sync_service:
        return SyncStatus(
            is_watching=False,
            vault_path=None,
            last_sync=None,
            pending_changes=0,
            sync_errors=0,
            conflict_count=0,
        )

    # Calculate pending changes (files modified since last sync)
    pending = 0 if not sync_service.is_watching else 1  # Simplified

    return SyncStatus(
        is_watching=sync_service.is_watching,
        vault_path=str(sync_service.vault_path) if sync_service.vault_path else None,
        last_sync=sync_service.sync_state.get("last_sync_at"),
        pending_changes=pending,
        sync_errors=sync_service.sync_state.get("error_count", 0),
        conflict_count=sync_service.sync_state.get("conflict_count", 0),
    )


@router.post("/obsidian/configure", response_model=SyncResponse)
async def configure_obsidian_sync(
    vault_path: str = Query(..., description="Path to Obsidian vault"),
    auto_sync: bool = Query(False, description="Enable automatic sync"),
    sync_interval: int = Query(30, description="Sync interval in seconds"),
    sync_types: list[str] = Query(["journal", "memory", "conversation"]),
):
    """Configure Obsidian vault path and sync settings."""
    try:
        sync_service = await get_obsidian_sync(vault_path)

        # Start watching the vault
        started = await sync_service.start_watching()
        if not started:
            raise HTTPException(
                status_code=500, detail="Failed to start watching vault"
            )

        return SyncResponse(
            status="success",
            message="Obsidian sync configured and started",
            details={
                "vault_path": str(sync_service.vault_path),
                "auto_sync": sync_service.config.get("auto_sync", False),
                "watching": sync_service.is_watching,
            },
        )

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Failed to configure sync: %s", e)
        raise HTTPException(status_code=500, detail=f"Configuration failed: {str(e)}")


@router.post("/obsidian/run", response_model=SyncResponse)
async def trigger_obsidian_sync(sync_request: SyncRequest):
    """Manually trigger a sync operation."""
    sync_service = await get_obsidian_sync()
    if not sync_service or not sync_service.is_watching:
        raise HTTPException(status_code=400, detail="No active sync configured")

    try:
        dry_run = sync_request.dry_run
        scopes = sync_request.scopes

        # Log the sync request
        logger.info("Sync triggered: dry_run=%s, scopes=%s", dry_run, scopes)

        # Count changes
        changes = await sync_service.scan_for_changes()

        if dry_run:
            return SyncResponse(
                status="dry_run",
                message=f"Found {len(changes)} changes (dry run)",
                details={"changes": changes, "scopes": scopes},
            )

        # Process changes
        if changes:
            await sync_service.process_changes(changes, scopes)

        # Export any pending Nexus changes
        await sync_service.export_nexus_changes(scopes)

        return SyncResponse(
            status="success",
            message=f"Synced {len(changes)} changes",
            details={
                "processed": len(changes),
                "conflicts": sync_service.sync_state.get("conflict_count", 0),
            },
        )

    except Exception as e:
        logger.error("Sync failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


@router.get("/obsidian/conflicts", response_model=dict)
async def get_sync_conflicts():
    """Get list of unresolved sync conflicts."""
    sync_service = await get_obsidian_sync()
    if not sync_service:
        return {"conflicts": []}

    conflicts = await sync_service.get_conflicts()
    return {"conflicts": conflicts}


@router.post("/obsidian/conflicts/{nexus_id}/resolve", response_model=SyncResponse)
async def resolve_sync_conflict(
    nexus_id: str,
    use_local: bool = Body(
        ..., description="True to use vault version, False to use Nexus version"
    ),
):
    """Resolve a sync conflict by choosing which version to keep."""
    sync_service = await get_obsidian_sync()
    if not sync_service:
        raise HTTPException(status_code=400, detail="No active sync configured")

    resolved = await sync_service.resolve_conflict(nexus_id, use_local)
    if not resolved:
        raise HTTPException(
            status_code=404, detail="Conflict not found or already resolved"
        )

    return SyncResponse(
        status="success",
        message="Conflict resolved",
        details={"nexus_id": nexus_id, "used_local": use_local},
    )


@router.get("/obsidian/health", response_model=dict)
async def get_sync_health():
    """Get sync health metrics and recent sync history."""
    sync_service = await get_obsidian_sync()
    if not sync_service:
        return {
            "status": "not_configured",
            "health": "unknown",
            "metrics": {},
            "history": [],
        }

    health = await sync_service.get_health_metrics()
    return {
        "status": "ok" if sync_service.is_watching else "stopped",
        "health": health["status"],
        "metrics": health["metrics"],
        "history": health["recent_history"],
    }


# --- Internal helper functions ---


async def _validate_vault_path(vault_path: Path) -> tuple[bool, str]:
    """Validate that vault path exists and is accessible."""
    try:
        if not vault_path.exists():
            return False, f"Vault path does not exist: {vault_path}"

        if not vault_path.is_dir():
            return False, f"Vault path is not a directory: {vault_path}"

        # Check if it's a valid Obsidian vault (has .obsidian folder)
        obsidian_folder = vault_path / ".obsidian"
        if not obsidian_folder.exists():
            logger.warning(
                "No .obsidian folder found in %s, but proceeding anyway", vault_path
            )

        return True, "ok"

    except Exception as e:
        return False, f"Validation error: {str(e)}"
