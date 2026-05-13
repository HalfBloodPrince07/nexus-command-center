"""File processor agent — parent-child chunking, summarization, and GraphRAG ingestion."""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from pathlib import Path
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    class RecursiveCharacterTextSplitter:  # type: ignore[override]
        def __init__(self, chunk_size: int, chunk_overlap: int, separators: list[str] | None = None):
            self.chunk_size = max(chunk_size, 1)
            self.chunk_overlap = max(min(chunk_overlap, self.chunk_size - 1), 0)

        def split_text(self, text: str) -> list[str]:
            if not text:
                return []
            chunks: list[str] = []
            start = 0
            while start < len(text):
                end = min(start + self.chunk_size, len(text))
                chunk = text[start:end].strip()
                if chunk:
                    chunks.append(chunk)
                if end >= len(text):
                    break
                start = max(end - self.chunk_overlap, start + 1)
            return chunks

from backend.config import settings
from backend.core import database as db_module


class FileProcessor:
    SUPPORTED_MIME_TYPES = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/markdown",
        "text/plain",
        "image/png",
        "image/jpeg",
        "image/webp",
    }

    # ------------------------------------------------------------------ #
    # Public entry point                                                   #
    # ------------------------------------------------------------------ #

    async def process_file(
        self,
        file_id: str,
        file_path: str,
        original_name: str,
        mime_type: str,
        collection: str = "files",
    ) -> AsyncGenerator[dict, None]:
        if mime_type not in self.SUPPORTED_MIME_TYPES:
            err = f"Unsupported MIME type: {mime_type}"
            if db_module.database:
                await db_module.database.update_file_status(file_id, "error", error_message=err)
            yield {"stage": "error", "chunk_count": 0, "message": err}
            return

        try:
            # ── 1. Content-hash deduplication ──────────────────────────
            yield {"stage": "parsing", "chunk_count": 0, "message": f"Parsing {original_name}"}

            file_hash = await asyncio.to_thread(self._sha256_file, file_path)
            if db_module.database:
                existing = await db_module.database.get_file_by_hash(file_hash, collection)
                if existing and existing["id"] != file_id:
                    chunk_count = existing.get("chunk_count", 0)
                    await db_module.database.update_file_status(
                        file_id, "ready", chunk_count=chunk_count
                    )
                    await db_module.database.store_content_hash(
                        file_hash, file_id, original_name, collection
                    )
                    yield {
                        "stage": "done",
                        "chunk_count": chunk_count,
                        "message": f"Duplicate of '{existing['original_name']}' — skipped re-embedding.",
                    }
                    return

            # ── 2. Parse into (page_num, text) pairs ───────────────────
            pages: list[tuple[int, str]] = []
            if not mime_type.startswith("image/"):
                pages = await self._parse_document(file_path, mime_type)

            full_text = "\n\n".join(text for _, text in pages)

            # ── 2b. Summarize document via local LLM ───────────────────
            yield {"stage": "chunking", "chunk_count": 0, "message": "Summarizing document"}
            summary = ""
            if full_text.strip() and settings.SUMMARIZATION_ENABLED:
                summary = await self._summarize_document(full_text, original_name)

            # ── 2c. Extract entities for knowledge graph ───────────────
            graph_data: dict = {"entities": [], "relationships": []}
            if summary:
                graph_data = await self._extract_entities(summary, original_name)

            # ── 3. Parent-child chunking ────────────────────────────────
            yield {"stage": "chunking", "chunk_count": 0, "message": "Chunking content"}

            parent_splitter = RecursiveCharacterTextSplitter(
                chunk_size=settings.PARENT_CHUNK_SIZE,
                chunk_overlap=0,
                separators=["\n\n", "\n", ". ", " ", ""],
            )
            child_splitter = RecursiveCharacterTextSplitter(
                chunk_size=settings.CHILD_CHUNK_SIZE,
                chunk_overlap=settings.CHILD_CHUNK_OVERLAP,
                separators=["\n\n", "\n", ". ", " ", ""],
            )

            payload: list[dict] = []
            child_idx = 0
            parent_idx = 0

            for page_num, page_text in pages:
                if not page_text.strip():
                    continue
                parent_chunks = parent_splitter.split_text(page_text)
                for parent_text in parent_chunks:
                    if not parent_text.strip():
                        parent_idx += 1
                        continue
                    parent_id = f"{file_id}_parent_{parent_idx}"
                    child_chunks = child_splitter.split_text(parent_text)
                    for child_text in child_chunks:
                        if not child_text.strip():
                            continue
                        payload.append({
                            "id": f"{file_id}_chunk_{child_idx}",
                            "text": child_text,
                            "metadata": {
                                "file_id": file_id,
                                "original_name": original_name,
                                "chunk_index": child_idx,
                                "parent_id": parent_id,
                                "parent_text": parent_text,
                                "page_num": page_num,
                                "collection": collection,
                                "chunk_type": "child",
                                "is_summary": "false",
                            },
                        })
                        child_idx += 1
                    parent_idx += 1

            # Prepend summary chunk so retrieval hits it first
            if summary:
                payload.insert(0, {
                    "id": f"{file_id}_summary",
                    "text": summary,
                    "metadata": {
                        "file_id": file_id,
                        "original_name": original_name,
                        "chunk_index": -1,
                        "parent_id": f"{file_id}_summary",
                        "parent_text": summary,
                        "page_num": 0,
                        "collection": collection,
                        "chunk_type": "summary",
                        "is_summary": "true",
                    },
                })

            # ── 4. Embed all chunks (summary first, then children) ──────
            yield {"stage": "embedding", "chunk_count": len(payload), "message": "Embedding chunks"}
            if payload:
                from backend.db.vector_store import init_vector_store as _init_vs
                store = await _init_vs()
                await store.upsert_chunks(collection, payload)

            # ── 5. Incremental BM25 update ──────────────────────────────
            from backend.app.agents.rag_retriever import rag_retriever
            if payload:
                child_texts = [c["text"] for c in payload]
                child_ids = [c["id"] for c in payload]
                rag_retriever._add_to_bm25_index(collection, child_texts, child_ids)
            else:
                await rag_retriever.rebuild_bm25_index(collection)

            # ── 5b. Ingest into Neo4j knowledge graph ──────────────────
            from backend.db.graph_store import graph_store
            await graph_store.upsert_document(file_id, original_name, summary)
            await graph_store.upsert_entities(
                file_id,
                graph_data.get("entities", []),
                graph_data.get("relationships", []),
            )

            # ── 6. Persist content hash + mark ready ───────────────────
            if db_module.database:
                await db_module.database.store_content_hash(
                    file_hash, file_id, original_name, collection
                )
                await db_module.database.update_file_status(
                    file_id, "ready",
                    chunk_count=len(payload),
                    processed_at=time.time(),
                )

            yield {
                "stage": "done",
                "chunk_count": len(payload),
                "message": (
                    f"Processed {original_name} → {parent_idx} parents, "
                    f"{child_idx} child chunks"
                    + (", 1 summary" if summary else "")
                    + "."
                ),
            }

        except Exception as exc:
            err = str(exc)
            logger.error("File processing failed for %s: %s", file_id, err)
            if db_module.database:
                await db_module.database.update_file_status(file_id, "error", error_message=err)
            yield {"stage": "error", "chunk_count": 0, "message": err}

    # ------------------------------------------------------------------ #
    # Summarization & entity extraction                                    #
    # ------------------------------------------------------------------ #

    async def _summarize_document(self, full_text: str, original_name: str) -> str:
        """Call the local LLM to generate a dense, context-rich document summary."""
        truncated = full_text[: settings.SUMMARIZATION_MAX_INPUT_CHARS]
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert document analyst. Produce a dense, comprehensive "
                    "summary capturing: main topics, key concepts, important facts, "
                    "named entities, and the document's purpose. "
                    "Write 200-400 words in clear paragraph form."
                ),
            },
            {
                "role": "user",
                "content": f"Summarize this document titled '{original_name}':\n\n{truncated}",
            },
        ]
        try:
            from backend.app.agents._lm_studio import complete_chat
            summary = await complete_chat(
                messages=messages,
                model=settings.lm_studio_model,
                temperature=0.2,
                max_tokens=settings.SUMMARIZATION_MAX_TOKENS,
            )
            return (summary or "").strip()
        except Exception as exc:
            logger.warning("Summarization skipped for %s: %s", original_name, exc)
            return ""

    async def _extract_entities(self, summary: str, original_name: str) -> dict:
        """Prompt the local LLM to extract entities and relationships as JSON."""
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a knowledge extraction specialist. Extract entities and "
                    "relationships from the text. Return ONLY valid JSON with this exact "
                    "structure (no markdown, no commentary):\n"
                    '{"entities": [{"name": "...", "type": "PERSON|ORG|CONCEPT|LOCATION|EVENT|TECHNOLOGY"}], '
                    '"relationships": [{"source": "...", "target": "...", "type": "VERB_PHRASE"}]}\n'
                    "Extract 5-15 entities and 3-10 relationships."
                ),
            },
            {
                "role": "user",
                "content": f"Extract entities and relationships:\n\n{summary}",
            },
        ]
        try:
            from backend.app.agents._lm_studio import complete_chat
            raw = await complete_chat(
                messages=messages,
                model=settings.lm_studio_model,
                temperature=0.0,
                max_tokens=1024,
            )
            raw = (raw or "").strip()
            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            data = json.loads(raw)
            return {
                "entities": data.get("entities", []),
                "relationships": data.get("relationships", []),
            }
        except Exception as exc:
            logger.warning("Entity extraction skipped for %s: %s", original_name, exc)
            return {"entities": [], "relationships": []}

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _sha256_file(file_path: str) -> str:
        """Compute SHA-256 hex digest of a file (runs in thread via asyncio.to_thread)."""
        h = hashlib.sha256()
        with open(file_path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    async def _parse_document(
        self, file_path: str, mime_type: str
    ) -> list[tuple[int, str]]:
        """Parse a document and return a list of (page_num, text) tuples.

        page_num is 1-indexed for PDFs; 0 for all other formats.
        Returns an empty list if parsing completely fails.
        """
        loop = asyncio.get_event_loop()
        is_pdf = mime_type == "application/pdf" or file_path.lower().endswith(".pdf")

        if is_pdf:
            # ── PDF Tier 1: PyMuPDF (block-level, preserves reading order) ──
            try:
                def _fitz() -> list[tuple[int, str]]:
                    import fitz  # PyMuPDF  # noqa: PLC0415
                    doc = fitz.open(file_path)
                    pages: list[tuple[int, str]] = []
                    for page_num, page in enumerate(doc, start=1):
                        blocks = page.get_text("blocks")
                        # Sort blocks by vertical position then horizontal (natural reading order)
                        text_blocks = sorted(
                            (b for b in blocks if b[6] == 0 and b[4].strip()),
                            key=lambda b: (b[1], b[0]),
                        )
                        page_text = "\n\n".join(b[4].strip() for b in text_blocks)
                        if page_text.strip():
                            pages.append((page_num, page_text))
                    return pages

                pages = await loop.run_in_executor(None, _fitz)
                if pages:
                    logger.debug("PyMuPDF parsed %s (%d pages)", file_path, len(pages))
                    return pages
            except Exception as exc:
                logger.warning("PyMuPDF failed for %s (%s), trying pypdf", file_path, exc)

            # ── PDF Tier 2: pypdf ────────────────────────────────────────
            try:
                def _pypdf() -> list[tuple[int, str]]:
                    import pypdf  # noqa: PLC0415
                    reader = pypdf.PdfReader(file_path)
                    pages: list[tuple[int, str]] = []
                    for i, page in enumerate(reader.pages, start=1):
                        text = (page.extract_text() or "").strip()
                        if text:
                            pages.append((i, text))
                    return pages

                pages = await loop.run_in_executor(None, _pypdf)
                if pages:
                    logger.debug("pypdf parsed %s (%d pages)", file_path, len(pages))
                    return pages
            except Exception as exc:
                logger.warning("pypdf failed for %s (%s), trying pdfminer", file_path, exc)

            # ── PDF Tier 3: pdfminer.six ─────────────────────────────────
            try:
                def _pdfminer() -> list[tuple[int, str]]:
                    from pdfminer.high_level import extract_text as pdfminer_extract  # noqa: PLC0415
                    text = pdfminer_extract(file_path) or ""
                    return [(0, text)] if text.strip() else []

                pages = await loop.run_in_executor(None, _pdfminer)
                if pages:
                    logger.debug("pdfminer parsed %s", file_path)
                    return pages
            except Exception as exc:
                logger.warning("pdfminer failed for %s (%s)", file_path, exc)
                raise RuntimeError(
                    f"All PDF parsers failed for {Path(file_path).name}. "
                    "Install pymupdf: conda run -n Command pip install pymupdf"
                ) from exc

        # ── Non-PDF: unstructured ────────────────────────────────────────
        try:
            def _unstructured() -> list[tuple[int, str]]:
                from unstructured.partition.auto import partition  # noqa: PLC0415
                elements = partition(filename=file_path)
                text = "\n\n".join(
                    el.text.strip()
                    for el in elements
                    if getattr(el, "text", None) and el.text.strip()
                )
                return [(0, text)] if text.strip() else []

            pages = await loop.run_in_executor(None, _unstructured)
            if pages:
                return pages
        except Exception as exc:
            logger.warning("unstructured failed for %s (%s)", file_path, exc)

        return []


file_processor = FileProcessor()
