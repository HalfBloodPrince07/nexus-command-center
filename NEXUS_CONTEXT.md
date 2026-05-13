# NEXUS OS — Agent Context File

> Read this before touching any code. ~300 lines. Covers everything needed to continue work without reading the repo.

---

## What It Is

A **local-first AI command center** — a glassmorphism desktop web app that lets users chat with a multi-agent AI system running entirely on their machine (LM Studio for LLM, local HF embeddings, Redis, ChromaDB, SQLite). No cloud LLM calls. Agents route tasks to specialists (RAG, file processing, research, vision). The UI is a Next.js 14 app with a left sidebar (nav), main content area (tabs), and a right dashboard panel (system stats + memory).

---

## How to Run

```bash
# Backend — from repo root
cd backend
conda run -n Command pip install -r requirements.txt   # first time only
conda run -n Command uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload

# Frontend — from repo root
cd nexus-os-frontend
npm install    # first time only
npm run dev    # serves on http://localhost:3000
```

**External dependencies that must be running:**
- LM Studio on `http://localhost:1234` — serves the LLM and embedding model
- Redis on `localhost:6379` — episodic memory + A2A message bus (graceful degradation if missing)

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14 (App Router), React 18, TypeScript, Tailwind CSS |
| UI Animation | Framer Motion 12 |
| 3D visuals | Three.js + @react-three/fiber + @react-three/drei |
| State management | Zustand 5 (immer + devtools + persist) |
| Backend | Python 3.11+, FastAPI, uvicorn |
| LLM inference | LM Studio (OpenAI-compatible API via langchain-openai) |
| Embeddings | LM Studio (`nomic-embed-text`) + HuggingFace local fallback |
| Vector DB | ChromaDB 0.5.5 (persistent, `data/chroma/`) |
| Primary DB | SQLite async via SQLAlchemy + aiosqlite (`data/nexus.db`) |
| Episodic memory | Redis sorted sets (async via redis.asyncio) |
| RAG retrieval | ChromaDB vector search + BM25 (rank-bm25) hybrid |
| Research pipeline | LangGraph (partial — Phase 3) |
| System metrics | psutil + GPUtil |

---

## Project Structure (key files only)

