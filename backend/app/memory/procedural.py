from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, func, update

from backend.core.database import (
    ProceduralMemory as ProceduralMemoryRow,
    get_session,
)

logger = logging.getLogger(__name__)


class ProceduralMemory:
    async def store(
        self,
        pattern_type: str,
        trigger: str,
        action: str,
        session_id: str = "",
        confidence: float = 1.0,
    ) -> str:
        try:
            new_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc)
            async with get_session() as session:
                row = ProceduralMemoryRow(
                    id=new_id,
                    pattern_type=pattern_type,
                    trigger=trigger,
                    action=action,
                    confidence=confidence,
                    use_count=1,
                    created_at=now,
                    updated_at=now,
                    session_id=session_id or None,
                )
                session.add(row)
                await session.flush()
            return new_id
        except Exception as e:
            logger.warning("Procedural store failed: %s", e)
            return ""

    async def get_patterns(
        self,
        pattern_type: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        try:
            async with get_session() as session:
                stmt = select(ProceduralMemoryRow)
                if pattern_type:
                    stmt = stmt.where(ProceduralMemoryRow.pattern_type == pattern_type)
                stmt = stmt.order_by(ProceduralMemoryRow.updated_at.desc()).limit(limit)
                result = await session.execute(stmt)
                rows = result.scalars().all()
                return [
                    {
                        "id": r.id,
                        "pattern_type": r.pattern_type,
                        "trigger": r.trigger,
                        "action": r.action,
                        "confidence": r.confidence,
                        "use_count": r.use_count,
                        "session_id": r.session_id,
                        "created_at": r.created_at,
                        "updated_at": r.updated_at,
                    }
                    for r in rows
                ]
        except Exception as e:
            logger.warning("Procedural get_patterns failed: %s", e)
            return []

    async def increment_use(self, pattern_id: str) -> None:
        try:
            async with get_session() as session:
                row = await session.get(ProceduralMemoryRow, pattern_id)
                if row is None:
                    return
                row.use_count = (row.use_count or 0) + 1
                row.updated_at = datetime.now(timezone.utc)
                await session.flush()
        except Exception as e:
            logger.warning("Procedural increment_use failed: %s", e)

    async def get_stats(self) -> dict:
        try:
            async with get_session() as session:
                total_res = await session.execute(
                    select(func.count(ProceduralMemoryRow.id))
                )
                total = int(total_res.scalar() or 0)

                by_type_res = await session.execute(
                    select(
                        ProceduralMemoryRow.pattern_type,
                        func.count(ProceduralMemoryRow.id),
                    ).group_by(ProceduralMemoryRow.pattern_type)
                )
                by_type_rows = by_type_res.all()

                by_type = {"preference": 0, "behavior": 0, "skill": 0}
                for ptype, count in by_type_rows:
                    by_type[ptype or "unknown"] = int(count)

                return {"total": total, "by_type": by_type}
        except Exception as e:
            logger.warning("Procedural stats failed: %s", e)
            return {"total": 0, "by_type": {"preference": 0, "behavior": 0, "skill": 0}}
