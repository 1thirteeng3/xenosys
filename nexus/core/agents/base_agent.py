"""
XenoSys Core - Agent System
Multi-agent orchestration with metacognitive capabilities and L4 Knowledge Graph interception
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Awaitable, Callable, Optional, TYPE_CHECKING
from uuid import UUID, uuid4

import dspy

# Importação condicional para evitar dependência circular (Type Hinting)
if TYPE_CHECKING:
    # Ajuste este path conforme o local exato da sua classe ContextualMemoryClient
    from nexus.core.memory.l4_contextual.graph_integration import ContextualMemoryClient

try:
    from .signatures import ExtractKnowledgeGraph
except ImportError:
    # Fallback seguro caso o arquivo signatures.py ainda não tenha sido criado
    class ExtractKnowledgeGraph(dspy.Signature):
        """Extrai entidades e relações de uma conversa para salvar em Knowledge Graph."""
        user_input = dspy.InputField()
        agent_response = dspy.InputField()
        entities = dspy.OutputField()
        relations = dspy.OutputField()

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
    CRITIC = "critic"  # Adversarial pair role


class AgentState(str, Enum):
    """Agent lifecycle states."""
    IDLE = "idle"
    THINKING = "thinking"
    ACTING = "acting"
    WAITING_TOOL = "waiting_tool"
    WAITING_HITL = "waiting_hitl"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentType(str, Enum):
    """Agent type definitions."""
    EXECUTOR = "executor"
    CRITIC = "critic"
    HYBRID = "hybrid"


class MessageRole(str, Enum):
    """Message roles in agent dialogue."""
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
    result: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    approved: Optional[bool] = None  # For HITL


@dataclass
class AgentMessage:
    """A message in agent dialogue."""
    id: str = field(default_factory=lambda: str(uuid4()))
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
    agent_id: Optional[str] = None
    entity_id: Optional[str] = None
    context: dict[str, Any] = field(default_factory=dict)
    max_iterations: int = 10
    timeout_seconds: float = 300.0
    temperature: Optional[float] = None
    system_prompt: Optional[str] = None


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
    error: Optional[str] = None


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

    def register(self, tool: Tool, toolsets: Optional[list[str]] = None) -> None:
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

    def get(self, name: str) -> Optional[Tool]:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self, toolset: Optional[str] = None) -> list[str]:
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
    - L4 Knowledge Graph interception (Metacognitive Memory)
    - Message history management
    - Tool execution with HITL support
    - State machine transitions
    - Logging and tracing
    """

    def __init__(
        self,
        agent_id: str,
        role: AgentRole,
        agent_type: AgentType = AgentType.EXECUTOR,
        name: Optional[str] = None,
        description: Optional[str] = None,
        system_prompt: Optional[str] = None,
        tools: Optional[list[str]] = None,
        llm_config: Optional[dict[str, Any]] = None,
        l4_client: Optional['ContextualMemoryClient'] = None,
    ) -> None:
        self.agent_id = agent_id
        self.role = role
        self.agent_type = agent_type
        self.name = name or agent_id
        self.description = description or ""
        self.system_prompt = system_prompt or ""
        self.tools = tools or []
        self.llm_config = llm_config or {}
        
        # Cliente do Knowledge Graph
        self.l4 = l4_client

        # Initialize DSPy LM (must be configured at startup)
        self._init_dspy_lm()

        # State
        self.state = AgentState.IDLE
        self.is_active = True  # Required for repository
        self.messages: list[AgentMessage] = []
        self.current_tool_call: Optional[ToolCall] = None

        # Metacognitive state
        self.iteration_count = 0
        self.thought_history: list[str] = []

    def _init_dspy_lm(self) -> None:
        """
        Initialize DSPy LM with provider injection.
        Also configures the L4 Knowledge Extractor if L4 client is available.
        """
        import os

        config = self.llm_config or {}
        provider = config.get("provider", "openai")
        model_name = config.get("model", "gpt-4o")

        try:
            if provider == "openai":
                api_key = config.get("api_key") or os.environ.get("OPENAI_API_KEY")
                if not api_key:
                    logger.warning(f"Agent {self.name}: OPENAI_API_KEY not set, using fallback")
                self.lm = dspy.LM(f"openai/{model_name}", api_key=api_key)

            elif provider == "anthropic":
                api_key = config.get("api_key") or os.environ.get("ANTHROPIC_API_KEY")
                if not api_key:
                    logger.warning(f"Agent {self.name}: ANTHROPIC_API_KEY not set, using fallback")
                self.lm = dspy.LM(f"anthropic/{model_name}", api_key=api_key)

            elif provider == "ollama":
                api_base = config.get("api_base", "http://localhost:11434")
                self.lm = dspy.LM(f"ollama/{model_name}", api_base=api_base)

            elif provider == "azure":
                api_key = config.get("api_key") or os.environ.get("AZURE_API_KEY")
                api_base = config.get("api_base") or os.environ.get("AZURE_API_BASE")
                if not api_base:
                    raise ValueError("Azure deployment requires api_base configuration")
                self.lm = dspy.LM(
                    f"azure/{model_name}",
                    api_key=api_key,
                    api_base=api_base,
                )
            else:
                raise ValueError(f"LLM provider not supported: {provider}")

            # Configure DSPy global context
            dspy.configure(lm=self.lm)
            logger.info(f"DSPy LM configured: {provider}/{model_name} for agent {self.name}")

            # Instancia o extrator L4 (Se a memória contextual estiver ativada)
            if self.l4 is not None:
                self.knowledge_extractor = dspy.Predict(ExtractKnowledgeGraph)

        except ImportError:
            logger.warning(f"Agent {self.name}: DSPy not installed, using litellm fallback")
            self.lm = None
            self.knowledge_extractor = None
        except Exception as e:
            logger.error(f"Agent {self.name}: Failed to configure DSPy: {e}")
            self.lm = None
            self.knowledge_extractor = None

    @property
    def is_critic(self) -> bool:
        """Check if this is a critic/auditor agent."""
        return self.agent_type == AgentType.CRITIC or self.role == AgentRole.REFLECTOR

    async def think(self, request: AgentRequest) -> AgentMessage:
        """
        Think phase - generate next action.
        Override this method to implement custom reasoning.
        """
        context = self._build_context(request)
        response = await self._call_llm(context)

        message = AgentMessage(
            role=MessageRole.ASSISTANT,
            content=response["content"],
            tool_calls=self._parse_tool_calls(response.get("tool_calls", [])),
        )
        return message

    async def act(self, message: AgentMessage) -> AgentMessage:
        """
        Act phase - execute planned action.
        """
        if message.tool_calls:
            for tool_call in message.tool_calls:
                await self._execute_tool(tool_call)
                message.tool_results.append(tool_call)
        return message

    async def observe(self, result: AgentMessage) -> None:
        """
        Observe phase - process results and update state.
        """
        self.messages.append(result)
        self.thought_history.append(result.content[:200])  # Truncate for history

    async def run(self, request: AgentRequest) -> AgentResponse:
        """
        Main agent execution loop (ReAct pattern) com Interceptação L4.
        """
        self.state = AgentState.THINKING
        self.iteration_count = 0

        try:
            # ==========================================
            # 1. PRE-HOOK (LEITURA DO "CADERNINHO" L4)
            # ==========================================
            l4_context = ""
            if self.l4:
                l4_context = await self.l4.read_graph(query=request.message)

            # System message enriquecido com o Knowledge Graph
            enriched_system_prompt = request.system_prompt or self.system_prompt
            if l4_context:
                enriched_system_prompt += f"\n\n[CONTEXTO DE MEMÓRIA DINÂMICA (L4)]\n{l4_context}"

            if enriched_system_prompt:
                self.messages.append(AgentMessage(
                    role=MessageRole.SYSTEM,
                    content=enriched_system_prompt,
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

                # ==========================================
                # 2. INFERÊNCIA PRINCIPAL (CHECAGEM DE SAÍDA)
                # ==========================================
                if not thought.tool_calls:
                    # Resposta direta (sem ferramentas)
                    self.state = AgentState.COMPLETED
                    final_content = thought.content
                    
                    # 3. POST-HOOK ASSÍNCRONO
                    if self.l4 and hasattr(self, 'knowledge_extractor') and self.knowledge_extractor:
                        asyncio.create_task(self._reflect_and_store(request.message, final_content))

                    return AgentResponse(
                        session_id=request.session_id,
                        message_id=str(uuid4()),
                        content=final_content,
                        done=True,
                        iterations=self.iteration_count,
                        tool_calls=thought.tool_calls,
                    )

                # ACT
                self.state = AgentState.ACTING
                for tool_call in thought.tool_calls:
                    if tool_call.name == "final_answer":
                        self.state = AgentState.COMPLETED
                        final_content = tool_call.arguments.get("answer", "")
                        
                        # 3. POST-HOOK ASSÍNCRONO
                        if self.l4 and hasattr(self, 'knowledge_extractor') and self.knowledge_extractor:
                            asyncio.create_task(self._reflect_and_store(request.message, final_content))

                        return AgentResponse(
                            session_id=request.session_id,
                            message_id=str(uuid4()),
                            content=final_content,
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

    # ==========================================
    # FUNÇÃO DO POST-HOOK (METÁCOGNIÇÃO L4)
    # ==========================================
    async def _reflect_and_store(self, user_input: str, agent_response: str) -> None:
        """Tarefa de background: Avalia a conversa e atualiza o Knowledge Graph."""
        try:
            # Pede ao DSPy para abstrair/aprender regras novas da conversa
            extraction = self.knowledge_extractor(user_input=user_input, agent_response=agent_response)
            
            # Valida as chaves do output do DSPy
            entities = getattr(extraction, 'entities', None)
            relations = getattr(extraction, 'relations', None)
            
            if entities and relations:
                await self.l4.create_relations(
                    entities=entities, 
                    relations=relations
                )
                logger.info(f"🧠 [L4 Updated] Novas memórias cognitivas consolidadas no grafo.")
        except Exception as e:
            logger.warning(f"⚠️ [L4 Reflection Error] Falha ao extrair memória: {e}")

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
        return True

    async def _call_llm(self, context: list[dict[str, Any]]) -> dict[str, Any]:
        """Call LLM with context."""
        if hasattr(self, 'lm') and self.lm is not None:
            return await self._call_dspy(context)
        return await self._call_litellm(context)

    async def _call_dspy(self, context: list[dict[str, Any]]) -> dict[str, Any]:
        """Call LLM using DSPy."""
        import dspy

        try:
            messages = []
            for msg in context[-20:]:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                messages.append(dspy.UserMessage(content) if role == "user" else dspy.AssistantMessage(content))

            response = self.lm(messages)

            if response:
                content = response[0].content if hasattr(response[0], 'content') else str(response[0])
                return {
                    "content": content,
                    "tool_calls": [],
                    "model": self.llm_config.get("model", "dspy"),
                    "tokens_in": 0,
                    "tokens_out": 0,
                }

            return {"content": "DSPy returned empty response", "tool_calls": []}

        except Exception as e:
            logger.error(f"DSPy call failed: {e}")
            return await self._call_litellm(context)

    async def _call_litellm(self, context: list[dict[str, Any]]) -> dict[str, Any]:
        """Call LLM with context using litellm (fallback)."""
        try:
            import litellm

            model = self.llm_config.get("model", "gpt-4o")
            provider = self.llm_config.get("provider", "openai")
            model_str = f"{provider}/{model}" if provider != "openai" else model

            messages_for_api = []
            for msg in context[-20:]:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                messages_for_api.append({"role": role, "content": content})

            optional_params = {}
            if self.llm_config.get("temperature"):
                optional_params["temperature"] = self.llm_config["temperature"]
            if self.llm_config.get("max_tokens"):
                optional_params["max_tokens"] = self.llm_config["max_tokens"]
            if self.llm_config.get("top_p"):
                optional_params["top_p"] = self.llm_config["top_p"]
            if self.llm_config.get("api_key"):
                optional_params["api_key"] = self.llm_config["api_key"]

            response = await litellm.acompletion(
                model=model_str,
                messages=messages_for_api,
                **optional_params
            )

            content = response.choices[0].message.content or ""
            usage = getattr(response, 'usage', None)
            tokens_in = getattr(usage, 'prompt_tokens', 0) if usage else 0
            tokens_out = getattr(usage, 'completion_tokens', 0) if usage else 0

            return {
                "content": content,
                "tool_calls": [],
                "model": model,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
            }

        except ImportError:
            logger.warning("litellm not installed, using placeholder response")
            return {
                "content": "This is a placeholder response (litellm not available).",
                "tool_calls": [],
            }
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return {
                "content": f"Error: {str(e)}",
                "tool_calls": [],
                "error": str(e),
            }

    def _build_context(self, request: AgentRequest) -> list[dict[str, Any]]:
        """Build context for LLM call."""
        messages = [
            {"role": "system", "content": self.system_prompt},
        ]

        if request.context.get("memory"):
            messages.append({
                "role": "system",
                "content": f"Relevant memory:\n{request.context['memory']}"
            })

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
            "type": self.agent_type.value,
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
        kwargs["agent_type"] = AgentType.HYBRID
        super().__init__(**kwargs)
        self.sub_agents: dict[str, Agent] = {}

    def register_agent(self, agent: Agent) -> None:
        """Register a sub-agent."""
        self.sub_agents[agent.agent_id] = agent

    async def think(self, request: AgentRequest) -> AgentMessage:
        return await super().think(request)


class ReflectorAgent(Agent):
    """Metacognitive agent for self-improvement."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs["role"] = AgentRole.REFLECTOR
        kwargs["agent_type"] = AgentType.CRITIC
        super().__init__(**kwargs)
        self.insights: list[dict[str, Any]] = []

    async def think(self, request: AgentRequest) -> AgentMessage:
        return AgentMessage(
            role=MessageRole.ASSISTANT,
            content="Reflection complete.",
        )


class AdversarialAgent(Agent):
    """
    Adversarial pair - acts as critic/auditor for executor agents.
    Every executor has a paired critic for quality assurance.
    """

    def __init__(self, target_agent_id: str, **kwargs: Any) -> None:
        kwargs["role"] = AgentRole.REFLECTOR
        kwargs["agent_type"] = AgentType.CRITIC
        super().__init__(**kwargs)
        self.target_agent_id = target_agent_id

    async def think(self, request: AgentRequest) -> AgentMessage:
        critique = self._generate_critique(request)
        return AgentMessage(
            role=MessageRole.ASSISTANT,
            content=critique,
        )

    def _generate_critique(self, request: AgentRequest) -> str:
        # Placeholder - actual implementation uses LLM to evaluate
        return "Critique placeholder"
