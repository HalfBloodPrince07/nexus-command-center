import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from backend.api.routes import health
from backend.api import websocket
from backend.api.ws import agent_network
from backend.api.routes import folders, chat_history, sync_conflicts, sync, chat_history_extended
from backend.core import database, message_bus
from backend.core.file_watcher import get_file_watcher
from backend.core.chat_indexer import ChatHistoryIndexer
from backend.app.agents.proactive.smart_daily_briefing_agent import get_briefing_agent
from backend.config import settings, validate_settings, setup_logging

# Setup logging first
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("NEXUS OS starting up...")

    # Validate settings
    warnings = validate_settings()
    for warning in warnings:
        logger.warning(warning)

    # Initialize Database
    try:
        await database.init_db()
    except database.DatabaseError as e:
        logger.critical("Database initialization failed: %s. Aborting startup.", e)
        raise

    # Initialize File Watcher and start watching existing folders
    try:
        watcher = await get_file_watcher()
        db = database.get_database()
        if db:
            watched_folders = await db.get_all_watched_folders()
            for folder in watched_folders:
                if folder.get("is_active"):
                    await watcher.add_folder(
                        folder["path"], folder.get("collection", "files")
                    )
        logger.info(
            "File watcher initialized with %d folders",
            len(watched_folders) if "watched_folders" in locals() else 0,
        )
    except Exception as e:
        logger.error("Failed to initialize file watcher: %s", e, exc_info=True)

        # Initialize Chat History Indexer
        try:
            chat_indexer = ChatHistoryIndexer()
            await chat_indexer.initialize()
            app.state.chat_indexer = chat_indexer
            logger.info("Chat history indexer initialized")
        except Exception as e:
            logger.error("Failed to initialize chat indexer: %s", e, exc_info=True)

        # Initialize Smart Daily Briefing Agent scheduler
        try:
            briefing_agent = await get_briefing_agent()
            await briefing_agent.initialize_scheduler()
            logger.info(
                "Daily briefing agent initialized [schedule: %s]",
                getattr(settings, "DAILY_BRIEFING_CRON", "0 7 * * *"),
            )
        except Exception as e:
            logger.error(
                "Failed to initialize daily briefing agent: %s", e, exc_info=True
            )

        # Connect Message Bus (optional)
        await message_bus.message_bus.connect()

    yield

    # Shutdown
    logger.info("NEXUS OS shutting down...")

    # Stop daily briefing agent
    try:
        briefing_agent = await get_briefing_agent()
        if briefing_agent.scheduler and briefing_agent.scheduler.running:
            await briefing_agent.shutdown_scheduler()
        logger.info("Daily briefing agent stopped")
    except Exception as e:
        logger.error("Error stopping briefing agent: %s", e)

    # Stop file watcher
    try:
        watcher = await get_file_watcher()
        if watcher.is_running:
            watcher.stop()
        logger.info("File watcher stopped")
    except Exception as e:
        logger.error("Error stopping file watcher: %s", e)

    # Disconnect Message Bus
    await message_bus.message_bus.disconnect()


app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION, lifespan=lifespan)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(folders.router, prefix="/api/folders", tags=["Folder Management"])
app.include_router(
    chat_history.router, prefix="/api", tags=["Chat History"]
)  # prefix is set in router

# WebSocket routers do not use a prefix
app.include_router(websocket.router, tags=["Chat"])
app.include_router(agent_network.router, tags=["Agent Network"])


app.include_router(sync_conflicts.router, prefix="/api/sync/conflicts", tags=["Sync Conflicts"])
app.include_router(sync.router, prefix="/api/sync", tags=["Sync"])
app.include_router(chat_history_extended.router, prefix="/api", tags=["Chat History"])


@app.get("/")
async def root():
    return {"message": f"Welcome to {settings.APP_NAME} v{settings.APP_VERSION}"}
