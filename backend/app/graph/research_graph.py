"""LangGraph orchestration for the full Nexus OS research pipeline (Phases 1–6)."""
from __future__ import annotations

import logging
from typing import List, Optional, TypedDict

from langgraph.graph import END, StateGraph

logger = logging.getLogger(__name__)


# ── State schema ─────────────────────────────────────────────────────────────

class ResearchState(TypedDict):
    # Session identity
    session_id: str
    raw_query: str
    slug: str

    # Phase 1 — query expansion & planning
    optimized_queries: List[dict]
    research_title: str
    research_scope: str

    # Phase 2 — web search & scraping
    discovered_urls: List[dict]
    scraped_sources: List[dict]
    total_sources_scraped: int
    scrape_failures: List[str]
    retry_count: int

    # Phase 3 — outlining & section drafting
    outline: List[dict]        # outline["sections"] unpacked
    outline_meta: dict         # full outline dict (title, estimated_word_count, sections)
    drafted_sections: List[dict]

    # Phase 4 — synthesis
    synthesized_report: str

    # Phase 5 — fact-checking & annotation
    claims: List[dict]
    fact_checked_report: str
    verified_claim_count: int
    hallucinated_claim_count: int
    avg_confidence: float

    # Phase 6 — output export
    output_paths: dict         # {md, pdf, docx}

    # Control flow
    current_phase: str
    error: Optional[str]


# ── Phase 1 — Query optimizer ─────────────────────────────────────────────────

async def query_optimizer_node(state: ResearchState) -> dict:
    from backend.app.agents.query_architect import query_architect

    research_title = state.get("raw_query", "")
    research_scope = ""
    optimized_queries: list[dict] = []

    async for event in query_architect.run(state["raw_query"]):
        if event.get("type") == "result":
            data = event.get("data", {})
            research_title = data.get("research_title", research_title)
            research_scope = data.get("research_scope", "")
            optimized_queries = data.get("queries", [])
        elif event.get("type") == "error":
            return {
                "optimized_queries": [],
                "research_title": state["raw_query"],
                "research_scope": "",
                "current_phase": "failed",
                "error": event.get("detail", "Query optimizer failed"),
            }

    return {
        "optimized_queries": optimized_queries,
        "research_title": research_title,
        "research_scope": research_scope,
        "current_phase": "searching",
        "error": None,
    }


# ── Phase 2a — Web search ─────────────────────────────────────────────────────

async def search_executor_node(state: ResearchState) -> dict:
    from backend.app.agents.web_scout import web_scout

    discovered_urls: list[dict] = []
    async for event in web_scout.run(state.get("optimized_queries") or []):
        if event.get("type") == "result":
            discovered_urls = event.get("data", [])
        elif event.get("type") == "error":
            return {
                "discovered_urls": [],
                "current_phase": "failed",
                "error": event.get("detail", "Web search failed"),
            }

    return {
        "discovered_urls": discovered_urls,
        "current_phase": "scraping" if discovered_urls else "failed",
        "error": None if discovered_urls else "No URLs discovered from search",
    }


# ── Phase 2b — Scraper ────────────────────────────────────────────────────────

async def scraper_node(state: ResearchState) -> dict:
    from backend.app.agents.scraper_agent import scraper_agent

    scraped_sources: list[dict] = []
    scrape_failures: list[str] = []

    async for event in scraper_agent.run(
        state["slug"], state["session_id"], state.get("discovered_urls") or []
    ):
        if event.get("type") == "result":
            scraped_sources = event.get("data", [])
            scrape_failures = event.get("failures", [])

    total = len(scraped_sources)
    retry_count = (state.get("retry_count") or 0)

    if total < 3 and retry_count < 1:
        return {
            "scraped_sources": scraped_sources,
            "total_sources_scraped": total,
            "scrape_failures": scrape_failures,
            "retry_count": retry_count + 1,
            "current_phase": "retry",
        }

    return {
        "scraped_sources": scraped_sources,
        "total_sources_scraped": total,
        "scrape_failures": scrape_failures,
        "current_phase": "ingesting" if scraped_sources else "failed",
        "error": None if scraped_sources else "No sources scraped after retry",
    }


# ── Phase 2c — ChromaDB ingestion ─────────────────────────────────────────────

async def chroma_ingester_node(state: ResearchState) -> dict:
    """Index scraped source chunks into the slug-scoped ChromaDB collection.

    This makes them available for ChromaDB semantic search during fact-checking.
    The scraper already does this internally; this node is a no-op safety net.
    """
    try:
        from backend.db.vector_store import init_vector_store
        vs = await init_vector_store()
        slug = state["slug"]
        sources = state.get("scraped_sources") or []
        already_indexed = 0
        new_chunks: list[dict] = []

        for src in sources:
            chroma_count = src.get("chroma_chunk_count", 0)
            if chroma_count > 0:
                already_indexed += 1
                continue
            # Source wasn't indexed by scraper — index now
            text = src.get("clean_text") or src.get("text") or ""
            url = src.get("url", "")
            if not text:
                continue
            for i, chunk in enumerate(text[j: j + 600] for j in range(0, len(text), 500)):
                new_chunks.append({
                    "id": f"{slug}_{hash(url)}_{i}",
                    "text": chunk,
                    "metadata": {"url": url, "source_url": url, "domain": src.get("domain", ""), "slug": slug},
                })

        if new_chunks:
            await vs.upsert_chunks(f"research_{slug}", new_chunks)
            logger.info("chroma_ingester: indexed %d additional chunks for slug '%s'", len(new_chunks), slug)

    except Exception as exc:
        logger.warning("chroma_ingester_node error (non-fatal): %s", exc)

    return {"current_phase": "outlining"}


