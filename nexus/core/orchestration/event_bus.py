"""
XenoSys Core - Event Bus
AsyncIO event-driven communication system
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Awaitable, Callable, Protocol
from uuid import uuid4

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Core event types for XenoSys."""
    # Session events
    SESSION_CREATED = "session_created"
    SESSION_ENDED = "session_ended"
    SESSION_MESSAGE = "session_message"
    
    # Agent events
    AGENT_STARTED = "agent_started"
    AGENT_COMPLETED = "agent_completed"
    AGENT_ERROR = "agent_error"
    AGENT_TOOL_CALL = "agent_tool_call"
    AGENT_TOOL_RESULT = "agent_tool_result"
    
    # Memory events
    MEMORY_READ = "memory_read"
    MEMORY_WRITE = "memory_write"
    MEMORY_SEARCH = "memory_search"
    MEMORY_SYNC = "memory_sync"
    
    # Learning events
    LEARNING_STAR_STARTED = "learning_star_started"
    LEARNING_STAR_COMPLETED = "learning_star_completed"
    LEARNING_LORA_SWAP = "learning_lora_swap"
    LEARNING_TRAINING_STARTED = "learning_training_started"
    LEARNING_TRAINING_COMPLETED = "learning_training_completed"
    
    # LLMOps events
    LLMOPS_COST_WARNING = "llmops_cost_warning"
    LLMOPS_RATE_LIMIT = "llmops_rate_limit"
    LLMOPS_HITL_PENDING = "llmops_hitl_pending"
    LLMOPS_HITL_APPROVED = "llmops_hitl_approved"
    LLMOPS_HITL_REJECTED = "llmops_hitl_rejected"
    
    # Entity events
    ENTITY_CREATED = "entity_created"
    ENTITY_UPDATED = "entity_updated"
    ENTITY_DELETED = "entity_deleted"
    
    # System events
    SYSTEM_SHUTDOWN = "system_shutdown"
    SYSTEM_ERROR = "system_error"


@dataclass
class Event:
    """XenoSys event object."""
    type: EventType
    timestamp: datetime = field(default_factory=datetime.utcnow)
    event_id: str = field(default_factory=lambda: str(uuid4()))
    
    # Correlation
    session_id: str | None = None
    agent_id: str | None = None
    user_id: str | None = None
    
    # Payload
    data: dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    source: str = "system"
    priority: int = 0
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "type": self.type.value,
            "timestamp": self.timestamp.isoformat(),
            "event_id": self.event_id,
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "user_id": self.user_id,
            "data": self.data,
            "source": self.source,
            "priority": self.priority,
        }


# Type aliases
EventHandler = Callable[[Event], Awaitable[None] | None]
EventFilter = Callable[[Event], bool]


@dataclass
class Subscription:
    """Event subscription."""
    id: str
    event_types: set[EventType] | Literal["*"]
    handler: EventHandler
    filter_fn: EventFilter | None = None
    once: bool = False
    priority: int = 0


Literal = str  # For type hint


