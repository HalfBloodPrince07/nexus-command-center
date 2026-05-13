from __future__ import annotations

import asyncio
import json
import logging
import shutil
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Body, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

try:
    import aiofiles
except ImportError:
    import asyncio as _asyncio

    class _FallbackAsyncFile:
        def __init__(self, path: Path, mode: str):
            self._path = path
            self._mode = mode
            self._handle = None

        async def __aenter__(self):
            self._handle = await _asyncio.to_thread(open, self._path, self._mode)
            return self

        async def __aexit__(self, exc_type, exc, tb):
            if self._handle is not None:
                await _asyncio.to_thread(self._handle.close)

        async def write(self, data: bytes):
            if self._handle is None:
                raise RuntimeError("File handle is not open")
            await _asyncio.to_thread(self._handle.write, data)

    class _AioFilesFallback:
        @staticmethod
        def open(path: Path, mode: str):
            return _FallbackAsyncFile(path, mode)

    aiofiles = _AioFilesFallback()

from backend.app.agents.file_processor import file_processor
from backend.app.agents.rag_retriever import rag_retriever
from backend.config import settings
from backend.core import database as db_module
from backend.db.vector_store import init_vector_store as _init_vector_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/files", tags=["files"])

# ── In-memory folder watchers ─────────────────────────────────────────────────
# { watcher_id: { "path": str, "collection": str, "seen": set[str] } }
_folder_watchers: dict[str, dict[str, Any]] = {}
_watcher_task: asyncio.Task | None = None


def _require_database():
    if db_module.database is None:
        raise RuntimeError("Database is not initialized")
    return db_module.database


# ── Background processing ─────────────────────────────────────────────────────

async def process_file_background(
    file_id: str,
    file_path: str,
    original_name: str,
    mime_type: str,
    collection: str,
) -> None:
    database = _require_database()
    await database.update_file_status(file_id, "processing")
    async for _event in file_processor.process_file(file_id, file_path, original_name, mime_type, collection):
        pass


async def _folder_watcher_loop() -> None:
    """Background loop that scans registered folder paths for new files."""
    supported_suffixes = {
        ".pdf", ".docx", ".xlsx", ".md", ".txt", ".png", ".jpg", ".jpeg", ".webp"
    }
    mime_map = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".md": "text/markdown",
        ".txt": "text/plain",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }

    while True:
        await asyncio.sleep(settings.FOLDER_WATCH_INTERVAL_SECONDS)

        for watcher_id, watcher in list(_folder_watchers.items()):
            folder = Path(watcher["path"])
            if not folder.is_dir():
                continue

            collection = watcher["collection"]
            seen: set[str] = watcher["seen"]

            for fp in folder.rglob("*"):
                if not fp.is_file():
                    continue
                if fp.suffix.lower() not in supported_suffixes:
                    continue
                key = str(fp)
                if key in seen:
                    continue

                seen.add(key)
                database = db_module.database
                if database is None:
                    continue

                file_id = str(uuid.uuid4())
                upload_dir = settings.upload_dir / file_id
                upload_dir.mkdir(parents=True, exist_ok=True)
                dest = upload_dir / fp.name

                try:
                    shutil.copy2(fp, dest)
                    mime = mime_map.get(fp.suffix.lower(), "application/octet-stream")
                    size = dest.stat().st_size

                    await database.save_file_record(
                        file_id, fp.name, fp.name, mime, size, collection
                    )
                    asyncio.create_task(
                        process_file_background(file_id, str(dest), fp.name, mime, collection)
                    )
                    logger.info("Folder watcher auto-ingested: %s", fp.name)
                except Exception as exc:
                    logger.warning("Folder watcher failed for %s: %s", fp, exc)


def _ensure_watcher_running() -> None:
    global _watcher_task
    if _watcher_task is None or _watcher_task.done():
        _watcher_task = asyncio.create_task(_folder_watcher_loop())


# ── Static / search routes ────────────────────────────────────────────────────

