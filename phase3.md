# PHASE 3 — Research Cluster: Deep Web Research
**Timeline:** Week 6–8 | **Status:** `planned`

---

## Table of Contents

1. [Goal & Deliverable](#1-goal--deliverable)
2. [Architecture Overview](#2-architecture-overview)
3. [Dependencies](#3-dependencies)
4. [Config Updates](#4-config-updates)
5. [Data Directory Structure](#5-data-directory-structure)
6. [Backend — Agent Personalities](#6-backend--agent-personalities)
7. [Backend — Agent Implementations](#7-backend--agent-implementations)
   - 7.1 [Web Scout Agent](#71-web-scout-agent)
   - 7.2 [Scraper Agent](#72-scraper-agent)
   - 7.3 [Fact Checker Agent](#73-fact-checker-agent)
   - 7.4 [Report Builder Agent](#74-report-builder-agent)
   - 7.5 [Research Lead Agent](#75-research-lead-agent)
8. [Backend — API Endpoints](#8-backend--api-endpoints)
9. [Backend — A2A Integration](#9-backend--a2a-integration)
10. [Backend — LangGraph Wiring](#10-backend--langgraph-wiring)
11. [Backend — Supervisor Routing Update](#11-backend--supervisor-routing-update)
12. [Frontend — State & Types](#12-frontend--state--types)
13. [Frontend — Research Tab](#13-frontend--research-tab)
    - 13.1 [New Research Subtab](#131-new-research-subtab)
    - 13.2 [Reports Library Subtab](#132-reports-library-subtab)
    - 13.3 [Source Manager Subtab](#133-source-manager-subtab)
    - 13.4 [Report Viewer](#134-report-viewer)
    - 13.5 [Agent Pipeline Visualization](#135-agent-pipeline-visualization)
14. [Frontend — API Client](#14-frontend--api-client)
15. [Frontend — Sidebar & AppShell Updates](#15-frontend--sidebar--appshell-updates)
16. [Testing Checklist](#16-testing-checklist)
17. [Acceptance Criteria](#17-acceptance-criteria)
18. [Week-by-Week Breakdown](#18-week-by-week-breakdown)

---

## 1. Goal & Deliverable

User types: `"Research quantum computing advances in 2024"`

Expected outcome:
1. Live pipeline progress shown in UI (each agent lights up as it runs)
2. Web Scout queries DuckDuckGo with multiple query variations
3. Scraper fetches and cleans content from top-ranked URLs
4. Fact Checker cross-validates claims across 2+ sources
5. Report Builder synthesizes a structured markdown report
6. Report saved to `./data/deep_research/{slug}/report.md`
7. Report auto-indexed in ChromaDB via Memory Archivist A2A call
8. Future query: `"Do I have any research on quantum computing?"` → RAG retrieves it

---

## 2. Architecture Overview

```
Supervisor (Nexus)
  └── Research Lead (new Tier 2 Domain Lead)
        ├── Web Scout        → duckduckgo-search, URL ranking
        ├── Scraper Agent    → httpx + trafilatura, clean text
        ├── Fact Checker     → cross-source validation, confidence scores
        └── Report Builder   → markdown synthesis, disk save, A2A → Memory Archivist

WebSocket /ws/chat
  └── streams: thinking | agent_switch | progress | chunk | done | error

New REST endpoints:
  GET  /api/research                         — list all saved reports
  GET  /api/research/{slug}                  — get report metadata + content
  DELETE /api/research/{slug}               — delete report + ChromaDB entries
  GET  /api/research/sources                 — list all scraped sources
  POST /api/research/start                   — trigger research (returns job_id)
  GET  /api/research/status/{job_id}         — poll job status (SSE fallback)
```

---

## 3. Dependencies

### 3.1 Python (add to `backend/requirements.txt`)

```
duckduckgo-search>=6.2.0
trafilatura>=1.12.0
httpx>=0.27.0          # already present — verify version
langchain-core>=0.3.0  # already present — verify
langgraph>=0.2.0
python-slugify>=8.0.0
aiofiles>=24.1.0       # already present — verify
```

Install command:
```bash
pip install duckduckgo-search trafilatura langgraph python-slugify
```

### 3.2 Node.js (add to `nexus-os-frontend/package.json`)

```json
"react-markdown": "^9.0.1",
"remark-gfm": "^4.0.0",
"rehype-highlight": "^7.0.0",
"highlight.js": "^11.10.0",
"react-syntax-highlighter": "^15.5.0",
"@types/react-syntax-highlighter": "^15.5.13"
```

Install command:
```bash
cd nexus-os-frontend
npm install react-markdown remark-gfm rehype-highlight highlight.js react-syntax-highlighter @types/react-syntax-highlighter
```

---

## 4. Config Updates

**File:** `backend/config.py`

Add the following fields to the `Settings` class:

```python
# Phase 3 — Research Cluster
DEEP_RESEARCH_DIR: Path = DATA_DIR / "deep_research"
MAX_SEARCH_RESULTS: int = 10          # URLs returned by Web Scout per query
MAX_SCRAPE_CONCURRENCY: int = 5       # parallel httpx requests in Scraper
SCRAPE_TIMEOUT_SECONDS: int = 15      # per-URL timeout
MIN_SOURCES_FOR_FACT_CHECK: int = 2   # min independent sources for a claim to pass
RESEARCH_CHUNK_SIZE: int = 800        # chunk size for research report indexing
RESEARCH_CHUNK_OVERLAP: int = 100
DUCKDUCKGO_REGION: str = "wt-wt"      # worldwide, change to "us-en" for US results
DUCKDUCKGO_SAFESEARCH: str = "off"
MAX_QUERY_VARIATIONS: int = 3         # how many query rewrites Web Scout generates
MAX_FACT_CLAIMS: int = 10             # max claims sent to Fact Checker per report
```

Add to `validate_settings()`:
```python
settings.DEEP_RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
```

Add to `PHASE_STATUS`:
```python
"phase_3": {"name": "Research Cluster", "status": "active", "weeks": "6-8"},
```

---

## 5. Data Directory Structure

```
data/
└── deep_research/
    └── {slug}/                        # e.g. quantum-computing-advances-2024
        ├── report.md                  # final synthesized report
        ├── metadata.json              # topic, date, source_count, confidence, job_id
        ├── sources/
        │   ├── {url_hash}.json        # raw scraped content + metadata per source
        │   └── ...
        └── fact_check.json            # all claims + per-claim confidence + source refs
```

**`metadata.json` schema:**
```json
{
  "slug": "quantum-computing-advances-2024",
  "topic": "quantum computing advances in 2024",
  "created_at": "2026-04-19T10:30:00Z",
  "source_count": 8,
  "avg_confidence": 0.87,
  "status": "complete",
  "job_id": "uuid",
  "chroma_collection": "nexus_research",
  "word_count": 1240,
  "tags": ["quantum computing", "2024", "technology"]
}
```

**`sources/{url_hash}.json` schema:**
```json
{
  "url": "https://example.com/article",
  "url_hash": "abc123",
  "domain": "example.com",
  "title": "Article title",
  "scraped_at": "2026-04-19T10:30:00Z",
  "char_count": 4200,
  "quality_score": 0.82,
  "extraction_status": "success",
  "error": null,
  "text": "Full cleaned article text..."
}
```

---

## 6. Backend — Agent Personalities

Create new YAML files under `backend/personalities/`:

### 6.1 `web_scout.yaml`

```yaml
name: web_scout
display_name: Vector
description: Web search specialist — finds and ranks relevant URLs
tier: 3
domain: research

system_prompt: |
  You are Vector, a precision web search agent. Your job is to find the most
  authoritative and relevant web sources for a given research topic.

  Given a research topic, you:
  1. Generate {max_variations} distinct search query variations
  2. Prioritize academic sources, reputable news outlets, and primary sources
  3. Avoid duplicate domains
  4. Score URLs by apparent authority and topical relevance
  5. Return only the top {max_results} unique, high-quality URLs

  Output format:
  - Return a JSON array of objects: {url, title, domain, relevance_score, query_used}
  - relevance_score: 0.0–1.0 (1.0 = highly relevant, authoritative primary source)
  - Never hallucinate URLs — only return URLs from actual search results
```

### 6.2 `scraper_agent.yaml`

```yaml
name: scraper_agent
display_name: Fetch
description: Web content extractor — cleans raw HTML into readable text
tier: 3
domain: research

system_prompt: |
  You are Fetch, a web content extraction agent. Your job is to retrieve and
  clean article text from URLs for research purposes.

  You extract:
  - Main article body (not nav, ads, footers)
  - Publication date when available
  - Author when available
  - Key facts and statistics

  You handle gracefully:
  - Paywalls (flag as paywall, return partial content if visible)
  - Timeouts (flag as timeout, skip)
  - Non-HTML content (flag as unsupported)
  - 4xx/5xx errors (flag with status code)

  Quality scoring criteria:
  - Word count (>500 = good, <200 = poor)
  - Presence of dates, numbers, named entities (higher = better quality)
  - No quality score above 0.9 unless text is rich and substantive
```

### 6.3 `fact_checker.yaml`

```yaml
name: fact_checker
display_name: Verity
description: Fact validation agent — cross-checks claims across sources
tier: 3
domain: research

system_prompt: |
  You are Verity, a fact-checking agent. Your job is to validate research claims
  by finding corroboration across multiple independent sources.

  For each claim:
  1. Search the scraped source texts for supporting evidence
  2. A claim is VERIFIED if it appears in {min_sources}+ independent sources
  3. A claim is UNVERIFIED if it appears in only 1 source
  4. A claim is CONTRADICTED if sources disagree — flag the disagreement
  5. Assign a confidence score 0.0–1.0

  Confidence scoring:
  - 1.0 = Verified in 3+ authoritative sources with consistent details
  - 0.8 = Verified in 2+ sources, minor wording differences
  - 0.6 = Verified in 2+ sources but one is lower quality
  - 0.4 = Single source, reputable
  - 0.2 = Single source, low quality or unclear
  - 0.0 = Contradicted across sources

  Output format: JSON array of claims with fields:
  {claim, confidence, status, source_urls, contradiction_note}
```

### 6.4 `report_builder.yaml`

```yaml
name: report_builder
display_name: Scribe
description: Research synthesis agent — builds structured reports from verified facts
tier: 3
domain: research

system_prompt: |
  You are Scribe, a research report synthesis agent. You produce professional,
  structured research reports from verified facts and scraped sources.

  Your reports always include:
  1. **Executive Summary** (3–5 sentences, key findings only)
  2. **Key Findings** (bullet points, verified facts with confidence badges)
  3. **Detailed Analysis** (narrative synthesis of findings by theme/subtopic)
  4. **Contradictions & Uncertainties** (flag any disputed claims)
  5. **Sources** (numbered list with URL, domain, quality score)
  6. **Methodology** (queries used, sources attempted vs scraped, date of research)

  Style guidelines:
  - Factual, neutral tone
  - No speculation beyond what sources support
  - Cite sources inline as [1], [2], etc.
  - Confidence badges: [HIGH], [MEDIUM], [LOW] after each key finding
  - If confidence is below 0.5, mark the finding explicitly as unverified

  Output: Valid markdown only. No preamble or explanation outside the report.
```

### 6.5 `research_lead.yaml`

```yaml
name: research_lead
display_name: Atlas
description: Research orchestration agent — manages the full research pipeline
tier: 2
domain: research

system_prompt: |
  You are Atlas, the Research Lead. You orchestrate end-to-end research pipelines
  by coordinating specialist agents: Vector (web search), Fetch (scraping),
  Verity (fact-checking), and Scribe (report building).

  Your responsibilities:
  1. Decompose the user's research topic into concrete search questions
  2. Coordinate the pipeline sequentially: Scout → Scraper → Checker → Builder
  3. Stream progress updates to the user at each step
  4. Handle failures gracefully (too few sources → retry with different queries)
  5. Ensure the final report is complete before declaring success

  Pipeline stages and user-visible messages:
  - "Generating search queries..." (Web Scout starting)
  - "Found {n} sources, fetching content..." (Scraper starting)
  - "Validating {n} claims across sources..." (Fact Checker starting)
  - "Synthesizing report..." (Report Builder starting)
  - "Research complete. Report saved." (Done)

  If fewer than 3 sources are successfully scraped, retry Scout with broader queries.
  If Fact Checker returns all claims as unverified, note data scarcity in report.
```

---

## 7. Backend — Agent Implementations

### 7.1 Web Scout Agent

**File:** `backend/app/agents/web_scout.py`

**Class:** `WebScoutAgent`

**Responsibilities:**
- Accept a raw research topic string
- Generate `MAX_QUERY_VARIATIONS` distinct query rewrites via LM Studio
- Run each query through `duckduckgo_search.DDGS().text()`
- Deduplicate results by URL and domain
- Score and rank by domain authority heuristics + title relevance
- Return top `MAX_SEARCH_RESULTS` results

**Key methods:**

```python
async def generate_query_variations(self, topic: str) -> list[str]:
    """Use LM Studio to rewrite the topic into N search query variations."""
    # prompt: "Generate {n} distinct DuckDuckGo search queries for: {topic}"
    # parse LLM response as newline-separated queries
    # fallback: return [topic] if parsing fails

async def search_single_query(self, query: str) -> list[dict]:
    """Run one DDGS query, return list of {url, title, body, source} dicts."""
    # use duckduckgo_search.DDGS().text(query, max_results=MAX_SEARCH_RESULTS)
    # run in asyncio executor (DDGS is sync)

async def score_and_rank(self, results: list[dict], topic: str) -> list[dict]:
    """
    Score each result:
    - domain_score: known authoritative domains (arxiv, nature, ieee, .gov, .edu) = 1.0
    - title_relevance: keyword overlap with topic words / total topic words
    - final_score = 0.4 * domain_score + 0.6 * title_relevance
    Sort descending, deduplicate by domain (keep highest score per domain).
    """

async def run(self, topic: str) -> AsyncGenerator[dict, None]:
    """
    Yields WebSocket events:
      {"type": "progress", "agent": "Vector", "stage": "searching", "detail": "Query 1/3: ..."}
      {"type": "progress", "agent": "Vector", "stage": "ranking", "detail": "Ranked 24 results → top 10"}
      {"type": "result", "agent": "Vector", "data": [list of scored URL dicts]}
    """
```

**Error handling:**
- `RatelimitException` from DDGS → wait 2s, retry once, then yield error event
- Empty results for a query variation → log and continue to next variation
- If all queries return 0 results → yield `{"type": "error", "agent": "Vector", "detail": "No results found"}`

---

### 7.2 Scraper Agent

**File:** `backend/app/agents/scraper_agent.py`

**Class:** `ScraperAgent`

**Responsibilities:**
- Accept list of URL dicts from Web Scout
- Fetch HTML concurrently (semaphore-limited to `MAX_SCRAPE_CONCURRENCY`)
- Extract clean text using `trafilatura.extract()`
- Score content quality
- Save each result to `data/deep_research/{slug}/sources/{url_hash}.json`
- Return list of successfully scraped sources

**Key methods:**

```python
async def fetch_url(self, session: httpx.AsyncClient, url: str) -> dict:
    """
    GET with timeout=SCRAPE_TIMEOUT_SECONDS, follow_redirects=True.
    Returns {url, status_code, html, error}.
    Catches: httpx.TimeoutException → status="timeout"
             httpx.RequestError    → status="error"
             4xx/5xx               → status="http_error", code=N
    """

def extract_text(self, html: str, url: str) -> dict:
    """
    Call trafilatura.extract(html, include_comments=False, include_tables=True).
    If result is None or len < 200 chars → quality_score = 0.1
    Compute quality_score:
      - word_count score: min(word_count / 500, 1.0) * 0.5
      - has_numbers: 0.2 if re.search(r'\d', text) else 0
      - has_dates: 0.3 if date pattern found else 0
    Return {text, word_count, quality_score, title, date, author}
    """

async def run(self, slug: str, urls: list[dict]) -> AsyncGenerator[dict, None]:
    """
    Yields WebSocket events:
      {"type": "progress", "agent": "Fetch", "stage": "scraping", "detail": "Fetching 10 URLs..."}
      {"type": "progress", "agent": "Fetch", "stage": "scraped", "detail": "3/10 complete — example.com ✓"}
      {"type": "progress", "agent": "Fetch", "stage": "scraped", "detail": "4/10 — paywall.com ✗ (paywall)"}
      {"type": "result", "agent": "Fetch", "data": [list of source dicts], "success_count": N}
    Save each source to disk as {url_hash}.json where url_hash = sha256(url)[:12].
    """
```

**Paywall detection heuristics:**
- Text length < 300 AND page title contains "subscribe", "sign in", "paywall"
- Meta tags `paywall` or `isAccessibleForFree: false`
- Mark as `extraction_status: "paywall"`, `quality_score: 0.1`

---

### 7.3 Fact Checker Agent

**File:** `backend/app/agents/fact_checker.py`

**Class:** `FactCheckerAgent`

**Responsibilities:**
- Accept synthesized source texts
- Use LM Studio to extract key factual claims from the combined text
- For each claim, search which source texts contain supporting evidence
- Assign confidence scores and verification status
- Save `fact_check.json` to the research directory
- Return structured claim objects

**Key methods:**

```python
async def extract_claims(self, sources: list[dict], topic: str) -> list[str]:
    """
    Prompt LM Studio:
      "From these research sources about {topic}, extract up to {MAX_FACT_CLAIMS}
       distinct factual claims as a JSON array of strings. Claims must be:
       - Specific and verifiable (include numbers, dates, names where present)
       - Not redundant
       - Directly relevant to {topic}"
    Parse JSON response. Fallback: split on newlines if JSON parse fails.
    """

def check_claim_in_source(self, claim: str, source_text: str) -> float:
    """
    Keyword-based similarity: extract key noun phrases from claim,
    check what fraction appear in source_text (case-insensitive).
    Returns 0.0–1.0 hit rate.
    """

async def verify_claims(self, claims: list[str], sources: list[dict]) -> list[dict]:
    """
    For each claim:
      1. Run check_claim_in_source() against all source texts
      2. Count sources with hit_rate > 0.5 as "supporting"
      3. supporting_count >= MIN_SOURCES_FOR_FACT_CHECK → status="verified"
         supporting_count == 1                          → status="unverified"
         hit_rate inconsistency detected                → status="contradicted"
      4. confidence = min(supporting_count / 3, 1.0) * avg_quality_of_supporting_sources
    Return list of {claim, status, confidence, source_urls, contradiction_note}
    """

async def run(self, slug: str, sources: list[dict], topic: str) -> AsyncGenerator[dict, None]:
    """
    Yields:
      {"type": "progress", "agent": "Verity", "stage": "extracting", "detail": "Extracting claims..."}
      {"type": "progress", "agent": "Verity", "stage": "checking", "detail": "Checking claim 3/10..."}
      {"type": "result", "agent": "Verity", "data": [claim objects], "avg_confidence": 0.82}
    Save to data/deep_research/{slug}/fact_check.json
    """
```

---

### 7.4 Report Builder Agent

**File:** `backend/app/agents/report_builder.py`

**Class:** `ReportBuilderAgent`

**Responsibilities:**
- Accept verified claims, sources list, and topic
- Prompt LM Studio to synthesize a full structured markdown report
- Save report to `data/deep_research/{slug}/report.md`
- Write `metadata.json` to the same directory
- Trigger A2A call to index report in ChromaDB (Memory Archivist)
- Return report content and metadata

**Key methods:**

```python
async def build_report(
    self,
    topic: str,
    claims: list[dict],
    sources: list[dict],
    queries_used: list[str],
) -> str:
    """
    Build a prompt with:
      - topic
      - verified claims (with confidence labels)
      - source list (url, domain, quality_score)
      - queries used
    Stream LM Studio response.
    Return complete markdown string.
    """

def save_to_disk(self, slug: str, report_md: str, metadata: dict) -> Path:
    """
    Write data/deep_research/{slug}/report.md
    Write data/deep_research/{slug}/metadata.json
    Return path to report.md
    """

async def index_in_chroma(self, slug: str, report_md: str, metadata: dict) -> None:
    """
    Chunk report_md with RESEARCH_CHUNK_SIZE / RESEARCH_CHUNK_OVERLAP.
    Add chunks to ChromaDB collection "nexus_research" with metadata:
      {type: "research_report", slug, topic, created_at, source_count, avg_confidence}
    This is the A2A Memory Archivist call (direct ChromaDB call in Phase 3;
    replace with A2A message bus call in Phase 5).
    """

def generate_slug(self, topic: str) -> str:
    """slugify(topic) with max_length=60, separator='-'"""

async def run(
    self,
    slug: str,
    topic: str,
    claims: list[dict],
    sources: list[dict],
    queries_used: list[str],
) -> AsyncGenerator[dict, None]:
    """
    Yields:
      {"type": "progress", "agent": "Scribe", "stage": "synthesizing", "detail": "Writing report..."}
      {"type": "chunk", "agent": "Scribe", "content": "# Research Report..."}  (streamed tokens)
      {"type": "progress", "agent": "Scribe", "stage": "saving", "detail": "Saving to disk..."}
      {"type": "progress", "agent": "Scribe", "stage": "indexing", "detail": "Indexing in knowledge base..."}
      {"type": "result", "agent": "Scribe", "slug": slug, "path": str(path), "metadata": metadata}
    """
```

---

### 7.5 Research Lead Agent

**File:** `backend/app/agents/research_lead.py`

**Class:** `ResearchLead`

**Responsibilities:**
- Entry point for the research pipeline
- Manages sequential execution: Scout → Scraper → Checker → Builder
- Streams consolidated progress events over WebSocket
- Handles retries (if < 3 sources scraped, retry Scout with broader queries)
- Exposes `run_research(topic, job_id)` as the main async entry point

**Key methods:**

```python
async def run_research(
    self,
    topic: str,
    job_id: str,
    session_id: str,
) -> AsyncGenerator[dict, None]:
    """
    Full pipeline:

    STEP 1 — Web Scout
      yield {"type": "thinking", "agent": "Atlas", "detail": "Planning research..."}
      async for event in web_scout.run(topic): yield event
      urls = extract result from Scout events
      if len(urls) == 0: yield error and return

    STEP 2 — Scraper Agent
      yield {"type": "agent_switch", "from": "Atlas", "to": "Fetch"}
      async for event in scraper.run(slug, urls): yield event
      sources = extract scraped sources
      if len(sources) < 3:
        yield retry notice
        async for event in web_scout.run(broader_topic): yield event  # retry
        async for event in scraper.run(slug, new_urls): yield event
      if len(sources) == 0: yield error and return

    STEP 3 — Fact Checker
      yield {"type": "agent_switch", "from": "Fetch", "to": "Verity"}
      async for event in fact_checker.run(slug, sources, topic): yield event
      claims = extract verified claims

    STEP 4 — Report Builder
      yield {"type": "agent_switch", "from": "Verity", "to": "Scribe"}
      async for event in report_builder.run(slug, topic, claims, sources, queries): yield event

    STEP 5 — Done
      yield {
        "type": "done",
        "agent": "Atlas",
        "detail": "Research complete.",
        "slug": slug,
        "metadata": metadata,
      }
      save job status to DB
    """

async def get_research_intent(self, message: str) -> bool:
    """
    Return True if the message is a research request.
    Patterns: "research X", "investigate X", "find out about X",
              "deep dive into X", "look into X", "study X"
    """
```

**Job tracking** — add to `backend/core/database.py`:

```python
# New table: research_jobs
# Columns: job_id (PK), topic, slug, status, created_at, completed_at, error
async def create_research_job(job_id, topic, slug) -> None
async def update_research_job_status(job_id, status, error=None) -> None
async def get_research_job(job_id) -> dict | None
async def list_research_jobs() -> list[dict]
```

---

## 8. Backend — API Endpoints

**File:** `backend/app/api/research.py` (new file)

```python
router = APIRouter(prefix="/api/research", tags=["research"])
```

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/research` | List all completed research reports (metadata only) |
| `GET` | `/api/research/{slug}` | Get single report — metadata + full markdown content |
| `DELETE` | `/api/research/{slug}` | Delete report files + ChromaDB entries + DB record |
| `GET` | `/api/research/{slug}/sources` | List all sources for a specific report |
| `GET` | `/api/research/sources` | List all sources across all reports |
| `POST` | `/api/research/start` | Start research job (returns `job_id`; pipeline runs via WS) |
| `GET` | `/api/research/status/{job_id}` | Get job status: `pending/running/complete/failed` |

**`POST /api/research/start` request body:**
```json
{
  "topic": "quantum computing advances in 2024",
  "session_id": "uuid"
}
```

**`POST /api/research/start` response:**
```json
{
  "job_id": "uuid",
  "slug": "quantum-computing-advances-in-2024",
  "status": "pending",
  "message": "Research job queued. Connect WebSocket to stream progress."
}
```

**Register router** in `backend/app/main.py`:
```python
from backend.app.api.research import router as research_router
app.include_router(research_router)
```

---

## 9. Backend — A2A Integration

**File:** `backend/app/agents/report_builder.py` → `index_in_chroma()`

Phase 3 implements direct ChromaDB indexing (no Redis hop needed yet).
The A2A message bus will be used in Phase 5 when the Memory Archivist agent is a separate process.

For now, `index_in_chroma()` directly calls `backend/db/vector_store.py`:

```python
from backend.db.vector_store import get_vector_store

async def index_in_chroma(self, slug, report_md, metadata):
    vs = await get_vector_store()
    chunks = self._chunk_text(report_md)
    ids = [f"research_{slug}_{i}" for i in range(len(chunks))]
    metadatas = [{**metadata, "chunk_index": i} for i in range(len(chunks))]
    await asyncio.to_thread(vs.collection.add, documents=chunks, ids=ids, metadatas=metadatas)
```

**ChromaDB collection name:** `nexus_research` (separate from `nexus_files` used by Phase 2)

Update `backend/db/vector_store.py` to support multiple named collections:
```python
def get_collection(name: str = "nexus_files") -> chromadb.Collection:
    """Return or create a collection by name."""
```

---

## 10. Backend — LangGraph Wiring

**File:** `backend/app/graph/research_graph.py` (new file)

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
import operator

class ResearchState(TypedDict):
    topic: str
    job_id: str
    slug: str
    session_id: str
    queries: list[str]
    urls: list[dict]
    sources: list[dict]
    claims: list[dict]
    report_md: str
    metadata: dict
    errors: Annotated[list[str], operator.add]
    status: str  # "searching" | "scraping" | "checking" | "building" | "done" | "failed"
    retry_count: int

def build_research_graph() -> StateGraph:
    graph = StateGraph(ResearchState)

    graph.add_node("web_scout",    web_scout_node)
    graph.add_node("scraper",      scraper_node)
    graph.add_node("fact_checker", fact_checker_node)
    graph.add_node("report_builder", report_builder_node)

    graph.set_entry_point("web_scout")

    graph.add_conditional_edges(
        "web_scout",
        should_proceed_to_scraper,
        {"proceed": "scraper", "failed": END}
    )
    graph.add_conditional_edges(
        "scraper",
        should_proceed_to_fact_checker,
        {"proceed": "fact_checker", "retry": "web_scout", "failed": END}
    )
    graph.add_edge("fact_checker", "report_builder")
    graph.add_edge("report_builder", END)

    return graph.compile()

# Condition functions:
def should_proceed_to_scraper(state: ResearchState) -> str:
    return "proceed" if len(state["urls"]) > 0 else "failed"

def should_proceed_to_fact_checker(state: ResearchState) -> str:
    if len(state["sources"]) >= 3:
        return "proceed"
    if state["retry_count"] < 1:
        return "retry"
    return "failed" if len(state["sources"]) == 0 else "proceed"
```

**Supervisor routing update** — in `backend/app/agents/supervisor.py`, before calling LM Studio, check research intent:

```python
from backend.app.agents.research_lead import ResearchLead
research_lead = ResearchLead()

# In stream_response():
if await research_lead.get_research_intent(user_message):
    async for event in research_lead.run_research(user_message, job_id, session_id):
        yield event
    return
# else: proceed to normal LM Studio chat
```

---

## 11. Backend — Supervisor Routing Update

**File:** `backend/app/agents/knowledge_lead.py`

Add research intent pattern to `classify_intent()`:

```python
RESEARCH_PATTERNS = [
    r"\b(research|investigate|deep dive|look into|study|analyze)\b",
    r"\bresearch\s+(topic|question|query|about)\b",
    r"\bfind out (everything|all|more) about\b",
]

def classify_intent(self, message: str, has_image: bool = False) -> str:
    # ... existing checks ...
    if any(re.search(p, lowered) for p in self.RESEARCH_PATTERNS):
        return "research"
    # ... rest of method
```

In `route()`, add:
```python
if intent == "research":
    yield {"type": "agent_switch", "from": "Aria", "to": "Atlas", "content": ""}
    async for event in research_lead.route(session_id, user_message, model):
        yield event
    return
```

---

## 12. Frontend — State & Types

### 12.1 Types

**File:** `nexus-os-frontend/src/types/research.ts` (new file)

```typescript
export interface ResearchReport {
  slug: string;
  topic: string;
  created_at: string;
  source_count: number;
  avg_confidence: number;
  status: "pending" | "running" | "complete" | "failed";
  job_id: string;
  word_count: number;
  tags: string[];
}

export interface ResearchSource {
  url: string;
  url_hash: string;
  domain: string;
  title: string;
  scraped_at: string;
  char_count: number;
  quality_score: number;
  extraction_status: "success" | "paywall" | "timeout" | "error" | "http_error";
  error: string | null;
}

export interface ResearchClaim {
  claim: string;
  status: "verified" | "unverified" | "contradicted";
  confidence: number;
  source_urls: string[];
  contradiction_note: string | null;
}

export type PipelineStage =
  | "idle"
  | "searching"
  | "ranking"
  | "scraping"
  | "checking"
  | "building"
  | "saving"
  | "indexing"
  | "complete"
  | "failed";

export interface PipelineAgentState {
  id: "Atlas" | "Vector" | "Fetch" | "Verity" | "Scribe";
  label: string;
  stage: PipelineStage;
  detail: string;
  status: "idle" | "active" | "complete" | "error";
}

export interface ResearchJob {
  job_id: string;
  topic: string;
  slug: string;
  status: "pending" | "running" | "complete" | "failed";
  pipeline: PipelineAgentState[];
  report?: ResearchReport;
  error?: string;
}
```

### 12.2 Zustand Store

**File:** `nexus-os-frontend/src/stores/useResearchStore.ts` (new file)

```typescript
import { create } from "zustand";
import { immer } from "zustand/middleware/immer";
import { devtools } from "zustand/middleware";
import type { ResearchJob, ResearchReport, ResearchSource, PipelineAgentState } from "@/types/research";

interface ResearchState {
  // Active job
  activeJob: ResearchJob | null;
  // Completed reports
  reports: ResearchReport[];
  // Sources (all, across reports)
  sources: ResearchSource[];
  // UI state
  activeSubTab: "new" | "library" | "sources";
  viewingSlug: string | null;
  viewingReport: { content: string; metadata: ResearchReport } | null;
  isLoading: boolean;

  // Actions
  startJob: (topic: string, jobId: string, slug: string) => void;
  updatePipelineAgent: (agentId: string, updates: Partial<PipelineAgentState>) => void;
  completeJob: (report: ResearchReport) => void;
  failJob: (error: string) => void;
  setReports: (reports: ResearchReport[]) => void;
  setSources: (sources: ResearchSource[]) => void;
  setActiveSubTab: (tab: "new" | "library" | "sources") => void;
  openReport: (slug: string, content: string, metadata: ResearchReport) => void;
  closeReport: () => void;
  setLoading: (loading: boolean) => void;
}

const INITIAL_PIPELINE: PipelineAgentState[] = [
  { id: "Atlas", label: "Research Lead", stage: "idle", detail: "", status: "idle" },
  { id: "Vector", label: "Web Scout",    stage: "idle", detail: "", status: "idle" },
  { id: "Fetch",  label: "Scraper",      stage: "idle", detail: "", status: "idle" },
  { id: "Verity", label: "Fact Checker", stage: "idle", detail: "", status: "idle" },
  { id: "Scribe", label: "Report Builder",stage: "idle", detail: "", status: "idle" },
];

export const useResearchStore = create<ResearchState>()(
  devtools(
    immer((set) => ({
      activeJob: null,
      reports: [],
      sources: [],
      activeSubTab: "new",
      viewingSlug: null,
      viewingReport: null,
      isLoading: false,

      startJob: (topic, jobId, slug) =>
        set((s) => {
          s.activeJob = {
            job_id: jobId,
            topic,
            slug,
            status: "running",
            pipeline: INITIAL_PIPELINE.map((a) => ({ ...a })),
          };
        }),

      updatePipelineAgent: (agentId, updates) =>
        set((s) => {
          if (!s.activeJob) return;
          const agent = s.activeJob.pipeline.find((a) => a.id === agentId);
          if (agent) Object.assign(agent, updates);
        }),

      completeJob: (report) =>
        set((s) => {
          if (s.activeJob) s.activeJob.status = "complete";
          s.reports.unshift(report);
        }),

      failJob: (error) =>
        set((s) => {
          if (s.activeJob) {
            s.activeJob.status = "failed";
            s.activeJob.error = error;
          }
        }),

      setReports: (reports) => set((s) => { s.reports = reports; }),
      setSources: (sources) => set((s) => { s.sources = sources; }),
      setActiveSubTab: (tab) => set((s) => { s.activeSubTab = tab; }),
      openReport: (slug, content, metadata) =>
        set((s) => {
          s.viewingSlug = slug;
          s.viewingReport = { content, metadata };
        }),
      closeReport: () => set((s) => { s.viewingSlug = null; s.viewingReport = null; }),
      setLoading: (loading) => set((s) => { s.isLoading = loading; }),
    }))
  )
);
```

---

## 13. Frontend — Research Tab

**File:** `nexus-os-frontend/src/components/tabs/ResearchTab.tsx` (new file)

Top-level tab component. Manages subtab routing.

```typescript
type ResearchSubTab = "new" | "library" | "sources";

// Subtab navigation bar with 3 options: New Research | Reports Library | Source Manager
// Renders active subtab component based on useResearchStore().activeSubTab
// Conditionally renders ReportViewer overlay if viewingSlug is set
```

---

### 13.1 New Research Subtab

**File:** `nexus-os-frontend/src/components/research/NewResearch.tsx`

**UI Elements:**
- Large textarea: `"What do you want to research?"` placeholder
- `Research` button (primary, disabled while job running)
- Live pipeline visualization (see §13.5) shown once job starts
- Completion card: report title, confidence score, source count, "View Report" button

**Behavior:**
1. User types topic, clicks Research
2. Call `POST /api/research/start` → get `job_id`
3. WebSocket connection receives events → update store via `updatePipelineAgent()`
4. On `type: "done"` event → call `completeJob()` + show completion card
5. On `type: "error"` → call `failJob()` + show error state with retry button

**Progress stages shown per agent:**
```
[ Atlas — Research Lead ]  ●  Planning research...
[ Vector — Web Scout    ]  ●  Generating 3 query variations...
[ Fetch — Scraper       ]  ◐  Fetching 10 URLs (4/10 complete)
[ Verity — Fact Checker ]  ○  Waiting...
[ Scribe — Report Builder] ○  Waiting...
```

Icons: `○` idle, `◐` active (spinning), `●` complete, `✗` error

---

### 13.2 Reports Library Subtab

**File:** `nexus-os-frontend/src/components/research/ReportsLibrary.tsx`

**UI Elements:**
- Search bar (filter by topic/tag)
- Sort dropdown: `Latest | Oldest | Highest Confidence | Most Sources`
- Card grid (2 columns on large screen, 1 on mobile)

**Each `ReportCard` shows:**
- Topic (title)
- Date created (relative: "2 days ago")
- Source count badge: `8 sources`
- Avg confidence badge: `HIGH` / `MEDIUM` / `LOW` with color coding
  - HIGH: avg_confidence ≥ 0.75 → green
  - MEDIUM: 0.5–0.74 → amber
  - LOW: < 0.5 → red
- Word count
- Tags (up to 3 shown, remainder as `+N more`)
- "View Report" button → opens ReportViewer
- Delete button (with confirmation dialog)

**On mount:** `GET /api/research` → `setReports(data)`

---

### 13.3 Source Manager Subtab

**File:** `nexus-os-frontend/src/components/research/SourceManager.tsx`

**UI Elements:**
- Filter bar: filter by report slug, extraction status, quality score range
- Sort: Domain | Quality Score | Date | Status
- Data table with columns:
  - Domain (favicon + name)
  - URL (truncated, clickable → opens in new tab)
  - Report (which research report this came from)
  - Quality Score (0.0–1.0 with progress bar visualization)
  - Status badge: `success` (green) / `paywall` (amber) / `timeout` (red) / `error` (red)
  - Scraped date
  - Char count
- Pagination: 25 rows per page

**On mount:** `GET /api/research/sources` → `setSources(data)`

---

### 13.4 Report Viewer

**File:** `nexus-os-frontend/src/components/research/ReportViewer.tsx`

Full-screen modal overlay (or side panel on large screens).

**UI Elements:**
- Close button (top right)
- Report metadata header:
  - Topic (h1)
  - Date | Source count | Avg confidence badge | Word count
- Markdown renderer using `react-markdown` + `remark-gfm` + `rehype-highlight`
- Custom renderers:
  - `[HIGH]` / `[MEDIUM]` / `[LOW]` tokens → colored inline badges
  - Inline citations `[1]`, `[2]` → hover tooltip with source URL
  - Code blocks → syntax highlighted via `react-syntax-highlighter`
- Sources accordion (collapsed by default) — lists all sources with quality scores
- "Export" button → triggers browser download of `report.md`
- "Ask about this" button → pre-fills chat with: `"Based on my research about {topic}, ..."`

**Fetch report content:** `GET /api/research/{slug}` on `viewingSlug` change

---

### 13.5 Agent Pipeline Visualization

**File:** `nexus-os-frontend/src/components/research/PipelineViz.tsx`

Animated node graph showing agents communicating during research.

**Layout:**
```
[Atlas] ──→ [Vector] ──→ [Fetch] ──→ [Verity] ──→ [Scribe]
```

**Per-node state:**
- `idle`: dim circle, grey
- `active`: bright circle, pulsing glow animation (Framer Motion `animate: scale`)
- `complete`: solid filled circle, checkmark icon
- `error`: red circle, X icon

**Animated arrows:**
- Inactive arrow: grey dashed line
- Active arrow: animated gradient line (left→right particle flow using Framer Motion)
- Use `motion.path` on SVG lines between nodes

**Detail text:**
Below each node, a small text label showing `agent.detail` (e.g., `"4/10 scraped"`)
Animate text changes with `AnimatePresence` + `motion.p` fadeIn/Out

**Implementation notes:**
- Pure Framer Motion + SVG (no Three.js needed for this component)
- Nodes positioned in a horizontal row with flex
- SVG overlay for arrows using absolute positioning
- Entire component width: 100% of parent container

---

## 14. Frontend — API Client

**File:** `nexus-os-frontend/src/lib/researchApi.ts` (new file)

```typescript
import { API_BASE_URL } from "@/lib/constants";
import type { ResearchReport, ResearchSource } from "@/types/research";

export async function startResearch(topic: string, sessionId: string) {
  const res = await fetch(`${API_BASE_URL}/api/research/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ topic, session_id: sessionId }),
  });
  if (!res.ok) throw new Error(`Failed to start research: ${res.statusText}`);
  return res.json() as Promise<{ job_id: string; slug: string; status: string }>;
}

export async function listReports(): Promise<ResearchReport[]> {
  const res = await fetch(`${API_BASE_URL}/api/research`);
  if (!res.ok) throw new Error("Failed to fetch reports");
  return res.json();
}

export async function getReport(slug: string): Promise<{ content: string; metadata: ResearchReport }> {
  const res = await fetch(`${API_BASE_URL}/api/research/${slug}`);
  if (!res.ok) throw new Error(`Report not found: ${slug}`);
  return res.json();
}

export async function deleteReport(slug: string): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/api/research/${slug}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`Failed to delete report: ${slug}`);
}

export async function listAllSources(): Promise<ResearchSource[]> {
  const res = await fetch(`${API_BASE_URL}/api/research/sources`);
  if (!res.ok) throw new Error("Failed to fetch sources");
  return res.json();
}

export async function getJobStatus(jobId: string) {
  const res = await fetch(`${API_BASE_URL}/api/research/status/${jobId}`);
  if (!res.ok) throw new Error("Failed to get job status");
  return res.json() as Promise<{ status: string; error?: string }>;
}
```

---

## 15. Frontend — Sidebar & AppShell Updates

### 15.1 Add Research Tab to Sidebar

**File:** `nexus-os-frontend/src/components/layout/Sidebar.tsx`

Add `Research` nav item with `FlaskConical` icon from Lucide React.

```typescript
{ id: "research", label: "Research", icon: FlaskConical, phase: 3 }
```

### 15.2 Register ResearchTab in AppShell

**File:** `nexus-os-frontend/src/components/layout/AppShell.tsx`

```typescript
import ResearchTab from "@/components/tabs/ResearchTab";

// In the tab renderer switch/map:
case "research":
  return <ResearchTab />;
```

### 15.3 WebSocket event handler update

**File:** `nexus-os-frontend/src/hooks/useWebSocket.ts`

Add handling for research-specific event types:

```typescript
case "progress":
  if (event.agent) {
    researchStore.updatePipelineAgent(event.agent, {
      stage: event.stage,
      detail: event.detail,
      status: "active",
    });
  }
  break;

case "done":
  if (event.slug) {
    researchStore.completeJob(event.metadata);
  }
  break;
```

---

## 16. Testing Checklist

### Backend

- [ ] `web_scout.py` — unit test `score_and_rank()` with mock DDGS results
- [ ] `web_scout.py` — unit test `generate_query_variations()` with mock LM Studio response
- [ ] `scraper_agent.py` — unit test `extract_text()` with real HTML fixture
- [ ] `scraper_agent.py` — unit test paywall detection heuristics
- [ ] `scraper_agent.py` — unit test `fetch_url()` error handling (mock httpx exceptions)
- [ ] `fact_checker.py` — unit test `check_claim_in_source()` with known claims
- [ ] `fact_checker.py` — unit test `verify_claims()` with mock sources
- [ ] `report_builder.py` — unit test `generate_slug()` for special characters and long topics
- [ ] `report_builder.py` — unit test `save_to_disk()` file creation
- [ ] `report_builder.py` — unit test `index_in_chroma()` with mock ChromaDB
- [ ] `research_lead.py` — integration test full pipeline with mock agents
- [ ] `research_graph.py` — unit test conditional edge functions
- [ ] API `GET /api/research` — returns empty list when no reports
- [ ] API `POST /api/research/start` — returns job_id and slug
- [ ] API `GET /api/research/{slug}` — returns 404 for unknown slug
- [ ] API `DELETE /api/research/{slug}` — removes files and ChromaDB entries

### Frontend

- [ ] `ResearchTab` renders without crashing
- [ ] `NewResearch` → typing topic + clicking Research calls `startResearch()`
- [ ] `PipelineViz` → all 5 nodes render idle on mount
- [ ] `PipelineViz` → active node shows pulse animation
- [ ] `ReportsLibrary` → loads reports on mount via `listReports()`
- [ ] `ReportCard` → confidence badge color correct for each tier
- [ ] `SourceManager` → table renders with correct columns
- [ ] `ReportViewer` → `[HIGH]` token renders as green badge
- [ ] `ReportViewer` → "Export" triggers file download
- [ ] `useResearchStore` — `startJob` initializes pipeline with 5 idle agents
- [ ] `useResearchStore` — `updatePipelineAgent` mutates correct agent only

---

## 17. Acceptance Criteria

1. **End-to-end research flow works:**
   User submits `"Research quantum computing advances in 2024"` via chat or Research tab.
   All 5 pipeline agents activate sequentially. Report is saved to disk.

2. **Report appears in Reports Library** within 5 seconds of completion.
   Report card shows correct source count, confidence score, and date.

3. **Report Viewer renders** the full markdown with syntax highlighting, confidence badges, and source links.

4. **Source Manager** shows all scraped URLs with quality scores and extraction statuses.

5. **RAG integration:** After research completes, asking `"What do I know about quantum computing?"` retrieves content from the saved report (not just files from Phase 2).

6. **Graceful degradation:**
   - If DuckDuckGo rate-limits → retry once, then surface error to user
   - If < 3 sources scraped → attempt one retry with broader query
   - If all claims unverified → report is still generated with a "Low confidence data" warning

7. **Existing features unbroken:**
   - Phase 1 chat still works
   - Phase 2 file upload and RAG retrieval still work
   - WebSocket streaming still works for normal chat

---

## 18. Week-by-Week Breakdown

### Week 6 — Agents & Pipeline Core

**Goal:** All 4 specialist agents functional with unit tests. Research Lead wires them together. No UI yet — test via HTTP + raw WebSocket.

| Day | Task |
|-----|------|
| Mon | Install deps. Create `web_scout.py`. Implement `search_single_query()` + `score_and_rank()`. Verify DDGS works. |
| Tue | Implement `generate_query_variations()` (LM Studio prompt). Write unit tests. Create `web_scout.yaml` personality. |
| Wed | Create `scraper_agent.py`. Implement `fetch_url()` + `extract_text()` + paywall detection. Write unit tests with HTML fixtures. |
| Thu | Create `fact_checker.py`. Implement `extract_claims()` + `verify_claims()`. Create `fact_checker.yaml`. Write unit tests. |
| Fri | Create `report_builder.py`. Implement `build_report()` + `save_to_disk()` + `index_in_chroma()`. Test disk output. |

### Week 7 — Orchestration & API

**Goal:** Research Lead + LangGraph pipeline. REST API + WebSocket streaming. Backend fully functional.

| Day | Task |
|-----|------|
| Mon | Create `research_lead.py`. Wire Scout → Scraper → Checker → Builder. Test full pipeline from CLI. |
| Wed | Create `research_graph.py` (LangGraph). Implement conditional edges + retry logic. |
| Thu | Create `backend/app/api/research.py`. Implement all 6 endpoints. Add DB `research_jobs` table. |
| Fri | Update `knowledge_lead.py` with research intent detection. Update Supervisor routing. Update WebSocket handler for new event types. End-to-end test via curl + wscat. |

### Week 8 — Frontend & Polish

**Goal:** Full frontend implementation. All subtabs working. Pipeline visualization animated. QA pass.

| Day | Task |
|-----|------|
| Mon | Create `useResearchStore.ts`. Create `researchApi.ts`. Create `research.ts` types. |
| Tue | Build `ResearchTab.tsx` + `NewResearch.tsx` (input form + pipeline progress display). |
| Wed | Build `PipelineViz.tsx` (animated node graph). Integrate with store events via WebSocket. |
| Thu | Build `ReportsLibrary.tsx` + `ReportCard.tsx`. Build `SourceManager.tsx`. |
| Fri | Build `ReportViewer.tsx` (markdown renderer + confidence badges + export). Update `Sidebar.tsx` + `AppShell.tsx`. QA full flow. Fix regressions. |

---

*Phase 3 complete when: user can research any topic end-to-end, view the structured report, and query past research via RAG.*
