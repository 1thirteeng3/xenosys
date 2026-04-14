"""
XenoSys Core - Agent System
Multi-agent orchestration with metacognitive capabilities
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Awaitable, Callable
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ============================================================================
# Agent Types
# ============================================================================

class AgentRole(str, Enum):
    """Agent role definitions."""
    ORCHESTRATOR = "orchestrator"
    EXECUTOR = "executor"
    PLANNER = "planner"
    ANALYZER = "analyzer"
    REFLECTOR = "reflector"
    SPECIALIST = "specialist"


class AgentState(str, Enum):
    """Agent lifecycle states."""
    IDLE = "idle"
    THINKING = "thinking"
    ACTING = "acting"
    WAITING_TOOL = "waiting_tool"
    WAITING_HITL = "waiting_hitl"
    COMPLETED = "completed"
    FAILED = "failed"


class MessageRole(str, Enum):
    """Message roles in agent对话."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class ToolCall:
    """A tool call made by an agent."""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)
    result: str | None = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    approved: bool | None = None  # For HITL


@dataclass
class AgentMessage:
    """A message in agent对话."""
    id: str = field(default_factory=str(uuid4))
    role: MessageRole = MessageRole.USER
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_results: list[ToolCall] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentRequest:
    """Request to run an agent."""
    session_id: str
    user_id: str
    message: str
    agent_id: str | None = None
    context: dict[str, Any] = field(default_factory=dict)
    max_iterations: int = 10
    timeout_seconds: float = 300.0
    temperature: float | None = None
    system_prompt: str | None = None


@dataclass
class AgentResponse:
    """Response from an agent."""
    session_id: str
    message_id: str
    content: str
    done: bool = True
    iterations: int = 0
    tool_calls: list[ToolCall] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


# ============================================================================
# Tool System
# ============================================================================

class Tool(ABC):
    """Base class for agent tools."""
    
    name: str = ""
    description: str = ""
    parameters: dict[str, Any] = {}
    requires_approval: bool = False  # HITL requirement
    
    @abstractmethod
    async def execute(self, **kwargs: Any) -> str:
        """Execute the tool and return result."""
        pass
    
    def validate(self, **kwargs: Any) -> bool:
        """Validate tool parameters."""
        return True


class ToolRegistry:
    """Registry for available tools."""
    
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}
        self._toolsets: dict[str, set[str]] = {}  # toolset -> tool names
    
    def register(self, tool: Tool, toolsets: list[str] | None = None) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool
        if toolsets:
            for ts in toolsets:
                if ts not in self._toolsets:
                    self._toolsets[ts] = set()
                self._toolsets[ts].add(tool.name)
        logger.info(f"Registered tool: {tool.name}")
    
    def unregister(self, name: str) -> bool:
        """Unregister a tool."""
        if name in self._tools:
            del self._tools[name]
            for ts in self._toolsets:
                self._toolsets[ts].discard(name)
            return True
        return False
    
    def get(self, name: str) -> Tool | None:
        """Get a tool by name."""
        return self._tools.get(name)
    
    def list_tools(self, toolset: str | None = None) -> list[str]:
        """List available tool names."""
        if toolset:
            return list(self._toolsets.get(toolset, set()))
        return list(self._tools.keys())
    
    def get_tools_for_agent(self, agent_id: str) -> list[Tool]:
        """Get tools available for an agent (placeholder for ACL)."""
        return list(self._tools.values())


# Global registry
tool_registry = ToolRegistry()


# ============================================================================
# Agent Base Class
# ============================================================================

