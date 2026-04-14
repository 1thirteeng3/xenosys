# C4 and UML Modeling Guide

Guide for creating architectural documentation using the C4 model and UML diagrams.

## C4 Model Overview

C4 Model provides four levels of architecture documentation:
1. **Context** - The big picture
2. **Container** - Applications and data stores
3. **Component** - Components within containers
4. **Code** - Implementation details (optional)

## Level 1: Context Diagram

Shows the system in its environment with actors and systems.

### Template

```
┌─────────────────────────────────────────────────────────────────┐
│                      [System Name]                               │
│                                                                  │
│   ┌─────────┐          ┌──────────────┐          ┌─────────┐   │
│   │ Actor 1 │          │              │          │ System  │   │
│   └────┬────┘          │   OUR SYSTEM │          │  (Ext)  │   │
│        │               │              │          └────┬────┘   │
│        │               │   ┌────────┐ │               │        │
│        │               │   │Gateway │ │               │        │
│        │               │   └────────┘ │               │        │
│        │               │   ┌────────┐ │               │        │
│        │               │   │ Agents │ │               │        │
│        │               │   └────────┘ │               │        │
│        │               │   ┌────────┐ │               │        │
│        │               │   │Memory  │ │               │        │
│        │               │   └────────┘ │               │        │
│        │               └──────────────┘               │        │
│        │                      │                       │        │
└────────┼──────────────────────┼───────────────────────┼────────┘
         │                      │                       │
         ▼                      ▼                       ▼
    [Telegram,             [Internal              [External
     Discord,              Services]              APIs]
     Slack]
```

### Documentation Format

```markdown
## System Context

### Scope
[One paragraph describing what the system does]

### External Actors
| Actor | Description | Role |
|-------|-------------|------|
| User | End users interacting via messaging platforms | Primary |
| Admin | System administrators | Management |
| External API | Third-party services | Integration |

### External Systems
| System | Description | Interface |
|--------|-------------|-----------|
| OpenAI | LLM provider | API |
| VectorDB | Semantic search | API |
```

## Level 2: Container Diagram

Shows the major architectural components (applications, databases, services).

### Template

```
┌─────────────────────────────────────────────────────────────────┐
│                         XenoSys                                  │
│                                                                  │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │  Gateway    │    │   Core      │    │   Memory    │         │
│  │  (TypeScript)│    │  (Python)   │    │  (Multi-tier)│         │
│  │             │    │             │    │             │         │
│  │ ┌─────────┐ │    │ ┌─────────┐ │    │ ┌─────────┐ │         │
│  │ │Channels │ │◄──►│ │ Orchestr │ │◄──►│ │  L1     │ │         │
│  │ └─────────┘ │    │ │  ation   │ │    │ │ (Cache) │ │         │
│  │ ┌─────────┐ │    │ └─────────┘ │    │ └─────────┘ │         │
│  │ │  Event  │ │    │ ┌─────────┐ │    │ ┌─────────┐ │         │
│  │ │   Bus   │ │    │ │  Agents │ │    │ │  L2     │ │         │
│  │ └─────────┘ │    │ └─────────┘ │    │ │(Vector) │ │         │
│  │ ┌─────────┐ │    │ ┌─────────┐ │    │ └─────────┘ │         │
│  │ │Plugins  │ │    │ │ Learning│ │    │ ┌─────────┐ │         │
│  │ └─────────┘ │    │ │ Engine  │ │    │ │  L3     │ │         │
│  └──────┬──────┘    └──────┬─────┘    │ │(SQL)    │ │         │
│         │                  │          │ └─────────┘ │         │
│         │    gRPC          │          └─────────────┘         │
│         └──────────────────┘                                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Documentation Format

```markdown
## Container Overview

### Gateway (TypeScript)
- **Technology**: Node.js, Hono, TypeScript
- **Responsibilities**: Protocol handling, channel adapters, plugin system
- **Public API**: HTTP REST, WebSocket, SSE

### Core (Python)
- **Technology**: Python 3.12, asyncio, DSPy
- **Responsibilities**: Agent orchestration, tool execution, learning
- **Public API**: gRPC

