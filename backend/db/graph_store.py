"""Neo4j knowledge graph for GraphRAG — entity and relationship storage.

Completely optional: if Neo4j is unavailable or NEO4J_ENABLED=False in config,
every method is a no-op and the rest of the system keeps working.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from backend.config import settings

logger = logging.getLogger(__name__)


class GraphStore:
    """Async Neo4j wrapper for document entities and relationships."""

    def __init__(self) -> None:
        self._driver: Any = None
        self._available: bool = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        if not settings.NEO4J_ENABLED:
            logger.info("Neo4j disabled via config — graph features inactive")
            return
        try:
            from neo4j import AsyncGraphDatabase  # type: ignore[import]

            self._driver = AsyncGraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            )
            await self._driver.verify_connectivity()
            await self._create_schema()
            self._available = True
            logger.info("Neo4j connected: %s", settings.NEO4J_URI)
        except ImportError:
            logger.warning(
                "neo4j package not installed — install with: "
                "conda run -n Command pip install neo4j"
            )
        except Exception as exc:
            logger.warning("Neo4j unavailable (%s) — graph features disabled", exc)

    async def close(self) -> None:
        if self._driver is not None:
            await self._driver.close()
            self._driver = None
        self._available = False

    async def _create_schema(self) -> None:
        constraints = [
            "CREATE CONSTRAINT doc_id IF NOT EXISTS FOR (d:Document) REQUIRE d.file_id IS UNIQUE",
            "CREATE CONSTRAINT entity_name IF NOT EXISTS FOR (e:Entity) REQUIRE (e.name, e.type) IS UNIQUE",
        ]
        async with self._driver.session() as session:
            for cypher in constraints:
                try:
                    await session.run(cypher)
                except Exception:
                    pass  # Constraint may already exist

    # ------------------------------------------------------------------
    # Document operations
    # ------------------------------------------------------------------

    async def upsert_document(self, file_id: str, name: str, summary: str) -> None:
        if not self._available:
            return
        cypher = """
        MERGE (d:Document {file_id: $file_id})
        SET d.name = $name, d.summary = $summary
        """
        async with self._driver.session() as session:
            await session.run(cypher, file_id=file_id, name=name, summary=summary)

    async def delete_document(self, file_id: str) -> None:
        """Remove a Document node and detach all its relationships."""
        if not self._available:
            return
        cypher = "MATCH (d:Document {file_id: $file_id}) DETACH DELETE d"
        async with self._driver.session() as session:
            await session.run(cypher, file_id=file_id)

    # ------------------------------------------------------------------
    # Entity / relationship operations
    # ------------------------------------------------------------------

    async def upsert_entities(
        self,
        file_id: str,
        entities: list[dict],
        relationships: list[dict],
    ) -> None:
        """Store entities as nodes and link them to the document.

        Args:
            file_id: Parent document file ID.
            entities: List of {"name": str, "type": str} dicts.
            relationships: List of {"source": str, "target": str, "type": str} dicts.
        """
        if not self._available or not entities:
            return

        async with self._driver.session() as session:
            # Upsert Entity nodes and HAS_ENTITY edges
            for ent in entities:
                name = (ent.get("name") or "").strip()
                etype = (ent.get("type") or "CONCEPT").strip().upper()
                if not name:
                    continue
                await session.run(
                    """
                    MERGE (e:Entity {name: $name, type: $type})
                    WITH e
                    MATCH (d:Document {file_id: $file_id})
                    MERGE (d)-[:HAS_ENTITY]->(e)
                    """,
                    name=name,
                    type=etype,
                    file_id=file_id,
                )

            # Upsert RELATES_TO edges between entities
            for rel in relationships:
                src = (rel.get("source") or "").strip()
                tgt = (rel.get("target") or "").strip()
                rtype = (rel.get("type") or "RELATED_TO").strip().upper().replace(" ", "_")
                if not src or not tgt:
                    continue
                await session.run(
                    """
                    MATCH (a:Entity {name: $src}), (b:Entity {name: $tgt})
                    MERGE (a)-[r:RELATES_TO {type: $rtype}]->(b)
                    """,
                    src=src,
                    tgt=tgt,
                    rtype=rtype,
                )

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    async def find_related_files(self, file_id: str, depth: int = 2) -> list[str]:
        """Return file_ids of documents sharing entities with the given document."""
        if not self._available:
            return []
        cypher = """
        MATCH (d:Document {file_id: $file_id})-[:HAS_ENTITY]->(e:Entity)
              <-[:HAS_ENTITY]-(related:Document)
        WHERE related.file_id <> $file_id
        WITH related, count(e) AS shared
        ORDER BY shared DESC
        LIMIT 10
        RETURN related.file_id AS file_id
        """
        async with self._driver.session() as session:
            result = await session.run(cypher, file_id=file_id)
            records = await result.values()
            return [r[0] for r in records if r]

    async def search_entities_for_query(self, query: str, limit: int = 10) -> list[str]:
        """Find file_ids whose entities match the query terms.

        Uses case-insensitive substring match across entity names.
        """
        if not self._available:
            return []
        terms = [t.strip().lower() for t in query.split() if len(t.strip()) > 2]
        if not terms:
            return []

        # Build a filter for any entity whose name contains any term
        conditions = " OR ".join([f"toLower(e.name) CONTAINS '{t}'" for t in terms[:5]])
        cypher = f"""
        MATCH (e:Entity)<-[:HAS_ENTITY]-(d:Document)
        WHERE {conditions}
        WITH d, count(e) AS relevance
        ORDER BY relevance DESC
        LIMIT {limit}
        RETURN d.file_id AS file_id
        """
        async with self._driver.session() as session:
            try:
                result = await session.run(cypher)
                records = await result.values()
                return [r[0] for r in records if r]
            except Exception as exc:
                logger.warning("Graph entity search failed: %s", exc)
                return []

    async def get_document_entities(self, file_id: str) -> list[dict]:
        """Return all entities associated with a document."""
        if not self._available:
            return []
        cypher = """
        MATCH (d:Document {file_id: $file_id})-[:HAS_ENTITY]->(e:Entity)
        RETURN e.name AS name, e.type AS type
        """
        async with self._driver.session() as session:
            result = await session.run(cypher, file_id=file_id)
            records = await result.values()
            return [{"name": r[0], "type": r[1]} for r in records if r]


# Module-level singleton
graph_store = GraphStore()


async def init_graph_store() -> GraphStore:
    """Initialize and return the global graph store."""
    await graph_store.initialize()
    return graph_store
