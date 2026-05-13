import logging
from datetime import datetime, timezone, timedelta
import uuid
import json
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager

from sqlalchemy import select, func, update, delete, and_, CheckConstraint, text
from sqlalchemy.orm import sessionmaker, declarative_base, Mapped, mapped_column
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import String, DateTime, Integer, Text, Float, Boolean

from backend.config import settings

# Configure logging
logger = logging.getLogger(__name__)

DATABASE_URL = f"sqlite+aiosqlite:///{settings.DATABASE_PATH}"


class DatabaseError(Exception):
    """Custom exception for database operations."""

    pass


try:
    # check_same_thread is required for SQLite
    async_engine = create_async_engine(
        DATABASE_URL, connect_args={"check_same_thread": False}, echo=False
    )
    async_session_maker = sessionmaker(
        bind=async_engine, class_=AsyncSession, expire_on_commit=False
    )
except Exception as e:
    logger.critical("Failed to create database engine: %s", e)
    raise DatabaseError(f"Failed to create database engine: {e}") from e

Base = declarative_base()

# ── ORM Models ────────────────────────────────────────────────────────────────


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    title: Mapped[Optional[str]] = mapped_column(String)
    message_count: Mapped[int] = mapped_column(Integer, default=0)


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    conversation_id: Mapped[str] = mapped_column(String, index=True)
    role: Mapped[str] = mapped_column(String)  # "user", "assistant", "system"
    content: Mapped[str] = mapped_column(Text)
    agent_id: Mapped[Optional[str]] = mapped_column(String)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    token_count: Mapped[Optional[int]] = mapped_column(Integer)


class ResearchSession(Base):
    __tablename__ = "research_sessions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','running','drafting','fact_checking','done','failed')",
            name="ck_research_session_status",
        ),
    )
    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    raw_query: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, default="pending", nullable=False)
    phase: Mapped[str] = mapped_column(String, default="init", nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    error_log: Mapped[Optional[str]] = mapped_column(Text)
    config_json: Mapped[Optional[str]] = mapped_column(Text)


class ResearchQuery(Base):
    __tablename__ = "research_queries"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    query_type: Mapped[Optional[str]] = mapped_column(String)
    search_engine: Mapped[Optional[str]] = mapped_column(String)
    results_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


class ScrapedSource(Base):
    __tablename__ = "scraped_sources"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    query_id: Mapped[Optional[str]] = mapped_column(String)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[Optional[str]] = mapped_column(String)
    title: Mapped[Optional[str]] = mapped_column(Text)
    author: Mapped[Optional[str]] = mapped_column(String)
    published_date: Mapped[Optional[str]] = mapped_column(String)
    scraped_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    quality_score: Mapped[float] = mapped_column(Float, default=0.0)
    domain_authority_score: Mapped[float] = mapped_column(Float, default=0.0)
    is_paywalled: Mapped[bool] = mapped_column(Boolean, default=False)
    is_javascript_rendered: Mapped[bool] = mapped_column(Boolean, default=False)
    raw_html_path: Mapped[Optional[str]] = mapped_column(Text)
    clean_text_path: Mapped[Optional[str]] = mapped_column(Text)
    scrape_status: Mapped[str] = mapped_column(String, default="pending")
    error_message: Mapped[Optional[str]] = mapped_column(Text)


class ContentChunk(Base):
    __tablename__ = "content_chunks"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    chunk_index: Mapped[Optional[int]] = mapped_column(Integer)
    chunk_text: Mapped[Optional[str]] = mapped_column(Text)
    chroma_doc_id: Mapped[Optional[str]] = mapped_column(String)
    token_count: Mapped[Optional[int]] = mapped_column(Integer)


class ReportOutline(Base):
    __tablename__ = "report_outline"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    section_number: Mapped[Optional[int]] = mapped_column(Integer)
    section_title: Mapped[Optional[str]] = mapped_column(Text)
    section_brief: Mapped[Optional[str]] = mapped_column(Text)
    assigned_sources: Mapped[Optional[str]] = mapped_column(Text)
    keywords: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, default="pending")


class DraftedSection(Base):
    __tablename__ = "drafted_sections"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    outline_id: Mapped[Optional[str]] = mapped_column(String)
    section_number: Mapped[Optional[int]] = mapped_column(Integer)
    section_title: Mapped[Optional[str]] = mapped_column(Text)
    draft_content: Mapped[Optional[str]] = mapped_column(Text)
    word_count: Mapped[Optional[int]] = mapped_column(Integer)
    sources_cited: Mapped[Optional[str]] = mapped_column(Text)
    draft_iteration: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


class Claim(Base):
    __tablename__ = "claims"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_section: Mapped[Optional[str]] = mapped_column(Text)
    verification_status: Mapped[Optional[str]] = mapped_column(String)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    supporting_urls: Mapped[Optional[str]] = mapped_column(Text)
    contradicting_urls: Mapped[Optional[str]] = mapped_column(Text)
    corrected_text: Mapped[Optional[str]] = mapped_column(Text)
    citation_key: Mapped[Optional[str]] = mapped_column(String)


class OutputArtifact(Base):
    __tablename__ = "output_artifacts"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    artifact_type: Mapped[Optional[str]] = mapped_column(String)
    file_path: Mapped[Optional[str]] = mapped_column(Text)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


class WatchedFolder(Base):
    __tablename__ = "watched_folders"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    path: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    collection: Mapped[str] = mapped_column(String, default="files")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


