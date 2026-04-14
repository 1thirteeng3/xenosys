# XenoSys — Unified Multi-Agent System
## Technical Specifications Document

**Version:** 1.0  
**Date:** April 14, 2026  
**Classification:** Technical Architecture Document  
**Authors:** XenoSys Development Team  
**Status:** Production Ready

---

## Table of Contents

1. [Identification and Overview](#1-identification-and-overview)
2. [System Architecture](#2-system-architecture)
3. [Data Design (Persistence)](#3-data-design-persistence)
4. [Interface and Component Design](#4-interface-and-component-design)
5. [Non-Functional Requirements and Security](#5-non-functional-requirements-and-security)
6. [Risks and Assumptions](#6-risks-and-assumptions)

---

## 1. Identification and Overview

### 1.1 System Scope

**XenoSys** is a unified multi-agent metacognitive system that unifies two existing applications (App1 - TypeScript Gateway and App2 - Python Agent) into a single, cohesive platform. The system provides:

- **Multi-Agent Orchestration**: Runtime for managing multiple autonomous agents with adversarial pairing (executor + critic)
- **Multi-Layer Memory System**: Three persistent memory layers beyond context window (Semantic L1, Long-term L2, Episodic L3) plus working memory
- **Self-Improvement Capabilities**: STaR (Self-Taught Reasoning) implementation and LoRA adapter evolution
- **Unified Gateway**: TypeScript-based channel adapters, plugin system, and ACP (Agent Communication Protocol)
- **LLMOps Governance**: Telemetry, cost tracking, policy enforcement, and Human-in-the-Loop (HITL) approval workflows

The system acts as an intelligent orchestration layer that bridges multiple AI providers (OpenAI, Anthropic, Local LLMs) with external tools and notebook cloud environments for training.

### 1.2 Context and Ecosystem Integration

XenoSys integrates with the following external systems:

| External System | Integration Type | Purpose |
|-----------------|------------------|---------|
| **AI Providers** | gRPC / REST API | OpenAI, Anthropic, Local LLM inference |
| **MCP (Model Context Protocol)** | gRPC | External tool orchestration |
| **Web Tools** | HTTP API | Browser automation, web scraping |
| **Kaggle/Colab API** | REST API | LoRA adapter training pipelines |
| **PostgreSQL 16** | asyncpg | L3 Episodic Memory persistence |
| **ChromaDB** | Python Client | L1 Semantic Memory vector storage |
| **Git Infrastructure** | Git CLI/API | L2 Long-term Memory versioning |
| **Redis Streams** | Redis Client | Event bus scaling and pub/sub |
| **Jaeger/Grafana** | OpenTelemetry | Distributed tracing and monitoring |

### 1.3 Design Objectives

The architecture prioritizes the following objectives in order of importance:

| Priority | Objective | Description |
|----------|-----------|--------------|
| **1** | **Security First** | Prompt injection defense, RBAC, MFA, encryption at rest/transit, adversarial security auditing |
| **2** | **Observability** | Full OpenTelemetry integration, granular cost tracking, audit logging |
| **3** | **Resilience** | Circuit breakers, graceful degradation, failover strategies |
| **4** | **Extensibility** | Plugin system, capability contracts, entity composition |
| **5** | **Performance** | Sub-100ms response for gateway, efficient memory retrieval |
| **6** | **Self-Improvement** | STaR implementation, LoRA hot-swap, continuous learning |

### 1.4 Architectural Unification Strategy

The system unifies two legacy applications:

**App1 (TypeScript/Node.js 22+)** contributes:
- Gateway de canais tipado e extensível (20+ channel adapters)
- Plugin system com registry público
- Capability contracts para terceiros
- ACP (Agent Communication Protocol) server
- Control UI em Lit Web Components
- Hono HTTP/WS server

**App2 (Python 3.12+)** contributes:
- Agent runtime maduro (error classification, retry, rate limiting)
- Sistema de ferramentas robusto (60+ tools)
- SQLite + FTS5 para episodic memory
- Abstrações de terminal backends
- ~3000 testes como base de confiança
- DSPy-based agent foundation

**Bridge Strategy:** gRPC + Protocol Buffers with ACP over gRPC for type-safe cross-language communication.

---

## 2. System Architecture

### 2.1 Architectural Pattern

**Primary Pattern:** Modular Monolith with Event-Driven Interiors  
**Secondary Pattern:** Microservices-ready (preparation for horizontal scaling)

The system employs a **Modular Monolith** architecture where:
- The TypeScript Gateway and Python Core are separate processes but tightly integrated
- Internal modules within each process follow domain-driven design
- Event bus enables loose coupling between modules
- Clear bounded contexts with well-defined interfaces

This pattern was chosen over pure microservices to reduce operational complexity while maintaining separation of concerns, and over monolithic to allow independent scaling of gateway vs. agent runtime.

### 2.2 Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                              XENOSYS SYSTEM                                       │
│                                                                                  │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                         USER SURFACE LAYER                               │   │
│  │   Control UI (Lit) │ CLI │ Mobile SDK │ REST API │ Messaging Channels    │   │
│  └────────────────────────────────┬───────────────────────────────────────────┘   │
│                                   │                                              │
│  ┌────────────────────────────────▼───────────────────────────────────────────┐   │
│  │                    UNIFIED GATEWAY (TypeScript/Node.js 22+)               │   │
│  │                                                                             │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐    │   │
│  │  │  Channels   │  │   Plugins   │  │   ACP Srv   │  │   gRPC Bridge   │    │   │
│  │  │   Adapters  │  │  Registry   │  │    (80+)    │  │   to Python     │    │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────┘    │   │
│  │                                                                             │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐    │   │
│  │  │    Auth     │  │   Session   │  │    Rate     │  │   Telemetry     │    │   │
│  │  │  (JWT/MFA)  │  │   Manager   │  │   Limiter   │  │   Exporter      │    │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────┘    │   │
│  └────────────────────────────────┬───────────────────────────────────────────┘   │
│                                   │ gRPC / ACP                                   │
│  ┌────────────────────────────────▼───────────────────────────────────────────┐   │
│  │                  ORCHESTRATION BUS (Python/asyncio)                        │   │
│  │                                                                             │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐    │   │
│  │  │  Event Bus  │  │  Task Queue │  │   Entity    │  │  Lifecycle      │    │   │
│  │  │  (async)    │  │  (Priority) │  │   Router    │  │    Manager      │    │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────┘    │   │
│  └────────────────────────────┬─────────────────────────────────────────────────┘   │
│                               │                                                 │
│  ┌────────────────────────────┼─────────────────────────────────────────────────┐ │
│  │                            │                                                 │ │
│  │  ┌─────────────────────────▼─────────────────────────────────────────────┐ │ │
│  │  │                         AGENT RUNTIME                                  │ │ │
│  │  │                                                                         │ │ │
│  │  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │ │ │
│  │  │  │ Base Agent  │  │ Adversarial │  │   Agent     │  │   Parallel  │  │ │ │
│  │  │  │  (DSPy)     │  │   Pairs     │  │   Registry  │  │   Executor  │  │ │ │
│  │  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │ │ │
│  │  │                                                                         │ │ │
│  │  │  ┌──────────────────────────────────────────────────────────────────┐  │ │ │
│  │  │  │                        TOOLS SYSTEM (60+)                       │  │ │ │
│  │  │  │  Terminal │ FileOps │ WebScraper │ MCP │ Custom Plugins        │  │ │ │
│  │  │  └──────────────────────────────────────────────────────────────────┘  │ │ │
│  │  └──────────────────────────────────────────────────────────────────────────┘ │ │
│  │                                                                                  │
│  │  ┌─────────────────────────▼─────────────────────────────────────────────┐    │
│  │  │                        MEMORY SYSTEM                                  │    │
│  │  │                                                                         │    │
│  │  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │    │
│  │  │  │   Working   │  │     L1      │  │     L2      │  │     L3      │   │    │
│  │  │  │   Memory    │  │  Semantic   │  │ Long-term   │  │  Episodic   │   │    │
│  │  │  │ (Context)   │  │  (ChromaDB) │  │  (Git/MD)   │  │   (Postgre) │   │    │
│  │  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘   │    │
│  │  │           │              │              │              │                │    │
│  │  │           └──────────────┴──────────────┴──────────────┘                │    │
│  │  │                              │                                        │    │
│  │  │                    ┌───────────▼───────────┐                            │    │
│  │  │                    │  Memory Orchestrator │                            │    │
│  │  │                    └───────────────────────┘                            │    │
│  │  └─────────────────────────────────────────────────────────────────────────┘    │
│  │                                                                                  │
│  │  ┌─────────────────────────▼─────────────────────────────────────────────┐    │
│  │  │                      LEARNING ENGINE                                   │    │
│  │  │                                                                         │    │
│  │  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │    │
│  │  │  │    LoRA    │  │  Dreaming   │  │    STaR    │  │  DSPy Opt   │   │    │
│  │  │  │  Registry  │  │  (Idle)     │  │  (Self-Imp) │  │  (Compile)  │   │    │
│  │  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘   │    │
│  │  └─────────────────────────────────────────────────────────────────────────┘    │
│  └────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                      │
│  ┌────────────────────────────────────────────────────────────────────────────────┐ │
│  │                          LLMOPS LAYER                                          │ │
│  │                                                                                │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │ │
│  │  │  Telemetry  │  │ Cost Tracker│  │ Governance  │  │    HITL     │          │ │
│  │  │(OpenTelemetry)│ (Per-Agent) │ (Policy Eng) │  │  (Approval) │          │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘          │ │
│  │                                                                                │ │
│  │  ┌──────────────────────────────────────────────────────────────────────┐   │ │
│  │  │                       State Manager                                  │   │ │
│  │  │                   (Distributed Persistence)                          │   │ │
│  │  └──────────────────────────────────────────────────────────────────────┘   │ │
│  └────────────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────────────┘
                                        │
              ┌─────────────────────────┼─────────────────────────┐
              ▼                         ▼                         ▼
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│    AI PROVIDERS     │    │  EXTERNAL TOOLS     │    │   NOTEBOOK CLOUD    │
│                     │    │                     │    │                     │
│  OpenAI (GPT-4o)    │    │  MCP Servers       │    │  Kaggle API         │
│  Anthropic (Claude) │    │  Web APIs           │    │  Google Colab       │
│  Local LLMs (llama) │    │  Browserbase        │    │  (LoRA Training)    │
└─────────────────────┘    └─────────────────────┘    └─────────────────────┘
```

### 2.3 Container-Level Architecture

```
nexus/
├── gateway/                    # TypeScript (Node.js 22+) — App1 fork
│   ├── src/
│   │   ├── channels/           # 20+ channel adapters (Slack, Discord, Teams, etc.)
│   │   ├── plugins/            # Plugin system + registry
│   │   ├── plugin-sdk/         # Public extension API
│   │   ├── acp/                # Agent Communication Protocol
│   │   ├── grpc/               # gRPC bridge to Python runtime
│   │   ├── gateway/            # HTTP/WS server (Hono)
│   │   └── auth/               # JWT, MFA, RBAC handlers
│   └── ui/                     # Lit Web Components dashboard
│
├── core/                       # Python 3.12+ — App2 fork + extensions
│   ├── orchestration/
│   │   ├── event_bus.py        # AsyncIO event bus
│   │   ├── task_queue.py       # Priority task queue
│   │   ├── entity_router.py    # Entity → agent mapping
│   │   └── lifecycle.py        # Agent lifecycle FSM
│   │
│   ├── agents/
│   │   ├── base_agent.py       # DSPy-based base agent
│   │   ├── adversarial.py      # Critic/auditor agent wrapper
│   │   ├── registry.py         # Agent registry
│   │   ├── identity.py         # System prompt management
│   │   └── parallel.py         # Parallel execution engine
│   │
│   ├── memory/
│   │   ├── orchestrator.py     # Memory layer coordinator
│   │   ├── l1_semantic/        # LLM-wiki / Obsidian-like
│   │   │   ├── vault.py        # Note graph manager
│   │   │   ├── embedder.py     # Vectorization pipeline (sentence-transformers)
│   │   │   └── retriever.py    # Semantic search
│   │   ├── l2_longterm/        # OpenViking system-file
│   │   │   ├── filesystem.py   # Hierarchical file system abstraction
│   │   │   ├── compressor.py   # LLM-based compression
│   │   │   └── indexer.py      # Content indexing
│   │   ├── l3_episodic/        # Relational DB
│   │   │   ├── models.py       # SQLAlchemy models
│   │   │   ├── session_db.py   # Session storage (FTS5)
│   │   │   └── timeline.py     # Episodic timeline queries
│   │   └── working_memory.py   # Context window management
│   │
│   ├── entities/
│   │   ├── entity.py           # Entity data model
│   │   ├── builder.py          # Entity builder DSL
│   │   ├── runtime.py          # Entity execution engine
│   │   └── templates/          # Built-in entity templates
│   │
│   ├── learning/
│   │   ├── lora/
│   │   │   ├── registry.py     # LoRA adapter registry
│   │   │   ├── swap.py         # Hot-swap adapter mechanism
│   │   │   └── trainer.py      # Notebook cloud integration
│   │   ├── dreaming/
│   │   │   ├── scheduler.py    # Idle detection + scheduling
│   │   │   ├── star.py         # STaR implementation
│   │   │   └── evaluator.py    # Self-evaluation scoring
│   │   └── dspy_optimizer.py   # DSPy program optimization
│   │
│   ├── tools/                  # App2 tools (60+ preserved)
│   │   └── [tool modules]
│   │
│   └── llmops/
│       ├── telemetry.py        # OpenTelemetry integration
│       ├── cost_tracker.py     # Per-agent cost accounting
│       ├── governance.py       # Policy engine
│       ├── hitl.py             # Human-in-the-loop manager
│       └── state_manager.py    # Distributed state persistence
│
└── notebooks/                  # Training pipelines
    ├── lora_finetune.ipynb     # Generic LoRA trainer
    ├── star_dataset.ipynb      # STaR dataset generator
    └── eval_benchmark.ipynb    # Agent evaluation
```

### 2.4 Architectural Justification

| Decision | Justification |
|----------|---------------|
| **Modular Monolith** | Reduces operational complexity vs microservices while maintaining domain separation. Allows independent scaling of gateway vs. agent runtime. |
| **TypeScript Gateway + Python Core** | Preserves App1 strengths (channel adapters, plugins) and App2 strengths (agent runtime, tools, DSPy). Natural I/O-bound vs CPU-bound separation. |
| **gRPC Bridge** | Type-safe cross-language communication, efficient binary serialization, native code generation from Protocol Buffers. |
| **Event-Driven Orchestration** | Loose coupling between components, natural fit for async agent execution, enables parallel processing and scaling. |
| **Multi-Layer Memory** | Addresses LLM context window limitations with persistent, queryable memory layers at different abstraction levels. |
| **Adversarial Agent Pairs** | Built-in security and quality assurance - every executor has a critic/auditor for self-correction. |
| **PostgreSQL + FTS5** | ACID compliance for episodic memory, full-text search without separate infrastructure, JSONB for flexible schema. |
| **ChromaDB for L1** | Native Python support, efficient vector search, integrated embedding models. |
| **Git-based L2** | Version control built-in, Markdown is LLM-friendly, mature tooling. |

---

## 3. Data Design (Persistence)

### 3.1 Data Model

#### 3.1.1 L3 Episodic Memory (PostgreSQL Schema)

```sql
-- Core tables for episodic memory (L3)

-- Agents
CREATE TABLE agents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    type VARCHAR(50) NOT NULL, -- 'executor', 'critic', 'hybrid'
    system_prompt TEXT,
    model_provider VARCHAR(50),
    model_name VARCHAR(100),
    lora_adapter_id UUID,
    memory_vault_id UUID,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE
);

-- Sessions
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID NOT NULL REFERENCES agents(id),
    entity_id UUID,
    user_id VARCHAR(255),
    started_at TIMESTAMP DEFAULT NOW(),
    ended_at TIMESTAMP,
    status VARCHAR(50) DEFAULT 'active', -- 'active', 'completed', 'failed'
    total_tokens_in INTEGER DEFAULT 0,
    total_tokens_out INTEGER DEFAULT 0,
    total_cost_usd DECIMAL(10, 6) DEFAULT 0,
    metadata JSONB DEFAULT '{}'
);

-- Messages (FTS5 indexed)
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES sessions(id),
    role VARCHAR(20) NOT NULL, -- 'user', 'assistant', 'system', 'tool'
    content TEXT NOT NULL,
    model VARCHAR(100),
    tokens_in INTEGER,
    tokens_out INTEGER,
    cost_usd DECIMAL(10, 6),
    latency_ms INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

-- Full-text search index
CREATE INDEX idx_messages_fts ON messages USING GIN(to_tsvector('english', content));
CREATE INDEX idx_messages_session ON messages(session_id);
CREATE INDEX idx_messages_created ON messages(created_at DESC);

-- Memory entries
CREATE TABLE memory_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID NOT NULL REFERENCES agents(id),
    memory_type VARCHAR(20) NOT NULL, -- 'semantic', 'longterm', 'episodic'
    content TEXT NOT NULL,
    embedding VECTOR(384), -- sentence-transformers default
    importance_score DECIMAL(3, 2) DEFAULT 0.5,
    created_at TIMESTAMP DEFAULT NOW(),
    accessed_at TIMESTAMP,
    access_count INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}'
);

-- Entities
CREATE TABLE entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    agent_ids UUID[] NOT NULL,
    routing_strategy VARCHAR(50) DEFAULT 'semantic', -- 'semantic', 'sequential', 'parallel'
    max_rounds INTEGER DEFAULT 3,
    memory_config JSONB DEFAULT '{"l1": null, "l2": null, "l3": null}',
    created_by VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE
);

-- LoRA Adapters
CREATE TABLE lora_adapters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    model_base VARCHAR(100) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    version INTEGER DEFAULT 1,
    accuracy_score DECIMAL(5, 4),
    training_dataset_id UUID,
    trained_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    metadata JSONB DEFAULT '{}'
);

