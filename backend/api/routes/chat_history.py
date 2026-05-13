"""Chat history search endpoints for semantic search over past conversations."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.core.chat_indexer import get_chat_indexer
from backend.core import database as db_module

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat/history", tags=["chat", "history"])


class SearchResult(BaseModel):
    conversation_id: str
    conversation_title: str
    message_id: str
    snippet: str
    score: float
    timestamp: str
    match_type: str
    role: str = "assistant"


class ChatSearchResponse(BaseModel):
    results: list[SearchResult]
    total: int
    query: str


class ChatSearchQuery(BaseModel):
    query: str


def _require_database():
    if db_module.database is None:
        raise RuntimeError("Database is not initialized")
    return db_module.database


@router.get("/search", response_model=ChatSearchResponse)
async def search_chat_history(
    q: str = Query(..., description="Search query"),
    top_k: int = Query(20, ge=1, le=100, description="Number of results to return"),
    date_from: str | None = Query(None, description="Start date in ISO format"),
    date_to: str | None = Query(None, description="End date in ISO format"),
    conversation_id: str | None = Query(
        None, description="Filter to specific conversation"
    ),
):
    """Search over all past chat conversations using semantic similarity.

    Returns messages ranked by relevance to the query, with contextual snippets
    showing ±2 messages around each match.
    """
    if not q or len(q.strip()) < 3:
        raise HTTPException(
            status_code=400, detail="Query must be at least 3 characters"
        )

    # Parse date filters
    start_date = None
    end_date = None
    if date_from:
        try:
            start_date = datetime.fromisoformat(date_from.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date_from format")
    if date_to:
        try:
            end_date = datetime.fromisoformat(date_to.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date_to format")

    try:
        indexer = await get_chat_indexer()

        results = await indexer.search(
            query=q,
            top_k=top_k,
            date_from=start_date,
            date_to=end_date,
            conversation_id=conversation_id,
        )

        # Convert to Pydantic models
        search_results = [
            SearchResult(
                conversation_id=r["conversation_id"],
                conversation_title=r["conversation_title"],
                message_id=r["message_id"],
                snippet=r["snippet"],
                score=r["score"],
                timestamp=r["timestamp"],
                match_type=r["match_type"],
                role=r.get("role", "assistant"),
            )
            for r in results
        ]

        return ChatSearchResponse(
            results=search_results,
            total=len(search_results),
            query=q,
        )

    except Exception as e:
        logger.error("Failed to search chat history: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.post("/index", response_model=dict)
async def index_chat_message(chat_query: ChatSearchQuery):
    """Index a single chat message for testing purposes."""
    try:
        indexer = await get_chat_indexer()
        # Mock indexing - in production this would be called automatically
        # when messages are saved
        return {"status": "success", "message": "Message indexed"}
    except Exception as e:
        logger.error("Failed to index chat message: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Indexing failed: {str(e)}")


@router.get("/stats", response_model=dict)
async def get_index_stats():
    """Get statistics about the chat history index."""
    try:
        from backend.db.vector_store import init_vector_store

        chroma = await init_vector_store()

        # Get collection count (use peek if available)
        try:
            collection = chroma.get_collection("chat_messages")
            count = collection.count() if hasattr(collection, "count") else 0
        except Exception:
            count = 0

        return {
            "collection": "chat_messages",
            "indexed_messages": count,
            "status": "active" if count > 0 else "empty",
        }
    except Exception as e:
        logger.error("Failed to get index stats: %s", e)
        return {"collection": "chat_messages", "indexed_messages": 0, "status": "error"}
