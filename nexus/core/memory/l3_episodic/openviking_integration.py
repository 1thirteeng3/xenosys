"""
XenoSys Memory System - L3 Episodic Memory
Built on OpenViking for session logging, interaction records, and raw files via REST API.

OpenViking: https://github.com/volcengine/OpenViking
Records each interaction, log, and raw file with date and time.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

import httpx

from ...resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    get_breaker_registry,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Episodic Memory Types
# ============================================================================

@dataclass
class SessionRecord:
    """A session record in episodic memory."""
    id: UUID = field(default_factory=uuid4)
    session_id: str = ""
    agent_id: Optional[str] = None
    entity_id: Optional[str] = None
    user_id: str = ""
    status: str = "active"  # active, completed, failed
    started_at: datetime = field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None
    message_count: int = 0
    token_count: int = 0
    cost_usd: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InteractionRecord:
    """A single interaction/message record."""
    id: UUID = field(default_factory=uuid4)
    session_id: str = ""
    message_id: str = ""
    role: str = "user"  # user, assistant, system, tool
    content: str = ""
    model: Optional[str] = None
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LogRecord:
    """A log record for debugging/audit."""
    id: UUID = field(default_factory=uuid4)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    level: str = "info"  # debug, info, warning, error
    source: str = ""  # component name
    session_id: Optional[str] = None
    agent_id: Optional[str] = None
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RawFileRecord:
    """A raw file record (attachments, outputs, etc.)."""
    id: UUID = field(default_factory=uuid4)
    session_id: Optional[str] = None
    filename: str = ""
    content_type: str = ""
    size_bytes: int = 0
    storage_path: str = ""  # Path to stored file
    checksum: str = ""  # SHA256
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# OpenViking HTTP Client
# ============================================================================

class OpenVikingClient:
    """
    Client for OpenViking episodic memory operations via HTTP.
    
    OpenViking provides:
    - Session logging with full history
    - Interaction recording with timestamps
    - Debug log aggregation
    - Raw file storage with checksums
    - Timeline queries and replay
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.endpoint = self.config.get("endpoint", "http://localhost:8080")
        self.api_key = self.config.get("api_key", "")
        self.timeout = httpx.Timeout(self.config.get("timeout", 30.0))
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
            self._client = httpx.AsyncClient(
                base_url=self.endpoint,
                timeout=self.timeout,
                headers=headers,
            )
        return self._client
    
    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def connect(self) -> bool:
        """Connect to OpenViking (verify health)."""
        try:
            client = await self._get_client()
            response = await client.get("/health")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to connect to OpenViking: {e}")
            return False
    
    # =========================================================================
    # Session Operations
    # =========================================================================
    
    async def create_session(
        self,
        session_id: str,
        agent_id: Optional[str] = None,
        entity_id: Optional[str] = None,
        user_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SessionRecord:
        """Create a new session record via HTTP."""
        try:
            client = await self._get_client()
            response = await client.post(
                "/api/v1/sessions",
                json={
                    "session_id": session_id,
                    "agent_id": agent_id,
                    "entity_id": entity_id,
                    "user_id": user_id,
                    "metadata": metadata or {},
                }
            )
            
            if response.status_code in (200, 201):
                data = response.json()
                return SessionRecord(
                    session_id=session_id,
                    agent_id=agent_id,
                    entity_id=entity_id,
                    user_id=user_id,
                    metadata=metadata or {},
                )
            raise Exception(f"Failed to create session: {response.status_code}")
            
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            raise
    
    async def get_session(self, session_id: str) -> Optional[SessionRecord]:
        """Get a session by ID."""
        try:
            client = await self._get_client()
            response = await client.get(f"/api/v1/sessions/{session_id}")
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            return SessionRecord(
                session_id=data.get("session_id", ""),
                agent_id=data.get("agent_id"),
                entity_id=data.get("entity_id"),
                user_id=data.get("user_id", ""),
                status=data.get("status", "active"),
                message_count=data.get("message_count", 0),
                token_count=data.get("token_count", 0),
                cost_usd=data.get("cost_usd", 0.0),
            )
            
        except Exception as e:
            logger.error(f"Failed to get session: {e}")
            return None
    
    async def update_session(
        self,
        session_id: str,
        status: Optional[str] = None,
        message_count: Optional[int] = None,
        token_count: Optional[int] = None,
        cost_usd: Optional[float] = None,
    ) -> Optional[SessionRecord]:
        """Update session metrics."""
        try:
            client = await self._get_client()
            update_data = {}
            if status:
                update_data["status"] = status
            if message_count is not None:
                update_data["message_count"] = message_count
            if token_count is not None:
                update_data["token_count"] = token_count
            if cost_usd is not None:
                update_data["cost_usd"] = cost_usd
            
            response = await client.patch(
                f"/api/v1/sessions/{session_id}",
                json=update_data
            )
            
            if response.status_code == 200:
                return await self.get_session(session_id)
            return None
            
        except Exception as e:
            logger.error(f"Failed to update session: {e}")
            return None
    
    async def list_sessions(
        self,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[SessionRecord]:
        """List sessions with filters."""
        try:
            client = await self._get_client()
            params = {"limit": limit}
            if user_id:
                params["user_id"] = user_id
            if agent_id:
                params["agent_id"] = agent_id
            if status:
                params["status"] = status
            
            response = await client.get("/api/v1/sessions", params=params)
            
            if response.status_code != 200:
                return []
            
            return [
                SessionRecord(
                    session_id=s.get("session_id", ""),
                    agent_id=s.get("agent_id"),
                    user_id=s.get("user_id", ""),
                    status=s.get("status", "active"),
                )
                for s in response.json().get("sessions", [])
            ]
            
        except Exception as e:
            logger.error(f"Failed to list sessions: {e}")
            return []
    
    # =========================================================================
    # Interaction Operations
    # =========================================================================
    
    async def record_interaction(
        self,
        session_id: str,
        role: str,
        content: str,
        message_id: Optional[str] = None,
        model: Optional[str] = None,
        tokens_in: int = 0,
        tokens_out: int = 0,
        cost_usd: float = 0.0,
        latency_ms: int = 0,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> InteractionRecord:
        """Record an interaction message via HTTP with circuit breaker."""
        message_id = message_id or str(uuid4())
        
        # Get or create circuit breaker
        registry = get_breaker_registry()
        breaker = await registry.get_or_create(
            "openviking_interaction",
            fail_max=3,
            timeout_duration=30.0,
        )
        
        async def _do_record() -> InteractionRecord:
            client = await self._get_client()
            response = await client.post(
                "/api/v1/events",
                json={
                    "type": "interaction",
                    "session_id": session_id,
                    "message_id": message_id,
                    "role": role,
                    "content": content,
                    "model": model,
                    "tokens_in": tokens_in,
                    "tokens_out": tokens_out,
                    "cost_usd": cost_usd,
                    "latency_ms": latency_ms,
                    "tool_calls": tool_calls or [],
                    "metadata": metadata or {},
                }
            )
            
            if response.status_code in (200, 201):
                return InteractionRecord(
                    session_id=session_id,
                    message_id=message_id,
                    role=role,
                    content=content,
                    model=model,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    cost_usd=cost_usd,
                    latency_ms=latency_ms,
                    tool_calls=tool_calls or [],
                    metadata=metadata or {},
                )
            raise Exception(f"Failed to record interaction: {response.status_code}")
        
        try:
            return await breaker.call(_do_record)
        except CircuitBreakerOpenError:
            # Fast fail: raise to allow fallback
            logger.warning("OpenViking circuit breaker open, fast failing")
            raise
        except Exception as e:
            logger.error(f"Failed to record interaction: {e}")
            raise
    
    async def get_session_interactions(
        self,
        session_id: str,
        limit: int = 1000,
    ) -> List[InteractionRecord]:
        """Get all interactions for a session."""
        try:
            client = await self._get_client()
            response = await client.get(
                f"/api/v1/sessions/{session_id}/interactions",
                params={"limit": limit}
            )
            
            if response.status_code != 200:
                return []
            
            return [
                InteractionRecord(
                    session_id=i.get("session_id", ""),
                    message_id=i.get("message_id", ""),
                    role=i.get("role", "user"),
                    content=i.get("content", ""),
                    model=i.get("model"),
                    tokens_in=i.get("tokens_in", 0),
                    tokens_out=i.get("tokens_out", 0),
                    cost_usd=i.get("cost_usd", 0.0),
                    latency_ms=i.get("latency_ms", 0),
                )
                for i in response.json().get("interactions", [])
            ]
            
        except Exception as e:
            logger.error(f"Failed to get interactions: {e}")
            return []
    
    # =========================================================================
    # Log Operations
    # =========================================================================
    
    async def record_log(
        self,
        level: str,
        source: str,
        message: str,
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> LogRecord:
        """Record a log entry via HTTP."""
        try:
            client = await self._get_client()
            response = await client.post(
                "/api/v1/events",
                json={
                    "type": "log",
                    "level": level,
                    "source": source,
                    "message": message,
                    "session_id": session_id,
                    "agent_id": agent_id,
                    "data": data or {},
                }
            )
            
            if response.status_code in (200, 201):
                return LogRecord(
                    level=level,
                    source=source,
                    message=message,
                    session_id=session_id,
                    agent_id=agent_id,
                    data=data or {},
                )
            raise Exception(f"Failed to record log: {response.status_code}")
            
        except Exception as e:
            logger.error(f"Failed to record log: {e}")
            raise
    
    async def query_logs(
        self,
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        level: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000,
    ) -> List[LogRecord]:
        """Query logs with filters."""
        try:
            client = await self._get_client()
            params = {"limit": limit}
            if session_id:
                params["session_id"] = session_id
            if agent_id:
                params["agent_id"] = agent_id
            if level:
                params["level"] = level
            if start_time:
                params["start_time"] = start_time.isoformat()
            if end_time:
                params["end_time"] = end_time.isoformat()
            
            response = await client.get("/api/v1/logs", params=params)
            
            if response.status_code != 200:
                return []
            
            return [
                LogRecord(
                    level=l.get("level", "info"),
                    source=l.get("source", ""),
                    message=l.get("message", ""),
                    session_id=l.get("session_id"),
                    agent_id=l.get("agent_id"),
                    data=l.get("data", {}),
                )
                for l in response.json().get("logs", [])
            ]
            
        except Exception as e:
            logger.error(f"Failed to query logs: {e}")
            return []


# ============================================================================
# Episodic Memory Store
# ============================================================================

class EpisodicMemoryStore:
    """
    L3 Episodic Memory store using OpenViking via HTTP.
    
    Provides:
    - Session history with full context via REST API
    - Interaction logging with token/cost tracking
    - Debug log aggregation
    - Raw file storage
    - Timeline queries
    """
    
    def __init__(self, openviking_client: Optional[OpenVikingClient] = None):
        self.openviking = openviking_client or OpenVikingClient()
    
    async def initialize(self) -> bool:
        """Initialize the episodic store."""
        return await self.openviking.connect()
    
    async def close(self) -> None:
        """Close the store."""
        await self.openviking.close()
    
    # Session operations
    async def create_session(
        self,
        session_id: str,
        agent_id: Optional[str] = None,
        entity_id: Optional[str] = None,
        user_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SessionRecord:
        """Create a new session."""
        return await self.openviking.create_session(
            session_id=session_id,
            agent_id=agent_id,
            entity_id=entity_id,
            user_id=user_id,
            metadata=metadata,
        )
    
    async def get_session(self, session_id: str) -> Optional[SessionRecord]:
        """Get a session."""
        return await self.openviking.get_session(session_id)
    
    async def end_session(
        self,
        session_id: str,
        status: str = "completed",
    ) -> Optional[SessionRecord]:
        """End a session."""
        return await self.openviking.update_session(
            session_id=session_id,
            status=status,
        )
    
    # Interaction operations
    async def record_message(
        self,
        session_id: str,
        role: str,
        content: str,
        **kwargs: Any,
    ) -> InteractionRecord:
        """Record a message in a session."""
        return await self.openviking.record_interaction(
            session_id=session_id,
            role=role,
            content=content,
            **kwargs,
        )
    
    async def get_messages(
        self,
        session_id: str,
        limit: int = 1000,
    ) -> List[InteractionRecord]:
        """Get session messages."""
        return await self.openviking.get_session_interactions(session_id, limit)
    
    # Log operations
    async def log(
        self,
        level: str,
        source: str,
        message: str,
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        **data: Any,
    ) -> LogRecord:
        """Record a log entry."""
        return await self.openviking.record_log(
            level=level,
            source=source,
            message=message,
            session_id=session_id,
            agent_id=agent_id,
            data=data,
        )
    
    async def query_logs(
        self,
        session_id: Optional[str] = None,
        **kwargs: Any,
    ) -> List[LogRecord]:
        """Query logs."""
        return await self.openviking.query_logs(
            session_id=session_id,
            **kwargs,
        )
    
    # Timeline operations
    async def get_timeline(
        self,
        session_id: str,
    ) -> Dict[str, Any]:
        """Get a complete timeline for a session."""
        session = await self.get_session(session_id)
        if not session:
            return {}
        
        messages = await self.get_messages(session_id)
        logs = await self.query_logs(session_id=session_id)
        
        timeline = []
        
        for msg in messages:
            timeline.append({
                "type": "message",
                "timestamp": msg.created_at,
                "role": msg.role,
                "content": msg.content[:200],
                "tokens": msg.tokens_in + msg.tokens_out,
            })
        
        for log in logs:
            timeline.append({
                "type": "log",
                "timestamp": log.timestamp,
                "level": log.level,
                "source": log.source,
                "message": log.message,
            })
        
        timeline.sort(key=lambda x: x["timestamp"], reverse=True)
        
        return {
            "session": session,
            "events": timeline,
        }


# Global episodic store instance
_global_episodic_store: Optional[EpisodicMemoryStore] = None


def get_episodic_store(config: Optional[Dict[str, Any]] = None) -> EpisodicMemoryStore:
    """Get or create global episodic store."""
    global _global_episodic_store
    if _global_episodic_store is None:
        _global_episodic_store = EpisodicMemoryStore(
            openviking_client=OpenVikingClient(config)
        )
    return _global_episodic_store