-- Cost Records
CREATE TABLE cost_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID REFERENCES agents(id),
    entity_id UUID REFERENCES entities(id),
    session_id UUID REFERENCES sessions(id),
    user_id VARCHAR(255),
    model VARCHAR(100) NOT NULL,
    tokens_in INTEGER NOT NULL,
    tokens_out INTEGER NOT NULL,
    cost_usd DECIMAL(10, 6) NOT NULL,
    timestamp TIMESTAMP DEFAULT NOW()
);

-- Governance Policies
CREATE TABLE policies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    rule_type VARCHAR(50) NOT NULL, -- 'rate_limit', 'budget', 'content_filter'
    rule_config JSONB NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    priority INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- HITL Approvals
CREATE TABLE hitl_approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES sessions(id),
    action_type VARCHAR(100) NOT NULL,
    proposed_content TEXT,
    status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'approved', 'rejected'
    reviewer_id VARCHAR(255),
    reviewed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
```

#### 3.1.2 L1 Semantic Memory (ChromaDB Collections)

| Collection | Dimensions | Description |
|------------|------------|-------------|
| `semantic_notes` | 384 | User notes and documentation |
| `knowledge_graph` | 384 | Structured knowledge from LLM |
| `agent_memories` | 384 | Agent-specific learnings |
| `entity_context` | 384 | Entity composition context |

#### 3.1.3 L2 Long-term Memory (File System)

```
memory/l2/
├── users/
│   └── {user_id}/
│       ├── projects/
│       │   └── {project_id}/
│       │       ├── index.md
│       │       └── notes/
│       └── knowledge/
│           └── {topic}/
│               └── content.md
├── agents/
│   └── {agent_id}/
│       ├── learnings/
│       │   └── {topic}.md
│       └── configurations/
│           └── {config}.md
└── system/
    └── policies/
        └── {policy_id}.md
