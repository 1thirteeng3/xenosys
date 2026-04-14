"""
XenoSys Messaging Module
Message broker abstraction with Redis and native in-memory support.
"""

from __future__ import annotations

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


# ============================================================================
# Message Types
# ============================================================================

class MessagePriority(str, Enum):
    """Message priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class MessageState(str, Enum):
    """Message delivery state."""
    PENDING = "pending"
    PUBLISHED = "published"
    CONSUMED = "consumed"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass
class Message:
    """A message in the broker."""
    id: UUID = field(default_factory=uuid4)
    topic: str = ""
    payload: str = ""  # JSON serialized
    priority: MessagePriority = MessagePriority.NORMAL
    state: MessageState = MessageState.PENDING
    headers: Dict[str, str] = field(default_factory=dict)
    correlation_id: Optional[str] = None
    reply_to: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    expiration: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MessageEnvelope:
    """Wrapper for message with metadata."""
    message: Message
    consumer_tag: Optional[str] = None
    delivery_tag: Optional[int] = None


# ============================================================================
# Message Broker Interface
# ============================================================================

class MessageBroker(ABC):
    """
    Abstract message broker interface.
    
    Implementations can use Redis, RabbitMQ, Kafka, or in-memory.
    """
    
    @abstractmethod
    async def connect(self) -> bool:
        """Connect to the message broker."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the message broker."""
        pass
    
    @abstractmethod
    async def publish(
        self,
        topic: str,
        payload: Any,
        priority: MessagePriority = MessagePriority.NORMAL,
        headers: Optional[Dict[str, str]] = None,
        correlation_id: Optional[str] = None,
        reply_to: Optional[str] = None,
        expiration: Optional[datetime] = None,
    ) -> Message:
        """Publish a message to a topic."""
        pass
    
    @abstractmethod
    async def subscribe(
        self,
        topic: str,
        handler: Callable[[Message], Awaitable[None]],
        consumer_group: Optional[str] = None,
    ) -> str:
        """Subscribe to a topic and return consumer ID."""
        pass
    
    @abstractmethod
    async def unsubscribe(self, consumer_id: str) -> bool:
        """Unsubscribe from a topic."""
        pass
    
    @abstractmethod
    async def acknowledge(self, message: Message) -> bool:
        """Acknowledge message processing."""
        pass
    
    @abstractmethod
    async def reject(self, message: Message, requeue: bool = False) -> bool:
        """Reject message processing."""
        pass
    
    @abstractmethod
    async def list_topics(self) -> List[str]:
        """List available topics."""
        pass


# ============================================================================
# In-Memory Message Broker (Native)
# ============================================================================