# ── Phase 3a — Outline generator ─────────────────────────────────────────────

async def outline_generator_node(state: ResearchState) -> dict:
    from backend.app.agents.outline_architect import outline_architect

    query_strings = [q.get("query", "") for q in (state.get("optimized_queries") or [])]
    outline_data: dict = {}

    async for event in outline_architect.run(
        state.get("research_title", state["raw_query"]),
        state.get("research_scope", ""),
        state.get("scraped_sources") or [],
        query_strings,
    ):
        if event.get("type") == "result":
            outline_data = event.get("data", {})
        elif event.get("type") == "error":
            return {"current_phase": "failed", "error": event.get("detail", "Outline generation failed")}

    sections = outline_data.get("sections", [])
    if not sections:
        return {"current_phase": "failed", "error": "Outline produced no sections"}

    return {
        "outline": sections,
        "outline_meta": outline_data,
        "research_title": outline_data.get("report_title", state.get("research_title", "")),
        "current_phase": "drafting",
        "error": None,
    }


# ── Phase 3b — Section drafter ───────────────────────────────────────────────

async def section_drafter_node(state: ResearchState) -> dict:
    from backend.app.agents.section_drafter import section_drafter

    drafted: list[dict] = []
    async for event in section_drafter.draft_all_sections(
        state.get("research_title", state["raw_query"]),
        state.get("outline") or [],
        state.get("scraped_sources") or [],
    ):
        if event.get("type") == "result":
            drafted = event.get("data", [])
        elif event.get("type") == "error":
            logger.warning("section_drafter_node error event: %s", event.get("detail"))

    if not drafted:
        return {"current_phase": "failed", "error": "Section drafting produced no content"}

    return {
        "drafted_sections": drafted,
        "current_phase": "synthesizing",
        "error": None,
    }


def should_continue_drafting(state: ResearchState) -> str:
    drafted = len(state.get("drafted_sections") or [])
    total = len(state.get("outline") or [])
    return "section_drafter" if drafted < total else "synthesizer"


# ── Phase 4 — Synthesizer ─────────────────────────────────────────────────────

async def synthesizer_node(state: ResearchState) -> dict:
    from backend.app.agents.synthesis_director import synthesis_director

    report_text = ""
    async for event in synthesis_director.run(
        state.get("research_title", state["raw_query"]),
        state["raw_query"],
        state.get("drafted_sections") or [],
        state.get("scraped_sources") or [],
    ):
        if event.get("type") == "result":
            report_text = event.get("data", {}).get("report_text", "")
        elif event.get("type") == "chunk":
            report_text += event.get("content", "")

    if not report_text:
        return {"current_phase": "failed", "error": "Synthesis produced no output"}

    return {
        "synthesized_report": report_text,
        "current_phase": "claim_extracting",
        "error": None,
    }


# ── Phase 5a — Claim extractor ────────────────────────────────────────────────

async def claim_extractor_node(state: ResearchState) -> dict:
    from backend.app.agents.fact_checker import _extract_claims_from_report

    claims_raw = await _extract_claims_from_report(
        state.get("synthesized_report", ""),
        state["raw_query"],
    )
    return {
        "claims": claims_raw,
        "current_phase": "claim_verifying",
    }


# ── Phase 5b — Claim verifier ─────────────────────────────────────────────────

async def claim_verifier_node(state: ResearchState) -> dict:
    from backend.app.agents.fact_checker import _verify_claim

    claims_raw = state.get("claims") or []
    verified: list[dict] = []
    for claim in claims_raw:
        result = await _verify_claim(claim, state.get("scraped_sources") or [], state["slug"])
        verified.append(result)

    v_count = sum(1 for c in verified if c.get("verification_status") == "verified")
    h_count = sum(1 for c in verified if c.get("verification_status") == "hallucinated")
    avg_conf = round(
        sum(c.get("confidence_score", 0.0) for c in verified) / len(verified) if verified else 0.0, 3
    )

    return {
        "claims": verified,
        "verified_claim_count": v_count,
        "hallucinated_claim_count": h_count,
        "avg_confidence": avg_conf,
        "current_phase": "annotating",
    }


# ── Phase 5c — Report annotator ───────────────────────────────────────────────

