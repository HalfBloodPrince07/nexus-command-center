"""Chat history semantic search implementation."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    from backend.core.database import Database

from backend.config import settings
from backend.core import database as db_module
from backend.core.hf_embeddings import get_embeddings_model

logger = logging.getLogger(__name__)

class ChatHistoryIndexer:
    """Handles indexing and semantic search over chat messages."""
    
    def __init__(self, collection_name: str = "chat_messages"):
        self.collection_name = collection_name
        self._chroma = None
        self._embeddings = None
    
    async def _init_chroma(self):
        """Initialize ChromaDB instance."""
        if self._chroma is None:
            from backend.db.vector_store import init_vector_store
            self._chroma = await init_vector_store() 
        return self._chroma
    
    async def _init_embeddings(self):
        """Initialize embeddings model."""
        if self._embeddings is None:
            self._embeddings = await get_embeddings_model()
        return self._embeddings
    
    async def index_message(
        self,
        conversation_id: str,
        message_id: str,
        role: str,
        content: str,
        timestamp: datetime,
        agent_id: Optional[str] = None,
    ) -> None:
        """Index a single message in ChromaDB."""
        if not content or len(content.strip()) < 10:
            return  # Skip empty or very short messages
        
        try:
            chroma = await self._init_chroma()
            embeddings = await self._init_embeddings()
            
            # Generate embeddings
            embedding = await embeddings.aembed_query(content)
            
            # Store in ChromaDB with metadata
            doc_id = f"{conversation_id}_{message_id}"
            
            chroma.upsert(
                collection_name=self.collection_name,
                documents=[content],
                embeddings=[embedding],
                metadatas=[{
                    "conversation_id": conversation_id,
                    "message_id": message_id,
                    "role": role,
                    "agent_id": agent_id or "system",
                    "timestamp": timestamp.isoformat(),
                }],
                ids=[doc_id],
            )
            
            logger.debug("Indexed chat message %s in conversation %s", message_id, conversation_id)
            
        except Exception as e:
            logger.error("Failed to index chat message %s: %s", message_id, e)
    
    async def search(
        self,
        query: str,
        top_k: int = 20,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        conversation_id: Optional[str] = None,
    ) -> list[dict]:
        """Search for relevant chat messages using vector similarity."""
        try:
            chroma = await self._init_chroma()
            embeddings = await self._init_embeddings()
            
            # Generate query embedding
            query_embedding = await embeddings.aembed_query(query)
            
            # Build metadata filters
            where_clause = None
            filters = {}
            if date_from:
                filters["timestamp"] = {"$gte": date_from.isoformat()}
            if date_to:
                if "timestamp" not in filters:
                    filters["timestamp"] = {}
                filters["timestamp"]["$lte"] = date_to.isoformat()}
            if conversation_id:
                filters["conversation_id"] = conversation_id
            
            if filters:
                where_clause = filters
            
            # Perform search
            results = chroma.query(
                collection_name=self.collection_name,
                query_embeddings=[query_embedding],
                n_results=min(top_k * 2, 50),  # Get more results to have room for reranking
                where=where_clause,
                include=["metadatas", "documents", "distances"],
            )
            
            if not results or not results.get("ids") or not results["ids"][0]:
                return []
            
            # Map results to search result format
            search_results = []
            for idx, doc_id in enumerate(results["ids"][0]):
                metadata = results["metadatas"][0][idx]
                conversation_id = metadata["conversation_id"]
                message_id = metadata["message_id"]
                content = results["documents"][0][idx]
                score = 1.0 - (results["distances"][0][idx] or 0)
                
                # Skip results that are from the same user message
                if score < 0.3:  # Quality threshold
                    continue
                
                # Get context: ±2 messages around the matched message
                context = await self._get_message_context(
                    conversation_id, message_id, window=2
                )
                
                # Get conversation title
                conversation_title = await self._get_conversation_title(conversation_id)
                
                search_results.append({
                    "conversation_id": conversation_id,
                    "conversation_title": conversation_title,
                    "message_id": message_id,
                    "snippet": context,
                    "score": round(score, 4),
                    "timestamp": metadata["timestamp"],
                    "match_type": "vector",  # For now, only vector search
                    "role": metadata.get("role", "user"),
                })
            
            # Sort by score and limit results
            search_results.sort(key=lambda x: x["score"], reverse=True)
            return search_results[:top_k]
            
        except Exception as e:
            logger.error("Failed to search chat history: %s", e)
            return []
    
    async def _get_message_context(
        self,
        conversation_id: str,
        message_id: str,
        window: int = 2,
    ) -> str:
        """Get ±2 messages context around the matched message."""
        try:
            messages = await self._get_conversation_messages(
                conversation_id, before_message_id=message_id, limit=window + 1
            )
            
            # Find the message in the list
            target_idx = None
            for idx, msg in enumerate(messages):
                if msg["id"] == message_id:
                    target_idx = idx
                    break
            
            if target_idx is None:
                # Message not found, return just the message content
                msg = await self._get_message(conversation_id, message_id)
                return msg.get("content", "") if msg else ""
            
            # Build context window
            start = max(0, target_idx - window)
            end = min(len(messages), target_idx + window + 1)
            context_messages = messages[start:end]
            
            # Format as a snippet
            snippet_parts = []
            for msg in context_messages:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")[:200]  # Truncate long messages
                snippet_parts.append(f"{role}: {content}")
            
            return "\n".join(snippet_parts)
            
        except Exception as e:
            logger.error("Failed to get message context: %s", e)
            # Fallback: just return the message content
            msg = await self._get_message(conversation_id, message_id)
            return msg.get("content", "") if msg else ""
    
    async def _get_conversation_messages(
        self,
        conversation_id: str,
        before_message_id: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict]:
        """Get messages from a conversation."""
        db = db_module.database
        if not db:
            return []
        
        try:
            # This is a simplified version - in production, you'd want to implement
            # proper pagination and filtering
            return await db.get_conversation_history(conversation_id)
        except Exception as e:
            logger.error("Failed to get conversation messages: %s", e)
            return []
    
    async def _get_message(self, conversation_id: str, message_id: str) -> dict | None:
        """Get a single message by ID."""
        db = db_module.database
        if not db:
            return None
        
        try:
            # In production, implement a proper query
            messages = await db.get_conversation_history(conversation_id)
            for msg in messages:
                if msg.get("id") == message_id:
                    return msg
            return None
        except Exception as e:
            logger.error("Failed to get message: %s", e)
            return None
    
    async def _get_conversation_title(self, conversation_id: str) -> str:
        """Get the title of a conversation."""
        db = db_module.database
        if not db:
            return "Untitled Conversation"
        
        try:
            conv = await db.get_or_create_conversation(conversation_id)
            return conv.title or f"Conversation {conversation_id[:8]}"
        except Exception as e:
            logger.error("Failed to get conversation title: %s", e)
            return "Untitled Conversation"
    
    async def delete_message(self, conversation_id: str, message_id: str) -> bool:
        """Delete a message from the index."""
        try:
            chroma = await self._init_chroma()
            doc_id = f"{conversation_id}_{message_id}"
            chroma.delete(documents=[doc_id], collection_name=self.collection_name)
            return True
        except Exception as e:
            logger.error("Failed to delete chat message %s: %s", message_id, e)
            return False


# Global indexer instance
_indexer: ChatHistoryIndexer | None = None


async def get_chat_indexer() -> ChatHistoryIndexer:
    """Get or create the global chat history indexer instance."""
    global _indexer
    if _indexer is None:
        _indexer = ChatHistoryIndexer()
    return _indexer
