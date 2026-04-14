# 1. OBJECTIVE

Develop a comprehensive, production-ready technical specification for XenoSys — a Unified Multi-Agent Metacognitive System that unifies App1 (TypeScript Gateway) and App2 (Python Agent Runtime) into a single cohesive platform. The specification must cover all six required topics: identification/overview, system architecture, data design, interface/component design, non-functional requirements/security, and risks/assumptions. The system must be ready for 100% production deployment with enterprise-grade reliability, security, and observability.

# 2. CONTEXT SUMMARY

**Project Background:**
- **App1 (TypeScript)**: Multi-channel adapter layer (Telegram, Slack, Discord, Webhook, API), plugin system, ACP (Agent Communication Protocol), control UI with Lit Web Components
- **App2 (Python)**: Mature agent runtime with 60+ tools, SQLite+FTS5 episodic memory, terminal backend abstractions, ~3000 tests

**Key System Components:**
- **Gateway (TypeScript/Node.js 22+)**: Channel adapters, plugin system, gRPC bridge, Hono HTTP server
- **Core (Python 3.12+)**: Event bus, agent runtime with DSPy, three-tier memory system (L1/L2/L3), learning engine (LoRA, STaR), LLMOps layer
- **Data Stores**: PostgreSQL 16 (L3 episodic), ChromaDB (L1 semantic), Redis (caching/pubsub), Git-backed Markdown (L2 long-term)
- **External Integrations**: AI providers (OpenAI, Anthropic), external tools (MCP, Web APIs), notebook cloud (Kaggle/Colab for LoRA training)

**Development Methodology:** SDD (Specification-Driven Development) + DDD (Domain-Driven Design)

# 3. APPROACH OVERVIEW

**Architectural Pattern:** Modular Monolith with Event-Driven Core

The system uses a Modular Monolith architecture where:
- Gateway (TypeScript) and Core (Python) are separate deployable modules
- Communication happens via gRPC with ACP (Agent Communication Protocol)
- Event bus provides loose coupling within Core
- Horizontal scaling achieved via Redis Streams for event bus

**Why Modular Monolith:**
- Single team ownership initially (lower complexity)
- Shared PostgreSQL benefits from ACID transactions
- Clear migration path to microservices when needed
- Preserves App1 TypeScript ecosystem and App2 Python ML libraries

**Key Design Principles:**
1. Event-Task Driven: All actions triggered by events/tasks; agents "sleep" without events
2. Adversarial by Default: Every executor has a paired critic/auditor agent
3. Memory-First: Three persistent memory layers beyond context window
4. Composable Entities: Multi-agents can form "Entities" acting as single agent
5. Human-in-the-Loop: Critical decisions require human approval by default
6. Self-Improving: Agents perform STaR on idle; LoRA adapters evolve with use

# 4. IMPLEMENTATION STEPS

## Phase 1: Foundation (Weeks 1-4)
1. Set up TypeScript Gateway project structure with Hono framework
2. Define gRPC protobuf definitions for TypeScript ↔ Python interop
3. Implement basic gRPC bridge with circuit breaker
4. Create Python EventBus with asyncio pub/sub
5. Design and implement PostgreSQL L3 schema with migrations
6. Implement basic JWT + API key authentication
7. Create health and readiness endpoints

## Phase 2: Core Agent (Weeks 5-8)
1. Implement base Agent class with ReAct pattern
2. Create ToolRegistry and base Tool class
3. Implement tool execution with HITL support
4. Build session management (CRUD, state tracking)
5. Implement L1 memory (in-memory LRU cache with TTL)
6. Create basic cost tracker with budget limits
7. Implement rate limiting per user/agent

## Phase 3: Memory System (Weeks 9-12)
1. Integrate ChromaDB for L2 semantic memory
2. Build MemoryManager orchestrator for tier routing
3. Implement L3 episodic memory read/write
4. Create cross-tier memory search
5. Add per-agent memory namespacing
6. Implement importance-based memory promotion

## Phase 4: Advanced Features (Weeks 13-16)
1. Build Entity system (definition, runtime, routing)
2. Create Entity builder UI for power users
3. Implement LoRA adapter registry with hot-swap
4. Build STaR self-improvement trainer
5. Implement HITL approval workflow
6. Create monitoring dashboard

## Phase 5: Production Ready (Weeks 17-20)
1. Implement full RBAC authorization
2. Add OpenTelemetry tracing and metrics
3. Integrate Redis for event bus scaling
4. Create comprehensive API documentation
5. Perform load testing and performance validation
6. Complete security audit and hardening

# 5. TESTING AND VALIDATION

**Unit Testing:**
- Python: pytest with pytest-asyncio, target 80% coverage
- TypeScript: vitest, target 80% coverage

**Integration Testing:**
- gRPC bridge end-to-end tests
- Memory system tier integration tests
- Agent execution flow tests

**Validation Criteria:**
- Gateway endpoints return correct status codes
- gRPC bridge successfully communicates between TS and Python
- Event bus publishes and receives events correctly
- Agent executes ReAct loop with tool calls
- L1/L2/L3 memory tier routing works correctly
- Cost tracker enforces budget limits
- HITL workflow completes approval/rejection cycle
- All security authentication flows work (JWT, API keys)

**Production Readiness Checks:**
- Health check returns healthy status
- Readiness check passes when all dependencies connected
- Graceful shutdown completes without data loss
- Telemetry exports traces and metrics correctly