async def report_annotator_node(state: ResearchState) -> dict:
    from backend.app.agents.fact_checker import annotate_report_with_verdicts
    from backend.app.agents.report_builder import report_builder_agent

    synthesized = state.get("synthesized_report", "")
    claims = state.get("claims") or []
    annotated = annotate_report_with_verdicts(synthesized, claims) if claims else synthesized

    # Persist
    extra = {
        "report_title": state.get("research_title", ""),
        "section_count": len(state.get("drafted_sections") or []),
        "verified_claims": state.get("verified_claim_count", 0),
        "hallucinated_claims": state.get("hallucinated_claim_count", 0),
        "avg_confidence": state.get("avg_confidence", 0.0),
    }
    async for _ in report_builder_agent.save_and_index(
        state["slug"],
        state["raw_query"],
        annotated,
        state.get("scraped_sources") or [],
        extra_metadata=extra,
    ):
        pass  # Graph node — fire and forget save; errors logged inside

    return {
        "fact_checked_report": annotated,
        "current_phase": "exporting",
        "error": None,
    }


# ── Phase 6 — Output exporter ─────────────────────────────────────────────────

async def output_exporter_node(state: ResearchState) -> dict:
    from backend.app.agents.output_exporter import output_exporter

    output_paths: dict = {}
    async for event in output_exporter.run(
        state["slug"],
        title=state.get("research_title", "Research Report"),
    ):
        if event.get("type") == "result":
            output_paths = event.get("output_paths", {})

    return {
        "output_paths": output_paths,
        "current_phase": "done",
    }


# ── Conditional edge helpers ──────────────────────────────────────────────────

def _route_after_planning(state: ResearchState) -> str:
    return "failed" if state.get("current_phase") == "failed" else "proceed"


def _route_after_search(state: ResearchState) -> str:
    return "proceed" if state.get("discovered_urls") else "failed"


def _route_after_scraping(state: ResearchState) -> str:
    sources = state.get("scraped_sources") or []
    if sources:
        return "proceed"
    if (state.get("retry_count") or 0) < 1:
        return "retry"
    return "failed"


def should_proceed_to_scraper(state: dict) -> str:
    urls = state.get("discovered_urls") or state.get("urls") or []
    return "proceed" if urls else "failed"


def should_proceed_to_fact_checker(state: dict) -> str:
    sources = state.get("scraped_sources") or state.get("sources") or []
    retry_count = state.get("retry_count") or 0
    if len(sources) >= 3:
        return "proceed"
    if len(sources) == 0 and retry_count >= 1:
        return "failed"
    if retry_count < 1:
        return "retry"
    return "proceed"


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_research_graph() -> StateGraph:
    graph = StateGraph(ResearchState)

    # Nodes
    graph.add_node("query_optimizer", query_optimizer_node)
    graph.add_node("search_executor", search_executor_node)
    graph.add_node("scraper", scraper_node)
    graph.add_node("chroma_ingester", chroma_ingester_node)
    graph.add_node("outline_generator", outline_generator_node)
    graph.add_node("section_drafter", section_drafter_node)
    graph.add_node("synthesizer", synthesizer_node)
    graph.add_node("claim_extractor", claim_extractor_node)
    graph.add_node("claim_verifier", claim_verifier_node)
    graph.add_node("report_annotator", report_annotator_node)
    graph.add_node("output_exporter", output_exporter_node)

    # Entry
    graph.set_entry_point("query_optimizer")

    # Edges
    graph.add_conditional_edges(
        "query_optimizer",
        _route_after_planning,
        {"proceed": "search_executor", "failed": END},
    )
    graph.add_conditional_edges(
        "search_executor",
        _route_after_search,
        {"proceed": "scraper", "failed": END},
    )
    graph.add_conditional_edges(
        "scraper",
        _route_after_scraping,
        {"proceed": "chroma_ingester", "retry": "search_executor", "failed": END},
    )
    graph.add_edge("chroma_ingester", "outline_generator")
    graph.add_conditional_edges(
        "outline_generator",
        lambda s: "failed" if s.get("current_phase") == "failed" else "proceed",
        {"proceed": "section_drafter", "failed": END},
    )
    # Section drafter either loops or proceeds (currently always proceeds since draft_all_sections handles all)
    graph.add_conditional_edges(
        "section_drafter",
        should_continue_drafting,
        {"section_drafter": "section_drafter", "synthesizer": "synthesizer"},
    )
    graph.add_conditional_edges(
        "synthesizer",
        lambda s: "failed" if s.get("current_phase") == "failed" else "proceed",
        {"proceed": "claim_extractor", "failed": END},
    )
    graph.add_edge("claim_extractor", "claim_verifier")
    graph.add_edge("claim_verifier", "report_annotator")
    graph.add_edge("report_annotator", "output_exporter")
    graph.add_edge("output_exporter", END)

    # Compile with optional SQLite checkpointing for resume-on-failure
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
        checkpointer = SqliteSaver.from_conn_string(str(
            __import__("pathlib").Path("data/checkpoints.db")
        ))
        return graph.compile(checkpointer=checkpointer)
    except Exception:
        return graph.compile()


research_graph = build_research_graph()
