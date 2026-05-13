# NEXUS OS — Current Project Flow and State

---

## Table of Contents

1. [Application Runtime Flow](#1-application-runtime-flow)
2. [Implementation Status by Component](#2-implementation-status-by-component)
3. [Current Known Limitations & WIP](#3-current-known-limitations--wip)
4. [Data Structures in Use](#4-data-structures-in-use)

---

## 1. Application Runtime Flow

### Startup Sequence

```
┌─────────────────────────────────────────────────────────────┐
│                    Server Initialization                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. Load configuration from .env                             │
│     └── Settings class initialized                           │
│                                                              │
│  2. Setup logging                                             │
│     └── Log level: INFO (from DEBUG=true)                    │
│                                                              │
│  3. Create data directories                                   │
│     ├── ./data/                                              │
│     ├── ./data/conversations/                                │
│     ├── ./data/files/                                        │
│     ├── ./data/chroma/                                       │
│     └── ./data/uploads/                                      │
│                                                              │
│  4. Initialize database (SQLite)                              │
│     └── conversations, messages tables created               │
│                                                              │
│  5. Initialize vector store                                   │
│     └── ChromaDB collection created                          │
│                                                              │
│  6. Rebuild BM25 indexes                                      │
│     ├── nexus_files collection                                │
│     ├── nexus_research collection                            │
│     └── nexus_journal collection                             │
│                                                              │
│  7. Register routers                                          │
│     ├── files_router    → document upload/RAG                │
│     ├── agents_router   → agent management                   │
│     ├── chat_router     → WebSocket chat                     │
│     ├── research_router → research API                       │
│     └── health_router   → health checks                      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Request/Response Cycle (Chat)

```
1. Client: WebSocket.connect("ws://localhost:8000/ws/chat")
2. Server:  ChatRoomManager.create_room() → returns conversation_id
3. Server:  Yields {"type": "connected", "conversation_id": "uuid"}
4. Client:  WebSocket.send({type: "message", content: "Hello"})
5. Server:  chat_router receives message
6. Server:  Routes to Supervisor.stream_response() based on intent
7. Server:  Supervisors streams tokens via HTTPX generator
8. Client:  Each token received, rendered with framer-motion
```

---

## 2. Implementation Status by Component

### Backend — Phase 1 (Command Center) ✅ COMPLETE

| Component | File Path | Status | Notes |
|-----------|-----------|--------|-------|
| FastAPI Application | `backend/app/main.py` | ✅ Complete | Lifespan events, router registration |
| Core Configuration | `backend/config.py` | ✅ Complete | Settings validation, directory creation |
| Database Layer | `backend/core/database.py` | ✅ Complete | SQLite conversations storage |
| WebSocket Handler | `backend/app/ws/chat.py` | ✅ Complete | Chat room manager, event streaming |
| Supervisor Agent | `backend/app/agents/supervisor.py` | ✅ Complete | Intent classification, LLM routing |
| LM Studio Client | `backend/app/agents/_lm_studio.py` | ✅ Complete | Synchronous HTTP calls for embeddings |

### Backend — Phase 2 (Knowledge Cluster) 🔄 PLANNED

| Component | File Path | Status | Notes |
|-----------|-----------|--------|-------|
| Document Upload | `backend/app/api/files.py` | 📋 Planned | Chunking, metadata extraction |
| RAG Retriever | `backend/app/agents/rag_retriever.py` | 📋 Planned | Hybrid search implementation |
| Vision Agent | `backend/app/agents/vision_agent.py` | 📋 Planned | Image analysis capabilities |
| File Processor | `backend/app/agents/file_processor.py` | 📋 Planned | Multi-format document parsing |

### Backend — Phase 3 (Research Cluster) 🔄 ACTIVE

| Component | File Path | Status | Notes |
|-----------|-----------|--------|-------|
| Web Scout Agent | `backend/app/agents/web_scout.py` | ✅ Complete | DDGS search, query variations, ranking |
| Scraper Agent | `backend/app/agents/scraper_agent.py` | ✅ Complete | trafilatura extraction, paywall detection |
| Fact Checker | `backend/app/agents/fact_checker.py` | ✅ Complete | Cross-source validation |
| Report Builder | `backend/app/agents/report_builder.py` | ✅ Complete | Markdown synthesis, disk save |
| Research Lead | `backend/app/agents/research_lead.py` | ✅ Complete | Pipeline orchestration |
| Research Graph | `backend/app/graph/research_graph.py` | ✅ Complete | LangGraph conditional edges |
| API Endpoints | `backend/app/api/research.py` | ✅ Complete | All 6 research endpoints |

### Frontend — Phase 1 (Command Center) ✅ COMPLETE

| Component | File Path | Status | Notes |
|-----------|-----------|--------|-------|
| App Shell Layout | `nexus-os-frontend/src/components/layout/AppShell.tsx` | ✅ Complete | Sidebar, tab navigation |
| Chat Components | `nexus-os-frontend/src/components/chat/ChatWindow.tsx` | ✅ Complete | Message rendering, streaming |
| Zustand Store | `nexus-os-frontend/src/stores/useAppStore.ts` | ✅ Complete | Global state management |
| WebSocket Hook | `nexus-os-frontend/src/hooks/useWebSocket.ts` | ✅ Complete | Connection, event handling |

### Frontend — Phase 3 (Research Tab) 🔄 ACTIVE

| Component | File Path | Status | Notes |
|-----------|-----------|--------|-------|
| Research Types | `nexus-os-frontend/src/types/research.ts` | ✅ Complete | Report, source, claim interfaces |
| Research Store | `nexus-os-frontend/src/stores/useResearchStore.ts` | ✅ Complete | Zustand store with immer |
| API Client | `nexus-os-frontend/src/lib/researchApi.ts` | ✅ Complete | Fetch functions for all endpoints |
| Pipeline Viz | `nexus-os-frontend/src/components/research/PipelineViz.tsx` | 🔄 In Progress | Animated node graph |

---

## 3. Current Known Limitations & WIP

### Functional Limitations

1. **LM Studio Dependency**
   - All LLM and embedding operations require LM Studio running locally on port 1234
   - No fallback to remote APIs configured
   - Vision model requires explicit configuration in `.env`

2. **Research Pipeline Retry Logic**
   - Only single retry for Web Scout if < 3 sources scraped
   - DDGS rate limiting may cause incomplete research runs
   - Fact checker confidence scoring uses simple keyword matching (not semantic)

3. **No Authentication/Authorization**
   - No user/session isolation — all conversations share same database
   - Not suitable for multi-user deployments without additional auth layer

4. **Database Limits**
   - SQLite file size limit (~14GB for WAL mode on Windows)
   - No connection pooling for high-concurrency scenarios

5. **Web Scraping Limitations**
   - trafilatura may fail on heavily obfuscated sites
   - Paywall detection heuristic-based, not perfect
   - SCRAPE_TIMEOUT_SECONDS default (15s) may be insufficient for slow sites

### In-Progress Work

| Item | Component | Progress | Notes |
|------|-----------|----------|-------|
| Pipeline Viz Animation | `PipelineViz.tsx` | 60% | Node rendering done; particle flow animation in progress |
| Report Viewer Markdown Renderer | `ReportViewer.tsx` | 40% | Basic markdown working; inline citation hover tooltips pending |
| Source Manager Filtering | `SourceManager.tsx` | 30% | Table structure done; filter/sort logic in progress |

### Known Bugs / Issues

1. **ChromaDB Collection Overwrite** — If same collection name used twice, old data is deleted rather than merged
2. **Research Graph Retry Logic** — May enter infinite loop if both conditions for retry and proceed are true simultaneously
3. **Fact Checker Edge Case** — Claims with identical keywords but different context may be incorrectly marked as verified

### Temporary Workarounds in Place

1. **Blocking HTTPX for Embeddings** — Uses synchronous `httpx.post` instead of async; works around ChromaDB threading model requirements
2. **Simple BM25 Implementation** — Naive keyword scoring rather than full BM25 formula due to complexity of implementing custom similarity functions in LangChain
3. **Direct ChromaDB Indexing (Phase 3)** — Bypasses A2A message bus for report indexing until Phase 5

---

## 4. Data Structures in Use

### Research Report Metadata

```python
{
    "slug": "quantum-computing-advances-2024",
    "topic": "quantum computing advances in 2024",
    "created_at": "2026-04-19T10:30:00Z",
    "source_count": 8,
    "avg_confidence": 0.87,
    "status": "complete",
    "job_id": "uuid-here",
    "chroma_collection": "nexus_research",
    "word_count": 1240,
    "tags": ["quantum computing", "2024", "technology"]
}
```

### Research Source Record

```python
{
    "url": "https://example.com/article",
    "url_hash": "abc123",
    "domain": "example.com",
    "title": "Article title",
    "scraped_at": "2026-04-19T10:30:00Z",
    "char_count": 4200,
    "quality_score": 0.82,
    "extraction_status": "success",  # success | paywall | timeout | error | http_error
    "error": None,
    "text": "Full cleaned article text..."
}
```

### Research Claim with Verification

```python
{
    "claim": "Quantum computers will achieve quantum supremacy in the next decade",
    "status": "unverified",  # verified | unverified | contradicted
    "confidence": 0.4,       # 0.0 - 1.0
    "source_urls": ["https://source1.com"],
    "contradiction_note": None
}
```

### WebSocket Event Structure

```python
{
    "type": "<event_type>",           # thinking | progress | chunk | done | error
    "agent_id": "Vector",             # Agent responsible (for thinking events)
    "stage": "searching",             # Pipeline stage (for progress events)
    "detail": "Query 1/3: ...",       # Human-readable status
    "content": "chunk of text...",    # LLM tokens or report content
    "data": {...}                     # Structured result data
}
```

---

## Summary

NEXUS OS is currently **fully functional for Phase 1 (Command Center)** with a working chat interface, WebSocket streaming, and conversation persistence. **Phase 2 (Knowledge Cluster) remains planned**, while **Phase 3 (Research Cluster) has all backend agents implemented** but frontend components are still in active development.

The architecture successfully implements the tiered agent hierarchy design, hybrid search capabilities, and live pipeline visualization. Remaining work focuses on completing the frontend research UI components and addressing known limitations around retry logic and web scraping robustness.
