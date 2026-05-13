"""Phase 5 — FactChecker: extract claims from synthesized report, verify, and annotate."""
from __future__ import annotations

import json
import logging
import re
from typing import AsyncGenerator

from backend.app.agents._lm_studio import complete_chat
from backend.config import settings

logger = logging.getLogger(__name__)

# ── System prompts ────────────────────────────────────────────────────────────

_CLAIM_EXTRACTOR_SYSTEM = """\
You are ClaimExtractor. Your function is to parse a research report and extract every
discrete, verifiable factual claim.

A "claim" is: a statement asserting a specific fact, statistic, date, name, relationship,
or causal connection. Opinions and projections are NOT claims.

Output ONLY a JSON array. No explanation, no preamble.

Schema per claim:
{
  "id": "<sequential integer as string, starts at 1>",
  "claim_text": "<exact claim as stated in report>",
  "claim_type": "statistic|date|attribution|causal|definitional|comparative",
  "source_section": "<section title where claim appears>",
  "context_sentence": "<the full sentence containing this claim>",
  "existing_citation": "<citation ref if present, else null>",
  "verifiability": "high|medium|low"
}\
"""

_ENTAILMENT_SYSTEM = """\
You are a fact-verification engine. You will receive a CLAIM and SUPPORTING PASSAGES
retrieved from web sources. Determine if the passages ENTAIL, CONTRADICT, or neither
support the claim.

Output ONLY JSON:
{
  "status": "verified|unverified|contradicted|hallucinated",
  "confidence": <0.0 to 1.0>,
  "reasoning": "<one sentence>",
  "correction": "<corrected version of claim if contradicted, else null>"
}

Definitions:
- verified: At least 2 passages clearly support the claim
- unverified: 1 passage partially supports, or support is ambiguous
- contradicted: Passages clearly state something different
- hallucinated: No passage supports the claim in any way\
"""

_MAX_CLAIMS_FROM_REPORT = 30
_CHROMA_DISTANCE_THRESHOLD = 0.35


# ── Sub-phase 5a: Claim extraction ───────────────────────────────────────────

