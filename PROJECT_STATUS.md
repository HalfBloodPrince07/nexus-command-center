# NEXUS OS — Project Status & Task Board

> For continuing agents: read this + `NEXUS_CONTEXT.md` (architecture). Do NOT read the full codebase.
> Last updated: 2026-04-20

---

## Quick Orientation

Local-first AI command center. FastAPI backend + Next.js 14 frontend. LLM via LM Studio (localhost:1234). No cloud calls.

Run backend: `conda run -n Command uvicorn backend.app.main:app --port 8000 --reload` (from repo root)
Run frontend: `cd nexus-os-frontend && npm run dev` (serves on localhost:3000)

---

## DONE — Fully Working

### Backend
- [x] FastAPI app with lifespan startup (`backend/app/main.py`)
- [x] WebSocket chat endpoint — `ws://localhost:8000/ws/chat?session_id=...`
  - Sends `{type:"connected", session_id, conversation_id}` on open
  - Pushes system metrics every 3s
  - `ping/pong`, `clear_history` messages handled
  - Image queries handled (`image_query` type)
  - **Main chat always routes to Supervisor directly — no intent-based routing**
- [x] Supervisor agent streams LM Studio responses, saves assistant message to SQLite
- [x] Chat history — user messages saved in `ws/chat.py`, assistant messages in `supervisor.py`
- [x] `GET /api/chat/history/{conversation_id}?limit=50` — returns messages as JSON with ISO timestamps
- [x] `GET /api/stats/conversation` — returns `{today_messages, avg_response_ms, weekly_messages[7]}`
- [x] `GET /api/system/metrics` — returns CPU/RAM/GPU/VRAM metrics (in `health.py`, registered with `/api` prefix)
- [x] Memory API (`/api/memory/stats`, `/api/memory/episodic/*`, `/api/memory/semantic/search`, `/api/memory/procedural`)
- [x] File upload + processing + ChromaDB embedding (`/api/files/*`)
- [x] Research pipeline — LangGraph, DuckDuckGo → scrape → fact-check → report (`/api/research/*`)
- [x] Settings API — model list from LM Studio, active model selection (`/api/settings`)
- [x] Three-tier memory system:
  - Episodic: Redis sorted sets, key `nexus:episodic:{session_id}`, cap 500/session
  - Semantic: ChromaDB collection `nexus_semantic_memory`, LM Studio embeddings
  - Procedural: SQLite `procedural_memories` table (types: preference/behavior/skill)
  - `memory_manager.remember_interaction()` fires as background task after every exchange
- [x] SQLite schema: `conversations`, `messages`, `files`, `research_jobs`, `procedural_memories`, `conversation_stats`
- [x] `record_message()` + `get_today_stats()` + `get_weekly_stats()` for conversation stats
- [x] Redis A2A message bus (HMAC-signed pub/sub) — `core/message_bus.py`
- [x] System metrics via psutil + GPUtil — `core/system_metrics.py`
- [x] BM25 + ChromaDB hybrid RAG retrieval — `agents/rag_retriever.py`
- [x] Vision agent for image analysis — `agents/vision_agent.py`

### Frontend
- [x] App shell: left sidebar (collapsible, 240px/72px) + main content + right dashboard panel (320px, spring-animated)
- [x] 8 navigation tabs: chat, dashboard, research, journal, files, memory, insights, settings
- [x] **Chat tab** — fully working, streaming, markdown rendering, image attach, agent status indicator
  - `conversationId` persisted to localStorage (key: `nexus-chat-storage`)
  - On WS connect, `loadHistory(conversationId)` restores messages from backend if store is empty
  - `historyLoaded` flag prevents double-load on reconnects
- [x] **Files tab** — upload (drag-drop), browser (grid/list), search, delete, reprocess
- [x] **Memory tab** — three-tier browser (Episodic list, Semantic vector search, Procedural pattern list)
- [x] **Research tab** — job launcher + pipeline visualizer + results viewer
- [x] **Settings tab** — LM Studio model selector (fetches from backend)
- [x] **Right dashboard panel** — system health (CPU/RAM/GPU/VRAM bars + 3D orbs), active agents, conversation stats (today + avg + 7-day chart using real weekly data), memory tier counts + availability dots
- [x] Zustand stores: `useAppStore`, `useChatStore`, `useMemoryStore`, `useResearchStore`
- [x] WebSocket hook with exponential backoff reconnect (max 10 attempts)
- [x] Framer Motion animations throughout + Three.js 3D resource orbs (CPU/RAM/GPU/VRAM)
- [x] Glassmorphism design system (custom Tailwind classes: `glass`, `glass-elevated`, `bg-surface-elevated`, `text-ink`, `text-ink-secondary`, `text-ink-muted`, `bg-gradient-primary`, `shadow-glass`)

---

## DONE — Recently Fixed (know these are already resolved)