class Agent(ABC):
    """
    Base class for XenoSys agents.
    
    Provides:
    - Message history management
    - Tool execution with HITL support
    - State machine transitions
    - Logging and tracing
    """
    
    def __init__(
        self,
        agent_id: str,
        role: AgentRole,
        name: str | None = None,
        description: str | None = None,
        system_prompt: str | None = None,
        tools: list[str] | None = None,
        llm_config: dict[str, Any] | None = None,
    ) -> None:
        self.agent_id = agent_id
        self.role = role
        self.name = name or agent_id
        self.description = description or ""
        self.system_prompt = system_prompt or ""
        self.tools = tools or []
        self.llm_config = llm_config or {}
        
        # State
        self.state = AgentState.IDLE
        self.messages: list[AgentMessage] = []
        self.current_tool_call: ToolCall | None = None
        
        # Metacognitive state
        self.iteration_count = 0
        self.thought_history: list[str] = []
        
    async def think(self, request: AgentRequest) -> AgentMessage:
        """
        Think phase - generate next action.
        
        Override this method to implement custom reasoning.
        """
        # Build context
        context = self._build_context(request)
        
        # Call LLM (placeholder - actual implementation uses DSPy)
        response = await self._call_llm(context)
        
        # Parse response
        message = AgentMessage(
            role=MessageRole.ASSISTANT,
            content=response["content"],
            tool_calls=self._parse_tool_calls(response.get("tool_calls", [])),
        )
        
        return message
    
    async def act(self, message: AgentMessage) -> AgentMessage:
        """
        Act phase - execute planned action.
        
        Can involve tool execution or direct response.
        """
        if message.tool_calls:
            # Execute tools
            for tool_call in message.tool_calls:
                await self._execute_tool(tool_call)
                message.tool_results.append(tool_call)
        else:
            # Direct response - no action needed
            pass
        
        return message
    
    async def observe(self, result: AgentMessage) -> None:
        """
        Observe phase - process results and update state.
        
        Used for metacognitive reflection.
        """
        self.messages.append(result)
        self.thought_history.append(result.content[:200])  # Truncate for history
    
    async def run(self, request: AgentRequest) -> AgentResponse:
        """
        Main agent execution loop (ReAct pattern).
        
        Think -> Act -> Observe -> repeat
        """
        self.state = AgentState.THINKING
        self.iteration_count = 0
        
        try:
            # System message
            if request.system_prompt:
                self.messages.append(AgentMessage(
                    role=MessageRole.SYSTEM,
                    content=request.system_prompt,
                ))
            
            # User message
            self.messages.append(AgentMessage(
                role=MessageRole.USER,
                content=request.message,
            ))
            
            # Main loop
            while self.iteration_count < request.max_iterations:
                self.iteration_count += 1
                
                # THINK
                self.state = AgentState.THINKING
                thought = await self.think(request)
                self.messages.append(thought)
                
                # Check for completion
                if not thought.tool_calls:
                    # Direct response
                    self.state = AgentState.COMPLETED
                    return AgentResponse(
                        session_id=request.session_id,
                        message_id=str(uuid4()),
                        content=thought.content,
                        done=True,
                        iterations=self.iteration_count,
                        tool_calls=thought.tool_calls,
                    )
                
                # ACT
                self.state = AgentState.ACTING
                for tool_call in thought.tool_calls:
                    if tool_call.name == "final_answer":
                        self.state = AgentState.COMPLETED
                        return AgentResponse(
                            session_id=request.session_id,
                            message_id=str(uuid4()),
                            content=tool_call.arguments.get("answer", ""),
                            done=True,
                            iterations=self.iteration_count,
                        )
                    
                    await self._execute_tool(tool_call)
                    thought.tool_results.append(tool_call)
                    
                    if tool_call.error:
                        logger.warning(f"Tool {tool_call.name} failed: {tool_call.error}")
                
                # OBSERVE
                self.state = AgentState.WAITING_TOOL
                await self.observe(thought)
            
            # Max iterations reached
            self.state = AgentState.COMPLETED
            return AgentResponse(
                session_id=request.session_id,
                message_id=str(uuid4()),
                content="Max iterations reached without final answer.",
                done=True,
                iterations=self.iteration_count,
            )
            
        except Exception as e:
            self.state = AgentState.FAILED
            logger.error(f"Agent {self.agent_id} failed: {e}", exc_info=True)
            return AgentResponse(
                session_id=request.session_id,
                message_id=str(uuid4()),
                content="",
                done=True,
                iterations=self.iteration_count,
                error=str(e),
            )
        finally:
            self._reset()
    
    async def _execute_tool(self, tool_call: ToolCall) -> None:
        """Execute a tool call."""
        tool_call.started_at = datetime.utcnow()
        
        tool = tool_registry.get(tool_call.name)
        if not tool:
            tool_call.error = f"Unknown tool: {tool_call.name}"
            return
        
        try:
            # Check if approval needed
            if tool.requires_approval:
                self.state = AgentState.WAITING_HITL
                # Signal HITL (implementation depends on integration)
                approved = await self._request_approval(tool_call)
                if not approved:
                    tool_call.approved = False
                    tool_call.error = "Tool execution rejected by human"
                    return
                tool_call.approved = True
            
            # Execute
            self.state = AgentState.ACTING
            result = await tool.execute(**tool_call.arguments)
            tool_call.result = result
            
        except Exception as e:
            tool_call.error = str(e)
            
        finally:
            tool_call.completed_at = datetime.utcnow()
    
    async def _request_approval(self, tool_call: ToolCall) -> bool:
        """Request human approval for tool execution."""
        # This would integrate with HITL system
        # For now, auto-approve
        return True
    
    async def _call_llm(self, context: list[dict[str, Any]]) -> dict[str, Any]:
        """Call LLM with context. Placeholder for DSPy integration."""
        # In production, this uses DSPy with configured LLM
        return {
            "content": "This is a placeholder response.",
            "tool_calls": [],
        }
    
    def _build_context(self, request: AgentRequest) -> list[dict[str, Any]]:
        """Build context for LLM call."""
        messages = [
            {"role": "system", "content": self.system_prompt},
        ]
        
        # Include memory context if available
        if request.context.get("memory"):
            messages.append({
                "role": "system",
                "content": f"Relevant memory:\n{request.context['memory']}"
            })
        
        # Include recent messages
        for msg in self.messages[-10:]:
            role = "assistant" if msg.role == MessageRole.ASSISTANT else "user"
            messages.append({"role": role, "content": msg.content})
        
        return messages
    
    def _parse_tool_calls(self, raw_calls: list[dict[str, Any]]) -> list[ToolCall]:
        """Parse tool calls from LLM response."""
        calls = []
        for raw in raw_calls:
            calls.append(ToolCall(
                name=raw.get("name", ""),
                arguments=raw.get("arguments", {}),
            ))
        return calls
    
    def _reset(self) -> None:
        """Reset agent state after run."""
        self.messages.clear()
        self.current_tool_call = None
        self.thought_history.clear()
    
    def get_state(self) -> dict[str, Any]:
        """Get current agent state."""
        return {
            "agent_id": self.agent_id,
            "role": self.role.value,
            "state": self.state.value,
            "iteration_count": self.iteration_count,
            "message_count": len(self.messages),
        }