```

### 3.2 Data Dictionary

#### Critical Fields Definition

| Field | Table | Type | Description | Constraints |
|-------|-------|------|-------------|-------------|
| `id` | All | UUID | Unique identifier | Primary key, auto-generated |
| `agent_id` | sessions, messages, memory_entries | UUID | Reference to agent | Foreign key, not null |
| `entity_id` | sessions, entities, cost_records | UUID | Reference to entity | Foreign key, nullable |
| `session_id` | messages, hitl_approvals | UUID | Reference to session | Foreign key, not null |
| `user_id` | sessions, cost_records | VARCHAR(255) | User identifier | For cost attribution |
| `content` | messages, memory_entries | TEXT | Main content | Not null, max 1MB |
| `embedding` | memory_entries | VECTOR(384) | Semantic vector | For similarity search |
| `lora_adapter_id` | agents | UUID | Reference to LoRA | Foreign key, nullable |
| `metadata` | All tables | JSONB | Flexible key-value | Default '{}' |
| `system_prompt` | agents | TEXT | Agent instruction set | Max 32KB |
| `routing_strategy` | entities | VARCHAR(50) | Entity routing type | 'semantic', 'sequential', 'parallel' |
| `cost_usd` | sessions, cost_records | DECIMAL(10,6) | Cost in USD | >= 0, precision 6 |
| `tokens_in` | messages, cost_records | INTEGER | Input tokens | >= 0 |
| `tokens_out` | messages, cost_records | INTEGER | Output tokens | >= 0 |

### 3.3 Storage Strategy

| Data Type | Storage | Rationale |
|-----------|---------|-----------|
| **Session History** | PostgreSQL (L3) | ACID compliance, FTS5 for search, JSONB for metadata |
| **Message Log** | PostgreSQL (L3) | Time-series, efficient queries, cost tracking |
| **Semantic Embeddings** | ChromaDB (L1) | Vector similarity search, integrated embedding |
| **Knowledge Docs** | Git + Markdown (L2) | Version control, LLM-friendly, hierarchical |
| **Agent Configs** | Git + YAML (L2) | Version control, declarative |
| **LoRA Adapters** | S3/Local FS | Binary files, versioning, hot-swap ready |
| **Event Streams** | Redis Streams | Pub/sub, ordering, replay capability |
| **Cache** | Redis | Session cache, rate limiting, temporary state |
| **File Uploads** | S3-compatible | Large files, attachments, media |

---

## 4. Interface and Component Design

### 4.1 Modular Decomposition

#### 4.1.1 Gateway Module (TypeScript)

| Component | Responsibility | Public API |
|-----------|---------------|------------|
| `ChannelAdapter` | Abstraction for messaging platforms | `send()`, `receive()`, `subscribe()` |
| `PluginRegistry` | Plugin lifecycle management | `register()`, `unload()`, `getPlugin()` |
| `ACPHandler` | Agent Communication Protocol | `handleMessage()`, `routeToAgent()` |
| `GRPCClient` | Bridge to Python runtime | `invokeAgent()`, `streamEvents()` |
| `AuthManager` | JWT validation, MFA | `authenticate()`, `authorize()` |
| `SessionManager` | User session state | `create()`, `resume()`, `invalidate()` |
| `RateLimiter` | Per-user, per-agent limits | `checkLimit()`, `consume()` |

#### 4.1.2 Core Module (Python)

| Component | Responsibility | Public API |
|-----------|---------------|------------|
| `EventBus` | Async event distribution | `publish()`, `subscribe()`, `unsubscribe()` |
| `TaskQueue` | Priority task scheduling | `enqueue()`, `dequeue()`, `schedule()` |
| `EntityRouter` | Route requests to entities | `route()`, `resolve()` |
| `LifecycleManager` | Agent state machine | `start()`, `stop()`, `pause()`, `resume()` |
| `BaseAgent` | DSPy-based agent core | `run()`, `execute()`, `evaluate()` |
| `AdversarialPair` | Executor + Critic pairing | `executeWithCritique()` |
| `AgentRegistry` | Agent CRUD, discovery | `register()`, `get()`, `list()` |
| `MemoryOrchestrator` | Multi-layer memory coordination | `store()`, `retrieve()`, `search()` |
| `LoRASwapper` | Hot-swap LoRA adapters | `load()`, `unload()`, `swap()` |
| `DreamingScheduler` | Idle detection, STaR scheduling | `scheduleDream()`, `runSTAR()` |
| `CostTracker` | Per-agent cost accounting | `record()`, `dashboard()`, `enforceBudget()` |
| `PolicyEngine` | Governance rule enforcement | `evaluate()`, `enforce()` |
| `HITLManager` | Human approval workflow | `requestApproval()`, `review()` |

### 4.2 API Design

#### 4.2.1 Gateway REST API

| Method | Endpoint | Description | Request Body | Response |
|--------|----------|-------------|--------------|----------|
| `POST` | `/api/v1/agents` | Create agent | `{name, type, systemPrompt, model}` | `{id, status}` |
| `GET` | `/api/v1/agents` | List agents | - | `{agents[]}` |
| `GET` | `/api/v1/agents/{id}` | Get agent | - | `{agent}` |
| `PUT` | `/api/v1/agents/{id}` | Update agent | `{systemPrompt, model}` | `{agent}` |
| `DELETE` | `/api/v1/agents/{id}` | Delete agent | - | `{status}` |
| `POST` | `/api/v1/agents/{id}/execute` | Execute agent | `{input, sessionId}` | `{output, sessionId}` |
| `POST` | `/api/v1/entities` | Create entity | `{name, agentIds, routingStrategy}` | `{id, status}` |
| `GET` | `/api/v1/entities` | List entities | - | `{entities[]}` |
| `POST` | `/api/v1/entities/{id}/execute` | Execute entity | `{input}` | `{output}` |
| `GET` | `/api/v1/sessions/{id}` | Get session | - | `{session, messages[]}` |
| `GET` | `/api/v1/memory/search` | Search memory | `{query, layer, limit}` | `{results[]}` |
| `GET` | `/api/v1/costs/dashboard` | Cost dashboard | - | `{dashboard}` |
| `POST` | `/api/v1/hitl/approve` | Approve HITL | `{approvalId, decision}` | `{status}` |

#### 4.2.2 gRPC Bridge API

```protobuf
// Agent service
service AgentService {
  rpc ExecuteAgent (ExecuteAgentRequest) returns (ExecuteAgentResponse);
  rpc StreamExecute (ExecuteAgentRequest) returns (stream StreamChunk);
  rpc GetAgent (GetAgentRequest) returns (Agent);
  rpc ListAgents (ListAgentsRequest) returns (ListAgentsResponse);
}

