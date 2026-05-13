"""Tests for ReportBuilderAgent — generate_slug, save_to_disk, _chunk_text."""
from __future__ import annotations

import json
import re
import shutil
import tempfile
from pathlib import Path

import pytest

from backend.app.agents.report_builder import ReportBuilderAgent
from backend.config import settings


@pytest.fixture
def agent() -> ReportBuilderAgent:
    return ReportBuilderAgent()


@pytest.fixture
def tmp_research_dir(monkeypatch, tmp_path):
    """Override DEEP_RESEARCH_DIR to a temporary directory for isolation."""
    research_dir = tmp_path / "deep_research"
    research_dir.mkdir()
    monkeypatch.setattr(settings, "DEEP_RESEARCH_DIR", research_dir)
    return research_dir


# ---------------------------------------------------------------------------
# generate_slug
# ---------------------------------------------------------------------------


def test_generate_slug_basic(agent: ReportBuilderAgent) -> None:
    slug = agent.generate_slug("Quantum Computing in 2024!")
    assert slug == slug.lower(), "Slug must be lowercase"
    assert re.match(r"^[a-z0-9\-]+$", slug), f"Slug has special chars: '{slug}'"
    assert len(slug) <= 60, f"Slug exceeds 60 chars: len={len(slug)}"


def test_generate_slug_long_topic(agent: ReportBuilderAgent) -> None:
    long_topic = "This is an extremely long topic title that goes well beyond " * 5
    slug = agent.generate_slug(long_topic)
    assert len(slug) <= 60, f"Long-topic slug exceeds 60 chars: len={len(slug)}"


def test_generate_slug_strips_special_chars(agent: ReportBuilderAgent) -> None:
    slug = agent.generate_slug("AI & Machine Learning: A Deep Dive (2024)")
    assert "&" not in slug
    assert ":" not in slug
    assert "(" not in slug


def test_generate_slug_is_non_empty(agent: ReportBuilderAgent) -> None:
    slug = agent.generate_slug("Hello World")
    assert slug, "Slug must not be empty for a valid topic"


# ---------------------------------------------------------------------------
# save_to_disk
# ---------------------------------------------------------------------------


def test_save_to_disk_creates_report_md(agent: ReportBuilderAgent, tmp_research_dir: Path) -> None:
    slug = "test-slug"
    agent.save_to_disk(slug, "# Hello\nContent body here.", {"slug": slug, "topic": "Test"})
    report_file = tmp_research_dir / slug / "report.md"
    assert report_file.exists(), f"report.md not found at {report_file}"


def test_save_to_disk_creates_metadata_json(agent: ReportBuilderAgent, tmp_research_dir: Path) -> None:
    slug = "test-slug"
    metadata = {"slug": slug, "topic": "Test Topic", "created_at": "2024-01-01"}
    agent.save_to_disk(slug, "# Report", metadata)
    meta_file = tmp_research_dir / slug / "metadata.json"
    assert meta_file.exists(), f"metadata.json not found at {meta_file}"


def test_save_to_disk_metadata_json_is_valid(agent: ReportBuilderAgent, tmp_research_dir: Path) -> None:
    slug = "json-check-slug"
    metadata = {"slug": slug, "topic": "JSON Test", "avg_confidence": 0.85}
    agent.save_to_disk(slug, "# Content", metadata)
    meta_file = tmp_research_dir / slug / "metadata.json"
    parsed = json.loads(meta_file.read_text(encoding="utf-8"))
    assert parsed["slug"] == slug
    assert parsed["avg_confidence"] == 0.85


def test_save_to_disk_report_content_preserved(agent: ReportBuilderAgent, tmp_research_dir: Path) -> None:
    slug = "content-check"
    content = "# My Report\n\nThis is the report body with **bold** text.\n"
    agent.save_to_disk(slug, content, {"slug": slug})
    report_file = tmp_research_dir / slug / "report.md"
    assert report_file.read_text(encoding="utf-8") == content


# ---------------------------------------------------------------------------
# _chunk_text
# ---------------------------------------------------------------------------


def test_chunk_text_respects_size(agent: ReportBuilderAgent) -> None:
    """All chunks must be <= RESEARCH_CHUNK_SIZE in length."""
    text = "A" * 5000
    chunks = agent._chunk_text(text)
    max_allowed = settings.RESEARCH_CHUNK_SIZE + settings.RESEARCH_CHUNK_OVERLAP
    for i, chunk in enumerate(chunks):
        assert len(chunk) <= max_allowed, (
            f"Chunk {i} length {len(chunk)} exceeds {max_allowed}"
        )


def test_chunk_text_covers_full_content(agent: ReportBuilderAgent) -> None:
    """The first and last characters of the original text must appear in chunks."""
    text = "START" + "X" * 2000 + "END"
    chunks = agent._chunk_text(text)
    assert chunks, "Expected at least one chunk"
    all_content = "".join(chunks)
    assert "START" in all_content
    assert "END" in all_content


def test_chunk_text_short_text_single_chunk(agent: ReportBuilderAgent) -> None:
    """Text shorter than RESEARCH_CHUNK_SIZE should produce exactly one chunk."""
    text = "short text"
    chunks = agent._chunk_text(text)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_chunk_text_empty_produces_empty_list(agent: ReportBuilderAgent) -> None:
    chunks = agent._chunk_text("")
    # Empty string: loop condition `0 < 0` is False so list is empty
    assert chunks == []
