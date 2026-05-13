import logging
from pathlib import Path
import httpx
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # App
    APP_NAME: str = "NEXUS OS"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # LM Studio / Local Inference (Phase 2+) - LOCAL INFERENCE ONLY
    # Vision model for image inputs (falls back to LLM if empty)
    LM_STUDIO_VISION_MODEL: str = ""
    LM_STUDIO_MODEL: str = "local-model"

    # LM Studio settings (used for chat/vision inference only — embeddings use HuggingFace locally)
    LM_STUDIO_BASE_URL: str = "http://localhost:1234/v1"
    LM_STUDIO_API_KEY: str = "lm-studio"
    LM_STUDIO_EMBEDDING_MODEL: str = "nomic-embed-text"

    # Main LLM Model Configuration
    SUPERVISOR_MODEL: str = "local-model"
    SUPERVISOR_TEMPERATURE: float = 0.7
    SUPERVISOR_MAX_TOKENS: int = 2048
    SUPERVISOR_CONTEXT_WINDOW: int = 4096

    # Hugging Face Transformers Embeddings (LOCAL HF MODEL - NOT LM Studio/Ollama)
    # Uses huggingface_hub + torch to download from HF directly
    # BAAI/bge-m3: 1024-dim, 8192-token context, CLS pooling, MIT license, no prefix required
    # Top MTEB retrieval score among sub-1B local models; perfect for RAG/ChromaDB
    HF_EMBEDDING_MODEL_ID: str = "BAAI/bge-m3"

    # Ollama (fallback for Phase 2+)
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # Database
    DATA_DIR: Path = Path("./data")
    DATABASE_PATH: Path = DATA_DIR / "nexus.db"
    CONVERSATIONS_DIR: Path = DATA_DIR / "conversations"

    # Redis / A2A Bus
    REDIS_URL: str = "redis://localhost:6379"
    A2A_SECRET_KEY: str = "nexus-dev-secret-change-in-production"
    A2A_MESSAGE_TTL: int = 3600  # seconds

    # Personalities
    PERSONALITIES_DIR: Path = Path(__file__).parent / "personalities"
    ACTIVE_PERSONALITY: str = "nexus_default"
    dynamic_personality_enabled: bool = True

    # Memory (Phase 2+)
    CHROMA_PERSIST_DIR: Path = DATA_DIR / "chroma"
    CHROMA_COLLECTION_PREFIX: str = "nexus"

    # RAG Configuration (Phase 2+)
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 50

    # HF Embeddings - Download Directory
    HF_EMBEDDING_CACHE_DIR: Path = DATA_DIR / "embeddings/hf_cache"

    # Cross-Encoder Reranker (pairs with BAAI/bge-m3, MIT licence)
    HF_RERANKER_MODEL_ID: str = "BAAI/bge-reranker-v2-m3"
    HF_RERANKER_CACHE_DIR: Path = DATA_DIR / "embeddings/reranker_cache"

    # Parent-Child Chunking
    # Children (~512 chars) are embedded for precise retrieval.
    # Parents (~2048 chars) are stored in metadata and returned to the LLM for richer context.
    PARENT_CHUNK_SIZE: int = 2048  # chars per parent chunk
    CHILD_CHUNK_SIZE: int = 512    # chars per child chunk
    CHILD_CHUNK_OVERLAP: int = 64  # overlap between sibling child chunks

    # Document Upload (Phase 2+)
    UPLOAD_DIR: Path = DATA_DIR / "uploads"
    MAX_UPLOAD_SIZE_MB: int = 50

    # File Storage (Phase 2+, stubs)
    FILES_DIR: Path = DATA_DIR / "files"
    MAX_FILE_SIZE_MB: int = 50

    # Phase 3 — Research Cluster
    DEEP_RESEARCH_DIR: Path = DATA_DIR / "deep_research"
    MAX_SEARCH_RESULTS: int = 10
    MAX_SCRAPE_CONCURRENCY: int = 5
    SCRAPE_TIMEOUT_SECONDS: int = 15
    MIN_SOURCES_FOR_FACT_CHECK: int = 2
    RESEARCH_CHUNK_SIZE: int = 800
    RESEARCH_CHUNK_OVERLAP: int = 100
    DUCKDUCKGO_REGION: str = "wt-wt"
    DUCKDUCKGO_SAFESEARCH: str = "off"
    MAX_QUERY_VARIATIONS: int = 3
    MAX_FACT_CLAIMS: int = 10

    # Agent Limits
    MAX_CONVERSATION_HISTORY: int = 20
    SUPERVISOR_TIMEOUT_SECONDS: int = 60
    MAX_CONCURRENT_AGENTS: int = 10

    # Neo4j Knowledge Graph (optional — disabled if NEO4J_ENABLED=false)
    NEO4J_ENABLED: bool = False
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "nexus-password"

    # Summarization pipeline (requires LM Studio running)
    SUMMARIZATION_ENABLED: bool = True
    SUMMARIZATION_MAX_INPUT_CHARS: int = 12000
    SUMMARIZATION_MAX_TOKENS: int = 512

    # Folder watch polling interval (seconds)
    FOLDER_WATCH_INTERVAL_SECONDS: int = 30

    # Phase 4 — Journal & Life Cluster
    JOURNAL_DIR: Path = DATA_DIR / "journal"
    MOOD_MIN: int = 1
    MOOD_MAX: int = 10
    MOOD_WINDOW_DAYS_SHORT: int = 7
    MOOD_WINDOW_DAYS_MID: int = 30
    MOOD_WINDOW_DAYS_LONG: int = 90
    PSYCHOLOGY_MIN_ENTRIES: int = 5      # minimum entries before psychology agent runs
    RELATIONSHIP_SENTIMENT_DECAY: float = 0.9  # older interactions weigh less
    MAX_DECISION_CONTEXT_TOKENS: int = 3000

    # Phase 5 — Memory
    MEMORY_DECAY_HALF_LIFE_DAYS: float = 60.0
    MEMORY_REINFORCE_BOOST: float = 0.2
    MEMORY_CONFLICT_SIM_THRESHOLD: float = 0.85
    MEMORY_MAX_LINKS_PER_NODE: int = 25
    CHROMA_COLLECTION_MEMORY: str = "nexus_memory"

    # Phase 6 — Proactive Intelligence
    SCHEDULER_TIMEZONE: str = "local"
    BRIEFING_HOUR: int = 6           # local time
    NIGHTLY_HOUR: int = 22
    PERIODIC_INTERVAL_HOURS: int = 4
    INSIGHT_MAX_PER_BRIEFING: int = 3
    INSIGHT_MIN_SEVERITY: float = 0.4      # filter before push
    PATTERN_WINDOWS_DAYS: list[int] = [7, 30, 90]
    ANOMALY_Z_THRESHOLD: float = 2.0

    @property
    def chunk_size(self) -> int:
        return self.CHUNK_SIZE

    @property
    def chunk_overlap(self) -> int:
        return self.CHUNK_OVERLAP

    @property
    def upload_dir(self) -> Path:
        return self.UPLOAD_DIR

    @property
    def max_upload_size_mb(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB

    @property
    def lm_studio_model(self) -> str:
        return self.LM_STUDIO_MODEL or self.SUPERVISOR_MODEL

    @property
    def lm_studio_vision_model(self) -> str:
        return self.LM_STUDIO_VISION_MODEL or self.lm_studio_model

    model_config = SettingsConfigDict(env_file="backend/.env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()

PHASE_STATUS = {
    "phase_1": {"name": "Command Center", "status": "active", "weeks": "1-2"},
    "phase_2": {"name": "Knowledge Cluster", "status": "planned", "weeks": "3-5"},
    "phase_3": {"name": "Research Cluster", "status": "active", "weeks": "6-8"},
    "phase_4": {"name": "Life OS", "status": "active", "weeks": "9-12"},
    "phase_5": {"name": "Memory System", "status": "active", "weeks": "13-14"},
    "phase_6": {"name": "Proactive Intelligence", "status": "active", "weeks": "15-16"},
}

def validate_settings() -> list[str]:
    warnings = []
    # Create data directories with parents=True for nested paths (e.g., ./data/chroma)
    try:
        settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
        settings.CONVERSATIONS_DIR.mkdir(parents=True, exist_ok=True)
        settings.FILES_DIR.mkdir(parents=True, exist_ok=True)
        settings.CHROMA_PERSIST_DIR.mkdir(parents=True, exist_ok=True)
        settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        # HF Embeddings cache directory (for local model downloads)
        settings.HF_EMBEDDING_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        settings.HF_RERANKER_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        settings.DEEP_RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
        settings.JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        warnings.append(f"Could not create data directories: {e}")

    # Check personalities directory
    if not settings.PERSONALITIES_DIR.exists():
        warnings.append(f"Personalities directory not found at: {settings.PERSONALITIES_DIR}")

    # Check LM Studio reachability
    try:
        httpx.get(f"{settings.LM_STUDIO_BASE_URL}/models", timeout=5.0)
    except httpx.RequestError:
        warnings.append(f"Could not connect to LM Studio at {settings.LM_STUDIO_BASE_URL}. Is it running?")
        
    return warnings

def setup_logging():
    log_level = settings.LOG_LEVEL.upper()
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # Suppress verbose logs from libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

setup_logging()
