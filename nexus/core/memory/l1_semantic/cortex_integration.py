"""
XenoSys Memory System - L1 Semantic Memory
Built on Cortex for semantic search and knowledge graphs.

Cortex: https://github.com/abbacusgroup/cortex
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
# Semantic Memory Types
# ============================================================================

@dataclass
class SemanticEntry:
    """A semantic memory entry with embedding."""
    id: UUID = field(default_factory=uuid4)
    content: str = ""
    embedding: Optional[List[float]] = None
    agent_id: Optional[str] = None
    entity_id: Optional[str] = None
    importance: float = 0.5
    created_at: datetime = field(default_factory=datetime.utcnow)
    accessed_at: Optional[datetime] = None
    access_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SemanticSearchResult:
    """Result from semantic search."""
    entry: SemanticEntry
    score: float  # Similarity score


# ============================================================================
# Cortex Integration Interface
# ============================================================================

class CortexClient:
    """
    Interface to Cortex for semantic memory operations.
    
    Cortex provides:
    - Vector embedding storage
    - Semantic similarity search
    - Knowledge graph operations
    - Multi-modal memory support
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.endpoint = self.config.get("endpoint", "http://localhost:8000")
        self.api_key = self.config.get("api_key", "")
        self.embedding_model = self.config.get("embedding_model", "sentence-transformers")
        self._connected = False
    
    async def connect(self) -> bool:
        """Connect to Cortex server."""
        try:
            # In production, would verify connectivity
            self._connected = True
            logger.info(f"Connected to Cortex at {self.endpoint}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Cortex: {e}")
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from Cortex."""
        self._connected = False
        logger.info("Disconnected from Cortex")
    
    async def create_collection(self, name: str, dimension: int = 384) -> bool:
        """Create a new collection for embeddings."""
        # Would call Cortex API
        logger.info(f"Creating collection: {name}")
        return True
    
    async def add_embedding(
        self,
        collection: str,
        entry: SemanticEntry,
    ) -> UUID:
        """Add embedding to Cortex."""
        # Would call Cortex API
        return entry.id
    
    async def search(
        self,
        collection: str,
        query: str,
        top_k: int = 10,
        filter_dict: Optional[Dict[str, Any]] = None,
    ) -> List[SemanticSearchResult]:
        """Search for similar embeddings."""
        # Would call Cortex API
        # Return mock results for now
        return []
    
    async def delete_entry(self, collection: str, entry_id: UUID) -> bool:
        """Delete an entry."""
        return True
    
    async def get_entry(self, collection: str, entry_id: UUID) -> Optional[SemanticEntry]:
        """Get a specific entry."""
        return None


# ============================================================================
# Semantic Memory Store
# ============================================================================

class SemanticMemoryStore:
    """
    L1 Semantic Memory using Cortex for storage and retrieval.
    
    Provides:
    - Vector embedding storage
    - Semantic similarity search
    - Agent-specific memory namespaces
    - Importance-based retention
    """
    
    def __init__(
        self,
        cortex_client: Optional[CortexClient] = None,
        default_collection: str = "xenosys_semantic",
    ):
        self.cortex = cortex_client or CortexClient()
        self.default_collection = default_collection
        self._local_cache: Dict[str, SemanticEntry] = {}
        self._lock = asyncio.Lock()
    
    async def initialize(self) -> bool:
        """Initialize the semantic memory store."""
        connected = await self.cortex.connect()
        if connected:
            await self.cortex.create_collection(self.default_collection)
        return connected
    
    async def store(
        self,
        content: str,
        agent_id: Optional[str] = None,
        entity_id: Optional[str] = None,
        importance: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> UUID:
        """Store a semantic memory entry."""
        entry = SemanticEntry(
            content=content,
            agent_id=agent_id,
            entity_id=entity_id,
            importance=importance,
            metadata=metadata or {},
        )
        
        # Generate embedding (placeholder - would use actual embedding model)
        entry.embedding = await self._generate_embedding(content)
        
        # Store in Cortex
        await self.cortex.add_embedding(self.default_collection, entry)
        
        # Cache locally
        async with self._lock:
            self._local_cache[str(entry.id)] = entry
        
        logger.info(f"Stored semantic entry: {entry.id}")
        return entry.id
    
    async def retrieve(
        self,
        entry_id: UUID,
    ) -> Optional[SemanticEntry]:
        """Retrieve a specific semantic entry."""
        # Check cache first
        async with self._lock:
            entry = self._local_cache.get(str(entry_id))
        
        if entry:
            entry.accessed_at = datetime.utcnow()
            entry.access_count += 1
            return entry
        
        # Would fetch from Cortex
        return None
    
    async def search(
        self,
        query: str,
        agent_id: Optional[str] = None,
        entity_id: Optional[str] = None,
        top_k: int = 10,
    ) -> List[SemanticSearchResult]:
        """Search semantic memory for relevant content."""
        # Apply filters
        filters = {}
        if agent_id:
            filters["agent_id"] = agent_id
        if entity_id:
            filters["entity_id"] = entity_id
        
        # Search Cortex
        results = await self.cortex.search(
            collection=self.default_collection,
            query=query,
            top_k=top_k,
            filter_dict=filters if filters else None,
        )
        
        logger.info(f"Semantic search returned {len(results)} results")
        return results
    
    async def get_agent_memories(
        self,
        agent_id: str,
        limit: int = 100,
    ) -> List[SemanticEntry]:
        """Get all memories for a specific agent."""
        # Would query from Cortex
        return []
    
    async def delete(
        self,
        entry_id: UUID,
    ) -> bool:
        """Delete a semantic entry."""
        await self.cortex.delete_entry(self.default_collection, entry_id)
        
        async with self._lock:
            self._local_cache.pop(str(entry_id), None)
        
        return True
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        async with self._lock:
            return {
                "cached_entries": len(self._local_cache),
                "collection": self.default_collection,
                "connected": self.cortex._connected,
            }
    
    async def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text."""
        # Placeholder - would use sentence-transformers
        # In production: model.encode(text).tolist()
        import hashlib
        # Deterministic mock embedding based on text hash
        h = hashlib.sha256(text.encode()).digest()
        # Convert to list of floats (truncated to 384 dims)
        return [float(b) / 255.0 for b in h[:384]]