- [x] **Chat history not restoring on page refresh** — was: `connected` event sent `session_id` key but frontend read `conversation_id`. Fixed in `ws/chat.py` to send both keys.
- [x] **Double user message save** — was: `ws/chat.py` saved user msg, then `supervisor.py` saved it again. Removed duplicate from `supervisor.py`.
- [x] **Non-general intent responses not saved** — RAG/image/research tokens were streamed but never written to DB. Fixed in `ws/chat.py`.
- [x] **Main chat routing to wrong agents** — messages containing "research", "find", "search" keywords were rerouted to Aria/Echo/Iris, causing LM Studio errors. Fixed: main chat always uses Supervisor directly.
- [x] **MemoryTab.tsx missing** — was crashing the app when clicking Memory tab. Created.
- [x] **Weekly stats chart** — was fake/approximated. Now uses real `GET /api/stats/conversation` → `weekly_messages[7]` from SQLite.

---

## NOT DONE — Stub / ComingSoon Tabs

These tabs exist in the sidebar but render a `<ComingSoon>` component. They need to be built.

### Dashboard Tab (`activeTab === "dashboard"`)
**File to create:** `nexus-os-frontend/src/components/tabs/DashboardTab.tsx`
**What it should show:**
- Agent performance charts (response time, message count per agent)
- Live system metrics (reuse data from `useAppStore.systemMetrics`, already pushed via WS)
- Conversation volume over time (use `GET /api/stats/conversation` → `weekly_messages`)
- Model info (active model name, context window)
- Error rate / failed requests count
- Suggested stack: recharts or chart.js for graphs, data already available

### Journal Tab (`activeTab === "journal"`)
**File to create:** `nexus-os-frontend/src/components/tabs/JournalTab.tsx`
**What it should show:**
- Daily journal entries (text editor)
- Mood/energy tracking (emoji or slider input)
- AI-powered reflection / insights on past entries
- Needs: new SQLite table `journal_entries (id, date, content, mood, created_at)`, new API route `GET/POST /api/journal`

### Insights Tab (`activeTab === "insights"`)
**File to create:** `nexus-os-frontend/src/components/tabs/InsightsTab.tsx`
**What it should show:**
- Proactive pattern analysis from procedural memory
- Usage trends, most-asked topics
- Suggested next actions
- Needs: new API route `GET /api/insights` that queries procedural + semantic memory

---

## NOT DONE — Backend Gaps

### 1. `/api/system/metrics` — CHECK BEFORE IMPLEMENTING
The frontend calls `GET /api/system/metrics` on WS connect. This route already exists in `backend/app/api/health.py` (line ~37) and is registered with `prefix="/api"` in `main.py`. Verify it returns the right shape before assuming it's broken:
```json
{"cpu_percent": 13, "ram_percent": 82, "ram_used_gb": 25.4, "ram_total_gb": 31.1, "gpu_percent": 23, "gpu_temp_c": 57, "gpu_vram_percent": 61, "gpu_name": "NVIDIA ..."}
```

### 2. Procedural Memory Write-Back
Procedural patterns are never written automatically. Currently only the API can create them (`POST /api/memory/procedural`). The system should learn patterns from repeated interactions (e.g. user always prefers concise answers, always asks about certain topics).
- Where to add: `memory/manager.py` → `remember_interaction()` — after episodic/semantic, add a procedural extraction step
- Logic: detect preference signals in user messages ("always", "prefer", "don't", "stop"), store as `preference` pattern type

### 3. Per-Tab Specialised Chat Endpoints
The main chat is intentionally generic (Supervisor only). Future tabs need their own WS or HTTP streaming endpoints that use `knowledge_lead.route()`:
- Research tab chat → routes to `research_lead`
- Files tab chat → routes to `rag_retriever` (Echo)
- These don't exist yet

### 4. Conversation Title Auto-Generation
`conversations.title` in SQLite is always `null`. Should auto-generate from the first user message (e.g. first 60 chars, or ask LLM for a 5-word summary). Useful for future conversation list/history browser.

---

## NOT DONE — Frontend Gaps

### 1. Conversation History Browser (sidebar or new tab)
No way to browse past conversations. `GET /api/chat/history/{id}` exists but there's no UI to list or switch conversations. Backend has `get_all_conversations()` function in `database.py` but no API route exposes it.
- Needs: `GET /api/conversations` route + conversation switcher UI in sidebar or a new panel

### 2. Agent List in Right Panel — Hardcoded
The Active Agents section in `DashboardPanel.tsx` hardcodes "1/19 agents active" and shows only the Supervisor slot + 3 empty placeholders. It should show the real active agents from `useAppStore.activeAgents` dynamically. The data is already in the store — just the rendering is hardcoded.

### 3. System Metrics HTTP Endpoint Missing from Frontend Fallback
`useWebSocket.ts` line ~50 calls `GET /api/system/metrics` on connect. If that route works, metrics show immediately on load (not waiting for the first 3s WS push). Confirm this works end-to-end.

### 4. Image Query History Not Restored
When `loadHistory()` restores messages, images are stored as base64 in the user message content (`data:image/jpeg;base64,...`). The `MessageBubble.tsx` component needs to handle this case and render the image preview. Currently image messages from history might show as raw base64 text.

