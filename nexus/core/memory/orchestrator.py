"""
XenoSys Memory System - Orchestrator
Coordinates multi-layer memory operations (L1-L4).

Memory Layers:
- L1 Semantic (Cortex): Vector embeddings, semantic search
- L2 Long-term (Obsidian/2ndBrain): User notes, personal knowledge
- L3 Episodic (OpenViking): Session logs, interactions, raw files
- L4 Contextual (Membase/BrainSys): AI's second brain, patterns
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from .l1_semantic.cortex_integration import (
    SemanticMemoryStore,
    SemanticSearchResult,
    get_semantic_store,
)
from .l2_longterm.secondbrain_integration import (
    SecondBrainStore,
    NoteSearchResult,
    get_secondbrain_store,
)
from .l3_episodic.openviking_integration import (
    EpisodicMemoryStore,
    SessionRecord,
    InteractionRecord,
    get_episodic_store,
)
from .working.brainsys_integration import (
    BrainSysStore,
    ContextEntry,
    PatternRecord,
    get_brainsys_store,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Memory Layer Enum
# ============================================================================

class MemoryLayer(Enum):
    """Memory layer identifiers."""
    SEMANTIC = "semantic"      # L1 - Cortex
    LONGTERM = "longterm"      # L2 - Obsidian (2ndBrain)
    EPISODIC = "episodic"       # L3 - OpenViking
    CONTEXTUAL = "contextual"   # L4 - Membase (BrainSys)


# ============================================================================
# Memory Query Types
# ============================================================================

@dataclass
class MemoryQuery:
    """Query for memory search."""
    query: str
    layers: List[MemoryLayer] = field(default_factory=lambda: [
        MemoryLayer.SEMANTIC,
        MemoryLayer.CONTEXTUAL,
    ])
    agent_id: Optional[str] = None
    entity_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    top_k: int = 10
    min_importance: float = 0.0


@dataclass
class MemoryResult:
    """Result from memory retrieval."""
    content: str
    layer: MemoryLayer
    relevance: float
    importance: float
    source_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Memory Orchestrator
# ============================================================================

class MemoryOrchestrator:
    """
    Orchestrates multi-layer memory operations.
    
    Provides:
    - Unified memory search across layers
    - Automatic layer selection based on query
    - Memory routing based on content type
    - Consistency management between layers
    """
    
    def __init__(
        self,
        semantic_store: Optional[SemanticMemoryStore] = None,
        secondbrain_store: Optional[SecondBrainStore] = None,
        episodic_store: Optional[EpisodicMemoryStore] = None,
        brainsys_store: Optional[BrainSysStore] = None,
    ):
        self.semantic = semantic_store or get_semantic_store()
        self.secondbrain = secondbrain_store or get_secondbrain_store()
        self.episodic = episodic_store or get_episodic_store()
        self.brainsys = brainsys_store or get_brainsys_store()
        
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize all memory stores."""
        if self._initialized:
            return
        
        # Initialize each store
        try:
            await self.semantic.initialize()
        except Exception as e:
            logger.warning(f"Semantic store init failed: {e}")
        
        try:
            await self.secondbrain.initialize()
        except Exception as e:
            logger.warning(f"2ndBrain store init failed: {e}")
        
        try:
            await self.episodic.initialize()
        except Exception as e:
            logger.warning(f"Episodic store init failed: {e}")
        
        try:
            await self.brainsys.initialize()
        except Exception as e:
            logger.warning(f"BrainSys store init failed: {e}")
        
        self._initialized = True
        logger.info("Memory orchestrator initialized")
    
    # =========================================================================
    # Store Operations
    # =========================================================================
    
    async def store(
        self,
        content: str,
        layer: MemoryLayer,
        agent_id: Optional[str] = None,
        entity_id: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        importance: float = 0.5,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> UUID:
        """Store content in specified layer."""
        if layer == MemoryLayer.SEMANTIC:
            return await self.semantic.store(
                content=content,
                agent_id=agent_id,
                entity_id=entity_id,
                importance=importance,
                metadata=metadata,
            )
        
        elif layer == MemoryLayer.LONGTERM:
            return await self.secondbrain.store(
                content=content,
                tags=tags,
                user_id=user_id,
                metadata=metadata,
            )
        
        elif layer == MemoryLayer.EPISODIC:
            # Store as interaction
            if session_id:
                await self.episodic.record_message(
                    session_id=session_id,
                    role="system",
                    content=content,
                )
            return uuid4()
        
        elif layer == MemoryLayer.CONTEXTUAL:
            return await self.brainsys.capture_context(
                content=content,
                source_session_id=session_id,
                importance=importance,
                tags=tags,
                metadata=metadata,
            )
        
        raise ValueError(f"Unknown memory layer: {layer}")
    
    # =========================================================================
    # Search Operations
    # =========================================================================
    
    async def search(
        self,
        query: MemoryQuery,
    ) -> List[MemoryResult]:
        """Search across multiple memory layers."""
        results = []
        
        # Determine which layers to search
        layers = query.layers or [
            MemoryLayer.SEMANTIC,
            MemoryLayer.CONTEXTUAL,
        ]
        
        # Search each layer
        if MemoryLayer.SEMANTIC in layers:
            semantic_results = await self._search_semantic(query)
            results.extend(semantic_results)
        
        if MemoryLayer.LONGTERM in layers:
            longterm_results = await self._search_longterm(query)
            results.extend(longterm_results)
        
        if MemoryLayer.EPISODIC in layers:
            episodic_results = await self._search_episodic(query)
            results.extend(episodic_results)
        
        if MemoryLayer.CONTEXTUAL in layers:
            contextual_results = await self._search_contextual(query)
            results.extend(contextual_results)
        
        # Sort by relevance and filter by importance
        results = [r for r in results if r.importance >= query.min_importance]
        results.sort(key=lambda r: r.relevance * r.importance, reverse=True)
        
        # Limit results
        return results[:query.top_k]
    
    async def _search_semantic(self, query: MemoryQuery) -> List[MemoryResult]:
        """Search semantic memory (Cortex)."""
        results = await self.semantic.search(
            query=query.query,
            agent_id=query.agent_id,
            entity_id=query.entity_id,
            top_k=query.top_k,
        )
        
        return [
            MemoryResult(
                content=r.entry.content,
                layer=MemoryLayer.SEMANTIC,
                relevance=r.score,
                importance=r.entry.importance,
                source_id=str(r.entry.id),
            )
            for r in results
        ]
    
    async def _search_longterm(self, query: MemoryQuery) -> List[MemoryResult]:
        """Search long-term memory (2ndBrain/Obsidian)."""
        results = await self.secondbrain.search(
            query=query.query,
            user_id=query.user_id,
            limit=query.top_k,
        )
        
        return [
            MemoryResult(
                content=r.note.content,
                layer=MemoryLayer.LONGTERM,
                relevance=r.score,
                importance=0.6,  # Default for user notes
                source_id=r.note.path,
                metadata={"title": r.note.title, "tags": r.note.tags},
            )
            for r in results
        ]
    
    async def _search_episodic(self, query: MemoryQuery) -> List[MemoryResult]:
        """Search episodic memory (OpenViking)."""
        results = []
        
        # Get sessions for query
        if query.session_id:
            messages = await self.episodic.get_messages(query.session_id)
            query_lower = query.query.lower()
            
            for msg in messages:
                if query_lower in msg.content.lower():
                    results.append(MemoryResult(
                        content=msg.content,
                        layer=MemoryLayer.EPISODIC,
                        relevance=0.8,
                        importance=0.5,
                        source_id=msg.message_id,
                        metadata={"role": msg.role, "tokens": msg.tokens_in + msg.tokens_out},
                    ))
        
        # Limit
        return results[:query.top_k]
    
    async def _search_contextual(self, query: MemoryQuery) -> List[MemoryResult]:
        """Search contextual memory (BrainSys/Membase)."""
        results = await self.brainsys.retrieve_context(
            query=query.query,
            top_k=query.top_k,
        )
        
        return [
            MemoryResult(
                content=entry.content,
                layer=MemoryLayer.CONTEXTUAL,
                relevance=1.0,  # Semantic search
                importance=entry.importance,
                source_id=str(entry.id),
                metadata={"type": entry.context_type, "tags": entry.tags},
            )
            for entry in results
        ]
    
    # =========================================================================
    # Context Retrieval for Agents
    # =========================================================================
    
    async def get_agent_context(
        self,
        agent_id: str,
        query: str,
        include_sessions: bool = True,
    ) -> str:
        """Get formatted context for an agent."""
        mem_query = MemoryQuery(
            query=query,
            layers=[
                MemoryLayer.SEMANTIC,
                MemoryLayer.CONTEXTUAL,
            ],
            agent_id=agent_id,
            top_k=5,
        )
        
        results = await self.search(mem_query)
        
        if not results:
            return ""
        
        # Format context
        context_parts = ["Relevant context:"]
        for r in results:
            layer_name = r.layer.value
            context_parts.append(f"[{layer_name}] {r.content[:300]}")
        
        return "\n\n".join(context_parts)
    
    # =========================================================================
    # Session Memory Operations
    # =========================================================================
    
    async def create_session_memory(
        self,
        session_id: str,
        agent_id: Optional[str] = None,
        entity_id: Optional[str] = None,
        user_id: str = "",
    ) -> None:
        """Create session in episodic memory."""
        await self.episodic.create_session(
            session_id=session_id,
            agent_id=agent_id,
            entity_id=entity_id,
            user_id=user_id,
        )
    
    async def record_session_message(
        self,
        session_id: str,
        role: str,
        content: str,
        **kwargs: Any,
    ) -> None:
        """Record message in session."""
        await self.episodic.record_message(
            session_id=session_id,
            role=role,
            content=content,
            **kwargs,
        )
        
        # Also capture in BrainSys for AI context
        if role == "assistant":
            await self.brainsys.capture_context(
                content=content,
                context_type="analysis",
                source_session_id=session_id,
                importance=0.7,
            )
    
    async def end_session_memory(
        self,
        session_id: str,
        status: str = "completed",
    ) -> None:
        """End session in episodic memory."""
        await self.episodic.end_session(session_id, status)
    
    # =========================================================================
    # Statistics
    # =========================================================================
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get statistics from all memory layers."""
        return {
            "semantic": await self.semantic.get_stats(),
            "secondbrain": await self.secondbrain.get_stats(),
            "episodic": {},  # Could add more stats
            "brainsys": await self.brainsys.get_stats(),
        }


# Global orchestrator instance
_orchestrator: Optional[MemoryOrchestrator] = None


def get_memory_orchestrator(config: Optional[Dict[str, Any]] = None) -> MemoryOrchestrator:
    """Get or create global memory orchestrator."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = MemoryOrchestrator()
    return _orchestrator