# ============================================================================
# Memory Vault (Agent-specific namespace)
# ============================================================================

class MemoryVault:
    """
    A named collection of semantic memories for an agent or entity.
    Provides namespacing and access control.
    """
    
    def __init__(
        self,
        vault_id: str,
        name: str,
        owner_id: str,  # Agent or Entity ID
        store: Optional[SemanticMemoryStore] = None,
    ):
        self.vault_id = vault_id
        self.name = name
        self.owner_id = owner_id
        self.store = store or _global_semantic_store
    
    async def add_memory(
        self,
        content: str,
        importance: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> UUID:
        """Add memory to this vault."""
        return await self.store.store(
            content=content,
            agent_id=self.owner_id,
            importance=importance,
            metadata=metadata,
        )
    
    async def search(self, query: str, top_k: int = 10) -> List[SemanticSearchResult]:
        """Search within this vault."""
        return await self.store.search(
            query=query,
            agent_id=self.owner_id,
            top_k=top_k,
        )
    
    async def get_all(self, limit: int = 100) -> List[SemanticEntry]:
        """Get all memories in this vault."""
        return await self.store.get_agent_memories(
            agent_id=self.owner_id,
            limit=limit,
        )


# Global semantic store instance
_global_semantic_store: Optional[SemanticMemoryStore] = None


def get_semantic_store(config: Optional[Dict[str, Any]] = None) -> SemanticMemoryStore:
    """Get or create global semantic store."""
    global _global_semantic_store
    if _global_semantic_store is None:
        _global_semantic_store = SemanticMemoryStore(
            cortex_client=CortexClient(config) if config else None
        )
    return _global_semantic_store