```
nexus-os/
├── NEXUS_CONTEXT.md              ← YOU ARE HERE
├── backend/
│   ├── config.py                 ← Pydantic settings (all env vars, ports, paths)
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py               ← FastAPI app + lifespan + router registration
│   │   ├── api/
│   │   │   ├── agents.py         ← GET /api/agents/status
│   │   │   ├── chat.py           ← GET /api/chat/history/{conversation_id}
│   │   │   ├── files.py          ← file upload/list/delete/search
│   │   │   ├── health.py         ← GET /api/health
│   │   │   ├── memory.py         ← CRUD for all three memory tiers
│   │   │   ├── research.py       ← research job management
│   │   │   ├── settings.py       ← GET/POST /api/settings
│   │   │   └── stats.py          ← GET /api/stats/conversation (today + weekly)
│   │   ├── agents/
│   │   │   ├── supervisor.py     ← streams LM Studio, loads history, dispatches agents
│   │   │   ├── knowledge_lead.py ← intent classifier / router
│   │   │   ├── rag_retriever.py  ← BM25 + vector hybrid RAG
│   │   │   ├── file_processor.py ← chunk, embed, upsert to ChromaDB
│   │   │   ├── research_lead.py  ← research orchestration (LangGraph)
│   │   │   └── vision_agent.py   ← image understanding
│   │   ├── memory/
│   │   │   ├── manager.py        ← MemoryManager (orchestrates all three tiers)
│   │   │   ├── episodic.py       ← Redis sorted sets, per-session events (cap 500)
│   │   │   ├── semantic.py       ← ChromaDB collection "nexus_semantic_memory"
│   │   │   └── procedural.py     ← SQLite "procedural_memories" table
│   │   └── ws/
│   │       └── chat.py           ← WebSocket /ws/chat?session_id=...
│   ├── core/
│   │   ├── database.py           ← SQLAlchemy ORM models + all DB query functions
│   │   ├── hf_embeddings.py      ← local HuggingFace embedding model loader
│   │   ├── inference_service.py  ← LM Studio inference abstraction
│   │   ├── message_bus.py        ← Redis pub/sub A2A bus (HMAC-signed)
│   │   └── system_metrics.py     ← psutil + GPUtil metrics
│   └── db/
│       └── vector_store.py       ← ChromaDB VectorStore class + init
│
├── data/
│   ├── nexus.db                  ← live SQLite DB
│   ├── chroma/                   ← ChromaDB persistent store
│   └── uploads/                  ← user-uploaded files
│
└── nexus-os-frontend/src/
    ├── app/
    │   ├── layout.tsx / page.tsx
    │   └── chat/page.tsx         ← main app page
    ├── components/
    │   ├── layout/
    │   │   ├── AppShell.tsx      ← root layout wrapper
    │   │   ├── Sidebar.tsx       ← left nav (tab icons)
    │   │   └── DashboardPanel.tsx← right panel (system health + agents + stats + memory)
    │   ├── tabs/
    │   │   ├── ChatTab.tsx       ← main chat interface
    │   │   ├── FilesTab.tsx      ← file upload + browser + search
    │   │   ├── MemoryTab.tsx     ← memory browser (Episodic/Semantic/Procedural)
    │   │   ├── ResearchTab.tsx   ← research job launcher + results
    │   │   └── SettingsTab.tsx
    │   ├── chat/
    │   │   ├── ChatWindow.tsx / ChatInput.tsx / MessageBubble.tsx
    │   │   └── AgentActivityPanel.tsx
    │   ├── three/                ← Three.js 3D resource orbs
    │   └── ui/                   ← GlassCard, ComingSoon, etc.
    ├── stores/
    │   ├── useAppStore.ts        ← activeTab, systemMetrics, agentStatuses
    │   ├── useChatStore.ts       ← messages, streaming, conversationId, loadHistory
    │   ├── useMemoryStore.ts     ← memory stats + layer data
    │   └── useResearchStore.ts
    ├── hooks/
    │   ├── useWebSocket.ts       ← WS lifecycle, reconnect, all message handlers
    │   └── useAutoScroll.ts
    └── lib/
        ├── constants.ts          ← WS_URL=ws://localhost:8000/ws/chat, API_URL=http://localhost:8000
        ├── types.ts              ← ChatMessage, AgentStatus, SystemMetrics, TabId
        ├── memoryApi.ts          ← fetch wrappers for /api/memory/* + formatRelativeTime
        ├── statsApi.ts           ← fetchConversationStats → ConversationStats
        └── utils.ts              ← cn(), generateId()
```

---

## Database Schema (SQLite — `data/nexus.db`)

| Table | Key columns | Purpose |
|-------|-------------|---------|
| `conversations` | id, title, message_count, created_at, updated_at | conversation metadata |
| `messages` | id, conversation_id, role, content, agent_id, timestamp | chat history |
| `files` | id, filename, mime_type, size_bytes, status, chunk_count | uploaded file tracking |
| `research_jobs` | job_id, topic, slug, status, created_at | research pipeline jobs |
| `procedural_memories` | id, pattern_type, trigger, action, confidence, use_count | behavior patterns |
| `conversation_stats` | session_id, date (YYYY-MM-DD), message_count, total_response_ms | daily stats aggregation |

All DB functions are module-level async functions in `backend/core/database.py`.

---

## Memory Architecture (Three Tiers)

| Tier | Storage | Collection/Key | What's Stored |
|------|---------|----------------|---------------|
| **Episodic** | Redis sorted sets | `nexus:episodic:{session_id}` | Per-session interaction events, capped at 500. Score = Unix timestamp. Available indicator from Redis ping. |
| **Semantic** | ChromaDB | `nexus_semantic_memory` | Factual snippets extracted from assistant responses (>100 chars, contains fact indicators). Uses LM Studio embeddings. |
| **Procedural** | SQLite | `procedural_memories` table | Learned behavior patterns (types: preference/behavior/skill) with confidence scores. |

