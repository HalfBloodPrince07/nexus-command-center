from __future__ import annotations

import json
import logging
import re
from typing import Any

from backend.app.agents._lm_studio import complete_chat
from backend.config import settings
from backend.core import database as db

logger = logging.getLogger(__name__)

_nlp = None


def _get_nlp():
    global _nlp
    if _nlp is not None:
        return _nlp
    try:
        import spacy
        _nlp = spacy.load("en_core_web_sm")
    except Exception as exc:
        logger.warning("spaCy model not available, falling back to LLM-only NER: %s", exc)
        _nlp = False
    return _nlp


def _vader_sentiment(text: str) -> float:
    try:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        analyzer = SentimentIntensityAnalyzer()
        return analyzer.polarity_scores(text)["compound"]
    except Exception:
        return 0.0


def _extract_json(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\"people\"\s*:\s*\[.*?\]\s*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return {"people": []}


class RelationshipFinderAgent:
    async def process_entry(self, entry_id: str, body: str) -> list[dict[str, Any]]:
        names_from_spacy: list[str] = []
        nlp = _get_nlp()
        if nlp and nlp is not False:
            doc = nlp(body[:5000])
            names_from_spacy = list({ent.text for ent in doc.ents if ent.label_ == "PERSON"})

        messages = [
            {"role": "system", "content": (
                "You are Orbit. Given a journal entry, extract people mentioned.\n"
                "Output ONLY valid JSON: {\"people\": [{\"name\": \"...\", \"aliases\": [], \"relation_type\": \"friend|family|colleague|unknown\", \"sentiment\": <-1.0 to 1.0>, \"snippet\": \"<= 200 chars\"}]}\n"
                "Merge duplicates. Use context to infer relation_type."
            )},
            {"role": "user", "content": (
                f"Entry:\n{body[:3000]}\n\n"
                + (f"spaCy detected these names: {', '.join(names_from_spacy)}" if names_from_spacy else "")
            )},
        ]

        raw = await complete_chat(
            messages=messages,
            model=settings.lm_studio_model,
            temperature=0.3,
            max_tokens=768,
        )
        result = _extract_json(raw)
        people = result.get("people", [])

        processed = []
        for person in people:
            name = person.get("name", "").strip()
            if not name or len(name) < 2:
                continue

            snippet = person.get("snippet", "")[:200]
            vader_score = _vader_sentiment(snippet) if snippet else 0.0
            llm_score = float(person.get("sentiment", 0.0))
            sentiment = (vader_score + llm_score) / 2.0

            rel_id = await db.upsert_relationship(
                name=name,
                aliases=json.dumps(person.get("aliases", [])),
                relation_type=person.get("relation_type", "unknown"),
            )

            await db.add_interaction(
                relationship_id=rel_id,
                entry_id=entry_id,
                sentiment=sentiment,
                snippet=snippet,
            )

            processed.append({
                "name": name,
                "relation_type": person.get("relation_type", "unknown"),
                "sentiment": round(sentiment, 3),
                "snippet": snippet,
            })

        return processed

    async def graph(self) -> dict[str, Any]:
        from backend.models.charts import ChartPayload, GraphNode, GraphEdge

        async with db.get_session() as session:
            from sqlalchemy import select
            from backend.core.database import Relationship, Interaction

            rels = (await session.execute(select(Relationship))).scalars().all()
            if not rels:
                return ChartPayload(
                    id="relationship-graph",
                    type="graph",
                    title="Relationships",
                    nodes=[GraphNode(id="user", label="You", size=2.0, color="#6366F1")],
                    edges=[GraphEdge(source="user", target="user", label="self", weight=0)],
                    meta={},
                ).model_dump()

            nodes = [GraphNode(id="user", label="You", size=2.0, color="#6366F1")]
            edges = []

            for r in rels:
                sentiment = r.sentiment_avg or 0.0
                if sentiment > 0.3:
                    color = "#22c55e"
                elif sentiment < -0.3:
                    color = "#ef4444"
                else:
                    color = "#94a3b8"

                nodes.append(GraphNode(
                    id=r.id,
                    label=r.name,
                    size=min(3.0, 1.0 + (r.interaction_count or 0) * 0.2),
                    color=color,
                    category=r.relation_type or "unknown",
                    metadata={"sentiment": sentiment, "interactions": r.interaction_count},
                ))
                edges.append(GraphEdge(
                    source="user",
                    target=r.id,
                    weight=max(0.1, abs(sentiment)),
                    color=color,
                    label=r.relation_type,
                ))

        return ChartPayload(
            id="relationship-graph",
            type="graph",
            title="Relationships",
            nodes=nodes,
            edges=edges,
            meta={"decay_factor": settings.RELATIONSHIP_SENTIMENT_DECAY},
        ).model_dump()
