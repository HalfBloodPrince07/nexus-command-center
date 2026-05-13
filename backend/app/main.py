from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from backend.app.api.health import router as health_router
from backend.app.api.agents import router as agents_router
from backend.app.api.files import router as files_router
from backend.app.api.research import router as research_router
from backend.app.api.settings import router as settings_router
from backend.app.api.memory import router as memory_router
from backend.app.api.stats import router as stats_router
from backend.app.api.chat import router as chat_history_router
from backend.app.api.journal import router as journal_router
from backend.app.api.insights import router as insights_router
from backend.api.routes.analytics import router as analytics_router
from backend.app.core.scheduler import nexus_scheduler
from backend.app.memory.manager import memory_manager
from backend.app.ws.chat import router as chat_router
from backend.config import settings, setup_logging, validate_settings
from backend.core.database import init_db
from backend.db.graph_store import init_graph_store
from backend.db.vector_store import init_vector_store

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("NEXUS OS starting up...")

    warnings = validate_settings()
    for warning in warnings:
        logger.warning(warning)

    await init_db()
    await init_vector_store()
    await init_graph_store()

    from backend.app.agents.rag_retriever import rag_retriever

    for collection in ["files", "research", "journal", "memory"]:
        try:
            await rag_retriever.rebuild_bm25_index(collection)
        except Exception:
            pass

    app.include_router(files_router)
    app.include_router(agents_router)
    app.include_router(chat_router)
    app.include_router(research_router)
    app.include_router(settings_router)
    app.include_router(memory_router)
    app.include_router(stats_router)
    app.include_router(chat_history_router)
    app.include_router(journal_router)
    app.include_router(insights_router)
    app.include_router(health_router, prefix="/api", tags=["Health"])
    app.include_router(analytics_router, prefix="/api", tags=["Analytics"])

    await nexus_scheduler.start()

    yield

    await nexus_scheduler.shutdown()
    logger.info("NEXUS OS shutting down...")
    try:
        await memory_manager.close()
    except Exception as exc:
        logger.warning("Memory manager close failed: %s", exc)
    try:
        from backend.db.graph_store import graph_store

        await graph_store.close()
    except Exception as exc:
        logger.warning("Graph store close failed: %s", exc)


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": f"Welcome to {settings.APP_NAME} v{settings.APP_VERSION}"}