class InMemoryMessageBroker(MessageBroker):
    """
    Native in-memory message broker for development/testing.
    
    Not suitable for production with multiple instances.
    """
    
    def __init__(self):
        self._topics: Dict[str, List[Message]] = {}
        self._subscriptions: Dict[str, tuple[str, Callable[[Message], Awaitable[None]]]] = {}
        self._subscriptions_by_topic: Dict[str, List[str]] = {}
        self._connected = False
        self._lock = asyncio.Lock()
        self._message_id = 0
    
    async def connect(self) -> bool:
        """Connect to in-memory broker."""
        self._connected = True
        logger.info("In-memory message broker connected")
        return True
    
    async def disconnect(self) -> None:
        """Disconnect from in-memory broker."""
        self._connected = False
        self._topics.clear()
        self._subscriptions.clear()
        self._subscriptions_by_topic.clear()
        logger.info("In-memory message broker disconnected")
    
    async def publish(
        self,
        topic: str,
        payload: Any,
        priority: MessagePriority = MessagePriority.NORMAL,
        headers: Optional[Dict[str, str]] = None,
        correlation_id: Optional[str] = None,
        reply_to: Optional[str] = None,
        expiration: Optional[datetime] = None,
    ) -> Message:
        """Publish a message to in-memory topic."""
        if not self._connected:
            raise RuntimeError("Broker not connected")
        
        # Serialize payload
        if isinstance(payload, (dict, list)):
            payload_str = json.dumps(payload)
        else:
            payload_str = str(payload)
        
        message = Message(
            id=uuid4(),
            topic=topic,
            payload=payload_str,
            priority=priority,
            headers=headers or {},
            correlation_id=correlation_id,
            reply_to=reply_to,
            expiration=expiration,
        )
        
        async with self._lock:
            if topic not in self._topics:
                self._topics[topic] = []
            
            # Add based on priority (higher priority first)
            self._topics[topic].append(message)
            self._topics[topic].sort(
                key=lambda m: list(MessagePriority).index(m.priority),
                reverse=True
            )
        
        # Notify subscribers
        await self._dispatch_message(topic, message)
        
        logger.debug(f"Published message {message.id} to topic {topic}")
        return message
    
    async def subscribe(
        self,
        topic: str,
        handler: Callable[[Message], Awaitable[None]],
        consumer_group: Optional[str] = None,
    ) -> str:
        """Subscribe to in-memory topic."""
        if not self._connected:
            raise RuntimeError("Broker not connected")
        
        consumer_id = f"consumer-{uuid4()}"
        
        async with self._lock:
            self._subscriptions[consumer_id] = (topic, handler)
            
            if topic not in self._subscriptions_by_topic:
                self._subscriptions_by_topic[topic] = []
            self._subscriptions_by_topic[topic].append(consumer_id)
        
        logger.info(f"Subscribed {consumer_id} to topic {topic}")
        return consumer_id
    
    async def unsubscribe(self, consumer_id: str) -> bool:
        """Unsubscribe from in-memory topic."""
        async with self._lock:
            if consumer_id in self._subscriptions:
                topic, _ = self._subscriptions.pop(consumer_id)
                
                if topic in self._subscriptions_by_topic:
                    self._subscriptions_by_topic[topic].remove(consumer_id)
                
                logger.info(f"Unsubscribed {consumer_id} from topic {topic}")
                return True
        return False
    
    async def acknowledge(self, message: Message) -> bool:
        """Acknowledge in-memory message."""
        message.state = MessageState.CONSUMED
        logger.debug(f"Acknowledged message {message.id}")
        return True
    
    async def reject(self, message: Message, requeue: bool = False) -> bool:
        """Reject in-memory message."""
        if requeue:
            message.retry_count += 1
            if message.retry_count >= message.max_retries:
                message.state = MessageState.FAILED
                logger.warning(f"Message {message.id} failed after {message.retry_count} retries")
            else:
                # Requeue by adding back to topic
                async with self._lock:
                    if message.topic in self._topics:
                        self._topics[message.topic].append(message)
        else:
            message.state = MessageState.FAILED
        
        return True
    
    async def list_topics(self) -> List[str]:
        """List in-memory topics."""
        async with self._lock:
            return list(self._topics.keys())
    
    async def _dispatch_message(self, topic: str, message: Message) -> None:
        """Dispatch message to all subscribers of the topic."""
        async with self._lock:
            consumer_ids = self._subscriptions_by_topic.get(topic, []).copy()
        
        for consumer_id in consumer_ids:
            if consumer_id in self._subscriptions:
                _, handler = self._subscriptions[consumer_id]
                
                try:
                    await handler(message)
                    message.state = MessageState.CONSUMED
                except Exception as e:
                    logger.error(f"Error in consumer {consumer_id}: {e}")
                    message.state = MessageState.FAILED


# ============================================================================
# Redis Message Broker (Production)
# ============================================================================

