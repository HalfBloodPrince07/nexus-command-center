"""
Event-driven file watcher using watchdog for cross-platform file monitoring.
Replaces polling-based implementation with real-time event handling.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import shutil
import uuid
import time
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Set
from urllib.parse import urlparse, unquote

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

if TYPE_CHECKING:
    from backend.config import Settings
    from backend.core.database import Database

from backend.config import settings
from backend.core import database as db_module
from backend.app.agents.file_processor import file_processor

logger = logging.getLogger(__name__)


class FileWatcherError(Exception):
    """Custom exception for file watcher operations."""

    pass


class DebouncedEventHandler(FileSystemEventHandler):
    """
    Handles watchdog file system events with debouncing.
    Files often trigger multiple events during save operations.
    """

    def __init__(
        self, callback: Callable[[Path, str], None], debounce_seconds: float = 5.0
    ):
        """
        Args:
            callback: Function to call when a file event is confirmed
            debounce_seconds: Time to wait after last event before processing
        """
        self.callback = callback
        self.debounce_seconds = debounce_seconds
        self.pending_files: Dict[str, float] = {}
        self.processed_hashes: Set[str] = set()
        self.lock = asyncio.Lock()

    def on_any_event(self, event: FileSystemEvent) -> None:
        """Called on any file system event."""
        if event.is_directory:
            return

        file_path = Path(event.src_path)

        # Only process supported file types
        if not self._is_supported_file(file_path):
            return

        # For deletion events, process immediately
        if event.event_type == "deleted":
            asyncio.create_task(self._handle_deletion(file_path))
            return

        # For created/modified events, debounce
        if event.event_type in ["created", "modified"]:
            self._debounce_file(file_path)

    def _is_supported_file(self, file_path: Path) -> bool:
        """Check if file has supported extension."""
        supported_exts = {
            ".pdf",
            ".docx",
            ".xlsx",
            ".md",
            ".txt",
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
        }
        return file_path.suffix.lower() in supported_exts

    def _debounce_file(self, file_path: Path) -> None:
        """Queue file for processing after debounce period."""
        file_key = str(file_path.resolve())
        self.pending_files[file_key] = time.time()

        # Create async task to process after debounce
        asyncio.create_task(self._process_after_debounce(file_key))

    async def _process_after_debounce(self, file_key: str) -> None:
        """Wait for debounce period then process file if no new events."""
        await asyncio.sleep(self.debounce_seconds)

        async with self.lock:
            if file_key not in self.pending_files:
                return

            # Check if file was modified again during debounce
            last_event_time = self.pending_files[file_key]
            if time.time() - last_event_time < self.debounce_seconds:
                # File was modified again, wait longer
                return

            # Remove from pending and process
            del self.pending_files[file_key]
            file_path = Path(file_key)

            # Verify file still exists and is readable
            if not file_path.exists() or not file_path.is_file():
                return

            # Compute hash to check for duplicates
            try:
                file_hash = await self._compute_file_hash(file_path)
                if file_hash in self.processed_hashes:
                    logger.debug("Skipping duplicate file: %s", file_path)
                    return
            except Exception as e:
                logger.warning("Failed to compute hash for %s: %s", file_path, e)
                return

            self.processed_hashes.add(file_hash)

            # Call the callback
            try:
                await self.callback(file_path, file_hash)
            except Exception as e:
                logger.error("Error processing file %s: %s", file_path, e)

    async def _handle_deletion(self, file_path: Path) -> None:
        """Handle file deletion events."""
        try:
            # Use callback to handle deletion (will be implemented in watcher)
            await self.callback(file_path, "deleted")
        except Exception as e:
            logger.error("Error handling deletion of %s: %s", file_path, e)

    async def _compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA256 hash of file."""
        hasher = hashlib.sha256()
        async with asyncio.Lock():
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hasher.update(chunk)
        return hasher.hexdigest()

    async def cleanup_old_hashes(self, max_age_hours: int = 24) -> None:
        """Clean up processed hashes older than max_age_hours."""
        # This is a simple implementation - in production, track timestamps
        self.processed_hashes.clear()


