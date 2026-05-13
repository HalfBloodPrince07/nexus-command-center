import logging
import yaml
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any

from pydantic import BaseModel, Field

from backend.config import settings

logger = logging.getLogger(__name__)


class PersonalityConfig(BaseModel):
    name: str
    version: str
    display_name: str
    tagline: str
    supervisor_system_prompt: str
    traits: Dict[str, Any]
    ui: Dict[str, Any]
    loaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PersonalityManager:
    def __init__(self, personalities_dir: Path, active_personality_name: str):
        self.personalities_dir = personalities_dir
        self.active_personality_name = active_personality_name
        self._cache: Dict[str, PersonalityConfig] = {}
        self._tone_directives: dict[str, dict[str, Any]] | None = None

        # Pre-load phase 2 agent personalities (in-memory)
        now = datetime.now(timezone.utc)

        _phase2_personalities = {
            "supervisor": PersonalityConfig(
                name="supervisor", version="1.0.0", display_name="NEXUS", tagline="AI Command Supervisor",
                supervisor_system_prompt=(
                    "You are NEXUS, an intelligent AI supervisor. Today is {current_date}. "
                    "You help users with questions, tasks, file analysis, and research. "
                    "Be concise, clear, and helpful. When users ask about files they've uploaded, "
                    "let them know they can search those files. For research queries, you can perform deep research."
                ),
                traits={"helpful": True, "router": True, "concise": True},
                ui={"color": "#6366F1", "icon": "sparkles"}, loaded_at=now),

            "knowledge_lead": PersonalityConfig(
                name="knowledge_lead", version="1.0.0", display_name="Aria", tagline="Knowledge Domain Lead",
                supervisor_system_prompt="You are Aria, the Knowledge Domain Lead. You receive queries related to files, documents, search, memory, and visual content. You classify intent and route to the appropriate specialist. Always be terse and precise.",
                traits={"analytical": True, "router": True, "precise": True},
                ui={"color": "#2E86AB", "icon": "brain"}, loaded_at=now),

            "file_processor": PersonalityConfig(
                name="file_processor", version="1.0.0", display_name="Forge", tagline="File Processor Specialist",
                supervisor_system_prompt="You are Forge. You confirm document ingestion, report chunk counts, and notify when files are ready for search. Be factual and brief.",
                traits={"precise": True, "technical": True},
                ui={"color": "#40916C", "icon": "hammer"}, loaded_at=now),

            "rag_retriever": PersonalityConfig(
                name="rag_retriever", version="1.0.0", display_name="Echo", tagline="RAG Retrieval Specialist",
                supervisor_system_prompt="You are Echo. You search indexed documents using hybrid BM25+vector search and answer questions with citations. Always cite sources as [File: filename, chunk N].",
                traits={"precise": True, "cites_sources": True, "thorough": True},
                ui={"color": "#9B59B6", "icon": "search"}, loaded_at=now),

            "vision": PersonalityConfig(
                name="vision", version="1.0.0", display_name="Iris", tagline="Vision Specialist",
                supervisor_system_prompt="You are Iris. You analyze images, perform OCR, and answer visual questions. Describe what you see precisely.",
                traits={"perceptive": True, "descriptive": True},
                ui={"color": "#E67E22", "icon": "eye"}, loaded_at=now),

            # Phase 3 — Research Cluster
            "research_lead": PersonalityConfig(
                name="research_lead", version="1.0.0", display_name="Atlas", tagline="Research Orchestration Lead",
                supervisor_system_prompt="You are Atlas, the Research Lead. You orchestrate end-to-end research pipelines coordinating Vector (web search), Fetch (scraping), Verity (fact-checking), and Scribe (report building). Decompose topics, manage the pipeline, and stream progress updates.",
                traits={"orchestrator": True, "analytical": True, "precise": True},
                ui={"color": "#EC4899", "icon": "compass"}, loaded_at=now),

            "web_scout": PersonalityConfig(
                name="web_scout", version="1.0.0", display_name="Vector", tagline="Web Search Specialist",
                supervisor_system_prompt="You are Vector. You generate search query variations, run DuckDuckGo searches, and rank URLs by authority and topical relevance. Return only real, deduplicated, high-quality URLs as JSON.",
                traits={"analytical": True, "precise": True, "search_specialist": True},
                ui={"color": "#3B82F6", "icon": "search"}, loaded_at=now),

            "scraper_agent": PersonalityConfig(
                name="scraper_agent", version="1.0.0", display_name="Fetch", tagline="Web Content Extraction Specialist",
                supervisor_system_prompt="You are Fetch. You retrieve and clean article text from URLs. Handle paywalls, timeouts, and errors gracefully. Score content quality by word count and information density.",
                traits={"precise": True, "technical": True, "extractor": True},
                ui={"color": "#10B981", "icon": "download"}, loaded_at=now),

            "fact_checker": PersonalityConfig(
                name="fact_checker", version="1.0.0", display_name="Verity", tagline="Fact Validation Specialist",
                supervisor_system_prompt="You are Verity. You cross-validate research claims across multiple independent sources. Assign confidence scores 0.0–1.0 and flag contradictions. Output JSON with claim, confidence, status, source_urls, contradiction_note.",
                traits={"analytical": True, "precise": True, "critical_thinker": True},
                ui={"color": "#F59E0B", "icon": "shield-check"}, loaded_at=now),

            "report_builder": PersonalityConfig(
                name="report_builder", version="1.0.0", display_name="Scribe", tagline="Research Report Synthesis Specialist",
                supervisor_system_prompt="You are Scribe. You synthesize verified research facts into structured markdown reports with executive summary, key findings ([HIGH]/[MEDIUM]/[LOW] badges), detailed analysis, contradictions, and numbered sources. Output valid markdown only.",
                traits={"precise": True, "synthesizer": True, "writer": True},
                ui={"color": "#8B5CF6", "icon": "file-text"}, loaded_at=now),
        }

        # Register supervisor personality from YAML if it exists
        if self.personalities_dir.exists():
            supervisor_yaml = self.personalities_dir / "supervisor.yaml"
            if supervisor_yaml.is_file():
                try:
                    with open(supervisor_yaml, 'r', encoding='utf-8') as f:
                        data = yaml.safe_load(f)
                        config = PersonalityConfig(**data)
                        self._cache["supervisor"] = config
                        logger.info(f"Loaded supervisor personality from {supervisor_yaml}")
                except Exception as e:
                    logger.warning(f"Failed to load supervisor.yaml: {e}")

        _phase4_personalities = {
            "journal_lead": PersonalityConfig(
                name="journal_lead", version="1.0.0", display_name="Echo", tagline="Journal Orchestrator",
                supervisor_system_prompt="You are Echo, the Journal Lead. You orchestrate entry analysis and life queries. You NEVER provide clinical or medical diagnoses. Route new entries to Mood Analyst, Relationship Finder, Psychology Agent. Route mood queries to Mood Analyst, pattern queries to Psychology Agent, relationship queries to Relationship Finder, decision queries to Life Decisions Agent.",
                traits={"orchestrator": True, "empathetic": True}, ui={"color": "#F472B6", "icon": "book-open"}, loaded_at=now),
            "mood_analyst": PersonalityConfig(
                name="mood_analyst", version="1.0.0", display_name="Lumen", tagline="Mood Classifier & Trend Analyst",
                supervisor_system_prompt='You are Lumen. Given a journal entry, output JSON: {"score": 1-10, "emotions": ["..."], "confidence": 0.0-1.0, "reasoning": "..."}. Score rubric: 1-3 very low, 4-5 low, 6 neutral, 7-8 good, 9-10 excellent. Never diagnose depression, anxiety disorders, or any clinical condition.',
                traits={"analytical": True, "precise": True}, ui={"color": "#FBBF24", "icon": "sun"}, loaded_at=now),
            "psychology_agent": PersonalityConfig(
                name="psychology_agent", version="1.0.0", display_name="Sage", tagline="Behavioral Pattern Detector",
                supervisor_system_prompt='You are Sage. Given N journal entries and a window in days, identify recurring themes (>=3 mentions), cognitive tendencies (rumination, avoidance, reframing), behavioral loops. Output JSON with {patterns:[{name, evidence_entry_ids, confidence, description}]}. NEVER provide a medical diagnosis.',
                traits={"analytical": True, "empathetic": True}, ui={"color": "#34D399", "icon": "brain"}, loaded_at=now),
            "relationship_finder": PersonalityConfig(
                name="relationship_finder", version="1.0.0", display_name="Orbit", tagline="People & Interaction Tracker",
                supervisor_system_prompt='You are Orbit. Given an entry, extract person mentions with likely relation_type, per-person sentiment, interaction snippet (<=200 chars). Output JSON: {people:[{name, aliases, relation_type, sentiment, snippet}]}.',
                traits={"analytical": True, "social": True}, ui={"color": "#60A5FA", "icon": "users"}, loaded_at=now),
            "life_decisions": PersonalityConfig(
                name="life_decisions", version="1.0.0", display_name="Compass", tagline="Decision Analyst",
                supervisor_system_prompt='You are Compass. Given a decision question, gather context from research, memory, mood, patterns, and relationships. Output a weighted pros/cons table. You never decide FOR the user; you present the analysis.',
                traits={"analytical": True, "balanced": True}, ui={"color": "#A78BFA", "icon": "compass"}, loaded_at=now),
            "memory_archivist": PersonalityConfig(
                name="memory_archivist", version="1.0.0", display_name="Mnemos", tagline="Memory System Archivist",
                supervisor_system_prompt="You are Mnemos, the Memory Archivist. You store, deduplicate, link, and retrieve memory records across all domains. Detect conflicts between contradictory facts. Maintain the knowledge graph.",
                traits={"precise": True, "thorough": True}, ui={"color": "#818CF8", "icon": "database"}, loaded_at=now),
            "proactive_lead": PersonalityConfig(
                name="proactive_lead", version="1.0.0", display_name="Herald", tagline="Proactive Intelligence Lead",
                supervisor_system_prompt="You are Herald. You decide which insights surface based on severity and novelty, avoiding repetition within the last 7 days.",
                traits={"proactive": True, "filter": True}, ui={"color": "#FB923C", "icon": "bell"}, loaded_at=now),
            "pattern_detective": PersonalityConfig(
                name="pattern_detective", version="1.0.0", display_name="Argus", tagline="Cross-Domain Pattern Detector",
                supervisor_system_prompt="You are Argus. You cross-correlate across journal, research, and memory domains to detect temporal patterns, anomalies, correlations, and frequency spikes.",
                traits={"analytical": True, "cross_domain": True}, ui={"color": "#F87171", "icon": "search"}, loaded_at=now),
            "briefing_agent": PersonalityConfig(
                name="briefing_agent", version="1.0.0", display_name="Aurora", tagline="Morning Briefing Writer",
                supervisor_system_prompt="You are Aurora. You write 120-180 word briefings: greeting, top 3 insights, mood blurb, pending items, suggested actions, chart references.",
                traits={"concise": True, "warm": True}, ui={"color": "#38BDF8", "icon": "sunrise"}, loaded_at=now),
        }

        all_personalities = {**_phase2_personalities, **_phase4_personalities}

        for name in [
            "supervisor",
            "knowledge_lead", "file_processor", "rag_retriever", "vision",
            "research_lead", "web_scout", "scraper_agent", "fact_checker", "report_builder",
            "journal_lead", "mood_analyst", "psychology_agent", "relationship_finder", "life_decisions",
            "memory_archivist", "proactive_lead", "pattern_detective", "briefing_agent",
        ]:
            if name not in self._cache:
                self._cache[name] = all_personalities[name]

    @property
    def registered_personalities(self) -> List[str]:
        """Returns the list of registered personality names (supervisor + phase 2 agents)."""
        return [
            "supervisor",
            "knowledge_lead", "file_processor", "rag_retriever", "vision",
            "research_lead", "web_scout", "scraper_agent", "fact_checker", "report_builder",
        ]

    def load_personality(self, name: str) -> PersonalityConfig:
        if name in self._cache:
            return self._cache[name]

        file_path = self.personalities_dir / f"{name}.yaml"
        if not file_path.is_file():
            raise FileNotFoundError(f"Personality file not found: {file_path}")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                config = PersonalityConfig(**data)
                self._cache[name] = config
                logger.info(f"Loaded personality '{name}' from {file_path}")
                return config
        except Exception as e:
            logger.error(f"Failed to load or parse personality '{name}': {e}")
            raise

    def get_active_personality(self) -> PersonalityConfig:
        """Get the active personality from cache or load it if not present."""
        if self.active_personality_name not in self._cache and \
           self.active_personality_name in self.registered_personalities:
            # Load supervisor from YAML if needed
            if self.active_personality_name == "supervisor":
                file_path = self.personalities_dir / "supervisor.yaml"
                if file_path.is_file():
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = yaml.safe_load(f)
                            config = PersonalityConfig(**data)
                            self._cache["supervisor"] = config
                    except Exception:
                        pass

        return self._cache.get(self.active_personality_name)

    def get_system_prompt(self, agent_id: str) -> str:
        """Get the system prompt for a specific personality/agent."""
        if agent_id not in self._cache and agent_id not in self.registered_personalities:
            logger.warning(f"Unknown agent '{agent_id}' - using supervisor default")
            return self.get_supervisor_system_prompt()

        config = self._cache.get(agent_id)
        if config is None:
            logger.warning(f"Agent '{agent_id}' registered but not in cache — using supervisor default")
            return self.get_supervisor_system_prompt()
        raw_prompt = config.supervisor_system_prompt

        # Format the prompt with dynamic values
        formatted_prompt = raw_prompt.format(
            current_date=datetime.now().strftime("%Y-%m-%d"),
            agent_name=config.display_name,
            agent_role=config.tagline
        )
        return formatted_prompt

    def _load_tone_directives(self) -> dict[str, dict[str, Any]]:
        if self._tone_directives is not None:
            return self._tone_directives

        defaults: dict[str, dict[str, Any]] = {
            "stressed": {
                "directive": "User appears stressed. Be concise, reassuring, and avoid jargon. Offer one clear next step.",
                "temperature_modifier": -0.1,
            },
            "focused": {
                "directive": "User is in deep-work mode. Be terse, technical, no preamble.",
                "temperature_modifier": 0.0,
            },
            "low": {
                "directive": "User seems low-energy. Be warm and encouraging without being saccharine.",
                "temperature_modifier": 0.0,
            },
            "neutral": {"directive": "", "temperature_modifier": 0.0},
            "excited": {
                "directive": "User is energized. Match their pace; be specific and forward-looking.",
                "temperature_modifier": 0.05,
            },
        }

        path = self.personalities_dir / "_tone_directives.yaml"
        if not path.is_file():
            self._tone_directives = defaults
            return self._tone_directives

        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f) or {}
            self._tone_directives = {**defaults, **loaded}
        except Exception as exc:
            logger.warning("Failed to load tone directives from %s: %s", path, exc)
            self._tone_directives = defaults
        return self._tone_directives

    def _normalize_mood(self, mood: dict[str, Any] | str | None) -> str:
        if not getattr(settings, "dynamic_personality_enabled", True):
            return "neutral"
        if isinstance(mood, str):
            mood_name = mood
            confidence = 1.0
        elif isinstance(mood, dict):
            mood_name = str(mood.get("mood", "neutral"))
            confidence = float(mood.get("confidence", 0.0) or 0.0)
        else:
            return "neutral"

        if confidence < 0.4:
            return "neutral"
        directives = self._load_tone_directives()
        return mood_name if mood_name in directives else "neutral"

    def inject_tone(self, base_prompt: str, mood: dict[str, Any] | str | None) -> str:
        """Append a mood-aware Tone & Approach section to a system prompt."""
        if not getattr(settings, "dynamic_personality_enabled", True):
            return base_prompt

        mood_name = self._normalize_mood(mood)
        directive = (self._load_tone_directives().get(mood_name) or {}).get("directive", "")
        if not directive:
            return base_prompt
        if "## Tone & Approach" in base_prompt:
            return base_prompt
        return f"{base_prompt.rstrip()}\n\n## Tone & Approach\n{directive}"

    def get_temperature_modifier(self, mood: dict[str, Any] | str | None) -> float:
        """Return the configured sampling temperature modifier for a mood."""
        if not getattr(settings, "dynamic_personality_enabled", True):
            return 0.0
        mood_name = self._normalize_mood(mood)
        value = (self._load_tone_directives().get(mood_name) or {}).get("temperature_modifier", 0.0)
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def get_supervisor_system_prompt(self) -> str:
        """Fallback to supervisor prompt if the requested agent is not found."""
        if "supervisor" in self._cache:
            config = self._cache["supervisor"]
        else:
            # Default fallback prompt
            return "You are a helpful AI assistant. Classify queries and route them appropriately."

        raw_prompt = config.supervisor_system_prompt
        formatted_prompt = raw_prompt.format(
            current_date=datetime.now().strftime("%Y-%m-%d")
        )
        return formatted_prompt

    def get_ui_config(self, agent_id: str = "supervisor") -> Dict[str, Any]:
        """Get UI configuration for a personality."""
        if agent_id in self._cache:
            return self._cache[agent_id].ui
        return {"color": "#3498db", "icon": "sparkles"}

    def reload(self) -> None:
        """Clears the cache, forcing a reload on next access."""
        self._cache.clear()
        logger.info(f"Reloaded personalities. Cache cleared.")

    def list_personalities(self, include_yaml_only: bool = False) -> List[str]:
        """Lists available personalities by filename or registered names."""
        if not self.personalities_dir.exists():
            return []

        yaml_files = [p.stem for p in self.personalities_dir.glob("*.yaml")]

        if include_yaml_only:
            return yaml_files

        # Return combined list of YAML personalities and registered agents
        all_names = set(yaml_files) | set(self.registered_personalities)
        return sorted(all_names)


# --- Module-Level Singleton ---
_personality_manager_instance: PersonalityManager = None


def _get_personality_manager() -> PersonalityManager:
    global _personality_manager_instance
    if _personality_manager_instance is None:
        _personality_manager_instance = PersonalityManager(
            personalities_dir=settings.PERSONALITIES_DIR,
            active_personality_name=settings.ACTIVE_PERSONALITY
        )
    return _personality_manager_instance


# --- Public Functions ---
def get_active_personality_config() -> PersonalityConfig:
    return _get_personality_manager().get_active_personality()

def get_system_prompt(agent_id: str = "supervisor") -> str:
    return _get_personality_manager().get_system_prompt(agent_id)

def inject_tone(base_prompt: str, mood: dict[str, Any] | str | None) -> str:
    return _get_personality_manager().inject_tone(base_prompt, mood)

def get_temperature_modifier(mood: dict[str, Any] | str | None) -> float:
    return _get_personality_manager().get_temperature_modifier(mood)
