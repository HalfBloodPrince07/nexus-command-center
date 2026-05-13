import json
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
import logging

from sqlalchemy import select, func, and_

from backend.core.database import (
    ResearchSession,
    ResearchQuery,
    JournalEntry,
    LifeFact,
    ContentHash,
    get_session,
)

logger = logging.getLogger(__name__)


def extract_keywords(text: str) -> List[str]:
    """Extract simple keywords from text."""
    if not text:
        return []
    # Simple extraction - split on whitespace, filter short words
    words = [w.strip().lower() for w in text.split() if len(w.strip()) > 3]
    # Filter common stop words
    stop_words = {
        "the",
        "and",
        "for",
        "are",
        "but",
        "not",
        "you",
        "all",
        "can",
        "had",
        "her",
        "was",
        "one",
        "our",
        "out",
        "day",
        "get",
        "has",
        "him",
        "his",
        "how",
        "its",
        "may",
        "new",
        "now",
        "old",
        "see",
        "two",
        "way",
        "who",
        "boy",
        "did",
        "its",
        "let",
        "put",
        "say",
        "she",
        "too",
        "use",
    }
    return [w for w in words if w not in stop_words]


async def extract_topics_from_research_sessions(
    period_days: int = 30,
) -> List[Dict[str, Any]]:
    """Extract topics from research sessions and queries within the specified period."""
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=period_days)

        async with get_session() as session:
            # Get research sessions
            stmt = select(ResearchSession).where(
                and_(
                    ResearchSession.started_at >= cutoff,
                    ResearchSession.status != "failed",
                )
            )
            result = await session.execute(stmt)
            sessions = result.scalars().all()

            topic_freq: Dict[str, int] = {}

            # Extract from session titles
            for session in sessions:
                if session.title:
                    keywords = extract_keywords(session.title)
                    for kw in keywords:
                        topic_freq[kw] = topic_freq.get(kw, 0) + 1

            # Also extract from queries
            query_stmt = select(ResearchQuery).where(ResearchQuery.created_at >= cutoff)
            query_result = await session.execute(query_stmt)
            queries = query_result.scalars().all()

            for query in queries:
                if query.query_text:
                    keywords = extract_keywords(query.query_text)
                    for kw in keywords:
                        topic_freq[kw] = topic_freq.get(kw, 0) + 1

            # Sort by frequency and return top topics
            sorted_topics = sorted(topic_freq.items(), key=lambda x: x[1], reverse=True)

            return [
                {"topic": topic, "count": count, "source": "research"}
                for topic, count in sorted_topics[:50]
            ]
    except Exception as e:
        logger.error("Failed to extract topics from research sessions: %s", e)
        return []


async def extract_topics_from_journal(
    period_days: int = 30,
) -> List[Dict[str, Any]]:
    """Extract topics from journal entries within the specified period."""
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=period_days)

        async with get_session() as session:
            # Get journal entries
            stmt = select(JournalEntry).where(JournalEntry.created_at >= cutoff)
            result = await session.execute(stmt)
            entries = result.scalars().all()

            topic_freq: Dict[str, int] = {}

            # Extract from entry bodies
            for entry in entries:
                if entry.body_md:
                    keywords = extract_keywords(entry.body_md)
                    for kw in keywords:
                        topic_freq[kw] = topic_freq.get(kw, 0) + 1

            # Sort by frequency and return top topics
            sorted_topics = sorted(topic_freq.items(), key=lambda x: x[1], reverse=True)

            return [
                {"topic": topic, "count": count, "source": "journal"}
                for topic, count in sorted_topics[:50]
            ]
    except Exception as e:
        logger.error("Failed to extract topics from journal: %s", e)
        return []


async def extract_topics_from_files(
    period_days: int = 30,
) -> List[Dict[str, Any]]:
    """Extract topics from indexed files and life facts within the specified period."""
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=period_days)

        async with get_session() as session:
            # Get life facts (these often contain extracted entities/concepts)
            stmt = select(LifeFact).where(LifeFact.first_seen >= cutoff)
            result = await session.execute(stmt)
            facts = result.scalars().all()

            topic_freq: Dict[str, int] = {}

            # Extract from life facts
            for fact in facts:
                if fact.fact:
                    # Simple extraction - split into words and look for capitalized terms/nouns
                    keywords = extract_keywords(fact.fact)
                    for kw in keywords:
                        topic_freq[kw] = topic_freq.get(kw, 0) + 1

            # Sort by frequency and return top topics
            sorted_topics = sorted(topic_freq.items(), key=lambda x: x[1], reverse=True)

            return [
                {"topic": topic, "count": count, "source": "file"}
                for topic, count in sorted_topics[:50]
            ]
    except Exception as e:
        logger.error("Failed to extract topics from files: %s", e)
        return []


async def aggregate_all_topics(
    period_days: int = 30,
) -> List[Dict[str, Any]]:
    """Aggregate topics from all sources and calculate frequencies."""
    try:
        # Extract from each source
        research_topics = await extract_topics_from_research_sessions(period_days)
        journal_topics = await extract_topics_from_journal(period_days)
        file_topics = await extract_topics_from_files(period_days)

        # Combine and aggregate
        all_topics: Dict[str, Dict[str, Any]] = {}

        # Aggregate research topics
        for item in research_topics:
            topic = item["topic"]
            if topic not in all_topics:
                all_topics[topic] = {"count": 0, "sources": []}
            all_topics[topic]["count"] += item["count"]
            if "research" not in all_topics[topic]["sources"]:
                all_topics[topic]["sources"].append("research")

        # Aggregate journal topics
        for item in journal_topics:
            topic = item["topic"]
            if topic not in all_topics:
                all_topics[topic] = {"count": 0, "sources": []}
            all_topics[topic]["count"] += item["count"]
            if "journal" not in all_topics[topic]["sources"]:
                all_topics[topic]["sources"].append("journal")

        # Aggregate file topics
        for item in file_topics:
            topic = item["topic"]
            if topic not in all_topics:
                all_topics[topic] = {"count": 0, "sources": []}
            all_topics[topic]["count"] += item["count"]
            if "file" not in all_topics[topic]["sources"]:
                all_topics[topic]["sources"].append("file")

        # Convert to list and sort by total count
        result = [
            {"topic": topic, "count": data["count"], "sources": data["sources"]}
            for topic, data in all_topics.items()
        ]

        result.sort(key=lambda x: x["count"], reverse=True)

        return result[:100]  # Top 100 topics
    except Exception as e:
        logger.error("Failed to aggregate all topics: %s", e)
        return []