class RedisMessageBroker(MessageBroker):
    """
    Redis-based message broker for production.
    
    Uses Redis streams for pub/sub with consumer groups.
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        ssl: bool = False,
    ):
        self._host = host
        self._port = port
        self._db = db
        self._password = password
        self._ssl = ssl
        self._client = None
        self._connected = False
        self._subscriptions: Dict[str, str] = {}  # consumer_id -> topic
        self._handlers: Dict[str, Callable[[Message], Awaitable[None]]] = {}
        self._reader_tasks: Dict[str, asyncio.Task] = {}
    
    async def connect(self) -> bool:
        """Connect to Redis."""
        try:
            import redis.asyncio as redis
            
            self._client = redis.Redis(
                host=self._host,
                port=self._port,
                db=self._db,
                password=self._password,
                ssl=self._ssl,
                decode_responses=False,
            )
            
            await self._client.ping()
            self._connected = True
            logger.info(f"Redis message broker connected to {self._host}:{self._port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        # Cancel reader tasks
        for task in self._reader_tasks.values():
            task.cancel()
        
        self._reader_tasks.clear()
        
        if self._client:
            await self._client.aclose()
            self._client = None
        
        self._connected = False
        self._subscriptions.clear()
        self._handlers.clear()
        
        logger.info("Redis message broker disconnected")
    
    async def publish(
        self,
        topic: str,
        payload: Any,
        priority: MessagePriority = MessagePriority.NORMAL,
        headers: Optional[Dict[str, str]] = None,
        correlation_id: Optional[str] = None,
        reply_to: Optional[str] = None,
        expiration: Optional[datetime] = None,
    ) -> Message:
        """Publish a message to Redis stream."""
        if not self._connected:
            raise RuntimeError("Broker not connected")
        
        # Serialize payload
        if isinstance(payload, (dict, list)):
            payload_str = json.dumps(payload)
        else:
            payload_str = str(payload)
        
        message = Message(
            id=uuid4(),
            topic=topic,
            payload=payload_str,
            priority=priority,
            headers=headers or {},
            correlation_id=correlation_id,
            reply_to=reply_to,
            expiration=expiration,
        )
        
        # Build stream message
        stream_data = {
            "id": str(message.id),
            "payload": message.payload,
            "priority": message.priority.value,
            "correlation_id": message.correlation_id or "",
            "reply_to": message.reply_to or "",
            "timestamp": message.timestamp.isoformat(),
        }
        
        for k, v in message.headers.items():
            stream_data[f"header:{k}"] = v
        
        if message.expiration:
            stream_data["expiration"] = message.expiration.isoformat()
        
        # Add to stream
        stream_key = f"stream:{topic}"
        await self._client.xadd(stream_key, stream_data)
        
        logger.debug(f"Published message {message.id} to Redis stream {topic}")
        return message
    
    async def subscribe(
        self,
        topic: str,
        handler: Callable[[Message], Awaitable[None]],
        consumer_group: Optional[str] = None,
    ) -> str:
        """Subscribe to Redis stream."""
        if not self._connected:
            raise RuntimeError("Broker not connected")
        
        consumer_id = f"consumer-{uuid4()}"
        group_name = consumer_group or f"group-{topic}"
        
        stream_key = f"stream:{topic}"
        
        # Create consumer group if it doesn't exist
        try:
            await self._client.xgroup_create(
                stream_key, group_name, id="0", mkstream=True
            )
        except Exception:
            # Group already exists
            pass
        
        self._subscriptions[consumer_id] = topic
        self._handlers[consumer_id] = handler
        
        # Start reading task
        task = asyncio.create_task(
            self._read_stream(consumer_id, stream_key, group_name)
        )
        self._reader_tasks[consumer_id] = task
        
        logger.info(f"Subscribed {consumer_id} to Redis stream {topic}")
        return consumer_id
    
    async def unsubscribe(self, consumer_id: str) -> bool:
        """Unsubscribe from Redis stream."""
        if consumer_id in self._reader_tasks:
            self._reader_tasks[consumer_id].cancel()
            del self._reader_tasks[consumer_id]
        
        if consumer_id in self._subscriptions:
            del self._subscriptions[consumer_id]
        
        if consumer_id in self._handlers:
            del self._handlers[consumer_id]
        
        logger.info(f"Unsubscribed {consumer_id}")
        return True
    
    async def acknowledge(self, message: Message) -> bool:
        """Acknowledge Redis message."""
        # For consumer groups, need to track delivery info
        logger.debug(f"Acknowledged message {message.id}")
        return True
    
    async def reject(self, message: Message, requeue: bool = False) -> bool:
        """Reject Redis message."""
        logger.debug(f"Rejected message {message.id}, requeue={requeue}")
        return True
    
    async def list_topics(self) -> List[str]:
        """List Redis streams."""
        if not self._connected:
            return []
        
        keys = await self._client.keys("stream:*")
        return [k.replace("stream:", "") for k in keys]
    
    async def _read_stream(
        self,
        consumer_id: str,
        stream_key: str,
        group_name: str,
    ) -> None:
        """Background task to read from stream."""
        while consumer_id in self._subscriptions:
            try:
                # Read from stream
                messages = await self._client.xreadgroup(
                    group_name,
                    consumer_id,
                    {stream_key: ">"},
                    count=10,
                    block=5000,
                )
                
                for stream, msgs in messages or []:
                    for msg_id, msg_data in msgs:
                        message = self._parse_stream_message(msg_id, msg_data)
                        
                        if consumer_id in self._handlers:
                            try:
                                await self._handlers[consumer_id](message)
                                # ACK the message
                                await self._client.xack(stream_key, group_name, msg_id)
                            except Exception as e:
                                logger.error(f"Error handling message: {e}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error reading stream: {e}")
                await asyncio.sleep(1)
    
    def _parse_stream_message(self, msg_id: bytes, msg_data: Dict[bytes, bytes]) -> Message:
        """Parse Redis stream message."""
        def decode(b: bytes) -> str:
            return b.decode("utf-8") if isinstance(b, bytes) else str(b)
        
        headers = {}
        for k, v in msg_data.items():
            key_str = decode(k)
            if key_str.startswith("header:"):
                headers[key_str[7:]] = decode(v)
        
        return Message(
            id=UUID(decode(msg_data.get(b"id", b""))),
            topic=decode(msg_data.get(b"topic", b"")),
            payload=decode(msg_data.get(b"payload", b"")),
            priority=MessagePriority(decode(msg_data.get(b"priority", b"normal"))),
            headers=headers,
            correlation_id=decode(msg_data.get(b"correlation_id", b"")) or None,
            reply_to=decode(msg_data.get(b"reply_to", b"")) or None,
        )


# ============================================================================
# Message Broker Factory
# ============================================================================

def create_message_broker(
    backend: str = "memory",
    **config: Any,
) -> MessageBroker:
    """
    Create a message broker based on backend.
    
    Args:
        backend: "memory" or "redis"
        **config: Configuration for the broker
    
    Returns:
        MessageBroker implementation
    """
    if backend == "redis":
        return RedisMessageBroker(
            host=config.get("host", "localhost"),
            port=config.get("port", 6379),
            db=config.get("db", 0),
            password=config.get("password"),
            ssl=config.get("ssl", False),
        )
    elif backend == "memory":
        return InMemoryMessageBroker()
    else:
        raise ValueError(f"Unknown message broker backend: {backend}")


# ============================================================================
# Global Broker Instance
# ============================================================================

_global_broker: Optional[MessageBroker] = None


def get_message_broker(
    backend: str = "memory",
    **config: Any,
) -> MessageBroker:
    """Get or create global message broker."""
    global _global_broker
    
    if _global_broker is None:
        _global_broker = create_message_broker(backend, **config)
    
    return _global_broker


async def initialize_broker(
    backend: str = "memory",
    **config: Any,
) -> bool:
    """Initialize global message broker."""
    global _global_broker
    
    broker = get_message_broker(backend, **config)
    return await broker.connect()


async def shutdown_broker() -> None:
    """Shutdown global message broker."""
    global _global_broker
    
    if _global_broker:
        await _global_broker.disconnect()
        _global_broker = None