"""
XenoSys Entities Module
Multi-agent composition into single entities with routing.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


# ============================================================================
# Entity Types
# ============================================================================

class RoutingStrategy(str, Enum):
    """Entity routing strategies."""
    SEMANTIC = "semantic"    # Embedding similarity to agent expertise
    SEQUENTIAL = "sequential" # Round-robin through agents
    PARALLEL = "parallel"     # All agents, aggregate results


@dataclass
class Entity:
    """An entity (composed multi-agent)."""
    id: UUID = field(default_factory=uuid4)
    name: str = ""
    description: str = ""
    agent_ids: List[str] = field(default_factory=list)
    routing_strategy: RoutingStrategy = RoutingStrategy.SEMANTIC
    max_rounds: int = 3
    memory_config: Dict[str, Any] = field(default_factory=dict)  # L1/L2/L3 bindings
    is_active: bool = True
    created_by: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class EntityExecutionResult:
    """Result of entity execution."""
    entity_id: UUID
    session_id: str
    content: str
    iterations: int
    agents_used: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Entity Builder
# ============================================================================

class EntityBuilder:
    """
    DSL for building entities.
    
    Usage:
        entity = (EntityBuilder("Senior Developer")
            .add_agent("python_expert")
            .add_agent("ts_expert")
            .with_adversarial_pair()
            .with_routing(RoutingStrategy.SEMANTIC)
            .with_memory("python_vault", "projects/python")
            .build())
    """
    
    def __init__(self, name: str):
        self._name = name
        self._description = ""
        self._agent_ids: List[str] = []
        self._routing = RoutingStrategy.SEMANTIC
        self._max_rounds = 3
        self._memory_config: Dict[str, Any] = {}
        self._adversarial = False
    
    def description(self, desc: str) -> "EntityBuilder":
        """Set entity description."""
        self._description = desc
        return self
    
    def add_agent(self, agent_id: str) -> "EntityBuilder":
        """Add an agent to the entity."""
        self._agent_ids.append(agent_id)
        return self
    
    def add_agents(self, *agent_ids: str) -> "EntityBuilder":
        """Add multiple agents."""
        self._agent_ids.extend(agent_ids)
        return self
    
    def with_routing(self, strategy: RoutingStrategy) -> "EntityBuilder":
        """Set routing strategy."""
        self._routing = strategy
        return self
    
    def with_max_rounds(self, rounds: int) -> "EntityBuilder":
        """Set maximum rounds."""
        self._max_rounds = rounds
        return self
    
    def with_memory(
        self,
        l1_vault: Optional[str] = None,
        l2_path: Optional[str] = None,
        l3_prefix: Optional[str] = None,
    ) -> "EntityBuilder":
        """Set memory configuration."""
        self._memory_config = {
            "l1": l1_vault,
            "l2": l2_path,
            "l3": l3_prefix,
        }
        return self
    
    def with_adversarial_pair(self) -> "EntityBuilder":
        """Add adversarial pairing to all agents."""
        self._adversarial = True
        return self
    
    def build(self, created_by: str = "system") -> Entity:
        """Build the entity."""
        entity = Entity(
            name=self._name,
            description=self._description,
            agent_ids=self._agent_ids,
            routing_strategy=self._routing,
            max_rounds=self._max_rounds,
            memory_config=self._memory_config,
            created_by=created_by,
        )
        
        # Store adversarial flag in memory config for runtime
        if self._adversarial:
            entity.memory_config["_adversarial"] = True
        
        logger.info(f"Built entity: {entity.name} ({len(entity.agent_ids)} agents, adversarial={self._adversarial})")
        return entity
    
    def build_with_critic(self, executor_agent: Agent, critic_system_prompt: str) -> tuple[Agent, Agent]:
        """
        Build executor + critic pair for adversarial execution.
        
        Returns a tuple of (executor, critic) that can be used together.
        """
        from ..agents.base_agent import AdversarialAgent
        
        # Create critic for the executor
        critic = AdversarialAgent(
            agent_id=str(uuid4()),
            role=AgentRole.REFLECTOR,
            agent_type=AgentType.CRITIC,
            name=f"Critic for {executor_agent.name}",
            system_prompt=critic_system_prompt or self._get_default_critic_prompt(),
            target_agent_id=executor_agent.agent_id,
        )
        
        logger.info(f"Built adversarial pair: {executor_agent.name} <-> {critic.name}")
        return executor_agent, critic
    
    def _get_default_critic_prompt(self) -> str:
        """Get default critic system prompt."""
        return """You are a critical auditor agent. Your role is to:
