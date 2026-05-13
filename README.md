# NEXUS OS — Command Center & Research Nexus

A modular, agentic AI operating system that combines conversational intelligence with autonomous research capabilities. Built with FastAPI backend + Next.js frontend, featuring WebSocket streaming, RAG-based knowledge retrieval, and multi-agent collaboration patterns.

## MCP Server

Nexus OS includes a FastMCP server that exposes the agent toolbelt to external MCP clients such as Claude Desktop, Claude Code, and custom integrations.

Start it from the repo root:

```powershell
conda run -n Command python -m backend.mcp_server
```

The default port is `8765`. Override it with `MCP_SERVER_PORT`. If `MCP_AUTH_TOKEN` is unset, the server binds to `127.0.0.1` and only accepts localhost traffic. If `MCP_AUTH_TOKEN` is set, clients must send `Authorization: Bearer <token>`.

Useful endpoints:

- MCP transport: `http://127.0.0.1:8765/mcp`
- Tool reflection: `http://127.0.0.1:8765/tools/list`

See `backend/mcp/README.md` for Claude Desktop and Claude Code configuration snippets.

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         NEXUS OS                                     │
├─────────────────────────────────────────────────────────────────────┤
│  Frontend (Next.js)                              Backend (FastAPI)   │
│  ┌──────────────────┐                            ┌────────────────┐ │
│  │ App Shell        │◄──────────────────────────►│ Lifespan       │ │
│  │ ┌──────────────┐ │                            │ Initialization │ │
│  │ │ Sidebar      │ │◄─────── WebSocket ───────►│ Database Setup  │ │
│  │ ├─ Chat Tab    │ │◄─────── Events ─────────►│ Vector Store     │ │
│  │ ├─ Files Tab   │ │                            │ ChromaDB        │ │
│  │ ├─ Research    │ │◄───────── Pipeline ─────►│ Message Bus      │ │
│  │ │  ├─ New Res. │ │                            │ Redis/A2A       │ │
│  │ │  ├─ Library  │ │◄─── Progress Events ────►│ Personalities    │ │
│  │ │  └─ Sources  │ │                            │ Config          │ │
│  │ └──────────────┘ │                            └────────────────┘ │
│  └──────────────────┘                                          ▲   │
│       │                                                        │   │
│       ▼ WebSocket (ws://localhost:8000/ws/chat)                │   │
└─────────────────────────────────────────────────────────────────────┼──┘
                                                                      │
                     ┌────────────────────────────────────────────────┘
                     │
    ┌────────────────▼─────────────────────────────────────────────────┐
    │                    Agent Cluster (Phase 2/3)                      │
    ├─────────────────────────────────────────────────────────────────┤
    │  Supervisor (Tier 1)                                             │
    │   ├── Knowledge Lead (Tier 2 — Files, Journal, Memory)           │
    │   └── Research Lead (Tier 2 — Web Scout, Scraper, Fact Checker)  │
    │       ├── Vector (Web Scout)                                     │
    │       ├── Fetch (Scraper Agent)                                  │
    │       ├── Verity (Fact Checker)                                  │
    │       └── Scribe (Report Builder)                                │
    └─────────────────────────────────────────────────────────────────┘
                     ▲        ▲         ▲          ▲           ▲
                     │        │         │          │           │
             ┌───────┴────┐  ┌┴───┐   ┌┴───┐  ┌┴───┐    ┌─────┴────┐
             │ DuckDuckGo │  │HTTP│  │Text│  │ChromaDB│ │ LM Studio │
             └────────────┘  └────┘   └────┘   └───────┘   └────────┘
```

---

## 📁 Project Structure

```
nexus-os/
├── backend/                          # FastAPI Backend
│   ├── app/                          # Application logic (Phase 2-3+)
│   │   ├── main.py                   # FastAPI entry point
│   │   ├── api/                      # REST API endpoints
│   │   │   ├── research.py           # Research cluster API
│   │   ├── ws/                       # WebSocket handlers
│   │   └── graph/                    # LangGraph pipelines
│   │       └── research_graph.py     # Research orchestration graph
│   ├── agents/                       # Agent implementations
│   │   ├── supervisor.py             # Main supervisor agent
│   │   ├── research_lead.py          # Research pipeline orchestrator
│   │   ├── web_scout.py              # Web search specialist (Vector)
│   │   ├── scraper_agent.py          # Content extractor (Fetch)
│   │   ├── fact_checker.py           # Claim validator (Verity)
│   │   └── report_builder.py         # Report synthesizer (Scribe)
│   ├── core/                         # Core utilities
│   │   ├── database.py               # SQLite conversation storage
│   │   ├── message_bus.py            # Inter-agent messaging
│   │   ├── personality.py            # Agent system prompts
│   │   └── hf_embeddings.py          # HuggingFace embedding service
│   ├── db/                           # Database layer
│   │   ├── vector_store.py           # ChromaDB + LM Studio embeddings
│   │   └── __main__.py
│   ├── personalities/                # Agent configurations (YAML)
│   │   └── nexus_default.yaml
│   ├── config.py                     # Settings & validation
│   └── main.py                       # Legacy backend entry point
├── nexus-os-frontend/                # Next.js Frontend
│   ├── src/
│   │   ├── app/                      # Next.js App Router pages
│   │   ├── components/               # React components
│   │   │   ├── chat/                 # Chat UI (Phase 1)
│   │   │   ├── tabs/                 # Tab navigation
│   │   │   └── research/             # Research cluster UI (Phase 3)
│   │   ├── stores/                   # Zustand state management
│   │   │   ├── useAppStore.ts        # Global app state
│   │   │   ├── useChatStore.ts       # Chat conversation state
│   │   │   └── useResearchStore.ts   # Research cluster state
│   │   ├── hooks/                    # Custom React hooks
│   │   │   └── useWebSocket.ts       # WebSocket client hook
│   │   ├── lib/                      # Utilities & API clients
│   │   ├── types/                    # TypeScript type definitions
│   │   └── __tests__/                # Vitest test suite
├── data/                             # Persistent storage
│   ├── conversations/               # Chat history (JSON)
│   ├── uploads/                     # Uploaded documents (Phase 2)
│   ├── files/                       # Indexed file chunks (Phase 2)
│   ├── chroma/                      # Vector embeddings (ChromaDB)
│   └── deep_research/               # Research reports (Phase 3)
├── .env.example                      # Environment template
└── phase3.md                         # Research cluster spec document
```

---

## 🎯 Phase Roadmap

| Phase | Name | Status | Description |
|-------|------|--------|-------------|
| **1** | Command Center | ✅ Active | Core chat interface, WebSocket streaming, conversation history persistence |
| **2** | Knowledge Cluster | 🔄 Planned | Document upload, RAG-based retrieval, vector embeddings via LM Studio + HuggingFace |
| **3** | Research Cluster | 🔄 Planned | Autonomous web research pipeline (Scout → Scraper → Checker → Builder) |
| **4** | Life OS | 📋 Planned | Personal journal, memory system, daily summaries |
| **5** | Intelligence Layer | 📋 Planned | Multi-agent collaboration, self-reflection, advanced reasoning |

---

## 🔧 Tech Stack

### Backend

- **FastAPI** — High-performance async web framework
- **Pydantic v2** — Data validation & settings management
- **SQLite (SQLAlchemy)** — Conversation history storage
- **ChromaDB** — Vector database for embeddings
- **LangGraph** — Stateful agent orchestration
- **HTTPX / Aiohttp** — Async HTTP client

### Frontend

- **Next.js 14** — App Router, React Server Components
- **TypeScript** — Type-safe development
- **Tailwind CSS + Glassmorphism UI Kit** — Modern styling
- **Zustand** — Minimalist state management
- **Framer Motion** — Smooth animations
- **React Three Fiber** — 3D graphics (Hero orb, particle effects)

### AI/ML

- **LM Studio API** — Local LLM inference (`http://localhost:1234/v1`)
- **HuggingFace Transformers** — Embedding model service
- **DuckDuckGo Search API** — Web research queries

---

## 🚀 Quick Start

### Prerequisites

```bash
# Python 3.10+ with pip, Node.js 18+, Redis (optional for A2A)
python --version      # ≥3.10
node --version        # ≥18
redis-server          # Optional: redis-cli ping
```

### Installation

**Backend:**

```bash
cd backend
pip install -r requirements.txt  # if exists, otherwise: pip install fastapi uvicorn pydantic-settings sqlalchemy chromadb langgraph
```

**Frontend:**

```bash
cd nexus-os-frontend
npm install
cp .env.example .env.local      # Configure API_URL, WS_URL
npm run dev
```

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

# ChromaDB Vector Store
CHROMA_PERSIST_DIR=./data/chroma
```

### Running the Application

**Backend (Terminal 1):**

```bash
cd backend
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
# Or legacy: uvicorn main:app --reload
```

**Frontend (Terminal 2):**

```bash
cd nexus-os-frontend
npm run dev
# Opens at http://localhost:3000
```

---

## 📡 API Reference

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

**Message Types:**

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

## 🏛️ Data Models

### Research Report Structure (Phase 3)

```json
{
  "slug": "quantum-computing-advances-2024",
  "topic": "quantum computing advances in 2024",
  "created_at": "2026-04-19T10:30:00Z",
  "source_count": 8,
  "avg_confidence": 0.87,
  "status": "complete",
  "job_id": "uuid-here",
  "word_count": 1240,
  "tags": ["quantum computing", "2024", "technology"],
  "content": "# Research Report\n\n## Executive Summary\n..."
}
```

---

## 🔍 WebSocket Event Flow (Research Pipeline)

```
User: "Research quantum computing advances in 2024"
    │
    ▼
┌───────────────────────────────────────────┐
│ WebSocket Handler (knowledge_lead.py)     │
├───────────────────────────────────────────┤
│ detect research intent                    │
│ → route to Research Lead                  │
└───────────────────────────────────────────┘
    │
    ▼
┌───────────────────────────────────────────┐
│ WebSocket Event: thinking                 │
│ {type: "thinking", agent: "Atlas"}        │
└───────────────────────────────────────────┘
    │
    ▼
┌───────────────────────────────────────────┐
│ Step 1: Web Scout (Vector)                │
│ ──────→ progress: searching               │
│ ──────→ progress: Query 1/3              │
│ ──────→ progress: ranking                │
│ ──────→ result: URLs ranked              │
└───────────────────────────────────────────┘
    │
    ▼
┌───────────────────────────────────────────┐
│ WebSocket Event: agent_switch             │
│ {type: "agent_switch", from: "Atlas",     │
│  to: "Fetch"}                             │
└───────────────────────────────────────────┘
    │
    ▼
┌───────────────────────────────────────────┐
│ Step 2: Scraper Agent (Fetch)             │
│ ──────→ progress: scraping                │
│ ──────→ progress: Scraped 4/10 URLs      │
│ ──────→ result: sources[]                 │
└───────────────────────────────────────────┘
    │
    ▼ (similar flow for Fact Checker → Report Builder)
```

---

## 🧪 Testing

### Backend Tests

```bash
cd backend
pytest tests/ -v --cov=app --cov-report=html
```

### Frontend Tests

```bash
cd nexus-os-frontend
npm run test                    # Run all tests
npm run test:watch              # Watch mode with re-runs
```

---

## 🛠️ Development Guidelines

1. **Type Safety:** All frontend code must be TypeScript; no `any` types unless explicitly justified
2. **Streaming First:** Prefer streaming responses over batch for chat and research pipelines
3. **Error Handling:** Wrap all async agent calls in try-catch, yield error events to UI
4. **State Management:** Use Zustand stores with immer middleware for immutable updates
5. **Agent Personality System:** Define agent behavior via YAML system prompts in `backend/personalities/`

---

## 📝 License

Internal project documentation. NEXUS OS is developed as part of the Command Center development initiative.

---

*Built with ❤️ — Modular AI Systems Architecture*
