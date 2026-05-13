from __future__ import annotations

import json
import logging
import time
from typing import Any

import redis.asyncio as aioredis

from backend.config import settings

logger = logging.getLogger(__name__)

_MAX_ENTRIES_PER_SESSION = 500
_STATS_KEY = "nexus:episodic:_stats"


def _session_key(session_id: str) -> str:
    return f"nexus:episodic:{session_id}"


class EpisodicMemory:
    def __init__(self) -> None:
        self._redis: aioredis.Redis | None = None

    async def get_redis(self) -> aioredis.Redis | None:
        if self._redis is not None:
            return self._redis
        try:
            client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            # Ping to verify connectivity
            await client.ping()
            self._redis = client
            return self._redis
        except Exception as e:
            logger.warning("Episodic memory: Redis unavailable (%s)", e)
            self._redis = None
            return None

    async def store(
        self,
        session_id: str,
        event_type: str,
        content: str,
        metadata: dict | None = None,
    ) -> bool:
        r = await self.get_redis()
        if r is None:
            return False
        try:
            ts = time.time()
            payload = {
                "type": event_type,
                "content": content,
                "metadata": metadata or {},
                "timestamp": ts,
            }
            key = _session_key(session_id)
            value = json.dumps(payload)
            await r.zadd(key, {value: ts})
            # Trim to last N entries (keep highest scores)
            await r.zremrangebyrank(key, 0, -(_MAX_ENTRIES_PER_SESSION + 1))
            # Increment total_stored stat
            await r.hincrby(_STATS_KEY, "total_stored", 1)
            return True
        except Exception as e:
            logger.warning("Episodic store failed: %s", e)
            return False

    async def recall(self, session_id: str, limit: int = 20) -> list[dict]:
        r = await self.get_redis()
        if r is None:
            return []
        try:
            key = _session_key(session_id)
            raw = await r.zrevrange(key, 0, max(limit - 1, 0), withscores=True)
            out: list[dict] = []
            for value, score in raw:
                try:
                    entry = json.loads(value)
                except Exception:
                    entry = {"content": value}
                entry.setdefault("timestamp", float(score))
                out.append(entry)
            return out
        except Exception as e:
            logger.warning("Episodic recall failed: %s", e)
            return []

    async def recall_all(self, limit: int = 50) -> list[dict]:
        """Return the most recent events across ALL sessions, sorted by timestamp desc."""
        r = await self.get_redis()
        if r is None:
            return []
        try:
            all_entries: list[dict] = []
            async for key in r.scan_iter(match="nexus:episodic:*"):
                if key == _STATS_KEY:
                    continue
                session_id = key[len("nexus:episodic:"):]
                raw = await r.zrevrange(key, 0, limit - 1, withscores=True)
                for value, score in raw:
                    try:
                        entry = json.loads(value)
                    except Exception:
                        entry = {"content": str(value)}
                    entry.setdefault("timestamp", float(score))
                    entry["session_id"] = session_id
                    all_entries.append(entry)
            all_entries.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
            return all_entries[:limit]
        except Exception as e:
            logger.warning("Episodic recall_all failed: %s", e)
            return []

    async def get_stats(self) -> dict:
        r = await self.get_redis()
        if r is None:
            return {"total": 0, "available": False}
        try:
            total = 0
            # Sum cardinality across all session keys
            try:
                async for key in r.scan_iter(match="nexus:episodic:*"):
                    if key == _STATS_KEY:
                        continue
                    try:
                        total += await r.zcard(key)
                    except Exception:
                        continue
            except Exception:
                # Fallback to hash stat
                raw = await r.hget(_STATS_KEY, "total_stored")
                total = int(raw) if raw else 0
            return {"total": int(total), "available": True}
        except Exception as e:
            logger.warning("Episodic stats failed: %s", e)
            return {"total": 0, "available": False}

    async def clear_session(self, session_id: str) -> None:
        r = await self.get_redis()
        if r is None:
            return
        try:
            await r.delete(_session_key(session_id))
        except Exception as e:
            logger.warning("Episodic clear_session failed: %s", e)

    async def close(self) -> None:
        if self._redis is not None:
            try:
                await self._redis.close()
            except Exception:
                pass
            self._redis = None
