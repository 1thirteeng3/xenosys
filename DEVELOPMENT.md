# XenoSys — Unified Multi-Agent System
## Development Document (DDD Strategic & Tactical Design)

**Version:** 1.0  
**Date:** April 14, 2026  
**Classification:** Development Specification  
**Authors:** XenoSys Development Team  
**Methodology:** Domain-Driven Design (DDD) + Structured Design Methodology (SDD)

---

## Table of Contents

1. [Strategic Design (The Business Map)](#1-strategic-design-the-business-map)
   - [1.1 Ubiquitous Language](#11-ubiquitous-language)
   - [1.2 Bounded Contexts](#12-bounded-contexts)
   - [1.3 Context Mapping](#13-context-mapping)
2. [Tactical Design (Code Modeling)](#2-tactical-design-code-modeling)
   - [2.1 Entities vs Value Objects](#21-entities-vs-value-objects)
   - [2.2 Aggregates](#22-aggregates)
   - [2.3 Domain Services](#23-domain-services)
   - [2.4 Domain Events](#24-domain-events)

---

## 1. Strategic Design (The Business Map)

### 1.1 Ubiquitous Language

The following terms represent the core business concepts of XenoSys. All code, documentation, and communications must use these exact terms and definitions.

#### Core Domain Terms

| Term | Definition | Synonyms | Usage Context |
|------|------------|----------|----------------|
| **Agent** | An autonomous computational entity capable of reasoning, tool execution, and self-improvement. Each agent has a unique identity, role, and configuration. | Executor, Specialist, Orchestrator | Core Runtime, Agent Management |
| **Entity** | A composed group of one or more agents that operate as a single unit with unified routing logic. Entities expose a single interface while internally coordinating multiple specialized agents. | Multi-Agent, Composite Agent, Agent Group | Entity System, Execution |
| **Session** | A bounded conversation context between a user and an agent/entity. Sessions track message history, token usage, cost, and state. Sessions are identified by UUID and persist across multiple message exchanges. | Conversation, Dialog, Interaction | Gateway, Execution |
| **Message** | A single unit of communication within a session. Messages have roles (user/assistant/system/tool), content, and metadata including token counts and latency. | Prompt, Response, Input, Output | Gateway, Agent Runtime |
| **Tool** | A callable function that an agent can invoke to interact with external systems. Tools have names, descriptions, parameter schemas, and optional HITL (Human-in-the-Loop) requirements. | Function, Capability, Action | Tool System |
| **Memory** | Persistent storage of agent knowledge across sessions. Memory is organized in layers (L1 Semantic, L2 Long-term, L3 Episodic) with different retention and retrieval characteristics. | Knowledge, Context, State | Memory System |
| **LoRA Adapter** | A fine-tuned model adapter that modifies base LLM behavior for specific tasks. LoRA adapters can be hot-swapped without reloading the base model. | Adapter, Model Patch, Fine-tune | Learning Engine |
| **Policy** | A governance rule that enforces constraints on agent behavior, cost, content, or access. Policies are evaluated at runtime and can block or approve actions. | Rule, Governance, Constraint | LLMOps, Governance |
| **Channel** | A communication pathway for user interaction (e.g., Telegram, Discord, Slack, Web). Channels adapt external protocols to the internal ACP format. | Platform, Integration, Connector | Gateway |
| **Plugin** | An extension that adds capability to the gateway. Plugins can implement channels, tools, memory providers, transforms, or middleware. | Extension, Add-on, Module | Gateway |
| **HitL Approval** | A pending action requiring human authorization before execution. HITL items are queued, presented to approvers, and either approved or rejected. | Approval, Authorization, Review | LLMOps, HITL |

#### Agent-Specific Terms

| Term | Definition | Usage |
|------|------------|-------|
| **Agent Role** | The functional classification of an agent (Orchestrator, Executor, Planner, Analyzer, Reflector, Specialist). Roles determine default behaviors and routing. | Agent configuration |
| **Agent State** | The current lifecycle state of an agent (IDLE, THINKING, ACTING, WAITING_TOOL, WAITING_HITL, COMPLETED, FAILED). State transitions are tracked for observability. | Agent Runtime |
| **System Prompt** | The core instruction set that defines agent behavior, personality, and capabilities. System prompts are versioned and can reference memory. | Agent configuration |
| **Iteration** | A single cycle of the agent's think-act-observe loop. Iterations are counted and limited to prevent infinite loops. | Agent Runtime |
| **Tool Call** | A request to execute a specific tool with parameters. Tool calls include execution timing, results, and approval status. | Tool System |

#### Memory-Specific Terms

| Term | Definition | Layer |
|------|------------|-------|
| **Semantic Memory (L1)** | Vector-embedded knowledge for similarity search. Stored in ChromaDB with 384-dimensional embeddings. | L1 |
| **Long-term Memory (L2)** | Versioned Markdown files organized in a hierarchical file system. Git-based with LLM-friendly content. | L2 |
| **Episodic Memory (L3)** | Session and message history stored in PostgreSQL with FTS5 full-text search. ACID compliant. | L3 |
| **Working Memory** | Current context window content. Managed dynamically to stay within LLM token limits. | Context |
| **Memory Entry** | A single unit of stored knowledge with content, embedding, importance score, and access metadata. | L1/L2/L3 |
| **Memory Vault** | A named collection of memory entries for a specific agent or entity. Provides namespacing. | L1 |

#### Learning-Specific Terms

| Term | Definition | Usage |
|------|------------|-------|
| **STaR (Self-Taught Reasoning)** | A self-improvement technique where agents generate rationales for their reasoning and learn from correct outcomes. | Self-Improvement |
| **Dreaming** | The process of running STaR cycles during agent idle time to improve capabilities without user interaction. | Self-Improvement |
| **LoRA Swap** | The hot-swap operation of loading a new LoRA adapter into an active agent without restarting. | Learning Engine |
| **LoRA Registry** | A catalog of available LoRA adapters with metadata, version history, and performance metrics. | Learning Engine |

#### Cost and Governance Terms

| Term | Definition | Usage |
|------|------------|-------|
| **Cost Record** | A granular entry tracking tokens, cost in USD, agent, entity, session, and user for a single operation. | Cost Tracking |
| **Budget** | A financial limit on spending that can be applied per user, entity, or globally. Enforcement triggers alerts or blocks. | Cost Governance |
| **Policy Engine** | The system that evaluates policies against requests and enforces restrictions. | Governance |
| **Circuit Breaker** | A pattern that prevents cascading failures by stopping requests to failing external services. | Resilience |

### 1.2 Bounded Contexts

XenoSys is divided into distinct bounded contexts, each with clear responsibilities and boundaries. Contexts are organized by domain and exposure level.

#### Context Map Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            XENOSYS BOUNDED CONTEXTS                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                      GATEWAY CONTEXT (External)                         │    │
│  │                                                                          │    │
│  │  Responsibility: User interface adapters, channel management,          │    │
│  │  authentication, session management, plugin system                     │    │
│  │                                                                          │    │
│  │  Modules:                                                               │    │
│  │  ├── ChannelManager (20+ adapters)                                     │    │
│  │  ├── PluginManager (registry, hooks)                                    │    │
│  │  ├── AuthManager (JWT, MFA, RBAC)                                       │    │
│  │  ├── SessionManager (state, history)                                   │    │
│  │  ├── ACPHandler (protocol parsing)                                     │    │
│  │  └── GRPCClient (bridge to core)                                       │    │
│  │                                                                          │    │
│  │  Public API: REST endpoints, WebSocket events                          │    │
│  │  Dependencies: Core Context (via gRPC)                                  │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                      │                                          │
│                                      │ gRPC / ACP                               │
│                                      ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                      CORE CONTEXT (Primary)                             │    │
│  │                                                                          │    │
│  │  Responsibility: Agent orchestration, execution, tool dispatching       │    │
│  │                                                                          │    │
│  │  Modules:                                                               │    │
│  │  ├── EventBus (asyncpub/sub)                                           │    │
│  │  ├── TaskQueue (priority scheduling)                                   │    │
│  │  ├── EntityRouter (routing logic)                                     │    │
│  │  ├── LifecycleManager (state machine)                                  │    │
│  │  └── AgentRegistry (CRUD, discovery)                                   │    │
│  │                                                                          │    │
│  │  Public API: gRPC services                                             │    │
│  │  Dependencies: Memory Context, Learning Context, LLMOps Context        │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│          │                           │                           │              │
│          ▼                           ▼                           ▼              │
│  ┌─────────────────┐   ┌─────────────────────┐   ┌─────────────────────┐    │
│  │  MEMORY CONTEXT  │   │   LEARNING CONTEXT   │   │   LLMOPS CONTEXT    │    │
│  │                  │   │                       │   │                     │    │
│  │ Responsibility:  │   │ Responsibility:      │   │ Responsibility:     │    │
│  │ Multi-layer       │   │ Agent self-          │   │ Observability,     │    │
│  │ memory storage    │   │ improvement, LoRA   │   │ cost tracking,     │    │
│  │ and retrieval     │   │ adapter management   │   │ governance         │    │
│  │                  │   │                       │   │                     │    │
│  │ Modules:          │   │ Modules:             │   │ Modules:            │    │
│  │ ├── MemoryOrch    │   │ ├── LoRARegistry     │   │ ├── Telemetry       │    │
│  │ ├── L1Semantic    │   │ ├── LoRASwapper      │   │ ├── CostTracker     │    │
│  │ ├── L2LongTerm    │   │ ├── DreamScheduler   │   │ ├── PolicyEngine    │    │
│  │ ├── L3Episodic    │   │ ├── STaREngine       │   │ ├── HITLManager     │    │
│  │ └── WorkingMem    │   │ └── DSPyOptimizer    │   │ └── StateManager    │    │
│  └─────────────────┘   └─────────────────────┘   └─────────────────────┘    │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

#### Context Definitions

##### 1. Gateway Context

**Purpose:** Handle all external user interactions and channel integrations.

**Responsibilities:**
- Accept user messages from multiple channels (Telegram, Discord, Slack, etc.)
- Authenticate and authorize users
- Manage session lifecycle
- Route messages to the Core via gRPC
- Return responses back to appropriate channels
- Plugin system for extensibility

**Domain:** User Interaction, Channel Management

**Public Interfaces:**
- REST API: `POST /api/v1/agents/execute`, `GET /api/v1/sessions/{id}`
- WebSocket: Real-time streaming
- Channel adapters: `ChannelAdapter` interface

**Technology:** TypeScript/Node.js 22+, Hono, Zod

**Boundaries:**
- **Internal:** Does not access agent internals directly
- **External:** Accepts channel-specific message formats, normalizes to ACP

---

##### 2. Core Context

**Purpose:** Orchestrate agent execution and manage agent lifecycle.

**Responsibilities:**
- Accept execution requests from Gateway
- Manage agent registry and discovery
- Execute agents using ReAct pattern
- Coordinate tool execution
- Handle event-driven workflows
- Manage entity routing and composition

**Domain:** Agent Orchestration, Execution

**Public Interfaces:**
- gRPC services: `AgentService`, `EntityService`
- Internal events: `AgentStarted`, `AgentCompleted`, `ToolCalled`

**Technology:** Python 3.12+, asyncio, DSPy

**Boundaries:**
- **Upstream:** Receives requests from Gateway
- **Downstream:** Coordinates with Memory, Learning, LLMOps contexts
- **Internal:** Contains EventBus, TaskQueue, AgentRuntime

---

##### 3. Memory Context

**Purpose:** Provide multi-layer persistent memory for agents.

**Responsibilities:**
- Store and retrieve semantic embeddings (L1)
- Manage versioned document storage (L2)
- Persist episodic session data (L3)
- Coordinate memory orchestration across layers
- Provide search capabilities (vector and full-text)

**Domain:** Knowledge Management, Memory Storage

**Public Interfaces:**
- Internal services: `MemoryService` (gRPC)
- In-process API: `MemoryOrchestrator`

**Technology:** ChromaDB, PostgreSQL, Git, sentence-transformers

**Boundaries:**
- **Upstream:** Serves requests from Core Context
- **Internal:** L1, L2, L3 are distinct storage with different access patterns
- **External:** PostgreSQL for L3, ChromaDB for L1, filesystem for L2

---

##### 4. Learning Context

**Purpose:** Enable agent self-improvement and LoRA adapter management.

**Responsibilities:**
- Manage LoRA adapter registry
- Execute hot-swap LoRA transitions
- Run STaR self-improvement cycles
- Schedule dreaming during agent idle
- Optimize DSPy programs

**Domain:** Model Training, Self-Improvement

**Public Interfaces:**
- Internal API: `LoRASwapper`, `DreamingScheduler`
- External: Kaggle/Colab API integration

**Technology:** PEFT, llama-cpp-python, DSPy

**Boundaries:**
- **Upstream:** Triggered by LLMOps (performance metrics)
- **External:** Kaggle/Colab for training compute
- **Internal:** STaR generates training data from agent sessions

---

##### 5. LLMOps Context

**Purpose:** Provide observability, governance, and cost management.

**Responsibilities:**
- Collect and export telemetry (OpenTelemetry)
- Track costs per agent/entity/user
- Enforce governance policies
- Manage HITL approval workflows
- Maintain distributed state

**Domain:** Operations, Governance, Observability

**Public Interfaces:**
- REST API: `GET /api/v1/costs/dashboard`, `POST /api/v1/hitl/approve`
- Telemetry export: Jaeger/Grafana

**Technology:** OpenTelemetry, SQLAlchemy, asyncpg

**Boundaries:**
- **Cross-cutting:** Interacts with all contexts
- **External:** Monitoring infrastructure (Jaeger, Grafana)
- **Internal:** Cost tracking requires access to session data

---

### 1.3 Context Mapping

The following describes how the bounded contexts communicate, dependencies, and data flow.

#### Upstream/Downstream Relationships

```
                         ┌──────────────┐
                         │   Gateway    │
                         │   Context    │
                         └──────┬───────┘
                                │
                                │ "I need agent execution"
                                ▼
                         ┌──────────────┐
                         │   Core       │ ◄── UPSTREAM (Consumer)
                         │   Context    │
                         └──────┬───────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
        ▼                       ▼                       ▼
┌───────────────┐    ┌───────────────────┐    ┌───────────────────┐
│    Memory    │    │     Learning     │    │     LLMOps       │
│   Context    │    │     Context      │    │     Context      │
│               │    │                   │    │                   │
│ DOWNSTREAM   │    │   DOWNSTREAM     │    │  CROSS-CUTTING   │
│ (Provider)   │    │   (Provider)     │    │  (Provider)      │
└───────────────┘    └───────────────────┘    └───────────────────┘
```

#### Communication Patterns

| From Context | To Context | Pattern | Protocol | Data Format |
|--------------|------------|---------|----------|-------------|
| Gateway | Core | Upstream Consumer | gRPC | Protocol Buffers |
| Core | Memory | Downstream Provider | Internal API | Python objects |
| Core | Learning | Downstream Provider | Internal API | Python objects |
| Core | LLMOps | Cross-cutting | Events | Domain Events |
| Memory | Core | Synchronous Response | Same-process | Python objects |
| LLMOps | All | Observability | OpenTelemetry | OTLP |

#### Anti-Corruption Layer (ACL)

The **Gateway Context** implements an ACL that protects the Core from poorly formatted external data:

```typescript
// Gateway ACL Example - Input Sanitization
class ACPSanitizer {
  sanitize(input: unknown): ACPMessage {
    // 1. Validate schema
    // 2. Escape special characters
    // 3. Remove prompt injection patterns
    // 4. Normalize encoding
    // 5. Validate against allow lists
    return validatedMessage;
  }
  
  detectPromptInjection(content: string): boolean {
    // Heuristic + ML-based detection
    return injectionPatterns.some(p => content.includes(p));
  }
}
```

The **Core Context** implements an ACL when calling external services:

```python
class ExternalLLMACL:
    """Protects from malformed LLM responses."""
    
    def validate_response(self, response: dict) -> LLMResponse:
        # 1. Schema validation
        # 2. Content filtering (PII, secrets)
        # 3. Output length limits
        return validated_response
```

#### Shared Kernel

The following is shared across contexts (avoiding duplication):

| Shared Component | Location | Used By |
|------------------|----------|---------|
| Domain Events | `core/events.py` | Core, Memory, LLMOps |
| Data Models | `core/models/` | All contexts |
| Configuration | `shared/config.py` | Gateway, Core |
| Exceptions | `shared/exceptions.py` | All contexts |

#### Published Language

All inter-context communication uses the **ACP (Agent Communication Protocol)**:

```typescript
// Gateway → Core Message Format
interface ACPMessage {
  version: "1.0";
  type: "request" | "response" | "error" | "event";
  id: string;
  requestId?: string;
  timestamp: number;
  source: { nodeId: string; agentId?: string };
  target?: { nodeId: string; agentId?: string };
  payload: Record<string, unknown>;
  metadata?: { correlationId?: string; ttl?: number; priority?: number };
}
```

---

## 2. Tactical Design (Code Modeling)

### 2.1 Entities vs Value Objects

The following defines the distinction between Entities (identity-bearing) and Value Objects (immutable attributes) within XenoSys.

#### Entities (Identity-Bearing)

| Entity | Identity | Lifecycle | Aggregate Root |
|--------|----------|-----------|----------------|
| **Agent** | `agent_id` (UUID) | Created → Configured → Active → Inactive | Yes - `Agent` |
| **Entity** | `entity_id` (UUID) | Created → Configured → Active → Inactive | Yes - `Entity` |
| **Session** | `session_id` (UUID) | Created → Active → Completed/Failed | Yes - `Session` |
| **Message** | `message_id` (UUID) | Created → Stored → Retrieved | No - Part of Session |
| **LoRA Adapter** | `adapter_id` (UUID) | Created → Trained → Active → Archived | Yes - `LoRAAdapter` |
| **MemoryEntry** | `entry_id` (UUID) | Created → Indexed → Accessed → Archived | No - Part of Vault |
| **HitLApproval** | `approval_id` (UUID) | Created → Pending → Reviewed | Yes - `HitLApproval` |
| **Policy** | `policy_id` (UUID) | Created → Active → Inactive | Yes - `Policy` |
| **CostRecord** | `record_id` (UUID) | Created → Aggregated | No - Part of Dashboard |

#### Entity Definitions

##### Agent Entity

```python
# core/agents/entity.py
from uuid import UUID
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class Agent:
    """Agent Entity - has persistent identity."""
    
    # Identity (immutable after creation)
    id: UUID
    
    # Attributes
    name: str
    role: AgentRole  # Enum: ORCHESTRATOR, EXECUTOR, PLANNER, etc.
    type: AgentType  # Enum: EXECUTOR, CRITIC, HYBRID
    
    # Configuration
    system_prompt: str
    model_provider: str  # 'openai', 'anthropic', 'local'
    model_name: str
    tools: list[str]  # Tool names
    
    # Memory binding
    memory_vault_id: Optional[UUID]
    lora_adapter_id: Optional[UUID]
    
    # State
    created_at: datetime
    updated_at: datetime
    is_active: bool
    metadata: dict
    
    # Identity methods
    def get_id(self) -> UUID:
        return self.id
    
    def is_same_identity(self, other: Agent) -> bool:
        """Two agents are the same if they have the same ID."""
        return self.id == other.id
```

##### Session Entity

```python
# core/sessions/entity.py
@dataclass
class Session:
    """Session Entity - conversation context with identity."""
    
    # Identity
    id: UUID
    
    # Relationships
    agent_id: UUID
    entity_id: Optional[UUID]
    user_id: str
    
    # State
    status: SessionStatus  # ACTIVE, WAITING, ENDED
    message_count: int
    token_count: int
    total_cost_usd: float
    
    # Lifecycle
    started_at: datetime
    ended_at: Optional[datetime]
    last_activity_at: datetime
    
    # Methods
    def add_message(self, message: Message) -> None:
        """Add message and update metrics."""
        self.message_count += 1
        self.last_activity_at = datetime.utcnow()
        
    def end(self) -> None:
        """End the session."""
        self.status = SessionStatus.ENDED
        self.ended_at = datetime.utcnow()
```

#### Value Objects (Immutable)

| Value Object | Attributes | Immutability |
|--------------|------------|--------------|
| **MessageRole** | `value: str` | Immutable - enum-like |
| **AgentRole** | `value: str` | Immutable - enum-like |
| **ChannelConfig** | `id, type, settings, auth` | Immutable after creation |
| **ToolCall** | `name, arguments, result, error` | Mutable during execution |
| **MonetaryValue** | `amount: Decimal, currency: str` | Immutable - operations return new instance |
| **TokenCount** | `input: int, output: int` | Immutable - operations return new instance |
| **Embedding** | `vector: list[float], model: str` | Immutable |
| **Timestamp** | `value: datetime` | Immutable |

#### Value Object Definitions

```python
# shared/value_objects.py
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

@dataclass(frozen=True)
class MonetaryValue:
    """Value Object - immutable monetary amount."""
    
    amount: Decimal
    currency: str = "USD"
    
    def __post_init__(self):
        # Validate immutability through frozen dataclass
        if self.amount < 0:
            raise ValueError("Amount cannot be negative")
    
    def add(self, other: 'MonetaryValue') -> 'MonetaryValue':
        """Return new instance - original unchanged."""
        if self.currency != other.currency:
            raise ValueError("Cannot add different currencies")
        return MonetaryValue(
            amount=self.amount + other.amount,
            currency=self.currency
        )
    
    def convert_to(self, rate: Decimal) -> 'MonetaryValue':
        """Return new instance with converted amount."""
        return MonetaryValue(
            amount=self.amount * rate,
            currency=self.currency
        )


@dataclass(frozen=True)
class TokenCount:
    """Value Object - immutable token counts."""
    
    input_tokens: int
    output_tokens: int
    
    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens
    
    @property
    def cost_usd(self) -> Decimal:
        """Calculate cost based on current pricing."""
        # Example: $10/1M input, $30/1M output
        input_cost = Decimal(self.input_tokens) / 1_000_000 * Decimal("10")
        output_cost = Decimal(self.output_tokens) / 1_000_000 * Decimal("30")
        return input_cost + output_cost


@dataclass(frozen=True)
class ChannelCredentials:
    """Value Object - channel authentication credentials."""
    
    type: str  # 'api_key', 'oauth2', 'webhook_secret'
    credentials: dict[str, str]  # Encrypted at rest
    
    def validate(self) -> bool:
        """Validate credentials format."""
        return self.type in ['api_key', 'oauth2', 'webhook_secret']
```

### 2.2 Aggregates

Aggregates define clusters of entities that should be treated as a single unit for data changes. Each aggregate has a single entry point (Aggregate Root).

#### Aggregate Definitions

##### 1. Agent Aggregate

```
┌─────────────────────────────────────────────────────────────────┐
│                     AGENT AGGREGATE                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Agent (Aggregate Root)                                   │   │
│  │  └── UUID id                                              │   │
│  │  └── name, role, system_prompt, model_config              │   │
│  │  └── tools[], memory_vault_id, lora_adapter_id           │   │
│  │                                                           │   │
│  │  Manages:                                                 │   │
│  │  - Agent configuration                                    │   │
│  │  - Memory binding                                         │   │
│  │  - LoRA adapter attachment                                │   │
│  └────────────────────────┬─────────────────────────────────┘   │
│                           │                                     │
│  ┌────────────────────────┼─────────────────────────────────┐   │
│  │  ┌──────────────────────▼──────────────────────────┐    │   │
│  │  │  Message (Entity)                                │    │   │
│  │  │  └── UUID id ←── Part of session aggregate      │    │   │
│  │  │  └── session_id (reference)                    │    │   │
│  │  │  └── role, content, tool_calls[]                │    │   │
│  │  └───────────────────────────────────────────────────┘    │   │
│  │                                                           │   │
│  │  Invariants:                                              │   │
│  │  - Agent must have valid model_config                    │   │
│  │  - Tools must exist in registry                          │   │
│  │  - memory_vault_id must reference valid vault           │   │
│  │  - lora_adapter_id must reference active adapter        │   │
│  │                                                           │   │
│  │  Repository: AgentRepository                              │   │
│  │  Boundary: Agent and its configuration only             │   │
│  └───────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

```python
# core/agents/aggregate.py
from uuid import UUID
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class AgentAggregate:
    """
    Agent Aggregate Root.
    
    Controls invariants:
    - Agent must have valid model configuration
    - Referenced tools must exist in registry
    - Memory vault and LoRA adapter must be valid
    """
    
    # Aggregate Root
    agent: 'Agent'
    
    # Related entities (loaded as needed)
    memory_vault: Optional['MemoryVault'] = None
    lora_adapter: Optional['LoRAAdapter'] = None
    
    # Domain methods
    def bind_memory_vault(self, vault: 'MemoryVault') -> None:
        """Bind agent to a memory vault."""
        self.agent.memory_vault_id = vault.id
        self.memory_vault = vault
    
    def attach_lora_adapter(self, adapter: 'LoRAAdapter') -> None:
        """Attach a LoRA adapter to this agent."""
        if not adapter.is_active:
            raise ValueError("Cannot attach inactive adapter")
        self.agent.lora_adapter_id = adapter.id
        self.lora_adapter = adapter
    
    def detach_lora_adapter(self) -> None:
        """Remove LoRA adapter from agent."""
        self.agent.lora_adapter_id = None
        self.lora_adapter = None
    
    def validate(self) -> bool:
        """Validate aggregate invariants."""
        if not self.agent.model_config:
            return False
        # Additional validation...
        return True
```

##### 2. Session Aggregate

```
┌─────────────────────────────────────────────────────────────────┐
│                    SESSION AGGREGATE                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Session (Aggregate Root)                                │   │
│  │  └── UUID id                                             │   │
│  │  └── agent_id, entity_id, user_id                       │   │
│  │  └── status, metrics (tokens, cost)                     │   │
│  │                                                           │   │
│  │  Contains:                                               │   │
│  │  - Message[] (ordered by timestamp)                     │   │
│  │  - CostRecord[] (accumulated)                           │   │
│  │  - HitLApproval[] (pending/resolved)                   │   │
│  └────────────────────────┬─────────────────────────────────┘   │
│                           │                                      │
│  ┌────────────────────────┼──────────────────────────────────┐   │
│  │  ┌─────────────────────▼─────────────────────────────┐   │   │
│  │  │  Message (Entity)                                  │   │   │
│  │  │  └── UUID id                                       │   │   │
│  │  │  └── role, content, tool_calls[]                  │   │   │
│  │  │  └── tokens, latency_ms, metadata                │   │   │
│  │  └───────────────────────────────────────────────────┘   │   │
│  │                                                           │   │
│  │  ┌─────────────────────▼─────────────────────────────┐   │   │
│  │  │  CostRecord (Entity)                               │   │   │
│  │  │  └── agent_id, model, tokens, cost_usd           │   │   │
│  │  └───────────────────────────────────────────────────┘   │   │
│  │                                                           │   │
│  │  Invariants:                                              │   │
│  │  - Session status must be valid transition              │   │
│  │  - Messages ordered by timestamp                        │   │
│  │  - Cost records cannot be deleted, only voided         │   │
│  │                                                           │   │
│  │  Repository: SessionRepository                           │   │
│  │  Boundary: Session, Messages, CostRecords               │   │
│  └───────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

##### 3. Entity Aggregate (Multi-Agent Composition)

```
┌─────────────────────────────────────────────────────────────────┐
│                     ENTITY AGGREGATE                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Entity (Aggregate Root)                                 │   │
│  │  └── UUID id                                             │   │
│  │  └── name, description                                  │   │
│  │  └── agent_ids[], routing_strategy                      │   │
│  │  └── max_rounds, memory_config                          │   │
│  │                                                           │   │
│  │  Contains:                                               │   │
│  │  - Agent[] (the composed agents)                        │   │
│  │  - MemoryConfig (L1/L2/L3 bindings)                     │   │
│  │  - RoutingStrategy                                      │   │
│  └────────────────────────┬─────────────────────────────────┘   │
│                           │                                      │
│  ┌────────────────────────┼──────────────────────────────────┐   │
│  │  ┌─────────────────────▼─────────────────────────────┐   │   │
│  │  │  Agent (Entity) - Member of Entity                 │   │   │
│  │  │  └── UUID id                                       │   │   │
│  │  │  └── role, memory_vault_id                        │   │   │
│  │  └───────────────────────────────────────────────────┘   │   │
│  │                                                           │   │
│  │  ┌─────────────────────▼─────────────────────────────┐   │   │
│  │  │  MemoryConfig (Value Object)                        │   │   │
│  │  │  └── l1_vault_id, l2_path, l3_session_prefix       │   │   │
│  │  └───────────────────────────────────────────────────┘   │   │
│  │                                                           │   │
│  │  Invariants:                                              │   │
│  │  - Entity must have at least one agent                  │   │
│  │  - All referenced agents must exist and be active       │   │
│  │  - max_rounds must be > 0                                │   │
│  │  - routing_strategy must be valid                        │   │
│  │                                                           │   │
│  │  Repository: EntityRepository                             │   │
│  └───────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

#### Aggregate Repository Pattern

```python
# core/agents/repository.py
from abc import ABC, abstractmethod
from uuid import UUID
from typing import Optional

class AgentRepository(ABC):
    """Repository interface for Agent Aggregate."""
    
    @abstractmethod
    async def save(self, agent: Agent) -> Agent:
        """Save agent and related entities."""
        pass
    
    @abstractmethod
    async def get_by_id(self, id: UUID) -> Optional[Agent]:
        """Retrieve agent by ID."""
        pass
    
    @abstractmethod
    async def delete(self, id: UUID) -> bool:
        """Delete agent (soft delete)."""
        pass
    
    @abstractmethod
    async def list_active(self) -> list[Agent]:
        """List all active agents."""
        pass


# core/agents/repository_postgres.py
class PostgresAgentRepository(AgentRepository):
    """PostgreSQL implementation."""
    
    async def save(self, agent: Agent) -> Agent:
        async with self.pool.transaction():
            # Insert/update agent
            await self.db.execute(
                "INSERT INTO agents (...) VALUES (...)",
                agent_to_row(agent)
            )
            # Related entities handled in same transaction
        return agent
```

### 2.3 Domain Services

Domain Services encapsulate business operations that don't naturally belong to a single Entity or Value Object.

#### Service Definitions

##### 1. Entity Routing Service

```python
# core/orchestration/entity_routing_service.py
from dataclasses import dataclass
from typing import Optional

@dataclass
class RoutingRequest:
    """Input for routing decision."""
    message: str
    entity_id: UUID
    available_agents: list[Agent]
    session_context: dict

@dataclass
class RoutingResult:
    """Result of routing decision."""
    selected_agent_id: UUID
    routing_reason: str
    confidence: float  # 0.0 - 1.0

class EntityRoutingService:
    """
    Domain Service for determining which agent to route to within an Entity.
    
    This service doesn't belong to a single entity because it makes
    cross-entity decisions based on message content.
    """
    
    def __init__(self, memory_service: 'MemoryService'):
        self.memory_service = memory_service
    
    async def route(self, request: RoutingRequest) -> RoutingResult:
        """
        Determine optimal agent for the incoming message.
        
        Strategies:
        - SEMANTIC: Use embedding similarity to match message to agent expertise
        - SEQUENTIAL: Round-robin through agents
        - PARALLEL: Send to all agents, aggregate results
        """
        entity = await self._get_entity(request.entity_id)
        
        if entity.routing_strategy == RoutingStrategy.SEMANTIC:
            return await self._semantic_route(request, entity)
        elif entity.routing_strategy == RoutingStrategy.SEQUENTIAL:
            return await self._sequential_route(request, entity)
        elif entity.routing_strategy == RoutingStrategy.PARALLEL:
            return await self._parallel_route(request, entity)
        
        raise ValueError(f"Unknown routing strategy: {entity.routing_strategy}")
    
    async def _semantic_route(
        self, 
        request: RoutingRequest, 
        entity: Entity
    ) -> RoutingResult:
        """Route using semantic similarity to agent expertise."""
        # Get message embedding
        message_embedding = await self._embed(request.message)
        
        # Score each agent by expertise match
        best_agent = None
        best_score = 0.0
        
        for agent in request.available_agents:
            # Get agent expertise embedding from memory
            agent_embedding = await self.memory_service.get_agent_embedding(
                agent.id
            )
            score = cosine_similarity(message_embedding, agent_embedding)
            if score > best_score:
                best_score = score
                best_agent = agent
        
        return RoutingResult(
            selected_agent_id=best_agent.id,
            routing_reason=f"Semantic match (confidence: {best_score:.2f})",
            confidence=best_score
        )
```

##### 2. Cost Calculation Service

```python
# llmops/cost_calculation_service.py
from decimal import Decimal
from dataclasses import dataclass

@dataclass
class CostConfig:
    """Pricing configuration per model."""
    provider: str
    model: str
    input_cost_per_million: Decimal
    output_cost_per_million: Decimal

class CostCalculationService:
    """
    Domain Service for calculating LLM costs.
    
    Encapsulates complex pricing logic that spans multiple
    sessions and models.
    """
    
    def __init__(self):
        self._pricing: dict[str, CostConfig] = {}
        self._load_pricing()
    
    def calculate(
        self, 
        model: str, 
        input_tokens: int, 
        output_tokens: int
    ) -> Decimal:
        """Calculate cost for a single request."""
        config = self._get_pricing(model)
        
        input_cost = Decimal(input_tokens) / 1_000_000 * config.input_cost_per_million
        output_cost = Decimal(output_tokens) / 1_000_000 * config.output_cost_per_million
        
        return input_cost + output_cost
    
    def calculate_session(self, session: Session) -> Decimal:
        """Calculate total cost for a session."""
        total = Decimal(0)
        for record in session.cost_records:
            total += self.calculate(
                record.model,
                record.tokens_in,
                record.tokens_out
            )
        return total
    
    def calculate_agent_usage(self, agent_id: UUID) -> Decimal:
        """Calculate total cost for an agent across all sessions."""
        # Aggregates from cost_records
        pass
    
    def _get_pricing(self, model: str) -> CostConfig:
        """Get pricing config for model."""
        # Fallback to default pricing
        return self._pricing.get(model, self._pricing['default'])
    
    def _load_pricing(self) -> None:
        """Load pricing from configuration."""
        # Default pricing (example values)
        self._pricing['default'] = CostConfig(
            provider='openai',
            model='gpt-4',
            input_cost_per_million=Decimal('30.00'),
            output_cost_per_million=Decimal('60.00')
        )
```

##### 3. Policy Enforcement Service

```python
# llmops/policy_enforcement_service.py
from enum import Enum

class PolicyDecision(Enum):
    ALLOW = "allow"
    DENY = "deny"
    REVIEW = "review"  # Requires HITL

@dataclass
class PolicyContext:
    """Context for policy evaluation."""
    user_id: str
    agent_id: Optional[UUID]
    entity_id: Optional[UUID]
    action: str
    content: Optional[str]
    session_id: Optional[UUID]

class PolicyEnforcementService:
    """
    Domain Service for evaluating governance policies.
    
    This service doesn't belong to any single entity because
    it evaluates policies across the entire system.
    """
    
    def __init__(self, policy_repository: 'PolicyRepository'):
        self.policy_repository = policy_repository
    
    async def evaluate(self, context: PolicyContext) -> PolicyDecision:
        """Evaluate all applicable policies."""
        policies = await self.policy_repository.list_active()
        
        # Order by priority
        policies.sort(key=lambda p: p.priority, reverse=True)
        
        for policy in policies:
            if self._applies(policy, context):
                decision = await self._evaluate_policy(policy, context)
                if decision != PolicyDecision.ALLOW:
                    return decision
        
        return PolicyDecision.ALLOW
    
    async def _evaluate_policy(
        self, 
        policy: Policy, 
        context: PolicyContext
    ) -> PolicyDecision:
        """Evaluate a single policy."""
        if policy.rule_type == PolicyRuleType.RATE_LIMIT:
            return await self._evaluate_rate_limit(policy, context)
        elif policy.rule_type == PolicyRuleType.BUDGET:
            return await self._evaluate_budget(policy, context)
        elif policy.rule_type == PolicyRuleType.CONTENT_FILTER:
            return await self._evaluate_content_filter(policy, context)
        
        return PolicyDecision.ALLOW
    
    async def _evaluate_rate_limit(
        self, 
        policy: Policy, 
        context: PolicyContext
    ) -> PolicyDecision:
        """Evaluate rate limit policy."""
        limit = policy.config['requests_per_minute']
        current = await self._get_rate(context.user_id, policy.id)
        
        if current >= limit:
            return PolicyDecision.DENY
        return PolicyDecision.ALLOW
    
    async def _evaluate_content_filter(
        self, 
        policy: Policy, 
        context: PolicyContext
    ) -> PolicyDecision:
        """Evaluate content filter policy."""
        if not context.content:
            return PolicyDecision.ALLOW
        
        blocked_patterns = policy.config.get('blocked_patterns', [])
        
        for pattern in blocked_patterns:
            if re.search(pattern, context.content):
                return PolicyDecision.REVIEW  # HITL for human review
        
        return PolicyDecision.ALLOW
```

##### 4. Memory Orchestration Service

```python
# memory/orchestration_service.py
from enum import Enum

class MemoryLayer(Enum):
    WORKING = "working"    # Context window
    SEMANTIC = "semantic"  # L1 - ChromaDB
    LONGTERM = "longterm"  # L2 - Git/Markdown
    EPISODIC = "episodic"  # L3 - PostgreSQL

class MemoryOrchestrationService:
    """
    Domain Service for coordinating multi-layer memory.
    
    Coordinates retrieval and storage across L1, L2, L3
    with intelligent caching and invalidation.
    """
    
    def __init__(
        self,
        semantic_store: 'SemanticStore',
        longterm_store: 'LongTermStore',
        episodic_store: 'EpisodicStore'
    ):
        self.semantic = semantic_store
        self.longterm = longterm_store
        self.episodic = episodic_store
    
    async def retrieve(
        self,
        query: str,
        agent_id: UUID,
        layers: list[MemoryLayer] = None,
        limit: int = 10
    ) -> list[MemoryResult]:
        """Retrieve relevant memories from specified layers."""
        layers = layers or [MemoryLayer.SEMANTIC, MemoryLayer.EPISODIC]
        results = []
        
        if MemoryLayer.SEMANTIC in layers:
            semantic_results = await self.semantic.search(
                query=query,
                agent_id=agent_id,
                limit=limit
            )
            results.extend(semantic_results)
        
        if MemoryLayer.LONGTERM in layers:
            longterm_results = await self.longterm.search(
                query=query,
                agent_id=agent_id
            )
            results.extend(longterm_results)
        
        if MemoryLayer.EPISODIC in layers:
            episodic_results = await self.episodic.search(
                query=query,
                agent_id=agent_id,
                limit=limit
            )
            results.extend(episodic_results)
        
        # Rank and dedupe results
        return self._rank_results(results)
    
    async def store(
        self,
        content: str,
        agent_id: UUID,
        layer: MemoryLayer,
        importance: float = 0.5
    ) -> UUID:
        """Store a memory in the specified layer."""
        if layer == MemoryLayer.SEMANTIC:
            return await self.semantic.store(content, agent_id, importance)
        elif layer == MemoryLayer.LONGTERM:
            return await self.longterm.store(content, agent_id)
        elif layer == MemoryLayer.EPISODIC:
            return await self.episodic.store(content, agent_id)
        
        raise ValueError(f"Unknown memory layer: {layer}")
    
    def _rank_results(self, results: list[MemoryResult]) -> list[MemoryResult]:
        """Rank results by relevance and recency."""
        # Combined scoring algorithm
        return sorted(
            results,
            key=lambda r: r.score * 0.7 + r.recency_weight * 0.3,
            reverse=True
        )
```

### 2.4 Domain Events

Domain Events represent important state changes that other parts of the system need to know about.

#### Event Definitions

```python
# core/events/base.py
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
from abc import ABC

@dataclass
class DomainEvent(ABC):
    """Base class for all domain events."""
    event_id: UUID
    occurred_at: datetime
    aggregate_id: UUID
    aggregate_type: str

# ============================================================================
# Agent Events
# ============================================================================

@dataclass
class AgentCreatedEvent(DomainEvent):
    """Fired when a new agent is created."""
    name: str
    role: str
    model_provider: str
    model_name: str
    created_by: str

@dataclass
class AgentConfigurationChangedEvent(DomainEvent):
    """Fired when agent configuration is modified."""
    changed_fields: list[str]
    old_values: dict
    new_values: dict

@dataclass
class AgentStateChangedEvent(DomainEvent):
    """Fired when agent state transitions."""
    old_state: str
    new_state: str
    reason: str | None

@dataclass
class AgentLoRAAttachedEvent(DomainEvent):
    """Fired when a LoRA adapter is attached to an agent."""
    adapter_id: UUID
    adapter_name: str

@dataclass
class AgentLoRADetachedEvent(DomainEvent):
    """Fired when a LoRA adapter is removed from an agent."""
    adapter_id: UUID

# ============================================================================
# Session Events
# ============================================================================

@dataclass
class SessionCreatedEvent(DomainEvent):
    """Fired when a new session is started."""
    agent_id: UUID
    entity_id: UUID | None
    user_id: str

@dataclass
class SessionEndedEvent(DomainEvent):
    """Fired when a session ends."""
    final_status: str  # 'completed', 'failed', 'cancelled'
    total_tokens: int
    total_cost_usd: float

@dataclass
class MessageReceivedEvent(DomainEvent):
    """Fired when a message is received."""
    role: str
    content_preview: str  # Truncated for logging
    token_count: int

# ============================================================================
# Execution Events
# ============================================================================

@dataclass
class AgentExecutionStartedEvent(DomainEvent):
    """Fired when agent begins execution."""
    request_id: str
    max_iterations: int

@dataclass
class AgentExecutionCompletedEvent(DomainEvent):
    """Fired when agent completes execution."""
    iterations: int
    success: bool
    output_preview: str

@dataclass
class AgentIterationEvent(DomainEvent):
    """Fired after each agent iteration."""
    iteration: int
    thought_preview: str
    tool_calls: list[str]

@dataclass
class ToolExecutionStartedEvent(DomainEvent):
    """Fired when a tool begins execution."""
    tool_name: str
    requires_approval: bool

@dataclass
class ToolExecutionCompletedEvent(DomainEvent):
    """Fired when a tool completes."""
    tool_name: str
    success: bool
    duration_ms: int
    result_preview: str | None

@dataclass
class HitLApprovalRequestedEvent(DomainEvent):
    """Fired when HITL approval is needed."""
    tool_name: str
    action_type: str
    content_preview: str

@dataclass
class HitLApprovalDecisionEvent(DomainEvent):
    """Fired when HITL decision is made."""
    approval_id: UUID
    decision: str  # 'approved', 'rejected'
    reviewer_id: str | None

# ============================================================================
# Memory Events
# ============================================================================

@dataclass
class MemoryStoredEvent(DomainEvent):
    """Fired when a memory is stored."""
    layer: str  # 'semantic', 'longterm', 'episodic'
    content_preview: str

@dataclass
class MemoryRetrievedEvent(DomainEvent):
    """Fired when memory is retrieved."""
    layer: str
    result_count: int

@dataclass
class MemoryPrunedEvent(DomainEvent):
    """Fired when memories are pruned."""
    layer: str
    entry_count: int

# ============================================================================
# Learning Events
# ============================================================================

@dataclass
class STaRCycleStartedEvent(DomainEvent):
    """Fired when STaR self-improvement begins."""
    dataset_size: int

@dataclass
class STaRCycleCompletedEvent(DomainEvent):
    """Fired when STaR cycle completes."""
    examples_generated: int
    improvement_score: float

@dataclass
class LoRASwapStartedEvent(DomainEvent):
    """Fired when LoRA adapter swap begins."""
    old_adapter_id: UUID | None
    new_adapter_id: UUID

@dataclass
class LoRASwapCompletedEvent(DomainEvent):
    """Fired when LoRA adapter swap completes."""
    success: bool
    duration_ms: int

# ============================================================================
# Cost & Governance Events
# ============================================================================

@dataclass
class BudgetExceededEvent(DomainEvent):
    """Fired when a budget limit is exceeded."""
    budget_limit_usd: float
    current_spend_usd: float
    period: str  # 'daily', 'monthly'

@dataclass
class PolicyViolationEvent(DomainEvent):
    """Fired when a policy is violated."""
    policy_id: UUID
    policy_name: str
    violation_details: str

@dataclass
class CircuitBreakerOpenedEvent(DomainEvent):
    """Fired when a circuit breaker opens."""
    service_name: str
    failure_count: int

# ============================================================================
# Event Publishing
# ============================================================================

class EventPublisher:
    """Central event publishing service."""
    
    def __init__(self):
        self._handlers: dict[str, list[Callable]] = {}
        self._event_bus: asyncio.Queue = asyncio.Queue()
    
    async def publish(self, event: DomainEvent) -> None:
        """Publish an event to all subscribers."""
        await self._event_bus.put(event)
    
    def subscribe(
        self, 
        event_type: str, 
        handler: Callable[[DomainEvent], Awaitable]
    ) -> None:
        """Subscribe to an event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
    
    async def start(self) -> None:
        """Start processing events from the bus."""
        while True:
            event = await self._event_bus.get()
            await self._dispatch(event)
    
    async def _dispatch(self, event: DomainEvent) -> None:
        """Dispatch event to all handlers."""
        event_type = type(event).__name__
        
        for handler in self._handlers.get(event_type, []):
            try:
                await handler(event)
            except Exception as e:
                logger.error(f"Event handler failed: {e}", exc_info=True)
```

#### Event Handler Example

```python
# llmops/cost_event_handler.py

class CostTrackingEventHandler:
    """Handles events to track costs."""
    
    def __init__(self, cost_service: CostCalculationService):
        self.cost_service = cost_service
    
    async def handle(self, event: DomainEvent) -> None:
        """Handle events that affect cost tracking."""
        if isinstance(event, ToolExecutionCompletedEvent):
            await self._handle_tool_completion(event)
        elif isinstance(event, AgentExecutionCompletedEvent):
            await self._handle_agent_completion(event)
    
    async def _handle_tool_completion(
        self, 
        event: ToolExecutionCompletedEvent
    ) -> None:
        """Track cost of tool execution (if LLM call)."""
        # Record cost to database
        pass
```

---

## Appendix A: Module to Context Mapping

| Module | Context | Responsibility |
|--------|---------|----------------|
| `gateway/channels/*` | Gateway | Channel adapter implementations |
| `gateway/plugins/*` | Gateway | Plugin system |
| `gateway/auth/*` | Gateway | Authentication & authorization |
| `gateway/grpc/*` | Gateway | gRPC client to Core |
| `core/orchestration/*` | Core | Agent orchestration |
| `core/agents/*` | Core | Agent definitions |
| `core/entities/*` | Core | Entity composition |
| `core/tools/*` | Core | Tool system |
| `core/memory/*` | Memory | Memory orchestration |
| `core/learning/*` | Learning | Self-improvement |
| `core/llmops/*` | LLMOps | Observability |

---

## Appendix B: Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | April 14, 2026 | XenoSys Team | Initial development document |

---

*This document defines the strategic and tactical design for XenoSys using Domain-Driven Design principles. All code must conform to this specification.*