`MemoryManager` in `memory/manager.py` — `remember_interaction(session_id, user_msg, assistant_msg)` is called as a background task after every exchange. `get_full_stats()` aggregates all three tiers concurrently.

---

## API Routes

### HTTP
```
GET  /                                    → health greeting
GET  /api/health                          → {status, version, db, redis, chromadb}
GET  /api/agents/status                   → {agents: AgentStatus[]}
GET  /api/stats/conversation              → {today_messages, avg_response_ms, weekly_messages[7]}
GET  /api/chat/history/{conversation_id}  → {messages[], conversation_id}  (?limit=50)

GET  /api/memory/stats                    → {episodic, semantic, procedural} counts
GET  /api/memory/episodic/{session_id}    → {items[], count}  (?limit=20)
POST /api/memory/episodic/{session_id}    → store event
DEL  /api/memory/episodic/{session_id}    → clear session
GET  /api/memory/semantic/search          → {results[], count}  (?q=, ?n=5)
POST /api/memory/semantic                 → store fact  (?fact=, ?category=)
GET  /api/memory/procedural               → {patterns[], count}  (?pattern_type=)
POST /api/memory/procedural               → store pattern

GET  /api/files                           → list files
POST /api/files/upload                    → multipart upload
GET  /api/files/{id}/status               → processing status
DEL  /api/files/{id}                      → delete
POST /api/files/search                    → RAG search across files
POST /api/files/{id}/reprocess            → reprocess file

POST /api/research/start                  → start research job  {topic}
GET  /api/research/jobs                   → list jobs
GET  /api/research/jobs/{slug}            → job detail + content
DEL  /api/research/jobs/{slug}            → delete

GET  /api/settings                        → current settings
POST /api/settings                        → update settings
```

### WebSocket — `ws://localhost:8000/ws/chat?session_id={id}`

**Client → Server:**
```json
{"type": "message", "content": "..."}
{"type": "image_query", "content": "...", "image_b64": "...", "image_mime": "image/jpeg"}
{"type": "clear_history"}
{"type": "ping"}
```

**Server → Client:**
```json
{"type": "connected", "conversation_id": "..."}
{"type": "thinking", "agent": "Nexus"}
{"type": "agent_switch", "from": "Nexus", "to": "Echo"}
{"type": "token", "content": "...", "agent_id": "supervisor"}
{"type": "done"}
{"type": "system_metrics", "cpu_percent": 13, "ram_percent": 82, ...}
{"type": "history_cleared"}
{"type": "error", "message": "..."}
{"type": "pong"}
{"type": "progress", "agent": "...", "detail": "...", "stage": "..."}   ← research only
{"type": "chunk", "content": "...", "agent": "Scribe"}                  ← research stream
{"type": "stream_end", "slug": "..."}                                   ← research done
```

System metrics are pushed every 3 seconds over the WebSocket.

---

## Frontend State (Zustand Stores)

### `useChatStore` (persists `conversationId` to localStorage)
- `messages: ChatMessage[]` — in-memory, restored from backend via `loadHistory()` on WS connect
- `conversationId: string | null` — persisted; sent as `session_id` WS query param
- `historyLoaded: boolean` — prevents double-load on reconnects
- `loadHistory(conversationId)` — fetches `GET /api/chat/history/{id}`, sets messages if empty
- `createStreamingMessage(agentId)` → returns id; `updateStreamingMessage(id, token)` appends
- `clearMessages()` — resets messages + historyLoaded flag

### `useAppStore`
- `activeTab: TabId` — controls which tab is shown (chat/dashboard/research/journal/files/memory/insights/settings)
- `systemMetrics: SystemMetrics | null` — updated from WS `system_metrics` events every 3s
- `activeAgents: AgentStatus[]` — updated from WS events (idle/thinking/streaming/error)