def _strip_json_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n?```\s*$", "", text, flags=re.MULTILINE)
    return text.strip()


async def _extract_claims_from_report(report_text: str, topic: str) -> list[dict]:
    user_prompt = (
        f"Research topic: {topic}\n\n"
        f"Report (first 6000 chars):\n{report_text[:6000]}\n\n"
        f"Extract up to {_MAX_CLAIMS_FROM_REPORT} distinct factual claims. "
        "Focus on statistics, named facts, dates, and attributions. "
        "Produce the JSON array now."
    )
    try:
        raw = await complete_chat(
            messages=[
                {"role": "system", "content": _CLAIM_EXTRACTOR_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            model=settings.lm_studio_model,
            temperature=0.1,
            max_tokens=2048,
        )
        match = re.search(r"\[.*\]", _strip_json_fences(raw), re.DOTALL)
        if match:
            claims = json.loads(match.group())
            return [c for c in claims if isinstance(c, dict)][:_MAX_CLAIMS_FROM_REPORT]
    except Exception as exc:
        logger.warning("ClaimExtractor JSON parse failed: %s", exc)

    # Fallback: sentence heuristics — any sentence with numbers/dates/names
    sentences = re.split(r"(?<=[.!?])\s+", report_text)
    fallback: list[dict] = []
    idx = 1
    for sent in sentences:
        if re.search(r"\d", sent) and 20 < len(sent) < 300:
            fallback.append({
                "id": str(idx),
                "claim_text": sent.strip(),
                "claim_type": "statistic",
                "source_section": "Unknown",
                "context_sentence": sent.strip(),
                "existing_citation": None,
                "verifiability": "medium",
            })
            idx += 1
            if len(fallback) >= _MAX_CLAIMS_FROM_REPORT:
                break
    return fallback


# ── Keyword-based source search (fast, no I/O) ───────────────────────────────

def _src_text(src: dict) -> str:
    return src.get("clean_text") or src.get("text") or ""


def _keyword_score(claim: str, source_text: str) -> float:
    keywords = [w for w in re.sub(r"[^\w\s]", "", claim.lower()).split() if len(w) > 3]
    if not keywords:
        return 0.0
    lower = source_text.lower()
    return sum(1 for kw in keywords if kw in lower) / len(keywords)


def _keyword_search(claim_text: str, sources: list[dict], threshold: float = 0.45) -> list[dict]:
    results: list[dict] = []
    for src in sources:
        text = _src_text(src)
        score = _keyword_score(claim_text, text)
        if score >= threshold:
            results.append({"text": text[:1500], "url": src.get("url", ""), "score": score})
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:5]


# ── ChromaDB semantic search ──────────────────────────────────────────────────

async def _chroma_search(claim_text: str, slug: str) -> list[dict]:
    try:
        from backend.db.vector_store import init_vector_store
        vs = await init_vector_store()
        # VectorStore.query returns list[dict] with keys: id, text, metadata, distance
        items = await vs.query(
            collection_name=f"research_{slug}",
            query_text=claim_text,
            n_results=10,
        )
        passages: list[dict] = []
        for item in items:
            dist = float(item.get("distance", 1.0))
            if dist < _CHROMA_DISTANCE_THRESHOLD:
                meta = item.get("metadata") or {}
                passages.append({
                    "text": (item.get("text") or "")[:1500],
                    "url": meta.get("url") or meta.get("source_url") or "",
                    "score": round(1.0 - dist, 3),
                })
        return passages
    except Exception as exc:
        logger.debug("ChromaDB search skipped for claim: %s", exc)
        return []


# ── Sub-phase 5b: LLM entailment + multi-strategy verification ───────────────

def _format_passages(passages: list[dict]) -> str:
    return "\n\n".join(
        f"[{i + 1}] (url: {p['url']})\n{p['text']}"
        for i, p in enumerate(passages[:5])
    )


async def _llm_entailment_check(claim_text: str, passages: list[dict]) -> dict:
    user_prompt = (
        f"CLAIM: {claim_text}\n\n"
        f"SUPPORTING PASSAGES:\n{_format_passages(passages)}\n\nVerdict:"
    )
    try:
        raw = await complete_chat(
            messages=[
                {"role": "system", "content": _ENTAILMENT_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            model=settings.lm_studio_model,
            temperature=0.0,
            max_tokens=256,
        )
        match = re.search(r"\{.*\}", _strip_json_fences(raw), re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception as exc:
        logger.warning("Entailment check failed: %s", exc)
    return {"status": "unverified", "confidence": 0.5, "reasoning": "LLM check unavailable", "correction": None}


async def _verify_claim(claim: dict, sources: list[dict], slug: str) -> dict:
    claim_text = claim.get("claim_text", "")

    # Strategy 1: keyword search across in-memory sources
    keyword_hits = _keyword_search(claim_text, sources)

    # Strategy 2: ChromaDB semantic search (only for high/medium verifiability)
    chroma_hits: list[dict] = []
    if claim.get("verifiability") in ("high", "medium"):
        chroma_hits = await _chroma_search(claim_text, slug)

    all_passages = keyword_hits + [p for p in chroma_hits if p["url"] not in {h["url"] for h in keyword_hits}]

    if not all_passages:
        return {
            **claim,
            "verification_status": "hallucinated",
            "confidence_score": 0.0,
            "supporting_urls": [],
            "corrected_text": None,
            "reasoning": "No supporting passages found in any source.",
        }

    # Strategy 3: LLM entailment (only if passages exist)
    verdict = await _llm_entailment_check(claim_text, all_passages)

    return {
        **claim,
        "verification_status": verdict.get("status", "unverified"),
        "confidence_score": round(float(verdict.get("confidence", 0.5)), 3),
        "supporting_urls": [p["url"] for p in all_passages[:3]],
        "corrected_text": verdict.get("correction"),
        "reasoning": verdict.get("reasoning", ""),
    }


# ── Sub-phase 5c: Report annotation ──────────────────────────────────────────

_NV_PATTERN = re.compile(r"\[NEEDS_VERIFICATION:\s*([^\]]+)\]")


def annotate_report_with_verdicts(report: str, claims: list[dict]) -> str:
    annotated = report

    # Build lookup: claim_text → claim for quick resolution of NEEDS_VERIFICATION markers
    claim_lookup: dict[str, dict] = {}
    for c in claims:
        key = c.get("claim_text", "").strip()
        if key:
            claim_lookup[key] = c

    # Pass 1: resolve [NEEDS_VERIFICATION: <text>] markers
    def _resolve_nv(match: re.Match) -> str:
        flagged_text = match.group(1).strip()
        # Find the closest claim by text overlap
        best: dict | None = None
        best_score = 0.0
        for key, claim in claim_lookup.items():
            kw = [w for w in re.sub(r"[^\w\s]", "", flagged_text.lower()).split() if len(w) > 3]
            if not kw:
                continue
            hits = sum(1 for w in kw if w in key.lower())
            score = hits / len(kw)
            if score > best_score:
                best_score = score
                best = claim

        if best and best_score > 0.4:
            status = best.get("verification_status", "unverified")
            if status == "verified":
                return flagged_text  # Remove flag, claim is supported
            elif status == "contradicted":
                correction = best.get("corrected_text")
                return f"~~{flagged_text}~~ *[Contradicted: {correction or 'See sources'}]*"
            elif status == "hallucinated":
                return f"~~{flagged_text}~~ **[⚠️ HALLUCINATED — no source support]**"
            else:
                return f"*{flagged_text}* ⚠️"  # Unverified, keep with flag

        # No matching claim — mark as unverified
        return f"*{flagged_text}* ⚠️"

    annotated = _NV_PATTERN.sub(_resolve_nv, annotated)

    # Pass 2: flag hallucinated claims by finding their context_sentence
    for claim in claims:
        if claim.get("verification_status") != "hallucinated":
            continue
        ctx = claim.get("context_sentence", "").strip()
        if ctx and ctx in annotated:
            warning = (
                f"\n> ⚠️ **HALLUCINATION DETECTED**: The following claim could not be "
                f"verified against any source: ~~{claim['claim_text']}~~\n"
            )
            annotated = annotated.replace(ctx, ctx + warning, 1)

    # Pass 3: append consolidated references from verified claims
    ref_urls: list[str] = []
    seen_refs: set[str] = set()
    for claim in sorted(claims, key=lambda c: c.get("confidence_score", 0), reverse=True):
        if claim.get("verification_status") == "verified":
            for url in claim.get("supporting_urls", []):
                if url and url not in seen_refs:
                    ref_urls.append(url)
                    seen_refs.add(url)

    # Find the highest existing [^N] reference number to avoid collisions
    existing_refs = re.findall(r"\[\^(\d+)\]", annotated)
    next_ref = max((int(n) for n in existing_refs), default=0) + 1

    if ref_urls:
        ref_block = "\n\n---\n## Verified Sources\n"
        for url in ref_urls:
            ref_block += f"[^{next_ref}]: {url}\n"
            next_ref += 1
        annotated += ref_block

    # Pass 4: append verification summary table
    verified = sum(1 for c in claims if c.get("verification_status") == "verified")
    unverified = sum(1 for c in claims if c.get("verification_status") == "unverified")
    contradicted = sum(1 for c in claims if c.get("verification_status") == "contradicted")
    hallucinated = sum(1 for c in claims if c.get("verification_status") == "hallucinated")
    total = len(claims)
    accuracy = f"{verified / max(total, 1) * 100:.1f}%"

    summary = f"""
---
## Verification Report
| Metric | Count |
|--------|-------|
| Total Claims Checked | {total} |
| ✅ Verified | {verified} |
| ⚠️ Unverified | {unverified} |
| ❌ Hallucinated | {hallucinated} |
| 🔄 Contradicted | {contradicted} |
| Overall Accuracy | {accuracy} |
"""
    return annotated + summary


# ── Agent class ───────────────────────────────────────────────────────────────

class FactCheckerAgent:
    def check_claim_in_source(self, claim: str, source_text: str) -> float:
        return _keyword_score(claim, source_text)

    async def verify_claims(self, claims: list[str], sources: list[dict]) -> list[dict]:
        results: list[dict] = []
        for idx, claim_text in enumerate(claims, start=1):
            hits = _keyword_search(claim_text, sources, threshold=0.45)
            status = (
                "verified"
                if len(hits) >= settings.MIN_SOURCES_FOR_FACT_CHECK
                else "unverified"
            )
            confidence = min(1.0, round(sum(hit.get("score", 0.0) for hit in hits) / max(len(hits), 1), 3)) if hits else 0.0
            results.append(
                {
                    "id": str(idx),
                    "claim": claim_text,
                    "claim_text": claim_text,
                    "status": status,
                    "verification_status": status,
                    "confidence": confidence,
                    "confidence_score": confidence,
                    "supporting_urls": [hit.get("url", "") for hit in hits],
                    "source_urls": [hit.get("url", "") for hit in hits],
                    "contradiction_note": None,
                }
            )
        return results

    async def run(
        self,
        slug: str,
        sources: list[dict],
        topic: str,
        report_text: str = "",
    ) -> AsyncGenerator[dict, None]:
        """
        Phase 5 pipeline:
        5a — extract claims from synthesized report
        5b — verify each claim against sources + ChromaDB + LLM entailment
        5c — annotate report with verdicts
        """
        yield {
            "type": "progress",
            "agent": "Verity",
            "stage": "extracting",
            "detail": "Extracting factual claims from synthesized report...",
        }

        # 5a: Extract claims (from report if available, else from sources)
        if report_text:
            claims_raw = await _extract_claims_from_report(report_text, topic)
        else:
            # Backward-compatible fallback: extract from source snippets
            combined = "\n\n".join(s.get("text", "")[:1500] for s in sources[:6])
            claims_raw = await _extract_claims_from_report(combined, topic)

        yield {
            "type": "progress",
            "agent": "Verity",
            "stage": "extracted",
            "detail": f"Extracted {len(claims_raw)} claims. Verifying against {len(sources)} sources...",
        }

        # 5b: Verify each claim
        verified_claims: list[dict] = []
        for i, claim in enumerate(claims_raw):
            yield {
                "type": "progress",
                "agent": "Verity",
                "stage": "checking",
                "detail": f"Checking claim {i + 1}/{len(claims_raw)}: {claim.get('claim_text', '')[:60]}...",
            }
            result = await _verify_claim(claim, sources, slug)
            verified_claims.append(result)

        # 5c: Annotate report
        annotated_report = report_text
        if report_text and verified_claims:
            yield {
                "type": "progress",
                "agent": "Verity",
                "stage": "annotating",
                "detail": "Annotating report with verification results...",
            }
            annotated_report = annotate_report_with_verdicts(report_text, verified_claims)

        # Persist fact-check data
        verified_count = sum(1 for c in verified_claims if c.get("verification_status") == "verified")
        hallucinated_count = sum(1 for c in verified_claims if c.get("verification_status") == "hallucinated")
        avg_confidence = round(
            sum(c.get("confidence_score", 0.0) for c in verified_claims) / len(verified_claims)
            if verified_claims else 0.0,
            3,
        )

        try:
            import json as _json
            path = settings.DEEP_RESEARCH_DIR / slug / "fact_check.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                _json.dumps({
                    "claims": verified_claims,
                    "avg_confidence": avg_confidence,
                    "verified_count": verified_count,
                    "hallucinated_count": hallucinated_count,
                }, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning("Failed to save fact_check.json: %s", exc)

        yield {
            "type": "result",
            "agent": "Verity",
            "data": verified_claims,
            "avg_confidence": avg_confidence,
            "verified_count": verified_count,
            "hallucinated_count": hallucinated_count,
            "annotated_report": annotated_report,
        }


fact_checker_agent = FactCheckerAgent()