// Entity service
service EntityService {
  rpc ExecuteEntity (ExecuteEntityRequest) returns (ExecuteEntityResponse);
  rpc StreamExecute (ExecuteEntityRequest) returns (stream StreamChunk);
}

// Memory service
service MemoryService {
  rpc Store (StoreMemoryRequest) returns (StoreMemoryResponse);
  rpc Retrieve (RetrieveMemoryRequest) returns (RetrieveMemoryResponse);
  rpc Search (SearchMemoryRequest) returns (SearchMemoryResponse);
}

// Event service
service EventService {
  rpc Subscribe (SubscribeRequest) returns (stream Event);
  rpc Publish (PublishRequest) returns (PublishResponse);
}
```

#### 4.2.3 ACP (Agent Communication Protocol)

| Message Type | Direction | Payload |
|--------------|-----------|---------|
| `EXECUTE` | Gateway → Core | `{task, context, sessionId}` |
| `RESULT` | Core → Gateway | `{output, metadata}` |
| `ERROR` | Core → Gateway | `{error, code, details}` |
| `EVENT` | Core → Gateway | `{type, data}` |
| `APPROVAL_REQUEST` | Core → Gateway | `{action, content, approvalId}` |

### 4.3 Logical Flows

#### 4.3.1 Agent Execution Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│    User     │────▶│   Gateway   │────▶│  gRPC Bridge│────▶│   Event Bus │
└─────────────┘     └─────────────┘     └─────────────┘     └──────┬──────┘
                                                                   │
                                                                   ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌──────┴──────┐
│    User     │◀────│   Gateway   │◀────│  gRPC Bridge│◀────│  Task Queue │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                                                                   │
                                              ┌──────────────────┴──────┐
                                              ▼                         ▼
                                      ┌─────────────┐          ┌─────────────┐
                                      │ Base Agent  │────────▶│   Tools     │
                                      │ (Executor)  │          │  (60+)      │
                                      └──────┬──────┘          └─────────────┘
                                             │
                                             ▼
                                      ┌─────────────┐
                                      │  Adversarial│
                                      │    Pair     │
                                      │  (Critic)   │
                                      └──────┬──────┘
                                             │
                                             ▼
                                      ┌─────────────┐     ┌─────────────┐
                                      │   Memory    │────▶│  L3 (Postgres)│
                                      │  Orchestrator│    └─────────────┘
                                      └─────────────┘
```