class File(Base):
    __tablename__ = "files"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'processing', 'ready', 'error')",
            name="ck_file_status",
        ),
    )
    id: Mapped[str] = mapped_column(String, primary_key=True)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    original_name: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[Optional[str]] = mapped_column(Text)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String, default="pending", nullable=False)
    collection: Mapped[str] = mapped_column(String, default="files")
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    content_hash: Mapped[Optional[str]] = mapped_column(
        String, nullable=True, index=True
    )
    file_metadata: Mapped[str] = mapped_column("metadata", Text, default="{}")


class ContentHash(Base):
    __tablename__ = "content_hashes"
    content_hash: Mapped[str] = mapped_column(String, primary_key=True)
    file_id: Mapped[str] = mapped_column(String, index=True)
    original_name: Mapped[str] = mapped_column(Text)
    collection: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


class ProceduralMemory(Base):
    __tablename__ = "procedural_memories"
    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    pattern_type: Mapped[str] = mapped_column(String, index=True)
    trigger: Mapped[str] = mapped_column(Text)
    action: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    use_count: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    session_id: Mapped[Optional[str]] = mapped_column(String)


class ConversationStat(Base):
    __tablename__ = "conversation_stats"
    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    session_id: Mapped[str] = mapped_column(String, index=True)
    date: Mapped[str] = mapped_column(String, index=True)
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    total_response_ms: Mapped[int] = mapped_column(Integer, default=0)
    response_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


class MemoryRecord(Base):
    __tablename__ = "memory_records"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    layer: Mapped[str] = mapped_column(String, index=True)  # "short","working","long"
    category: Mapped[Optional[str]] = mapped_column(String, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_agent: Mapped[Optional[str]] = mapped_column(String)
    source_ref: Mapped[Optional[str]] = mapped_column(String)
    confidence: Mapped[float] = mapped_column(Float, default=0.6)
    importance: Mapped[float] = mapped_column(Float, default=0.5)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    last_reinforced_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    chroma_id: Mapped[Optional[str]] = mapped_column(String)


class MemoryLink(Base):
    __tablename__ = "memory_links"
    src_id: Mapped[str] = mapped_column(String, primary_key=True)
    dst_id: Mapped[str] = mapped_column(String, primary_key=True)
    relation: Mapped[str] = mapped_column(String, primary_key=True)
    weight: Mapped[float] = mapped_column(Float, default=1.0)


class Insight(Base):
    __tablename__ = "insights"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    category: Mapped[Optional[str]] = mapped_column(String)
    severity: Mapped[float] = mapped_column(Float, default=0.0)
    title: Mapped[Optional[str]] = mapped_column(String)
    body_md: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_json: Mapped[Optional[str]] = mapped_column(Text)
    chart_payload_json: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class Briefing(Base):
    __tablename__ = "briefings"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    body_md: Mapped[str] = mapped_column(Text, nullable=False)
    hero_chart_json: Mapped[Optional[str]] = mapped_column(Text)
    mood_summary: Mapped[Optional[str]] = mapped_column(Text)
    insights_json: Mapped[Optional[str]] = mapped_column(Text)
    yesterday_journal_recap: Mapped[Optional[str]] = mapped_column(Text)
    mood_trend_direction: Mapped[Optional[str]] = mapped_column(Text)
    pending_research_json: Mapped[Optional[str]] = mapped_column(Text)
    new_files_count: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    top_3_files_json: Mapped[Optional[str]] = mapped_column(Text)
    predictive_patterns_json: Mapped[Optional[str]] = mapped_column(Text)
    goals_progress_json: Mapped[Optional[str]] = mapped_column(Text)
    suggested_focus: Mapped[Optional[str]] = mapped_column(Text)
    tags: Mapped[str] = mapped_column(Text, default="briefing")


class Goal(Base):
    __tablename__ = "goals"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    metric_type: Mapped[str] = mapped_column(String, nullable=False)
    target_value: Mapped[Optional[float]] = mapped_column(Float)
    target_period: Mapped[str] = mapped_column(String, nullable=False)
    start_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


class GoalEvent(Base):
    __tablename__ = "goal_events"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    goal_id: Mapped[str] = mapped_column(String, nullable=False)
    detected_from: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[Optional[float]] = mapped_column(Float)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    notes: Mapped[Optional[str]] = mapped_column(Text)
    confidence: Mapped[Optional[float]] = mapped_column(Float)


class MemoryConflict(Base):
    __tablename__ = "memory_conflicts"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    fact_a_id: Mapped[str] = mapped_column(String, nullable=False)
    fact_b_id: Mapped[str] = mapped_column(String, nullable=False)
    conflict_type: Mapped[str] = mapped_column(
        String, nullable=False
    )  # factual, temporal, preferential
    explanation: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String, default="open"
    )  # open, reviewing, resolved, dismissed
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class AnalyticsSnapshot(Base):
    __tablename__ = "analytics_snapshots"
    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    query_key: Mapped[str] = mapped_column(String, nullable=False, index=True)
    data: Mapped[str] = mapped_column(Text, nullable=False)  # JSON string
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class CustomAgent(Base):
    __tablename__ = "custom_agents"
    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(String, index=True)
    name: Mapped[str] = mapped_column(
        String, unique=True, index=True
    )  # e.g. "recipe-helper"
    display_name: Mapped[Optional[str]] = mapped_column(String)
    tagline: Mapped[Optional[str]] = mapped_column(Text)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    allowed_tools: Mapped[Optional[str]] = mapped_column(
        Text
    )  # JSON array: ["search_web", "save_memory"]
    parent_cluster: Mapped[Optional[str]] = mapped_column(
        String
    )  # knowledge|research|journal|memory|none
    ui_config: Mapped[Optional[str]] = mapped_column(Text)  # {color, icon}
    temperature: Mapped[float] = mapped_column(Float, default=0.7)
    max_tokens: Mapped[int] = mapped_column(Integer, default=2048)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


