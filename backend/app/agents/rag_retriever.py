"""RAG Retriever — hybrid search with RRF fusion and cross-encoder reranking."""
from __future__ import annotations

import asyncio
import logging
import re
from collections import Counter
from math import log
from typing import AsyncGenerator

import httpx

try:
    from rank_bm25 import BM25Okapi
except ImportError:
    class BM25Okapi:  # type: ignore[override]
        def __init__(self, corpus: list[list[str]]):
            self.corpus = corpus
            self.doc_freqs = [Counter(doc) for doc in corpus]
            self.doc_lens = [len(doc) or 1 for doc in corpus]
            self.avgdl = sum(self.doc_lens) / len(self.doc_lens) if self.doc_lens else 1.0
            self.term_df: Counter[str] = Counter()
            for doc in corpus:
                self.term_df.update(set(doc))

        def get_scores(self, query_tokens: list[str]) -> list[float]:
            scores: list[float] = []
            total_docs = max(len(self.corpus), 1)
            for freq_map, doc_len in zip(self.doc_freqs, self.doc_lens):
                score = 0.0
                for token in query_tokens:
                    tf = freq_map.get(token, 0)
                    if tf == 0:
                        continue
                    df = self.term_df.get(token, 0) or 1
                    idf = log((total_docs - df + 0.5) / (df + 0.5) + 1.0)
                    score += idf * tf / (tf + 0.5 + 1.5 * doc_len / self.avgdl)
                scores.append(score)
            return scores

from backend.config import settings
from backend.core.personality import get_system_prompt
from backend.core.resilience import EmbeddingUnavailable, degraded_event
from backend.app.agents._lm_studio import stream_chat_completion

logger = logging.getLogger(__name__)

# English stop words to filter from BM25 tokens
_STOP_WORDS: frozenset[str] = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "this", "that", "these", "those",
    "i", "you", "he", "she", "it", "we", "they", "me", "him", "her", "us",
    "them", "my", "your", "his", "its", "our", "their", "what", "which",
    "who", "when", "where", "how", "not", "no", "so", "if", "as", "from",
    "about", "into", "through", "during", "before", "after", "above",
    "below", "between", "out", "up", "down", "then", "than", "also", "just",
})


def _tokenize(text: str) -> list[str]:
    """Tokenize text for BM25: lowercase, alphanumeric only, no stop words, min 2 chars."""
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return [t for t in tokens if len(t) > 1 and t not in _STOP_WORDS]