@router.post("/upload")
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    collection: str = Form("files"),
):
    database = _require_database()
    file_id = str(uuid.uuid4())
    upload_dir = settings.upload_dir / file_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(file.filename or "upload.bin").name
    file_path = upload_dir / safe_name

    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    total_size = 0

    async with aiofiles.open(file_path, "wb") as handle:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            total_size += len(chunk)
            if total_size > max_bytes:
                await file.close()
                file_path.unlink(missing_ok=True)
                shutil.rmtree(upload_dir, ignore_errors=True)
                raise HTTPException(status_code=413, detail="File exceeds maximum upload size")
            await handle.write(chunk)

    await database.save_file_record(
        file_id,
        safe_name,
        file.filename or safe_name,
        file.content_type,
        total_size,
        collection,
    )

    background_tasks.add_task(
        process_file_background,
        file_id,
        str(file_path),
        file.filename or safe_name,
        file.content_type or "application/octet-stream",
        collection,
    )

    return {"file_id": file_id, "status": "pending", "original_name": file.filename or safe_name}


@router.get("/")
async def list_files(collection: str = Query("files")):
    database = _require_database()
    return {"data": await database.list_files(collection)}


@router.get("/search")
async def search_files(q: str, collection: str = Query("files"), n: int = Query(5, ge=1, le=20)):
    """Hybrid vector + BM25 chunk search across indexed file chunks."""
    vector_hits = await rag_retriever._vector_search(q, collection, n=n * 2)
    bm25_hits = rag_retriever._bm25_search(q, collection, n=n * 2)
    merged = rag_retriever._rrf_merge(vector_hits, bm25_hits)
    return {"chunks": merged[:n], "query": q}


@router.get("/search-global")
async def search_global(
    q: str,
    collection: str = Query("files"),
    n: int = Query(10, ge=1, le=30),
):
    """File-level search via document summaries and knowledge graph.

    Returns one result per matching file (not per chunk), ordered by relevance.
    """
    results = await rag_retriever.search_summaries(q, collection=collection, n=n)
    return {"results": results, "query": q}


@router.get("/watched-folders")
async def list_watched_folders():
    return {
        "watchers": [
            {"id": wid, "path": w["path"], "collection": w["collection"], "file_count": len(w["seen"])}
            for wid, w in _folder_watchers.items()
        ]
    }


# ── Pydantic request bodies ───────────────────────────────────────────────────

class WatchFolderRequest(BaseModel):
    path: str
    collection: str = "files"


class ChatContextRequest(BaseModel):
    query: str
    file_ids: list[str]
    collection: str = "files"
    n_results: int = 5


# ── Folder watch endpoints ────────────────────────────────────────────────────

@router.post("/watch-folder")
async def watch_folder(body: WatchFolderRequest):
    """Register a folder path for automatic file ingestion.

    The backend polls every FOLDER_WATCH_INTERVAL_SECONDS seconds.
    New files matching supported types are auto-ingested.
    """
    folder = Path(body.path)
    if not folder.is_dir():
        raise HTTPException(status_code=400, detail=f"Path is not an accessible directory: {body.path}")

    watcher_id = str(uuid.uuid4())
    _folder_watchers[watcher_id] = {
        "path": str(folder.resolve()),
        "collection": body.collection,
        "seen": set(),
    }
    _ensure_watcher_running()

    return {
        "watcher_id": watcher_id,
        "path": str(folder.resolve()),
        "collection": body.collection,
        "status": "watching",
    }


@router.delete("/watch-folder/{watcher_id}")
async def stop_watching_folder(watcher_id: str):
    if watcher_id not in _folder_watchers:
        raise HTTPException(status_code=404, detail="Watcher not found")
    del _folder_watchers[watcher_id]
    return {"status": "stopped", "watcher_id": watcher_id}


# ── Context-injected chat streaming endpoint ──────────────────────────────────

@router.post("/chat-context")
async def chat_with_context(body: ChatContextRequest):
    """Stream an LLM answer grounded in chunks from the specified files only."""
    if not body.file_ids:
        raise HTTPException(status_code=400, detail="At least one file_id is required")

    async def generate():
        try:
            async for token in rag_retriever.search_with_file_filter(
                query=body.query,
                file_ids=body.file_ids,
                collection=body.collection,
                n_results=body.n_results,
            ):
                yield f"data: {json.dumps({'token': token})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# ── Parameterised routes (must come after all static paths) ──────────────────

