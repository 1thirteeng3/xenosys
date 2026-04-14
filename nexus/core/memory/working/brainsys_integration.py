"""
XenoSys Memory System - L4 Contextual Memory (BrainSys)
Built on Membase for AI's second brain.

Membase: https://membase.so
The AI's own second brain - context captured, processed, and analyzed.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

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
# Membase Integration
# ============================================================================

class MembaseClient:
    """
    Client for Membase operations.
    
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
        self._connected = False
        self._contexts: Dict[str, ContextEntry] = {}
        self._patterns: Dict[str, PatternRecord] = {}
        self._lock = asyncio.Lock()
    
    async def connect(self) -> bool:
        """Connect to Membase."""
        try:
            # In production, would verify connectivity
            self._connected = True
            logger.info(f"Connected to Membase at {self.endpoint}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Membase: {e}")
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from Membase."""
        self._connected = False
        logger.info("Disconnected from Membase")
    
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
        """Store a context entry."""
        entry = ContextEntry(
            content=content,
            context_type=context_type,
            source_session_id=source_session_id,
            source_interaction_id=source_interaction_id,
            importance=importance,
            tags=tags or [],
            metadata=metadata or {},
        )
        
        # Generate embedding
        entry.embedding = await self._generate_embedding(content)
        
        async with self._lock:
            self._contexts[str(entry.id)] = entry
        
        logger.info(f"Stored context: {entry.id}")
        return entry
    
    async def get_context(self, context_id: UUID) -> Optional[ContextEntry]:
        """Get a context entry."""
        async with self._lock:
            return self._contexts.get(str(context_id))
    
    async def search_contexts(
        self,
        query: str,
        context_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        top_k: int = 10,
    ) -> List[ContextEntry]:
        """Search context entries."""
        results = []
        query_lower = query.lower()
        
        async with self._lock:
            for entry in self._contexts.values():
                # Filter by type
                if context_type and entry.context_type != context_type:
                    continue
                
                # Filter by tags
                if tags and not any(tag in entry.tags for tag in tags):
                    continue
                
                # Simple text search
                if query_lower in entry.content.lower():
                    results.append(entry)
        
        # Sort by importance
        results.sort(key=lambda e: e.importance, reverse=True)
        return results[:top_k]
    
    async def update_context(
        self,
        context_id: UUID,
        processed: bool = True,
        importance: Optional[float] = None,
    ) -> Optional[ContextEntry]:
        """Update a context entry."""
        async with self._lock:
            entry = self._contexts.get(str(context_id))
            if not entry:
                return None
            
            if processed:
                entry.processed_at = datetime.utcnow()
            if importance is not None:
                entry.importance = importance
            
            return entry
    
    # Pattern operations
    async def record_pattern(
        self,
        pattern_type: str,
        description: str,
        evidence: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PatternRecord:
        """Record a pattern."""
        pattern = PatternRecord(
            pattern_type=pattern_type,
            description=description,
            evidence=evidence or [],
            metadata=metadata or {},
        )
        
        async with self._lock:
            self._patterns[str(pattern.id)] = pattern
        
        logger.info(f"Recorded pattern: {pattern.id}")
        return pattern
    
    async def update_pattern_frequency(self, pattern_id: UUID) -> None:
        """Update pattern frequency."""
        async with self._lock:
            pattern = self._patterns.get(str(pattern_id))
            if pattern:
                pattern.frequency += 1
                pattern.last_seen = datetime.utcnow()
    
    async def get_patterns(
        self,
        pattern_type: Optional[str] = None,
        min_frequency: int = 1,
    ) -> List[PatternRecord]:
        """Get recorded patterns."""
        async with self._lock:
            patterns = list(self._patterns.values())
        
        if pattern_type:
            patterns = [p for p in patterns if p.pattern_type == pattern_type]
        patterns = [p for p in patterns if p.frequency >= min_frequency]
        
        return sorted(patterns, key=lambda p: p.frequency, reverse=True)
    
    # Analysis operations
    async def analyze_context(
        self,
        context_id: UUID,
    ) -> Optional[ContextAnalysis]:
        """Analyze a context entry."""
        entry = await self.get_context(context_id)
        if not entry:
            return None
        
        # Simple analysis (placeholder for actual LLM-based analysis)
        words = entry.content.split()
        
        # Extract key points (simple sentence extraction)
        sentences = entry.content.split('.')
        key_points = [s.strip() for s in sentences[:3] if s.strip()]
        
        # Extract entities (simple proper noun detection)
        entities = [w for w in words if w[0].isupper() and len(w) > 1][:10]
        
        analysis = ContextAnalysis(
            entry_id=context_id,
            summary=entry.content[:200] + "...",
            key_points=key_points,
            entities=entities,
            confidence=0.6,  # Placeholder
        )
        
        # Mark context as processed
        await self.update_context(context_id, processed=True)
        
        return analysis
    
    # Statistics
    async def get_stats(self) -> Dict[str, Any]:
        """Get BrainSys statistics."""
        async with self._lock:
            return {
                "total_contexts": len(self._contexts),
                "total_patterns": len(self._patterns),
                "by_type": self._count_by_type(),
                "connected": self._connected,
            }
    
    def _count_by_type(self) -> Dict[str, int]:
        """Count contexts by type."""
        counts: Dict[str, int] = {}
        for entry in self._contexts.values():
            t = entry.context_type
            counts[t] = counts.get(t, 0) + 1
        return counts
    
    async def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text."""
        # Placeholder - would use actual embedding model
        import hashlib
        h = hashlib.sha256(text.encode()).digest()
        return [float(b) / 255.0 for b in h[:384]]


# ============================================================================
# BrainSys Store (Contextual Memory)
# ============================================================================

class BrainSysStore:
    """
    L4 Contextual Memory store using Membase.
    
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
        # Store raw context
        entry = await self.capture_context(
            content=interaction_content,
            context_type=context_type,
            source_session_id=session_id,
            importance=0.8,
            tags=[context_type],
        )
        
        # Analyze context
        analysis = await self.membase.analyze_context(entry.id)
        
        if analysis:
            # Update entry with analysis metadata
            await self.membase.update_context(
                entry.id,
                importance=analysis.confidence,
            )
            
            # Detect and record patterns
            await self._detect_patterns(entry, analysis)
        
        return entry
    
    async def _detect_patterns(
        self,
        entry: ContextEntry,
        analysis: ContextAnalysis,
    ) -> None:
        """Detect patterns in the context."""
        # Check for behavioral patterns
        if len(analysis.key_points) > 2:
            await self.membase.record_pattern(
                pattern_type="behavioral",
                description=f"Multi-point response pattern ({len(analysis.key_points)} points)",
                evidence=[entry.content[:100]],
            )
        
        # Check for technical patterns
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
            tags=[session_id],  # Could use session tag
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