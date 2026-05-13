# PHASE 4, 5, 6 — Detailed Subtasks

**Project:** NEXUS OS
**Scope:** Journal & Life Cluster → Memory & Cross-Agent Intelligence → Proactive Intelligence Engine
**Timeline:** Week 9–16
**Status:** `planned`

---

## Table of Contents

- [Context & Assumptions](#context--assumptions)
- [Shared Cross-Phase Infrastructure](#shared-cross-phase-infrastructure)
- [PHASE 4 — Journal & Life Cluster + First Charts (Week 9–12)](#phase-4--journal--life-cluster--first-charts-week-912)
  - [4.1 Goal & Deliverable](#41-goal--deliverable)
  - [4.2 Architecture Overview](#42-architecture-overview)
  - [4.3 Dependencies](#43-dependencies)
  - [4.4 Config Updates](#44-config-updates)
  - [4.5 Data Directory & DB Schema](#45-data-directory--db-schema)
  - [4.6 Backend — Agent Personalities](#46-backend--agent-personalities)
  - [4.7 Backend — Agent Implementations](#47-backend--agent-implementations)
  - [4.8 Backend — ChartPayload Contract](#48-backend--chartpayload-contract)
  - [4.9 Backend — API Endpoints](#49-backend--api-endpoints)
  - [4.10 Backend — A2A & Supervisor Wiring](#410-backend--a2a--supervisor-wiring)
  - [4.11 Frontend — State, Types & API Client](#411-frontend--state-types--api-client)
  - [4.12 Frontend — Journal Tab](#412-frontend--journal-tab)
  - [4.13 Frontend — Dashboard Tab](#413-frontend--dashboard-tab)
  - [4.14 Testing Checklist](#414-testing-checklist)
  - [4.15 Acceptance Criteria](#415-acceptance-criteria)
  - [4.16 Week-by-Week Breakdown](#416-week-by-week-breakdown)
- [PHASE 5 — Memory System + Cross-Agent Intelligence (Week 13–14)](#phase-5--memory-system--cross-agent-intelligence-week-1314)
  - [5.1 Goal & Deliverable](#51-goal--deliverable)
  - [5.2 Architecture Overview](#52-architecture-overview)
  - [5.3 Dependencies & Config](#53-dependencies--config)
  - [5.4 Memory Data Model](#54-memory-data-model)
  - [5.5 Backend — Memory Archivist Agent](#55-backend--memory-archivist-agent)
  - [5.6 Backend — A2A Contract: MEMORY_STORE / MEMORY_QUERY](#56-backend--a2a-contract-memory_store--memory_query)
  - [5.7 Backend — Cross-Domain Search](#57-backend--cross-domain-search)
  - [5.8 Backend — API Endpoints](#58-backend--api-endpoints)
  - [5.9 Frontend — Memory Tab](#59-frontend--memory-tab)
  - [5.10 Testing Checklist](#510-testing-checklist)
  - [5.11 Acceptance Criteria](#511-acceptance-criteria)
  - [5.12 Week-by-Week Breakdown](#512-week-by-week-breakdown)
- [PHASE 6 — Proactive Intelligence Engine (Week 15–16)](#phase-6--proactive-intelligence-engine-week-1516)
  - [6.1 Goal & Deliverable](#61-goal--deliverable)
  - [6.2 Architecture Overview](#62-architecture-overview)
  - [6.3 Dependencies & Config](#63-dependencies--config)
  - [6.4 Scheduler Design](#64-scheduler-design)
  - [6.5 Backend — Agent Personalities](#65-backend--agent-personalities)
  - [6.6 Backend — Agent Implementations](#66-backend--agent-implementations)
  - [6.7 Backend — Notifications Storage & Push](#67-backend--notifications-storage--push)
  - [6.8 Backend — API Endpoints](#68-backend--api-endpoints)
  - [6.9 Frontend — Insights Tab & Notifications](#69-frontend--insights-tab--notifications)
  - [6.10 Testing Checklist](#610-testing-checklist)
  - [6.11 Acceptance Criteria](#611-acceptance-criteria)
  - [6.12 Week-by-Week Breakdown](#612-week-by-week-breakdown)
- [Cross-Phase Risks & Mitigations](#cross-phase-risks--mitigations)

---

## Context & Assumptions

The project is a local-first Python/FastAPI backend + Next.js frontend. Phase 1–3 delivered:

- Command Center (Phase 1) — `backend/main.py`, `backend/api/websocket.py`, `backend/agents/supervisor.py`
- Knowledge Cluster (Phase 2) — ChromaDB via `backend/db/vector_store.py`, HF embeddings via `backend/core/hf_embeddings.py`
- Research Cluster (Phase 3) — Research Lead + 4 specialist agents under `backend/agents/`, personalities in `backend/personalities/`, reports in `data/deep_research/{slug}/`

Phase 4–6 builds on:

- **LM Studio** is the local LLM provider (OpenAI-compatible API at `http://localhost:1234/v1`).
- **ChromaDB** collections exist with the prefix `nexus_` and HF-embedded content.
- **LangGraph** is the orchestration framework for the Supervisor.
- **A2A message bus** stub exists in `backend/core/message_bus.py` (Redis-backed, optional).
- **Personalities** are YAML files in `backend/personalities/`.
- All Python installs in this repo use `conda run -n Command pip install ...`.

Phases 4–6 add three new clusters, each sharing conventions: agents live in `backend/agents/<domain>/`, personalities in `backend/personalities/`, REST routers in `backend/api/routes/<domain>.py`, SQLite migrations in `backend/core/database.py`, and frontend tabs under `nexus-os-frontend/src/components/tabs/`.

---

## Shared Cross-Phase Infrastructure

These deliverables are referenced by multiple phases and should be built once, first touched in Phase 4.

1. **A2A message contract v2.** Extend `backend/core/message_bus.py` to carry typed envelopes:

   ```python
   class A2AMessage(BaseModel):
       msg_id: str
       from_agent: str
       to_agent: str
       action: Literal["MEMORY_STORE", "MEMORY_QUERY", "FACT_EXTRACT",
                       "CHART_REQUEST", "INSIGHT_PUSH", "CONTEXT_FETCH"]
       payload: dict
       correlation_id: str | None
       ts: datetime
   ```

   Persist all messages to a new SQLite table `a2a_messages` for debugging.

2. **Unified ChartPayload schema** (see §4.8) — all visualization-producing agents emit this.

3. **Agent registry**. Create `backend/agents/registry.py` with a dict that maps `agent_name → class` so Supervisor/Leads can instantiate specialists dynamically without hard imports.

4. **New SQLite tables (forward-declared, added per phase):**
   - Phase 4: `journal_entries`, `mood_scores`, `life_facts`, `relationships`, `interactions`, `decisions`
   - Phase 5: `memory_records`, `memory_conflicts`, `memory_links`
   - Phase 6: `insights`, `briefings`, `scheduled_jobs`

---

# PHASE 4 — Journal & Life Cluster + First Charts (Week 9–12)

## 4.1 Goal & Deliverable

User writes: *"Today I had a tough meeting with Priya. I'm frustrated but relieved it's over."*

Expected outcome:

1. Entry is saved and classified with mood = 4/10, tags = `["frustration", "relief"]`.
2. Person `Priya` is auto-extracted, interaction logged with sentiment = negative.
3. Life fact extracted: *"User has regular meetings with Priya"*.
4. A chart in the Dashboard updates: mood line crossing today's point, relationship graph adds/updates the Priya edge with sentiment color.
5. User asks *"How has my mood been?"* → Supervisor routes to Journal Lead → Mood Analyst → Chart in Dashboard + text response in Chat.
6. User asks *"Should I take this job?"* → Life Decisions Agent pulls research reports + journal entries + relationships → weighted pros/cons presentation.

## 4.2 Architecture Overview

```
Supervisor (Nexus)
  └── Journal Lead (Tier 2 Domain Lead — "Journal")
        ├── Mood Analyst          → classify mood, emotion tags, trends, ChartPayload
        ├── Psychology Agent      → behavioral patterns (7d/30d/90d sliding window)
        ├── Relationship Finder   → NER, sentiment per person, frequency, isolation
        └── Life Decisions Agent  → multi-source decision framework (A2A to Memory, Research)

A2A:
  Journal agents ──MEMORY_STORE──> Memory Archivist (Phase 5 stub in Phase 4)
  Life Decisions ──CONTEXT_FETCH──> Research + Memory + Journal

REST:
  POST   /api/journal                 — create entry
  GET    /api/journal                 — list entries (paginated, date filter)
  GET    /api/journal/{id}            — single entry with mood + facts
  DELETE /api/journal/{id}
  GET    /api/journal/mood/trend      — ChartPayload for mood over time
  GET    /api/journal/insights        — psychology-generated insight cards
  GET    /api/journal/relationships   — graph nodes + edges
  POST   /api/journal/decisions       — start decision analysis
  GET    /api/journal/decisions/{id}  — result of decision analysis
  GET    /api/journal/decisions       — decisions log

WS events:
  journal.saved, mood.computed, insight.generated, decision.progress, chart.update
```

## 4.3 Dependencies

### 4.3.1 Python (add to `backend/requirements.txt`)

```
spacy>=3.7.0                     # NER for Relationship Finder
https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1-tar.gz
vaderSentiment>=3.3.2            # fast sentiment per person mention
python-dateutil>=2.9.0           # already present — verify
networkx>=3.2                    # relationship graph math
```

Install:

```bash
conda run -n Command pip install spacy vaderSentiment networkx
conda run -n Command python -m spacy download en_core_web_sm
```

### 4.3.2 Node.js (add to `nexus-os-frontend/package.json`)

```json
"recharts": "^2.12.7",
"react-calendar-heatmap": "^1.9.0",
"d3-force": "^3.0.0",
"react-force-graph-2d": "^1.25.0",
"@types/react-calendar-heatmap": "^1.6.7",
"date-fns": "^3.6.0",
"@tiptap/react": "^2.4.0",
"@tiptap/starter-kit": "^2.4.0"
```

Install:

```bash
cd nexus-os-frontend
npm install recharts react-calendar-heatmap d3-force react-force-graph-2d date-fns @tiptap/react @tiptap/starter-kit @types/react-calendar-heatmap
```

## 4.4 Config Updates

**File:** `backend/config.py` — add to `Settings`:

```python
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
```

Add to `validate_settings()`:

```python
settings.JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
```

Update `PHASE_STATUS`:

```python
"phase_4": {"name": "Life OS", "status": "active", "weeks": "9-12"},
```

## 4.5 Data Directory & DB Schema

### 4.5.1 Directory layout

```
data/
└── journal/
    └── {YYYY}/{MM}/
        └── {entry_id}.md         # raw markdown body (versionable)
```

### 4.5.2 SQLite tables (add to `backend/core/database.py`)

```sql
CREATE TABLE journal_entries (
  id TEXT PRIMARY KEY,
  created_at TIMESTAMP NOT NULL,
  body_md TEXT NOT NULL,           -- source of truth for the entry text
  word_count INTEGER,
  title TEXT,
  tags TEXT                        -- JSON array
);

CREATE TABLE mood_scores (
  entry_id TEXT PRIMARY KEY REFERENCES journal_entries(id) ON DELETE CASCADE,
  score INTEGER NOT NULL CHECK (score BETWEEN 1 AND 10),
  emotions TEXT NOT NULL,          -- JSON array: ["frustration","relief"]
  confidence REAL,
  model TEXT,
  computed_at TIMESTAMP
);
CREATE INDEX idx_mood_entry_date ON mood_scores(computed_at);

CREATE TABLE life_facts (
  id TEXT PRIMARY KEY,
  fact TEXT NOT NULL,
  category TEXT,                   -- "preference","habit","history","goal","health"
  source_entry_id TEXT REFERENCES journal_entries(id) ON DELETE SET NULL,
  confidence REAL,
  first_seen TIMESTAMP,
  last_reinforced TIMESTAMP
);

CREATE TABLE relationships (
  id TEXT PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,
  aliases TEXT,                    -- JSON array
  relation_type TEXT,              -- "friend","family","colleague","unknown"
  sentiment_avg REAL,              -- rolling average
  interaction_count INTEGER DEFAULT 0,
  last_seen TIMESTAMP
);

CREATE TABLE interactions (
  id TEXT PRIMARY KEY,
  relationship_id TEXT REFERENCES relationships(id) ON DELETE CASCADE,
  entry_id TEXT REFERENCES journal_entries(id) ON DELETE CASCADE,
  sentiment REAL,                  -- -1.0 .. +1.0
  snippet TEXT,
  occurred_at TIMESTAMP
);

CREATE TABLE decisions (
  id TEXT PRIMARY KEY,
  question TEXT NOT NULL,
  status TEXT,                     -- "pending","analyzing","complete","recorded_outcome"
  analysis_json TEXT,              -- full pros/cons + weights
  chosen_option TEXT,
  outcome TEXT,
  outcome_recorded_at TIMESTAMP,
  created_at TIMESTAMP,
  completed_at TIMESTAMP
);
```

Migrations are executed in `database.init_db()` with `CREATE TABLE IF NOT EXISTS`. Add async helpers:
`create_journal_entry`, `upsert_mood`, `upsert_life_fact`, `upsert_relationship`, `add_interaction`,
`list_entries(start, end)`, `get_mood_series(window_days)`, `get_relationship_graph()`,
`create_decision`, `update_decision_analysis`, `record_decision_outcome`.

## 4.6 Backend — Agent Personalities

Create the following files under `backend/personalities/`:

### 4.6.1 `journal_lead.yaml` — *Echo*

```yaml
name: journal_lead
display_name: Echo
description: Journal orchestrator — routes to Mood, Psychology, Relationship, Decision specialists
tier: 2
domain: journal
system_prompt: |
  You are Echo, the Journal Lead. You orchestrate entry analysis and life queries.
  You NEVER provide clinical or medical diagnoses.
  Routing rules:
    - New entry saved        → Mood Analyst, Relationship Finder, Psychology Agent (async)
    - "How has my mood been" → Mood Analyst
    - "What patterns do I have" → Psychology Agent
    - "Who have I talked about" → Relationship Finder
    - "Should I..."          → Life Decisions Agent
  Always return at least a short textual response alongside any chart payload.
```

### 4.6.2 `mood_analyst.yaml` — *Lumen*

```yaml
name: mood_analyst
display_name: Lumen
description: Mood classifier & trend analyst
tier: 3
domain: journal
system_prompt: |
  You are Lumen. Given a journal entry, output JSON:
    {"score": 1-10, "emotions": ["..."], "confidence": 0.0-1.0, "reasoning": "..."}
  Score rubric:
    1-3 = very low mood    4-5 = low mood
    6   = neutral          7-8 = good       9-10 = excellent
  Emotions come from a fixed lexicon (see mood_lexicon.json).
  Never diagnose depression, anxiety disorders, or any clinical condition.
```

### 4.6.3 `psychology_agent.yaml` — *Sage*

```yaml
name: psychology_agent
display_name: Sage
description: Behavioral pattern detector — sliding window analyst
tier: 3
domain: journal
system_prompt: |
  You are Sage. Given N journal entries and a window in days, identify:
    - recurring themes (>=3 mentions)
    - cognitive tendencies (rumination, avoidance, reframing)
    - behavioral loops ("every time X, then Y")
  Output JSON with {patterns:[{name, evidence_entry_ids, confidence, description}]}.
  NEVER provide a medical diagnosis. Refer the user to a professional for clinical concerns.
```

### 4.6.4 `relationship_finder.yaml` — *Nexus*Relay (alias *Orbit*)

```yaml
name: relationship_finder
display_name: Orbit
description: People & interaction tracker
tier: 3
domain: journal
system_prompt: |
  You are Orbit. Given an entry, extract:
    - person mentions with likely relation_type
    - per-person sentiment from surrounding context
    - interaction snippet (<=200 chars)
  Output JSON: {people:[{name, aliases, relation_type, sentiment, snippet}]}.
  Use aliases to merge with existing relationships table when names match.
```

### 4.6.5 `life_decisions.yaml` — *Compass*

```yaml
name: life_decisions
display_name: Compass
description: Decision analyst — multi-source pros/cons with weights
tier: 3
domain: journal
system_prompt: |
  You are Compass. Given a decision question, you ask A2A for:
    - research reports on the topic (Research cluster)
    - memory facts on the user (Memory Archivist)
    - mood/pattern trends (Mood + Psychology)
    - relationship effects (Relationship Finder)
  Output a weighted pros/cons table:
    {question, options:[{name, pros:[{text,weight}], cons:[{text,weight}],
     score, sources:["research:slug","journal:id","memory:id"]}],
     recommendation, confidence, caveats}
  You never decide FOR the user; you present the analysis.
```

## 4.7 Backend — Agent Implementations

File layout:

```
backend/agents/journal/
  __init__.py
  journal_lead.py
  mood_analyst.py
  psychology_agent.py
  relationship_finder.py
  life_decisions.py
  lexicon/
    mood_lexicon.json        # 50–80 emotion tags grouped into 8 families
```

### 4.7.1 `MoodAnalystAgent`

- **Entry:** `async def analyze(entry_id: str, body: str) -> MoodResult`
- Calls LM Studio with a JSON-only prompt. Parses with `json.loads`, with a fallback that extracts the first JSON block via regex.
- Writes row into `mood_scores` via `upsert_mood`.
- Emits A2A `MEMORY_STORE` with `{category:"mood", entry_id, score, emotions}`.
- **Trend method:** `async def trend(window_days: int) -> ChartPayload` reads `mood_scores` grouped by day and returns ChartPayload of type `line`.

### 4.7.2 `PsychologyAgent`

- **Entry:** `async def analyze_window(days: int) -> list[PatternInsight]`.
- Guard: returns empty list if `len(entries) < PSYCHOLOGY_MIN_ENTRIES`.
- Chunks entries if window > token budget; summarizes chunks then aggregates.
- Stores patterns as `life_facts` rows with `category="pattern"`.
- Returns ChartPayload of type `bar` for frequency of each pattern.

### 4.7.3 `RelationshipFinderAgent`

- **Entry:** `async def process_entry(entry_id: str, body: str)`.
- Runs `spacy(body).ents` filtered to `PERSON`, then asks LM Studio to canonicalize (split "Priya" vs "Pri").
- For each person: `vaderSentiment` on the surrounding sentence → upsert `relationships`, append `interactions`.
- Applies `RELATIONSHIP_SENTIMENT_DECAY` when updating rolling averages.
- Provides `async def graph() -> ChartPayload` of type `graph` (nodes=people, edges=shared-entry co-occurrence).
- **Isolation detection:** if `max(last_seen) > 14 days` and user's mood < 5 → emit an isolation flag (consumed by Phase 6 Pattern Detective later).

### 4.7.4 `LifeDecisionsAgent`

- **Entry:** `async def analyze(question: str) -> DecisionResult`.
- Fan-out (parallel `asyncio.gather`):
  - A2A `CONTEXT_FETCH` to Research Lead for related reports
  - A2A `MEMORY_QUERY` to Memory Archivist (or direct SQLite in Phase 4 pre-5.x)
  - Local reads: mood trend (30d), top patterns, key relationships
- Concatenate context ≤ `MAX_DECISION_CONTEXT_TOKENS` (truncate by relevance).
- LM Studio call returns the structured JSON shown in the personality prompt.
- Persist to `decisions` table. Stream events: `decision.progress` (stage), `decision.complete`.
- Expose `async def record_outcome(decision_id, outcome)`.

### 4.7.5 `JournalLead`

- `on_new_entry(entry_id)`: save markdown to disk → fan-out Mood + Relationship (await) + Psychology (fire-and-forget).
- `on_chat_query(message)`: classify intent via a small router prompt, dispatch to specialist.
- Emits WS `journal.saved`, `mood.computed`, `chart.update`.

## 4.8 Backend — ChartPayload Contract

**File:** `backend/models/charts.py`

```python
class ChartPayload(BaseModel):
    id: str                        # stable id for React keys
    type: Literal["line","bar","radar","heatmap","graph","calendar"]
    title: str
    series: list[ChartSeries]      # for line/bar/radar
    nodes: list[GraphNode] | None  # for graph
    edges: list[GraphEdge] | None  # for graph
    x_label: str | None
    y_label: str | None
    meta: dict                     # window_days, units, color_mode, thresholds
```

- All chart-producing endpoints and agents MUST return this shape.
- Frontend receives it via REST (polled) and WS (`chart.update`) — single renderer per type.
- Validation: `type=="graph"` requires non-null `nodes` + `edges`; `type in {line,bar,radar}` requires non-empty `series`.

## 4.9 Backend — API Endpoints

**File:** `backend/api/routes/journal.py` (new)

```python
router = APIRouter(prefix="/api/journal", tags=["journal"])
```

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/journal` | Create entry. Body: `{title?, body_md}`. Returns entry + mood. |
| `GET`  | `/api/journal` | List with `?from=&to=&limit=&offset=`. |
| `GET`  | `/api/journal/{id}` | Full entry + mood + related people. |
| `DELETE` | `/api/journal/{id}` | Delete entry + cascaded mood/interactions; fires `MEMORY_STORE` tombstone. |
| `GET`  | `/api/journal/mood/calendar?year=YYYY` | Calendar heatmap ChartPayload. |
| `GET`  | `/api/journal/mood/trend?window=7\|30\|90` | Line-chart ChartPayload. |
| `GET`  | `/api/journal/insights?window=30` | Psychology insight cards. |
| `GET`  | `/api/journal/relationships` | Force graph ChartPayload. |
| `GET`  | `/api/journal/relationships/{name}` | Single-person detail + interaction list. |
| `POST` | `/api/journal/decisions` | Start a decision analysis. Body: `{question}`. Returns `decision_id`. |
| `GET`  | `/api/journal/decisions` | List decisions. |
| `GET`  | `/api/journal/decisions/{id}` | Analysis JSON + status. |
| `POST` | `/api/journal/decisions/{id}/outcome` | Record actual outcome. |

Wire the router in `backend/main.py`:

```python
from backend.api.routes import journal
app.include_router(journal.router)
```

## 4.10 Backend — A2A & Supervisor Wiring

1. **Supervisor update** (`backend/agents/supervisor.py`): add a routing branch for Journal intents. Recognize `"journal"`, `"how do I feel"`, `"mood"`, `"pattern"`, `"should I"`, etc. If matched, hand off to `JournalLead`.
2. **A2A emits:** Mood, Psychology, Relationship agents all send `MEMORY_STORE` envelopes with `category` set accordingly. Memory Archivist is a stub in Phase 4 that just writes to `life_facts` — replaced in Phase 5.
3. **Streaming:** reuse the existing WebSocket protocol (`thinking | agent_switch | progress | chunk | done`). Add new types: `chart.update`, `insight.generated`, `decision.progress`.

## 4.11 Frontend — State, Types & API Client

### 4.11.1 Types (`src/types/journal.ts` — new)

```ts
export type Mood = { score:number; emotions:string[]; confidence:number };
export type JournalEntry = { id:string; createdAt:string; title?:string; bodyMd:string; mood?:Mood; tags:string[] };
export type ChartPayload = { id:string; type:"line"|"bar"|"radar"|"heatmap"|"graph"|"calendar"; title:string; series?:any[]; nodes?:any[]; edges?:any[]; xLabel?:string; yLabel?:string; meta?:Record<string,unknown> };
export type Decision = { id:string; question:string; status:"pending"|"analyzing"|"complete"|"recorded_outcome"; analysis?:any; chosenOption?:string; outcome?:string };
```

### 4.11.2 Store (`src/stores/journalStore.ts`) — Zustand

- Slices: `entries`, `moodByDay`, `insights`, `relationshipsGraph`, `decisions`.
- Actions: `createEntry`, `deleteEntry`, `loadMoodTrend(window)`, `loadCalendar(year)`, `loadInsights(window)`, `loadRelationships`, `startDecision`, `recordOutcome`.
- WebSocket middleware: on `chart.update`, patch the corresponding chart slice.

### 4.11.3 API client (`src/lib/api/journal.ts`) — thin fetch wrappers mirroring §4.9

## 4.12 Frontend — Journal Tab

**File:** `src/components/tabs/JournalTab.tsx` (new)

Subtabs wired via a local pill navigator.

### 4.12.1 New Entry

- TipTap editor with minimal toolbar (bold, italic, list, link).
- Autosave draft to `localStorage` every 4 s.
- On save → `POST /api/journal`, show mood card (score + emotion chips) with fade animation.

### 4.12.2 Timeline

- Virtualized list (`react-window`) of entry cards.
- Each card: date, truncated body, mood color bar (`red→green` gradient from score 1→10), emotion chips.
- Infinite scroll with `?offset=`.

### 4.12.3 Mood Calendar

- `react-calendar-heatmap` with custom color scale:
  `#3b0a0a → #b91c1c → #f59e0b → #84cc16 → #22c55e`.
- Year selector; click a day → drill-down to that day's entries.

### 4.12.4 Insights

- Fetch `/api/journal/insights?window=30` → list of insight cards.
- Card: title, description, supporting entry count, confidence bar, "View evidence" → modal.

### 4.12.5 Decisions Log

- "New Decision" button → modal with `question` textarea.
- Analysis shown as a side-by-side options grid with weighted pros/cons; clicking a pro/con highlights its source.
- "Record outcome" input appears 7 days after completion.

## 4.13 Frontend — Dashboard Tab

**File:** `src/components/tabs/DashboardTab.tsx` (new)

### 4.13.1 Chart primitives (`src/components/charts/`)

- `MoodLineChart.tsx` — Recharts `LineChart` with reference line at score 6.
- `TopicBarChart.tsx` — Recharts `BarChart`.
- `HealthRadarChart.tsx` — Recharts `RadarChart` (placeholder values until Phase 4 late or deferred).
- `RelationshipGraph.tsx` — `react-force-graph-2d` with sentiment-colored edges; click a node → person detail drawer.
- `MoodCalendarHeatmap.tsx` — wraps `react-calendar-heatmap`.
- All components accept `ChartPayload` and render accordingly.

### 4.13.2 Layout

- 2×2 grid on desktop, stacked on mobile.
- Dashboard fetches multiple ChartPayload endpoints in parallel on mount.
- WS subscription updates charts in place.

### 4.13.3 Subtabs

- **Overview** — mood line (30d) + top 3 insight cards + relationships preview.
- **Mood Charts** — full line chart + calendar heatmap side by side + emotion frequency bar.
- **Life Analytics** — pattern bar charts from Psychology Agent.
- **Relationships** — full force graph + sortable people table.

## 4.14 Testing Checklist

### Backend (`backend/tests/test_phase4_*.py`)

- `test_mood_analyst_json_parsing` — valid + malformed LM responses.
- `test_relationship_finder_ner` — known sample text with 3 named people.
- `test_psychology_min_entries_guard`.
- `test_decision_fanout` — mock A2A, assert 3 sources merged.
- `test_journal_crud_roundtrip`.
- `test_chart_payload_validation` — schema enforcement.
- `test_supervisor_routes_journal_intent`.

### Frontend (`src/__tests__/phase4/*.test.tsx`)

- JournalTab submits entry → shows mood card.
- MoodLineChart renders with zero/one/N data points.
- RelationshipGraph renders and responds to node click.
- Decisions flow: start → progress stream → complete → outcome.

### Manual

- Write 5 entries over 5 simulated days; confirm calendar colors update.
- Ask "Should I quit my job?" and verify Research+Journal+Memory all appear in sources.

## 4.15 Acceptance Criteria

- ✅ Creating a journal entry triggers mood computation within 5 s.
- ✅ Mood calendar renders last 90 days without errors.
- ✅ Relationship graph renders ≥3 nodes after ≥3 entries mentioning different people.
- ✅ Decision analysis returns in <30 s and cites ≥2 source types.
- ✅ All new endpoints return `ChartPayload` where applicable and pass schema validation.
- ✅ Psychology Agent refuses to diagnose (guardrail test passes).

## 4.16 Week-by-Week Breakdown

| Week | Deliverables |
|---|---|
| 9 | Migrations, personalities, Mood Analyst, Journal REST create/list, TipTap editor, mood card. |
| 10 | Relationship Finder (spaCy+Vader), Psychology Agent, insights endpoint, calendar heatmap subtab. |
| 11 | Life Decisions Agent, A2A fan-out, Decisions Log subtab, WS chart.update plumbing. |
| 12 | ChartPayload contract locked, Dashboard tab with all 4 chart components, relationship force graph, end-to-end acceptance. |

---

# PHASE 5 — Memory System + Cross-Agent Intelligence (Week 13–14)

## 5.1 Goal & Deliverable

Ask *"What do you know about me?"* → response aggregates:

- Extracted facts from journal (`life_facts`)
- Research report summaries
- Uploaded file summaries (Knowledge cluster)
- People + dominant sentiment
- Explicit memory records created during chats

Plus a 3D force-directed knowledge graph in the Memory tab, a facts database view, and a conflict resolution UI.

## 5.2 Architecture Overview

```
Every agent ──A2A MEMORY_STORE──▶ Memory Archivist ──▶ memory_records (SQLite)
                                                    ├─▶ ChromaDB (semantic)
                                                    └─▶ memory_links (graph)

Supervisor ──MEMORY_QUERY──▶ Memory Archivist
Memory Archivist ──cross-search──▶ ChromaDB(nexus_research, nexus_files, nexus_memory)

Conflict pipeline:
  new fact → similarity search → if contradicts existing (score > 0.85 text sim,
  opposing polarity) → enqueue in memory_conflicts
```

## 5.3 Dependencies & Config

### 5.3.1 Python

Already covered: `chromadb`, `spacy`, `vaderSentiment`. Add:

```
rapidfuzz>=3.9.0                 # conflict similarity detection
```

Install: `conda run -n Command pip install rapidfuzz`.

### 5.3.2 Node.js

```json
"three": "^0.165.0",
"@react-three/fiber": "^8.16.0",
"@react-three/drei": "^9.108.0",
"react-force-graph-3d": "^1.24.0"
```

Install:

```bash
cd nexus-os-frontend
npm install three @react-three/fiber @react-three/drei react-force-graph-3d
```

(Some of these may already exist from Phase 1 3D work — verify, don't duplicate.)

### 5.3.3 Config

```python
# Phase 5 — Memory
MEMORY_DECAY_HALF_LIFE_DAYS: float = 60.0
MEMORY_REINFORCE_BOOST: float = 0.2
MEMORY_CONFLICT_SIM_THRESHOLD: float = 0.85
MEMORY_MAX_LINKS_PER_NODE: int = 25
CHROMA_COLLECTION_MEMORY: str = "nexus_memory"
```

## 5.4 Memory Data Model

### 5.4.1 SQLite tables

```sql
CREATE TABLE memory_records (
  id TEXT PRIMARY KEY,
  layer TEXT NOT NULL,            -- "short","working","long"
  category TEXT,                  -- "fact","preference","event","goal","mood","person"
  content TEXT NOT NULL,
  source_agent TEXT,
  source_ref TEXT,                -- e.g. "journal:<entry_id>", "research:<slug>"
  confidence REAL,
  importance REAL,                -- 0-1, affects decay resistance
  created_at TIMESTAMP,
  last_reinforced_at TIMESTAMP,
  decay_score REAL,               -- recomputed on read (not stored long-term, optional)
  chroma_id TEXT                  -- mirror id in ChromaDB
);
CREATE INDEX idx_mem_layer ON memory_records(layer);
CREATE INDEX idx_mem_category ON memory_records(category);

CREATE TABLE memory_links (
  src_id TEXT REFERENCES memory_records(id) ON DELETE CASCADE,
  dst_id TEXT REFERENCES memory_records(id) ON DELETE CASCADE,
  relation TEXT,                  -- "mentions","contradicts","supports","follows"
  weight REAL,
  PRIMARY KEY (src_id, dst_id, relation)
);

CREATE TABLE memory_conflicts (
  id TEXT PRIMARY KEY,
  record_a TEXT REFERENCES memory_records(id) ON DELETE CASCADE,
  record_b TEXT REFERENCES memory_records(id) ON DELETE CASCADE,
  similarity REAL,
  detected_at TIMESTAMP,
  status TEXT,                    -- "open","resolved","ignored"
  resolution_note TEXT,
  resolved_at TIMESTAMP
);
```

### 5.4.2 Layers

- **short-term** — current conversation turn; cleared on new session.
- **working** — current session; promoted to long-term on importance > 0.5 or explicit user confirmation.
- **long-term** — persistent, backed by SQLite + ChromaDB.

### 5.4.3 Decay formula

```
decay_score = importance * exp(-ln(2) * age_days / HALF_LIFE) + last_reinforced_boost
```

Recompute at query time; used for ranking retrieved memories, never destructive.

## 5.5 Backend — Memory Archivist Agent

**File:** `backend/agents/memory/memory_archivist.py`

Personality `backend/personalities/memory_archivist.yaml` — *Mnemos*.

### 5.5.1 Responsibilities

- Consume A2A `MEMORY_STORE` envelopes from all agents.
- Deduplicate via ChromaDB similarity + exact hash on content.
- Classify layer (default: `long` for facts, `working` for conversational snippets).
- Detect conflicts via `rapidfuzz.fuzz.token_set_ratio` + polarity check.
- Handle A2A `MEMORY_QUERY` with `{query, filters, top_k}` → returns ranked records.

### 5.5.2 Key methods

```python
async def store(record: MemoryInput) -> MemoryRecord
async def query(q: str, filters: dict | None, top_k: int = 20) -> list[MemoryRecord]
async def reinforce(record_id: str) -> None
async def detect_conflicts(record_id: str) -> list[MemoryConflict]
async def resolve_conflict(conflict_id: str, winner_id: str | None, note: str) -> None
async def cross_search(q: str, collections: list[str]) -> list[MemoryRecord]
async def knowledge_graph() -> GraphPayload
```

### 5.5.3 Migration from Phase 4 stub

- Replace the Phase 4 `life_facts` writer with calls to `memory_archivist.store(...)`.
- One-shot migration script `backend/scripts/migrate_facts_to_memory.py` copies existing `life_facts` rows into `memory_records` preserving source references.

## 5.6 Backend — A2A Contract: MEMORY_STORE / MEMORY_QUERY

```python
class MemoryStorePayload(BaseModel):
    content: str
    category: Literal["fact","preference","event","goal","mood","person","file","research"]
    source_ref: str                    # "journal:<id>", "file:<id>", "research:<slug>"
    confidence: float = 0.6
    importance: float = 0.5
    metadata: dict = {}

class MemoryQueryPayload(BaseModel):
    query: str
    filters: dict = {}                 # {category, source_type, since, until}
    top_k: int = 20
    include_chroma: bool = True
```

All pre-Phase-5 agents that wrote directly to local tables are updated to publish via A2A. Memory Archivist acknowledges with correlation id; originator moves on.

## 5.7 Backend — Cross-Domain Search

**Supervisor enhancement:** For queries like *"anything in my files AND journal about X?"* the Supervisor now calls:

```python
async def cross_domain_search(q: str) -> CrossDomainResult:
    # fan-out in parallel:
    memory = await memory_archivist.query(q, top_k=15)
    research = await rag_retriever.search(q, collection="nexus_research", top_k=10)
    files = await rag_retriever.search(q, collection="nexus_files", top_k=10)
    return merge_and_rerank(memory, research, files)
```

Merging uses a simple normalized score: `0.5 * semantic_score + 0.3 * importance + 0.2 * recency`.

## 5.8 Backend — API Endpoints

**File:** `backend/api/routes/memory.py` (new)

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/memory/search?q=&category=&limit=` | Semantic + keyword search across memory. |
| `GET` | `/api/memory/facts` | Paginated table of long-term facts. |
| `GET` | `/api/memory/graph?depth=2&root=` | 3D knowledge graph payload. |
| `GET` | `/api/memory/conflicts?status=open` | List pending conflicts. |
| `POST` | `/api/memory/conflicts/{id}/resolve` | Body: `{winner_id?, note}`. |
| `POST` | `/api/memory/reinforce/{id}` | Boost importance/decay. |
| `DELETE` | `/api/memory/{id}` | Soft-delete (tombstone record). |
| `GET` | `/api/memory/cross-search?q=` | Triggers Supervisor cross-domain fan-out. |

## 5.9 Frontend — Memory Tab

**File:** `src/components/tabs/MemoryTab.tsx` (new)

### 5.9.1 Knowledge Graph subtab

- `react-force-graph-3d` instance in a `<Canvas>` container.
- Node size proportional to `importance`, color by `category`.
- Hover → tooltip with content preview.
- Click → side drawer with full record + "Reinforce" + "Delete" + linked records list.
- URL param `?root=<id>&depth=2` for deep links.

### 5.9.2 Facts Database subtab

- TanStack Table with columns: category, content (truncated), source_ref (linkable), confidence, created_at.
- Column filters + multi-select category facet.
- Row action menu: Reinforce, Delete, Find in graph.

### 5.9.3 Conflicts subtab

- Stacked cards: `record_a` vs `record_b` side-by-side with diff highlight.
- Buttons: "Keep A", "Keep B", "Keep both (resolve note)", "Ignore".
- Empty state with count of resolved conflicts.

### 5.9.4 Cross-cluster chat query

- Chat tab gains a subtle `[search memory]` quick-action button; clicking prepends `cross:` to the message which Supervisor recognizes → routes to `cross_domain_search`.

## 5.10 Testing Checklist

- `test_memory_store_dedup` — storing the same content twice reinforces instead of duplicating.
- `test_memory_conflict_detection` — seed contradictory facts, assert conflict created.
- `test_memory_decay_ordering` — older fact of equal importance ranks lower.
- `test_cross_domain_merge_ranking`.
- `test_migration_script_idempotent`.
- Frontend: graph renders 100-node fixture in <2 s; conflict resolve round-trips.

## 5.11 Acceptance Criteria

- ✅ Every Phase 4 agent writes through Memory Archivist (no direct SQLite fact writes remain).
- ✅ "What do you know about me?" returns ≥3 categories of evidence.
- ✅ Conflicts UI shows seeded test conflicts and resolves them persistently.
- ✅ 3D knowledge graph loads and is interactive with ≥50 nodes.
- ✅ Memory decay demonstrably down-ranks year-old records vs week-old in identical-query tests.

## 5.12 Week-by-Week Breakdown

| Week | Deliverables |
|---|---|
| 13 | SQLite schemas, Memory Archivist agent + A2A contract, migration script, REST endpoints, Facts Database subtab. |
| 14 | Conflict detection + resolution UI, 3D knowledge graph, cross-domain search, rewire all prior agents through Archivist, acceptance tests. |

---

# PHASE 6 — Proactive Intelligence Engine (Week 15–16)

## 6.1 Goal & Deliverable

The system pushes without being asked:

- **Morning Briefing (6 AM):** *"Good morning. Your mood is trending up. You've been researching career changes and journaling about dissatisfaction — a pattern worth considering. Today's top 3 insights → …"* with embedded charts.
- **Nightly Analysis (10 PM):** background cross-correlation, stores insights.
- **Periodic Check (every 4 h):** anomaly scans (e.g., mood drop, isolation flag, research burst).
- **Notification Bell:** unread insight count in the sidebar; clicking opens a dropdown of the most recent N.

## 6.2 Architecture Overview

```
APScheduler ──▶ Proactive Lead ──▶ Pattern Detective ──queries──▶ Memory, Journal, Research
                                ▲
                                └─ Briefing Agent ──▶ ChartPayload + notifications

Notifications ──WS broadcast──▶ Frontend bell + banner
```

## 6.3 Dependencies & Config

### 6.3.1 Python

```
apscheduler>=3.10.4
tzlocal>=5.2
```

Install: `conda run -n Command pip install apscheduler tzlocal`.

### 6.3.2 Config

```python
# Phase 6 — Proactive Intelligence
SCHEDULER_TIMEZONE: str = "local"
BRIEFING_HOUR: int = 6           # local time
NIGHTLY_HOUR: int = 22
PERIODIC_INTERVAL_HOURS: int = 4
INSIGHT_MAX_PER_BRIEFING: int = 3
INSIGHT_MIN_SEVERITY: float = 0.4      # filter before push
PATTERN_WINDOWS_DAYS: list[int] = [7, 30, 90]
ANOMALY_Z_THRESHOLD: float = 2.0
```

## 6.4 Scheduler Design

**File:** `backend/core/scheduler.py` (new)

- Uses `AsyncIOScheduler` started in `lifespan` of `backend/main.py`.
- Three registered jobs:
  - `morning_briefing` — cron `hour=BRIEFING_HOUR, minute=0`
  - `nightly_analysis` — cron `hour=NIGHTLY_HOUR, minute=0`
  - `periodic_check`   — interval `hours=PERIODIC_INTERVAL_HOURS`
- Every job records start/end in a new `scheduled_jobs` SQLite table (`id`, `name`, `started_at`, `completed_at`, `status`, `error`).
- Graceful shutdown on FastAPI `shutdown` event.

## 6.5 Backend — Agent Personalities

### 6.5.1 `proactive_lead.yaml` — *Herald*

- Decides WHICH insights surface (severity + novelty filter), avoids repetition vs last 7 days.

### 6.5.2 `pattern_detective.yaml` — *Argus*

- Cross-correlates across domains: *"research burst on X AND journal mentions of X"*, *"mood drop AND isolation"*, etc.

### 6.5.3 `briefing_agent.yaml` — *Aurora*

- Writes a 120–180 word briefing: greeting, top 3 insights, mood blurb, pending items, suggested actions, chart references.

## 6.6 Backend — Agent Implementations

**File layout:**

```
backend/agents/proactive/
  proactive_lead.py
  pattern_detective.py
  briefing_agent.py
```

### 6.6.1 Pattern Detective

- **Temporal patterns:** `detect_streaks(metric, min_length=3)` on mood scores and research activity.
- **Correlation:** Pearson on mood vs interaction sentiment of key relationships; topic overlap (cosine) of research reports vs journal tags.
- **Anomalies:** z-score > `ANOMALY_Z_THRESHOLD` on any rolling metric.
- **Frequency:** topics/people that jumped from 0-1 mentions to ≥3 in the last 7 days.
- Outputs: list of `PatternInsight(severity, category, description, evidence_refs[], chart_payload?)`.

### 6.6.2 Briefing Agent

- Gathers:
  - Top N insights from Proactive Lead
  - Mood 7d summary
  - Pending decisions (status != complete)
  - Open memory conflicts count
- LM Studio prompt produces markdown briefing + one hero ChartPayload.
- Persist to `briefings` table; push via WS + store in `insights` table as `briefing` type.

### 6.6.3 Proactive Lead

- `async def run_nightly()` — calls Pattern Detective over 7d + 30d, stores insights.
- `async def run_morning()` — calls Briefing Agent consuming yesterday's + fresh insights.
- `async def run_periodic()` — lightweight anomaly scan only; pushes only if severity ≥ threshold.
- **Deduplication:** same-signature insight in last 7 days is skipped or merged.

## 6.7 Backend — Notifications Storage & Push

### 6.7.1 SQLite tables

```sql
CREATE TABLE insights (
  id TEXT PRIMARY KEY,
  category TEXT,                   -- "pattern","anomaly","briefing","correlation","suggestion"
  severity REAL,
  title TEXT,
  body_md TEXT,
  evidence_json TEXT,              -- refs
  chart_payload_json TEXT,         -- optional
  created_at TIMESTAMP,
  read_at TIMESTAMP
);
CREATE INDEX idx_insights_created ON insights(created_at);

CREATE TABLE briefings (
  id TEXT PRIMARY KEY,
  created_at TIMESTAMP,
  body_md TEXT NOT NULL,
  hero_chart_json TEXT,
  mood_summary TEXT,
  insights_json TEXT               -- ids & snippets
);

CREATE TABLE scheduled_jobs (
  id TEXT PRIMARY KEY,
  name TEXT,
  started_at TIMESTAMP,
  completed_at TIMESTAMP,
  status TEXT,
  error TEXT
);
```

### 6.7.2 WebSocket broadcast

- Reuse `/ws/chat` with new event types: `insight.new`, `briefing.new`.
- A fan-out channel `WebSocketManager.broadcast(event)` maintains per-session connections.

## 6.8 Backend — API Endpoints

**File:** `backend/api/routes/insights.py` (new)

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/insights?unread=true&limit=50` | Paginated insights. |
| `POST` | `/api/insights/{id}/read` | Mark read. |
| `DELETE` | `/api/insights/{id}` | Dismiss. |
| `GET` | `/api/briefings/today` | Today's briefing if any. |
| `GET` | `/api/briefings?limit=30` | Archive. |
| `POST` | `/api/scheduler/trigger/{job}` | Dev-only: manually fire `morning/nightly/periodic`. |
| `GET` | `/api/scheduler/jobs` | List scheduled-job run history. |

## 6.9 Frontend — Insights Tab & Notifications

### 6.9.1 Insights Tab (`src/components/tabs/InsightsTab.tsx`)

Subtabs:

- **Morning Briefing:** hero card with greeting, body, hero chart. "Show evidence" expand → insight cards.
- **Patterns:** swipeable stack of pattern insight cards, each with supporting chart.
- **History:** archive list with date filter.

### 6.9.2 NotificationBell (`src/components/layout/NotificationBell.tsx`)

- Placed in the sidebar.
- Shows unread count badge (fetched on mount + updated via WS `insight.new`).
- Dropdown with 5 most recent; "See all" → Insights tab.

### 6.9.3 Chat banner

- Slim top banner on Chat tab when `GET /api/briefings/today` returns not-yet-dismissed briefing.
- Actions: "Read full", "Dismiss".

### 6.9.4 Dev controls

- Hidden panel (Cmd+Shift+D) to trigger jobs manually and inspect scheduler run history.

## 6.10 Testing Checklist

- `test_scheduler_registers_three_jobs`.
- `test_pattern_detective_correlation` — seeded mood + research data produces expected cross-domain pattern.
- `test_briefing_structure` — always emits greeting, ≤3 insights, 1 hero chart.
- `test_insight_dedup_7day`.
- `test_ws_broadcast_insight_new`.
- Frontend: notification bell badge increments on simulated WS event; briefing banner dismiss is persistent.

## 6.11 Acceptance Criteria

- ✅ Manual trigger of `morning` job produces a briefing with a hero ChartPayload and ≥2 insights.
- ✅ A 7-day simulated dataset where mood drops 3 days in a row produces an anomaly insight.
- ✅ Notification bell reflects unread count accurately across reload.
- ✅ Duplicate insights within 7 days are suppressed.
- ✅ Scheduler gracefully shuts down without leaving zombie tasks.

## 6.12 Week-by-Week Breakdown

| Week | Deliverables |
|---|---|
| 15 | Scheduler + tables, Pattern Detective (temporal + anomaly + correlation + frequency), insights API, dev trigger panel. |
| 16 | Briefing Agent, Proactive Lead dedup, NotificationBell + banner, Insights tab (all subtabs), WS wiring, acceptance. |

---

## Cross-Phase Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| LM Studio latency under parallel agent fan-out | User-visible lag on briefing and decisions | Cap concurrency via `asyncio.Semaphore(MAX_CONCURRENT_AGENTS)`; stream early partials. |
| Mood miscategorization → Proactive Lead raises false alarms | Trust erosion | Require `confidence ≥ 0.6` for insights; allow user to mark "not useful", feed back into Proactive Lead filter. |
| Conflict detection false positives on paraphrases | Conflict queue noise | Combine rapidfuzz text sim with ChromaDB semantic distance AND polarity check. |
| Scheduler fires before data exists | Empty briefings | Skip job if `journal_entries` count < 3 in last 7 days; log skip reason. |
| A2A bus not running (Redis optional) | Missing memory writes | Fallback: Memory Archivist exposes an in-process async queue when `message_bus.connected is False`. |
| 3D graph performance with >500 nodes | Lag | Cap initial load with `?depth=2`; lazy-load expansion on node click. |
| Psychology Agent drifting into clinical territory | Safety | Guardrail system prompt + unit test that asserts refusal on diagnosis prompts. |
| Sensitive journal data exfiltration | Privacy | All data stays local (LM Studio, SQLite, ChromaDB); block any outbound HTTP unless whitelisted domains (Research only). |
