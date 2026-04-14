"""
XenoSys Memory System - L3 Episodic Memory
Built on OpenViking for session logging, interaction records, and raw files.

OpenViking: https://github.com/volcengine/OpenViking
Records each interaction, log, and raw file with date and time.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

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
# OpenViking Integration
# ============================================================================

class OpenVikingClient:
    """
    Client for OpenViking episodic memory operations.
    
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
        self.data_path = self.config.get("data_path", "./xenosys_episodic")
        self._ensure_data_dir()
        self._sessions: Dict[str, SessionRecord] = {}
        self._interactions: Dict[str, List[InteractionRecord]] = {}
        self._logs: List[LogRecord] = []
        self._files: Dict[str, RawFileRecord] = {}
        self._lock = asyncio.Lock()
    
    def _ensure_data_dir(self) -> None:
        """Ensure data directory exists."""
        import os
        os.makedirs(self.data_path, exist_ok=True)
        os.makedirs(f"{self.data_path}/sessions", exist_ok=True)
        os.makedirs(f"{self.data_path}/interactions", exist_ok=True)
        os.makedirs(f"{self.data_path}/logs", exist_ok=True)
        os.makedirs(f"{self.data_path}/files", exist_ok=True)
    
    async def connect(self) -> bool:
        """Connect to OpenViking (mock for now)."""
        logger.info(f"Connected to OpenViking at {self.endpoint}")
        return True
    
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
        """Create a new session record."""
        session = SessionRecord(
            session_id=session_id,
            agent_id=agent_id,
            entity_id=entity_id,
            user_id=user_id,
            metadata=metadata or {},
        )
        
        async with self._lock:
            self._sessions[session_id] = session
        
        # Persist to disk
        await self._persist_session(session)
        
        logger.info(f"Created session: {session_id}")
        return session
    
    async def get_session(self, session_id: str) -> Optional[SessionRecord]:
        """Get a session by ID."""
        return self._sessions.get(session_id)
    
    async def update_session(
        self,
        session_id: str,
        status: Optional[str] = None,
        message_count: Optional[int] = None,
        token_count: Optional[int] = None,
        cost_usd: Optional[float] = None,
    ) -> Optional[SessionRecord]:
        """Update session metrics."""
        session = self._sessions.get(session_id)
        if not session:
            return None
        
        if status:
            session.status = status
            if status in ("completed", "failed"):
                session.ended_at = datetime.utcnow()
        
        if message_count is not None:
            session.message_count = message_count
        if token_count is not None:
            session.token_count = token_count
        if cost_usd is not None:
            session.cost_usd = cost_usd
        
        await self._persist_session(session)
        return session
    
    async def list_sessions(
        self,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[SessionRecord]:
        """List sessions with filters."""
        sessions = list(self._sessions.values())
        
        if user_id:
            sessions = [s for s in sessions if s.user_id == user_id]
        if agent_id:
            sessions = [s for s in sessions if s.agent_id == agent_id]
        if status:
            sessions = [s for s in sessions if s.status == status]
        
        # Sort by started_at descending
        sessions.sort(key=lambda s: s.started_at, reverse=True)
        return sessions[:limit]
    
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
        """Record an interaction message."""
        message_id = message_id or str(uuid4())
        
        interaction = InteractionRecord(
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
        
        # Store
        async with self._lock:
            if session_id not in self._interactions:
                self._interactions[session_id] = []
            self._interactions[session_id].append(interaction)
        
        # Persist
        await self._persist_interaction(interaction)
        
        # Update session
        await self._update_session_message_count(session_id)
        
        logger.info(f"Recorded interaction: {session_id}/{message_id}")
        return interaction
    
    async def get_session_interactions(
        self,
        session_id: str,
        limit: int = 1000,
    ) -> List[InteractionRecord]:
        """Get all interactions for a session."""
        interactions = self._interactions.get(session_id, [])
        return interactions[:limit]
    
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
        """Record a log entry."""
        log = LogRecord(
            level=level,
            source=source,
            session_id=session_id,
            agent_id=agent_id,
            message=message,
            data=data or {},
        )
        
        async with self._lock:
            self._logs.append(log)
        
        # Persist
        await self._persist_log(log)
        
        return log
    
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
        logs = self._logs.copy()
        
        if session_id:
            logs = [l for l in logs if l.session_id == session_id]
        if agent_id:
            logs = [l for l in logs if l.agent_id == agent_id]
        if level:
            logs = [l for l in logs if l.level == level]
        if start_time:
            logs = [l for l in logs if l.timestamp >= start_time]
        if end_time:
            logs = [l for l in logs if l.timestamp <= end_time]
        
        # Sort by timestamp
        logs.sort(key=lambda l: l.timestamp, reverse=True)
        return logs[:limit]
    
    # =========================================================================
    # Raw File Operations
    # =========================================================================
    
    async def store_file(
        self,
        filename: str,
        content: bytes,
        content_type: str = "application/octet-stream",
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> RawFileRecord:
        """Store a raw file."""
        import hashlib
        import os
        
        # Calculate checksum
        checksum = hashlib.sha256(content).hexdigest()
        
        # Generate storage path
        file_id = str(uuid4())
        ext = os.path.splitext(filename)[1]
        storage_path = f"{self.data_path}/files/{file_id}{ext}"
        
        # Write to disk
        with open(storage_path, "wb") as f:
            f.write(content)
        
        record = RawFileRecord(
            filename=filename,
            content_type=content_type,
            size_bytes=len(content),
            storage_path=storage_path,
            checksum=checksum,
            session_id=session_id,
            metadata=metadata or {},
        )
        
        async with self._lock:
            self._files[file_id] = record
        
        logger.info(f"Stored file: {filename} ({len(content)} bytes)")
        return record
    
    async def get_file(self, file_id: str) -> Optional[RawFileRecord]:
        """Get a file record."""
        return self._files.get(file_id)
    
    async def get_file_content(self, file_id: str) -> Optional[bytes]:
        """Get file content."""
        record = await self.get_file(file_id)
        if not record:
            return None
        
        try:
            with open(record.storage_path, "rb") as f:
                return f.read()
        except Exception:
            return None
    
    # =========================================================================
    # Persistence (Local JSON files for demo)
    # =========================================================================
    
    async def _persist_session(self, session: SessionRecord) -> None:
        """Persist session to disk."""
        import json
        from datetime import datetime
        
        path = f"{self.data_path}/sessions/{session.session_id}.json"
        data = {
            "id": str(session.id),
            "session_id": session.session_id,
            "agent_id": session.agent_id,
            "entity_id": session.entity_id,
            "user_id": session.user_id,
            "status": session.status,
            "started_at": session.started_at.isoformat(),
            "ended_at": session.ended_at.isoformat() if session.ended_at else None,
            "message_count": session.message_count,
            "token_count": session.token_count,
            "cost_usd": session.cost_usd,
            "metadata": session.metadata,
        }
        
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    
    async def _persist_interaction(self, interaction: InteractionRecord) -> None:
        """Persist interaction to disk."""
        import json
        
        path = f"{self.data_path}/interactions/{interaction.message_id}.json"
        data = {
            "id": str(interaction.id),
            "session_id": interaction.session_id,
            "message_id": interaction.message_id,
            "role": interaction.role,
            "content": interaction.content,
            "model": interaction.model,
            "tokens_in": interaction.tokens_in,
            "tokens_out": interaction.tokens_out,
            "cost_usd": interaction.cost_usd,
            "latency_ms": interaction.latency_ms,
            "created_at": interaction.created_at.isoformat(),
            "tool_calls": interaction.tool_calls,
            "metadata": interaction.metadata,
        }
        
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    
    async def _persist_log(self, log: LogRecord) -> None:
        """Persist log to disk."""
        import json
        
        path = f"{self.data_path}/logs/{log.id}.json"
        data = {
            "id": str(log.id),
            "timestamp": log.timestamp.isoformat(),
            "level": log.level,
            "source": log.source,
            "session_id": log.session_id,
            "agent_id": log.agent_id,
            "message": log.message,
            "data": log.data,
        }
        
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    
    async def _update_session_message_count(self, session_id: str) -> None:
        """Update session message count."""
        session = self._sessions.get(session_id)
        if session:
            session.message_count = len(self._interactions.get(session_id, []))


# ============================================================================
# Episodic Memory Store
# ============================================================================

class EpisodicMemoryStore:
    """
    L3 Episodic Memory store using OpenViking.
    
    Provides:
    - Session history with full context
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
    
    # File operations
    async def store_file(
        self,
        filename: str,
        content: bytes,
        content_type: str = "application/octet-stream",
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> RawFileRecord:
        """Store a file."""
        return await self.openviking.store_file(
            filename=filename,
            content=content,
            content_type=content_type,
            session_id=session_id,
            metadata=metadata,
        )
    
    async def get_file(self, file_id: str) -> Optional[RawFileRecord]:
        """Get a file."""
        return await self.openviking.get_file(file_id)
    
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
        
        # Combine and sort by timestamp
        timeline = []
        
        for msg in messages:
            timeline.append({
                "type": "message",
                "timestamp": msg.created_at,
                "role": msg.role,
                "content": msg.content[:200],  # Truncate
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