# XenoSys Technical Specification

> **Document Type**: Production-Ready Technical Specification  
> **Version**: 1.0.0  
> **Status**: Final Release  
> **Methodology**: SDD (Specification-Driven Development) + DDD (Domain-Driven Design)

---

## Section 1: Identification and Overview

### 1.1 System Scope

**XenoSys** is a **Unified Multi-Agent Metacognitive System** that unifies:

- **App1 (TypeScript Gateway)**: Multi-channel adapter layer (Telegram, Slack, Discord, Webhook, API), plugin system, ACP (Agent Communication Protocol), control UI
- **App2 (Python Agent Runtime)**: Mature agent runtime with 60+ tools, episodic memory, terminal backend

**Core Capabilities**:
- Unified agent execution across TypeScript and Python
- Four-tier memory system (L1/L2/L3/L4)
- Event-driven agent activation
- Human-in-the-Loop (HITL) governance
- Self-improvement via STaR and LoRA adapters

### 1.2 Context

**System Context Diagram**:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        XenoSys Platform                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌───────────────┐     ┌─────────────────┐     ┌────────────────┐ │
│  │   Channel    │     │   Gateway       │     │    gRPC        │ │
│  │  Adapters   │────▶│   (TypeScript)  │◀───▶│    Bridge      │ │
│  │ (TELEGRAM)  │     │   Port 3000     │     │                │ │
│  │ (SLACK)     │     │                 │     │                │ │
│  │ (DISCORD)   │     └─────────────────┘     └────────────────┘ │
│  │ (WEBHOOK)   │              │ gRPC                        │         │
│  └───────────────┘              │                           │         │
│                               │  ┌─────────────────────────┴───────┐ │
│                        ┌───────▼──────────┐                    │ │
│                        │  Core (Python)   │◀──────────────────────┘ │
│                        │  Port 50051      │                         │
│                        │                 │                         │
│                        │  ┌───────────┐  │                         │
│                        │  │ EventBus │  │                         │
│                        │  │  (async) │  │                         │
│                        │  └───────────┘  │                         │
│                        │       │         │                         │
│                        │  ┌────▼────┐  │                         │
│                        │  │ Agent  │  │                         │
│                        │  │Runtime │  │                         │
│                        │  └───────┘  │                         │
│                        └─────────────┘                          │
│                              │                              │
│         ┌──────────────────────┼──────────────────────┐
│         │                      │                      │              │
│    ┌────▼────┐        ┌──────▼─────┐       ┌──────▼────┐ ┌────▼────┐
│    │   L1   │        │    L2    │       │    L3    │ │   L4   │
│    │  Cache  │        │ Semantic  │       │Episodic  │ │Contextual│
│    │ (Redis)│        │(ChromaDB)│       │ (Postgre)│ │  Graph  │
│    └───────┘        └──────────┘       └──────────┘ │(mcp-mem)│
│                                                       └─────────┘
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.3 Design Objectives

| Priority | Objective | Metric |
|----------|-----------|---------|
| **1** | Security | JWT + API key auth, RBAC, no credential leak |
| **2** | Reliability | Circuit breaker, graceful degradation |
| **3** | Performance | <200ms p95 latency for agent response |
| **4** | Observability | OpenTelemetry, health/readiness |
| **5** | Scalability | Redis Streams for horizontal scaling |

**Key Design Principles**:

1. **Event-Task Driven**: Agents "sleep" without events
2. **Adversarial by Default**: Every executor has paired critic/auditor
3. **Memory-First**: Four persistent memory layers (L1/L2/L3/L4) beyond context
4. **Composable Entities**: Multi-agents form single entities
5. **Human-in-the-Loop**: Critical decisions require human approval
6. **Self-Improving**: STaR self-improvement, LoRA adapter evolution

---

## Section 2: System Architecture

### 2.1 Architectural Pattern

**Modular Monolith with Event-Driven Core**

| Component | Technology | Role |
|-----------|------------|------|
| Gateway | TypeScript/Node.js 22+ | Channel adapters, REST API, gRPC server |
| Core | Python 3.12+ | Agent runtime, DSPy, event bus |
| Data Stores | PostgreSQL 16, ChromaDB, Redis, mcp-memory-service | L1/L2/L3/L4 memory |
| External | OpenAI, Anthropic, MCP | AI providers, tools |

