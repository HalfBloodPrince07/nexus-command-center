# NEXUS OS — Command Center & Research Nexus

A modular, agentic AI operating system that combines conversational intelligence with autonomous research capabilities. Built with FastAPI backend + Next.js frontend, featuring WebSocket streaming, RAG-based knowledge retrieval, and multi-agent collaboration patterns.

---

## Table of Contents

- [Quick Start](#quick-start)
- [Architecture Overview](#architecture-overview)
- [System Capabilities](#system-capabilities)
- [Installation & Setup](#installation--setup)
- [Project Structure](#project-structure)
- [API Reference](#api-reference)
- [Development Guidelines](#development-guidelines)

---

## Quick Start

### Prerequisites

```bash
# Python 3.10+ with pip, Node.js 18+, LM Studio running locally
python --version      # ≥3.10
node --version        # ≥18
lmstudio              # Running on localhost:1234
redis-server          # Optional (for A2A message bus)
```

### Installation

**Backend:**
```bash
cd backend
pip install -r requirements.txt  # if exists, otherwise:
pip install fastapi uvicorn pydantic-settings sqlalchemy chromadb langgraph duckduckgo-search trafilatura httpx aiosqlite
```

**Frontend:**
```bash
cd nexus-os-frontend
npm install
cp .env.example .env.local
# Configure API_URL=http://localhost:8000, WS_URL=ws://localhost:8000/ws/chat
npm run dev
```

### Running the Application

**Backend (Terminal 1):**
```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend (Terminal 2):**
```bash
cd nexus-os-frontend
npm run dev
# Opens at http://localhost:3000
```

---

## Architecture Overview

### High-Level Design

NEXUS OS follows a **tiered agent hierarchy pattern**:

```
┌─────────────────────────────────────────────────────────────────────┐
│                         NEXUS OS                                     │
├─────────────────────────────────────────────────────────────────────┤
│  Frontend (Next.js)                              Backend (FastAPI)   │
│  ┌──────────────────┐◄──────── WebSocket ─────────►│ Lifespan       │
│  │ App Shell        │◄───────────────────────────►│ Initialization │
│  │ ├─ Chat Tab     │◄─────── Events ────────────►│ Database Setup   │
│  │ ├─ Files Tab    │◄──────────────────────────►│ Vector Store      │
│  │ ├─ Research Tab │◄──────── Pipeline ────────►│ Message Bus       │
│  │ └──────────────┐ │                            │ Personalities     │
│                   ▼ │◄──────────────────────────►│ Config            │
│  └─────────────────┘ │                            └─────────────────┘
│        │             │                                         ▲
│        │ WebSocket   │                                         │
│        │(ws://localhost:8000/ws/chat)                        │   │
│          ▼                                                  │   │
│         [Agent Cluster]                                     │   │
│    ┌──────────────────┐                                    │   │
│    │ Supervisor       │─┬───────────────────────────────┐  │   │
│    │ (Tier 1)         │ │                               │  │   │
│    ├──────────────────┤ │  Research Lead               │  │   │
│    │ Knowledge Lead   │─┴→ (Tier 2)                    │  │   │
│    └──────────────────┘     ├── Web Scout              │  │   │
│          │                  ├── Scraper Agent          │  │   │
│          │                  ├── Fact Checker           │  │   │
│          ▼                  └── Report Builder         │  │   │
│    [External Services]                                 │  │   │
│    ┌────────────┐     ┌────────┐    ┌────────┐        │  │   │
│    │ LM Studio  │     │DDG     │    │ChromaDB│        │  │   │
│    └────────────┘     └────────┘    └────────┘        │  │   │
└───────────────────────────────────────────────────────┴──┘
```

### Key Architectural Principles

| Principle | Implementation |
|-----------|----------------|
| **Modularity** | Agents are state machines with well-defined input/output contracts |
| **Streaming** | All LLM responses stream via WebSocket for real-time UI updates |
| **Resilience** | Graceful degradation when external services (DDGS, LM Studio) fail |
| **Extensibility** | Agent personalities defined externally in YAML files |

---

## System Capabilities

### Phase 1: Command Center (✅ Active)

- Interactive chat with real-time token streaming via WebSocket
- Multi-agent conversation routing (Supervisor → specialized agents)
- Conversation history persistence in SQLite
- Image input support for vision queries
- System metrics monitoring

### Phase 2: Knowledge Cluster (🔄 Planned)

- Document upload and chunking
- RAG-based retrieval with hybrid search (BM25 + embeddings)
- Vector embeddings via LM Studio + HuggingFace
- Journal/memory system with daily summaries

### Phase 3: Research Cluster (🔄 Planned)

- Autonomous web research pipeline:
  - **Vector** → DuckDuckGo search with query variations and ranking
  - **Fetch** → Web scraping with paywall detection
  - **Verity** → Cross-source fact validation
  - **Scribe** → Structured report synthesis
- Live pipeline visualization
- Research library with RAG indexing

### Phase 4: Life OS (📋 Planned)

- Personal journal entries
- Memory system for long-term context
- Daily/weekly summary generation

---

## Installation & Setup

### Environment Configuration

Create `backend/.env` based on `.env.example`:

```bash
APP_NAME="NEXUS OS"
APP_VERSION="1.0.0"
DEBUG=true
LOG_LEVEL=INFO

# Server Settings
HOST=0.0.0.0
PORT=8000
CORS_ORIGINS=["http://localhost:3000"]

# LM Studio (Required for LLM + Embeddings)
LM_STUDIO_BASE_URL=http://localhost:1234/v1
LM_STUDIO_API_KEY=lm-studio

# Database & Storage
DATA_DIR=./data
DATABASE_PATH=./data/nexus.db
CONVERSATIONS_DIR=./data/conversations
FILES_DIR=./data/files

# ChromaDB Vector Store
CHROMA_PERSIST_DIR=./data/chroma
```

### Running Tests

**Backend:**
```bash
cd backend
pytest tests/ -v --cov=app --cov-report=html
```

**Frontend:**
```bash
cd nexus-os-frontend
npm run test                    # Run all tests
npm run test:watch              # Watch mode with re-runs
```

---

## Project Structure

```
nexus-os/
├── backend/                          # FastAPI Backend
│   ├── app/                          # Application logic (Phase 2-3+)
│   │   ├── main.py                   # FastAPI entry point
│   │   ├── api/                      # REST API endpoints
│   │   │   ├── research.py           # Research cluster API
│   │   │   ├── files.py              # Document upload/RAG API
│   │   │   └── agents.py             # Agent management
│   │   ├── ws/                       # WebSocket handlers
│   │   │   └── chat.py               # Chat room manager
│   │   └── graph/                    # LangGraph pipelines
│   │       └── research_graph.py     # Research orchestration
│   ├── agents/                       # Agent implementations
│   │   ├── supervisor.py             # Main supervisor agent
│   │   ├── knowledge_lead.py         # Knowledge cluster orchestrator
│   │   ├── research_lead.py          # Research pipeline orchestrator
│   │   └── [specialists]/            # Web Scout, Scraper, etc.
│   ├── core/                         # Core utilities
│   │   ├── database.py               # SQLite conversation storage
│   │   ├── message_bus.py            # Inter-agent messaging
│   │   ├── personality.py            # Agent system prompts
│   │   └── hf_embeddings.py          # HuggingFace embedding service
│   ├── db/                           # Database layer
│   │   └── vector_store.py           # ChromaDB + LM Studio embeddings
│   ├── personalities/                # Agent configurations (YAML)
│   │   └── nexus_default.yaml
│   ├── config.py                     # Settings & validation
│   └── tests/                        # Unit/integration tests
├── nexus-os-frontend/                # Next.js Frontend
│   ├── src/
│   │   ├── app/                      # Next.js App Router pages
│   │   ├── components/               # React components
│   │   │   ├── chat/                 # Chat UI (Phase 1)
│   │   │   ├── tabs/                 # Tab navigation
│   │   │   └── research/             # Research cluster UI (Phase 3)
│   │   ├── stores/                   # Zustand state management
│   │   ├── hooks/                    # Custom React hooks
│   │   │   └── useWebSocket.ts       # WebSocket client hook
│   │   ├── lib/                      # Utilities & API clients
│   │   └── types/                    # TypeScript definitions
├── data/                             # Persistent storage
│   ├── conversations/                # Chat history (JSON)
│   ├── uploads/                      # Uploaded documents (Phase 2)
│   ├── files/                        # Indexed file chunks (Phase 2)
│   ├── chroma/                       # Vector embeddings (ChromaDB)
│   └── deep_research/                # Research reports (Phase 3)
├── .env.example                      # Environment template
├── ARCHITECTURE.md                    # Detailed technical architecture
└── phase3.md                         # Research cluster spec document
```

---

## API Reference

### REST Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Welcome message with app version |
| `GET` | `/api/system/metrics` | Live system metrics (CPU, RAM, GPU) |
| `POST` | `/api/research/start` | Start autonomous research job |
| `GET` | `/api/research` | List all completed reports |
| `GET` | `/api/research/{slug}` | Get report metadata + content |
| `DELETE` | `/api/research/{slug}` | Delete report and vector embeddings |

### WebSocket Endpoints

**Connection:** `ws://localhost:8000/ws/chat?conversation_id={uuid}`

**Message Types (Client → Server):**
- `message` — User sends chat message (or `image_query` with base64 image)
- `ping/pong` — Heartbeat mechanism
- `clear_history` — Clear conversation history

**Server Events:**
| Type | Description |
|------|-------------|
| `connected` | Connection established, returns `conversation_id` |
| `thinking` | Agent is reasoning (updates UI thinking state) |
| `agent_switch` | Switch between agents (e.g., Supervisor → Research Lead) |
| `stream_token` / `token` | Streaming LLM tokens for chat/research reports |
| `progress` | Pipeline progress events (research stages, agent status) |
| `chunk` | Chunks of report content during synthesis |
| `done` | Pipeline complete, returns metadata |
| `system_metrics` | Pushed system resource metrics |
| `error` | Error message from server |

---

## Development Guidelines

1. **Type Safety:** All frontend code must be TypeScript; no `any` types unless explicitly justified
2. **Streaming First:** Prefer streaming responses over batch for chat and research pipelines
3. **Error Handling:** Wrap all async agent calls in try-catch, yield error events to UI
4. **State Management:** Use Zustand stores with immer middleware for immutable updates
5. **Agent Personality System:** Define agent behavior via YAML system prompts in `backend/personalities/`

---

## License

Internal project documentation. NEXUS OS is developed as part of the Command Center development initiative.

---

*Built with ❤️ — Modular AI Systems Architecture*
