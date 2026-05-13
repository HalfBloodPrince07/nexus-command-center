from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


_FACT_INDICATORS = (
    " is ", " are ", " was ", " were ", " means ", " refers to ",
    " defined as ", " consists of ", " includes ", " because ",
)


def _looks_factual(text: str) -> bool:
    lowered = text.lower()
    return any(tok in lowered for tok in _FACT_INDICATORS)


class SemanticMemory:
    COLLECTION = "nexus_semantic_memory"

    async def _store(self):
        from backend.db.vector_store import init_vector_store as _init_vs
        return await _init_vs()

    async def store(
        self,
        fact: str,
        source: str = "",
        category: str = "general",
        session_id: str = "",
    ) -> bool:
        if not fact or not fact.strip():
            return False
        try:
            store = await self._store()
            payload = [{
                "id": str(uuid.uuid4()),
                "text": fact.strip(),
                "metadata": {
                    "source": source,
                    "category": category,
                    "session_id": session_id,
                    "stored_at": datetime.now(timezone.utc).isoformat(),
                },
            }]
            await store.upsert_chunks(self.COLLECTION, payload)
            return True
        except Exception as e:
            logger.warning("Semantic store failed: %s", e)
            return False

    async def search(
        self,
        query: str,
        n: int = 5,
        category: str | None = None,
    ) -> list[dict]:
        if not query or not query.strip():
            return []
        try:
            store = await self._store()
            results = await store.query(self.COLLECTION, query, n_results=n)
            if category:
                results = [
                    r for r in results
                    if (r.get("metadata") or {}).get("category") == category
                ]
            return results
        except Exception as e:
            logger.warning("Semantic search failed: %s", e)
            return []

    async def browse(
        self,
        limit: int = 50,
        category: str | None = None,
    ) -> list[dict]:
        try:
            store = await self._store()
            collection = store.get_collection(self.COLLECTION)

            try:
                data = collection.get(include=["documents", "metadatas"])
            except Exception:
                data = collection.get()

            ids = data.get("ids", []) or []
            documents = data.get("documents", []) or []
            metadatas = data.get("metadatas", []) or []

            rows: list[dict] = []
            for idx in range(min(len(ids), len(documents))):
                text = documents[idx]
                if not text:
                    continue
                metadata = metadatas[idx] if idx < len(metadatas) and isinstance(metadatas[idx], dict) else {}
                if category and metadata.get("category") != category:
                    continue
                rows.append({
                    "id": ids[idx],
                    "text": text,
                    "score": 0.0,
                    "metadata": metadata,
                })

            rows.sort(key=lambda row: (row.get("metadata") or {}).get("stored_at") or "", reverse=True)
            return rows[:limit]
        except Exception as e:
            logger.warning("Semantic browse failed: %s", e)
            return []

    async def get_stats(self) -> dict:
        try:
            store = await self._store()
            collection = store.get_collection(self.COLLECTION)
            total = 0
            try:
                total = int(collection.count())
            except Exception:
                try:
                    data = collection.get(include=[])
                    total = len(data.get("ids", []) or [])
                except Exception:
                    total = 0
            return {"total": int(total), "available": True}
        except Exception as e:
            logger.warning("Semantic stats failed: %s", e)
            return {"total": 0, "available": False}

    async def extract_and_store(
        self,
        session_id: str,
        user_msg: str,
        assistant_msg: str,
    ) -> None:
        try:
            if not assistant_msg:
                return
            text = assistant_msg.strip()
            if len(text) <= 100:
                return
            if not _looks_factual(text):
                return
            # Store a bounded snippet to avoid blowing up the collection
            snippet = text[:2000]
            await self.store(
                fact=snippet,
                source=f"session:{session_id}",
                category="conversation",
                session_id=session_id,
            )
        except Exception as e:
            logger.warning("Semantic extract_and_store failed: %s", e)
