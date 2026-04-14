"""
XenoSys Learning Engine - LoRA Module
LoRA adapter registry and hot-swap mechanism.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


# ============================================================================
# LoRA Types
# ============================================================================

@dataclass
class LoRAAdapter:
    """A LoRA adapter configuration."""
    id: UUID = field(default_factory=uuid4)
    name: str = ""
    model_base: str = ""  # base model (e.g., llama-2-7b)
    file_path: str = ""  # path to adapter weights
    version: int = 1
    accuracy_score: Optional[float] = None
    training_dataset_id: Optional[str] = None
    trained_at: Optional[datetime] = None
    is_active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class LoRASwapResult:
    """Result of a LoRA adapter swap."""
    success: bool
    old_adapter_id: Optional[UUID]
    new_adapter_id: UUID
    duration_ms: int
    error: Optional[str] = None


# ============================================================================
# LoRA Registry
# ============================================================================

class LoRARegistry:
    """
    Registry for LoRA adapters.
    
    Provides:
    - Adapter CRUD operations
    - Version management
    - Hot-swap capability
    - Performance tracking
    """
    
    def __init__(self, storage_path: str = "./lora_adapters"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self._adapters: Dict[str, LoRAAdapter] = {}
        self._active_per_agent: Dict[str, UUID] = {}  # agent_id -> adapter_id
        self._lock = asyncio.Lock()
    
    # =========================================================================
    # Registry Operations
    # =========================================================================
    
    async def register(
        self,
        name: str,
        model_base: str,
        file_path: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> LoRAAdapter:
        """Register a new LoRA adapter."""
        adapter = LoRAAdapter(
            name=name,
            model_base=model_base,
            file_path=file_path,
            metadata=metadata or {},
        )
        
        async with self._lock:
            self._adapters[str(adapter.id)] = adapter
        
        logger.info(f"Registered LoRA adapter: {adapter.name} ({adapter.id})")
        return adapter
    
    async def get(self, adapter_id: UUID) -> Optional[LoRAAdapter]:
        """Get an adapter by ID."""
        async with self._lock:
            return self._adapters.get(str(adapter_id))
    
    async def get_by_name(self, name: str) -> Optional[LoRAAdapter]:
        """Get an adapter by name."""
        async with self._lock:
            for adapter in self._adapters.values():
                if adapter.name == name:
                    return adapter
        return None
    
    async def list_adapters(
        self,
        model_base: Optional[str] = None,
        active_only: bool = True,
    ) -> List[LoRAAdapter]:
        """List adapters with optional filters."""
        async with self._lock:
            adapters = list(self._adapters.values())
        
        if model_base:
            adapters = [a for a in adapters if a.model_base == model_base]
        if active_only:
            adapters = [a for a in adapters if a.is_active]
        
        return sorted(adapters, key=lambda a: a.created_at, reverse=True)
    
    async def deactivate(self, adapter_id: UUID) -> bool:
        """Deactivate an adapter."""
        async with self._lock:
            adapter = self._adapters.get(str(adapter_id))
            if adapter:
                adapter.is_active = False
                return True
        return False
    
    # =========================================================================
    # Hot-Swap Operations
    # =========================================================================
    
    async def swap(
        self,
        agent_id: str,
        new_adapter_id: UUID,
    ) -> LoRASwapResult:
        """Hot-swap adapter for an agent."""
        start_time = datetime.utcnow()
        
        # Get old adapter
        old_adapter_id = self._active_per_agent.get(agent_id)
        
        # Get new adapter
        new_adapter = await self.get(new_adapter_id)
        if not new_adapter:
            return LoRASwapResult(
                success=False,
                old_adapter_id=old_adapter_id,
                new_adapter_id=new_adapter_id,
                duration_ms=0,
                error="Adapter not found",
            )
        
        if not new_adapter.is_active:
            return LoRASwapResult(
                success=False,
                old_adapter_id=old_adapter_id,
                new_adapter_id=new_adapter_id,
                duration_ms=0,
                error="Adapter is not active",
            )
        
        try:
            # In production, would actually load/unload the adapter
            # For demo, just update the mapping
            await asyncio.sleep(0.1)  # Simulate load time
            
            async with self._lock:
                self._active_per_agent[agent_id] = new_adapter_id
            
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            logger.info(f"Swapped LoRA adapter for agent {agent_id}: {old_adapter_id} -> {new_adapter_id}")
            
            return LoRASwapResult(
                success=True,
                old_adapter_id=old_adapter_id,
                new_adapter_id=new_adapter_id,
                duration_ms=duration_ms,
            )
            
        except Exception as e:
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            return LoRASwapResult(
                success=False,
                old_adapter_id=old_adapter_id,
                new_adapter_id=new_adapter_id,
                duration_ms=duration_ms,
                error=str(e),
            )
    
    async def get_active_adapter(self, agent_id: str) -> Optional[LoRAAdapter]:
        """Get the active adapter for an agent."""
        adapter_id = self._active_per_agent.get(agent_id)
        if adapter_id:
            return await self.get(adapter_id)
        return None
    
    async def unload_agent(self, agent_id: str) -> bool:
        """Unload adapter from an agent."""
        async with self._lock:
            if agent_id in self._active_per_agent:
                del self._active_per_agent[agent_id]
                return True
        return False
    
    # =========================================================================
    # Version Management
    # =========================================================================
    
    async def create_version(
        self,
        base_adapter_id: UUID,
        file_path: str,
        accuracy_score: Optional[float] = None,
    ) -> Optional[LoRAAdapter]:
        """Create a new version of an adapter."""
        base = await self.get(base_adapter_id)
        if not base:
            return None
        
        new_version = LoRAAdapter(
            name=base.name,
            model_base=base.model_base,
            file_path=file_path,
            version=base.version + 1,
            accuracy_score=accuracy_score,
            trained_at=datetime.utcnow(),
        )
        
        async with self._lock:
            self._adapters[str(new_version.id)] = new_version
        
        return new_version
    
    # =========================================================================
    # Statistics
    # =========================================================================
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        adapters = list(self._adapters.values())
        
        by_model: Dict[str, int] = {}
        for a in adapters:
            by_model[a.model_base] = by_model.get(a.model_base, 0) + 1
        
        return {
            "total_adapters": len(adapters),
            "active_adapters": len([a for a in adapters if a.is_active]),
            "by_model": by_model,
            "agents_with_adapters": len(self._active_per_agent),
        }


# Global registry instance
_lora_registry: Optional[LoRARegistry] = None


def get_lora_registry(storage_path: str = "./lora_adapters") -> LoRARegistry:
    """Get or create global LoRA registry."""
    global _lora_registry
    if _lora_registry is None:
        _lora_registry = LoRARegistry(storage_path)
    return _lora_registry