**Why Modular Monolith**:
- Single team ownership (lower complexity)
- Shared PostgreSQL benefits from ACID
- Clear migration path to microservices
- Preserves TypeScript and Python ecosystems

### 2.2 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     EXTERNAL LAYER                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐  │
│  │ OpenAI   │  │Anthropic │  │  MCP    │  │ Notebook │  │
│  │   API   │  │   API   │  │ Tools  │  │  (LoRA) │  │
│  └──────────┘  └──────────┘  └──────────┘  └────────────┘  │
└──────────────────────────────────────────────────────────────┬──────┘
                                                       │
┌───────────────────────────────────────────────────────▼──────┐
│                        GATEWAY LAYER                         │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                  Hono HTTP Server                       │   │
│  │           (Channels, Plugin System, Auth)              │   │
│  └──────────────────────────────────────────────────────┘   │
│                               │                            │
│  ┌─────────────────────────────▼──────────────────────┐   │
│  │                 gRPC Bridge                         │   │
│  │         (Circuit Breaker, Load Balancing)             │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
                                │ gRPC
                                ▼
┌────────────────────────────────────────────────────────────────┐
│                        CORE LAYER                              │
│  ┌──────────────────────────────────────────────────────┐    │
│  │                   EventBus (asyncio)                   │    │
│  │              (Pub/Sub, Redis Streams)                    │    │
│  └──────────────────────────────────────────────────────┘    │
│                               │                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  Executor  │  │  Critic    │  │  Auditor   │     │
│  │  (ReAct)  │  │            │  │            │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│         │                                           │          │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │               MemoryManager                     │   │
│  │      (L1 Cache → L2 Semantic → L3 Episodic)    │   │
│  └──────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────┘
```

### 2.3 IPC Communication

| Path | Protocol | Format | Purpose |
|------|----------|--------|---------|
| External → Gateway | HTTP/WS | JSON | Channel adapters |
| Gateway ↔ Core | gRPC | Protobuf | Agent execution |
| Core → EventBus | asyncio | Event objects | Pub/Sub |
| Gateway → External | REST | JSON | AI providers |

### 2.4 Ports

| Service | Port | Bind | Exposure |
|---------|------|------|-----------|
| Gateway | 3000 | 127.0.0.1 | Internal |
| Core | 50051 | 127.0.0.1 | Internal |
| Redis | 6379 | 127.0.0.1 | Internal |
| PostgreSQL | 5432 | 127.0.0.1 | Internal |

---

## Section 3: Data Design

### 3.1 Data Model (PostgreSQL L3)

```sql
-- Core Schemas

-- Users and Authentication
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    key_hash VARCHAR(255) NOT NULL,
    name VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP
);

-- Agents
CREATE TABLE agents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    name VARCHAR(255) NOT NULL,
    config JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Sessions
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID REFERENCES agents(id),
    user_id UUID REFERENCES users(id),
    status VARCHAR(50) DEFAULT 'active',
    metadata JSONB DEFAULT '{}',
    started_at TIMESTAMP DEFAULT NOW(),
    ended_at TIMESTAMP
);

-- Memory (L3 Episodic)
CREATE TABLE episodic_memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES sessions(id),
    agent_id UUID REFERENCES agents(id),
    memory_type VARCHAR(50) NOT NULL,
    content JSONB NOT NULL,
    importance_score FLOAT DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_episodic_session ON episodic_memory(session_id);
CREATE INDEX idx_episodic_agent ON episodic_memory(agent_id);
CREATE INDEX idx_episodic_created ON episodic_memory(created_at DESC);

-- Audit Trail
CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    agent_id UUID REFERENCES agents(id),
    session_id UUID REFERENCES sessions(id),
    action VARCHAR(100) NOT NULL,
    details JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 3.2 Data Dictionary (Critical Fields)

| Table | Field | Type | Description |
|-------|-------|------|-------------|
| users | id | UUID | Primary key |
| users | email | VARCHAR | User email (unique) |
| api_keys | key_hash | VARCHAR | Hashed API key |
| api_keys | user_id | UUID | Foreign key to users |
| agents | config | JSONB | Agent configuration |
| sessions | status | VARCHAR | active/completed/failed |
| episodic_memory | content | JSONB | Memory content |
| episodic_memory | importance_score | FLOAT | 0.0-1.0 score |
| audit_log | action | VARCHAR | Action performed |

