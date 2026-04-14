"""
XenoSys Memory System - L4 Contextual Memory (BrainSys)
Built on Membase for AI's second brain via REST API.

Membase: https://membase.so
The AI's own second brain - context captured, processed, and analyzed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

import httpx

logger = logging.getLogger(__name__)


# ============================================================================
# BrainSys Types
# ============================================================================

@dataclass
class ContextEntry:
    """A context entry in BrainSys."""
    id: UUID = field(default_factory=uuid4)
    content: str = ""
    context_type: str = "general"  # analysis, summary, insight, pattern
    source_session_id: Optional[str] = None
    source_interaction_id: Optional[str] = None
    embedding: Optional[List[float]] = None
    importance: float = 0.7  # Higher default than L1
    created_at: datetime = field(default_factory=datetime.utcnow)
    processed_at: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ContextAnalysis:
    """Analysis result from processing context."""
    entry_id: UUID
    summary: str
    key_points: List[str] = field(default_factory=list)
    entities: List[str] = field(default_factory=list)
    sentiment: str = "neutral"
    confidence: float = 0.5


@dataclass
class PatternRecord:
    """A recurring pattern detected in context."""
    id: UUID = field(default_factory=uuid4)
    pattern_type: str = ""  # behavioral, linguistic, technical
    description: str = ""
    frequency: int = 0
    first_seen: datetime = field(default_factory=datetime.utcnow)
    last_seen: datetime = field(default_factory=datetime.utcnow)
    evidence: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Membase HTTP Client
# ============================================================================

class MembaseClient:
    """
    Client for Membase operations via HTTP.
    
    Membase provides:
    - Context storage and retrieval
    - Pattern detection and learning
    - Semantic memory for AI
    - Real-time context analysis
    - Multi-modal context support
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.endpoint = self.config.get("endpoint", "http://localhost:9000")
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
        """Connect to Membase."""
        try:
            client = await self._get_client()
            response = await client.get("/health")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to connect to Membase: {e}")
            return False
    
    # Context operations
    async def store_context(
        self,
        content: str,
        context_type: str = "general",
        source_session_id: Optional[str] = None,
        source_interaction_id: Optional[str] = None,
        importance: float = 0.7,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ContextEntry:
        """Store a context entry via HTTP."""
        try:
            client = await self._get_client()
            response = await client.post(
                "/api/v1/context",
                json={
                    "content": content,
                    "context_type": context_type,
                    "source_session_id": source_session_id,
                    "source_interaction_id": source_interaction_id,
                    "importance": importance,
                    "tags": tags or [],
                    "metadata": metadata or {},
                }
            )
            
            if response.status_code in (200, 201):
                data = response.json()
                return ContextEntry(
                    content=content,
                    context_type=context_type,
                    source_session_id=source_session_id,
                    source_interaction_id=source_interaction_id,
                    importance=importance,
                    tags=tags or [],
                    metadata=metadata or {},
                )
            raise Exception(f"Failed to store context: {response.status_code}")
            
        except Exception as e:
            logger.error(f"Failed to store context: {e}")
            raise
    
    async def get_context(self, context_id: UUID) -> Optional[ContextEntry]:
        """Get a context entry."""
        try:
            client = await self._get_client()
            response = await client.get(f"/api/v1/context/{context_id}")
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            return ContextEntry(
                content=data.get("content", ""),
                context_type=data.get("context_type", "general"),
                importance=data.get("importance", 0.7),
            )
            
        except Exception as e:
            logger.error(f"Failed to get context: {e}")
            return None
    
    async def search_contexts(
        self,
        query: str,
        context_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        top_k: int = 10,
    ) -> List[ContextEntry]:
        """Search context entries via HTTP."""
        try:
            client = await self._get_client()
            response = await client.post(
                "/api/v1/context/search",
                json={
                    "query": query,
                    "context_type": context_type,
                    "tags": tags,
                    "top_k": top_k,
                }
            )
            
            if response.status_code != 200:
                return []
            
            return [
                ContextEntry(
                    content=c.get("content", ""),
                    context_type=c.get("context_type", "general"),
                    importance=c.get("importance", 0.7),
                    tags=c.get("tags", []),
                )
                for c in response.json().get("results", [])
            ]
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
    
    async def update_context(
        self,
        context_id: UUID,
        processed: bool = True,
        importance: Optional[float] = None,
    ) -> Optional[ContextEntry]:
        """Update a context entry."""
        try:
            client = await self._get_client()
            update_data = {"processed": processed}
            if importance is not None:
                update_data["importance"] = importance
            
            response = await client.patch(
                f"/api/v1/context/{context_id}",
                json=update_data
            )
            
            if response.status_code == 200:
                return await self.get_context(context_id)
            return None
            
        except Exception as e:
            logger.error(f"Failed to update context: {e}")
            return None
    
    # Pattern operations
    async def record_pattern(
        self,
        pattern_type: str,
        description: str,
        evidence: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PatternRecord:
        """Record a pattern via HTTP."""
        try:
            client = await self._get_client()
            response = await client.post(
                "/api/v1/patterns",
                json={
                    "pattern_type": pattern_type,
                    "description": description,
                    "evidence": evidence or [],
                    "metadata": metadata or {},
                }
            )
            
            if response.status_code in (200, 201):
                return PatternRecord(
                    pattern_type=pattern_type,
                    description=description,
                    evidence=evidence or [],
                    metadata=metadata or {},
                )
            raise Exception(f"Failed to record pattern: {response.status_code}")
            
        except Exception as e:
            logger.error(f"Failed to record pattern: {e}")
            raise
    
    async def update_pattern_frequency(self, pattern_id: UUID) -> None:
        """Update pattern frequency via HTTP."""
        try:
            client = await self._get_client()
            await client.post(f"/api/v1/patterns/{pattern_id}/increment")
        except Exception as e:
            logger.error(f"Failed to update pattern frequency: {e}")
    
    async def get_patterns(
        self,
        pattern_type: Optional[str] = None,
        min_frequency: int = 1,
    ) -> List[PatternRecord]:
        """Get recorded patterns."""
        try:
            client = await self._get_client()
            params = {"min_frequency": min_frequency}
            if pattern_type:
                params["pattern_type"] = pattern_type
            
            response = await client.get("/api/v1/patterns", params=params)
            
            if response.status_code != 200:
                return []
            
            return [
                PatternRecord(
                    pattern_type=p.get("pattern_type", ""),
                    description=p.get("description", ""),
                    frequency=p.get("frequency", 0),
                    evidence=p.get("evidence", []),
                )
                for p in response.json().get("patterns", [])
            ]
            
        except Exception as e:
            logger.error(f"Failed to get patterns: {e}")
            return []
    
    # Analysis operations
    async def analyze_context(
        self,
        context_id: UUID,
    ) -> Optional[ContextAnalysis]:
        """Analyze a context entry via HTTP."""
        try:
            client = await self._get_client()
            response = await client.post(f"/api/v1/context/{context_id}/analyze")
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            return ContextAnalysis(
                entry_id=context_id,
                summary=data.get("summary", ""),
                key_points=data.get("key_points", []),
                entities=data.get("entities", []),
                sentiment=data.get("sentiment", "neutral"),
                confidence=data.get("confidence", 0.5),
            )
            
        except Exception as e:
            logger.error(f"Failed to analyze context: {e}")
            return None
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get BrainSys statistics."""
        return {
            "endpoint": self.endpoint,
        }


# ============================================================================
# BrainSys Store (Contextual Memory)
# ============================================================================

class BrainSysStore:
    """
    L4 Contextual Memory store using Membase via HTTP.
    
    Provides:
    - AI's own second brain for context analysis
    - Pattern detection and learning
    - Context importance scoring
    - Semantic context search
    - Real-time analysis
    """
    
    def __init__(self, membase_client: Optional[MembaseClient] = None):
        self.membase = membase_client or MembaseClient()
    
    async def initialize(self) -> bool:
        """Initialize BrainSys store."""
        return await self.membase.connect()
    
    async def close(self) -> None:
        """Close the store."""
        await self.membase.close()
    
    async def capture_context(
        self,
        content: str,
        context_type: str = "general",
        source_session_id: Optional[str] = None,
        source_interaction_id: Optional[str] = None,
        importance: float = 0.7,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ContextEntry:
        """Capture new context from interaction."""
        return await self.membase.store_context(
            content=content,
            context_type=context_type,
            source_session_id=source_session_id,
            source_interaction_id=source_interaction_id,
            importance=importance,
            tags=tags,
            metadata=metadata,
        )
    
    async def analyze_and_capture(
        self,
        session_id: str,
        interaction_content: str,
        context_type: str = "analysis",
    ) -> ContextEntry:
        """Capture and analyze context from interaction."""
        entry = await self.capture_context(
            content=interaction_content,
            context_type=context_type,
            source_session_id=session_id,
            importance=0.8,
            tags=[context_type],
        )
        
        analysis = await self.membase.analyze_context(entry.id)
        
        if analysis:
            await self.membase.update_context(
                entry.id,
                importance=analysis.confidence,
            )
            
            await self._detect_patterns(entry, analysis)
        
        return entry
    
    async def _detect_patterns(
        self,
        entry: ContextEntry,
        analysis: ContextAnalysis,
    ) -> None:
        """Detect patterns in the context."""
        if len(analysis.key_points) > 2:
            await self.membase.record_pattern(
                pattern_type="behavioral",
                description=f"Multi-point response pattern ({len(analysis.key_points)} points)",
                evidence=[entry.content[:100]],
            )
        
        if any(tag in entry.tags for tag in ["code", "debug", "error"]):
            await self.membase.record_pattern(
                pattern_type="technical",
                description="Technical problem-solving pattern",
                evidence=[entry.content[:100]],
            )
    
    async def retrieve_context(
        self,
        query: str,
        context_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        top_k: int = 10,
    ) -> List[ContextEntry]:
        """Retrieve relevant context."""
        return await self.membase.search_contexts(
            query=query,
            context_type=context_type,
            tags=tags,
            top_k=top_k,
        )
    
    async def get_patterns(
        self,
        pattern_type: Optional[str] = None,
    ) -> List[PatternRecord]:
        """Get learned patterns."""
        return await self.membase.get_patterns(pattern_type=pattern_type)
    
    async def get_session_context(
        self,
        session_id: str,
    ) -> List[ContextEntry]:
        """Get all context for a session."""
        return await self.membase.search_contexts(
            query="",
            tags=[session_id],
            top_k=100,
        )
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get BrainSys statistics."""
        return await self.membase.get_stats()


# Global BrainSys store instance
_global_brainsys_store: Optional[BrainSysStore] = None


def get_brainsys_store(config: Optional[Dict[str, Any]] = None) -> BrainSysStore:
    """Get or create global BrainSys store."""
    global _global_brainsys_store
    if _global_brainsys_store is None:
        _global_brainsys_store = BrainSysStore(
            membase_client=MembaseClient(config)
        )
    return _global_brainsys_store