class CustomAgentInvocation(Base):
    __tablename__ = "custom_agent_invocations"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    agent_id: Mapped[str] = mapped_column(String, index=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    system_prompt_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    response: Mapped[Optional[str]] = mapped_column(Text)
    tools_used: Mapped[Optional[str]] = mapped_column(Text)  # JSON array of tool names
    tool_params: Mapped[Optional[str]] = mapped_column(Text)  # JSON object with params
    started_at: Mapped[datetime] = mapped_column(DateTime)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    succeeded: Mapped[Optional[bool]] = mapped_column(Boolean)


class ScheduledJob(Base):
    __tablename__ = "scheduled_jobs"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    started_at: Mapped[datetime] = mapped_column(DateTime)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String)
    error: Mapped[Optional[str]] = mapped_column(Text)


class JournalEntry(Base):
    __tablename__ = "journal_entries"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    body_md: Mapped[str] = mapped_column(Text, nullable=False)
    word_count: Mapped[Optional[int]] = mapped_column(Integer)
    title: Mapped[Optional[str]] = mapped_column(String)
    tags: Mapped[Optional[str]] = mapped_column(Text)


class MoodScore(Base):
    __tablename__ = "mood_scores"
    entry_id: Mapped[str] = mapped_column(String, primary_key=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    emotions: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    model: Mapped[Optional[str]] = mapped_column(String)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), index=True
    )


class LifeFact(Base):
    __tablename__ = "life_facts"
    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    fact: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String)
    source_entry_id: Mapped[Optional[str]] = mapped_column(String)
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    first_seen: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    last_reinforced: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


class Relationship(Base):
    __tablename__ = "relationships"
    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    aliases: Mapped[Optional[str]] = mapped_column(Text)
    relation_type: Mapped[Optional[str]] = mapped_column(String)
    sentiment_avg: Mapped[Optional[float]] = mapped_column(Float)
    interaction_count: Mapped[int] = mapped_column(Integer, default=0)
    last_seen: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


class Interaction(Base):
    __tablename__ = "interactions"
    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    relationship_id: Mapped[str] = mapped_column(String, index=True)
    entry_id: Mapped[str] = mapped_column(String, index=True)
    sentiment: Mapped[Optional[float]] = mapped_column(Float)
    snippet: Mapped[Optional[str]] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


class Decision(Base):
    __tablename__ = "decisions"
    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[Optional[str]] = mapped_column(String)
    analysis_json: Mapped[Optional[str]] = mapped_column(Text)
    chosen_option: Mapped[Optional[str]] = mapped_column(String)
    outcome: Mapped[Optional[str]] = mapped_column(Text)
    outcome_recorded_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


# ── Helpers ───────────────────────────────────────────────────────────────────


@asynccontextmanager
async def get_session() -> AsyncSession:
    session = async_session_maker()
    try:
        yield session
        await session.commit()
    except Exception as e:
        await session.rollback()
        logger.error("Database session error: %s", e)
        raise DatabaseError(f"Session error: {e}") from e
    finally:
        await session.close()


async def init_db() -> None:
    global database
    async with async_engine.begin() as conn:
        try:
            await conn.run_sync(Base.metadata.create_all)
            for migration_sql in ["ALTER TABLE files ADD COLUMN content_hash TEXT"]:
                try:
                    await conn.execute(text(migration_sql))
                except Exception:
                    pass
            logger.info("Database initialized successfully.")
            if database is None:
                database = Database()
        except Exception as e:
            logger.error("Failed to initialize database: %s", e)
            raise DatabaseError(f"Failed to initialize DB: {e}") from e


async def get_or_create_conversation(conversation_id: str) -> Conversation:
    async with get_session() as session:
        res = await session.get(Conversation, conversation_id)
        if res:
            return res
        new_convo = Conversation(id=conversation_id)
        session.add(new_convo)
        return new_convo


async def save_message(
    conversation_id: str, role: str, content: str, agent_id: str = "supervisor"
) -> Message:
    async with get_session() as session:
        convo = await session.get(Conversation, conversation_id)
        if not convo:
            convo = Conversation(id=conversation_id)
            session.add(convo)
            await session.flush()
        if role == "user" and not convo.title:
            convo.title = content[:72]
        msg = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            agent_id=agent_id,
        )
        session.add(msg)
        convo.updated_at, convo.message_count = (
            datetime.now(timezone.utc),
            convo.message_count + 1,
        )
        await session.flush()
        return msg


async def get_conversation_history(
    conversation_id: str, limit: int = 20
) -> List[Dict[str, Any]]:
    async with get_session() as session:
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.timestamp.desc())
            .limit(limit)
        )
        res = await session.execute(stmt)
        return [
            {
                "role": m.role,
                "content": m.content,
                "agent_id": m.agent_id,
                "timestamp": m.timestamp,
            }
            for m in reversed(res.scalars().all())
        ]


