"""Atlas — Research Lead: orchestrates the full research pipeline via WebSocket streaming."""

from __future__ import annotations

import logging
import re
from typing import AsyncGenerator

from slugify import slugify

from backend.app.agents.fact_checker import fact_checker_agent
from backend.config import settings
from backend.app.agents.outline_architect import outline_architect
from backend.app.agents.output_exporter import output_exporter
from backend.app.agents.query_architect import query_architect
from backend.app.agents.report_builder import report_builder_agent
from backend.app.agents.scraper_agent import scraper_agent
from backend.app.agents.section_drafter import section_drafter
from backend.app.agents.synthesis_director import synthesis_director
from backend.app.agents.web_scout import web_scout
from backend.core import database as db_module
from backend.core.event_bus import event_bus

logger = logging.getLogger(__name__)

_RESEARCH_PATTERNS = [
    r"\b(research|investigate|deep.dive.into|look.into|study|analyze)\b",
    r"\bfind out (everything|all|more) about\b",
    r"\bdo an? research on\b",
    r"\bresearch (topic|question|query|about)\b",
]


class ResearchLead:
    async def get_research_intent(self, message: str) -> bool:
        lowered = message.lower()
        return any(re.search(p, lowered) for p in _RESEARCH_PATTERNS)

    async def run_research(
        self,
        topic: str,
        job_id: str,
        session_id: str,
    ) -> AsyncGenerator[dict, None]:
        slug = slugify(topic, max_length=60, separator="-")

        try:
            await db_module.update_research_session(
                job_id, status="running", phase="init"
            )
        except Exception as exc:
            logger.warning("DB session tracking error: %s", exc)

        yield {
            "type": "thinking",
            "agent": "Atlas",
            "detail": "Planning research pipeline...",
        }

        # ── PHASE 1: Query Expansion ──────────────────────────────────────────
        await db_module.update_research_session(job_id, phase="query_expansion")
        optimized_queries: list[dict] = []
        research_title = topic
        research_scope = ""

        async for event in query_architect.run(topic):
            yield event
            if event.get("type") == "result" and event.get("agent") == "QueryArchitect":
                data = event.get("data", {})
                optimized_queries = data.get("queries", [])
                research_title = data.get("research_title", topic)
                research_scope = data.get("research_scope", "")

        if not optimized_queries:
            msg = "Query expansion produced no queries."
            yield {"type": "error", "agent": "Atlas", "detail": msg}
            await _safe_update_session(job_id, "failed", msg)
            return

        # Update session title now that we have a proper one
        try:
            await db_module.update_research_session(job_id, phase="web_search")
            # Persist queries to DB
            import uuid

            for q in optimized_queries:
                try:
                    await db_module.insert_research_query(
                        query_id=str(uuid.uuid4()),
                        session_id=job_id,
                        query_text=q.get("query", ""),
                        query_type=q.get("type"),
                        search_engine=q.get("target_engine"),
                    )
                except Exception:
                    pass
        except Exception as exc:
            logger.warning("DB phase update error: %s", exc)

        # ── PHASE 2a: Web Search ──────────────────────────────────────────────
        await event_bus.publish_agent_message(
            from_agent="Atlas",
            to_agent="Vector",
            message_type="task_assignment",
            payload={"session_id": session_id, "topic": topic, "phase": "web_search"},
        )
        yield {"type": "agent_switch", "from": "Atlas", "to": "Vector", "content": ""}
        discovered_urls: list[dict] = []

        async for event in web_scout.run(optimized_queries):
            yield event
            if event.get("type") == "result" and event.get("agent") == "Vector":
                discovered_urls = event.get("data", [])

        if not discovered_urls:
            msg = "No web sources discovered. Try rephrasing your query."
            yield {"type": "error", "agent": "Atlas", "detail": msg}
            await _safe_update_session(job_id, "failed", msg)
            return

        # ── PHASE 2b: Scraping ────────────────────────────────────────────────
        await event_bus.publish_agent_message(
            from_agent="Vector",
            to_agent="Fetch",
            message_type="task_assignment",
            payload={
                "session_id": session_id,
                "discovered_url_count": len(discovered_urls),
                "phase": "scraping",
            },
        )
        yield {"type": "agent_switch", "from": "Vector", "to": "Fetch", "content": ""}
        await db_module.update_research_session(job_id, phase="scraping")
        scraped_sources: list[dict] = []

        async for event in scraper_agent.run(slug, job_id, discovered_urls):
            yield event
            if event.get("type") == "result" and event.get("agent") == "Fetch":
                scraped_sources = event.get("data", [])

        # Retry with broader fallback queries if too few sources
        if len(scraped_sources) < 3:
            broader_queries = [
                {
                    "query": f"{topic} overview explained",
                    "type": "semantic",
                    "target_engine": "duckduckgo",
                    "expected_source_type": "news",
                },
                {
                    "query": f"{topic} introduction guide",
                    "type": "semantic",
                    "target_engine": "duckduckgo",
                    "expected_source_type": "technical_doc",
                },
            ]
            yield {
                "type": "progress",
                "agent": "Atlas",
                "stage": "retry",
                "detail": f"Only {len(scraped_sources)} source(s) — retrying with broader queries...",
            }
            extra_urls: list[dict] = []
            async for event in web_scout.run(broader_queries):
                yield event
                if event.get("type") == "result":
                    extra_urls = event.get("data", [])

            existing_urls = {u["url"] for u in discovered_urls}
            new_urls = [u for u in extra_urls if u["url"] not in existing_urls]
            if new_urls:
                async for event in scraper_agent.run(slug, job_id, new_urls):
                    yield event
                    if event.get("type") == "result":
                        seen = {s["url"] for s in scraped_sources}
                        scraped_sources.extend(
                            s for s in event.get("data", []) if s["url"] not in seen
                        )

        if not scraped_sources:
            msg = (
                "Could not scrape any content. Sources may be paywalled or unavailable."
            )
            yield {"type": "error", "agent": "Atlas", "detail": msg}
            await _safe_update_session(job_id, "failed", msg)
            return

        # ── PHASE 3a: Outline Generation ─────────────────────────────────────
        await event_bus.publish_agent_message(
            from_agent="Fetch",
            to_agent="OutlineArchitect",
            message_type="task_assignment",
            payload={
                "session_id": session_id,
                "scraped_source_count": len(scraped_sources),
                "phase": "outlining",
            },
        )
        yield {
            "type": "agent_switch",
            "from": "Fetch",
            "to": "OutlineArchitect",
            "content": "",
        }
        await db_module.update_research_session(job_id, phase="outlining")
        outline: dict = {}
        query_strings = [q.get("query", "") for q in optimized_queries]

        async for event in outline_architect.run(
            research_title, research_scope, scraped_sources, query_strings
        ):
            yield event
            if (
                event.get("type") == "result"
                and event.get("agent") == "OutlineArchitect"
            ):
                outline = event.get("data", {})

        sections_plan = outline.get("sections", [])
        report_title_final = outline.get("report_title", research_title)
        if not sections_plan:
            msg = "Outline generation produced no sections."
            yield {"type": "error", "agent": "Atlas", "detail": msg}
            await _safe_update_session(job_id, "failed", msg)
            return

        # ── PHASE 3b: Section Drafting ────────────────────────────────────────
        yield {
            "type": "agent_switch",
            "from": "OutlineArchitect",
            "to": "SectionDrafter",
            "content": "",
        }
        await db_module.update_research_session(job_id, phase="drafting")
        drafted_sections: list[dict] = []

        async for event in section_drafter.draft_all_sections(
            report_title_final, sections_plan, scraped_sources
        ):
            yield event
            if event.get("type") == "result" and event.get("agent") == "SectionDrafter":
                drafted_sections = event.get("data", [])

        if not drafted_sections:
            msg = "Section drafting produced no content."
            yield {"type": "error", "agent": "Atlas", "detail": msg}
            await _safe_update_session(job_id, "failed", msg)
            return

        # ── PHASE 4: Synthesis ────────────────────────────────────────────────
        await event_bus.publish_agent_message(
            from_agent="SectionDrafter",
            to_agent="SynthesisDirector",
            message_type="task_assignment",
            payload={
                "session_id": session_id,
                "drafted_section_count": len(drafted_sections),
                "phase": "synthesis",
            },
        )
        yield {
            "type": "agent_switch",
            "from": "SectionDrafter",
            "to": "SynthesisDirector",
            "content": "",
        }
        await db_module.update_research_session(job_id, phase="synthesis")
        final_report_text = ""
        synthesis_meta: dict = {}

        async for event in synthesis_director.run(
            report_title_final, topic, drafted_sections, scraped_sources
        ):
            yield event
            if (
                event.get("type") == "result"
                and event.get("agent") == "SynthesisDirector"
            ):
                synthesis_meta = event.get("data", {})
                final_report_text = synthesis_meta.get("report_text", "")

        if not final_report_text:
            msg = "Synthesis produced no output."
            yield {"type": "error", "agent": "Atlas", "detail": msg}
            await _safe_update_session(job_id, "failed", msg)
            return

        # ── PHASE 5: Fact Checking ────────────────────────────────────────────
        await event_bus.publish_agent_message(
            from_agent="SynthesisDirector",
            to_agent="Verity",
            message_type="task_assignment",
            payload={
                "session_id": session_id,
                "report_length": len(final_report_text),
                "phase": "fact_checking",
            },
        )
        yield {
            "type": "agent_switch",
            "from": "SynthesisDirector",
            "to": "Verity",
            "content": "",
        }
        await db_module.update_research_session(job_id, phase="fact_checking")
        annotated_report = final_report_text  # fallback if fact-check fails
        fc_meta: dict = {}

        async for event in fact_checker_agent.run(
            slug, scraped_sources, topic, final_report_text
        ):
            yield event
            if event.get("type") == "result" and event.get("agent") == "Verity":
                fc_meta = event
                annotated_report = event.get("annotated_report") or final_report_text

        # ── PHASE 6: Save + Index ─────────────────────────────────────────────
        await event_bus.publish_agent_message(
            from_agent="Verity",
            to_agent="Scribe",
            message_type="task_assignment",
            payload={
                "session_id": session_id,
                "verified_claims": fc_meta.get("verified_count", 0),
                "phase": "saving",
            },
        )
        yield {"type": "agent_switch", "from": "Verity", "to": "Scribe", "content": ""}
        await db_module.update_research_session(job_id, phase="saving")
        metadata: dict = {}
        report_slug = slug

        async for event in report_builder_agent.save_and_index(
            slug,
            topic,
            annotated_report,
            scraped_sources,
            extra_metadata={
                "report_title": report_title_final,
                "section_count": len(drafted_sections),
                "needs_verification_count": synthesis_meta.get(
                    "needs_verification_count", 0
                ),
                "outline_word_count_estimate": outline.get("estimated_word_count", 0),
                "verified_claims": fc_meta.get("verified_count", 0),
                "hallucinated_claims": fc_meta.get("hallucinated_count", 0),
                "avg_confidence": fc_meta.get("avg_confidence", 0.0),
            },
        ):
            yield event
            if event.get("type") == "result" and event.get("agent") == "Scribe":
                metadata = event.get("metadata", {})
                report_slug = event.get("slug", slug)

        # ── PHASE 6b: Export to PDF / DOCX ───────────────────────────────────
        await event_bus.publish_agent_message(
            from_agent="Scribe",
            to_agent="Exporter",
            message_type="task_assignment",
            payload={"session_id": session_id, "slug": slug, "phase": "exporting"},
        )
        yield {
            "type": "agent_switch",
            "from": "Scribe",
            "to": "Exporter",
            "content": "",
        }
        await db_module.update_research_session(job_id, phase="exporting")
        output_paths: dict = {
            "md": str(settings.DEEP_RESEARCH_DIR / slug / "report.md")
        }

        async for event in output_exporter.run(slug, title=report_title_final):
            yield event
            if event.get("type") == "result" and event.get("agent") == "Exporter":
                output_paths = event.get("output_paths", output_paths)

        # ── Done ──────────────────────────────────────────────────────────────
        await _safe_update_session(job_id, "done")
        yield {
            "type": "done",
            "agent": "Atlas",
            "detail": "Research complete. Report saved.",
            "slug": report_slug,
            "metadata": metadata,
            "research_title": report_title_final,
            "research_scope": research_scope,
            "source_count": len(scraped_sources),
            "section_count": len(drafted_sections),
            "output_paths": output_paths,
        }


async def _safe_update_session(
    session_id: str, status: str, error_log: str | None = None
) -> None:
    try:
        await db_module.update_research_session(
            session_id, status=status, error_log=error_log
        )
    except Exception as exc:
        logger.warning("Failed to update session %s → %s: %s", session_id, status, exc)


research_lead = ResearchLead()