class WatchdogFileWatcher:
    """
    Cross-platform file watcher using watchdog library.
    Provides event-driven file monitoring with debouncing and duplicate detection.
    """

    def __init__(self, database: db_module.Database | None = None):
        self.database = database or db_module.database
        self.observer: Optional[Observer] = None
        self.handlers: Dict[str, DebouncedEventHandler] = {}
        self.is_running = False
        self._pause_lock = asyncio.Lock()
        self._is_paused = False

    async def start(self) -> None:
        """Start the file watcher with configured folders."""
        if self.is_running:
            logger.warning("File watcher is already running")
            return

        try:
            # Load watched folders from database
            folders = await self._load_watched_folders()

            self.observer = Observer()

            for folder in folders:
                if folder.get("is_active", True):
                    await self._add_watch_folder(
                        folder["path"], folder.get("collection", "files")
                    )

            self.observer.start()
            self.is_running = True

            logger.info("File watcher started, monitoring %d folders", len(folders))

        except Exception as e:
            logger.error("Failed to start file watcher: %s", e)
            raise FileWatcherError(f"Failed to start file watcher: {e}")

    async def stop(self) -> None:
        """Stop the file watcher."""
        if not self.is_running or self.observer is None:
            return

        try:
            self.observer.stop()
            self.observer.join(timeout=5)
            self.is_running = False
            self.handlers.clear()

            logger.info("File watcher stopped")

        except Exception as e:
            logger.error("Error stopping file watcher: %s", e)
            raise FileWatcherError(f"Error stopping file watcher: {e}")

    async def add_folder(self, path: str, collection: str = "files") -> str:
        """Add a folder to watch. Returns watcher_id."""
        folder = Path(path).resolve()

        if not folder.exists():
            raise FileWatcherError(f"Path does not exist: {path}")
        if not folder.is_dir():
            raise FileWatcherError(f"Path is not a directory: {path}")

        try:
            # Test read access
            folder.iterdir()
        except PermissionError:
            raise FileWatcherError(f"No read permission for folder: {path}")

        watcher_id = str(folder)

        if watcher_id in self.handlers:
            raise FileWatcherError(f"Folder already being watched: {path}")

        await self._add_watch_folder(str(folder), collection)

        # Save to database
        if self.database:
            await self.database.add_watched_folder(watcher_id, str(folder), collection)

        logger.info("Added folder watcher: %s", folder)
        return watcher_id

    async def remove_folder(self, watcher_id: str) -> None:
        """Remove a folder from watching."""
        if watcher_id not in self.handlers:
            raise FileWatcherError(f"Watcher not found: {watcher_id}")

        try:
            # Remove from observer
            if self.observer:
                self.observer.unschedule(self.handlers[watcher_id])

            # Remove from handlers
            del self.handlers[watcher_id]

            # Update database
            if self.database:
                await self.database.remove_watched_folder(watcher_id)

            logger.info("Removed folder watcher: %s", watcher_id)

        except Exception as e:
            logger.error("Error removing folder watcher %s: %s", watcher_id, e)
            raise FileWatcherError(f"Error removing folder watcher: {e}")

    async def pause(self) -> None:
        """Pause file watching (e.g., during research runs)."""
        async with self._pause_lock:
            self._is_paused = True
        logger.info("File watcher paused")

    async def resume(self) -> None:
        """Resume file watching."""
        async with self._pause_lock:
            self._is_paused = False
        logger.info("File watcher resumed")

    async def get_status(self) -> dict:
        """Get current watcher status."""
        return {
            "is_running": self.is_running,
            "is_paused": self._is_paused,
            "watched_folders": [
                {
                    "path": watcher_id,
                    "collection": handler.collection,
                    "pending_files": len(handler.pending_files),
                }
                for watcher_id, handler in self.handlers.items()
            ],
            "total_pending_files": sum(
                len(h.pending_files) for h in self.handlers.values()
            ),
        }

    async def _add_watch_folder(self, path: str, collection: str) -> None:
        """Internal method to add a folder to the observer."""
        if not self.observer:
            raise FileWatcherError("Observer not initialized")

        handler = DebouncedEventHandler(
            callback=self._process_file_event, debounce_seconds=5.0
        )
        handler.collection = collection  # type: ignore

        self.observer.schedule(handler, path, recursive=True)
        self.handlers[path] = handler

    async def _process_file_event(self, file_path: Path, file_hash: str) -> None:
        """Process a file event (ingest new/modified files)."""
        # Check if paused
        async with self._pause_lock:
            if self._is_paused:
                logger.debug("File watcher paused, skipping: %s", file_path)
                return

        try:
            # Verify file exists and is readable
            if not file_path.exists() or not file_path.is_file():
                return

            # Skip if file is too small (likely incomplete write)
            if file_path.stat().st_size < 100:
                logger.debug("File too small, skipping: %s", file_path)
                return

            # Check if already ingested via hash
            if self.database:
                existing = await self.database.get_file_by_hash(file_hash, "files")
                if existing:
                    logger.debug(
                        "File already ingested (via hash), skipping: %s", file_path
                    )
                    return

            # Ingest the file
            await self._ingest_file(file_path, file_hash)

        except Exception as e:
            logger.error("Error processing file event for %s: %s", file_path, e)

    async def _ingest_file(self, file_path: Path, file_hash: str) -> None:
        """Ingest a single file into the system."""
        try:
            # Copy to upload directory
            file_id = (
                str(uuid.uuid4())
                if hasattr(self, "uuid")
                else str(__import__("uuid").uuid4())
            )
            upload_dir = Path(settings.upload_dir) / file_id
            upload_dir.mkdir(parents=True, exist_ok=True)

            dest = upload_dir / file_path.name
            shutil.copy2(file_path, dest)

            # Determine MIME type
            mime_map = {
                ".pdf": "application/pdf",
                ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ".md": "text/markdown",
                ".txt": "text/plain",
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".webp": "image/webp",
            }
            mime_type = mime_map.get(
                file_path.suffix.lower(), "application/octet-stream"
            )

            size = dest.stat().st_size

            # Save to database
            if self.database:
                await self.database.save_file_record(
                    file_id, file_path.name, file_path.name, mime_type, size, "files"
                )

                # Store content hash
                await self.database.store_content_hash(
                    file_hash, file_id, file_path.name, "files"
                )

            # Queue for processing
            async for _event in file_processor.process_file(
                file_id, str(dest), file_path.name, mime_type, "files"
            ):
                pass

            # Emit WebSocket event
            from backend.api.websocket import manager

            await manager.broadcast(
                {
                    "type": "file_ingested",
                    "file_id": file_id,
                    "filename": file_path.name,
                    "status": "completed",
                }
            )

            logger.info("File watcher auto-ingested: %s", file_path.name)

        except Exception as e:
            logger.error("Failed to ingest file %s: %s", file_path, e)
            raise

    async def _load_watched_folders(self) -> list[dict]:
        """Load watched folders from database."""
        if not self.database:
            return []

        try:
            return await self.database.get_all_watched_folders()
        except Exception as e:
            logger.error("Failed to load watched folders from DB: %s", e)
            return []


# Global watcher instance
_watcher: WatchdogFileWatcher | None = None


async def get_file_watcher() -> WatchdogFileWatcher:
    """Get or create the global file watcher instance."""
    global _watcher
    if _watcher is None:
        _watcher = WatchdogFileWatcher()
    return _watcher