class RAGRetriever:
    def __init__(self) -> None:
        self._bm25_indices: dict[str, BM25Okapi] = {}
        self._bm25_corpus: dict[str, list[str]] = {}
        self._bm25_ids: dict[str, list[str]] = {}
        self._bm25_tokenized: dict[str, list[list[str]]] = {}
        self.personality = get_system_prompt("rag_retriever")

    # ------------------------------------------------------------------ #
    # BM25 index management                                                #
    # ------------------------------------------------------------------ #

    async def rebuild_bm25_index(self, collection: str) -> None:
        """Full rebuild from ChromaDB — use on startup or explicit reindex."""
        from backend.db.vector_store import init_vector_store as _init_vs
        store = await _init_vs()
        data = store.get_collection(collection).get(include=["documents", "metadatas"])
        documents: list[str] = data.get("documents") or []
        ids: list[str] = [str(i) for i in (data.get("ids") or [])]

        if not documents:
            self._bm25_indices[collection] = BM25Okapi([[]])
            self._bm25_corpus[collection] = []
            self._bm25_ids[collection] = []
            self._bm25_tokenized[collection] = [[]]
            return

        tokenized = [_tokenize(doc) for doc in documents]
        self._bm25_corpus[collection] = documents
        self._bm25_ids[collection] = ids
        self._bm25_tokenized[collection] = tokenized
        self._bm25_indices[collection] = BM25Okapi(tokenized if tokenized else [[]])

    def _add_to_bm25_index(
        self,
        collection: str,
        new_texts: list[str],
        new_ids: list[str],
    ) -> None:
        """Incrementally add documents to an existing BM25 index.

        Called by FileProcessor after every upload to avoid the O(n) full rebuild.
        On first call for a collection the lists are initialised from scratch.
        """
        existing_corpus = self._bm25_corpus.get(collection, [])
        existing_ids = self._bm25_ids.get(collection, [])
        existing_tokenized = self._bm25_tokenized.get(collection, [])

        new_tokenized = [_tokenize(t) for t in new_texts]

        updated_corpus = existing_corpus + new_texts
        updated_ids = existing_ids + new_ids
        updated_tokenized = existing_tokenized + new_tokenized

        self._bm25_corpus[collection] = updated_corpus
        self._bm25_ids[collection] = updated_ids
        self._bm25_tokenized[collection] = updated_tokenized
        self._bm25_indices[collection] = BM25Okapi(updated_tokenized if updated_tokenized else [[]])

    # ------------------------------------------------------------------ #
    # Search primitives                                                    #
    # ------------------------------------------------------------------ #

    async def _vector_search(
        self, query: str, collection: str, n: int = 20
    ) -> list[dict]:
        from backend.db.vector_store import init_vector_store as _init_vs
        store = await _init_vs()
        return await store.query(collection, query, n_results=n)

    def _bm25_search(
        self, query: str, collection: str, n: int = 20
    ) -> list[dict]:
        index = self._bm25_indices.get(collection)
        corpus = self._bm25_corpus.get(collection, [])
        ids = self._bm25_ids.get(collection, [])
        if index is None or not corpus:
            return []

        tokens = _tokenize(query)
        if not tokens:
            return []

        scores = index.get_scores(tokens)
        ranked = sorted(enumerate(scores), key=lambda item: item[1], reverse=True)[:n]

        results: list[dict] = []
        for rank, (idx, score) in enumerate(ranked, start=1):
            if score <= 0:
                break
            results.append({
                "id": ids[idx] if idx < len(ids) else f"{collection}_{idx}",
                "text": corpus[idx] if idx < len(corpus) else "",
                "metadata": {},
                "score": float(score),
                "rank": rank,
                "source": "bm25",
            })
        return results

    # ------------------------------------------------------------------ #
    # Reciprocal Rank Fusion                                               #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _rrf_merge(
        vector_hits: list[dict],
        bm25_hits: list[dict],
        k: int = 60,
    ) -> list[dict]:
        """Reciprocal Rank Fusion (Cormack et al., 2009).

        score(d) = Σ  1 / (k + rank_i(d))   for each retrieval system i

        k=60 is the canonical value from the original paper. Using two systems
        (dense vector + sparse BM25) always outperforms either alone.
        """
        rrf_scores: dict[str, float] = {}
        hit_by_id: dict[str, dict] = {}

        for rank, hit in enumerate(vector_hits, start=1):
            chunk_id = str(hit.get("id") or "")
            if not chunk_id:
                continue
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
            hit_by_id.setdefault(chunk_id, hit)

        for rank, hit in enumerate(bm25_hits, start=1):
            chunk_id = str(hit.get("id") or "")
            if not chunk_id:
                continue
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
            hit_by_id.setdefault(chunk_id, hit)

        merged: list[dict] = []
        for chunk_id, score in sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True):
            hit = dict(hit_by_id[chunk_id])
            hit["score"] = score
            hit["source"] = "rrf"
            merged.append(hit)

        return merged

    # ------------------------------------------------------------------ #
    # Cross-encoder reranking                                              #
    # ------------------------------------------------------------------ #

    async def _rerank(
        self, query: str, candidates: list[dict], n: int = 5
    ) -> list[dict]:
        """Rerank candidates using the local cross-encoder (no LLM/LM Studio needed).

        Falls back to RRF order if the reranker model hasn't been downloaded yet
        or fails for any reason.
        """
        if not candidates:
            return []

        n = min(n, len(candidates))
        documents = [(c.get("text") or "") for c in candidates]

        try:
            from backend.app.processing.reranker import reranker
            top_indices = await asyncio.to_thread(reranker.rerank, query, documents, n)
            return [candidates[i] for i in top_indices]
        except Exception as exc:
            logger.warning("Cross-encoder reranking failed (%s). Using RRF order.", exc)
            return candidates[:n]

    # ------------------------------------------------------------------ #
    # Parent-chunk expansion                                               #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _expand_to_parents(candidates: list[dict]) -> list[dict]:
        """Swap child chunk text for its parent chunk text if available.

        Child chunks are small (~512 chars) for precise retrieval.
        Parent chunks are larger (~2048 chars) and give the LLM more context.
        The parent_text is stored directly in the child's ChromaDB metadata.
        """
        expanded: list[dict] = []
        for chunk in candidates:
            meta = chunk.get("metadata") or {}
            parent_text = meta.get("parent_text", "")
            if parent_text and parent_text.strip():
                chunk = dict(chunk)
                chunk["text"] = parent_text
                chunk["metadata"] = {**meta, "context_expanded": True}
            expanded.append(chunk)
        return expanded

    # ------------------------------------------------------------------ #
    # Graph-aware retrieval helpers                                        #
    # ------------------------------------------------------------------ #

    async def _graph_related_file_ids(self, query: str) -> list[str]:
        """Return file IDs whose entities match the query (via Neo4j)."""
        try:
            from backend.db.graph_store import graph_store
            return await graph_store.search_entities_for_query(query)
        except Exception as exc:
            logger.debug("Graph search skipped: %s", exc)
            return []

    async def search_summaries(
        self,
        query: str,
        collection: str = "files",
        n: int = 10,
    ) -> list[dict]:
        """Return file-level results by querying summary chunks + knowledge graph.

        Each result contains file_id, original_name, summary text, score, and
        graph-derived entities. Used by the global search UI.
        """
        from backend.db.vector_store import init_vector_store as _init_vs
        store = await _init_vs()
        chroma_collection = store.get_collection(collection)

        # Query only summary chunks
        try:
            raw = chroma_collection.query(
                query_texts=[query],
                n_results=min(n * 2, 50),
                where={"is_summary": "true"},
                include=["documents", "metadatas", "distances"],
            )
            doc_list = raw["documents"][0] or []
            meta_list = raw["metadatas"][0] or []
            dist_list = raw["distances"][0] or []
        except Exception as exc:
            logger.warning("Summary query failed: %s", exc)
            doc_list, meta_list, dist_list = [], [], []

        vector_results: dict[str, dict] = {}
        for text, meta, dist in zip(doc_list, meta_list, dist_list):
            fid = (meta or {}).get("file_id", "")
            if fid and fid not in vector_results:
                # BAAI/bge-m3 produces L2-normalised vectors; ChromaDB returns L2 distance
                # which ranges [0, 2] for unit vectors. Map to [0, 1] similarity score.
                score = max(0.0, 1.0 - float(dist) / 2.0)
                vector_results[fid] = {
                    "file_id": fid,
                    "original_name": (meta or {}).get("original_name", ""),
                    "summary": text,
                    "score": score,
                    "entities": [],
                    "source": "vector",
                }

        # Augment with graph search
        graph_file_ids = await self._graph_related_file_ids(query)
        for i, fid in enumerate(graph_file_ids):
            if fid not in vector_results:
                vector_results[fid] = {
                    "file_id": fid,
                    "original_name": "",
                    "summary": "",
                    "score": max(0.1, 0.5 - i * 0.05),
                    "entities": [],
                    "source": "graph",
                }

        # Fetch entities for all results (best-effort)
        try:
            from backend.db.graph_store import graph_store
            for fid, result in vector_results.items():
                result["entities"] = await graph_store.get_document_entities(fid)
        except Exception:
            pass

        sorted_results = sorted(
            vector_results.values(), key=lambda r: r["score"], reverse=True
        )
        return sorted_results[:n]

    async def search_with_file_filter(
        self,
        query: str,
        file_ids: list[str],
        collection: str = "files",
        n_results: int = 5,
    ) -> AsyncGenerator[str | dict, None]:
        """Retrieve chunks from specific files only and stream an LLM answer."""
        if not file_ids:
            yield "No files selected."
            return

        from backend.db.vector_store import init_vector_store as _init_vs
        store = await _init_vs()
        chroma_collection = store.get_collection(collection)

        try:
            where_clause: dict = (
                {"file_id": {"$in": file_ids}}
                if len(file_ids) > 1
                else {"file_id": file_ids[0]}
            )
            raw = chroma_collection.query(
                query_texts=[query],
                n_results=min(n_results * 3, 30),
                where=where_clause,
                include=["documents", "metadatas", "distances"],
            )
            doc_list = raw["documents"][0] or []
            meta_list = raw["metadatas"][0] or []
            ids_list = raw["ids"][0] or []
            dist_list = raw["distances"][0] or []
        except Exception as exc:
            yield f"Vector search failed: {exc}"
            return

        vector_hits = [
            {"id": i, "text": t, "metadata": m, "distance": float(d)}
            for i, t, m, d in zip(ids_list, doc_list, meta_list, dist_list)
        ]
        bm25_hits = self._bm25_search(query, collection, n=n_results * 3)
        # Filter BM25 to selected files
        bm25_hits = [
            h for h in bm25_hits
            if any(fid in (h.get("id") or "") for fid in file_ids)
        ]

        merged = self._rrf_merge(vector_hits, bm25_hits)
        reranked = await self._rerank(query, merged[:20], n=n_results)
        final_chunks = self._expand_to_parents(reranked)

        async for token in self.stream_answer(query, final_chunks, session_id=""):
            yield token

    # ------------------------------------------------------------------ #
    # Main search entry point                                              #
    # ------------------------------------------------------------------ #

    async def search(
        self,
        query: str,
        collection: str = "files",
        n_results: int = 5,
        session_id: str = "",
    ) -> AsyncGenerator[str | dict, None]:
        fetch_n = max(n_results * 4, 20)

        degraded: dict | None = None
        try:
            vector_hits, bm25_hits = await asyncio.gather(
                self._vector_search(query, collection, n=fetch_n),
                asyncio.to_thread(self._bm25_search, query, collection, fetch_n),
            )
        except EmbeddingUnavailable as exc:
            logger.warning(
                "Vector search unavailable; falling back to BM25",
                extra={"collection": collection, "query": query[:120], "error": str(exc)},
            )
            vector_hits = []
            bm25_hits = await asyncio.to_thread(self._bm25_search, query, collection, fetch_n)
            degraded = degraded_event(
                "Echo",
                "embedding_unavailable",
                "Semantic search is unavailable; using BM25 keyword search only.",
            )

        # RRF fusion
        merged = self._rrf_merge(vector_hits, bm25_hits)

        # Cross-encoder reranking on top-20 candidates
        rerank_pool = merged[:20]
        reranked = await self._rerank(query, rerank_pool, n=n_results)

        # Expand child chunks → parent context
        final_chunks = self._expand_to_parents(reranked)

        if degraded:
            yield degraded

        async for token in self.stream_answer(query, final_chunks, session_id):
            yield token

    async def stream_answer(
        self,
        query: str,
        context_chunks: list[dict],
        session_id: str,
    ) -> AsyncGenerator[str, None]:
        if not context_chunks:
            context_text = "No relevant documents were found."
        else:
            lines: list[str] = []
            for idx, chunk in enumerate(context_chunks, start=1):
                meta = chunk.get("metadata") or {}
                name = meta.get("original_name") or meta.get("filename") or "unknown"
                page = meta.get("page_num")
                page_note = f" (page {page})" if page else ""
                text = (chunk.get("text") or "").strip()
                lines.append(f"[{idx}] {name}{page_note}:\n{text}")
            context_text = "\n\n".join(lines)

        messages = [
            {
                "role": "system",
                "content": (
                    self.personality
                    + "\nAnswer only from the provided context. "
                    "Cite sources inline with bracketed numbers like [1]. "
                    "If the context doesn't contain the answer, say so clearly."
                ),
            },
            {
                "role": "user",
                "content": f"Question: {query}\n\nContext:\n{context_text}",
            },
        ]

        try:
            async for token in stream_chat_completion(
                messages=messages,
                model=settings.lm_studio_model,
                temperature=0.2,
                max_tokens=2048,
            ):
                yield token
        except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as exc:
            logger.warning("LM Studio unavailable during RAG answer", extra={"error": str(exc)})
            yield degraded_event("Echo", "llm_unavailable", "Could not reach the local model for answer synthesis.")
            yield "I found context, but I can't reach the local model right now to synthesize an answer."
        except Exception as exc:
            logger.warning("RAG answer generation failed", extra={"error": str(exc)})
            yield degraded_event("Echo", "answer_generation_failed", str(exc))
            yield f"Error generating answer: {exc}"


rag_retriever = RAGRetriever()
