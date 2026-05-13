"""Phase 2b — HybridScraper: fetch URLs, extract clean text, ingest to ChromaDB + SQLite."""
from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import uuid
from typing import AsyncGenerator
from urllib.parse import urlparse

import httpx
import trafilatura

from backend.config import settings
from backend.core import database as db_module
from backend.core.resilience import RateLimited, ScrapeBlocked, degraded_event, with_retry

logger = logging.getLogger(__name__)

try:
    from playwright.async_api import async_playwright
    _PLAYWRIGHT_OK = True
except ImportError:
    _PLAYWRIGHT_OK = False
    logger.debug("playwright not installed — JS-fallback scraping disabled")

_JS_HEAVY_DOMAINS = {"medium.com", "substack.com", "notion.so", "hashnode.dev"}
_PAYWALL_SIGNALS = [
    "subscribe to read", "sign in to continue", "members only",
    "premium content", "paywall", "subscribe now to read",
]
_BLOCKED_EXTENSIONS = {".pdf", ".mp4", ".zip", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"}
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def _extract_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().lstrip("www.")
    except Exception:
        return ""


def _is_paywall(html: str) -> bool:
    html_lower = html.lower()
    if any(s in html_lower for s in _PAYWALL_SIGNALS):
        return True
    if '"isAccessibleForFree"' in html and ('"False"' in html or '"false"' in html):
        return True
    return False


def _compute_quality(text: str, paywalled: bool) -> float:
    if paywalled or not text:
        return 0.0
    score = 0.0
    words = text.split()
    score += min(len(words) / 2000, 0.4)
    score += 0.2 if any(c.isdigit() for c in text) else 0.0
    score += 0.2 if re.search(r"\d{4}", text) else 0.0
    score += 0.1 if len(re.findall(r"\n\n", text)) > 5 else 0.0
    score += 0.1 if ("conclusion" in text.lower() or "summary" in text.lower()) else 0.0
    return round(min(score, 1.0), 3)


def _sliding_window_chunks(text: str, size: int = 600, overlap: int = 100) -> list[str]:
    step = max(size - overlap, 1)
    return [text[i : i + size] for i in range(0, len(text), step) if text[i : i + size].strip()]


async def _scrape_trafilatura(
    url: str, client: httpx.AsyncClient
) -> tuple[str, str, bool, object]:
    resp = await client.get(
        url, headers=_HEADERS,
        timeout=settings.SCRAPE_TIMEOUT_SECONDS,
        follow_redirects=True,
    )
    resp.raise_for_status()
    html = resp.text
    paywalled = _is_paywall(html)
    text = trafilatura.extract(html, include_tables=True, include_comments=False, no_fallback=False) or ""
    meta = None
    try:
        meta = trafilatura.extract_metadata(html, default_url=url)
    except Exception:
        pass
    return html, text, paywalled, meta


@with_retry(
    max_attempts=3,
    backoff="exponential",
    retry_on=(httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError),
    base_delay=0.5,
)
async def _scrape_archive(url: str, client: httpx.AsyncClient) -> tuple[str, str, bool, object]:
    archived_url = f"https://web.archive.org/web/{url}"
    resp = await client.get(
        archived_url,
        headers=_HEADERS,
        timeout=settings.SCRAPE_TIMEOUT_SECONDS,
        follow_redirects=True,
    )
    resp.raise_for_status()
    html = resp.text
    text = trafilatura.extract(html, include_tables=True, include_comments=False, no_fallback=False) or ""
    meta = None
    try:
        meta = trafilatura.extract_metadata(html, default_url=url)
    except (ValueError, TypeError):
        pass
    return html, text, False, meta


async def _scrape_playwright(url: str) -> tuple[str, str, bool, object]:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent=_HEADERS["User-Agent"],
            viewport={"width": 1280, "height": 720},
        )
        page = await ctx.new_page()
        await page.route(
            "**/*.{png,jpg,jpeg,gif,svg,css,woff,woff2,ico}",
            lambda route: route.abort(),
        )
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=25000)
            await page.wait_for_timeout(2000)
            for sel in ["button[id*='accept']", "button[class*='accept']", "#cookie-accept"]:
                try:
                    await page.click(sel, timeout=800)
                except Exception:
                    pass
            html = await page.content()
        finally:
            await browser.close()
    paywalled = _is_paywall(html)
    text = trafilatura.extract(html, include_tables=True, include_comments=False) or ""
    meta = None
    try:
        meta = trafilatura.extract_metadata(html, default_url=url)
    except Exception:
        pass
    return html, text, paywalled, meta


