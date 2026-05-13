# NEXUS OS — Detailed System Architecture Documentation

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Component Diagram](#2-component-diagram)
3. [Data Flow Architecture](#3-data-flow-architecture)
4. [Agent Architecture (Phase 2 & 3)](#4-agent-architecture-phase-2--3)
5. [Database Design](#5-database-design)
6. [Vector Store Architecture](#6-vector-store-architecture)
7. [WebSocket Protocol Specification](#7-websocket-protocol-specification)
8. [Design Decisions & Trade-offs](#8-design-decisions--trade-offs)

---

## 1. System Overview

NEXUS OS is a **modular, event-driven AI operating system** designed to orchestrate multiple intelligent agents across conversational and autonomous research workloads. The architecture follows an **agent hierarchy pattern** with clear separation of concerns between:

- **Tier 1 (Supervisor):** Global orchestrator, intent routing
- **Tier 2 (Domain Leads):** Specialized workflows (Knowledge, Research)
- **Tier 3 (Specialists):** Task-specific agents (Search, Scraping, Fact-checking)

### Key Architectural Principles

| Principle | Implementation |
|-----------|----------------|
| **Modularity** | Agents are state machines with well-defined input/output contracts |
| **Streaming** | All LLM responses stream via WebSocket for real-time UI updates |
| **Resilience** | Graceful degradation when external services (DDGS, LM Studio) fail |
| **Extensibility** | Agent personalities defined externally in YAML files |

---

## 2. Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CLIENT LAYER                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────────────┐  │
│  │ Next.js App  │  │ Zustand      │  │ useWebSocket Hook               │  │
│  │ ──────────   │  │ Store (Chat) │  │ └── Message dispatch            │  │
│  │ Tabs, UI     │◄►│ State        │  │ └── Event handling              │  │
│  └──────────────┘  └──────────────┘  └──────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │ WebSocket (ws://localhost:8000/ws/chat)
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         BACKEND LAYER                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                        FastAPI Application                            │   │
│  ├──────────────────────────────────────────────────────────────────────┤   │
│  │  Lifespan Event Context                                              │   │
│  │  ┌──────────────┐  ┌─────────────┐  ┌────────────────────────────┐   │   │
│  │  │ init_db()    │  │ init_vector │  │ Rebuild BM25 indexes       │   │   │
│  │  └──────────────┘  │_store()     │  └────────────────────────────┘   │   │
│  ├──────────────────────────────────────────────────────────────────────┤   │
│  │  API Routes (REST)                                                   │   │
│  │  ├── /api/system/metrics  → system_metrics.py                       │   │
│  │  └── /api/research/*      → research_api.py                         │   │
│  ├──────────────────────────────────────────────────────────────────────┤   │
│  │  WebSocket Handler (chat_router)                                     │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │   │
│  │  │                        Supervisor                                │ │   │
│  │  │     ┌──────────────┐    ┌──────────────┐    ┌──────────────┐   │ │   │
│  │  │     │ Intent Router│──►│ Research Lead│──►│ Knowledge     │   │ │   │
│  │  │     └──────────────┘    └──────────────┘    │ Leader       │   │ │   │
│  │  │                                              └──────────────┘   │ │   │
│  │  │                             Research Lead (Tier 2)               │ │   │
│  │  │     ┌──────────────┐    ┌──────────────┐    ┌──────────────┐   │ │   │
│  │  │     │ Web Scout    │◄───│              │──►│ Scraper Agent│   │ │   │
│  │  │     │ (Vector)     │    │ Research     │    │             │   │ │   │
│  │  │     └──────────────┘    │ Lead         │◄───│ Fact Checker│   │ │   │
│  │  │                         └──────────────┘    │ (Verity)     │   │ │   │
│  │  │                                              └──────────────┘   │ │   │
│  │  │                             Knowledge Lead (Tier 2)              │ │   │
│  │  │     ┌──────────────┐    ┌──────────────┐    ┌──────────────┐   │ │   │
│  │  │     │ Files        │◄───│              │──►│ Journal       │   │ │   │
│  │  │     │ (Upload/RAG) │    │ Knowledge    │    │ Entries      │   │ │   │
│  │  │     └──────────────┘    │ Lead         │◄───│ Memory       │   │ │   │
│  │  │                         └──────────────┘    │ Manager      │   │ │   │
│  │  └─────────────────────────────────────────────────────────────────┘   │   │
│  ├──────────────────────────────────────────────────────────────────────┤   │
│  │  External Services Integration                                        │   │
│  │  ├── LM Studio API (1234/v1) → LLM inference + embeddings            │   │
│  │  ├── DuckDuckGo Search API     → Web queries                         │   │
│  │  └── HuggingFace Hub           → Embedding model downloads           │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────────────────┤
│                        DATA LAYER                                           │
│  ├── SQLite (conversations)     → JSON-backed chat history               │
│  ├── ChromaDB (embeddings)      → Vector indices + BM25 fallback          │
│  └── File System                → Raw documents, research reports         │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Data Flow Architecture

### Chat Message Flow (Phase 1)

```
┌──────────────┐     JSON      ┌──────────────┐     WebSocket    ┌──────────────┐
│   User       │ ───────────►  │  Frontend    │ ◄──────────────► │  Backend     │
│  Input Field │               │  ChatWindow  │                   │  Supervisor  │
└──────────────┘               │              │                   │  Agent       │
                               │  useWebSocket│                   └──────────────┘
                               │   Hook        │                      │
                               │  sendMessage()│                      │
                               └─────┬─────────┘                      ▼
                                     │                            ┌──────────────┐
                                     │     Stream Tokens          │ LM Studio   │
                                     └─────►──────────────────────► API         │
                                          │                                  │
                                          │  Token-by-token                │
                                          └────────────────────────────────┘

Event Sequence:
1. User types → dispatchChatMessage(content)
2. Frontend → WebSocket.send({type: "message", content})
3. Backend receives → Supervisor.stream_response()
4. LLM streams tokens via HTTPX generator
5. Each token sent as {type: "stream_token", content}
6. UI renders incrementally with framer-motion
```

### Research Pipeline Flow (Phase 3)

```
┌──────────────┐     Intent Detection    ┌──────────────┐
│ User Message │ ◄─────────────────────► │ Knowledge    │
└──────────────┘                         │ Leader       │
                                         └─────┬────────┘
                                               │ detect research intent
                                               ▼
                                      ┌──────────────┐
                                      │ Research     │
                                      │ Lead (Atlas)│
                                      └─────┬────────┘
                                           │ run_research()
                                           ▼
                                   ┌──────────────┐
                                   │ Web Scout    │◄─┐
                                   │  (Vector)   │  │ search DDGS
                                   └─────┬────────┘  │
                                          │          │
                                          │ query variations
                                          ▼         │
                                    ┌──────────────┐│
                                    │ DuckDuckGo   ││
                                    │ Search API   ││
                                    └─────┬────────┘│
                                          │ results │
                                          ▼         │
                                   ┌──────────────┐│ rank & dedupe
                                   └─────┬────────┘│
                                         │ urls    │
                                         ▼         │
                                      ┌──────────────┐
                                      │ Scraper      │◄─┐
                                      │  (Fetch)     │  │ fetch HTML
                                      └─────┬────────┘  │
                                             │          │
                                             │ clean text│
                                             ▼          │
                                        ┌──────────────┐│
                                        │ Fact Checker ││ validate claims
                                        │  (Verity)    ││ cross-source
                                        └─────┬────────┘│
                                              │ claims │
                                              ▼         │
                                         ┌──────────────┐
                                         │ Report       │◄─┐ synthesize
                                         │ Builder      │ │ markdown
                                         │  (Scribe)   │ │ + index
                                         └─────┬────────┘│
                                               │ report │
                                               ▼         │
                                      ┌──────────────┐  │ ChromaDB
                                      │ Disk Storage │──┘ research
                                      │              │  collection
                                      └──────────────┘
```

### Event Flow (WebSocket)

- `thinking`: Agent is planning
- `progress`: Pipeline stage updates
- `agent_switch`: Transition between agents
- `chunk`: Report content streaming
- `done`: Final report metadata returned

---

## 4. Agent Architecture (Phase 2 & 3)

### Hierarchy Overview

| Tier | Role | Responsibility | Agents |
|------|------|----------------|--------|
| **1** | Supervisor | Global orchestration, intent routing | supervisor.py |
| **2** | Knowledge Lead | Files upload/RAG, journaling, memory | knowledge_lead.py |
| **2** | Research Lead | Full research pipeline coordination | research_lead.py |
| **3** | Specialist | Single-purpose tasks with well-defined outputs | web_scout, scraper_agent, fact_checker, report_builder |

### Agent State Machine Pattern

All agents follow a consistent pattern:

```python
class Agent:
    """Agent base class following streaming state machine pattern."""
    
    async def run(self, input_data) -> AsyncGenerator[dict, None]:
        """
        Stream events as agent processes input.
        
        Event types:
          - thinking: Initial planning/reasoning
          - progress: Intermediate status updates
          - result: Final output data
          - error: Error occurrence with context
        
        Each yield provides a dictionary event for WebSocket transmission.
        """
        yield {"type": "thinking", "detail": "..."}
        
        # Agent processing logic here...
        
        yield {"type": "result", "data": ...}


# Example: WebScoutAgent state machine
async def web_scout.run(topic: str) -> AsyncGenerator[dict, None]:
    # 1. Thinking phase
    yield {"type": "thinking", "detail": "Generating search queries..."}
    
    # 2. Query generation
    queries = await generate_query_variations(topic)
    
    # 3. Streaming search (progress events)
    for query in queries:
        yield {
            "type": "progress", 
            "stage": "searching",
            "detail": f"Query: {query}"
        }
        
        results = await search_single_query(query)
    
    # 4. Ranking phase (progress event)
    ranked = await score_and_rank(results, topic)
    yield {"type": "progress", "stage": "ranking"}
    
    # 5. Result phase
    yield {"type": "result", "data": ranked}
```

### Personality System

Agent behavior is configured via YAML system prompts:

**File:** `backend/personalities/web_scout.yaml`

```yaml
name: web_scout
display_name: Vector
description: Web search specialist — finds and ranks relevant URLs
tier: 3
domain: research

system_prompt: |
  You are Vector, a precision web search agent. Your job is to find the most
  authoritative and relevant web sources for a given research topic.
  
  [Detailed behavioral instructions...]

capabilities:
  - duckduckgo_search
  - query_variation_generation
  - domain_authority_scoring
```

Agents load their personality during initialization, enabling **runtime configuration** without code changes.

---

## 5. Database Design

### SQLite Schema (Conversations)

```sql
-- conversations table
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,          -- conversation_id UUID
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- messages table
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    role TEXT CHECK(role IN ('user', 'assistant')),
    content TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    agent_id TEXT DEFAULT 'supervisor'
);

-- Research jobs table (Phase 3)
CREATE TABLE IF NOT EXISTS research_jobs (
    job_id TEXT PRIMARY KEY,
    topic TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    status TEXT CHECK(status IN ('pending', 'running', 'complete', 'failed')),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,
    error TEXT
);

-- Index for fast message retrieval by conversation
CREATE INDEX IF NOT EXISTS idx_messages_conversation 
ON messages(conversation_id);
```

### Research Data Structure

**Research Report Directory:** `data/deep_research/{slug}/`

```
{slug}/
├── report.md                  # Final synthesized markdown report
├── metadata.json              # Topic, date, source_count, confidence, job_id
├── sources/
│   └── {url_hash}.json        # Raw scraped content per source
└── fact_check.json            # All claims + per-claim confidence + source refs
```

---

## 6. Vector Store Architecture

### Hybrid Search Strategy

NEXUS OS uses **BM25 + Embedding hybrid search** via ChromaDB:

```
┌─────────────────────────────────────────────────────────────┐
│                    Vector Retrieval Flow                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Query: "quantum computing advances"                        │
│       ↓                                                      │
│  ┌─────────────────┐    ┌─────────────────┐                 │
│  │ BM25 Keyword    │    │ Embedding Vector│                 │
│  │ Search          │◄──►│ Search          │                 │
│  │ (exact matches) │    │ (semantic)      │                 │
│  └───────┬──────────┘    └───────┬────────┘                 │
│          │                       │                          │
│          ▼                       ▼                          │
│  ┌───────────────────────────────────────────────┐         │
│  │           RRF Fusion (Reciprocal Rank)        │         │
│  │  Score = Σ(1/(rank_i + k)) for each source    │         │
│  └─────────────────────┬─────────────────────────┘         │
│                        │                                    │
│                        ▼                                    │
│              Top-N Ranked Results                           │
└─────────────────────────────────────────────────────────────┘
```

### LM Studio Embedding Function

Custom embedding function for synchronous ChromaDB integration:

```python
class LMStudioEmbeddingFunction(chromadb.EmbeddingFunction):
    """Synchronous HTTP call to LM Studio embeddings endpoint."""
    
    def __call__(self, input: list[str]) -> chromadb.Embeddings:
        response = httpx.post(
            f"{self.url}/embeddings",
            json={"model": self.embedding_model, "input": input},
            timeout=60  # Blocking call required for ChromaDB threading model
        )
        return response.json()["data"][0]["embedding"]
```

---

## 7. WebSocket Protocol Specification

### Connection Handshake

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Always `"connected"` on connection open |
| `conversation_id` | string | UUID assigned by server |

### Message Format (Client → Server)

```json
{
  "type": "message",              // or "image_query", "ping", "clear_history"
  "content": "user message text",
  "agent_id": "supervisor",       // optional: preferred agent
  "image_b64": "...",             // base64 image data (for vision queries)
  "image_mime": "image/jpeg"      // MIME type of image
}
```

### Server Event Format

```json
{
  "type": "<event_type>",
  
  // For thinking/thinking_end events:
  "agent_id": "supervisor",       // Agent responsible for response
  
  // For streaming events (token/stream_token):
  "content": "chunk of LLM output"
  
  // For progress events:
  "stage": "searching",           // Pipeline stage
  "detail": "Query 1/3: ..."      | human-readable status
  
  // For done/done_event:
  "slug": "research-report-id",   // Research report identifier
  "metadata": {...}               // Report metadata object
}
```

---

## 8. Design Decisions & Trade-offs

### 1. WebSocket vs REST for Chat Streaming

**Decision:** WebSocket exclusively for chat/research streaming.

| Aspect | WebSocket Choice | Trade-off |
|--------|------------------|-----------|
| Real-time UI updates | ✅ Single persistent connection | ❌ Requires reconnection logic on disconnect |
| Bidirectional communication | ✅ Server can push metrics/events | ❌ Not suitable for REST API patterns |
| Resource efficiency | ✅ One connection serves all interactions | ❌ Connection pooling required at scale |

**Alternative considered:** SSE (Server-Sent Events) — rejected because bidirectional events needed.

### 2. Blocking HTTPX vs Aiohttp for Embeddings

**Decision:** Blocking `httpx.post` in synchronous `__call__()`.

| Aspect | Blocking Choice | Trade-off |
|--------|-----------------|-----------|
| ChromaDB compatibility | ✅ Required by Chroma's threading model | ❌ Blocks embedding thread during LMS call |
| Error handling | ✅ Simple try-catch, clear timeout behavior | ❌ No async cancellation of pending requests |

**Alternative considered:** Asyncio.to_thread() wrapper — would still block the ChromaDB worker thread.

### 3. Agent Hierarchy (Tiered Design)

**Decision:** Strict tier hierarchy (1 → 2 → 3).

| Aspect | Tiered Choice | Trade-off |
|--------|---------------|-----------|
| Clear responsibility boundaries | ✅ Each agent has single purpose | ❌ More complex routing logic |
| Easier debugging | ✅ Can trace intent: User → Supervisor → ResearchLead → WebScout | ❌ Latency added by multiple hops |

**Alternative considered:** Flat agent pool — would require LLM to decide which agent handles each query, adding reasoning overhead.

### 4. Local-First Architecture (LM Studio)

**Decision:** Embed all AI models locally via LM Studio.

| Aspect | Local Choice | Trade-off |
|--------|--------------|-----------|
| Privacy & data control | ✅ No external API calls for sensitive research | ❌ Higher hardware requirements |
| Offline capability | ✅ Can function without network (with cached models) | ❌ Model updates require local downloads |
| Cost predictability | ✅ Fixed inference costs, no per-token fees | ❌ Development complexity of local model management |

### 5. BM25 + Embedding Hybrid Search

**Decision:** RRF fusion of exact matches and semantic similarity.

| Aspect | Hybrid Choice | Trade-off |
|--------|---------------|-----------|
| Precision for facts | ✅ Exact keyword matching ensures specific information retrieval | ❌ May miss semantically related content |
| Robustness to phrasing variations | ✅ Semantic search finds paraphrased concepts | ❌ Higher false-positive rate |

**Alternative considered:** Embedding-only — would fail at exact document lookup (e.g., "Show me what I wrote about quantum computing" on day 2).

---

## Summary

NEXUS OS architecture prioritizes **modularity, streaming responsiveness, and resilient agent composition**. The tiered hierarchy enables clean separation of concerns while the WebSocket-first design ensures smooth real-time user experience. Local-first AI integration provides privacy and cost predictability at the expense of hardware requirements.
