"""
XenoSys Agents Module
Multi-agent system with adversarial pairing and metacognition.
"""

from .base_agent import (
    Agent,
    AgentRole,
    AgentState,
    AgentType,
    AgentMessage,
    AgentRequest,
    AgentResponse,
    Tool,
    ToolCall,
    ToolRegistry,
    tool_registry,
    OrchestratorAgent,
    ReflectorAgent,
    AdversarialAgent,
    MessageRole,
)

from .registry import (
    AgentRepository,
    agent_repository,
    AgentFactory,
    AgentRegistry,
    agent_registry,
)

__all__ = [
    # Types
    "Agent",
    "AgentRole",
    "AgentState",
    "AgentType",
    "AgentMessage",
    "AgentRequest",
    "AgentResponse",
    "Tool",
    "ToolCall",
    "ToolRegistry",
    "tool_registry",
    "MessageRole",
    # Specialized Agents
    "OrchestratorAgent",
    "ReflectorAgent",
    "AdversarialAgent",
    # Registry
    "AgentRepository",
    "agent_repository",
    "AgentFactory",
    "AgentRegistry",
    "agent_registry",
]