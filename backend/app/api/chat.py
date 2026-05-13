from __future__ import annotations

from fastapi import APIRouter, Query

from backend.core.database import get_conversation_history, get_all_conversations

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.get("/conversations")
async def list_conversations(limit: int = Query(100, ge=1, le=500)) -> dict:
    conversations = await get_all_conversations()
    serializable = [
        {
            **c,
            "conversation_id": c.get("id") or c.get("conversation_id", ""),
            "created_at": c["created_at"].isoformat() if hasattr(c.get("created_at"), "isoformat") else str(c.get("created_at", "")),
            "updated_at": c["updated_at"].isoformat() if hasattr(c.get("updated_at"), "isoformat") else str(c.get("updated_at", "")),
        }
        for c in conversations[:limit]
    ]
    return {"conversations": serializable, "count": len(serializable)}


@router.get("/history/{conversation_id}")
async def get_history(
    conversation_id: str,
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    messages = await get_conversation_history(conversation_id, limit=limit)
    serializable = [
        {
            **m,
            "timestamp": (
                m["timestamp"].isoformat()
                if hasattr(m.get("timestamp"), "isoformat")
                else str(m.get("timestamp", ""))
            ),
        }
        for m in messages
    ]
    return {"messages": serializable, "conversation_id": conversation_id}
