# PHASE 7 — Polish, MCP, Settings & Advanced Features

**Timeline:** Week 17–18
**Goal:** Production-grade polish. MCP server exposing all tools. Full Settings page. Agent network visualizer. Advanced features: Obsidian export, chat history search, onboarding flow, keyboard shortcuts, daily briefings, goal tracking, focus analytics, custom agents.

**Final deliverable:** A complete, production-grade local-first intelligence platform — 18 agents across 4 clusters, 7 tabs with 25+ subtabs, data visualization dashboard, proactive morning briefings, vision model, MCP extensibility — all 100% local with zero cloud dependencies.

---

## Prerequisites

Before starting Phase 7, verify Phases 1–6 are functional:
- Phase 1: WebSocket chat with streaming works end-to-end
- Phase 2: Knowledge cluster (file upload, RAG, vision) ingests + retrieves
- Phase 3: Research pipeline produces full reports with citations
- Phase 4: Journal cluster (Mood Analyst, Psychology, Relationship Finder, Life Decisions) writes to DB
- Phase 5: Memory Archivist persists facts; embeddings searchable
- Phase 6: Pattern Detective + Briefing Agent skeletons exist

If any of the above is missing, those gaps must be patched before the corresponding Phase 7 subtask runs (e.g., goal tracker depends on Journal cluster being live).

---

## Task Tracks Overview

| Track | Theme | Subtasks |
|-------|-------|----------|
| **A** | Backend Infrastructure | A1–A6 |
| **B** | New Intelligence Agents | B1–B4 |
| **C** | Analytics & Comparisons | C1–C2 |
| **D** | Settings & Core UX | D1–D9 |
| **E** | Visualization & History | E1–E3 |
| **F** | Integration & Hardening | F1–F2 |

**Total: 24 subtasks.** Tracks A–C can run mostly in parallel. Track D depends on A1, A2, A3 being complete. Track E depends on D being scaffolded. Track F is final.

---

# TRACK A — Backend Infrastructure

## A1. MCP Server (FastMCP) Exposing All Agent Tools

**Subagent:** `api-developer` (with `ai-developer` consult)

**Prompt:**
> Build an MCP (Model Context Protocol) server using FastMCP that exposes Nexus OS's agent toolbelt to external MCP clients (Claude Desktop, Claude Code, custom integrations).
>
> **Location:** Create `backend/mcp/` with `server.py`, `tools.py`, `__init__.py`. Add an entry point script `backend/mcp_server.py` that runs the server standalone on a configurable port (default 8765, env var `MCP_SERVER_PORT`).
>
> **Tools to expose** (each is a thin wrapper around existing agent functions, never reimplement business logic):
> 1. `search_local_files(query: str, top_k: int = 5)` — calls `app/agents/rag_retriever.py`
> 2. `search_web(query: str, max_results: int = 10)` — calls `app/agents/web_scout.py`
> 3. `save_memory(fact: str, category: str, importance: int)` — calls `app/agents/memory/memory_archivist.py`
> 4. `get_journal_insights(date_range: str = "7d", topic: str | None = None)` — aggregates from journal tables
> 5. `save_research_report(title: str, query: str)` — kicks off research graph in `app/graph/research_graph.py`
> 6. `analyze_image(image_path: str, question: str)` — calls vision agent
>
> **Requirements:**
> - Each tool has a Pydantic input/output schema and a clear docstring (the docstring becomes the MCP tool description)
> - Tools must be async and respect existing timeouts in `backend/config.py`
> - Add a `tools/list` reflection endpoint returning all registered tools
> - Authentication: read `MCP_AUTH_TOKEN` from env; if set, require `Authorization: Bearer <token>` header. If unset, allow localhost only (bind 127.0.0.1)
> - Add `backend/mcp/README.md` with example client config snippets for Claude Desktop and Claude Code
> - Update root `README.md` to document MCP server startup
>
> **Verification:**
> - Manual: start server, hit `tools/list`, invoke `search_local_files` with a known indexed file, confirm results match `/api/files/search` REST endpoint
> - Add `backend/tests/test_mcp_server.py` with at least one happy-path test per tool using `httpx.AsyncClient`
>
> **Important:** Use `conda run -n Command pip install fastmcp` for any new deps. Update `requirements.txt` accordingly.

**Acceptance criteria:**
- [ ] `python backend/mcp_server.py` starts the server cleanly
- [ ] All 6 tools listed via reflection
- [ ] Each tool callable from a real MCP client (Claude Desktop config tested)
- [ ] No regressions in existing REST/WebSocket endpoints
- [ ] Documented in `backend/mcp/README.md`

---

## A2. Dynamic Personality System (Mood-Aware Tone Injection)

**Subagent:** `ai-developer`