async def clear_conversation(conversation_id: str) -> None:
    async with get_session() as session:
        await session.execute(
            delete(Message).where(Message.conversation_id == conversation_id)
        )
        await session.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(message_count=0, updated_at=datetime.now(timezone.utc))
        )


async def get_all_conversations() -> List[Dict[str, Any]]:
    async with get_session() as session:
        earliest = (
            select(Message.conversation_id, func.min(Message.timestamp).label("ts"))
            .where(Message.role == "user")
            .group_by(Message.conversation_id)
            .subquery()
        )
        first = (
            select(Message.conversation_id, Message.content)
            .join(
                earliest,
                and_(
                    Message.conversation_id == earliest.c.conversation_id,
                    Message.timestamp == earliest.c.ts,
                ),
            )
            .subquery()
        )
        stmt = (
            select(Conversation, first.c.content)
            .outerjoin(first, Conversation.id == first.c.conversation_id)
            .order_by(Conversation.updated_at.desc())
        )
        res = await session.execute(stmt)
        return [
            {
                "id": c.id,
                "title": c.title or (f[:72] if f else None),
                "message_count": c.message_count,
                "created_at": c.created_at,
                "updated_at": c.updated_at,
            }
            for c, f in res.all()
        ]


async def create_research_session(
    session_id: str,
    title: str,
    raw_query: str,
    slug: str,
    config_json: str | None = None,
) -> None:
    async with get_session() as session:
        session.add(
            ResearchSession(
                id=session_id,
                title=title,
                raw_query=raw_query,
                slug=slug,
                config_json=config_json,
            )
        )
        await session.flush()


async def update_research_session(session_id: str, **kwargs) -> None:
    async with get_session() as session:
        if kwargs.get("status") in ("done", "failed"):
            kwargs["completed_at"] = datetime.now(timezone.utc)
        elif kwargs.get("status") == "running":
            kwargs["started_at"] = datetime.now(timezone.utc)
        await session.execute(
            update(ResearchSession)
            .where(ResearchSession.id == session_id)
            .values(**kwargs)
        )
        await session.flush()


async def get_research_session(session_id: str) -> dict | None:
    async with get_session() as session:
        r = await session.get(ResearchSession, session_id)
        return (
            {"session_id": r.id, "title": r.title, "slug": r.slug, "status": r.status}
            if r
            else None
        )


async def list_research_sessions() -> list[dict]:
    async with get_session() as session:
        res = await session.execute(
            select(ResearchSession).order_by(ResearchSession.started_at.desc())
        )
        return [
            {"session_id": r.id, "title": r.title, "slug": r.slug, "status": r.status}
            for r in res.scalars().all()
        ]


async def delete_research_session_by_slug(slug: str) -> None:
    async with get_session() as session:
        rs = (
            (
                await session.execute(
                    select(ResearchSession).where(ResearchSession.slug == slug)
                )
            )
            .scalars()
            .first()
        )
        if rs:
            for tbl in [
                OutputArtifact,
                Claim,
                DraftedSection,
                ReportOutline,
                ContentChunk,
                ScrapedSource,
                ResearchQuery,
                ResearchSession,
            ]:
                await session.execute(
                    delete(tbl).where(
                        tbl.session_id == rs.id
                        if hasattr(tbl, "session_id")
                        else tbl.id == rs.id
                    )
                )


async def insert_research_query(
    query_id: str, session_id: str, query_text: str, **kwargs
) -> None:
    async with get_session() as session:
        session.add(
            ResearchQuery(
                id=query_id, session_id=session_id, query_text=query_text, **kwargs
            )
        )
        await session.flush()


async def insert_scraped_source(
    source_id: str, session_id: str, url: str, **kwargs
) -> None:
    async with get_session() as session:
        session.add(
            ScrapedSource(
                id=source_id,
                session_id=session_id,
                url=url,
                scraped_at=datetime.now(timezone.utc),
                **kwargs,
            )
        )
        await session.flush()


async def insert_content_chunk(
    chunk_id: str,
    session_id: str,
    source_id: str,
    chunk_text: str,
    chunk_index: int,
    **kwargs,
) -> None:
    async with get_session() as session:
        session.add(
            ContentChunk(
                id=chunk_id,
                session_id=session_id,
                source_id=source_id,
                chunk_text=chunk_text,
                chunk_index=chunk_index,
                **kwargs,
            )
        )
        await session.flush()


async def insert_report_outline(
    outline_id: str,
    session_id: str,
    section_number: int,
    section_title: str,
    section_brief: str,
    **kwargs,
) -> None:
    async with get_session() as session:
        session.add(
            ReportOutline(
                id=outline_id,
                session_id=session_id,
                section_number=section_number,
                section_title=section_title,
                section_brief=section_brief,
                **kwargs,
            )
        )
        await session.flush()


async def insert_drafted_section(
    section_id: str,
    session_id: str,
    outline_id: str,
    section_number: int,
    section_title: str,
    draft_content: str,
    **kwargs,
) -> None:
    async with get_session() as session:
        session.add(
            DraftedSection(
                id=section_id,
                session_id=session_id,
                outline_id=outline_id,
                section_number=section_number,
                section_title=section_title,
                draft_content=draft_content,
                **kwargs,
            )
        )
        await session.flush()


