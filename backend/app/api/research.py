from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.config import settings
from backend.core import database as db_module
from backend.db.vector_store import init_vector_store

router = APIRouter(prefix="/api/research", tags=["research"])


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class StartResearchRequest(BaseModel):
    topic: str
    session_id: str = ""


class StartResearchResponse(BaseModel):
    job_id: str   # maps to session.id — kept for frontend compatibility
    slug: str
    status: str
    message: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_metadata(slug: str) -> Optional[dict]:
    path = settings.DEEP_RESEARCH_DIR / slug / "metadata.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _list_slugs() -> list[str]:
    base = settings.DEEP_RESEARCH_DIR
    if not base.is_dir():
        return []
    return [d.name for d in base.iterdir() if d.is_dir() and (d / "metadata.json").is_file()]


async def _load_sources_for_slug(slug: str) -> list[dict]:
    """Load scraped sources from SQLite; fall back to legacy sources/ JSON files."""
    session_row = await db_module.get_session_by_slug(slug)
    if session_row:
        return await db_module.get_sources_for_session(session_row["session_id"])
    # Legacy fallback: sources stored as JSON files under sources/
    sources_dir = settings.DEEP_RESEARCH_DIR / slug / "sources"
    if not sources_dir.is_dir():
        return []
    results = []
    for f in sources_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            data.pop("text", None)
            results.append(data)
        except Exception:
            pass
    return results


async def _delete_chroma_entries(slug: str) -> None:
    try:
        vs = await init_vector_store()
        collection = vs.get_collection("research")
        collection.delete(where={"slug": slug})
    except Exception:
        pass


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("")
async def list_reports():
    slugs = _list_slugs()
    reports = []
    for slug in slugs:
        meta = _load_metadata(slug)
        if meta:
            reports.append(meta)
    reports.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return reports


@router.get("/sources")
async def list_all_sources():
    slugs = _list_slugs()
    all_sources = []
    for slug in slugs:
        for source in await _load_sources_for_slug(slug):
            source["report_slug"] = slug
            all_sources.append(source)
    return all_sources


@router.post("/start", response_model=StartResearchResponse)
async def start_research(body: StartResearchRequest):
    from slugify import slugify

    if not body.topic.strip():
        raise HTTPException(status_code=422, detail="Topic cannot be empty.")

    session_id = str(uuid.uuid4())
    raw_query = body.topic.strip()
    slug = slugify(raw_query, max_length=60, separator="-")

    try:
        await db_module.create_research_session(session_id, raw_query, raw_query, slug)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to create session: {exc}") from exc

    return StartResearchResponse(
        job_id=session_id,
        slug=slug,
        status="pending",
        message="Research session queued. Connect WebSocket to stream progress.",
    )


@router.get("/status/{job_id}")
async def get_job_status(job_id: str):
    session = await db_module.get_research_session(job_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    return session


@router.get("/{slug}/sources")
async def list_report_sources(slug: str):
    if not (settings.DEEP_RESEARCH_DIR / slug).is_dir():
        raise HTTPException(status_code=404, detail="Report not found.")
    return await _load_sources_for_slug(slug)


@router.get("/{slug}")
async def get_report(slug: str):
    meta = _load_metadata(slug)
    if meta is None:
        raise HTTPException(status_code=404, detail="Report not found.")
    report_path = settings.DEEP_RESEARCH_DIR / slug / "report.md"
    content = report_path.read_text(encoding="utf-8") if report_path.is_file() else ""
    return {"metadata": meta, "content": content}


@router.delete("/{slug}")
async def delete_report(slug: str):
    report_dir = settings.DEEP_RESEARCH_DIR / slug
    if not report_dir.is_dir():
        raise HTTPException(status_code=404, detail="Report not found.")

    await _delete_chroma_entries(slug)

    try:
        shutil.rmtree(report_dir)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to delete files: {exc}") from exc

    try:
        await db_module.delete_research_session_by_slug(slug)
    except Exception:
        pass

    return {"message": f"Report '{slug}' deleted."}
