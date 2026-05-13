"""Phase 3/4 persistence layer — saves synthesized report to disk and indexes in ChromaDB.

Drafting is handled by outline_architect → section_drafter → synthesis_director.
This module only handles save + index after synthesis is complete.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator

from slugify import slugify

from backend.config import settings
from backend.core.resilience import EmbeddingUnavailable, degraded_event
from backend.db.vector_store import init_vector_store

logger = logging.getLogger(__name__)


class ReportBuilderAgent:
    def generate_slug(self, topic: str) -> str:
        return slugify(topic, max_length=60, separator="-")

    def _chunk_text(self, text: str) -> list[str]:
        size = settings.RESEARCH_CHUNK_SIZE
        overlap = settings.RESEARCH_CHUNK_OVERLAP
        chunks: list[str] = []
        start = 0
        while start < len(text):
            chunks.append(text[start : start + size])
            start += size - overlap
        return chunks

    def save_to_disk(self, slug: str, report_md: str, metadata: dict) -> Path:
        report_dir = settings.DEEP_RESEARCH_DIR / slug
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / "report.md"
        report_path.write_text(report_md, encoding="utf-8")
        (report_dir / "metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return report_path

    async def index_in_chroma(self, slug: str, report_md: str, metadata: dict) -> None:
        try:
            vs = await init_vector_store()
            chunks = self._chunk_text(report_md)
            chunk_dicts = [
                {
                    "id": f"research_{slug}_{i}",
                    "text": chunk,
                    "metadata": {
                        "type": "research_report",
                        "slug": slug,
                        "topic": metadata.get("topic", ""),
                        "created_at": metadata.get("created_at", ""),
                        "source_count": metadata.get("source_count", 0),
                        "avg_confidence": metadata.get("avg_confidence", 0.0),
                        "chunk_index": i,
                    },
                }
                for i, chunk in enumerate(chunks)
            ]
            await vs.upsert_chunks("research", chunk_dicts)
            logger.info("Indexed %d chunks for '%s'", len(chunks), slug)
        except EmbeddingUnavailable as exc:
            logger.warning(
                "Report indexing degraded",
                extra={"slug": slug, "error": str(exc)},
            )
            raise

    async def save_and_index(
        self,
        slug: str,
        topic: str,
        report_md: str,
        sources: list[dict],
        extra_metadata: dict | None = None,
    ) -> AsyncGenerator[dict, None]:
        """Persist a completed report markdown to disk and index it in ChromaDB."""
        metadata = {
            "slug": slug,
            "topic": topic,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_count": len(sources),
            "status": "complete",
            "chroma_collection": "nexus_research",
            "word_count": len(report_md.split()),
            "tags": [w for w in topic.lower().split() if len(w) > 3][:5],
        }
        if extra_metadata:
            metadata.update(extra_metadata)

        yield {
            "type": "progress", "agent": "Scribe", "stage": "saving",
            "detail": "Saving report to disk...",
        }
        try:
            report_path = self.save_to_disk(slug, report_md, metadata)
        except OSError as exc:
            logger.warning("Report disk write failed", extra={"slug": slug, "error": str(exc)})
            yield degraded_event("Scribe", "disk_write_failed", "Could not save report to disk.")
            yield {"type": "error", "agent": "Scribe", "detail": f"Save failed: {exc}"}
            return
        except Exception as exc:
            logger.error("Failed to save report: %s", exc)
            yield {"type": "error", "agent": "Scribe", "detail": f"Save failed: {exc}"}
            return

        yield {
            "type": "progress", "agent": "Scribe", "stage": "indexing",
            "detail": "Indexing in knowledge base...",
        }
        try:
            await self.index_in_chroma(slug, report_md, metadata)
        except EmbeddingUnavailable as exc:
            yield degraded_event(
                "Scribe",
                "embedding_unavailable",
                f"Report saved, but indexing in ChromaDB failed: {exc}",
            )

        yield {
            "type": "result", "agent": "Scribe",
            "slug": slug,
            "path": str(report_path),
            "metadata": metadata,
        }


report_builder_agent = ReportBuilderAgent()