### 3.3 Storage Strategy

| Layer | Storage | TTL | Access Pattern |
|-------|---------|-----|--------------|
| L1 Cache | Redis | 1 hour | Most frequent |
| L2 Semantic | ChromaDB | Persistent | Frequent |
| L3 Episodic | PostgreSQL | 90 days | Historical |
| L4 Contextual | mcp-memory-service | Persistent | Graph-based ("Caderninho") |

**Memory Routing Logic**:

```python
class MemoryManager:
    async def store(self, memory: MemoryItem) -> None:
        if memory.importance_score > 0.9:
            # L4: Graph-based contextual memory
            await self.l4.write(memory)  # mcp-memory-service
        elif memory.importance_score > 0.8:
            # Immediately promote to L3
            await self.l3.write(memory)
        elif memory.importance_score > 0.5:
            # L2 first, promote later
            await self.l2.write(memory)
        else:
            # L1 only
            await self.l1.write(memory)
```

**L4 Integration Pattern**:
```python
class L4MemoryClient:
    """Cognitive Interception Pattern for L4 Graph Memory"""
    
    async def pre_hook(self, query: str) -> Dict:
        """Load contextual memory before agent responds"""
        result = await self.mcp.call('read_graph', query=query)
        return result.entities  # Returns graph entities
    
    async def post_hook(self, memory: MemoryItem) -> None:
        """Reflexive write - evaluate if new knowledge was learned"""
        if memory.importance_score > 0.7:
            # Async write to L4 graph
            await self.mcp.call('create_entities', entities=[{
                'name': memory.key,
                'content': memory.content
            }])
```

---

## Section 4: Interface and Component Design

### 4.1 Modular Decomposition

#### Gateway Components

| Component | Responsibility |
|-----------|---------------|
| `HonoServer` | HTTP/WS server, routing |
| `ChannelAdapters` | Telegram, Slack, Discord adapters |
| `PluginSystem` | Dynamic plugin loading |
| `GRPCBridge` | TypeScript ↔ Python communication |
| `AuthMiddleware` | JWT, API key validation |
| `HealthEndpoint` | Health and readiness checks |

#### Core Components

| Component | Responsibility |
|-----------|---------------|
| `EventBus` | Async pub/sub with Redis |
| `AgentRuntime` | ReAct agent loop |
| `ToolRegistry` | Tool discovery and execution |
| `MemoryManager` | Four-tier memory routing (L1→L4) |
| `CostTracker` | Budget and rate limiting |
| `HITLWorkflow` | Human approval workflow |

### 4.2 API Design

#### REST Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|------|
| `/health` | GET | None | Health check |
| `/ready` | GET | None | Readiness check |
| `/api/v1/agents` | POST | JWT | Create agent |
| `/api/v1/agents/:id` | GET | JWT | Get agent |
| `/api/v1/agents/:id/execute` | POST | JWT | Execute agent |
| `/api/v1/sessions` | GET | JWT | List sessions |
| `/api/v1/sessions/:id` | GET | JWT | Get session |
| `/api/v1/memory/:agent_id` | GET | JWT | Query memory |

#### gRPC Services

```protobuf
service AgentService {
    rpc Execute(ExecuteRequest) returns (ExecuteResponse);
    rpc StreamExecute(ExecuteRequest) returns (stream ExecuteResponse);
    rpc CreateSession(CreateSessionRequest) returns (Session);
}

service MemoryService {
    rpc Store(MemoryItem) returns (StoreResponse);
    rpc Query(MemoryQuery) returns (MemoryResults);
    rpc Forget(ForgetRequest) returns (ForgetResponse);
}
```

### 4.3 Logical Flows

#### Agent Execution Flow

```
User Request
     │
     ▼
┌─────────────┐
│ Auth Check  │───▶ 401 if invalid
└─────────────┘
     │
     ▼ Valid
┌─────────────┐
│ Rate Limit  │───▶ 429 if exceeded
└─────────────┘
     │
     ▼
┌─────────────┐
│  HITL?      │───▶ YES ──▶ Pending Queue ──▶ Human Approval
└─────────────┘
     │ NO
     ▼
┌─────────────┐
│  Execute   │
│  Agent     │───▶ Tool Calls
└─────────────┘
     │
     ▼
┌─────────────┐
│  Critic    │───▶ If failed, retry or fail
│  Review    │
└─────────────┘
     │
     ▼
┌─────────────┐
│  Response  │
│  + Memory  │
└─────────────┘
```