### 5. Memory Tab — Semantic Availability Indicator
The semantic memory layer shows `available: false` until ChromaDB + LM Studio embeddings are both running. But the UI doesn't tell the user *why* it's unavailable or give instructions. The `SemanticPanel` component in `MemoryTab.tsx` shows a `WifiOff` icon with a static message — could be improved with a retry button.

---

## Known Bugs / Issues

| # | Severity | Location | Description |
|---|----------|----------|-------------|
| 1 | Medium | `useWebSocket.ts:50` | `fetch /api/system/metrics` — 404 possible if health router prefix is wrong. Test: `curl http://localhost:8000/api/system/metrics` |
| 2 | Low | `DashboardPanel.tsx` | "1/19 agents active" is hardcoded string, not computed from store |
| 3 | Low | `useChatStore.ts` | `historyLoaded` is not in `partialize`, so it resets to `false` on every page load — this is CORRECT behavior intentionally |
| 4 | Low | `supervisor.py` | If LM Studio is not running, the error message is streamed as a token (valid) but it still gets saved to DB as an assistant message |
| 5 | Low | `ws/chat.py` | `image_query` response is saved with `agent_id="iris"` but vision may be handled by Supervisor depending on LM Studio vision model config |
| 6 | Info | `semantic.py` | Collection name is `nexus_semantic_memory` (no prefix), while all other ChromaDB collections use `nexus_` prefix from config. Not a bug but inconsistent. |

---

## Architecture Decisions Already Made (don't reverse these)

1. **Main chat tab = Supervisor only.** No routing to Aria/Echo/Iris from `/ws/chat`. Specialised routing is for future per-tab endpoints.
2. **No cloud LLM.** Everything goes through LM Studio at `localhost:1234`. Never add OpenAI/Anthropic API keys.
3. **Python installs via conda.** Always `conda run -n Command pip install ...`. Never plain `pip install`.
4. **Redis for episodic, ChromaDB for semantic, SQLite for procedural.** Don't swap these.
5. **session_id = conversation_id.** They are the same UUID. Frontend persists it as `nexus-chat-storage` in localStorage. Backend uses it as both the WS session key and the DB conversation ID.
6. **Async everywhere in backend.** All DB and memory ops are async. Don't introduce sync SQLAlchemy calls.
7. **Graceful degradation.** Redis down → episodic returns `available:false` (no crash). ChromaDB down → semantic returns `available:false`. Never crash the app because a memory tier is unavailable.
8. **Frontend custom Tailwind classes are defined in the project** — `glass`, `glass-elevated`, `bg-surface-elevated`, `bg-surface-tertiary`, `text-ink`, `text-ink-secondary`, `text-ink-muted`, `border-border-subtle`, `bg-gradient-primary`, `shadow-glass`, `font-display`. Use these; don't use hardcoded hex colors inline.

---

## File Locations for Active Work Areas

| Area | Files to edit |
|------|--------------|
| Dashboard tab (build it) | Create `nexus-os-frontend/src/components/tabs/DashboardTab.tsx`, edit `CommandCenter.tsx` to replace ComingSoon |
| Journal tab (build it) | Create `JournalTab.tsx`, add SQLite table in `database.py`, add `backend/app/api/journal.py`, register in `main.py` |
| Insights tab (build it) | Create `InsightsTab.tsx`, add `backend/app/api/insights.py` |
| Conversation list | Add `get_all_conversations()` route in `backend/app/api/chat.py`, add UI in `Sidebar.tsx` or new panel |
| Agent panel (fix hardcoding) | `nexus-os-frontend/src/components/layout/DashboardPanel.tsx` lines ~303-319 |
| Procedural auto-learning | `backend/app/memory/manager.py` → `remember_interaction()` method |
| Conversation auto-title | `backend/app/ws/chat.py` → after first user message save, fire background task to generate title |
| Per-tab chat endpoints | New file `backend/app/ws/research_chat.py` for Research tab, `backend/app/ws/files_chat.py` for Files tab |

---

## API Routes Reference (complete list)

```
GET  /api/health
GET  /api/personality
GET  /api/system/metrics
GET  /api/agents/status
GET  /api/stats/conversation          → {today_messages, avg_response_ms, weekly_messages[7]}
GET  /api/chat/history/{id}           → {messages[], conversation_id}
GET  /api/memory/stats
GET  /api/memory/episodic/{session_id}
POST /api/memory/episodic/{session_id}
DEL  /api/memory/episodic/{session_id}
GET  /api/memory/semantic/search      → ?q=&n=5
POST /api/memory/semantic
GET  /api/memory/procedural           → ?pattern_type=
POST /api/memory/procedural
GET  /api/files
POST /api/files/upload
GET  /api/files/{id}/status
DEL  /api/files/{id}
POST /api/files/search
POST /api/files/{id}/reprocess
POST /api/research/start
GET  /api/research/jobs
GET  /api/research/jobs/{slug}
DEL  /api/research/jobs/{slug}
GET  /api/settings
POST /api/settings

WS   ws://localhost:8000/ws/chat?session_id={uuid}
```