async def insert_claim(
    claim_id: str, session_id: str, claim_text: str, **kwargs
) -> None:
    async with get_session() as session:
        session.add(
            Claim(id=claim_id, session_id=session_id, claim_text=claim_text, **kwargs)
        )
        await session.flush()


async def insert_output_artifact(
    artifact_id: str, session_id: str, artifact_type: str, file_path: str, **kwargs
) -> None:
    async with get_session() as session:
        session.add(
            OutputArtifact(
                id=artifact_id,
                session_id=session_id,
                artifact_type=artifact_type,
                file_path=file_path,
                **kwargs,
            )
        )
        await session.flush()


async def get_sources_for_session(session_id: str) -> list[dict]:
    async with get_session() as session:
        res = await session.execute(
            select(ScrapedSource)
            .where(ScrapedSource.session_id == session_id)
            .order_by(ScrapedSource.quality_score.desc())
        )
        return [
            {"id": s.id, "url": s.url, "title": s.title, "quality": s.quality_score}
            for s in res.scalars().all()
        ]


class Database:
    async def save_file_record(
        self,
        file_id: str,
        filename: str,
        original_name: str,
        mime_type: Optional[str],
        size_bytes: int,
        collection: str = "files",
    ) -> str:
        async with get_session() as session:
            session.add(
                File(
                    id=file_id,
                    filename=filename,
                    original_name=original_name,
                    mime_type=mime_type,
                    size_bytes=size_bytes,
                    uploaded_at=datetime.now(timezone.utc),
                    collection=collection,
                )
            )
            await session.flush()
        return file_id

    async def update_file_status(
        self,
        file_id: str,
        status: str,
        chunk_count: int = 0,
        processed_at: Optional[datetime] = None,
        error_message: Optional[str] = None,
    ) -> bool:
        async with get_session() as session:
            values = {
                "status": status,
                "chunk_count": chunk_count,
                "processed_at": processed_at or datetime.now(timezone.utc),
            }
            if error_message:
                row = await session.get(File, file_id)
                meta = (
                    json.loads(row.file_metadata) if row and row.file_metadata else {}
                )
                meta["error_message"] = error_message
                values["file_metadata"] = json.dumps(meta)
            await session.execute(
                update(File).where(File.id == file_id).values(**values)
            )
            await session.flush()
        return True

    async def list_files(
        self, collection: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        async with get_session() as session:
            stmt = select(File)
            if collection:
                stmt = stmt.where(File.collection == collection)
            res = await session.execute(stmt.order_by(File.uploaded_at.desc()))
            return [
                {
                    "id": f.id,
                    "original_name": f.original_name,
                    "status": f.status,
                    "uploaded_at": f.uploaded_at,
                }
                for f in res.scalars().all()
            ]

    async def get_file(self, file_id: str) -> Optional[Dict[str, Any]]:
        async with get_session() as session:
            f = await session.get(File, file_id)
            return (
                {
                    "id": f.id,
                    "filename": f.filename,
                    "original_name": f.original_name,
                    "status": f.status,
                }
                if f
                else None
            )

    async def delete_file_record(self, file_id: str) -> bool:
        async with get_session() as session:
            res = await session.execute(delete(File).where(File.id == file_id))
            await session.flush()
            return bool(res.rowcount)

    async def delete_content_hash_by_file_id(self, file_id: str) -> None:
        async with get_session() as session:
            await session.execute(
                delete(ContentHash).where(ContentHash.file_id == file_id)
            )
            await session.flush()

    async def store_content_hash(
        self, content_hash: str, file_id: str, original_name: str, collection: str
    ) -> None:
        async with get_session() as session:
            session.add(
                ContentHash(
                    content_hash=content_hash,
                    file_id=file_id,
                    original_name=original_name,
                    collection=collection,
                )
            )
            await session.execute(
                update(File).where(File.id == file_id).values(content_hash=content_hash)
            )
            await session.flush()

    async def add_watched_folder(
        self, watcher_id: str, path: str, collection: str = "files"
    ) -> str:
        async with get_session() as session:
            session.add(
                WatchedFolder(
                    id=watcher_id,
                    path=path,
                    collection=collection,
                    is_active=True,
                    created_at=datetime.now(timezone.utc),
                )
            )
            await session.flush()
        return watcher_id

    async def remove_watched_folder(self, watcher_id: str) -> bool:
        async with get_session() as session:
            res = await session.execute(
                delete(WatchedFolder).where(WatchedFolder.id == watcher_id)
            )
            await session.flush()
            return bool(res.rowcount)

    async def get_all_watched_folders(self) -> list[dict]:
        async with get_session() as session:
            res = await session.execute(
                select(WatchedFolder).where(WatchedFolder.is_active == True)
            )
            return [
                {
                    "id": wf.id,
                    "path": wf.path,
                    "collection": wf.collection,
                    "is_active": wf.is_active,
                    "created_at": wf.created_at,
                }
                for wf in res.scalars().all()
            ]

    async def get_watched_folder(self, watcher_id: str) -> dict | None:
        async with get_session() as session:
            wf = await session.get(WatchedFolder, watcher_id)
            if wf:
                return {
                    "id": wf.id,
                    "path": wf.path,
                    "collection": wf.collection,
                    "is_active": wf.is_active,
                    "created_at": wf.created_at,
                }
            return None

    async def add_custom_agent(self, **kwargs) -> str:
        """Add a new custom agent."""
        async with get_session() as session:
            agent = CustomAgent(user_id=kwargs.get("user_id", "user"), **kwargs)
            session.add(agent)
            await session.flush()
            return str(agent.id)

    async def get_custom_agents(self, user_id: str) -> list[dict[str, Any]]:
        """List all enabled custom agents for user."""
        async with get_session() as session:
            stmt = select(CustomAgent).where(
                CustomAgent.user_id == user_id, CustomAgent.enabled == True
            )
            result = await session.execute(stmt.order_by(CustomAgent.created_at.desc()))
            agents = result.scalars().all()
            return [
                {
                    "id": a.id,
                    "name": a.name,
                    "display_name": a.display_name,
                    "tagline": a.tagline,
                    "system_prompt": a.system_prompt,
                    "allowed_tools": json.loads(a.allowed_tools or "[]"),
                    "parent_cluster": a.parent_cluster,
                    "ui_config": json.loads(a.ui_config or "{}"),
                    "temperature": a.temperature,
                    "max_tokens": a.max_tokens,
                    "enabled": a.enabled,
                    "created_at": a.created_at,
                    "updated_at": a.updated_at,
                }
                for a in agents
            ]

    async def get_custom_agent(
        self, agent_id: str, user_id: str
    ) -> dict[str, Any] | None:
        """Get specific agent by ID."""
        async with get_session() as session:
            agent = await session.get(CustomAgent, agent_id)
            if not agent or agent.user_id != user_id:
                return None
            return {
                "id": agent.id,
                "user_id": agent.user_id,
                "name": agent.name,
                "display_name": agent.display_name,
                "tagline": agent.tagline,
                "system_prompt": agent.system_prompt,
                "allowed_tools": json.loads(agent.allowed_tools or "[]"),
                "parent_cluster": agent.parent_cluster,
                "ui_config": json.loads(agent.ui_config or "{}"),
                "temperature": agent.temperature,
                "max_tokens": agent.max_tokens,
                "enabled": agent.enabled,
                "created_at": agent.created_at,
                "updated_at": agent.updated_at,
            }

    async def update_custom_agent(self, agent_id: str, user_id: str, **updates) -> bool:
        """Update custom agent fields."""
        async with get_session() as session:
            agent = await session.get(CustomAgent, agent_id)
            if not agent or agent.user_id != user_id:
                return False
            for key, value in updates.items():
                if hasattr(agent, key):
                    setattr(agent, key, value)
            agent.updated_at = datetime.now(timezone.utc)
            await session.flush()
            return True

    async def delete_custom_agent(self, agent_id: str, user_id: str) -> bool:
        """Soft-delete/Disable a custom agent."""
        async with get_session() as session:
            res = await session.execute(
                update(CustomAgent)
                .where(CustomAgent.id == agent_id, CustomAgent.user_id == user_id)
                .values(enabled=False, updated_at=datetime.now(timezone.utc))
            )
            await session.flush()
            return bool(res.rowcount)

    async def get_custom_agent_count(self, user_id: str) -> int:
        """Count enabled agents for user (enforces limit)."""
        async with get_session() as session:
            from sqlalchemy import func

            stmt = select(func.count()).where(
                CustomAgent.user_id == user_id, CustomAgent.enabled == True
            )
            result = await session.execute(stmt)
            return result.scalar_one()

    async def add_custom_agent_invocation(self, **params) -> str:
        """Log a custom agent invocation for audit trail."""
        async with get_session() as session:
            inv_id = str(uuid.uuid4())
            inv = CustomAgentInvocation(id=inv_id, **params)
            session.add(inv)
            await session.flush()
            return inv_id

    async def get_custom_agent_invocations(
        self, agent_id: str, user_id: str
    ) -> list[dict[str, Any]]:
        """Get audit log for a custom agent."""
        async with get_session() as session:
            stmt = (
                select(CustomAgentInvocation)
                .where(
                    CustomAgentInvocation.agent_id == agent_id,
                    CustomAgentInvocation.user_id == user_id,
                )
                .order_by(CustomAgentInvocation.started_at.desc())
                .limit(100)
            )
            result = await session.execute(stmt)
            invocations = result.scalars().all()
            return [
                {
                    "id": inv.id,
                    "prompt": inv.prompt,
                    "tools_used": json.loads(inv.tools_used or "[]"),
                    "succeeded": inv.succeeded,
                    "started_at": inv.started_at,
                    "completed_at": inv.completed_at,
                }
                for inv in invocations
            ]

    async def deactivate_watched_folder(self, watcher_id: str) -> bool:
        async with get_session() as session:
            res = await session.execute(
                update(WatchedFolder)
                .where(WatchedFolder.id == watcher_id)
                .values(is_active=False)
            )
            await session.flush()
            return bool(res.rowcount)

    async def get_analytics_snapshot(
        self, user_id: str, query_key: str
    ) -> Optional[Dict[str, Any]]:
        """Retrieve cached analytics result if not expired."""
        async with get_session() as session:
            result = await session.execute(
                select(AnalyticsSnapshot)
                .where(
                    AnalyticsSnapshot.user_id == user_id,
                    AnalyticsSnapshot.query_key == query_key,
                    AnalyticsSnapshot.expires_at > datetime.now(timezone.utc),
                )
                .order_by(AnalyticsSnapshot.created_at.desc())
            )
            snapshot = result.scalars().first()
            if snapshot:
                return json.loads(snapshot.data)
            return None

    async def set_analytics_snapshot(
        self, user_id: str, query_key: str, data: Dict[str, Any], ttl_seconds: int = 21600
    ) -> None:
        """Store analytics result with TTL (default 6 hours)."""
        async with get_session() as session:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
            session.add(
                AnalyticsSnapshot(
                    user_id=user_id,
                    query_key=query_key,
                    data=json.dumps(data),
                    expires_at=expires_at,
                )
            )
            await session.flush()

    async def cleanup_expired_snapshots(self) -> int:
        """Remove expired analytics snapshots."""
        async with get_session() as session:
            result = await session.execute(
                delete(AnalyticsSnapshot).where(
                    AnalyticsSnapshot.expires_at < datetime.now(timezone.utc)
                )
            )
            await session.flush()
            return result.rowcount or 0


database: Database | None = None


async def init_database() -> Database:
    global database
    await init_db()
    database = Database()
    return database


# ── Journal, Memory & Life OS Helpers ─────────────────────────────────────────


async def create_journal_entry(
    entry_id: str, body_md: str, title: str | None = None, tags: str | None = "[]"
) -> None:
    async with get_session() as session:
        session.add(
            JournalEntry(
                id=entry_id,
                body_md=body_md,
                title=title,
                tags=tags,
                word_count=len(body_md.split()),
                created_at=datetime.now(timezone.utc),
            )
        )
        await session.flush()


async def upsert_mood(
    entry_id: str,
    score: int,
    emotions: str,
    confidence: float | None = None,
    model: str | None = None,
) -> None:
    async with get_session() as session:
        existing = await session.get(MoodScore, entry_id)
        if existing:
            existing.score, existing.emotions, existing.confidence, existing.model = (
                score,
                emotions,
                confidence,
                model,
            )
            existing.computed_at = datetime.now(timezone.utc)
        else:
            session.add(
                MoodScore(
                    entry_id=entry_id,
                    score=score,
                    emotions=emotions,
                    confidence=confidence,
                    model=model,
                )
            )
        await session.flush()


# MemoryConflict CRUD methods (B4)
async def add_memory_conflict(
    fact_a_id: str,
    fact_b_id: str,
    conflict_type: str,
    explanation: str | None = None,
) -> str:
    """Add a new memory conflict to database."""
    async with get_session() as session:
        from uuid import uuid4

        conflict_id = str(uuid4())
        session.add(
            MemoryConflict(
                id=conflict_id,
                fact_a_id=fact_a_id,
                fact_b_id=fact_b_id,
                conflict_type=conflict_type,
                explanation=explanation,
            )
        )
        await session.flush()
        return conflict_id


async def get_memory_conflicts(
    status: str | None = None,
) -> list[dict[str, Any]]:
    """Get all memory conflicts with optional status filter."""
    async with get_session() as session:
        from sqlalchemy import select

        stmt = select(MemoryConflict).order_by(MemoryConflict.detected_at.desc())
        if status:
            stmt = stmt.where(MemoryConflict.status == status)
        result = await session.execute(stmt)
        conflicts = result.scalars().all()
        return [
            {
                "id": c.id,
                "fact_a_id": c.fact_a_id,
                "fact_b_id": c.fact_b_id,
                "conflict_type": c.conflict_type,
                "explanation": c.explanation,
                "status": c.status,
                "detected_at": c.detected_at,
            }
            for c in conflicts
        ]


async def list_journal_entries(
    limit: int = 50,
    offset: int = 0,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> list[dict]:
    async with get_session() as session:
        stmt = select(JournalEntry).order_by(JournalEntry.created_at.desc())
        if start_date:
            stmt = stmt.where(JournalEntry.created_at >= start_date)
        if end_date:
            stmt = stmt.where(JournalEntry.created_at <= end_date)
        result = await session.execute(stmt.offset(offset).limit(limit))
        rows = result.scalars().all()
        return [
            {
                "id": row.id,
                "title": row.title,
                "body_md": row.body_md,
                "word_count": row.word_count or 0,
                "tags": row.tags,
                "mood": (
                    {
                        "score": row.mood.score,
                        "emotions": row.mood.emotions,
                        "computed_at": row.mood.computed_at,
                    }
                    if hasattr(row, "mood") and row.mood
                    else None
                ),
                "created_at": row.created_at,
            }
            for row in rows
        ]


async def get_memory_records(
    limit: int = 50, layer: str | None = None, category: str | None = None
) -> list[dict]:
    async with get_session() as session:
        stmt = select(MemoryRecord).order_by(MemoryRecord.created_at.desc())
        if layer:
            stmt = stmt.where(MemoryRecord.layer == layer)
        if category:
            stmt = stmt.where(MemoryRecord.category == category)
        res = await session.execute(stmt.limit(limit))
        return [
            {
                "id": r.id,
                "layer": r.layer,
                "category": r.category,
                "content": r.content,
                "created_at": r.created_at,
            }
            for r in res.scalars().all()
        ]


async def upsert_relationship(
    name: str, aliases: str | None = "[]", relation_type: str | None = "unknown"
) -> str:
    async with get_session() as session:
        existing = (
            (
                await session.execute(
                    select(Relationship).where(Relationship.name == name)
                )
            )
            .scalars()
            .first()
        )
        if existing:
            existing.last_seen = datetime.now(timezone.utc)
            if relation_type != "unknown":
                existing.relation_type = relation_type
            return existing.id
        rid = str(uuid.uuid4())
        session.add(
            Relationship(
                id=rid, name=name, aliases=aliases, relation_type=relation_type
            )
        )
        await session.flush()
        return rid


async def add_interaction(
    relationship_id: str, entry_id: str, sentiment: float, snippet: str | None = None
) -> None:
    async with get_session() as session:
        session.add(
            Interaction(
                relationship_id=relationship_id,
                entry_id=entry_id,
                sentiment=sentiment,
                snippet=snippet,
                occurred_at=datetime.now(timezone.utc),
            )
        )
        rel = await session.get(Relationship, relationship_id)
        if rel:
            rel.interaction_count += 1
            cur_avg = rel.sentiment_avg or 0.0
            rel.sentiment_avg = (
                cur_avg * (rel.interaction_count - 1) + sentiment
            ) / rel.interaction_count
            rel.last_seen = datetime.now(timezone.utc)
        await session.flush()


async def get_mood_series(days: int = 30) -> list[dict]:
    async with get_session() as session:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        res = await session.execute(
            select(MoodScore)
            .where(MoodScore.computed_at >= cutoff)
            .order_by(MoodScore.computed_at.asc())
        )
        return [
            {"date": r.computed_at, "score": r.score, "emotions": r.emotions}
            for r in res.scalars().all()
        ]


async def create_decision(question: str) -> str:
    async with get_session() as session:
        did = str(uuid.uuid4())
        session.add(Decision(id=did, question=question, status="pending"))
        await session.flush()
        return did


async def update_decision_analysis(decision_id: str, analysis_json: str) -> None:
    async with get_session() as session:
        dec = await session.get(Decision, decision_id)
        if dec:
            dec.analysis_json, dec.status, dec.completed_at = (
                analysis_json,
                "complete",
                datetime.now(timezone.utc),
            )
        await session.flush()


async def create_insight(
    id: str, category: str, severity: float, title: str, body_md: str, **kwargs
) -> None:
    async with get_session() as session:
        session.add(
            Insight(
                id=id,
                category=category,
                severity=severity,
                title=title,
                body_md=body_md,
                **kwargs,
            )
        )
        await session.flush()


async def list_insights(unread_only: bool = False, limit: int = 50) -> list[dict]:
    async with get_session() as session:
        stmt = select(Insight).order_by(Insight.created_at.desc())
        if unread_only:
            stmt = stmt.where(Insight.read_at.is_(None))
        res = await session.execute(stmt.limit(limit))
        return [
            {
                "id": r.id,
                "category": r.category,
                "severity": r.severity,
                "title": r.title,
                "body_md": r.body_md,
                "created_at": r.created_at,
            }
            for r in res.scalars().all()
        ]


async def start_job_record(job_id: str, name: str) -> None:
    async with get_session() as session:
        session.add(
            ScheduledJob(
                id=job_id,
                name=name,
                started_at=datetime.now(timezone.utc),
                status="running",
            )
        )
        await session.flush()


async def complete_job_record(
    job_id: str, status: str, error: str | None = None
) -> None:
    async with get_session() as session:
        job = await session.get(ScheduledJob, job_id)
        if job:
            job.completed_at, job.status, job.error = (
                datetime.now(timezone.utc),
                status,
                error,
            )
        await session.flush()


# ── Stats Helpers ────────────────────────────────────────────────────────────


async def record_message(session_id: str, response_ms: int = 0) -> None:
    try:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        async with get_session() as session:
            stmt = select(ConversationStat).where(
                ConversationStat.session_id == session_id,
                ConversationStat.date == today,
            )
            row = (await session.execute(stmt)).scalars().first()
            if row is None:
                session.add(
                    ConversationStat(
                        session_id=session_id,
                        date=today,
                        message_count=1,
                        total_response_ms=max(0, response_ms),
                        response_count=1 if response_ms > 0 else 0,
                    )
                )
            else:
                row.message_count += 1
                if response_ms > 0:
                    row.total_response_ms += response_ms
                    row.response_count += 1
                row.updated_at = datetime.now(timezone.utc)
            await session.flush()
    except Exception as e:
        logger.warning("record_message failed: %s", e)


async def get_today_stats() -> dict:
    try:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        async with get_session() as session:
            res = await session.execute(
                select(
                    func.coalesce(func.sum(ConversationStat.message_count), 0),
                    func.coalesce(func.sum(ConversationStat.total_response_ms), 0),
                    func.coalesce(func.sum(ConversationStat.response_count), 0),
                ).where(ConversationStat.date == today)
            )
            msgs, ms, count = res.one()
            return {
                "today_messages": int(msgs),
                "avg_response_ms": int(ms / count) if count else None,
            }
    except Exception as e:
        return {"today_messages": 0, "avg_response_ms": None}


async def get_weekly_stats() -> list[int]:
    try:
        today = datetime.now(timezone.utc).date()
        dates = [
            (today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(6, -1, -1)
        ]
        async with get_session() as session:
            res = await session.execute(
                select(
                    ConversationStat.date,
                    func.coalesce(func.sum(ConversationStat.message_count), 0),
                )
                .where(ConversationStat.date.in_(dates))
                .group_by(ConversationStat.date)
            )
            by_date = {r[0]: int(r[1]) for r in res.all()}
        return [by_date.get(d, 0) for d in dates]
    except Exception:
        return [0] * 7