# ============================================================================
# Specialized Agents
# ============================================================================

class OrchestratorAgent(Agent):
    """Main orchestrator that delegates to specialized agents."""
    
    def __init__(self, **kwargs: Any) -> None:
        kwargs["role"] = AgentRole.ORCHESTRATOR
        super().__init__(**kwargs)
        self.sub_agents: dict[str, Agent] = {}
    
    def register_agent(self, agent: Agent) -> None:
        """Register a sub-agent."""
        self.sub_agents[agent.agent_id] = agent
    
    async def think(self, request: AgentRequest) -> AgentMessage:
        """Orchestrator decides which agent to delegate to."""
        # Parse intent and delegate
        # This is a simplified version
        return await super().think(request)


class ReflectorAgent(Agent):
    """Metacognitive agent for self-improvement."""
    
    def __init__(self, **kwargs: Any) -> None:
        kwargs["role"] = AgentRole.REFLECTOR
        super().__init__(**kwargs)
        self.insights: list[dict[str, Any]] = []
    
    async def think(self, request: AgentRequest) -> AgentMessage:
        """Analyze and reflect on previous agent actions."""
        # Extract insights from recent interactions
        # Suggest improvements
        return AgentMessage(
            role=MessageRole.ASSISTANT,
            content="Reflection complete.",
        )