### Memory (Multi-tier)
- **Technology**: Redis, ChromaDB, PostgreSQL
- **Responsibilities**: Context management, semantic search, persistence
```

## Level 3: Component Diagram

Shows the internal structure of each container.

### Gateway Components

```
┌─────────────────────────────────────────────────────────────────┐
│                        Gateway                                   │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Event Bus                             │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐               │   │
│  │  │ Subscribe│  │ Publish  │  │  Queue   │               │   │
│  │  └──────────┘  └──────────┘  └──────────┘               │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─────────────────┐              ┌─────────────────┐          │
│  │ Channel Manager │              │ Plugin Manager  │          │
│  │                 │              │                 │          │
│  │ ┌─────────────┐ │              │ ┌─────────────┐ │          │
│  │ │  Telegram   │ │              │ │   Load      │ │          │
│  │ │  Discord    │ │              │ │   Hooks     │ │          │
│  │ │  Slack      │ │              │ │   Invoke    │ │          │
│  │ │  Webhook    │ │              │ └─────────────┘ │          │
│  │ └─────────────┘ │              └─────────────────┘          │
│  └────────┬────────┘                                            │
│           │                                                     │
└───────────┼─────────────────────────────────────────────────────┘
            │
            ▼
     ┌──────────────┐
     │  gRPC Bridge │
     └──────────────┘
```

### Core Components

```
┌─────────────────────────────────────────────────────────────────┐
│                         Core                                     │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐    │
│  │                   Agent System                          │    │
│  │                                                         │    │
│  │   ┌────────────┐    ┌────────────┐    ┌────────────┐  │    │
│  │   │Orchestrator│◄──►│ Executor   │◄──►│ Reflector  │  │    │
│  │   └────────────┘    └────────────┘    └────────────┘  │    │
│  │          │                                            │    │
│  │          ▼                                            │    │
│  │   ┌────────────┐    ┌────────────┐                    │    │
│  │   │   Tool     │    │   Tool     │                    │    │
│  │   │  Registry  │    │   Router   │                    │    │
│  │   └────────────┘    └────────────┘                    │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌────────────────────┐    ┌────────────────────┐              │
│  │   Learning Engine  │    │    LLMOps Gov.     │              │
│  │                    │    │                    │              │
│  │ ┌────────────────┐ │    │ ┌────────────────┐ │              │
│  │ │  LoRA Manager  │ │    │ │ Cost Tracker   │ │              │
│  │ │  STaR Trainer  │ │    │ │ Rate Limiter   │ │              │
│  │ │  Skill Tracker │ │    │ │    HITL        │ │              │
│  │ └────────────────┘ │    │ └────────────────┘ │              │
│  └────────────────────┘    └────────────────────┘              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## UML Diagrams

### Sequence Diagram: Agent Execution

```
┌────────┐     ┌─────────┐     ┌────────┐     ┌────────┐     ┌────────┐
│ Client │     │Gateway  │     │ gRPC   │     │ Core   │     │ Memory │
└───┬────┘     └────┬────┘     └───┬────┘     └───┬────┘     └───┬────┘
    │               │               │               │               │
    │ POST /execute │               │               │               │
    │──────────────►│               │               │               │
    │               │               │               │               │
    │               │ ExecuteAgent  │               │               │
    │               │──────────────►│               │               │
    │               │               │               │               │
    │               │               │ Think Request │               │
    │               │               │──────────────►│               │
    │               │               │               │               │
    │               │               │               │ Search context│
    │               │               │               │──────────────►│
    │               │               │               │◄──────────────│
    │               │               │               │               │
    │               │               │  LLM Call     │               │
    │               │               │──────────────►│               │
    │               │               │               │               │
    │               │               │◄──────────────│               │
    │               │               │               │               │
    │               │               │ Tool Call     │               │
    │               │               │──────────────►│               │
    │               │               │               │               │
    │               │               │◄──────────────│               │
    │               │               │               │               │
    │               │ Response      │               │               │
    │               │◄──────────────│               │               │
    │               │               │               │               │
    │ Response      │               │               │               │
    │◄──────────────│               │               │               │
    │               │               │               │               │
```

### State Diagram: Agent Lifecycle

```
                                    ┌─────────────┐
                                    │    IDLE     │
                                    └──────┬──────┘
                                           │
                                           │ start
                                           ▼
                                  ┌─────────────────┐
                                  │    THINKING     │
                                  └────────┬────────┘
                                           │
                    ┌──────────────────────┼──────────────────────┐
                    │                      │                      │
                    ▼                      ▼                      │
           ┌────────────────┐     ┌────────────────┐             │
           │ ACTING (Direct)│     │ ACTING (Tool)  │             │
           └───────┬────────┘     └───────┬────────┘             │
                   │                      │                      │
                   │                      ▼                      │
                   │             ┌─────────────────┐             │
                   │             │  WAITING_TOOL   │             │
                   │             └────────┬────────┘             │
                   │                      │                      │
                   │                      ▼                      │
                   │             ┌─────────────────┐             │
                   │             │WAITING_HITL(Opt)│             │
                   │             └────────┬────────┘             │
                   │                      │                      │
                   └──────────────────────┼──────────────────────┘
                                          │
                                          ▼
                                 ┌─────────────────┐
                                 │   COMPLETED     │
                                 └────────┬────────┘
                                          │
                                          │ reset
                                          ▼
                                   ┌─────────────┐
                                   │    IDLE     │
                                   └─────────────┘
```