@router.get("/{file_id}")
async def get_file(file_id: str):
    database = _require_database()
    file_record = await database.get_file(file_id)
    if file_record is None:
        raise HTTPException(status_code=404, detail="File not found")
    return file_record


@router.get("/{file_id}/status")
async def get_file_status(file_id: str):
    database = _require_database()
    file_record = await database.get_file(file_id)
    if file_record is None:
        raise HTTPException(status_code=404, detail="File not found")

    meta: dict = {}
    try:
        meta = json.loads(file_record.get("metadata") or "{}")
    except Exception:
        pass

    return {
        "status": file_record["status"],
        "chunk_count": file_record["chunk_count"],
        "error_message": meta.get("error_message"),
    }


@router.post("/{file_id}/reprocess")
async def reprocess_file(file_id: str, background_tasks: BackgroundTasks):
    """Reset an errored file and retry processing."""
    database = _require_database()
    file_record = await database.get_file(file_id)
    if file_record is None:
        raise HTTPException(status_code=404, detail="File not found")

    file_path = settings.upload_dir / file_id / file_record["filename"]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk — please re-upload")

    await database.update_file_status(file_id, "pending", chunk_count=0)

    background_tasks.add_task(
        process_file_background,
        file_id,
        str(file_path),
        file_record["original_name"],
        file_record["mime_type"] or "application/octet-stream",
        file_record["collection"],
    )
    return {"file_id": file_id, "status": "reprocessing"}


@router.delete("/{file_id}")
async def delete_file(file_id: str):
    """Fully purge a file from all storage layers.

    Every step is individually guarded — a failure in one layer never aborts
    the others, so the record is always removed from SQLite even if ChromaDB
    or Neo4j had trouble. The caller always receives a well-formed JSON response.

    Layers purged:
      1. Filesystem  2. ChromaDB chunks  3. Neo4j graph
      4. ContentHash dedup  5. SQLite record  6. BM25 index
    """
    database = _require_database()

    try:
        file_record = await database.get_file(file_id)
    except Exception as exc:
        logger.error("Could not read file record for %s: %s", file_id, exc)
        raise HTTPException(status_code=500, detail="Database read error") from exc

    if file_record is None:
        raise HTTPException(status_code=404, detail="File not found")

    collection = file_record["collection"]
    errors: list[str] = []

    # 1. Filesystem — always safe to ignore errors
    try:
        upload_dir = settings.upload_dir / file_id
        shutil.rmtree(upload_dir, ignore_errors=True)
    except Exception as exc:
        logger.warning("Filesystem delete failed for %s: %s", file_id, exc)

    # 2. ChromaDB — delete all chunks (child + summary) for this file
    try:
        store = await _init_vector_store()
        await store.delete_by_file_id(collection, file_id)
    except Exception as exc:
        msg = f"ChromaDB delete failed: {exc}"
        logger.warning(msg)
        errors.append(msg)

    # 3. Neo4j knowledge graph — optional, non-fatal
    try:
        from backend.db.graph_store import graph_store
        await graph_store.delete_document(file_id)
    except Exception as exc:
        logger.debug("Graph delete skipped for %s: %s", file_id, exc)

    # 4. ContentHash dedup — must succeed so re-upload of same content works
    try:
        await database.delete_content_hash_by_file_id(file_id)
    except Exception as exc:
        msg = f"ContentHash delete failed: {exc}"
        logger.warning(msg)
        errors.append(msg)

    # 5. SQLite file record — primary record; must succeed
    try:
        await database.delete_file_record(file_id)
    except Exception as exc:
        msg = f"DB record delete failed: {exc}"
        logger.error(msg)
        errors.append(msg)
        raise HTTPException(status_code=500, detail=msg) from exc

    # 6. Rebuild BM25 in-memory index — fire-and-forget; never blocks the response
    async def _rebuild() -> None:
        try:
            await rag_retriever.rebuild_bm25_index(collection)
        except Exception as exc:
            logger.warning("BM25 rebuild failed after delete of %s: %s", file_id, exc)

    asyncio.create_task(_rebuild())

    return {
        "status": "deleted",
        "file_id": file_id,
        "warnings": errors if errors else None,
    }
