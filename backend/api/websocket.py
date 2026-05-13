import asyncio
import logging
import uuid
from typing import Dict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from backend.core.system_metrics import get_system_metrics

# Configure logging
logger = logging.getLogger(__name__)

# --- Supervisor Import with Mock Fallback ---
async def mock_supervisor_stream(content: str, conversation_id: str):
    """A mock streaming function for when the real supervisor isn't available."""
    response = "Supervisor agent not yet initialized — this is a placeholder response."
    for word in response.split():
        yield word + " "
        await asyncio.sleep(0.05)

try:
    from backend.agents.supervisor import stream_response as supervisor_stream_response
except ImportError:
    logger.warning("Supervisor agent not found. Falling back to mock implementation.")
    supervisor_stream_response = mock_supervisor_stream

# --- Database Import with Mock Fallback ---
try:
    from backend.core import database
except ImportError:
    database = None
    logger.warning("Database module not found. 'clear_history' will not work.")


METRICS_PUSH_INTERVAL = 3  # seconds


class ConnectionManager:
    """Manages active WebSocket connections."""
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    @property
    def active_connections_count(self) -> int:
        return len(self.active_connections)

    async def connect(self, websocket: WebSocket, conversation_id: str):
        await websocket.accept()
        self.active_connections[conversation_id] = websocket
        logger.info("WebSocket connected for conversation_id: %s. Total connections: %d", conversation_id, self.active_connections_count)

    def disconnect(self, conversation_id: str):
        if conversation_id in self.active_connections:
            del self.active_connections[conversation_id]
            logger.info("WebSocket disconnected for conversation_id: %s. Total connections: %d", conversation_id, self.active_connections_count)

    async def send_json(self, conversation_id: str, data: dict):
        if conversation_id in self.active_connections:
            websocket = self.active_connections[conversation_id]
            try:
                await websocket.send_json(data)
            except WebSocketDisconnect:
                self.disconnect(conversation_id)
            except Exception as e:
                logger.error("Failed to send JSON to %s: %s", conversation_id, e)
                self.disconnect(conversation_id)

    async def broadcast(self, data: dict):
        if not self.active_connections:
            return
        tasks = [self.send_json(cid, data) for cid in self.active_connections.keys()]
        await asyncio.gather(*tasks)

manager = ConnectionManager()
router = APIRouter()


async def metrics_push_loop(conversation_id: str):
    """Background task: push system metrics to the client every N seconds."""
    while True:
        await asyncio.sleep(METRICS_PUSH_INTERVAL)
        if conversation_id not in manager.active_connections:
            break
        try:
            metrics = get_system_metrics()
            await manager.send_json(conversation_id, {"type": "system_metrics", **metrics})
        except Exception as e:
            logger.debug("Metrics push failed for %s: %s", conversation_id, e)
            break


@router.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket, conversation_id: str = Query(None)):
    """The main chat WebSocket endpoint."""
    if not conversation_id:
        conversation_id = str(uuid.uuid4())

    await manager.connect(websocket, conversation_id)
    metrics_task: asyncio.Task | None = None

    try:
        # Send connection confirmation
        await manager.send_json(conversation_id, {"type": "connected", "conversation_id": conversation_id})

        # Start background metrics push
        metrics_task = asyncio.create_task(metrics_push_loop(conversation_id))

        while True:
            data = await websocket.receive_json()
            message_type = data.get("type")

            if message_type == "ping":
                await manager.send_json(conversation_id, {"type": "pong"})

            elif message_type == "message":
                content = data.get("content")
                if not content:
                    continue

                # Acknowledge receipt and start thinking
                await manager.send_json(conversation_id, {"type": "thinking", "agent_id": "supervisor"})

                # Stream the response
                try:
                    async for token in supervisor_stream_response(content, conversation_id):
                        if isinstance(token, dict):
                            # Explicitly forward known structured events
                            # (degraded / progress / thinking / result / etc.)
                            event_type = token.get("type")
                            if event_type == "degraded":
                                logger.info(
                                    "Forwarding degraded event to client %s: agent=%s reason=%s",
                                    conversation_id,
                                    token.get("agent"),
                                    token.get("reason"),
                                )
                            await manager.send_json(conversation_id, token)
                            continue
                        await manager.send_json(conversation_id, {
                            "type": "stream_token",
                            "content": token,
                            "agent_id": "supervisor"
                        })
                finally:
                    # Signal end of stream
                    await manager.send_json(conversation_id, {
                        "type": "stream_end",
                        "agent_id": "supervisor",
                        "conversation_id": conversation_id
                    })

            elif message_type == "clear_history":
                if database:
                    await database.clear_conversation(conversation_id)
                    await manager.send_json(conversation_id, {"type": "history_cleared"})
                else:
                    await manager.send_json(conversation_id, {"type": "error", "message": "Database not configured."})

    except WebSocketDisconnect:
        manager.disconnect(conversation_id)
    except Exception as e:
        logger.exception("An error occurred in the WebSocket for conversation %s: %s", conversation_id, e)
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
        finally:
            manager.disconnect(conversation_id)
    finally:
        if metrics_task and not metrics_task.done():
            metrics_task.cancel()