### Class Diagram: Memory System

```
┌─────────────────────────────────────────────────────────────────┐
│                         <<interface>>                            │
│                        MemoryLayer                               │
├─────────────────────────────────────────────────────────────────┤
│ + write(entry: MemoryEntry): str                                │
│ + read(entry_id: str): MemoryEntry | None                       │
│ + search(query, namespace, limit): list[SearchResult]           │
│ + delete(entry_id: str): bool                                   │
│ + stats(): dict                                                 │
└─────────────────────────────────────────────────────────────────┘
                    ▲                    ▲                    ▲
                    │                    │                    │
                    │                    │                    │
┌───────────────┐   │   ┌───────────────┐│   ┌───────────────┐│
│    L1Memory   │   │   │    L2Memory   ││   │    L3Memory   ││
├───────────────┤   │   ├───────────────┤│   ├───────────────┤│
│ - max_size    │   │   │ - embedder    ││   │ - engine      ││
│ - cache       │   │   │ - collection  ││   │ - session_fac ││
├───────────────┤   │   ├───────────────┤│   ├───────────────┤│
│ + get_recent  │   │   │ + initialize  ││   │ + initialize  ││
│ + get_context │   │   │ + search      ││   │ + search      ││
└───────────────┘   │   └───────────────┘│   └───────────────┘│
                    │                    │                    │
                    └────────────────────┼────────────────────┘
                                         │
                                         ▼
                              ┌─────────────────────┐
                              │   MemoryManager     │
                              ├─────────────────────┤
                              │ - l1: L1Memory      │
                              │ - l2: L2Memory      │
                              │ - l3: L3Memory      │
                              ├─────────────────────┤
                              │ + initialize()      │
                              │ + write(...)        │
                              │ + read(...)         │
                              │ + search(...)       │
                              │ + get_context(...)  │
                              │ + stats()           │
                              └─────────────────────┘
```

### Component Diagram: LLMOps Governance

```
┌─────────────────────────────────────────────────────────────────┐
│                     LLMOps Governance                            │
│                                                                  │
│  ┌──────────────────────┐  ┌──────────────────────┐             │
│  │     CostTracker      │  │     RateLimiter      │             │
│  │                      │  │                      │             │
│  │ ┌──────────────────┐ │  │ ┌──────────────────┐ │             │
│  │ │ - calculate_cost │ │  │ │ - acquire        │ │             │
│  │ │ - check_budget   │ │  │ │ - wait_for_slot  │ │             │
│  │ │ - record         │ │  │ │ - get_remaining  │ │             │
│  │ └──────────────────┘ │  │ └──────────────────┘ │             │
│  └──────────┬───────────┘  └──────────┬───────────┘             │
│             │                         │                         │
│             └────────────┬────────────┘                         │
│                          │                                       │
│                          ▼                                       │
│              ┌───────────────────────┐                          │
│              │       HITLManager      │                          │
│              ├───────────────────────┤                          │
│              │ - requests: Map       │                          │
│              │ - pending: Queue      │                          │
│              ├───────────────────────┤                          │
│              │ + create_request      │                          │
│              │ + approve             │                          │
│              │ + reject              │                          │
│              │ + get_pending         │                          │
│              └───────────┬───────────┘                          │
│                          │                                       │
│                          ▼                                       │
│              ┌───────────────────────┐                          │
│              │      AuditLogger       │                          │
│              ├───────────────────────┤                          │
│              │ + log                 │                          │
│              │ + query               │                          │
│              └───────────────────────┘                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Documentation Checklist

### Context Level
- [ ] System purpose clearly stated
- [ ] All external actors identified
- [ ] External system dependencies documented
- [ ] User journeys mapped

### Container Level
- [ ] All containers identified
- [ ] Technology stack specified per container
- [ ] Communication mechanisms documented
- [ ] Data stores identified

### Component Level
- [ ] Components within each container defined
- [ ] Public APIs documented
- [ ] Component responsibilities clear
- [ ] Dependencies between components mapped

### Code Level (Optional)
- [ ] Key classes/variables documented
- [ ] Important relationships shown
- [ ] Implementation notes included

## Tool Recommendations

- **Mermaid**: For code-generated diagrams
- **PlantUML**: For detailed UML
- **draw.io**: For visual editing
- **Structurizr**: For C4 model as code