#### HITL Approval Flow

```
Agent tries sensitive action
     │
     ▼
┌─────────────┐
│ Create     │
│ Approval   │
│ Request    │
└─────────────┘
     │
     ▼ Pending status
     │
User reviews request
     │
     ├─▶ APPROVE ──▶ Execute action
     │
     └─▶ REJECT ──▶ Log rejection
```

---

## Section 5: Non-Functional Requirements and Security

### 5.1 Security

#### Authentication

| Method | Use Case |
|-------|----------|
| JWT | User session authentication |
| API Key | Service-to-service, programmatic access |

#### Authorization

```python
class RBAC:
    ROLES = {
        'admin': ['*'],
        'developer': ['agent:read', 'agent:write', 'execution:*'],
        'user': ['agent:read', 'execution:read'],
        'viewer': ['agent:read', 'execution:read'],
    }
```

#### Secrets Management

- **API Keys**: Stored hashed in PostgreSQL
- **JWT Secret**: Environment variable, generated at first boot
- **OpenAI Key**: Injected via environment variable to subprocess

> **⚠️ NEVER pass secrets as command-line arguments**

### 5.2 Performance

| Metric | Target |
|--------|--------|
| Agent p95 latency | <200ms |
| Health check | <50ms |
| Memory query | <100ms |
| Concurrent agents | 100/user |

### 5.3 Availability

**Circuit Breaker**:

```python
class CircuitBreaker:
    def __init__(self, failure_threshold=5, timeout=30):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failures = 0
        self.state = 'CLOSED'

    def call(self, func):
        if self.state == 'OPEN':
            raise CircuitOpenError()
        try:
            result = func()
            self.failures = 0
            return result
        except Exception as e:
            self.failures += 1
            if self.failures >= self.failure_threshold:
                self.state = 'OPEN'
            raise
```

### 5.4 Observability

**Health Check**:

```python
@app.get('/health')
def health():
    return {'status': 'healthy'}

@app.get('/ready')
async def ready():
    checks = {
        'postgres': await check_postgres(),
        'redis': await check_redis(),
        'grpc': await check_grpc_bridge(),
    }
    return {
        'ready': all(checks.values()),
        'checks': checks
    }
```

---

## Section 6: Risks and Assumptions

### 6.1 Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Redis connection failure | Medium | High | Fallback to in-memory, queue for recovery |
| gRPC bridge latency | Low | Medium | Circuit breaker, timeout |
| ChromaDB corruption | Low | Medium | PostgreSQL backup |
| Token limit exceeded | Medium | Medium | Aggressive context eviction |

### 6.2 Assumptions

| Assumption | Validation |
|------------|------------|
| PostgreSQL 16 available | Docker Compose includes |
| Redis 7+ available | Docker Compose includes |
| Python 3.12+ on server | PEP 722 support |
| 100 concurrent users max | Load testing |
| 1GB memory per agent | Resource monitoring |

### 6.3 Dependencies

| Dependency | Version | Purpose |
|-----------|---------|---------|
| Node.js | 22+ | Gateway runtime |
| Python | 3.12+ | Core runtime |
| PostgreSQL | 16 | L3 storage |
| Redis | 7+ | L1 cache, pub/sub |
| ChromaDB | latest | L2 semantic |

---

## Appendix A: Verification Checklist

- [x] Gateway binds to 127.0.0.1 (not 0.0.0.0)
- [x] Cloudflare uses Token (Zero Trust)
- [x] Mobile AsyncStorage implemented
- [x] Mobile reconnects on foreground event
- [x] Desktop kills by PID (taskkill /PID)
- [x] Secrets via env var (not argv)
- [x] MCP DOMPurify sanitization
- [x] JWT Bearer authentication
- [x] 500 log culling limit
- [x] Hardware resource monitoring

---

**Document Approval**:

- Tech Lead: _________________________ Date: _______
- Security Lead: _________________________ Date: _______
- Product Owner: _________________________ Date: _______

---

*XenoSys Technical Specification - Production Ready*