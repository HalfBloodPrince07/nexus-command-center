"""WebSocket endpoint for real-time agent network visualization."""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from backend.core.event_bus import event_bus, get_agent_messages

logger = logging.getLogger(__name__)

router = APIRouter()


# Active connections for agent network visualization
class AgentNetworkConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.subscriber_map: Dict[str, str] = {}  # subscription_id -> websocket_id

    async def connect(self, websocket: WebSocket, client_id: str):
        """Connect a WebSocket client for agent network updates."""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(
            "Agent network WebSocket connected for client: %s. Total: %d",
            client_id,
            len(self.active_connections),
        )

        # Send initial connection confirmation
        await self.send_json(
            client_id,
            {
                "type": "connected",
                "client_id": client_id,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

        # Send recent agent message history
        recent_messages = get_agent_messages(limit=100)
        await self.send_json(
            client_id, {"type": "history", "messages": recent_messages}
        )

        # Subscribe to new agent messages
        subscription_id = f"agent_network_{client_id}"
        self.subscriber_map[subscription_id] = client_id
        event_bus.subscribe("agent_messages", self._make_callback(subscription_id))

    def _make_callback(self, subscription_id: str):
        """Factory for creating callbacks bound to a specific subscription."""

        async def callback(event_data: Dict[str, Any]):
            client_id = self.subscriber_map.get(subscription_id)
            if client_id:
                await self.send_json(
                    client_id, {"type": "agent_message", "data": event_data}
                )

        return callback

    def disconnect(self, client_id: str):
        """Disconnect a WebSocket client."""
        if client_id in self.active_connections:
            del self.active_connections[client_id]

            # Unsubscribe from agent messages
            subscription_id = f"agent_network_{client_id}"
            if subscription_id in self.subscriber_map:
                # We can't easily remove the callback from event_bus, but we can remove the mapping
                # The callback will be called but will find no client_id
                del self.subscriber_map[subscription_id]

            logger.info(
                "Agent network WebSocket disconnected for client: %s. Total: %d",
                client_id,
                len(self.active_connections),
            )

    async def send_json(self, client_id: str, data: Dict[str, Any]):
        """Send JSON data to a specific client."""
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]
            try:
                await websocket.send_json(data)
            except WebSocketDisconnect:
                self.disconnect(client_id)
            except Exception as e:
                logger.error("Failed to send JSON to client %s: %s", client_id, e)
                self.disconnect(client_id)

    async def broadcast(self, message_type: str, data: Dict[str, Any]):
        """Broadcast a message to all connected clients."""
        if not self.active_connections:
            return

        payload = {
            "type": message_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        }

        tasks = [self.send_json(cid, payload) for cid in self.active_connections.keys()]
        await asyncio.gather(*tasks, return_exceptions=True)


manager = AgentNetworkConnectionManager()


@router.websocket("/ws/agent-network")
async def websocket_endpoint(websocket: WebSocket, client_id: str = Query(None)):
    """WebSocket endpoint for real-time agent network visualization."""
    # Generate client_id if not provided
    if not client_id:
        client_id = f"anonymous_{id(websocket)}"

    try:
        # Ensure event bus is running
        await event_bus.start()
    except Exception as e:
        logger.error("Failed to start event bus: %s", e)
        await websocket.close(code=1011, reason="Server error")
        return

    try:
        # Connect and start listening
        await manager.connect(websocket, client_id)

        # Keep connection alive and handle client messages
        while True:
            data = await websocket.receive_json()
            message_type = data.get("type")

            if message_type == "ping":
                # Respond to ping to keep connection alive
                await manager.send_json(client_id, {"type": "pong"})

            elif message_type == "get_history":
                # Client requests recent message history
                limit = min(data.get("limit", 100), 1000)  # Cap at 1000
                since = data.get("since")
                messages = get_agent_messages(limit=limit, since=since)
                await manager.send_json(
                    client_id, {"type": "history", "messages": messages}
                )

            elif message_type == "clear_history":
                # Clear stored history (admin/reset functionality)
                event_bus.clear_messages()
                await manager.send_json(
                    client_id,
                    {
                        "type": "history_cleared",
                        "message": "Agent message history cleared",
                    },
                )

    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        logger.exception("Error in agent network WebSocket: %s", e)
        manager.disconnect(client_id)
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