**Prompt:**
> Extend `backend/core/personality.py` so the Supervisor injects mood-aware tone directives into every downstream agent's system prompt before invocation.
>
> **Flow:**
> 1. Supervisor receives a user message
> 2. Before delegating, supervisor calls `MoodAnalyst.get_current_mood(user_id)` (returns `{mood: "stressed"|"focused"|"low"|"neutral"|"excited", confidence: 0..1, recent_topics: [...]}`)
> 3. Supervisor maps mood → tone directive using a config table (YAML file at `backend/personalities/_tone_directives.yaml`)
> 4. The directive is appended to the target agent's system prompt as a "Tone & Approach" section
>
> **Files to create/modify:**
> - **New:** `backend/personalities/_tone_directives.yaml` — map of mood → directive text. Example:
>   ```yaml
>   stressed:
>     directive: "User appears stressed. Be concise, reassuring, and avoid jargon. Offer one clear next step."
>     temperature_modifier: -0.1
>   focused:
>     directive: "User is in deep-work mode. Be terse, technical, no preamble."
>     temperature_modifier: 0.0
>   low:
>     directive: "User seems low-energy. Be warm and encouraging without being saccharine."
>     temperature_modifier: 0.0
>   neutral: { directive: "", temperature_modifier: 0.0 }
>   excited:
>     directive: "User is energized. Match their pace; be specific and forward-looking."
>     temperature_modifier: 0.05
>   ```
> - **Modify:** `backend/core/personality.py` — add `inject_tone(base_prompt, mood) -> str` method on `PersonalityManager`
> - **Modify:** `backend/app/agents/supervisor.py` — call `inject_tone` on every delegation
> - **Modify:** Mood Analyst — expose `get_current_mood(user_id)` async method that reads recent journal entries (last 48h) and returns the schema above
>
> **Edge cases:**
> - Mood Analyst unavailable → fall back to `neutral` (log warning, don't block)
> - Confidence < 0.4 → use `neutral`
> - Allow user to disable via `SETTINGS.dynamic_personality_enabled` (defaults true)
>
> **Verification:** Add `backend/tests/test_dynamic_personality.py` covering: each mood produces correct directive, missing Mood Analyst falls back gracefully, disabled flag bypasses injection.

**Acceptance criteria:**
- [ ] Tone directive visible in agent system prompts (log at DEBUG level)
- [ ] Disabling via settings turns off injection cleanly
- [ ] Tests pass

---

## A3. Comprehensive Error Handling, Retry Logic, Graceful Degradation

**Subagent:** `debugger` then `code-reviewer`

**Prompt:**
> Audit every agent in `backend/app/agents/` and `backend/agents/` for error resilience. Implement a uniform retry + degradation pattern.
>
> **Standard pattern to enforce** (create `backend/core/resilience.py` with helpers):
> 1. `@with_retry(max_attempts=3, backoff="exponential", retry_on=(httpx.TimeoutException, httpx.HTTPStatusError))` decorator
> 2. `@with_fallback(fallback_fn)` decorator — runs `fallback_fn` if main fn raises after retries
> 3. Centralized `AgentError` exception hierarchy: `LLMUnavailable`, `EmbeddingUnavailable`, `ScrapeBlocked`, `RateLimited`, `InvalidInput`
> 4. All agents emit a `degraded` event (via existing event yielder) when fallbacks are taken so the UI can surface it
>
> **Specific degradation rules:**
> - **LM Studio down:** Supervisor returns a fixed "I can't reach the local model right now — start LM Studio and try again" message (don't crash the WebSocket)
> - **Embedding model unavailable:** RAG falls back to BM25-only search and emits `degraded`
> - **Scraper blocked (403/429):** Try archive.org as fallback, then skip with a logged source
> - **DuckDuckGo rate-limited:** Exponential backoff up to 60s, then surface error to user
> - **ChromaDB locked:** Retry 3x with 200ms backoff, then return empty results + `degraded` event
> - **Disk full / write fails:** Catch, log, surface to user via system notification (don't lose the in-flight conversation)
>
> **Process:**
> 1. Grep for bare `except Exception` and `except:` clauses — replace with specific exceptions
> 2. Wrap every external I/O call (LM Studio, ChromaDB, HTTPX, file I/O) with the retry decorator
> 3. Add structured logging (logger.warning with context dict) at every fallback site
> 4. Update `backend/api/websocket.py` to emit `degraded` events to the client
>
> **Verification:** Add `backend/tests/test_resilience.py` simulating each failure mode using `pytest` mocks. Run the existing test suite to confirm no regressions.

**Acceptance criteria:**
- [ ] No `except Exception:` without explicit logging in agent code
- [ ] All external I/O wrapped with retry
- [ ] `degraded` events surface in UI as a yellow banner (frontend integration in D9)
- [ ] Test suite covers each degradation path

---

## A4. Background File Watcher for Auto-Ingestion

**Subagent:** `api-developer`

**Prompt:**
> Build a background file watcher that auto-ingests new/changed files from user-configured folders.
>
> **Location:** `backend/core/file_watcher.py`
>
> **Approach:** Use `watchdog` library (cross-platform, Windows-compatible — important since user is on Windows 11). Avoid the existing `FOLDER_WATCH_INTERVAL_SECONDS` polling stub unless `watchdog` proves problematic.
>
> **Behavior:**
> - On startup (FastAPI lifespan), read watched folders from settings (`WATCHED_FOLDERS` env var, comma-separated, or DB-backed `user_settings` table)
> - Recursively watch each folder; on `created`/`modified` events for supported extensions (`.pdf .docx .md .txt .xlsx .png .jpg .jpeg`):
>   1. Debounce (5s — files often have multiple write events during save)
>   2. Compute SHA256 of file
>   3. Skip if hash already in `content_chunks` table
>   4. Enqueue ingestion via existing `app/agents/file_processor.py` pipeline
>   5. Emit a WebSocket event `file_ingested` so UI can refresh
> - Handle deletions: remove chunks from ChromaDB, mark source as `deleted` in SQLite (soft delete; user can undo within 7 days)
> - Pause during research runs (heavy I/O contention) — listen for `research_started` / `research_completed` events
>
> **Endpoints:**
> - `POST /api/folders/watch` — add a folder (validates exists, readable)
> - `DELETE /api/folders/watch/{folder_id}` — remove
> - `GET /api/folders/watch` — list
> - `GET /api/folders/watch/status` — running, queue depth, last error
>
> **Files:**
> - **New:** `backend/core/file_watcher.py`, `backend/api/routes/folders.py`
> - **Modify:** `backend/main.py` to start/stop watcher in lifespan
> - **Modify:** `backend/core/database.py` to add `watched_folders` table
>
> **Verification:** Manual test — drop a file in a watched folder, confirm it appears in Files tab within ~10 seconds.

**Acceptance criteria:**
- [ ] Files appear in vector store automatically on add
- [ ] Renames/deletes handled correctly
- [ ] Watcher does not crash on permission errors (log + skip)
- [ ] No duplicate ingestion on re-save

---

## A5. Chat History Semantic Search Endpoint

**Subagent:** `rag-expert`

**Prompt:**
> Build a semantic search endpoint over past conversations.
>
> **Location:** `backend/api/routes/chat_history.py`
>
> **Endpoint:**
> `GET /api/chat/history/search?q=<query>&top_k=20&date_from=<iso>&date_to=<iso>&conversation_id=<optional>`
>
> Returns:
> ```json
> {
>   "results": [
>     {
>       "conversation_id": "...",
>       "conversation_title": "...",
>       "message_id": "...",
>       "snippet": "...",  // ±2 messages context
>       "score": 0.87,
>       "timestamp": "...",
>       "match_type": "vector|keyword|hybrid"
>     }
>   ],
>   "total": 42
> }
> ```
>
> **Implementation:**
> - Index every assistant + user message into a dedicated ChromaDB collection `chat_messages` (run a one-time migration to backfill existing messages from `messages` table)
> - On every new message saved, also embed + index (hook into existing message persistence in `backend/core/database.py`)
> - Hybrid search: BM25 (over `messages.content`) + vector similarity, RRF-fused (reuse fusion logic from `app/agents/rag_retriever.py`)
> - Return ±2 surrounding messages as snippet context
> - Respect date filters via metadata filter on ChromaDB
>
> **Files:**
> - **New:** `backend/api/routes/chat_history.py`
> - **New:** `backend/scripts/backfill_chat_embeddings.py` (one-shot migration)
> - **Modify:** `backend/core/database.py` — hook embedding on message save
> - **Modify:** `backend/main.py` — register new router
>
> **Verification:** Backfill on existing DB, query for a known phrase, confirm correct conversation surfaces. Add `backend/tests/test_chat_history_search.py`.

**Acceptance criteria:**
- [ ] Query returns relevant messages across all past conversations
- [ ] New messages indexed automatically (no manual reindex)
- [ ] Date filters work
- [ ] <500ms p95 latency for top-20 results on 10k-message corpus

---

## A6. Obsidian-Compatible Markdown Export

**Subagent:** `api-developer`

**Prompt:**
> Build an Obsidian-compatible export service for all user-generated content (research reports, journal entries, memory facts, chat history).
>
> **Location:** `backend/core/obsidian_export.py` + `backend/api/routes/export.py`
>
> **Vault structure produced:**
> ```
> nexus-vault/
> ├── Research/
> │   └── {YYYY-MM-DD} {slug}.md    (with front-matter, [[wikilinks]] to sources)
> ├── Journal/
> │   └── {YYYY-MM-DD}.md           (daily note format Obsidian recognizes)
> ├── Memory/
> │   └── {category}/{fact-slug}.md
> ├── Conversations/
> │   └── {YYYY-MM-DD} {title}.md
> ├── Sources/
> │   └── {domain}/{slug}.md        (one note per scraped source, [[backlinked]])
> └── _meta/
>     ├── tags.json
>     └── export-manifest.json
> ```
>
> **Front-matter conventions (YAML):**
> ```yaml
> ---
> created: 2026-04-28T14:32:00
> updated: 2026-04-28T14:32:00
> type: research|journal|memory|conversation
> tags: [tag1, tag2]
> nexus_id: <uuid>
> ---
> ```
>
> **Endpoints:**
> - `POST /api/export/obsidian` — body `{scope: "all"|"research"|"journal"|"memory"|"chat", output_path: "/abs/path"}` — synchronous for small exports, returns 202 + job id for large
> - `GET /api/export/obsidian/jobs/{job_id}` — status + progress
>
> **Edge cases:**
> - Filename collisions → append `-2`, `-3`, etc.
> - Sanitize filenames (Windows-illegal chars: `<>:"/\|?*`)
> - Deduplicate source notes by URL
> - Wikilinks must point to actual generated filenames (build a slug → path map first, then render content in second pass)
>
> **Verification:** Export to a temp folder, open in Obsidian, confirm: graph view connects research → sources, daily notes appear in calendar plugin, tags pane shows extracted tags. Add `backend/tests/test_obsidian_export.py`.

**Acceptance criteria:**
- [ ] Generated vault opens in Obsidian without errors
- [ ] Wikilinks resolve (no broken refs)
- [ ] Daily notes integrate with calendar plugin
- [ ] Idempotent — re-running export updates instead of duplicating

---

# TRACK B — New Intelligence Agents

## B1. Smart Daily Briefing Agent

**Subagent:** `ai-developer`

**Prompt:**
> Build a Daily Briefing Agent that auto-generates a morning summary at a user-configurable time (default 7:00 AM).
>
> **Location:** `backend/app/agents/proactive/daily_briefing_agent.py` (extend the existing `briefing_agent.py` skeleton from Phase 6)
>
> **Briefing structure:**
> 1. **Yesterday's journal recap** — pull from journal tables, summarize via LM Studio (3–5 sentences)
> 2. **Mood trend** — last 7 days mood scores, direction arrow, notable shifts (delegate to Mood Analyst)
> 3. **Pending research** — any `running` or `pending` sessions in `research_sessions`
> 4. **New files** — count of files ingested in last 24h with top 3 by relevance
> 5. **Predictive patterns** — output from Pattern Detective (top 1–2 patterns surfaced)
> 6. **Goals progress** — from Goal Tracker (B2) if available
> 7. **Today's suggested focus** — single sentence based on calendar gaps + active research + journal themes
>
> **Personality:** YAML at `backend/personalities/proactive/daily_briefing_agent.yaml` — warm, concise, executive-summary tone (~250 words target).
>
> **Scheduling:** Use `APScheduler` (already in requirements). Cron-style schedule from settings (`DAILY_BRIEFING_CRON`, default `0 7 * * *`).
>
> **Output:**
> 1. Persist as a journal entry tagged `briefing` so it shows in journal
> 2. Send as a system notification (UI banner via WebSocket `briefing_ready` event)
> 3. Optionally email/push (skip for now, leave hook)
>
> **Endpoints:**
> - `POST /api/briefing/generate` — manual trigger (returns the briefing immediately)
> - `GET /api/briefing/latest` — today's briefing if generated
> - `GET /api/briefing/history?days=30`
>
> **Verification:** Manually trigger generation with seeded test data, confirm all 7 sections render and tone matches personality. Add unit tests for each section's data aggregation.

**Acceptance criteria:**
- [ ] Briefing generates on schedule
- [ ] All 7 sections present (or gracefully omitted if data missing)
- [ ] WebSocket notification fires
- [ ] Persisted to journal

---

## B2. Goal Tracker Agent

**Subagent:** `ai-developer`

**Prompt:**
> Build a Goal Tracker Agent that lets users set goals and auto-tracks progress from journal entries.
>
> **Location:** `backend/app/agents/proactive/goal_tracker.py`
>
> **Schema (add to `backend/core/database.py`):**
> ```sql
> CREATE TABLE goals (
>   id TEXT PRIMARY KEY,
>   user_id TEXT,
>   title TEXT NOT NULL,         -- "Read 2 books per month"
>   description TEXT,
>   metric_type TEXT,            -- count|duration|boolean|streak
>   target_value REAL,
>   target_period TEXT,          -- daily|weekly|monthly
>   start_date DATE,
>   end_date DATE,
>   status TEXT,                 -- active|paused|completed|abandoned
>   created_at DATETIME
> );
> CREATE TABLE goal_events (
>   id TEXT PRIMARY KEY,
>   goal_id TEXT,
>   detected_from TEXT,          -- journal_entry_id|manual
>   value REAL,
>   timestamp DATETIME,
>   notes TEXT,
>   confidence REAL,             -- 0..1, how sure the agent was
>   FOREIGN KEY (goal_id) REFERENCES goals(id)
> );
> ```
>
> **Auto-tracking flow:**
> 1. After every journal entry save, Goal Tracker is triggered (event-driven)
> 2. For each active goal, agent uses LM Studio with structured output to extract: `{progress_event: bool, value: number, confidence: 0..1, evidence: "quoted text"}`
> 3. If `confidence >= 0.7`, persist `goal_event` automatically; if `0.4–0.7`, mark as `pending_user_review`; if `<0.4`, ignore
>
> **Endpoints:**
> - `POST /api/goals` — create
> - `GET /api/goals` — list with computed progress
> - `PATCH /api/goals/{id}` — update / pause / complete
> - `DELETE /api/goals/{id}`
> - `GET /api/goals/{id}/events` — audit trail
> - `POST /api/goals/{id}/events` — manual event entry
> - `GET /api/goals/pending-review` — events with mid-confidence
> - `POST /api/goals/events/{event_id}/confirm`, `.../reject`
>
> **Personality:** `backend/personalities/proactive/goal_tracker.yaml` — encouraging, factual, never preachy.
>
> **Verification:** Seed a "exercise 3x/week" goal, write a journal entry mentioning a workout, confirm event auto-detected and progress percent updates.

**Acceptance criteria:**
- [ ] Goals persist
- [ ] Auto-detection works on journal entries
- [ ] Mid-confidence events surface for review
- [ ] Progress percentage computed correctly per `target_period`

---

## B3. Custom Agent Creation Framework

**Subagent:** `ai-developer` then `system-architect` review

**Prompt:**
> Let users define their own specialist agents with custom system prompts and tool access.
>
> **Location:** `backend/app/agents/custom/` + `backend/api/routes/custom_agents.py`
>
> **Schema:**
> ```sql
> CREATE TABLE custom_agents (
>   id TEXT PRIMARY KEY,
>   user_id TEXT,
>   name TEXT UNIQUE NOT NULL,
>   display_name TEXT,
>   tagline TEXT,
>   system_prompt TEXT NOT NULL,
>   allowed_tools JSON,          -- ["search_local_files", "search_web", ...]
>   parent_cluster TEXT,         -- knowledge|research|journal|memory|none
>   ui_config JSON,              -- {color, icon}
>   temperature REAL DEFAULT 0.7,
>   max_tokens INTEGER DEFAULT 2048,
>   created_at DATETIME,
>   updated_at DATETIME,
>   enabled BOOLEAN DEFAULT 1
> );
> ```
>
> **Tool access model:**
> - Whitelist approach — users pick from the same toolset MCP exposes (A1)
> - Each tool invocation is logged (`custom_agent_invocations` table) so user can audit
> - Tools that mutate state (save_memory, save_research_report) require explicit opt-in
>
> **Runtime:**
> - On supervisor delegation, custom agents are routable by name (`@my-tax-advisor`) or by intent classification (supervisor decides)
> - Custom agent runs in a sandbox: only allowed tools available, no access to other agents' state
>
> **Endpoints:**
> - `POST /api/agents/custom` — create (validates: name unique, system_prompt non-empty, allowed_tools subset of registry)
> - `GET /api/agents/custom` — list
> - `PATCH /api/agents/custom/{id}` — update
> - `DELETE /api/agents/custom/{id}` — soft delete (keeps invocation history)
> - `POST /api/agents/custom/{id}/test` — run with a sample prompt, return response without persisting
>
> **Safety:**
> - Reject system prompts that obviously try to override Nexus core behavior (heuristic check for phrases like "ignore previous instructions", "forget your role"). Surface as warning, allow user to confirm override
> - Hard limit: 20 custom agents per user
>
> **Verification:** Create a "Recipe Helper" custom agent with `search_web` and `search_local_files` tools, invoke it via chat, confirm tool restrictions enforced (can't `save_memory`).

**Acceptance criteria:**
- [ ] Users can CRUD custom agents
- [ ] Tool whitelist enforced at runtime
- [ ] Supervisor can route to custom agents
- [ ] Test endpoint works without polluting state
- [ ] Audit log of invocations queryable

---

## B4. Conflict Resolution Dialog Agent

**Subagent:** `ai-developer`

**Prompt:**
> When Memory Archivist detects contradictions between memory facts (or between a new fact and existing facts), trigger a guided resolution conversation.
>
> **Location:** `backend/app/agents/memory/conflict_resolver.py`
>
> **Detection (in Memory Archivist):**
> - On every new fact save, compare to top-10 most semantically similar existing facts
> - Use LM Studio with structured output: `{conflicts_with: [fact_id], conflict_type: "factual|temporal|preferential", explanation: "..."}`
> - If conflict detected → write to `memory_conflicts` table, status=`unresolved`
>
> **Schema:**
> ```sql
> CREATE TABLE memory_conflicts (
>   id TEXT PRIMARY KEY,
>   fact_a_id TEXT,
>   fact_b_id TEXT,
>   conflict_type TEXT,
>   explanation TEXT,
>   status TEXT,                  -- unresolved|resolved_keep_a|resolved_keep_b|resolved_merged|dismissed
>   resolution_notes TEXT,
>   detected_at DATETIME,
>   resolved_at DATETIME
> );
> ```
>
> **Resolution flow:**
> 1. UI shows a notification: "I found a possible contradiction in what I remember about you."
> 2. User clicks → opens dialog showing fact A, fact B, agent's explanation
> 3. Options: Keep A / Keep B / Merge (agent proposes merged version) / Both true (with context — adds qualifier to each) / Dismiss
> 4. Choice persisted; affected facts updated
>
> **Endpoints:**
> - `GET /api/memory/conflicts?status=unresolved`
> - `POST /api/memory/conflicts/{id}/resolve` — body: `{action: "keep_a|keep_b|merge|both|dismiss", merge_text?: string}`
> - `POST /api/memory/conflicts/{id}/propose_merge` — agent generates a merge proposal
>
> **Verification:** Seed conflicting facts ("user is vegetarian" + "user mentioned eating chicken yesterday"), confirm conflict detected, walk through resolution, confirm DB state correct after each action.

**Acceptance criteria:**
- [ ] Contradictions detected automatically
- [ ] User-facing dialog presents options clearly (UI part in Track E)
- [ ] All 5 resolution paths work and persist correctly

---

# TRACK C — Analytics & Comparisons

## C1. Focus Mode Analytics

**Subagent:** `database-expert` then `frontend-developer`

**Prompt (backend portion):**
> Build aggregation endpoints for "Focus Mode Analytics": what topics user researches most, what they journal about, blind spots in their thinking.
>
> **Location:** `backend/api/routes/analytics.py`
>
> **Endpoints:**
> - `GET /api/analytics/topics?period=30d&source=research|journal|all` — returns topic frequency: `[{topic, count, trend: "up|down|flat", first_seen, last_seen}]`
> - `GET /api/analytics/blind-spots?period=90d` — returns topics frequently encountered in research/files but never journaled about (potential blind spots)
> - `GET /api/analytics/research-velocity?period=30d` — research sessions started/completed per week
> - `GET /api/analytics/journal-themes?period=30d` — top recurring themes from journal entries (delegate to existing journal cluster topic extraction)
>
> **Implementation notes:**
> - Topic extraction: reuse existing keyword/entity extraction from journal cluster (spaCy NER + LM Studio summarization)
> - Cache results in a `analytics_snapshots` table with TTL (recompute on demand or every 6h)
> - Blind-spot logic: topic appears in research/files >= 3 times but in journal < 1 time over the period
>
> **Frontend portion:** Defer visualization to D1 (Insights tab will surface these).

**Acceptance criteria:**
- [ ] Endpoints return data within 2s on a 90-day corpus
- [ ] Blind spot detection produces meaningful, non-trivial output
- [ ] Cached results refresh appropriately

---

## C2. Snapshot Comparisons (This Month vs Last Month)

**Subagent:** `database-expert`

**Prompt:**
> Build a comparison endpoint contrasting key metrics across two periods.
>
> **Location:** `backend/api/routes/analytics.py` (extend C1's file)
>
> **Endpoint:**
> `GET /api/analytics/compare?metric=mood|productivity|topics|journal_volume|research_volume&period_a=2026-03&period_b=2026-04`
>
> Returns:
> ```json
> {
>   "metric": "mood",
>   "period_a": {"label": "March 2026", "value": 6.2, "samples": 28},
>   "period_b": {"label": "April 2026", "value": 7.1, "samples": 25},
>   "delta": 0.9,
>   "delta_pct": 14.5,
>   "direction": "up",
>   "significance": "moderate",
>   "narrative": "Mood improved meaningfully from March to April..."
> }
> ```
>
> **Metrics to support:**
> - `mood` — average daily mood score
> - `productivity` — derived from goal completion + research output
> - `topics` — Jaccard similarity of top-10 topics
> - `journal_volume` — entry count + word count
> - `research_volume` — sessions completed
> - `health` — if user logs health data (extensibility hook, even if data not yet captured)
> - `finances` — same hook
>
> **Narrative generation:** LM Studio call with the structured numbers + few-shot examples → 1–2 sentence human summary.
>
> **Verification:** Test with fixture data covering each metric type. Confirm `direction` correct for negative deltas on metrics where lower is better.

**Acceptance criteria:**
- [ ] All 5 core metrics implemented
- [ ] Narratives feel natural and accurate
- [ ] Extensibility hooks for health/finances documented

---

# TRACK D — Settings & Core UX (Frontend)

## D1. Settings Tab Shell + Models Subtab

**Subagent:** `frontend-developer`

**Prompt:**
> Build the Settings tab shell with subtab navigation and the first subtab: Models.
>
> **Files:**
> - **Modify:** `nexus-os-frontend/src/components/tabs/SettingsTab.tsx` — add subtab routing
> - **New:** `nexus-os-frontend/src/components/settings/ModelsSubtab.tsx`
> - **New:** `nexus-os-frontend/src/lib/modelsApi.ts`
>
> **Subtab navigation:** vertical tabs on left (Models / Agents / Notifications / Data & Export / Chat History — last one belongs to Chat tab actually, see E2). Use existing GlassCard styling.
>
> **Models subtab content:**
> - **LM Studio config card:**
>   - Base URL (input, default `http://localhost:1234/v1`)
>   - "Test connection" button → calls `GET /api/system/lm-studio/health` (build this endpoint too)
>   - Connection status badge (green/red dot)
> - **Available models card:**
>   - Polls `GET /api/system/lm-studio/models` every 30s
>   - Lists each loaded model with: name, context length, quantization, role assignment
>   - For each role (supervisor, embedding, vision, reranker), dropdown to pick from loaded models
>   - "Apply" button — POSTs to `/api/settings/models` and triggers backend reload
> - **Embedding model card:**
>   - Currently using BAAI/bge-m3 (display info)
>   - Toggle: re-index button (warns about cost) → triggers `POST /api/embeddings/reindex`
>
> **Backend endpoints needed (delegate to api-developer if not present):**
> - `GET /api/system/lm-studio/health`
> - `GET /api/system/lm-studio/models`
> - `GET /api/settings/models`, `POST /api/settings/models`
>
> **Visual polish:** Loading shimmers (use `react-loading-skeleton`), toast on save (`react-hot-toast` — install if not present).
>
> **Verification:** Disconnect LM Studio, confirm UI shows red status with helpful guidance.

**Acceptance criteria:**
- [ ] Subtab navigation works smoothly
- [ ] Connection test gives clear feedback
- [ ] Model assignments persist + take effect (verify by changing supervisor model and seeing different output)

---

## D2. Settings — Agents Subtab

**Subagent:** `frontend-developer`

**Prompt:**
> Build the Agents subtab in Settings. Lists all 18 agents (13 base + Daily Briefing + Goal Tracker + Conflict Resolver + Custom Agent slot + Pattern Detective).
>
> **Files:**
> - **New:** `nexus-os-frontend/src/components/settings/AgentsSubtab.tsx`
> - **New:** `nexus-os-frontend/src/lib/agentsApi.ts`
>
> **Per-agent card:**
> - Avatar (color + icon from personality config)
> - Name + tagline + cluster badge
> - Status indicator (active / idle / disabled / error)
> - Toggle: enable/disable
> - Expandable: personality tuning (show system prompt with edit-in-place; save creates a user override that persists in DB, not the YAML)
> - Stats: invocations last 7d, avg latency, error rate (from `agent_telemetry` table — build if missing)
> - "Test agent" button — quick prompt input, shows response inline
>
> **Filters at top:**
> - By cluster (Knowledge / Research / Journal / Memory / Proactive / Custom)
> - By status (Active / Disabled / Error)
> - Search by name
>
> **Custom agents section:** Separate area at the bottom with "+ New Custom Agent" CTA (opens form modal — build the form here, hooks to B3 endpoints).
>
> **Endpoints needed:**
> - `GET /api/agents` — list with status + stats
> - `PATCH /api/agents/{name}` — update enabled, system_prompt_override
> - `POST /api/agents/{name}/test` — body `{prompt}`, returns response
>
> **Verification:** Disable Pattern Detective, confirm it doesn't run. Override supervisor system prompt, confirm new prompt takes effect on next message.

**Acceptance criteria:**
- [ ] All agents listed
- [ ] Toggle works without backend restart
- [ ] System prompt overrides persist across restarts
- [ ] Custom agent creation form integrated

---

## D3. Settings — Notifications Subtab

**Subagent:** `frontend-developer`

**Prompt:**
> Build the Notifications subtab.
>
> **File:** `nexus-os-frontend/src/components/settings/NotificationsSubtab.tsx`
>
> **Sections:**
> 1. **Daily Briefing**
>    - Enable toggle
>    - Time picker (default 7:00 AM)
>    - Day selector (weekdays only / every day / weekends only)
>    - Channels: in-app banner, system tray (skip), email (skip — placeholder)
> 2. **Pattern Alerts**
>    - Enable toggle
>    - Threshold slider: confidence min (0.5–1.0)
>    - Categories to alert on (mood shifts, recurring topics, goal-related)
> 3. **Memory Conflicts**
>    - Enable toggle
>    - Auto-resolve safe conflicts (low confidence dismiss): toggle
> 4. **Research Completion**
>    - Notify when research session finishes: toggle
> 5. **System Alerts**
>    - LM Studio disconnect: always on (greyed)
>    - Disk space low: toggle
>    - Embedding model OOM: toggle
>
> **Endpoints:**
> - `GET /api/settings/notifications`, `PUT /api/settings/notifications`
> - Backend stores in a `user_settings` table with JSON value
>
> **Verification:** Change briefing time to 5 minutes from now, confirm it fires.

**Acceptance criteria:**
- [ ] All toggles persist
- [ ] Daily briefing schedule respected
- [ ] System alerts fire when triggered

---

## D4. Settings — Data & Export Subtab

**Subagent:** `frontend-developer`

**Prompt:**
> Build the Data & Export subtab — covers Obsidian export (A6), backup/restore, data deletion.
>
> **File:** `nexus-os-frontend/src/components/settings/DataExportSubtab.tsx`
>
> **Sections:**
> 1. **Obsidian Export** (powered by A6 endpoints)
>    - Scope selector: All / Research / Journal / Memory / Chat
>    - Output folder picker (use HTML5 directory input or path input — Windows-aware)
>    - "Export now" button → kicks off job, shows progress bar (poll job status)
>    - History list: recent exports with timestamp + folder + status
> 2. **Bi-directional Obsidian Sync** (E3 placeholder card here, "Configure" CTA → opens E3 wizard)
> 3. **Backup**
>    - Full backup (zip of `data/` folder excluding `embeddings/`) → endpoint `POST /api/backup` returns download URL
>    - Schedule: enable + cron picker, target folder
>    - Last backup info
> 4. **Restore**
>    - File picker for backup zip → `POST /api/restore` (requires confirmation modal — destructive)
> 5. **Data Deletion**
>    - "Delete chat history" / "Delete journal" / "Delete memory" / "Delete research" — each requires double-confirm
>    - "Reset everything" — triple-confirm, types literal `DELETE EVERYTHING`
>
> **Backend endpoints needed:**
> - `POST /api/backup` (zip + return blob)
> - `POST /api/restore` (multipart upload)
> - `DELETE /api/data/{scope}` where scope ∈ `chat|journal|memory|research|all`
>
> **Verification:** Backup → wipe → restore → confirm everything intact.

**Acceptance criteria:**
- [ ] Obsidian export integrated
- [ ] Backup/restore round-trips cleanly
- [ ] Destructive actions require explicit confirmation
- [ ] Scheduled backups run

---

## D5. Onboarding Flow

**Subagent:** `frontend-developer`

**Prompt:**
> Build a first-run onboarding flow. Triggers when `localStorage["nexus.onboarded"]` is unset OR `GET /api/onboarding/status` returns `complete: false`.
>
> **File:** `nexus-os-frontend/src/components/onboarding/OnboardingFlow.tsx` + step components in `onboarding/steps/`
>
> **Steps (full-screen modal with progress bar):**
> 1. **Welcome** — branding, "Nexus is your local AI workspace. Everything stays on your machine."
> 2. **LM Studio Setup**
>    - Detect: ping `http://localhost:1234/v1/models`
>    - If reachable: show "✓ LM Studio detected, X models loaded" + recommended model picks
>    - If not: instructions with a screenshot, "Re-check" button
>    - "Recommended models": list with download size, role
> 3. **File Folders** — let user pick folders to watch (calls A4 endpoints). At least one optional. Show example use cases.
> 4. **Journal Preferences** — opt in/out of journal cluster; pick reminder time; pick mood tracking style (1–10 scale / emoji / both)
> 5. **Daily Briefing** — opt in, pick time
> 6. **Privacy Confirmation** — explicit checkbox: "I understand all data stays on this machine. Nexus makes no external network calls except to user-approved sources."
> 7. **Done** — "You're all set. Try asking the supervisor anything."
>
> **State:** Use Zustand store `useOnboardingStore` to persist progress mid-flow (in case user closes tab).
>
> **Backend:**
> - `GET /api/onboarding/status` — completed steps, current step
> - `POST /api/onboarding/complete-step` — `{step_id, payload}`
> - `POST /api/onboarding/finish`
>
> **Skip option:** "Skip onboarding" link (small, secondary) at bottom of step 1 — sets all defaults.
>
> **Verification:** Fresh install simulation (clear localStorage + reset DB), walk through all steps, confirm settings actually applied.

**Acceptance criteria:**
- [ ] Flow appears on first run only
- [ ] Resumable if interrupted
- [ ] All chosen preferences applied
- [ ] Skip path uses sensible defaults

---

## D6. Keyboard Shortcuts System

**Subagent:** `frontend-developer`

**Prompt:**
> Implement a global keyboard shortcuts system.
>
> **File:** `nexus-os-frontend/src/hooks/useKeyboardShortcuts.ts` + `nexus-os-frontend/src/lib/shortcuts.ts`
>
> **Approach:** Use `mousetrap` or write a thin custom hook. Mac vs Windows: detect `navigator.platform` and use `Cmd` on Mac, `Ctrl` on Windows. Display labels accordingly.
>
> **Shortcuts:**
> - `Cmd/Ctrl+K` — Global search overlay (D7)
> - `Cmd/Ctrl+J` — Jump to journal tab + open new entry
> - `Cmd/Ctrl+N` — New chat conversation
> - `Cmd/Ctrl+/` — Show shortcuts help overlay
> - `Cmd/Ctrl+,` — Settings tab
> - `Cmd/Ctrl+R` — Research tab → new research (override browser refresh: use `Cmd+Shift+R` for refresh)
> - `Cmd/Ctrl+1–7` — Jump to tab N
> - `Esc` — Close any open modal/overlay
> - `?` — Show shortcuts help (when not in an input)
>
> **Constraints:**
> - Disable when user is typing in input/textarea/contenteditable
> - Allow user to customize via Settings (defer to a v2; for now, ship defaults)
>
> **Help overlay:**
> - Component `ShortcutsHelp.tsx` — modal listing all shortcuts with their actions
> - Keyboard-hint badges throughout UI (e.g., "Search ⌘K" in nav bar)
>
> **Verification:** Try every shortcut from every tab, confirm no conflicts with browser shortcuts on Chrome/Firefox/Edge on Windows.

**Acceptance criteria:**
- [ ] All shortcuts work consistently
- [ ] Help overlay accessible
- [ ] No interference with text input
- [ ] Mac/Windows label correct

---

## D7. Global Search Overlay (Cmd+K)

**Subagent:** `frontend-developer` + `rag-expert`

**Prompt:**
> Build a unified global search overlay (Cmd+K) that searches across files, research reports, journal entries, memory facts, and chat history.
>
> **File:** `nexus-os-frontend/src/components/search/GlobalSearch.tsx`
>
> **UX:** Spotlight-style modal centered, with input at top, grouped results below. Fuzzy matching client-side for snappy feel + server-side semantic search for deeper matches.
>
> **Result groups (in this order):**
> - Quick actions ("Start research on...", "New journal entry", "Settings → Models")
> - Conversations (chat history search — A5)
> - Files
> - Research reports
> - Journal entries
> - Memory facts
> - Custom agents
>
> Each result row: icon, title, snippet, source label, score. Arrow keys to navigate, Enter to open, Cmd+Enter to open in new context.
>
> **Backend endpoint:** `GET /api/search/global?q=<query>&limit=20` — fans out to: files RAG, chat history (A5), research title search, journal full-text + semantic, memory full-text + semantic. Returns ranked, grouped results.
>
> **Implementation:**
> - Debounce input 200ms
> - Show recent searches when input empty (localStorage)
> - Keyboard nav: ↑↓ to move, Enter, Cmd+Enter, Esc
> - Loading state with shimmer
>
> **Verification:** Type "stress" — confirm matches appear from journal, chat, and any related research reports.

**Acceptance criteria:**
- [ ] <300ms perceived latency for top results
- [ ] All 5 sources searched
- [ ] Keyboard nav fully functional
- [ ] Recent searches persist

---

## D8. Mobile-Responsive Design Pass

**Subagent:** `frontend-developer`

**Prompt:**
> Audit every tab/subtab for mobile responsiveness (≥375px width). The 3D orbs and dashboard panels are the highest-risk areas.
>
> **Approach:**
> 1. Walk through every tab at 375px, 768px, 1024px, 1440px in DevTools
> 2. For each issue found, fix in the component file
>
> **Specific concerns:**
> - **Sidebar** — collapses to bottom nav on <768px (icon-only, ~5 primary tabs)
> - **AgentActivityPanel** — collapsible drawer on mobile
> - **3D scenes (HeroOrb, ParticleField, Agent Network Visualizer)** — reduce particle count, lower DPR (`gl={{ pixelRatio: window.devicePixelRatio < 2 ? 1 : 1.5 }}`), or fall back to 2D static image on `<lg` if perf bad
> - **Charts (Recharts)** — set `ResponsiveContainer` on every chart; verify legends don't overflow
> - **Settings subtabs** — vertical tabs become accordion on mobile
> - **Global search** — full-screen on mobile
> - **Onboarding** — single-column on mobile
> - **Tables (memory facts, goals, source manager)** — convert to cards on mobile
>
> **Touch targets:** Minimum 44×44px for buttons.
>
> **Test:** Use Chrome DevTools device toolbar + a real phone if available.
>
> **Deliverable:** A PR with checked-off audit list (one bullet per tab) and screenshots before/after for the trickiest fixes.

**Acceptance criteria:**
- [ ] Every tab usable on a 375px-wide viewport
- [ ] No horizontal scroll on body
- [ ] Touch targets meet minimum
- [ ] 3D scenes don't tank perf on mid-range mobile

---

## D9. Micro-interactions Polish

**Subagent:** `frontend-developer`

**Prompt:**
> Final UX polish pass: toasts, shimmers, hover effects, transitions.
>
> **Install:** `react-hot-toast` (if not present), `react-loading-skeleton`.
>
> **Toasts (`react-hot-toast`):**
> - Success: file uploaded, settings saved, export complete, conversation saved
> - Error: LM Studio unreachable, embed failed, scrape blocked
> - Info: research started, briefing ready, conflict detected
> - Custom toast for `degraded` events (yellow, persistent until dismissed) from A3
>
> **Loading shimmers:**
> - Replace bare spinners on Files list, Research reports list, Memory grid, Chat history search results
> - Skeleton matches final layout shape (avoid layout shift)
>
> **Hover/Focus polish:**
> - Glass cards: subtle scale (1.01) + glow on hover
> - Buttons: pressed-down state (`active:scale-95`)
> - Tab transitions: 150ms ease
>
> **Page transitions:**
> - Tab switches: cross-fade via Framer Motion (already installed) — 200ms
> - Modal open/close: slide-up + backdrop fade
>
> **Empty states:**
> - Every list view (Files, Research, Memory, Goals, Custom Agents, Conflicts) needs an illustrated empty state with a clear CTA
>
> **Accessibility check:**
> - Focus rings visible on all interactive elements
> - `prefers-reduced-motion` honored — disable Framer animations under this query
>
> **Verification:** Use the app for 10 minutes; nothing should feel jarring. Review against existing component library — keep style consistent.

**Acceptance criteria:**
- [ ] Toasts fire on relevant actions
- [ ] No bare spinners (all replaced with shimmers where appropriate)
- [ ] Empty states present everywhere
- [ ] Reduced-motion preference respected

---

# TRACK E — Visualization & History

## E1. Agent Network Visualizer

**Subagent:** `frontend-developer` (3D specialty)

**Prompt:**
> Build a real-time 3D visualization showing which agents are talking to each other during a task.
>
> **File:** `nexus-os-frontend/src/components/three/AgentNetwork.tsx` + `AgentNetworkPanel.tsx` (the chrome around it)
>
> **Visualization (React Three Fiber):**
> - Nodes: one per agent, sized by activity, colored by cluster (matches personality YAML colors)
> - Layout: force-directed (use `d3-force-3d` or simple custom physics) with cluster grouping (knowledge cluster left, research right, journal bottom, etc.)
> - Edges: animated particle streams along edges when agents communicate (use `THREE.Points` or shader-based instancing)
> - Edge intensity scales with message volume in last 30s
> - Active agents pulse; idle agents dim
> - Click a node → side panel with: agent name, last 5 invocations, current state, "View logs" link
>
> **Data source:**
> - Subscribe to a new WebSocket channel `/ws/agent-network` (build endpoint in backend)
> - Backend emits `agent_message` events: `{from: "supervisor", to: "research_lead", message_type: "delegate", timestamp}` whenever agents communicate
>
> **Backend hook (api-developer):**
> - Add a thin event emitter in `backend/core/event_bus.py` (in-process, broadcast to all subscribers)
> - Every agent invocation publishes `agent_message` events
> - WebSocket route `backend/api/ws/agent_network.py` subscribes and forwards to clients
>
> **Performance:**
> - Cap particle count (5000)
> - Throttle updates to 30fps
> - Disable scene when not visible (Intersection Observer)
>
> **UX:**
> - Toggle: "Show live" / "Replay last task"
> - Time scrubber for replay (skip if too complex; v2)
> - Legend with cluster colors
> - Fullscreen button
>
> **Where it lives:** New panel accessible from Dashboard tab + linked from each agent's card in D2.
>
> **Verification:** Trigger a research task, watch nodes light up sequentially supervisor → research_lead → web_scout → scraper → fact_checker → report_builder.

**Acceptance criteria:**
- [ ] 30fps with 18 nodes + 50 edges
- [ ] Real-time updates with <500ms lag
- [ ] Click-to-inspect works
- [ ] No memory leaks on long sessions

---

## E2. Chat History Subtab

**Subagent:** `frontend-developer`

**Prompt:**
> Build the searchable Chat History subtab inside the Chat tab.
>
> **File:** `nexus-os-frontend/src/components/chat/ChatHistorySubtab.tsx`
>
> **Layout:**
> - Left: conversation list (paginated, sorted by recency, with title + preview + date)
> - Right: selected conversation full transcript
> - Top: search bar (powered by A5)
>
> **Features:**
> - Search across all messages (calls `/api/chat/history/search`)
> - Filter by date range, agent involved
> - Click a result snippet → opens conversation, scrolls to + highlights matched message
> - Bulk actions: archive, delete, export selected (download as MD)
> - Pin a conversation (sticky at top)
> - Rename conversation inline
>
> **Performance:**
> - Virtualize the message list (use `@tanstack/react-virtual`) for long conversations
> - Lazy-load conversations on scroll in the list
>
> **Verification:** With 100+ conversations, search latency feels instant; scrolling smooth.

**Acceptance criteria:**
- [ ] Search across all conversations
- [ ] Click-to-jump highlights message
- [ ] Bulk actions work
- [ ] Performance OK on 100+ conversations / 5000 messages

---

## E3. Obsidian Bi-directional Sync

**Subagent:** `api-developer` + `frontend-developer`

**Prompt:**
> Build bi-directional sync with an Obsidian vault — not just one-way export.
>
> **Approach:** File-based sync (no Obsidian plugin needed). Use the same vault structure as A6.
>
> **Backend:** `backend/core/obsidian_sync.py`
> - Watch the vault folder (reuse A4's watchdog infrastructure)
> - On Obsidian-side changes:
>   - Modified `.md` file → parse front-matter, find `nexus_id`, update corresponding record in DB (chat / journal / memory / research)
>   - New file in vault folder → import as journal entry (if in `Journal/`) or memory fact (if in `Memory/`)
>   - Deleted file → soft-delete corresponding record
> - On Nexus-side changes:
>   - Re-export incrementally (only changed records since last sync)
> - Conflict resolution: last-write-wins by default; if both changed within 5s of each other, surface conflict to user
>
> **Sync metadata:**
> - Table `sync_state`: `{nexus_id, vault_path, last_synced_at, last_local_hash, last_remote_hash}`
> - Each sync run is logged in `sync_runs` (start/end, files added/modified/deleted, conflicts)
>
> **Endpoints:**
> - `POST /api/sync/obsidian/configure` — set vault path, sync interval
> - `POST /api/sync/obsidian/run` — manual trigger
> - `GET /api/sync/obsidian/status` — last run, queue, conflicts
> - `GET /api/sync/obsidian/conflicts`, `POST /.../resolve`
>
> **Frontend:** Wizard inside Settings → Data & Export (D4) opens this:
> - Step 1: Pick vault path
> - Step 2: Choose what to sync (toggles per content type)
> - Step 3: Pick conflict strategy
> - Step 4: Initial sync (progress bar)
>
> **Safety:**
> - First sync requires explicit "I have a backup" confirmation
> - Dry-run mode shows what would change without applying
>
> **Verification:** Edit a journal note in Obsidian, save, confirm Nexus picks up change within 10s. Edit same note in Nexus, confirm vault file updates.

**Acceptance criteria:**
- [ ] Bidirectional changes propagate
- [ ] Conflicts surfaced and resolvable
- [ ] No data loss in stress test (rapid edits both sides)
- [ ] Sync runs logged

---

# TRACK F — Integration & Hardening

## F1. End-to-End Integration Testing

**Subagent:** `test-engineer`

**Prompt:**
> Build an E2E test suite covering the critical user journeys post-Phase-7.
>
> **Stack:** Playwright for frontend E2E (since it pairs well with Next.js); pytest for backend integration.
>
> **Critical journeys to cover:**
> 1. **First-run onboarding** → finishes successfully, settings persisted
> 2. **Send a message → get streaming response** with LM Studio mock
> 3. **Upload a file → file appears in Files tab → searchable via Cmd+K**
> 4. **Start a research session → completes → report viewable → exported to Obsidian**
> 5. **Create a journal entry → mood detected → goal progress updated → daily briefing reflects it**
> 6. **Memory conflict → resolution dialog → resolved correctly**
> 7. **Custom agent created → invokable in chat → respects tool whitelist**
> 8. **Cmd+K → search returns results across all sources**
> 9. **Settings → change supervisor model → next response uses new model**
> 10. **Backup → wipe → restore** → all data intact
>
> **MCP server:** Add a test invoking each tool from a mock MCP client.
>
> **CI:** Add a `make e2e` target. Document expected runtime (likely 5–10 min full suite).
>
> **Mocks:**
> - Mock LM Studio with a deterministic response server (already exists? Build a fixture if not)
> - Mock DuckDuckGo to avoid network flakiness
>
> **Deliverable:** All 10 journeys passing in CI.

**Acceptance criteria:**
- [ ] All 10 journeys covered
- [ ] CI runs reliably (<5% flake rate)
- [ ] Mocks deterministic
- [ ] Documented how to run locally

---

## F2. Production Hardening & Release

**Subagent:** `devops-engineer` + `security-auditor`

**Prompt:**
> Final hardening before declaring Phase 7 / v1.0 complete.
>
> **Security audit (security-auditor):**
> - Pen-test the WebSocket: malformed frames, oversized payloads, auth bypass attempts
> - MCP server: confirm localhost-only binding when no token; token comparison is constant-time
> - File upload: validate MIME types, scan for path traversal, enforce size limits (`MAX_UPLOAD_SIZE`)
> - Custom agents: confirm system prompt injection guards work (B3)
> - SQL injection scan via `sqlmap`-style prompts to all endpoints
> - Secrets check: no API keys, tokens, or local paths in repo or logs
> - Dependency audit: `pip-audit` and `npm audit`, document any known issues
>
> **Performance audit (devops-engineer):**
> - Load test WebSocket: 50 concurrent chats with streaming
> - Profile memory under sustained use (24h soak test on a typical workload)
> - Benchmark: cold start to first chat response, file ingestion throughput, research session duration
> - Profile DB query plans for slow queries; add indices where needed
> - Frontend: Lighthouse scores ≥90 on each tab (perf, a11y, best practices)
>
> **Deployment:**
> - Docker compose file for self-hosted single-machine deploy: `docker-compose.yml` covering backend + frontend + redis (optional)
> - Update root `README.md` with: architecture diagram, getting started, system requirements, FAQ
> - Build a `CHANGELOG.md` documenting v1.0 features
> - Versioning: tag `v1.0.0`
>
> **Documentation:**
> - User guide (`docs/user-guide.md`): every feature with screenshots
> - Operator guide (`docs/operator-guide.md`): backup, restore, troubleshooting
> - API reference auto-generated from FastAPI OpenAPI
> - MCP integration guide (already in A1 deliverables)
>
> **Pre-release checklist:**
> - [ ] All Phase 1–7 tests pass
> - [ ] No `TODO` / `FIXME` in critical paths
> - [ ] All `.env.example` keys documented
> - [ ] Cold start <30s on reference hardware
> - [ ] Memory stable over 24h soak
> - [ ] Lighthouse ≥90 across the board
> - [ ] No high/critical security findings unaddressed
>
> **Deliverable:** Tagged `v1.0.0` with release notes.

**Acceptance criteria:**
- [ ] Security audit findings triaged (fixed or documented)
- [ ] Perf benchmarks within targets
- [ ] Documentation complete
- [ ] Docker deploy works on a fresh machine

---

# Dependency Graph

```
A1 (MCP) ──────────────┐
A2 (Personality) ──────┤
A3 (Resilience) ───────┼──→ D2 (Agents subtab)
A4 (Watcher) ──────────┴──→ D5 (Onboarding folders step)
A5 (Chat search) ──────────→ D7 (Cmd+K) + E2 (History)
A6 (Obsidian) ─────────────→ D4 (Data & Export) + E3 (Sync)

B1 (Briefing) ─→ D3 (Notifications) + Dashboard widget
B2 (Goals) ───→ Insights tab additions
B3 (Custom agents) ─→ D2 (Agents subtab) + B3 form
B4 (Conflicts) ─→ Memory tab dialog UI

C1 + C2 ──→ Insights tab additions

D1 → D2 → D3 → D4 (Settings shell first)
D5 (Onboarding) — parallel to D1–D4
D6 (Shortcuts) → D7 (Cmd+K)
D8 (Mobile) — last in Track D
D9 (Polish) — last in Track D

E1 (Network viz) — depends on backend event bus from A3
E2 (Chat history) — depends on A5
E3 (Obsidian sync) — depends on A6 + A4

F1, F2 — final
```

**Suggested execution order (rough):**

Week 17:
1. A1 + A2 + A3 in parallel (3 backend agents) → A4 → A5 → A6
2. B1 + B2 in parallel
3. D1 → D2 → D3 → D4 (Settings as core spine)

Week 18:
4. B3 + B4 + C1 + C2 in parallel
5. D5 + D6 + D7 in parallel → D8 → D9
6. E1 + E2 + E3 in parallel
7. F1 → F2

---

# Phase 7 Deliverable Recap

When all 24 subtasks ship:

- **18 agents** across 4 clusters (+ proactive cluster + custom)
- **7 tabs** with **25+ subtabs**
- **MCP server** with 6 tools + custom agent extensibility
- **Daily briefings**, **goal tracking**, **focus analytics**, **snapshot comparisons**
- **Conflict resolution dialogs** for memory contradictions
- **Bi-directional Obsidian sync**
- **Global Cmd+K search** across all data
- **Mobile-responsive**, **keyboard-driven**, **animated agent network**
- **Zero cloud dependencies** — every byte local
- **Production-ready**: tested, hardened, documented, dockerized