#### 4.3.2 Entity Composition Flow

```
┌─────────────┐
│   Request   │
└──────┬──────┘
       │
       ▼
┌─────────────┐     ┌─────────────────┐
│   Entity   │────▶│ Entity Router   │
│   Router    │     │ (semantic/seq) │
└──────┬──────┘     └────────┬────────┘
       │                     │
       │      ┌──────────────┼──────────────┐
       ▼      ▼              ▼              ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│   Agent 1   │ │   Agent 2   │ │   Agent N   │
│ (Executor)  │ │(Adversarial)│ │  (Parallel) │
└──────┬──────┘ └──────┬──────┘ └──────┬──────┘
       │              │              │
       │    ┌─────────┴──────────┐   │
       └────▶   Result Aggregator  ◀───┘
              └────────────────────┘
                       │
                       ▼
              ┌─────────────┐
              │   Response  │
              └─────────────┘
```

#### 4.3.3 Self-Improvement (STaR) Flow

```
┌─────────────────┐
│  Agent Idle     │
│  (No events)     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│ Dreaming        │────▶│ Extract from L3 │
│ Scheduler       │     │ (past sessions) │
└────────┬────────┘     └────────┬────────┘
         │                       │
         ▼                       ▼
┌─────────────────┐     ┌─────────────────┐
│ Generate STaR   │     │  LLM generates  │
│ Dataset         │     │  rationales     │
└────────┬────────┘     └────────┬────────┘
         │                       │
         └───────────┬───────────┘
                     │
                     ▼
            ┌─────────────────┐
            │ Fine-tune LoRA  │
            │ (Kaggle/Colab)  │
            └────────┬────────┘
                     │
                     ▼
            ┌─────────────────┐
            │ Hot-swap LoRA   │
            │ in Agent        │
            └─────────────────┘
```

