"""
One-time script to backfill chat history embeddings into ChromaDB.

This script processes all existing messages from the database and indexes them
into the chat_messages collection for semantic search. Should be run once after
deploying feature A5.
"""

import asyncio
import logging
from datetime import datetime

from backend.core import database
from backend.core.chat_indexer import ChatHistoryIndexer

logger = logging.getLogger(__name__)


async def backfill_chat_embeddings(batch_size: int = 100):
    """
    Backfill all chat messages from database into ChromaDB.

    Args:
        batch_size: Number of messages to process in each batch
    """
    logger.info("Starting chat history backfill...")

    # Initialize database
    db = database.get_database()
    if not db:
        raise RuntimeError("Database not initialized")

    # Initialize chat indexer
    indexer = ChatHistoryIndexer()
    await indexer.initialize()

    # Get total message count
    total_count = await db.count("SELECT COUNT(*) FROM messages")
    logger.info(f"Found {total_count} messages to process")

    if total_count == 0:
        logger.info("No messages to backfill")
        return

    # Process in batches
    offset = 0
    processed = 0

    while offset < total_count:
        # Get message batch
        batch = await db.execute(
            "SELECT id, conversation_id, agent_name, content, created_at FROM messages "
            "ORDER BY created_at ASC LIMIT ? OFFSET ?",
            (batch_size, offset),
        )

        if not batch:
            break

        # Index each message
        for row in batch:
            try:
                # Add to ChromaDB with metadata
                await indexer.add_message(
                    message_id=row["id"],
                    conversation_id=row["conversation_id"],
                    content=row["content"],
                    timestamp=row["created_at"],
                    agent_name=row["agent_name"],
                )
                processed += 1

                if processed % 100 == 0:
                    logger.info(f"Processed {processed}/{total_count} messages...")

            except Exception as e:
                logger.error(f"Failed to index message {row['id']}: {e}")

        offset += batch_size

    # Build BM25 index after all messages are added
    await indexer.build_keyword_index()

    logger.info(f"Backfill completed! Successfully indexed {processed} messages")
    logger.info(
        f"ChromaDB collection '{indexer.collection_name}' ready with hybrid search"
    )


async def verify_backfill():
    """Verify the backfill was successful."""
    indexer = ChatHistoryIndexer()
    await indexer.initialize()

    count = indexer.get_message_count()
    logger.info(f"Total messages in ChromaDB: {count}")

    # Run a test search
    results = await indexer.search("test query", top_k=5)
    logger.info(f"Test search returned {len(results)} results")

    return count


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    try:
        # Run backfill
        asyncio.run(backfill_chat_embeddings())

        # Verify
        asyncio.run(verify_backfill())

    except Exception as e:
        logger.error(f"Backfill failed: {e}", exc_info=True)
        exit(1)
