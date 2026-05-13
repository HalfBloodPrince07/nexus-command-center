from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Dict

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from backend.app.agents.supervisor import supervisor
from backend.app.agents.knowledge_lead import knowledge_lead
from backend.core import database as db_module
from backend.core.system_metrics import get_system_metrics

logger = logging.getLogger(__name__)

METRICS_PUSH_INTERVAL = 3


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    @property
    def active_connections_count(self) -> int:
        return len(self.active_connections)

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket

    def disconnect(self, session_id: str):
        self.active_connections.pop(session_id, None)

    async def send_json(self, session_id: str, data: dict):
        websocket = self.active_connections.get(session_id)
        if websocket is None:
            return
        try:
            await websocket.send_json(data)
        except WebSocketDisconnect:
            self.disconnect(session_id)
        except Exception as exc:
            logger.error("Failed to send websocket message for %s: %s", session_id, exc)
            self.disconnect(session_id)


manager = ConnectionManager()
router = APIRouter()


async def metrics_push_loop(session_id: str):
    while True:
        await asyncio.sleep(METRICS_PUSH_INTERVAL)
        if session_id not in manager.active_connections:
            break
        try:
            metrics = get_system_metrics()
            await manager.send_json(session_id, {"type": "system_metrics", **metrics})
        except Exception:
            break


@router.websocket("/ws/chat")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str | None = Query(None),
    conversation_id: str | None = Query(None),
):
    session_id = session_id or conversation_id or str(uuid.uuid4())
    await manager.connect(websocket, session_id)
    metrics_task: asyncio.Task | None = None

    try:
        await manager.send_json(session_id, {"type": "connected", "session_id": session_id, "conversation_id": session_id})
        metrics_task = asyncio.create_task(metrics_push_loop(session_id))

        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "ping":
                await manager.send_json(session_id, {"type": "pong", "session_id": session_id})
                continue

            if msg_type == "clear_history":
                if db_module.database is None:
                    await manager.send_json(session_id, {"type": "error", "message": "Database not initialized"})
                else:
                    await db_module.clear_conversation(session_id)
                    await manager.send_json(session_id, {"type": "history_cleared", "session_id": session_id})
                continue

            if msg_type == "research_start":
                from backend.app.agents.research_lead import research_lead as _rl
                topic = data.get("topic", "").strip()
                job_id = data.get("job_id", "")
                if not topic or not job_id:
                    await manager.send_json(session_id, {"type": "error", "detail": "Missing topic or job_id"})
                    continue
                try:
                    async for event in _rl.run_research(topic, job_id, session_id):
                        await manager.send_json(session_id, {**event, "session_id": session_id})
                except Exception as _exc:
                    logger.exception("Research pipeline error for job %s: %s", job_id, _exc)
                    await manager.send_json(session_id, {"type": "error", "detail": str(_exc), "session_id": session_id})
                continue

            if msg_type == "image_query":
                image_b64 = data.get("image_b64")
                content = data.get("content", "Describe this image.")
                model = data.get("model")

                if db_module.database is not None:
                    await db_module.save_message(session_id, "user", content)

                image_tokens: list[str] = []
                async for event in knowledge_lead.route(
                    session_id,
                    content,
                    model=model,
                    image_b64=image_b64,
                    collection="files",
                ):
                    await manager.send_json(session_id, {**event, "session_id": session_id})
                    if event.get("type") == "token":
                        image_tokens.append(event.get("content", ""))

                if db_module.database is not None and image_tokens:
                    asyncio.create_task(
                        db_module.save_message(session_id, "assistant", "".join(image_tokens), agent_id="iris")
                    )
                continue

            if msg_type == "message":
                content = data.get("content")
                if not content:
                    continue
                model = data.get("model")
                start_time = time.monotonic()

                # Main chat is always handled by the Supervisor directly.
                # Specialised routing (Aria/Echo/Iris) is reserved for future
                # per-tab chat endpoints (Research tab, Files tab, etc.).
                if db_module.database is not None:
                    await db_module.save_message(session_id, "user", content)
                await manager.send_json(session_id, {"type": "thinking", "agent": "Nexus", "session_id": session_id})
                full_response_parts: list[str] = []
                async for item in supervisor.stream_response(content, session_id, model=model):
                    if isinstance(item, dict):
                        await manager.send_json(session_id, {**item, "session_id": session_id})
                        continue
                    full_response_parts.append(str(item))
                    await manager.send_json(
                        session_id,
                        {"type": "token", "content": item, "session_id": session_id, "agent": "Nexus"},
                    )
                await manager.send_json(session_id, {"type": "done", "session_id": session_id, "agent": "Nexus"})

                elapsed_ms = int((time.monotonic() - start_time) * 1000)
                asyncio.create_task(db_module.record_message(session_id, response_ms=elapsed_ms))

                try:
                    from backend.app.memory.manager import memory_manager as _mm
                    full_response = "".join(full_response_parts)
                    asyncio.create_task(
                        _mm.remember_interaction(session_id, content, full_response)
                    )
                except Exception as exc:
                    logger.warning("memory remember_interaction failed: %s", exc)

    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception as exc:
        logger.exception("WebSocket error for %s: %s", session_id, exc)
        try:
            await websocket.send_json({"type": "error", "message": str(exc)})
        except Exception:
            pass
        manager.disconnect(session_id)
    finally:
        if metrics_task and not metrics_task.done():
            metrics_task.cancel()