### 4.4 Component Interaction Diagrams

#### 4.4.1 Gateway to Core Communication

```
┌─────────────────────────────────────────────────────────────────┐
│                        GATEWAY (TypeScript)                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   │
│  │  HTTP    │   │  WebSocket│  │  gRPC    │   │   ACP    │   │
│  │  Server  │   │  Handler  │  │  Client  │   │  Parser  │   │
│  └────┬─────┘   └────┬─────┘   └────┬─────┘   └────┬─────┘   │
│       │              │              │              │          │
│       └──────────────┴──────────────┴──────────────┘          │
│                              │                                   │
│                     ┌────────▼────────┐                        │
│                     │   Auth Layer    │                        │
│                     │  (JWT, MFA, RBAC)│                        │
│                     └────────┬────────┘                        │
└──────────────────────────────┼──────────────────────────────────┘
                               │ gRPC / ACP
┌──────────────────────────────┼──────────────────────────────────┐
│                        CORE (Python)                             │
├──────────────────────────────┼──────────────────────────────────┤
│                     ┌────────▼────────┐                        │
│                     │   gRPC Server   │                        │
│                     └────────┬────────┘                        │
│                              │                                   │
│       ┌──────────────────────┼──────────────────────┐            │
│       │                      │                      │            │
│  ┌────▼────┐           ┌─────▼─────┐         ┌────▼────┐       │
│  │  Event  │           │  Task     │         │  ACP    │       │
│  │   Bus   │           │  Queue    │         │ Handler │       │
│  └────┬────┘           └─────┬─────┘         └─────────┘       │
│       │                      │                                    │
│       └──────────────────────┴────────────────────────────────┐  │
│                                                              │  │
│  ┌─────────────────────────────────────────────────────────┐  │  │
│  │                    AGENT EXECUTION                      │  │  │
│  │                                                         │  │  │
│  │  ┌──────────┐   ┌──────────┐   ┌──────────┐          │  │  │
│  │  │  Agent   │──▶│  Memory  │──▶│  Tools   │          │  │  │
│  │  │  Runtime │   │  System  │   │  System  │          │  │  │
│  │  └──────────┘   └──────────┘   └──────────┘          │  │  │
│  │       │              │              │                 │  │  │
│  │       └──────────────┴──────────────┘                 │  │  │
│  │                      │                                  │  │  │
│  │              ┌───────▼───────┐                         │  │  │
│  │              │  LLMOps Layer │                         │  │  │
│  │              │ (Telemetry,   │                         │  │  │
│  │              │  Cost, Gov)   │                         │  │  │
│  │              └───────────────┘                         │  │  │
│  └─────────────────────────────────────────────────────────┘  │  │
└───────────────────────────────────────────────────────────────┘  │
```

