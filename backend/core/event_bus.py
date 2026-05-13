"""In-process event emitter for tracking agent communications throughout Nexus OS."""

import asyncio
import json
import logging
from datetime import datetime
from typing import Callable, Dict, List, Any

logger = logging.getLogger(__name__)


class EventBus:
    """In-memory event emitter with pub/sub pattern for agent communications."""

    def __init__(self):
        # Mapping: channel -> list of subscriber callbacks
        self._subscribers: Dict[str, List[Callable]] = {}
        # Message queue for async processing
        self._queue: asyncio.Queue = asyncio.Queue()
        # Background task for processing
        self._worker_task: asyncio.Task | None = None
        # Track all agent messages for network visualization
        self._agent_messages: List[Dict[str, Any]] = []
        # Maximum messages to keep in memory (last 10k)
        self._max_messages = 10000

    async def start(self):
        """Start the async event processor."""
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._process_queue())
            logger.info("EventBus worker started")

    async def stop(self):
        """Stop the async event processor."""
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            logger.info("EventBus worker stopped")

    async def _process_queue(self):
        """Process events from the queue and notify subscribers."""
        while True:
            try:
                channel, event_data = await self._queue.get()

                # Store agent_messages for later replay/query
                if channel == "agent_messages":
                    self._agent_messages.append(event_data)
                    # Trim old messages to prevent memory bloat
                    if len(self._agent_messages) > self._max_messages:
                        self._agent_messages = self._agent_messages[
                            -self._max_messages :
                        ]

                # Notify all subscribers for this channel
                subscribers = self._subscribers.get(channel, [])
                if subscribers:
                    # Send to all subscribers concurrently
                    tasks = [self._safe_call(cb, event_data) for cb in subscribers]
                    await asyncio.gather(*tasks, return_exceptions=True)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("EventBus queue processing error: %s", e)

    async def _safe_call(self, callback: Callable, data: Dict[str, Any]):
        """Safely invoke a subscriber callback."""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(data)
            else:
                callback(data)
        except Exception as e:
            logger.error("EventBus subscriber error: %s", e)

    def subscribe(self, channel: str, callback: Callable):
        """Subscribe to a channel. Callback will receive event data dict."""
        if channel not in self._subscribers:
            self._subscribers[channel] = []
        self._subscribers[channel].append(callback)
        logger.debug("Added subscriber for channel: %s", channel)

    def unsubscribe(self, channel: str, callback: Callable):
        """Unsubscribe from a channel."""
        if channel in self._subscribers:
            self._subscribers[channel] = [
                cb for cb in self._subscribers[channel] if cb != callback
            ]
            logger.debug("Removed subscriber from channel: %s", channel)

    def publish(self, channel: str, data: Dict[str, Any]):
        """Publish an event to a channel (non-blocking)."""
        # Add timestamp if not present
        if "timestamp" not in data:
            data["timestamp"] = datetime.utcnow().isoformat()

        # Queue for async processing to avoid blocking
        try:
            self._queue.put_nowait((channel, data))
        except asyncio.QueueFull:
            logger.warning("EventBus queue full, dropping event: %s", channel)

    def get_agent_messages(
        self, limit: int = 1000, since: str | None = None
    ) -> List[Dict[str, Any]]:
        """Retrieve agent message history for visualization or replay."""
        messages = self._agent_messages

        # Filter by timestamp if provided
        if since:
            messages = [m for m in messages if m.get("timestamp", "") > since]

        # Return most recent
        return messages[-limit:]

    def clear_messages(self):
        """Clear all stored agent messages (useful for testing)."""
        self._agent_messages.clear()
        logger.info("Cleared event bus message history")


# Global event bus instance
event_bus = EventBus()


def publish_agent_message(
    from_agent: str, to_agent: str, message_type: str, payload: Dict[str, Any] = None
):
    """
    Publish an agent communication event.

    Args:
        from_agent: Name/ID of the sending agent
        to_agent: Name/ID of the receiving agent
        message_type: Type of communication (delegate, request, response, etc.)
        payload: Optional additional data
    """
    event_bus.publish(
        "agent_messages",
        {
            "from": from_agent,
            "to": to_agent,
            "message_type": message_type,
            "payload": payload or {},
        },
    )


# Async context manager for lifecycle management
class EventBusContext:
    def __init__(self):
        self.bus = event_bus

    async def __aenter__(self):
        await self.bus.start()
        return self.bus

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.bus.stop()


# Helper decorator to automatically publish agent interactions
def track_agent_communication(from_agent_identifier: str):
    """
    Decorator to automatically track agent-to-agent communications.

    Usage:
        @track_agent_communication("supervisor")
        async def delegate_to_research_lead(...):
            # This will auto-publish an agent_message event
            pass
    """

    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Execute the function
            result = await func(*args, **kwargs)

            # Publish communication event
            # Try to infer target agent from function name or args
            to_agent = getattr(func, "_to_agent", "unknown")
            message_type = getattr(func, "_message_type", func.__name__)

            publish_agent_message(
                from_agent=from_agent_identifier,
                to_agent=to_agent,
                message_type=message_type,
                payload={"args": str(args), "kwargs": list(kwargs.keys())},
            )

            return result

        return wrapper

    return decorator