def _save_files(slug: str, source_id: str, html: str, clean_text: str) -> tuple[str, str]:
    base = settings.DEEP_RESEARCH_DIR / slug
    html_dir = base / "raw_html"
    txt_dir = base / "clean_text"
    html_dir.mkdir(parents=True, exist_ok=True)
    txt_dir.mkdir(parents=True, exist_ok=True)

    raw_path = html_dir / f"{source_id}.html"
    txt_path = txt_dir / f"{source_id}.txt"
    if html:
        raw_path.write_text(html, encoding="utf-8", errors="replace")
    if clean_text:
        txt_path.write_text(clean_text, encoding="utf-8", errors="replace")
    return str(raw_path), str(txt_path)


async def _ingest_to_chroma(
    slug: str,
    source_id: str,
    url: str,
    domain: str,
    quality: float,
    published_date: str | None,
    text: str,
) -> list[tuple[str, str]]:
    """Chunk text, upsert to ChromaDB. Returns list of (chroma_doc_id, chunk_text)."""
    chunks = _sliding_window_chunks(text, size=600, overlap=100)
    if not chunks:
        return []
    chunk_dicts = [
        {
            "id": f"{source_id}_chunk_{i}",
            "text": chunk,
            "metadata": {
                "source_id": source_id,
                "url": url,
                "domain": domain,
                "quality_score": quality,
                "chunk_index": i,
                "published_date": published_date or "unknown",
            },
        }
        for i, chunk in enumerate(chunks)
    ]
    try:
        from backend.db.vector_store import init_vector_store
        vs = await init_vector_store()
        await vs.upsert_chunks(f"research_{slug}", chunk_dicts)
    except Exception as exc:
        logger.warning("ChromaDB ingestion failed for source %s: %s", source_id, exc)
        return []
    return [(c["id"], c["text"]) for c in chunk_dicts]