---

## 5. Non-Functional Requirements and Security

### 5.1 Security Architecture

#### 5.1.1 Authentication

| Method | Implementation | Use Case |
|--------|---------------|----------|
| **JWT** | RS256 tokens with short expiry (15min) | API authentication |
| **API Keys** | HMAC-signed keys for service-to-service | Internal services |
| **MFA** | TOTP (Time-based One-Time Password) | Admin access, high-risk actions |
| **OAuth 2.0** | OAuth 2.0 + OIDC for third-party integration | External channel adapters |

#### 5.1.2 Authorization (RBAC)

| Role | Permissions |
|------|-------------|
| `admin` | Full system access, user management, policy configuration |
| `power_user` | Entity creation, agent configuration, cost dashboard access |
| `user` | Execute predefined entities, view own sessions |
| `viewer` | Read-only access to dashboards |
| `service` | System-level operations, no user data access |

#### 5.1.3 Security Controls

| Control | Implementation |
|---------|---------------|
| **Input Sanitization** | Prompt injection detection, content filtering before LLM calls |
| **Output Filtering** | Sensitive data redaction, PII detection |
| **Encryption at Rest** | AES-256 for PostgreSQL, S3 encryption |
| **Encryption in Transit** | TLS 1.3 for all communications |
| **Audit Logging** | All security events logged to immutable storage |
| **Rate Limiting** | Per-user, per-agent, per-endpoint limits |
| **Circuit Breaker** | Graceful degradation on external service failures |

#### 5.1.4 Adversarial Security

- **Prompt Injection Defense**: Sanitization layer before any LLM call
- **Agent Audit Pair**: Every executor has a critic/auditor agent
- **Security Agent**: Dedicated security-focused agent always active for high-risk operations
- **HITL for High-Risk Actions**: Manual approval required for destructive operations

### 5.2 Performance Requirements

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Gateway Response Time** | < 100ms (P99) | HTTP request to response |
| **Agent Execution Start** | < 500ms (P99) | From task submission to first token |
| **Memory Retrieval (L1)** | < 50ms (P99) | Semantic search query |
| **Memory Retrieval (L3)** | < 100ms (P99) | Episodic memory query |
| **LoRA Swap Latency** | < 2s (P99) | Hot-swap adapter loading |
| **System Throughput** | 1000 concurrent agents | Sustained load |

#### 5.2.1 Caching Strategy

| Layer | Cache Type | TTL | Invalidation |
|-------|------------|-----|--------------|
| **Gateway** | Redis (session, rate limits) | 1h | Explicit, TTL-based |
| **L1 Memory** | ChromaDB (embeddings) | N/A | VectorDB native |
| **L2 Memory** | File system cache | 24h | Git-based |
| **LoRA Adapters** | LRU cache (memory) | N/A | Explicit unload |
| **API Responses** | Redis (expensive queries) | 5min | Event-based |

### 5.3 Availability and Reliability

#### 5.3.1 Service Level Objectives

| Component | SLO | Availability |
|-----------|-----|--------------|
| **Gateway** | 99.9% | 43min downtime/month |
| **Core Runtime** | 99.9% | 43min downtime/month |
| **L3 Memory** | 99.99% | 4.3min downtime/month |
| **L1 Memory** | 99.9% | 43min downtime/month |

#### 5.3.2 Failover Strategy

| Failure Scenario | Mitigation |
|------------------|------------|
| **Gateway Failure** | Load balancer routes to healthy instances |
| **Python Core Failure** | Restart with state recovery from PostgreSQL |
| **PostgreSQL Failure** | Read replicas, eventual consistency |
| **ChromaDB Failure** | Rebuild from L2/L3, cache warm-up |
| **LLM Provider Failure** | Circuit breaker, fallback to backup provider |
| **LoRA Adapter Corrupt** | Rollback to previous version, reload |

