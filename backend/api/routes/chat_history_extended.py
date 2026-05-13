"""Extended Chat History endpoints for conversation management."""

import re
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.core.database import async_session_maker
from backend.models.sync_models import ConversationPin
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat/history", tags=["chat", "history"])


class PinResponse(BaseModel):
    """Response model for pinning operations."""

    conversation_id: str
    pinned: bool
    pinned_at: Optional[str]


class ExportResponse(BaseModel):
    """Response model for export operations."""

    conversation_id: str
    download_url: str
    filename: str
    message_count: int


class ArchiveResponse(BaseModel):
    """Response model for archive/delete operations."""

    conversation_id: str
    archived: bool
    deleted: Optional[bool]


class MessageResponse(BaseModel):
    """Response model for a message."""

    id: str
    conversation_id: str
    role: str
    content: str
    agent_id: Optional[str]
    timestamp: str
    token_count: Optional[int]


class ConversationMessagesResponse(BaseModel):
    """Response model for conversation messages."""

    conversation_id: str
    title: Optional[str]
    messages: List[MessageResponse]


class ConversationResponse(BaseModel):
    """Response model for a conversation."""

    id: str
    title: Optional[str]
    created_at: str
    updated_at: str
    message_count: int
    archived: bool = False


# Helper to get database
class _RequireDatabase:
    @staticmethod
    async def get_db():
        from backend.core import database as db_module

        if db_module.database is None:
            raise RuntimeError("Database is not initialized")
        return db_module.database


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=ConversationMessagesResponse,
)
async def get_conversation_messages(
    conversation_id: str,
    scroll_to_message: Optional[str] = Query(
        None, description="Scroll to and highlight specific message ID"
    ),
):
    """Get all messages for a conversation."""
    try:
        async with async_session_maker() as session:
            from sqlalchemy import select
            from backend.core.database import Message, Conversation

            # Get messages
            stmt = (
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.timestamp)
            )
            result = await session.execute(stmt)
            messages = result.scalars().all()

            # Get conversation metadata
            conv_stmt = select(Conversation).where(Conversation.id == conversation_id)
            conv_result = await session.execute(conv_stmt)
            conversation = conv_result.scalar_one_or_none()

            # Convert messages
            message_responses = [
                MessageResponse(
                    id=msg.id,
                    conversation_id=msg.conversation_id,
                    role=msg.role,
                    content=msg.content,
                    agent_id=msg.agent_id,
                    timestamp=msg.timestamp.isoformat(),
                    token_count=msg.token_count,
                )
                for msg in messages
            ]

            return ConversationMessagesResponse(
                conversation_id=conversation_id,
                title=conv_result.title if conv_result else None,
                messages=message_responses[:20]
                if len(message_responses) > 20
                else message_responses,  # Return first 20
            )
    except Exception as e:
        logger.error(f"Failed to get conversation messages: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get messages: {str(e)}")


@router.post("/conversations/{conversation_id}/pin", response_model=PinResponse)
async def pin_conversation(conversation_id: str, pin: bool = True):
    """Pin or unpin a conversation."""
    try:
        async with async_session_maker() as session:
            # Upsert pin status
            stmt = (
                insert(ConversationPin)
                .values(
                    conversation_id=conversation_id,
                    user_id="default_user",
                    pinned=pin,
                    pinned_at=datetime.now(),
                )
                .on_conflict_do_update(
                    index_elements=["conversation_id", "user_id"],
                    set_={"pinned": pin, "pinned_at": datetime.now()},
                )
            )
            await session.execute(stmt)
            await session.commit()

            pinned_at = datetime.now().isoformat() if pin else None

            return PinResponse(
                conversation_id=conversation_id,
                pinned=pin,
                pinned_at=pinned_at,
            )
    except Exception as e:
        logger.error(f"Failed to pin conversation: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to pin: {str(e)}")


@router.get("/conversations/{conversation_id}/is_pinned", response_model=PinResponse)
async def get_pin_status(conversation_id: str):
    """Check if a conversation is pinned."""
    try:
        async with async_session_maker() as session:
            stmt = select(ConversationPin).where(
                ConversationPin.conversation_id == conversation_id,
                ConversationPin.user_id == "default_user",
            )
            result = await session.execute(stmt)
            pin = result.scalar_one_or_none()

            if pin and pin.pinned:
                return PinResponse(
                    conversation_id=conversation_id,
                    pinned=True,
                    pinned_at=pin.pinned_at.isoformat() if pin.pinned_at else None,
                )
            else:
                return PinResponse(
                    conversation_id=conversation_id,
                    pinned=False,
                    pinned_at=None,
                )
    except Exception as e:
        logger.error(f"Failed to get pin status: {e}")
        return PinResponse(
            conversation_id=conversation_id, pinned=False, pinned_at=None
        )


@router.post("/conversations/{conversation_id}/export", response_model=ExportResponse)
async def export_conversation(conversation_id: str):
    """Export a conversation as markdown."""
    try:
        async with async_session_maker() as session:
            from sqlalchemy import select
            from backend.core.database import Message, Conversation

            # Get messages
            msg_stmt = (
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.timestamp)
            )
            msg_result = await session.execute(msg_stmt)
            messages = msg_result.scalars().all()

            # Get conversation
            conv_stmt = select(Conversation).where(Conversation.id == conversation_id)
            conv_result = await session.execute(conv_stmt)
            conversation = conv_result.scalar_one_or_none()

            if not messages:
                raise HTTPException(
                    status_code=404, detail="Conversation not found or empty"
                )

            # Generate filename
            title = (
                conversation.title
                if conversation and conversation.title
                else f"conversation-{conversation_id[:8]}"
            )
            safe_title = re.sub(r"[^\w\s-]", "", title).strip().lower()
            safe_title = re.sub(r"[-\s]+", "-", safe_title)
            if not safe_title:
                safe_title = f"conversation-{conversation_id[:8]}"

            filename = f"{safe_title}.md"

            # Build markdown
            md_content = f"""# {title or "Untitled Conversation"}

*Exported: {datetime.now().strftime("%Y-%m-%d %H:%M UTC")}*  
*{len(messages)} messages*  

"""

            for msg in messages:
                md_content += f"\n---\n\n"
                md_content += f"**{msg.role.title()} [{msg.timestamp.strftime('%Y-%m-%d %H:%M')}]**  \n"
                if msg.agent_id:
                    md_content += f"*(Agent: {msg.agent_id})*  \n\n"
                md_content += f"{msg.content}\n\n"

            # Save to exports
            export_dir = Path("exports")
            export_dir.mkdir(exist_ok=True)

            file_path = export_dir / filename
            file_path.write_text(md_content, encoding="utf-8")

            return ExportResponse(
                conversation_id=conversation_id,
                download_url=f"/api/chat/history/download/{filename}",
                filename=filename,
                message_count=len(messages),
            )
    except Exception as e:
        logger.error(f"Failed to export conversation: {e}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


# Static file serving for downloads
@router.get("/download/{filename}")
async def download_export(filename: str):
    """Download exported markdown file."""
    try:
        file_path = Path("exports") / filename
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")

        from fastapi.responses import FileResponse

        return FileResponse(
            path=file_path,
            filename=filename,
            media_type="text/markdown",
        )
    except Exception as e:
        logger.error(f"Failed to serve download: {e}")
        raise HTTPException(status_code=404, detail="Download not available")