### `useMemoryStore`
- `stats: MemoryStats | null` — polled every 30s from `/api/memory/stats`
- `convStats: ConversationStats | null` — polled every 30s from `/api/stats/conversation`
- `episodicItems`, `semanticResults`, `proceduralPatterns` — loaded on demand in MemoryTab

---

## Agents

| Agent | ID | Tier | Role |
|-------|----|------|------|
| Nexus (Supervisor) | supervisor | T1 | Streams LLM, routes intent, loads history |
| Aria | aria | T2 | Knowledge domain lead, routes to RAG |
| Forge | forge | T3 | File processor (chunk, embed, index) |
| Echo | echo | T3 | RAG retriever (BM25 + vector hybrid) |
| Iris | iris | T3 | Vision specialist (image understanding) |

Intent routing in `knowledge_lead.py`. Agent statuses are pushed via WS events and reflected in the right panel and agent list.

---

## What's Implemented (Current State — Phase 2)

- [x] Full chat with streaming LLM responses via LM Studio
- [x] Multi-agent routing (Nexus → Aria → Echo/Forge/Iris)
- [x] Chat history persistence in SQLite + restoration on page refresh
- [x] File upload, chunking, embedding into ChromaDB, RAG retrieval
- [x] Three-tier memory: Redis episodic, ChromaDB semantic, SQLite procedural
- [x] Memory browser tab (MemoryTab) — episodic list, semantic vector search, procedural patterns
- [x] Conversation stats — today's message count, avg response time, 7-day activity chart
- [x] Real-time system metrics (CPU/RAM/GPU/VRAM) pushed every 3s via WebSocket
- [x] Image input (base64 over WebSocket → vision agent)
- [x] Research pipeline (LangGraph — DuckDuckGo → scrape → fact-check → report)
- [x] Settings page (model, temperature, context window, personality)
- [x] Left sidebar navigation + collapsible right dashboard panel
- [x] Glassmorphism UI with Framer Motion animations + Three.js 3D resource orbs

## What's NOT Done Yet (Future Phases)

- [ ] Dashboard tab — charts, agent performance, telemetry (Phase 3)
- [ ] Journal tab — mood tracking, AI insights (Phase 4)
- [ ] Insights tab — proactive pattern recognition (Phase 5)
- [ ] Full 19-agent system (only 5 active; placeholder slots in UI)
- [ ] `/api/system/metrics` HTTP endpoint (metrics only come via WS push currently)
- [ ] Memory write-back to procedural from conversations (currently manual API only)
- [ ] User authentication / multi-user support

---

## Key Conventions

- **Python imports:** always `from __future__ import annotations` at top
- **Python install:** use `conda run -n Command pip install` — never plain `pip install`
- **No cloud LLM calls:** all inference goes through LM Studio at `localhost:1234`
- **Async everywhere:** all DB and Redis operations are async
- **Error resilience:** all memory/db operations are try/except with graceful fallback; Redis/ChromaDB unavailability degrades gracefully (returns `available: false` not crashes)
- **Frontend comments:** minimal; only add when the WHY is non-obvious
- **Tailwind custom classes used:** `glass`, `glass-elevated`, `bg-surface-elevated`, `bg-surface-tertiary`, `text-ink`, `text-ink-secondary`, `text-ink-muted`, `border-border-subtle`, `bg-gradient-primary`, `shadow-glass`, `font-display`
- **WS session_id = conversationId** — they're the same UUID, stored in Zustand `useChatStore.conversationId`, persisted to localStorage as `nexus-chat-storage`

---

## Environment Variables (`backend/.env`)

```env
LM_STUDIO_BASE_URL=http://localhost:1234/v1
LM_STUDIO_MODEL=local-model
LM_STUDIO_EMBEDDING_MODEL=nomic-embed-text
REDIS_URL=redis://localhost:6379
DATABASE_PATH=./data/nexus.db
CHROMA_PERSIST_DIR=./data/chroma
```

All have defaults in `backend/config.py` — the `.env` only overrides what differs from defaults.