1. Evaluate executor agent outputs for correctness
2. Check for hallucinations or factual errors
3. Verify compliance with policies
4. Suggest improvements
Provide constructive feedback and identify any issues.
Be adversarial but fair - challenge assumptions but acknowledge good work."""


# ============================================================================
# Entity Repository
# ============================================================================

class EntityRepository:
    """
    Repository for entity persistence.
    """
    
    def __init__(self):
        self._entities: Dict[str, Entity] = {}
        self._lock = asyncio.Lock()
    
    async def save(self, entity: Entity) -> Entity:
        """Save entity."""
        async with self._lock:
            self._entities[str(entity.id)] = entity
        logger.info(f"Saved entity: {entity.name}")
        return entity
    
    async def get(self, entity_id: UUID) -> Optional[Entity]:
        """Get entity by ID."""
        return self._entities.get(str(entity_id))
    
    async def get_by_name(self, name: str) -> Optional[Entity]:
        """Get entity by name."""
        for entity in self._entities.values():
            if entity.name == name:
                return entity
        return None
    
    async def list_entities(
        self,
        active_only: bool = True,
    ) -> List[Entity]:
        """List all entities."""
        entities = list(self._entities.values())
        if active_only:
            entities = [e for e in entities if e.is_active]
        return sorted(entities, key=lambda e: e.created_at, reverse=True)
    
    async def delete(self, entity_id: UUID) -> bool:
        """Soft delete entity."""
        async with self._lock:
            entity = self._entities.get(str(entity_id))
            if entity:
                entity.is_active = False
                return True
        return False


# ============================================================================
# Entity Router
# ============================================================================

class EntityRouter:
    """
    Route requests to appropriate agents within an entity.
    """
    
    def __init__(self, entity_repo: Optional[EntityRepository] = None):
        self.entity_repo = entity_repo or EntityRepository()
    
    async def route(
        self,
        entity_id: UUID,
        message: str,
        available_agents: Dict[str, Any],  # agent_id -> agent
    ) -> List[str]:
        """Route message to agents based on strategy."""
        entity = await self.entity_repo.get(entity_id)
        if not entity:
            return []
        
        if entity.routing_strategy == RoutingStrategy.SEMANTIC:
            return await self._semantic_route(entity, message, available_agents)
        elif entity.routing_strategy == RoutingStrategy.SEQUENTIAL:
            return await self._sequential_route(entity, available_agents)
        elif entity.routing_strategy == RoutingStrategy.PARALLEL:
            return entity.agent_ids
        
        return entity.agent_ids[:1]  # Default to first
    
    async def _semantic_route(
        self,
        entity: Entity,
        message: str,
        available_agents: Dict[str, Any],
    ) -> List[str]:
        """Semantic routing based on message content."""
        # In production, would use embedding similarity
        # For demo, just return first agent
        return entity.agent_ids[:1]
    
    async def _sequential_route(
        self,
        entity: Entity,
        available_agents: Dict[str, Any],
    ) -> List[str]:
        """Sequential routing (round-robin)."""
        return entity.agent_ids


# ============================================================================
# Entity Runtime
# ============================================================================

class EntityRuntime:
    """
    Runtime for executing entities.
    """
    
    def __init__(
        self,
        entity_repo: Optional[EntityRepository] = None,
        router: Optional[EntityRouter] = None,
    ):
        self.entity_repo = entity_repo or EntityRepository()
        self.router = router or EntityRouter(self.entity_repo)
    
    async def execute(
        self,
        entity_id: UUID,
        session_id: str,
        message: str,
        agent_executor,  # Function to execute an agent
    ) -> EntityExecutionResult:
        """Execute an entity."""
        entity = await self.entity_repo.get(entity_id)
        if not entity:
            raise ValueError(f"Entity not found: {entity_id}")
        
        agents_used = []
        
        # Route to agents
        # In production, would have actual agent map
        agent_ids = await self.router.route(entity_id, message, {})
        
        # Execute each agent
        results = []
        for agent_id in agent_ids:
            if len(results) >= entity.max_rounds:
                break
            
            # Execute agent (placeholder)
            # result = await agent_executor(agent_id, message)
            # results.append(result)
            agents_used.append(agent_id)
        
        # Aggregate results
        content = f"Entity {entity.name} executed with {len(agents_used)} agents"
        
        return EntityExecutionResult(
            entity_id=entity_id,
            session_id=session_id,
            content=content,
            iterations=len(agents_used),
            agents_used=agents_used,
            metadata={"entity": entity.name},
        )


# Global instances
_entity_repo = EntityRepository()
_entity_router = EntityRouter(_entity_repo)
_entity_runtime = EntityRuntime(_entity_repo, _entity_router)


def get_entity_repo() -> EntityRepository:
    return _entity_repo


def get_entity_router() -> EntityRouter:
    return _entity_router


def get_entity_runtime() -> EntityRuntime:
    return _entity_runtime