class HybridScraper:
    def __init__(self, concurrency: int = 8) -> None:
        self._semaphore = asyncio.Semaphore(concurrency)

    def extract_text(self, html: str, url: str = "") -> dict:
        text = trafilatura.extract(html, include_tables=True, include_comments=False, no_fallback=False) or ""
        paywalled = _is_paywall(html)
        return {
            "text": text,
            "quality_score": _compute_quality(text, paywalled),
            "is_paywalled": paywalled,
            "url": url,
        }

    def _detect_paywall(self, html: str, text: str = "") -> bool:
        return _is_paywall(html) or (len(text.split()) < 50 and any(s in html.lower() for s in _PAYWALL_SIGNALS))

    async def fetch_url(self, client: httpx.AsyncClient, url: str) -> dict:
        try:
            response = await client.get(url, headers=_HEADERS, timeout=settings.SCRAPE_TIMEOUT_SECONDS)
        except httpx.TimeoutException:
            return {"html": None, "status_code": None, "error": "timeout"}
        except httpx.RequestError as exc:
            return {"html": None, "status_code": None, "error": str(exc)}
        status_code = response.status_code
        if status_code >= 400:
            return {"html": response.text, "status_code": status_code, "error": f"http_{status_code}"}
        return {"html": response.text, "status_code": status_code, "error": None}

    def _url_hash(self, url: str) -> str:
        return hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]

    async def _scrape_with_fallback(
        self, url: str, domain: str, client: httpx.AsyncClient
    ) -> tuple[str, str, bool, object, str]:
        """Returns (html, text, is_paywalled, meta, scrape_method)."""
        html, text, paywalled, meta, method = "", "", False, None, "trafilatura"
        try:
            html, text, paywalled, meta = await _scrape_trafilatura(url, client)
            # Try playwright if primary gives too little content and domain is JS-heavy
            if len(text.split()) < 150 and domain in _JS_HEAVY_DOMAINS and _PLAYWRIGHT_OK:
                html2, text2, paywalled2, meta2 = await _scrape_playwright(url)
                if len(text2.split()) > len(text.split()):
                    html, text, paywalled, meta, method = html2, text2, paywalled2, meta2, "playwright"
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status in (403, 429):
                if status == 429:
                    raise RateLimited(f"Scrape rate-limited for {url}") from exc
                try:
                    html, text, paywalled, meta = await _scrape_archive(url, client)
                    method = "archive.org"
                except Exception as archive_exc:
                    raise ScrapeBlocked(
                        f"Source blocked and archive fallback failed for {url}: {archive_exc}"
                    ) from archive_exc
            else:
                raise
        except (httpx.TimeoutException, httpx.RequestError):
            raise
        except Exception:
            if _PLAYWRIGHT_OK:
                html, text, paywalled, meta = await _scrape_playwright(url)
                method = "playwright"
            else:
                raise
        return html, text, paywalled, meta, method

    async def scrape_one(
        self,
        url_obj: dict,
        slug: str,
        session_id: str,
        client: httpx.AsyncClient,
    ) -> dict:
        url = url_obj.get("url", "")
        domain = url_obj.get("domain") or _extract_domain(url)
        source_id = str(uuid.uuid4())

        # Skip non-HTML file types
        path = urlparse(url).path.lower()
        if any(path.endswith(ext) for ext in _BLOCKED_EXTENSIONS):
            return {**url_obj, "id": source_id, "clean_text": "", "word_count": 0,
                    "scrape_status": "blocked", "quality_score": 0.0}

        scrape_status = "failed"
        error_msg: str | None = None
        html, text, paywalled, meta, method = "", "", False, None, "trafilatura"

        async with self._semaphore:
            try:
                html, text, paywalled, meta, method = await self._scrape_with_fallback(
                    url, domain, client
                )
            except httpx.TimeoutException:
                scrape_status, error_msg = "timeout", "timeout"
            except (RateLimited, ScrapeBlocked) as exc:
                scrape_status, error_msg = "blocked", str(exc)[:120]
            except Exception as exc:
                scrape_status, error_msg = "failed", str(exc)[:120]

        if error_msg:
            return {**url_obj, "id": source_id, "clean_text": "", "word_count": 0,
                    "scrape_status": scrape_status, "quality_score": 0.0,
                    "error_message": error_msg}

        word_count = len(text.split())
        quality = _compute_quality(text, paywalled)
        title = (meta.title if meta and meta.title else None) or url_obj.get("title", "")
        author = meta.author if meta and meta.author else None
        pub_date = str(meta.date) if meta and meta.date else None

        if paywalled:
            scrape_status = "paywall"
        elif word_count < 150:
            scrape_status = "low_content"
        else:
            scrape_status = "success"

        try:
            raw_html_path, clean_text_path = _save_files(slug, source_id, html, text)
        except OSError as exc:
            logger.warning(
                "Scraper disk write failed",
                extra={"source_id": source_id, "url": url, "error": str(exc)},
            )
            return {
                **url_obj,
                "id": source_id,
                "clean_text": text,
                "word_count": word_count,
                "scrape_status": "failed",
                "quality_score": 0.0,
                "error_message": "Disk write failed while saving scraped source.",
            }

        # Persist source metadata to SQLite
        try:
            await db_module.insert_scraped_source(
                source_id=source_id,
                session_id=session_id,
                url=url,
                query_id=url_obj.get("query_id"),
                domain=domain,
                title=title,
                author=author,
                published_date=pub_date,
                word_count=word_count,
                quality_score=quality,
                domain_authority_score=url_obj.get("authority_score", 0.3),
                is_paywalled=paywalled,
                raw_html_path=raw_html_path,
                clean_text_path=clean_text_path,
                scrape_status=scrape_status,
                error_message=None,
            )
        except Exception as exc:
            logger.warning("SQLite insert failed for %s: %s", url, exc)

        # ChromaDB ingestion + chunk records (only for usable content)
        chroma_chunk_count = 0
        if scrape_status == "success":
            chunk_pairs = await _ingest_to_chroma(
                slug, source_id, url, domain, quality, pub_date, text
            )
            chroma_chunk_count = len(chunk_pairs)
            for i, (doc_id, chunk_text) in enumerate(chunk_pairs):
                try:
                    await db_module.insert_content_chunk(
                        chunk_id=str(uuid.uuid4()),
                        session_id=session_id,
                        source_id=source_id,
                        chunk_text=chunk_text,
                        chunk_index=i,
                        chroma_doc_id=doc_id,
                        token_count=len(chunk_text.split()),
                    )
                except Exception as exc:
                    logger.debug("Chunk record insert failed: %s", exc)

        return {
            **url_obj,
            "id": source_id,
            "title": title,
            "author": author,
            "published_date": pub_date,
            "clean_text": text,
            "word_count": word_count,
            "quality_score": quality,
            "is_paywalled": paywalled,
            "scrape_method": method,
            "scrape_status": scrape_status,
            "raw_html_path": raw_html_path,
            "clean_text_path": clean_text_path,
            "chroma_chunk_count": chroma_chunk_count,
        }

    async def run(
        self,
        slug: str,
        session_id: str,
        urls: list[dict],
        max_urls: int = 80,
    ) -> AsyncGenerator[dict, None]:
        to_scrape = urls[:max_urls]
        yield {
            "type": "progress", "agent": "Fetch", "stage": "scraping",
            "detail": f"Scraping top {len(to_scrape)} of {len(urls)} discovered URLs...",
        }

        sources: list[dict] = []
        failures: list[str] = []
        completed = 0

        async with httpx.AsyncClient() as client:
            tasks = [self.scrape_one(u, slug, session_id, client) for u in to_scrape]
            for coro in asyncio.as_completed(tasks):
                result = await coro
                completed += 1
                domain_short = result.get("domain", result.get("url", "?"))[:35]
                status = result.get("scrape_status", "unknown")
                icon = "✓" if status == "success" else f"✗ ({status})"
                yield {
                    "type": "progress", "agent": "Fetch", "stage": "scraped",
                    "detail": f"{completed}/{len(to_scrape)} — {domain_short} {icon}",
                }
                if result.get("scrape_method") == "archive.org":
                    yield degraded_event(
                        "Fetch",
                        "archive_fallback",
                        f"Primary scrape was blocked; used archive.org for {result.get('url', '')}",
                        url=result.get("url", ""),
                    )
                if status == "blocked":
                    logger.warning(
                        "Skipping blocked scrape source",
                        extra={"url": result.get("url", ""), "error": result.get("error_message", "")},
                    )
                    yield degraded_event(
                        "Fetch",
                        "scrape_blocked",
                        f"Skipped blocked source: {result.get('url', '')}",
                        url=result.get("url", ""),
                    )
                if "Disk write failed" in (result.get("error_message") or ""):
                    yield degraded_event(
                        "Fetch",
                        "disk_write_failed",
                        "Could not persist scraped source content to disk.",
                        url=result.get("url", ""),
                    )
                if result.get("word_count", 0) >= 150 and result.get("scrape_status") == "success":
                    sources.append(result)
                elif status in ("failed", "timeout", "blocked"):
                    failures.append(result.get("url", ""))

        yield {
            "type": "result", "agent": "Fetch",
            "data": sources,
            "success_count": len(sources),
            "failure_count": len(failures),
        }


scraper_agent = HybridScraper()

ScraperAgent = HybridScraper
