""" ""Memory Archivist Agent -- stores, deduplicates, queries, and links memories.

Dual-write to SQLite (structured records) and ChromaDB (semantic search).
Conflicts are detected via rapidfuzz token-set similarity with a graceful
fallback to SequenceMatcher when rapidfuzz is not installed.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from sqlalchemy import select

from backend.app.agents._lm_studio import complete_chat  # noqa: F401 -- available for LLM-assisted resolution
from backend.config import settings
from backend.core.database import (
    create_memory_record,
    get_memory_records,
    get_session,
    MemoryRecord,
    MemoryLink,
    MemoryConflict,
)
from backend.models.charts import ChartPayload, GraphNode, GraphEdge

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Fuzzy-matching helper -- prefer rapidfuzz, fall back to stdlib
# ---------------------------------------------------------------------------

try:
    from rapidfuzz.fuzz import token_set_ratio as _token_set_ratio
except ImportError:
    logger.info(
        "rapidfuzz not installed; falling back to difflib for conflict detection"
    )

    from difflib import SequenceMatcher

    def _token_set_ratio(a: str, b: str) -> float:  # type: ignore[misc]
        """Return a 0-100 similarity score imitating rapidfuzz.fuzz.token_set_ratio."""
        return SequenceMatcher(None, a.lower(), b.lower()).ratio() * 100.0


# ---------------------------------------------------------------------------
# ChromaDB lazy accessor -- degrades gracefully when ChromaDB is unavailable
# ---------------------------------------------------------------------------


def _get_chroma_collection():
    """Return the nexus_memory ChromaDB collection, or None on failure."""
    try:
        from backend.db.vector_store import init_vector_store
        import asyncio

        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We are inside an async context; use a thread to avoid nested loop
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                vs = pool.submit(asyncio.run, init_vector_store()).result()
        else:
            vs = loop.run_until_complete(init_vector_store())

        return vs.get_collection(settings.CHROMA_COLLECTION_MEMORY)
    except Exception as exc:  # noqa: BLE001
        logger.warning("ChromaDB unavailable -- operating in SQLite-only mode: %s", exc)
        return None


async def _async_get_chroma_collection():
    """Async helper to obtain the ChromaDB collection."""
    try:
        from backend.db.vector_store import init_vector_store

        vs = await init_vector_store()
        return vs.get_collection(settings.CHROMA_COLLECTION_MEMORY)
    except Exception as exc:  # noqa: BLE001
        logger.warning("ChromaDB unavailable -- operating in SQLite-only mode: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Pydantic input model (re-exported for the API layer)
# ---------------------------------------------------------------------------


class MemoryInput(BaseModel):
    content: str = Field(..., min_length=1)
    category: str = "general"
    source_ref: str = ""
    confidence: float = Field(default=0.6, ge=0.0, le=1.0)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    metadata: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Decay scoring
# ---------------------------------------------------------------------------


def _decay_score(
    created_at: datetime, last_reinforced_at: datetime, importance: float
) -> float:
    """Compute a time-decayed relevance score.

    Uses exponential half-life decay based on the most recent reinforcement,
    multiplied by the base importance.
    """
    now = datetime.now(timezone.utc)
    # Use the most recent timestamp (reinforcement resets the clock)
    anchor = max(created_at, last_reinforced_at) if last_reinforced_at else created_at
    # Ensure tz-aware comparison
    if anchor.tzinfo is None:
        anchor = anchor.replace(tzinfo=timezone.utc)
    age_days = max((now - anchor).total_seconds() / 86400.0, 0.0)
    decay = math.exp(-math.log(2) * age_days / settings.MEMORY_DECAY_HALF_LIFE_DAYS)
    return decay * importance


# ---------------------------------------------------------------------------
# Content hashing for fast dedup
# ---------------------------------------------------------------------------


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.strip().lower().encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Agent class
# ---------------------------------------------------------------------------


class MemoryArchivistAgent:
    """Stores, retrieves, deduplicates, and links memory records."""

    # ── Store ─────────────────────────────────────────────────────────────

    async def store(
        self,
        input_data: MemoryInput | None = None,
        *,
        content: str = "",
        category: str = "general",
        source_ref: str = "",
        confidence: float = 0.6,
        importance: float = 0.5,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Store a new memory record with dedup check.

        Accepts either a ``MemoryInput`` pydantic model **or** keyword args.
        Returns the record id (or the id of the existing duplicate).
        """
        if input_data is not None:
            content = input_data.content
            category = input_data.category
            source_ref = input_data.source_ref
            confidence = input_data.confidence
            importance = input_data.importance
            metadata = input_data.metadata
        metadata = metadata or {}

        if not content or not content.strip():
            raise ValueError("Memory content must not be empty")

        content = content.strip()
        c_hash = _content_hash(content)

        # -- 1. Hash-based dedup in SQLite ------------------------------------
        async with get_session() as session:
            existing = (
                (
                    await session.execute(
                        select(MemoryRecord).where(MemoryRecord.content == content)
                    )
                )
                .scalars()
                .first()
            )
            if existing:
                logger.debug(
                    "Exact duplicate found (id=%s); skipping store", existing.id
                )
                return existing.id

        # -- 2. Semantic dedup via ChromaDB (similarity > 0.95) ---------------
        collection = await _async_get_chroma_collection()
        if collection is not None:
            try:
                results = collection.query(
                    query_texts=[content],
                    n_results=1,
                    include=["documents", "distances"],
                )
                if results and results.get("distances") and results["distances"][0]:
                    best_dist = results["distances"][0][0]
                    # ChromaDB L2 distance: similarity ~ 1 - dist/2 for normalised vectors
                    similarity = max(0.0, 1.0 - best_dist / 2.0)
                    if similarity > 0.95:
                        dup_id = results["ids"][0][0]
                        logger.info(
                            "Semantic duplicate detected (sim=%.3f, existing_chroma_id=%s); skipping",
                            similarity,
                            dup_id,
                        )
                        # Try to find the SQLite record that owns this chroma_id
                        async with get_session() as session:
                            row = (
                                (
                                    await session.execute(
                                        select(MemoryRecord).where(
                                            MemoryRecord.chroma_id == dup_id
                                        )
                                    )
                                )
                                .scalars()
                                .first()
                            )
                        return row.id if row else dup_id
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "ChromaDB dedup query failed -- proceeding with store: %s", exc
                )

        # -- 3. Write to SQLite -----------------------------------------------
        record_id = str(uuid.uuid4())
        chroma_id = f"mem_{record_id}"

        await create_memory_record(
            id=record_id,
            layer="long",
            content=content,
            category=category,
            source_ref=source_ref,
            confidence=confidence,
            importance=importance,
            chroma_id=chroma_id,
            source_agent="memory_archivist",
        )
        logger.info("Stored memory record %s (category=%s)", record_id, category)

        # -- 4. Write to ChromaDB ---------------------------------------------
        if collection is not None:
            try:
                meta = {
                    "record_id": record_id,
                    "category": category or "general",
                    "source_ref": source_ref or "",
                    "content_hash": c_hash,
                }
                collection.upsert(
                    ids=[chroma_id],
                    documents=[content],
                    metadatas=[meta],
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "ChromaDB upsert failed for record %s: %s", record_id, exc
                )

        # -- 5. Background conflict detection ---------------------------------
        try:
            await self.detect_conflicts(record_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Conflict detection failed for record %s: %s", record_id, exc
            )

        return record_id

    # ── Query ─────────────────────────────────────────────────────────────

    async def query(
        self,
        q: str,
        filters: dict[str, Any] | None = None,
        top_k: int = 20,
    ) -> list[dict[str, Any]]:
        """Semantic search over memories with decay-based re-scoring.

        Falls back to a plain SQLite keyword scan when ChromaDB is unavailable.
        """
        results: list[dict[str, Any]] = []
        collection = await _async_get_chroma_collection()

        if collection is not None:
            try:
                chroma_results = collection.query(
                    query_texts=[q],
                    n_results=min(top_k * 2, 100),  # over-fetch to allow re-ranking
                    include=["documents", "metadatas", "distances"],
                )
                ids = chroma_results.get("ids", [[]])[0]
                docs = chroma_results.get("documents", [[]])[0]
                metas = chroma_results.get("metadatas", [[]])[0]
                dists = chroma_results.get("distances", [[]])[0]

                # Resolve SQLite records for decay scoring
                record_ids = [m.get("record_id", "") for m in metas]
                records_by_id: dict[str, MemoryRecord] = {}
                if record_ids:
                    async with get_session() as session:
                        rows = (
                            (
                                await session.execute(
                                    select(MemoryRecord).where(
                                        MemoryRecord.id.in_(record_ids)
                                    )
                                )
                            )
                            .scalars()
                            .all()
                        )
                        records_by_id = {r.id: r for r in rows}

                for idx, chroma_id in enumerate(ids):
                    rid = metas[idx].get("record_id", "") if idx < len(metas) else ""
                    rec = records_by_id.get(rid)
                    distance = dists[idx] if idx < len(dists) else 1.0
                    semantic_sim = max(0.0, 1.0 - distance / 2.0)

                    if rec:
                        decay = _decay_score(
                            rec.created_at, rec.last_reinforced_at, rec.importance
                        )
                        # Final score blends semantic similarity with time-decayed importance
                        final_score = 0.7 * semantic_sim + 0.3 * decay
                        category = rec.category
                    else:
                        final_score = semantic_sim
                        category = (
                            metas[idx].get("category", "") if idx < len(metas) else ""
                        )

                    # Apply optional filters
                    if filters:
                        if "category" in filters and category != filters["category"]:
                            continue

                    results.append(
                        {
                            "id": rid or chroma_id,
                            "content": docs[idx] if idx < len(docs) else "",
                            "category": category,
                            "score": round(final_score, 4),
                            "semantic_similarity": round(semantic_sim, 4),
                            "metadata": metas[idx] if idx < len(metas) else {},
                        }
                    )

                results.sort(key=lambda r: r["score"], reverse=True)
                results = results[:top_k]

            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "ChromaDB query failed -- falling back to SQLite: %s", exc
                )
                results = []

        # Fallback: plain SQLite if ChromaDB produced nothing
        if not results:
            raw = await get_memory_records(
                limit=top_k * 2, category=filters.get("category") if filters else None
            )
            q_lower = q.lower()
            for row in raw:
                if q_lower in row.get("content", "").lower():
                    results.append(
                        {
                            "id": row["id"],
                            "content": row["content"],
                            "category": row.get("category", ""),
                            "score": 0.5,
                            "semantic_similarity": 0.0,
                            "metadata": {},
                        }
                    )
            results = results[:top_k]

        return results

    # ── Reinforce ─────────────────────────────────────────────────────────

    async def reinforce(self, record_id: str) -> bool:
        """Bump the reinforcement timestamp and importance for a record."""
        async with get_session() as session:
            rec = await session.get(MemoryRecord, record_id)
            if not rec:
                logger.warning("reinforce: record %s not found", record_id)
                return False
            rec.last_reinforced_at = datetime.now(timezone.utc)
            rec.importance = min(1.0, rec.importance + settings.MEMORY_REINFORCE_BOOST)
            await session.flush()
            logger.info(
                "Reinforced memory %s (importance=%.2f)", record_id, rec.importance
            )
            return True

    # ── Conflict Detection ────────────────────────────────────────────────

    async def detect_conflicts(self, record_id: str) -> list[str]:
        """Compare a record's content against existing memories.

        Uses rapidfuzz token_set_ratio (or difflib fallback) to find records
        whose text is similar but not identical -- potential contradictions.

        For each candidate, uses LM Studio to generate explanation and classify
        conflict type: factual, temporal, or preferential.

        Returns a list of created conflict ids.
        """
        from backend.app.agents._lm_studio import complete_chat

        async with get_session() as session:
            target = await session.get(MemoryRecord, record_id)
            if not target:
                return []
            target_content = target.content
            target_category = target.category

        # Fetch candidates from the same category
        candidates = await get_memory_records(limit=200, category=target_category)
        conflict_ids: list[str] = []

        for cand in candidates:
            if cand["id"] == record_id:
                continue

            ratio = _token_set_ratio(target_content, cand.get("content", ""))
            similarity = ratio / 100.0  # normalise to 0-1

            if similarity < settings.MEMORY_CONFLICT_SIM_THRESHOLD:
                continue
            if similarity > 0.95:
                # Near-duplicate, not a conflict
                continue

            # Use LM Studio to analyze conflict
            messages = [
                {
                    "role": "system",
                    "content": "You are a conflict detection assistant. Analyze two facts and determine if they contradict each other.",
                },
                {
                    "role": "user",
                    "content": f"""Fact A: {target_content}
Fact B: {cand.get("content", "")}

Are these facts in conflict? Respond in JSON:
{{
  "conflict": true/false,
  "conflict_type": "factual|temporal|preferential|none",
  "explanation": "Brief 1-2 sentence explanation of the conflict"
}}
""",
                },
            ]

            analysis_result = ""
            async for chunk in complete_chat(
                messages, model="llama3.1", temperature=0.3
            ):
                analysis_result += chunk.get("content", "")

            try:
                # Extract JSON from response
                import re

                json_match = re.search(r"\{.*\}", analysis_result, re.DOTALL)
                if json_match:
                    analysis = json.loads(json_match.group())
                else:
                    # Fallback simple parsing
                    analysis = {
                        "conflict": True,
                        "conflict_type": "factual",
                        "explanation": "Similar but potentially conflicting information detected",
                    }
            except (json.JSONDecodeError, ValueError):
                logger.warning(
                    "Failed to parse conflict analysis for %s vs %s",
                    record_id,
                    cand["id"],
                )
                continue

            if not analysis.get("conflict", False):
                continue

            conflict_id = str(uuid.uuid4())
            conflict_type = analysis.get("conflict_type", "factual")
            explanation = analysis.get("explanation", "Similar facts detected")

            async with get_session() as session:
                session.add(
                    MemoryConflict(
                        id=conflict_id,
                        fact_a_id=record_id,
                        fact_b_id=cand["id"],
                        conflict_type=conflict_type,
                        explanation=explanation,
                        status="unresolved",
                        detected_at=datetime.now(timezone.utc),
                    )
                )
                await session.flush()

            conflict_ids.append(conflict_id)
            logger.info(
                "Conflict detected: %s <-> %s (sim=%.3f, type=%s)",
                record_id,
                cand["id"],
                similarity,
                conflict_type,
            )

            # Emit WebSocket event
            await self._notify_conflict_detected(
                conflict_id, record_id, cand["id"], explanation
            )

        return conflict_ids

    # ── Resolve Conflict ──────────────────────────────────────────────────

    async def resolve_conflict(
        self,
        conflict_id: str,
        winner_id: str | None = None,
        note: str = "",
    ) -> bool:
        """Mark a conflict as resolved, optionally noting which record won."""
        async with get_session() as session:
            conflict = await session.get(MemoryConflict, conflict_id)
            if not conflict:
                logger.warning("resolve_conflict: conflict %s not found", conflict_id)
                return False
            conflict.status = "resolved"
            conflict.resolution_note = note or (
                f"winner={winner_id}" if winner_id else "manual"
            )
            conflict.resolved_at = datetime.now(timezone.utc)
            await session.flush()
            logger.info("Resolved conflict %s (winner=%s)", conflict_id, winner_id)

        # If a winner was chosen, reinforce it
        if winner_id:
            await self.reinforce(winner_id)

        return True

    # ── Internal Helpers ─────────────────────────────────────────────────-

    async def _notify_conflict_detected(
        self, conflict_id: str, fact_a_id: str, fact_b_id: str, explanation: str
    ) -> None:
        """Emit WebSocket notification when a conflict is detected.

        Sends a conflict_detected event to the frontend for UI updates.
        """
        # Import websockets at runtime to avoid circular imports
        # Assuming websocket manager exists at backend.app.ws.manager
        try:
            from backend.app.ws import manager

            # Build payload
            payload = {
                "event": "conflict_detected",
                "conflict_id": conflict_id,
                "fact_a_id": fact_a_id,
                "fact_b_id": fact_b_id,
                "explanation": explanation,
                "detected_at": datetime.now(timezone.utc).isoformat(),
            }

            # Emit to all connected clients
            await manager.broadcast("system", payload)

        except ImportError:
            logger.debug(
                "WebSocket manager not available, skipping conflict notification"
            )
        except Exception as exc:
            logger.warning("Failed to emit conflict_detected WebSocket event: %s", exc)

    # ── Knowledge Graph ───────────────────────────────────────────────────

    async def knowledge_graph(self, depth: int = 2) -> ChartPayload:
        """Build a graph visualisation of memory records and their links.

        Returns a ``ChartPayload`` of type ``"graph"`` consumable by the
        frontend charting components.
        """
        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []
        seen_ids: set[str] = set()

        async with get_session() as session:
            # Fetch all memory records
            records = (
                (await session.execute(select(MemoryRecord).limit(500))).scalars().all()
            )

            for rec in records:
                seen_ids.add(rec.id)
                decay = _decay_score(
                    rec.created_at, rec.last_reinforced_at, rec.importance
                )
                nodes.append(
                    GraphNode(
                        id=rec.id,
                        label=rec.content[:60]
                        + ("..." if len(rec.content) > 60 else ""),
                        size=max(0.3, decay),
                        category=rec.category or "general",
                        metadata={
                            "layer": rec.layer,
                            "confidence": rec.confidence,
                            "importance": rec.importance,
                        },
                    )
                )

            # Fetch all memory links (up to depth hops)
            links = (
                (
                    await session.execute(
                        select(MemoryLink).limit(
                            settings.MEMORY_MAX_LINKS_PER_NODE * len(seen_ids)
                        )
                    )
                )
                .scalars()
                .all()
            )

            for link in links:
                if link.src_id in seen_ids and link.dst_id in seen_ids:
                    edges.append(
                        GraphEdge(
                            source=link.src_id,
                            target=link.dst_id,
                            label=link.relation,
                            weight=link.weight,
                        )
                    )

        # Guard: ChartPayload validator requires non-empty nodes and edges
        if not nodes:
            nodes.append(GraphNode(id="_empty", label="No memories yet", size=0.5))
        if not edges:
            # Add a self-loop so the validator passes
            edges.append(
                GraphEdge(source=nodes[0].id, target=nodes[0].id, label="self")
            )

        return ChartPayload(
            id=f"memory_graph_{uuid.uuid4().hex[:8]}",
            type="graph",
            title="Memory Knowledge Graph",
            nodes=nodes,
            edges=edges,
            meta={"depth": depth, "node_count": len(nodes), "edge_count": len(edges)},
        )


# Convenience alias used by the API router
MemoryArchivistAgent = MemoryArchivistAgent  # noqa: E501 -- explicit re-export
