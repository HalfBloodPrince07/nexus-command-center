"""Typed MCP tool wrappers for the Nexus OS agent toolbelt."""
from __future__ import annotations

import asyncio
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import BaseModel, Field
from slugify import slugify

from backend.config import settings


class SearchLocalFilesInput(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


class FileSearchResult(BaseModel):
    id: str = ""
    text: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    score: float | None = None
    source: str | None = None


class SearchLocalFilesOutput(BaseModel):
    query: str
    results: list[FileSearchResult]


class SearchWebInput(BaseModel):
    query: str = Field(..., min_length=1)
    max_results: int = Field(default=10, ge=1, le=50)


class WebSearchResult(BaseModel):
    url: str
    title: str = ""
    snippet: str = ""
    domain: str = ""
    authority_score: float | None = None
    relevance_score: float | None = None
    composite_score: float | None = None


class SearchWebOutput(BaseModel):
    query: str
    results: list[WebSearchResult]


class SaveMemoryInput(BaseModel):
    fact: str = Field(..., min_length=1)
    category: str = Field(..., min_length=1)
    importance: int = Field(..., ge=1, le=10)


class SaveMemoryOutput(BaseModel):
    memory_id: str
    category: str
    importance: float
    saved: bool = True


class JournalInsightsInput(BaseModel):
    date_range: str = "7d"
    topic: str | None = None


class JournalEntrySummary(BaseModel):
    id: str
    title: str | None = None
    created_at: str
    excerpt: str


class JournalInsightsOutput(BaseModel):
    date_range: str
    topic: str | None = None
    entry_count: int
    entries: list[JournalEntrySummary]
    mood: dict[str, Any] | None = None
    insights: list[dict[str, Any]] = Field(default_factory=list)


class SaveResearchReportInput(BaseModel):
    title: str = Field(..., min_length=1)
    query: str = Field(..., min_length=1)


class SaveResearchReportOutput(BaseModel):
    session_id: str
    slug: str
    title: str
    status: str
    message: str


class AnalyzeImageInput(BaseModel):
    image_path: str = Field(..., min_length=1)
    question: str = Field(..., min_length=1)


class AnalyzeImageOutput(BaseModel):
    image_path: str
    question: str
    answer: str


def _timeout_seconds() -> float:
    return float(settings.SUPERVISOR_TIMEOUT_SECONDS)


async def _bounded(coro, timeout: float | None = None):
    return await asyncio.wait_for(coro, timeout=timeout or _timeout_seconds())


def _parse_date_range(value: str) -> tuple[datetime | None, int | None]:
    match = re.fullmatch(r"\s*(\d+)\s*([dDwWmMyY])\s*", value or "")
    if not match:
        return None, None
    amount = int(match.group(1))
    unit = match.group(2).lower()
    days = amount
    if unit == "w":
        days = amount * 7
    elif unit == "m":
        days = amount * 30
    elif unit == "y":
        days = amount * 365
    return datetime.now(timezone.utc) - timedelta(days=days), days


async def search_local_files(query: str, top_k: int = 5) -> SearchLocalFilesOutput:
    """Search indexed local Nexus OS files using the existing hybrid RAG retriever."""
    data = SearchLocalFilesInput(query=query, top_k=top_k)

    async def _search() -> list[dict[str, Any]]:
        from backend.app.agents.rag_retriever import rag_retriever

        vector_hits, bm25_hits = await asyncio.gather(
            rag_retriever._vector_search(data.query, "files", n=data.top_k * 2),
            asyncio.to_thread(rag_retriever._bm25_search, data.query, "files", data.top_k * 2),
        )
        return rag_retriever._rrf_merge(vector_hits, bm25_hits)[: data.top_k]

    results = await _bounded(_search())
    return SearchLocalFilesOutput(
        query=data.query,
        results=[FileSearchResult.model_validate(item) for item in results],
    )


async def search_web(query: str, max_results: int = 10) -> SearchWebOutput:
    """Search the web through the existing Web Scout agent and return ranked URLs."""
    data = SearchWebInput(query=query, max_results=max_results)

    async def _search() -> list[dict[str, Any]]:
        from backend.app.agents.web_scout import web_scout

        query_obj = {
            "id": "mcp-search",
            "query": data.query,
            "expected_source_type": "web",
        }
        async for event in web_scout.run([query_obj]):
            if event.get("type") == "result":
                return event.get("data", [])[: data.max_results]
        return []

    results = await _bounded(_search())
    return SearchWebOutput(
        query=data.query,
        results=[WebSearchResult.model_validate(item) for item in results],
    )


async def save_memory(fact: str, category: str, importance: int) -> SaveMemoryOutput:
    """Save a user fact through the existing Memory Archivist agent."""
    data = SaveMemoryInput(fact=fact, category=category, importance=importance)

    async def _save() -> str:
        from backend.app.agents.memory.memory_archivist import MemoryArchivistAgent

        agent = MemoryArchivistAgent()
        return await agent.store(
            content=data.fact,
            category=data.category,
            importance=data.importance / 10.0,
            source_ref="mcp",
            confidence=0.8,
        )

    memory_id = await _bounded(_save())
    return SaveMemoryOutput(
        memory_id=memory_id,
        category=data.category,
        importance=data.importance / 10.0,
    )


async def get_journal_insights(
    date_range: str = "7d",
    topic: str | None = None,
) -> JournalInsightsOutput:
    """Aggregate recent journal entries, mood trend data, and insight cards."""
    data = JournalInsightsInput(date_range=date_range, topic=topic)
    start_date, days = _parse_date_range(data.date_range)

    async def _collect() -> JournalInsightsOutput:
        from backend.app.agents.journal.mood_analyst import MoodAnalystAgent
        from backend.app.agents.journal.psychology_agent import PsychologyAgent
        from backend.core import database as db

        entries = await db.list_journal_entries(limit=200, start_date=start_date)
        if data.topic:
            needle = data.topic.lower()
            entries = [
                entry for entry in entries
                if needle in (entry.get("body_md") or "").lower()
                or needle in (entry.get("title") or "").lower()
            ]

        mood = None
        insights: list[dict[str, Any]] = []
        if days:
            mood = await MoodAnalystAgent().trend(window_days=max(days, 1))
            insights = await PsychologyAgent().insight_cards(days=max(days, 1))

        summaries = [
            JournalEntrySummary(
                id=str(entry["id"]),
                title=entry.get("title"),
                created_at=str(entry.get("created_at")),
                excerpt=(entry.get("body_md") or "")[:500],
            )
            for entry in entries
        ]
        return JournalInsightsOutput(
            date_range=data.date_range,
            topic=data.topic,
            entry_count=len(summaries),
            entries=summaries,
            mood=mood,
            insights=insights,
        )

    return await _bounded(_collect())


async def save_research_report(title: str, query: str) -> SaveResearchReportOutput:
    """Create a research session and start the existing research graph in the background."""
    data = SaveResearchReportInput(title=title, query=query)

    async def _start() -> SaveResearchReportOutput:
        from backend.app.graph.research_graph import research_graph
        from backend.core import database as db

        session_id = str(uuid.uuid4())
        slug = slugify(data.title or data.query, max_length=60, separator="-")
        await db.create_research_session(session_id, data.title, data.query, slug)

        initial_state = {
            "session_id": session_id,
            "raw_query": data.query,
            "slug": slug,
            "research_title": data.title,
            "retry_count": 0,
            "current_phase": "queued",
            "error": None,
        }

        async def _run_graph() -> None:
            try:
                await db.update_research_session(session_id, status="running", phase="graph")
                await research_graph.ainvoke(
                    initial_state,
                    config={"configurable": {"thread_id": session_id}},
                )
                await db.update_research_session(session_id, status="done", phase="done")
            except Exception as exc:  # noqa: BLE001
                await db.update_research_session(
                    session_id,
                    status="failed",
                    phase="failed",
                    error_log=str(exc),
                )

        asyncio.create_task(_run_graph())
        return SaveResearchReportOutput(
            session_id=session_id,
            slug=slug,
            title=data.title,
            status="queued",
            message="Research graph started in the background.",
        )

    return await _bounded(_start())


async def analyze_image(image_path: str, question: str) -> AnalyzeImageOutput:
    """Analyze an image with the existing Nexus OS vision agent."""
    data = AnalyzeImageInput(image_path=image_path, question=question)

    async def _analyze() -> str:
        from backend.app.agents.vision_agent import vision_agent

        tokens: list[str] = []
        async for token in vision_agent.analyze_image(
            image_path=data.image_path,
            question=data.question,
            session_id="mcp",
        ):
            tokens.append(token)
        return "".join(tokens)

    answer = await _bounded(_analyze())
    return AnalyzeImageOutput(
        image_path=data.image_path,
        question=data.question,
        answer=answer,
    )


REGISTERED_TOOLS = [
    search_local_files,
    search_web,
    save_memory,
    get_journal_insights,
    save_research_report,
    analyze_image,
]

TOOL_FUNCTIONS = {tool.__name__: tool for tool in REGISTERED_TOOLS}
