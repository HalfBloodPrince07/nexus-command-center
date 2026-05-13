from fastapi import APIRouter, Query, HTTPException
from typing import List, Optional
from pydantic import BaseModel, Field

from backend.core.database import get_memory_records
from backend.app.memory.manager import memory_manager
from backend.app.agents.memory.memory_archivist import MemoryArchivistAgent, MemoryInput

router = APIRouter(prefix="/api/memory", tags=["memory"])
archivist = MemoryArchivistAgent()

class EpisodicEntryIn(BaseModel):
    event_type: str = "interaction"
    content: str = Field(..., min_length=1)
    metadata: dict = {}

class ProceduralEntryIn(BaseModel):
    pattern_type: str = Field(..., min_length=1)
    trigger: str = Field(..., min_length=1)
    action: str = Field(..., min_length=1)
    session_id: str = ""
    confidence: float = 1.0

# ── New Phase 5 Agentic Endpoints ─────────────────────────────────────────────

@router.get("/search")
async def search_memories(q: str = Query(...), limit: int = 10):
    results = await archivist.query(q, top_k=limit)
    return results

@router.get("/records")
async def list_records(
    limit: int = Query(50), 
    layer: Optional[str] = None, 
    category: Optional[str] = None
):
    records = await get_memory_records(limit=limit, layer=layer, category=category)
    return records

@router.post("/store")
async def store_memory(input_data: MemoryInput):
    record_id = await archivist.store(input_data)
    return {"id": record_id, "status": "stored"}

# ── Restored Original Endpoints (Used by Frontend) ───────────────────────────

@router.get("/stats")
async def get_memory_stats() -> dict:
    return await memory_manager.get_full_stats()

@router.get("/episodic")
async def get_all_episodic(limit: int = Query(50, ge=1, le=200)) -> dict:
    items = await memory_manager.episodic.recall_all(limit=limit)
    return {"items": items, "count": len(items)}

@router.get("/episodic/{session_id}")
async def get_episodic(session_id: str, limit: int = Query(20, ge=1, le=500)) -> dict:
    items = await memory_manager.episodic.recall(session_id, limit=limit)
    return {"session_id": session_id, "items": items, "count": len(items)}

@router.post("/episodic/{session_id}")
async def store_episodic(session_id: str, body: EpisodicEntryIn) -> dict:
    ok = await memory_manager.episodic.store(
        session_id=session_id,
        event_type=body.event_type,
        content=body.content,
        metadata=body.metadata,
    )
    return {"ok": ok, "session_id": session_id}

@router.delete("/episodic/{session_id}")
async def clear_episodic(session_id: str) -> dict:
    await memory_manager.episodic.clear_session(session_id)
    return {"ok": True, "session_id": session_id}

@router.get("/semantic/search")
async def search_semantic(
    q: str = Query(..., min_length=1),
    n: int = Query(5, ge=1, le=50),
    category: Optional[str] = None,
) -> dict:
    results = await memory_manager.semantic.search(q, n=n, category=category)
    return {"query": q, "results": results, "count": len(results)}

@router.get("/semantic")
async def get_semantic(
    limit: int = Query(50, ge=1, le=200),
    category: Optional[str] = None,
) -> dict:
    items = await memory_manager.semantic.browse(limit=limit, category=category)
    return {"items": items, "count": len(items)}

@router.post("/semantic")
async def store_semantic(
    fact: str = Query(..., min_length=1),
    source: str = "",
    category: str = "general",
) -> dict:
    item_id = await memory_manager.semantic.store_fact(
        fact=fact, source=source, category=category
    )
    return {"ok": True, "id": item_id}

@router.get("/procedural")
async def get_procedural(
    limit: int = Query(50, ge=1, le=200),
    pattern_type: Optional[str] = None,
) -> dict:
    patterns = await memory_manager.procedural.get_patterns(limit=limit, pattern_type=pattern_type)
    return {"patterns": patterns, "count": len(patterns)}

@router.post("/procedural")
async def store_procedural(body: ProceduralEntryIn) -> dict:
    pid = await memory_manager.procedural.add_pattern(
        pattern_type=body.pattern_type,
        trigger=body.trigger,
        action=body.action,
        session_id=body.session_id,
        confidence=body.confidence,
    )
    return {"ok": True, "id": pid}

@router.delete("/procedural/{pid}")
async def delete_procedural(pid: str) -> dict:
    ok = await memory_manager.procedural.delete_pattern(pid)
    return {"ok": ok}