#### 5.3.3 Disaster Recovery

| Recovery Type | RTO (Recovery Time Objective) | RPO (Recovery Point Objective) |
|---------------|-------------------------------|-------------------------------|
| **Full System** | 4 hours | 1 hour (daily backups) |
| **Database** | 1 hour | 15 minutes (WAL archiving) |
| **Memory L1/L2** | 2 hours | 24 hours (git-based) |
| **Configuration** | 30 minutes | Real-time (git-based) |

#### 5.3.4 Backup Strategy

- **PostgreSQL**: Daily full backup, WAL continuous archiving, 30-day retention
- **L2 Memory**: Git push to remote, real-time
- **ChromaDB**: Export to S3 weekly, rebuild capability
- **LoRA Adapters**: Versioned in S3, 10 versions retained

### 5.4 Scalability

| Scale Dimension | Current Capacity | Scaling Strategy |
|-----------------|------------------|------------------|
| **Concurrent Agents** | 100 | Horizontal (more Python workers) |
| **Sessions** | 10,000 | PostgreSQL read replicas |
| **Memory Queries** | 1,000 QPS | ChromaDB clustering |
| **Event Throughput** | 10,000 EPS | Redis Streams partitioning |

---

## 6. Risks and Assumptions

### 6.1 Technical Risks

| Risk ID | Description | Severity | Probability | Impact | Mitigation |
|---------|-------------|----------|-------------|--------|------------|
| TR-001 | Self-improvement loop produces unstable behavior | High | Medium | System integrity | Skill quarantine, automatic rollback, HITL required |
| TR-002 | Prompt injection via external channels | High | High | Data security | Sanitization layer, security agent active |
| TR-003 | Uncontrolled cost from LoRA + dreaming | High | Medium | Financial | Hard budget limits, local-only training |
| TR-004 | Memory inconsistency L1/L2/L3 | Medium | Low | Data integrity | Eventual consistency protocol, versioning |
| TR-005 | DSPy compilation time too long | Medium | Medium | Development | Async compilation, fallback to non-compiled |
| TR-006 | LoRA swap latency impact | Medium | Low | UX | LRU cache, predictive pre-loading |
| TR-007 | gRPC bridge failure | Medium | Low | Availability | Circuit breaker, graceful fallback |
| TR-008 | Third-party API instability | Medium | High | Availability | Circuit breaker, multiple providers |
| TR-009 | VectorDB scaling limitations | Low | Low | Performance | ChromaDB clustering, migration path |
| TR-010 | Agent memory poisoning | High | Low | Security | Adversarial pair, audit logs |

### 6.2 Assumptions

| ID | Assumption | Evidence |
|----|------------|----------|
| A-001 | Third-party LLM APIs support >500 req/s | Current API documentation, rate limits |
| A-002 | PostgreSQL 16 + FTS5 performance adequate | Benchmark results from similar systems |
| A-003 | LoRA adapters can be hot-swapped <2s | llama-cpp-python warm-up tests |
| A-004 | Agent executes STaR without external triggers | Idle detection algorithm confirmed |
| A-005 | Kaggle/Colab APIs remain free tier available | Current API documentation |
| A-006 | TypeScript + Python gRPC performance sufficient | Benchmark of similar architectures |
| A-007 | LLM context window remains stable for memory | Vendor roadmap, 128K+ current |
| A-008 | Security agent can detect prompt injection | ML model trained on attack patterns |

### 6.3 Dependencies

| Dependency | Version | Source | Criticality |
|------------|---------|--------|-------------|
| Node.js | 22.x | nodejs.org | Critical |
| Python | 3.12+ | python.org | Critical |
| PostgreSQL | 16.x | postgresql.org | Critical |
| Redis | 7.x | redis.io | High |
| ChromaDB | latest | pypi | High |
| DSPy | 2.x | pypi | High |
| Hono | 4.x | npm | High |
| Lit | 3.x | npm | Medium |
| sentence-transformers | latest | pypi | High |
| PEFT | latest | pypi | High |

### 6.4 Open Issues

| Issue ID | Description | Priority | Owner |
|----------|-------------|----------|-------|
| OI-001 | Define exact prompt injection detection thresholds | High | Security Team |
| OI-002 | Select specific vector embedding model (sentence-transformers) | Medium | ML Team |
| OI-003 | Finalize LoRA training pipeline (Kaggle vs Colab) | Medium | DevOps |
| OI-004 | Choose telemetry backend (Jaeger vs Grafana) | Low | Infrastructure |
| OI-005 | Define exact cost budget enforcement policy | High | Finance |

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| **ACP** | Agent Communication Protocol - message format for agent-to-agent communication |
| **DSPy** | Declarative SPearhead Python - framework for LM program optimization |
| **Entity** | Composed multi-agent that acts as a single agent with routing |
| **HITL** | Human-in-the-Loop - manual approval for critical operations |
| **LoRA** | Low-Rank Adaptation - efficient model fine-tuning |
| **STaR** | Self-Taught Reasoning - self-improvement technique using rationales |
| **FTS5** | Full-Text Search 5 - PostgreSQL full-text search extension |

---

## Appendix B: Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | April 14, 2026 | XenoSys Team | Initial specification |

---

*This document is the authoritative source for the XenoSys system architecture. All implementation decisions must conform to this specification.*