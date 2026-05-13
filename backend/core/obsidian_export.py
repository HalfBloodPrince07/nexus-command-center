"""Obsidian-compatible markdown export service for all user-generated content."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional, Any
from urllib.parse import urlparse

if TYPE_CHECKING:
    from backend.core.database import Database

from backend.config import settings
from backend.core import database as db_module

logger = logging.getLogger(__name__)

# Filename sanitization for Windows
ILLEGAL_CHARS = re.compile(r'[<>:"/\\|?*]')
MAX_FILENAME_LENGTH = 100


class ObsidianExportError(Exception):
    """Custom exception for Obsidian export operations."""

    pass


class ObsidianExporter:
    """Handles export of all user-generated content to Obsidian-compatible Markdown files."""

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or Path(settings.DATA_DIR) / "obsidian_export"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Vault structure
        self.vault_structure = {
            "Research": self.output_dir / "Research",
            "Journal": self.output_dir / "Journal",
            "Memory": self.output_dir / "Memory",
            "Conversations": self.output_dir / "Conversations",
            "Sources": self.output_dir / "Sources",
            "_meta": self.output_dir / "_meta",
        }

        # Initialize vault directories
        for path in self.vault_structure.values():
            path.mkdir(parents=True, exist_ok=True)

        # Track generated files for link resolution
        self.generated_files: Dict[str, Path] = {}
        self.link_map: Dict[str, str] = {}

    async def export_all(self, scope: str = "all") -> Path:
        """Export all user-generated content to Obsidian vault."""
        try:
            export_timestamp = datetime.now(timezone.utc)

            if scope in ["all", "research"]:
                await self._export_research()
            if scope in ["all", "journal"]:
                await self._export_journal()
            if scope in ["all", "memory"]:
                await self._export_memory()
            if scope in ["all", "chat"]:
                await self._export_conversations()
            if scope in ["all"]:
                await self._export_sources()

            # Generate metadata
            await self._generate_manifest(export_timestamp, scope)
            await self._generate_tags_json()

            logger.info(
                "Obsidian export completed successfully. Vault: %s", self.output_dir
            )
            return self.output_dir

        except Exception as e:
            logger.error("Obsidian export failed: %s", e)
            raise ObsidianExportError(f"Export failed: {e}")

    async def _export_research(self) -> None:
        """Export research sessions."""
        db = db_module.database
        if not db:
            return

        sessions = await db.list_research_sessions()

        for session in sessions:
            # Generate filename
            timestamp = datetime.fromisoformat(session["created_at"]).strftime(
                "%Y-%m-%d"
            )
            slug = self._slugify(session.get("slug", f"research-{session['id']}"))
            filename = f"{timestamp} {slug}.md"

            # Build content
            content_lines = []

            # Front matter
            front_matter = {
                "created": session["created_at"],
                "updated": session.get("updated_at", session["created_at"]),
                "type": "research",
                "tags": (session.get("keywords") or []).split(",")
                if session.get("keywords")
                else [],
                "nexus_id": session["id"],
                "status": session.get("status", "completed"),
            }
            content_lines.append("---")
            content_lines.append(json.dumps(front_matter, indent=2))
            content_lines.append("---")
            content_lines.append("")

            # Title
            content_lines.append(f"# {session.get('title', 'Untitled Research')}")
            content_lines.append("")

            # Query
            if session.get("raw_query"):
                content_lines.append("## Query")
                content_lines.append(session["raw_query"])
                content_lines.append("")

            # Sources
            sources = await db.get_sources_for_session(session["id"])
            if sources:
                content_lines.append("## Sources")
                for source in sources:
                    source_slug = self._slugify(source["url"])
                    self.link_map[source["id"]] = f"Sources/{source_slug}"
                    content_lines.append(
                        f"- [[Sources/{source_slug}|{source['title'] or source['url']}]] (quality: {source['quality']})"
                    )
                content_lines.append("")

            # Report content if exists
            if session.get("report_markdown"):
                content_lines.append("## Report")
                content_lines.append(session["report_markdown"])
                content_lines.append("")

            # Write file
            await self._write_file(
                self.vault_structure["Research"] / filename, "\n".join(content_lines)
            )
            self.generated_files[session["id"]] = (
                self.vault_structure["Research"] / filename
            )

    async def _export_journal(self) -> None:
        """Export journal entries."""
        db = db_module.database
        if not db:
            return

        entries = await db.list_journal_entries()

        # Group by date for daily notes
        by_date = {}
        for entry in entries:
            date = datetime.fromisoformat(entry["created_at"]).strftime("%Y-%m-%d")
            if date not in by_date:
                by_date[date] = []
            by_date[date].append(entry)

        for date, items in by_date.items():
            filename = f"{date}.md"
            content_lines = []

            # Front matter
            front_matter = {
                "created": date,
                "updated": datetime.now(timezone.utc).isoformat(),
                "type": "journal",
                "tags": [],
            }
            content_lines.append("---")
            content_lines.append(json.dumps(front_matter, indent=2))
            content_lines.append("---")
            content_lines.append("")

            # Title
            content_lines.append(f"# Daily Note - {date}")
            content_lines.append("")

            # Journal entries
            for entry in items:
                if entry.get("title"):
                    content_lines.append(f"## {entry['title']}")
                else:
                    content_lines.append(f"## Entry {entry['id'][:8]}")

                # Tags
                if entry.get("tags"):
                    tags = (
                        json.loads(entry["tags"])
                        if isinstance(entry["tags"], str)
                        else entry["tags"]
                    )
                    content_lines.append(
                        f"Tags: {', '.join(f'#{tag}' for tag in tags)}"
                    )

                # Mood if available
                if entry.get("mood_score"):
                    content_lines.append(f"Mood: {entry['mood_score']}/10")

                # Content
                content_lines.append("")
                content_lines.append(entry.get("body_md", ""))
                content_lines.append("")

            await self._write_file(
                self.vault_structure["Journal"] / filename, "\n".join(content_lines)
            )
            self.generated_files[f"journal_{date}"] = (
                self.vault_structure["Journal"] / filename
            )

    async def _export_memory(self) -> None:
        """Export memory facts."""
        db = db_module.database
        if not db:
            return

        # Get memory records
        memories = await self._get_all_memory_records()

        # Group by category
        by_category = {}
        for memory in memories:
            category = memory.get("category", "uncategorized")
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(memory)

        for category, items in by_category.items():
            category_dir = self.vault_structure["Memory"] / self._sanitize_filename(
                category
            )
            category_dir.mkdir(exist_ok=True)

            # Create index file for category
            index_content = []
            index_content.append(f"# {category.title()} Memory")
            index_content.append("")

            for item in items:
                filename = self._sanitize_filename(
                    item.get("slug", f"fact-{item['id']}")
                )
                filename += ".md"

                # Individual fact file
                fact_content = []

                # Front matter
                front_matter = {
                    "created": item.get(
                        "created_at", datetime.now(timezone.utc).isoformat()
                    ),
                    "updated": item.get(
                        "updated_at", datetime.now(timezone.utc).isoformat()
                    ),
                    "type": "memory",
                    "tags": item.get("tags", []),
                    "nexus_id": item["id"],
                    "confidence": item.get("confidence", 0.0),
                    "category": category,
                }
                fact_content.append("---")
                fact_content.append(json.dumps(front_matter, indent=2))
                fact_content.append("---")
                fact_content.append("")

                # Content
                fact_content.append(f"# {item.get('topic', 'Memory Fact')}")
                fact_content.append("")
                fact_content.append("## Content")
                fact_content.append(item.get("content", ""))
                fact_content.append("")

                # Links
                if item.get("external_links"):
                    fact_content.append("## External Links")
                    for link in item["external_links"]:
                        fact_content.append(
                            f"- [{link.get('title', link['url'])}]({link['url']})"
                        )
                    fact_content.append("")

                await self._write_file(category_dir / filename, "\n".join(fact_content))

                # Add to index
                index_content.append(
                    f"- [[{category}/{filename}|{item.get('topic', 'Fact')[:50]}…]]"
                )

            index_content.append("")
            await self._write_file(category_dir / "index.md", "\n".join(index_content))

            self.generated_files[f"memory_{category}"] = category_dir / "index.md"

    async def _export_conversations(self) -> None:
        """Export chat conversations."""
        db = db_module.database
        if not db:
            return

        conversations = await db.get_all_conversations()

        for conv in conversations:
            messages = await db.get_conversation_history(conv["id"], limit=1000)
            if not messages:
                continue

            # Generate filename from conversation title or first message
            timestamp = (
                datetime.now(timezone.utc).strftime("%Y-%m-%d")
                if isinstance(conv["id"], str)
                else "1970-01-01"
            )
            conv_slug = self._slugify(conv["title"] or f"conv-{conv['id']}")
            filename = f"{timestamp} {conv_slug}.md"

            content_lines = []

            # Front matter
            front_matter = {
                "created": conv["created_at"],
                "updated": conv.get("updated_at", conv["created_at"]),
                "type": "conversation",
                "tags": ["chat", "conversation"],
                "nexus_id": conv["id"],
                "message_count": conv.get("message_count", len(messages)),
            }
            content_lines.append("---")
            content_lines.append(json.dumps(front_matter, indent=2))
            content_lines.append("---")
            content_lines.append("")

            # Title
            content_lines.append(
                f"# {conv['title'] or f'Conversation {conv["id"][:8]}'}"
            )
            content_lines.append("")

            # Messages
            content_lines.append(f"## Messages ({len(messages)})")
            content_lines.append("")

            for msg in messages:
                role = msg["role"].capitalize()
                content = msg["content"]
                agent_info = (
                    f" (agent: {msg['agent_id']})" if msg.get("agent_id") else ""
                )

                content_lines.append(f"### {role}{agent_info}")
                content_lines.append(f"_@{msg['timestamp']}_")
                content_lines.append("")
                content_lines.append(f"{content}")
                content_lines.append("")

            await self._write_file(
                self.vault_structure["Conversations"] / filename,
                "\n".join(content_lines),
            )
            self.generated_files[f"conv_{conv['id']}"] = (
                self.vault_structure["Conversations"] / filename
            )

    async def _export_sources(self) -> None:
        """Export scraped sources."""
        db = db_module.database
        if not db:
            return

        # Get sources from research sessions
        sources = await self._get_all_scraped_sources()

        for source in sources:
            # Create nested directory structure by domain
            domain = urlparse(source["url"]).netloc or "unknown"
            domain_dir = self.vault_structure["Sources"] / domain
            domain_dir.mkdir(exist_ok=True)

            # Generate filename
            slug = self._slugify(source.get("title", source["url"]))
            filename = f"{slug}.md"

            content_lines = []

            # Front matter
            front_matter = {
                "created": source.get(
                    "scraped_at", datetime.now(timezone.utc).isoformat()
                ),
                "updated": datetime.now(timezone.utc).isoformat(),
                "type": "source",
                "tags": ["source", "scraped", domain],
                "nexus_id": source["id"],
                "url": source["url"],
                "domain": domain,
                "quality_score": source.get("quality_score", 0.0),
                "is_paywalled": source.get("is_paywalled", False),
            }
            content_lines.append("---")
            content_lines.append(json.dumps(front_matter, indent=2))
            content_lines.append("---")
            content_lines.append("")

            # Title and metadata
            content_lines.append(f"# {source.get('title', 'Untitled')}")
            content_lines.append("")
            content_lines.append(f"**URL:** [{source['url']}]({source['url']})")
            content_lines.append(f"**Domain:** {domain}")
            content_lines.append(f"**Quality:** {source.get('quality_score', 0):.2f}")
            content_lines.append("")

            # Content if available
            if source.get("content"):
                content_lines.append("## Content")
                content_lines.append(source["content"][:50000])  # Limit size
                content_lines.append("")

                if len(source["content"]) > 50000:
                    content_lines.append("_Content truncated for export_")

            await self._write_file(domain_dir / filename, "\n".join(content_lines))
            self.generated_files[source["id"]] = domain_dir / filename

    async def _generate_manifest(
        self,
        timestamp: datetime,
        scope: str,
    ) -> None:
        """Generate export manifest."""
        manifest = {
            "version": "1.0",
            "export_timestamp": timestamp.isoformat(),
            "scope": scope,
            "vault_path": str(self.output_dir),
            "total_files": len(self.generated_files),
            "collections": {
                "Research": await self._count_files(self.vault_structure["Research"]),
                "Journal": await self._count_files(self.vault_structure["Journal"]),
                "Memory": await self._count_files(self.vault_structure["Memory"]),
                "Conversations": await self._count_files(
                    self.vault_structure["Conversations"]
                ),
                "Sources": await self._count_files(self.vault_structure["Sources"]),
            },
            "generated_files": {k: str(v) for k, v in self.generated_files.items()},
        }

        await self._write_file(
            self.vault_structure["_meta"] / "export_manifest.json",
            json.dumps(manifest, indent=2),
        )

    async def _generate_tags_json(self) -> None:
        """Generate consolidated tags file."""
        # Simple implementation - in production, collect tags from all content
        tags_data = {
            "version": "1.0",
            "tags": {},
            "collections": {
                "Research": ["research", "sources", "outlines", "reports"],
                "Journal": ["journal", "daily", "notes", "mood"],
                "Memory": ["memory", "facts", "knowledge", "long-term"],
                "Conversations": ["chat", "conversation", "assistant"],
                "Sources": ["source", "scraped", "web", "article"],
            },
        }

        await self._write_file(
            self.vault_structure["_meta"] / "tags.json",
            json.dumps(tags_data, indent=2),
        )

    async def _write_file(self, path: Path, content: str) -> None:
        """Write content to file with proper encoding."""
        async with asyncio.Lock():
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)

    def _sanitize_filename(self, filename: str) -> str:
        """Remove illegal characters for Windows filenames."""
        # Remove illegal characters
        sanitized = ILLEGAL_CHARS.sub("", filename)
        # Limit length
        if len(sanitized) > MAX_FILENAME_LENGTH:
            sanitized = sanitized[:MAX_FILENAME_LENGTH]
        # Ensure no leading/trailing spaces or dots
        sanitized = sanitized.strip(" .	")
        # If empty after sanitization, use fallback
        if not sanitized:
            sanitized = f"untitled_{hash(filename) % 1000}"
        return sanitized

    def _slugify(self, text: str) -> str:
        """Convert text to URL-safe slug."""
        # Convert to lowercase, replace spaces with hyphens, remove special chars
        slug = re.sub(r"[^\w\s-]", "", text.lower())
        slug = re.sub(r"[-\s]+", "-", slug).strip("-")
        return slug or "untitled"

    async def _get_all_memory_records(self) -> list[dict]:
        """Get all memory records from database."""
        db = db_module.database
        if not db:
            return []

        # Simplified implementation - in production, query directly
        try:
            # This is a placeholder - implement actual query
            return []
        except Exception as e:
            logger.error("Failed to get memory records: %s", e)
            return []

    async def _get_all_scraped_sources(self) -> list[dict]:
        """Get all scraped sources from database."""
        db = db_module.database
        if not db:
            return []

        # Simplified implementation
        try:
            # Placeholder - implement actual query
            return []
        except Exception as e:
            logger.error("Failed to get scraped sources: %s", e)
            return []

    async def _count_files(self, directory: Path) -> int:
        """Count markdown files in directory."""
        try:
            return len(list(directory.rglob("*.md")))
        except Exception:
            return 0


# Global exporter instance
_exporter: ObsidianExporter | None = None


async def get_obsidian_exporter(output_dir: Path | None = None) -> ObsidianExporter:
    """Get or create the global Obsidian exporter instance."""
    global _exporter
    if _exporter is None:
        _exporter = ObsidianExporter(output_dir)
    return _exporter
