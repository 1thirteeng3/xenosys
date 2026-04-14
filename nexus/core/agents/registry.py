"""
XenoSys - Agent Registry Module
Manages agent lifecycle, storage, and discovery.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, List, Optional
from uuid import UUID, uuid4

from .base_agent import Agent, AgentRole, AgentState, AgentType

logger = logging.getLogger(__name__)


# ============================================================================
# Agent Repository
# ============================================================================

class AgentRepository:
    """
    Repository interface for agent persistence.
    
    In production, this would integrate with the database.
    For now, uses in-memory storage.
    """
    
    def __init__(self) -> None:
        self._agents: Dict[str, Agent] = {}
        self._lock = asyncio.Lock()
    
    async def save(self, agent: Agent) -> Agent:
        """Save agent to repository."""
        async with self._lock:
            self._agents[agent.agent_id] = agent
            logger.info(f"Saved agent: {agent.agent_id}")
        return agent
    
    async def get_by_id(self, agent_id: str) -> Optional[Agent]:
        """Retrieve agent by ID."""
        return self._agents.get(agent_id)
    
    async def get_by_type(self, agent_type: AgentType) -> List[Agent]:
        """Get all agents of a specific type."""
        return [a for a in self._agents.values() if a.agent_type == agent_type]
    
    async def get_by_role(self, role: AgentRole) -> List[Agent]:
        """Get all agents with a specific role."""
        return [a for a in self._agents.values() if a.role == role]
    
    async def delete(self, agent_id: str) -> bool:
        """Soft delete an agent."""
        async with self._lock:
            if agent_id in self._agents:
                agent = self._agents[agent_id]
                # Mark as inactive rather than deleting
                agent.is_active = False
                logger.info(f"Deactivated agent: {agent_id}")
                return True
        return False
    
    async def list_all(self) -> List[Agent]:
        """List all agents."""
        return list(self._agents.values())
    
    async def list_active(self) -> List[Agent]:
        """List all active agents."""
        return [a for a in self._agents.values() if getattr(a, 'is_active', True)]


# Global registry instance
agent_repository = AgentRepository()


# ============================================================================
# Agent Factory
# ============================================================================

class AgentFactory:
    """
    Factory for creating agents with proper configuration.
    """
    
    @staticmethod
    def create_executor(
        name: str,
        system_prompt: str,
        tools: Optional[List[str]] = None,
        llm_config: Optional[Dict[str, Any]] = None,
    ) -> Agent:
        """Create an executor agent."""
        return Agent(
            agent_id=str(uuid4()),
            role=AgentRole.EXECUTOR,
            agent_type=AgentType.EXECUTOR,
            name=name,
            system_prompt=system_prompt,
            tools=tools,
            llm_config=llm_config,
        )
    
    @staticmethod
    def create_critic(
        name: str,
        system_prompt: str,
        target_agent_id: str,
        llm_config: Optional[Dict[str, Any]] = None,
    ) -> Agent:
        """Create a critic/auditor agent."""
        from .base_agent import AdversarialAgent
        return AdversarialAgent(
            agent_id=str(uuid4()),
            role=AgentRole.REFLECTOR,
            agent_type=AgentType.CRITIC,
            name=name,
            system_prompt=system_prompt,
            target_agent_id=target_agent_id,
            llm_config=llm_config,
        )
    
    @staticmethod
    def create_orchestrator(
        name: str,
        system_prompt: str,
        llm_config: Optional[Dict[str, Any]] = None,
    ) -> Agent:
        """Create an orchestrator agent."""
        from .base_agent import OrchestratorAgent
        return OrchestratorAgent(
            agent_id=str(uuid4()),
            role=AgentRole.ORCHESTRATOR,
            agent_type=AgentType.HYBRID,
            name=name,
            system_prompt=system_prompt,
            llm_config=llm_config,
        )
    
    @staticmethod
    def create_reflector(
        name: str,
        system_prompt: str,
        llm_config: Optional[Dict[str, Any]] = None,
    ) -> Agent:
        """Create a reflector/metacognitive agent."""
        from .base_agent import ReflectorAgent
        return ReflectorAgent(
            agent_id=str(uuid4()),
            role=AgentRole.REFLECTOR,
            agent_type=AgentType.CRITIC,
            name=name,
            system_prompt=system_prompt,
            llm_config=llm_config,
        )


# ============================================================================
# Agent Registry Service
# ============================================================================

class AgentRegistry:
    """
    Service for managing agent lifecycle and operations.
    """
    
    def __init__(self, repository: Optional[AgentRepository] = None) -> None:
        self.repository = repository or agent_repository
        self._event_handlers: Dict[str, List[Callable]] = {}
    
    async def register(self, agent: Agent) -> Agent:
        """Register a new agent."""
        await self.repository.save(agent)
        await self._publish_event("agent_registered", agent)
        return agent
    
    async def unregister(self, agent_id: str) -> bool:
        """Unregister an agent."""
        result = await self.repository.delete(agent_id)
        if result:
            await self._publish_event("agent_unregistered", {"agent_id": agent_id})
        return result
    
    async def get(self, agent_id: str) -> Optional[Agent]:
        """Get agent by ID."""
        return await self.repository.get_by_id(agent_id)
    
    async def list_agents(
        self,
        agent_type: Optional[AgentType] = None,
        role: Optional[AgentRole] = None,
        active_only: bool = True,
    ) -> List[Agent]:
        """List agents with optional filters."""
        if agent_type:
            return await self.repository.get_by_type(agent_type)
        elif role:
            return await self.repository.get_by_role(role)
        elif active_only:
            return await self.repository.list_active()
        return await self.repository.list_all()
    
    async def create_and_register(
        self,
        agent_type: str,
        name: str,
        system_prompt: str,
        **kwargs: Any,
    ) -> Agent:
        """Create and register an agent in one operation."""
        if agent_type == "executor":
            agent = AgentFactory.create_executor(name, system_prompt, **kwargs)
        elif agent_type == "critic":
            agent = AgentFactory.create_critic(name, system_prompt, **kwargs)
        elif agent_type == "orchestrator":
            agent = AgentFactory.create_orchestrator(name, system_prompt, **kwargs)
        elif agent_type == "reflector":
            agent = AgentFactory.create_reflector(name, system_prompt, **kwargs)
        else:
            raise ValueError(f"Unknown agent type: {agent_type}")
        
        return await self.register(agent)
    
    async def get_or_create_adversarial_pair(
        self,
        executor_id: str,
    ) -> tuple[Agent, Agent]:
        """Get or create an adversarial pair for an executor."""
        executor = await self.get(executor_id)
        if not executor:
            raise ValueError(f"Executor not found: {executor_id}")
        
        # Look for existing critic
        existing_critics = await self.repository.get_by_type(AgentType.CRITIC)
        critic = next(
            (c for c in existing_critics 
             if getattr(c, 'target_agent_id', None) == executor_id),
            None
        )
        
        if not critic:
            # Create new critic
            critic = AgentFactory.create_critic(
                name=f"Critic for {executor.name}",
                system_prompt=self._get_critic_system_prompt(),
                target_agent_id=executor_id,
            )
            await self.register(critic)
        
        return executor, critic
    
    def _get_critic_system_prompt(self) -> str:
        """Get default critic system prompt."""
        return """You are a critical auditor agent. Your role is to:
1. Evaluate executor agent outputs for correctness
2. Check for hallucinations or factual errors
3. Verify compliance with policies
4. Suggest improvements
Provide constructive feedback and identify any issues."""
    
    def subscribe(self, event: str, handler: Callable) -> None:
        """Subscribe to registry events."""
        if event not in self._event_handlers:
            self._event_handlers[event] = []
        self._event_handlers[event].append(handler)
    
    async def _publish_event(self, event: str, data: Any) -> None:
        """Publish event to handlers."""
        handlers = self._event_handlers.get(event, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(data)
                else:
                    handler(data)
            except Exception as e:
                logger.error(f"Event handler error: {e}")


# Global registry instance
agent_registry = AgentRegistry()