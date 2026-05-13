"""Obsidian bi-directional sync service for watching vault changes and importing to Nexus OS."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional, Any, Tuple
from watchdog.observers import Observer
from watchdog.events import (
    FileSystemEventHandler,
    FileModifiedEvent,
    FileCreatedEvent,
    FileDeletedEvent,
)

if TYPE_CHECKING:
    from backend.core.database import Database

from backend.config import settings
from backend.core import database as db_module

logger = logging.getLogger(__name__)


class SyncConflictError(Exception):
    """Raised when a sync conflict occurs (both files changed within 5s)."""

    def __init__(self, vault_path: Path, nexus_id: str, conflict_type: str):
        self.vault_path = vault_path
        self.nexus_id = nexus_id
        self.conflict_type = conflict_type
        super().__init__(f"Sync conflict: {vault_path} ({nexus_id}) - {conflict_type}")


class ObsidianSyncObserver(FileSystemEventHandler):
    """Watchdog event handler for Obsidian vault changes."""

    def __init__(
        self,
        vault_path: Path,
        sync_service: "ObsidianBiDiSync",
        debounce_delay: float = 2.0,
    ):
        self.vault_path = Path(vault_path)
        self.sync_service = sync_service
        self.debounce_delay = debounce_delay
        self.pending_events: Dict[str, asyncio.Task] = {}
        self.modification_times: Dict[str, float] = {}

        # Compile regex patterns for frontmatter
        self.frontmatter_pattern = re.compile(
            r"^---\s*\n(.*?)\n^---\s*\n", re.MULTILINE | re.DOTALL
        )
        self.nexus_id_pattern = re.compile(r"nexus_id:\s*([\w-]+)")
        self.type_pattern = re.compile(r"type:\s*(\w+)")

        logger.info("ObsidianSyncObserver initialized for vault: %s", vault_path)

    def _debounce_event(self, event_path: str, callback: callable):
        """Debounce rapid file changes to reduce sync churn."""
        if event_path in self.pending_events:
            # Cancel pending event and reschedule
            self.pending_events[event_path].cancel()

        async def delayed_callback():
            await asyncio.sleep(self.debounce_delay)
            try:
                callback(event_path)
            except Exception as e:
                logger.error("Error in sync callback: %s", e)
            finally:
                self.pending_events.pop(event_path, None)

        task = asyncio.create_task(delayed_callback())
        self.pending_events[event_path] = task

    def _extract_frontmatter(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Extract YAML frontmatter from Obsidian markdown file."""
        try:
            content = file_path.read_text(encoding="utf-8")
            match = self.frontmatter_pattern.search(content)

            if match:
                frontmatter_text = match.group(1)
                frontmatter = {}

                for line in frontmatter_text.split("\n"):
                    if ":" in line:
                        key, value = line.split(":", 1)
                        frontmatter[key.strip()] = value.strip()

                return frontmatter
        except Exception as e:
            logger.error("Failed to read frontmatter from %s: %s", file_path, e)

        return None

    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate hash of file content (excluding frontmatter)."""
        try:
            content = file_path.read_bytes()
            # Remove frontmatter from hash calculation
            text = content.decode("utf-8", errors="ignore")
            match = self.frontmatter_pattern.search(text)
            if match:
                # Hash only the body content
                body = text[match.end() :]
                return hashlib.md5(body.encode("utf-8")).hexdigest()[:16]
            # No frontmatter, hash entire content
            return hashlib.md5(content).hexdigest()[:16]
        except Exception as e:
            logger.error("Failed to hash file %s: %s", file_path, e)
            return ""


class ObsidianBiDiSync:
    """Main sync service coordinating bi-directional sync between Obsidian and Nexus OS."""

    def __init__(self, db: Optional["Database"] = None):
        self.db = db or db_module.database
        self.vault_path: Optional[Path] = None
        self.observer: Optional[Observer] = None
        self.event_handler: Optional[ObsidianSyncObserver] = None
        self.is_watching = False
        self.sync_state: Dict[str, Any] = {}

        # Sync configuration
        self.config = {
            "sync_interval": 30,  # seconds
            "debounce_delay": 2.0,
            "conflict_window": 5.0,  # seconds
            "auto_sync": False,
            "sync_types": ["journal", "memory", "conversation"],
        }

    async def configure(self, vault_path: str, **kwargs) -> bool:
        """Configure vault path and sync settings."""
        self.vault_path = Path(vault_path)

        if not self.vault_path.exists():
            logger.error("Vault path does not exist: %s", vault_path)
            return False

        # Update config
        self.config.update(kwargs)

        # Initialize sync state table if needed
        await self._ensure_sync_state_table()

        logger.info("Obsidian sync configured for: %s", vault_path)
        return True

    async def _ensure_sync_state_table(self):
        """Ensure sync_state table exists in database."""
        if not self.db:
            return

        # This would execute SQL to create the table if needed
        # CREATE TABLE IF NOT EXISTS sync_state (
        #     nexus_id TEXT PRIMARY KEY,
        #     vault_path TEXT NOT NULL,
        #     last_synced_at TIMESTAMP,
        #     last_local_hash TEXT,
        #     last_remote_hash TEXT,
        #     sync_status TEXT
        # )
        pass


# Global sync service instance
_sync_service: Optional[ObsidianBiDiSync] = None


async def init_obsidian_sync(vault_path: Optional[str] = None) -> ObsidianBiDiSync:
    """Initialize and return the global Obsidian sync service instance."""
    global _sync_service

    if _sync_service is None:
        _sync_service = ObsidianBiDiSync()

        if vault_path:
            await _sync_service.configure(vault_path)

    return _sync_service


async def get_obsidian_sync() -> Optional[ObsidianBiDiSync]:
    """Get the global sync service instance."""
    return _sync_service
