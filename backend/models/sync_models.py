"""Sync state and conflict resolution models for bi-directional synchronization."""

from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from sqlalchemy import String, DateTime, Integer, Boolean, Text, select
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncSession
from backend.core.database import Base
import uuid


class SyncState(Base):
    """Tracks synchronization state between Nexus OS and external systems like Obsidian."""

    __tablename__ = "sync_state"

    nexus_id: Mapped[str] = mapped_column(String, primary_key=True)
    vault_path: Mapped[str] = mapped_column(String, nullable=False)
    content_type: Mapped[str] = mapped_column(
        String, nullable=False
    )  # journal, memory, chat, etc.
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_local_hash: Mapped[Optional[str]] = mapped_column(
        String(32)
    )  # MD5 hash of local content
    last_remote_hash: Mapped[Optional[str]] = mapped_column(
        String(32)
    )  # MD5 hash of remote content
    sync_status: Mapped[str] = mapped_column(
        String, default="pending"
    )  # pending, synced, conflict
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Whether file is deleted (soft delete)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)


class SyncRun(Base):
    """Logs individual sync runs."""

    __tablename__ = "sync_runs"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String)  # running, success, failed, conflict
    files_added: Mapped[int] = mapped_column(Integer, default=0)
    files_modified: Mapped[int] = mapped_column(Integer, default=0)
    files_deleted: Mapped[int] = mapped_column(Integer, default=0)
    conflicts: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    config_snapshot: Mapped[Optional[str]] = mapped_column(Text)  # JSON of sync config


class ConversationPin(Base):
    """Tracks pinned conversation status."""

    __tablename__ = "conversation_pins"

    conversation_id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[Optional[str]] = mapped_column(
        String, default="default_user"
    )  # For multi-tenant
    pinned_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    pinned: Mapped[bool] = mapped_column(Boolean, default=True)
