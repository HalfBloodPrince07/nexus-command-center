"""Phase 4 — SynthesisDirector: merge independently drafted sections into a cohesive report."""
from __future__ import annotations

import logging
import re
from typing import AsyncGenerator

from backend.app.agents._lm_studio import stream_chat_completion
from backend.config import settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are SynthesisDirector, the master editor of a research report. You have received
independently drafted sections that must be unified into a single, polished document.

Your responsibilities:
1. MERGE all sections in the correct numbered order.
2. WRITE smooth transition sentences between each section (1-2 sentences that bridge
   the previous section to the next).
3. STANDARDIZE all citations to the format: [^N] where N is a sequential number.
   Build a consolidated [REFERENCES] section at the end.
4. REMOVE duplicate content if the same point appears in multiple sections.
5. ENSURE consistent terminology throughout (standardize synonyms to one term).
6. PRESERVE all factual content and inline [NEEDS_VERIFICATION] flags — do not remove them.
7. ADD an executive summary (≤250 words) at the very beginning if not already present.
8. FORMAT the final document in clean, professional Markdown.

DO NOT add new factual claims not present in the input sections.
DO NOT remove [NEEDS_VERIFICATION] flags.
Output only the complete merged Markdown document.\
"""


def _build_user_prompt(
    report_title: str,
    raw_query: str,
    sections: list[dict],
    sources: list[dict],
) -> str:
    section_count = len(sections)
    sections_text = "\n\n".join(
        f"--- SECTION {s['number']}: {s['title']} ---\n{s['text']}"
        for s in sorted(sections, key=lambda x: x.get("number", 0))
    )
    url_list = "\n".join(
        f"{i + 1}. {s.get('url', '')} [{s.get('domain', '')}]"
        for i, s in enumerate(sources)
    )
    return (
        f"Report Title: {report_title}\n"
        f"Research Topic: {raw_query}\n"
        f"Total Sections: {section_count}\n\n"
        f"DRAFTED SECTIONS:\n{sections_text}\n\n"
        f"---\nORIGINAL SOURCES MASTER LIST:\n{url_list}\n\n"
        "Produce the synthesized, unified research report now.\n"
        "Include: Executive Summary, all sections with transitions, consolidated References."
    )


def _extract_needs_verification_count(text: str) -> int:
    return len(re.findall(r"\[NEEDS_VERIFICATION:", text))


class SynthesisDirectorAgent:
    async def run(
        self,
        report_title: str,
        raw_query: str,
        sections: list[dict],
        sources: list[dict],
    ) -> AsyncGenerator[dict, None]:
        total_draft_words = sum(len(s.get("text", "").split()) for s in sections)
        yield {
            "type": "thinking",
            "agent": "SynthesisDirector",
            "detail": (
                f"Synthesizing {len(sections)} sections "
                f"(~{total_draft_words:,} draft words) into unified report..."
            ),
        }

        final_report = ""
        try:
            async for token in stream_chat_completion(
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": _build_user_prompt(report_title, raw_query, sections, sources),
                    },
                ],
                model=settings.lm_studio_model,
                temperature=0.25,
                max_tokens=8192,
            ):
                final_report += token
                yield {"type": "chunk", "agent": "SynthesisDirector", "content": token}
        except Exception as exc:
            logger.error("SynthesisDirector failed: %s", exc)
            # Fallback: join sections as-is with minimal formatting
            final_report = _assemble_fallback(report_title, sections, sources)
            yield {
                "type": "error",
                "agent": "SynthesisDirector",
                "detail": f"Synthesis failed ({exc}) — assembled sections directly",
            }

        needs_verification = _extract_needs_verification_count(final_report)
        yield {
            "type": "result",
            "agent": "SynthesisDirector",
            "data": {
                "report_text": final_report,
                "word_count": len(final_report.split()),
                "needs_verification_count": needs_verification,
            },
        }


def _assemble_fallback(report_title: str, sections: list[dict], sources: list[dict]) -> str:
    """Direct concatenation used only when LM Studio is unavailable during synthesis."""
    lines: list[str] = [f"# {report_title}\n"]
    for s in sorted(sections, key=lambda x: x.get("number", 0)):
        lines.append(s.get("text", ""))
        lines.append("")
    lines.append("\n## References\n")
    for i, src in enumerate(sources, 1):
        lines.append(f"[^{i}]: {src.get('url', '')} — {src.get('title', src.get('domain', ''))}")
    return "\n".join(lines)


synthesis_director = SynthesisDirectorAgent()