class EventBus:
    """
    AsyncIO event bus for XenoSys.
    
    Features:
    - Async event publishing with ordering guarantees
    - Typed subscriptions with event filtering
    - Priority-based handler execution
    - Once subscriptions (auto-unsubscribe after first event)
    - Event tracing/correlation
    """
    
    def __init__(self) -> None:
        self._subscriptions: dict[str, Subscription] = {}
        self._handlers: dict[EventType, list[tuple[int, EventHandler]]] = defaultdict(list)
        self._wildcard_handlers: list[tuple[int, EventHandler]] = []
        self._lock = asyncio.Lock()
        self._event_queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=10000)
        self._processor_task: asyncio.Task[None] | None = None
        self._running = False
        
    async def start(self) -> None:
        """Start the event processor."""
        if self._running:
            return
        self._running = True
        self._processor_task = asyncio.create_task(self._process_events())
        logger.info("EventBus started")
        
    async def stop(self) -> None:
        """Stop the event processor and cleanup."""
        self._running = False
        
        # Cancel processor
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
        
        # Publish shutdown event
        await self.publish(Event(type=EventType.SYSTEM_SHUTDOWN))
        
        logger.info("EventBus stopped")
    
    async def _process_events(self) -> None:
        """Process events from queue."""
        while self._running:
            try:
                event = await asyncio.wait_for(
                    self._event_queue.get(),
                    timeout=1.0
                )
                await self._dispatch_event(event)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing event: {e}", exc_info=True)
    
    async def publish(self, event: Event) -> None:
        """
        Publish an event to the bus.
        
        Events are queued and processed asynchronously to avoid blocking.
        """
        # Validate event type
        if not isinstance(event.type, EventType):
            raise ValueError(f"Invalid event type: {event.type}")
        
        if self._running:
            await self._event_queue.put(event)
        else:
            # Process immediately if bus is stopped
            await self._dispatch_event(event)
    
    async def _dispatch_event(self, event: Event) -> None:
        """Dispatch event to matching handlers."""
        # Get handlers for this event type
        handlers = list(self._handlers.get(event.type, []))
        
        # Add wildcard handlers
        handlers.extend(self._wildcard_handlers)
        
        # Sort by priority (higher first)
        handlers.sort(key=lambda x: -x[0])
        
        # Execute handlers
        for _, handler in handlers:
            try:
                # Check filter
                subs = self._find_subscription(handler)
                if subs and subs.filter_fn and not subs.filter_fn(event):
                    continue
                
                # Execute handler
                result = handler(event)
                if asyncio.iscoroutine(result):
                    await result
                    
            except Exception as e:
                logger.error(
                    f"Error in event handler for {event.type.value}: {e}",
                    exc_info=True
                )
        
        # Remove 'once' subscriptions
        await self._cleanup_once_subscriptions(event)
    
    def _find_subscription(self, handler: EventHandler) -> Subscription | None:
        """Find subscription by handler."""
        for sub in self._subscriptions.values():
            if sub.handler == handler:
                return sub
        return None
    
    async def _cleanup_once_subscriptions(self, event: Event) -> None:
        """Remove once subscriptions that matched."""
        async with self._lock:
            to_remove: list[str] = []
            
            for sub_id, sub in self._subscriptions.items():
                if not sub.once:
                    continue
                    
                # Check if matched
                matches = (
                    sub.event_types == "*" or 
                    event.type in sub.event_types
                )
                
                if matches and (not sub.filter_fn or sub.filter_fn(event)):
                    to_remove.append(sub_id)
            
            for sub_id in to_remove:
                self._unsubscribe_internal(sub_id)
    
    def subscribe(
        self,
        event_types: EventType | list[EventType] | str,
        handler: EventHandler,
        *,
        filter_fn: EventFilter | None = None,
        once: bool = False,
        priority: int = 0,
    ) -> str:
        """
        Subscribe to events.
        
        Args:
            event_types: EventType(s) to subscribe to, or "*" for all
            handler: Async function to call when event occurs
            filter_fn: Optional filter function
            once: If True, unsubscribe after first matching event
            priority: Handler priority (higher = runs first)
            
        Returns:
            Subscription ID for unsubscribing
        """
        if isinstance(event_types, str) and event_types != "*":
            raise ValueError("event_types must be EventType, list of EventTypes, or '*'")
        
        if event_types == "*":
            types: set[EventType] | str = "*"
        elif isinstance(event_types, list):
            types = set(event_types)
        else:
            types = {event_types}
        
        sub_id = str(uuid4())
        subscription = Subscription(
            id=sub_id,
            event_types=types,
            handler=handler,
            filter_fn=filter_fn,
            once=once,
            priority=priority,
        )
        
        self._subscriptions[sub_id] = subscription
        
        # Add to handler lists
        if types == "*":
            self._wildcard_handlers.append((priority, handler))
            self._wildcard_handlers.sort(key=lambda x: -x[0])
        else:
            for et in types:
                self._handlers[et].append((priority, handler))
                self._handlers[et].sort(key=lambda x: -x[0])
        
        logger.debug(f"Subscribed to {event_types}, handler: {handler}")
        return sub_id
    
    def subscribe_once(
        self,
        event_types: EventType | list[EventType],
        handler: EventHandler,
        filter_fn: EventFilter | None = None,
    ) -> str:
        """Subscribe for one event only."""
        return self.subscribe(event_types, handler, filter_fn=filter_fn, once=True)
    
    def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe by ID."""
        return self._unsubscribe_internal(subscription_id)
    
    def _unsubscribe_internal(self, subscription_id: str) -> bool:
        """Internal unsubscribe (must hold lock)."""
        sub = self._subscriptions.pop(subscription_id, None)
        if not sub:
            return False
        
        # Remove from handlers
        if sub.event_types == "*":
            self._wildcard_handlers = [
                (p, h) for p, h in self._wildcard_handlers
                if h != sub.handler
            ]
        else:
            for et in sub.event_types:
                self._handlers[et] = [
                    (p, h) for p, h in self._handlers.get(et, [])
                    if h != sub.handler
                ]
        
        logger.debug(f"Unsubscribed: {subscription_id}")
        return True
    
    def unsubscribe_all(self, event_types: EventType | list[EventType] | None = None) -> int:
        """
        Unsubscribe all handlers for event types.
        
        Args:
            event_types: Specific types to clear, or None for all
            
        Returns:
            Number of subscriptions removed
        """
        if event_types is None:
            count = len(self._subscriptions)
            self._subscriptions.clear()
            self._handlers.clear()
            self._wildcard_handlers.clear()
            return count
        
        if isinstance(event_types, EventType):
            event_types = [event_types]
        
        types_set = set(event_types)
        count = 0
        
        for sub_id in list(self._subscriptions.keys()):
            sub = self._subscriptions[sub_id]
            if sub.event_types == "*" or types_set & sub.event_types:
                self._unsubscribe_internal(sub_id)
                count += 1
        
        return count
    
    def get_stats(self) -> dict[str, Any]:
        """Get event bus statistics."""
        return {
            "subscription_count": len(self._subscriptions),
            "event_types_subscribed": {
                et.value: len(handlers)
                for et, handlers in self._handlers.items()
            },
            "wildcard_handlers": len(self._wildcard_handlers),
            "queue_size": self._event_queue.qsize(),
            "running": self._running,
        }


# Global instance
event_bus = EventBus()


# Convenience decorators
def on(*event_types: EventType):
    """Decorator to subscribe a handler to event types."""
    def decorator(func: EventHandler) -> EventHandler:
        event_bus.subscribe(list(event_types), func)
        return func
    return decorator


def once(*event_types: EventType):
    """Decorator to subscribe a one-time handler."""
    def decorator(func: EventHandler) -> EventHandler:
        event_bus.subscribe_once(list(event_types), func)
        return func
    return decorator