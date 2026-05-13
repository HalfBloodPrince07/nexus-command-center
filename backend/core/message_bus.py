import asyncio
import hmac
import hashlib
import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import uuid

import redis.asyncio as redis
from redis.asyncio.client import PubSub
from redis.exceptions import ConnectionError as RedisConnectionError

from backend.config import settings

# Configure logging
logger = logging.getLogger(__name__)

class MessageBusError(Exception):
    """Custom exception for Message Bus errors."""
    pass

@dataclass
class A2AMessage:
    id: str
    sender_id: str
    recipient_id: str
    message_type: str
    payload: Dict[str, Any]
    timestamp: datetime
    signature: Optional[str] = None
    priority: int = 5  # 1=low, 5=normal, 10=high

    def to_json(self) -> str:
        """Serialize the message to a JSON string."""
        # Use a custom default to handle datetime objects
        def default_serializer(o):
            if isinstance(o, datetime):
                return o.isoformat()
            raise TypeError(f"Object of type {o.__class__.__name__} is not JSON serializable")
        return json.dumps(asdict(self), default=default_serializer)

    @staticmethod
    def from_json(json_str: str) -> "A2AMessage":
        """Deserialize a JSON string to an A2AMessage object."""
        data = json.loads(json_str)
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return A2AMessage(**data)

    def get_signing_content(self) -> str:
        """Get the content string for HMAC signature."""
        return f"{self.id}{self.sender_id}{self.recipient_id}{self.message_type}{self.timestamp.isoformat()}"

def sign_message(message: A2AMessage) -> str:
    """Sign a message using HMAC-SHA256."""
    secret = settings.A2A_SECRET_KEY or "nexus-dev-secret"
    content = message.get_signing_content().encode('utf-8')
    signature = hmac.new(secret.encode('utf-8'), content, hashlib.sha256).hexdigest()
    return signature

def verify_message(message: A2AMessage) -> bool:
    """Verify the signature of a message."""
    if not message.signature:
        return False
    expected_signature = sign_message(message)
    return hmac.compare_digest(expected_signature, message.signature)


class MessageBus:
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self._redis: Optional[redis.Redis] = None
        self._pubsub: Optional[PubSub] = None
        self._listener_task: Optional[asyncio.Task] = None
        self._subscribers: Dict[str, asyncio.Queue] = {}
        self.degraded = False

    async def connect(self) -> None:
        """Connect to Redis and set up the message bus."""
        try:
            self._redis = redis.Redis.from_url(self.redis_url, decode_responses=True)
            await self._redis.ping()
            self._pubsub = self._redis.pubsub(ignore_subscribe_messages=True)
            await self._pubsub.subscribe("nexus:system")
            self._listener_task = asyncio.create_task(self._listen())
            logger.info("A2A Message Bus connected to Redis at %s", self.redis_url)
            self.degraded = False
        except RedisConnectionError as e:
            logger.warning("Redis unavailable at %s — A2A bus running in degraded mode. Error: %s", self.redis_url, e)
            self.degraded = True
            self._redis = None

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self._listener_task and not self._listener_task.done():
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
        if self._pubsub:
            await self._pubsub.close()
        if self._redis:
            await self._redis.close()
        logger.info("A2A Message Bus disconnected.")

    async def _listen(self):
        """Listen for messages on subscribed channels."""
        if not self._pubsub:
            return
        
        while True:
            try:
                message = await self._pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message is None:
                    await asyncio.sleep(0.01)
                    continue

                logger.debug("Received message on channel %s", message['channel'])
                a2a_message = A2AMessage.from_json(message['data'])

                if not verify_message(a2a_message):
                    logger.warning("Invalid signature for message %s. Discarding.", a2a_message.id)
                    continue

                # Route to appropriate subscribers
                if message['channel'] == "nexus:broadcast":
                    for queue in self._subscribers.values():
                        await queue.put(a2a_message)
                else: # Direct message
                    agent_id = message['channel'].split("nexus:agent:")[1]
                    if agent_id in self._subscribers:
                        await self._subscribers[agent_id].put(a2a_message)

            except RedisConnectionError as e:
                logger.error("Redis connection lost in listener: %s. Attempting to reconnect...", e)
                await asyncio.sleep(5)
            except Exception as e:
                logger.exception("Error in message bus listener: %s", e)
                await asyncio.sleep(1)


    async def publish(self, message: A2AMessage) -> None:
        """Publish a message to the appropriate channel."""
        if self.degraded or not self._redis:
            logger.warning("Message bus in degraded mode. Cannot publish message.")
            return

        message.signature = sign_message(message)
        
        channel = f"nexus:agent:{message.recipient_id}" if message.recipient_id != "broadcast" else "nexus:broadcast"
        
        try:
            await self._redis.publish(channel, message.to_json())
            logger.debug("Published message %s to %s", message.id, channel)
        except Exception as e:
            raise MessageBusError(f"Failed to publish message: {e}") from e

    async def subscribe(self, agent_id: str) -> asyncio.Queue:
        """Subscribe an agent to its channel and broadcast, returning a message queue."""
        if self.degraded or not self._pubsub:
            logger.warning("Message bus in degraded mode. Subscription for %s is offline.", agent_id)
            return asyncio.Queue()

        if agent_id not in self._subscribers:
            queue = asyncio.Queue()
            self._subscribers[agent_id] = queue
            await self._pubsub.subscribe(f"nexus:agent:{agent_id}")
            await self._pubsub.subscribe("nexus:broadcast")
            logger.info("Agent '%s' subscribed to message bus.", agent_id)
            return queue
        return self._subscribers[agent_id]

    async def send_heartbeat(self, agent_id: str) -> None:
        """Send a heartbeat message from an agent."""
        heartbeat_message = A2AMessage(
            id=str(uuid.uuid4()),
            sender_id=agent_id,
            recipient_id="broadcast",
            message_type="heartbeat",
            payload={"status": "alive"},
            timestamp=datetime.now(timezone.utc)
        )
        await self.publish(heartbeat_message)

    async def get_bus_stats(self) -> dict:
        """Get current stats of the message bus."""
        return {
            "connected": not self.degraded,
            "subscribers": list(self._subscribers.keys()),
            "redis_url": self.redis_url,
        }

# Module-level singleton
message_bus = MessageBus(redis_url=settings.REDIS_URL)
