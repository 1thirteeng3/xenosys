# XenoSys — Unified Multi-Agent System

A metacognitive multi-agent system with multi-layer memory, self-improvement, LoRA adapters, and LLMOps governance.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         XENOSYS SYSTEM                              │
├─────────────────────────────────────────────────────────────────────┤
│  Gateway (TypeScript)    │    Core (Python)                        │
│  ─────────────────────    │    ──────────────────                   │
│  • Channels (20+)        │    • Agents (DSPy-based)                │
│  • Plugins               │    • Entities (Multi-agent composition) │
│  • Auth (JWT/MFA)        │    • Memory System (L1-L4)              │
│  • gRPC Bridge           │    • Learning (STaR, LoRA)               │
│  • ACP Handler           │    • LLMOps (Telemetry, Cost, Gov)      │
└─────────────────────────────────────────────────────────────────────┘
```

## Memory System

XenoSys implements a **four-layer memory architecture** with specialized integrations:

| Layer | Name | Integration | Purpose |
|-------|------|-------------|---------|
| **L1** | Semantic Memory | [Cortex](https://github.com/abbacusgroup/cortex) | Vector embeddings, semantic search |
| **L2** | Long-term Memory (2ndBrain) | [Obsidian](https://obsidian.md) | User notes, personal knowledge |
| **L3** | Episodic Memory | [OpenViking](https://github.com/volcengine/OpenViking) | Session logs, interactions, raw files |
| **L4** | Contextual Memory (BrainSys) | [Membase](https://membase.so) | AI's second brain, patterns |

### Memory Integration Details

- **L1 - Cortex**: Vector-based semantic search for agent context retrieval
- **L2 - Obsidian (2ndBrain)**: User's personal knowledge management
- **L3 - OpenViking**: Records each interaction, log, and raw file with timestamps
- **L4 - Membase (BrainSys)**: AI's analysis of captured context, pattern detection

## Project Structure

```
nexus/
├── gateway/                    # TypeScript Gateway (App1)
│   ├── src/
│   │   ├── channels/           # Channel adapters (Telegram, Discord, Slack, etc.)
│   │   ├── plugins/            # Plugin system
│   │   ├── grpc/               # gRPC bridge to Python
│   │   ├── auth/               # Authentication (JWT, MFA, RBAC)
│   │   └── gateway/            # HTTP/WS server (Hono)
│   └── ui/                     # Lit Web Components
│
└── core/                       # Python Core (App2)
    ├── agents/                 # Agent system (DSPy-based)
    │   ├── base_agent.py       # Base agent with ReAct pattern
    │   └── registry.py          # Agent registry and factory
    │
    ├── entities/               # Entity composition
    │   └── entity.py           # Multi-agent entities with routing
    │
    ├── memory/                 # Multi-layer memory
    │   ├── orchestrator.py     # Memory coordination
    │   ├── l1_semantic/        # Cortex integration
    │   ├── l2_longterm/        # Obsidian (2ndBrain) integration
    │   ├── l3_episodic/        # OpenViking integration
    │   └── working/            # Membase (BrainSys) integration
    │
    ├── learning/               # Self-improvement
    │   ├── lora/               # LoRA adapter registry
    │   └── star.py             # STaR (Self-Taught Reasoning)
    │
    ├── llmops/                 # Operations
    │   ├── telemetry.py        # OpenTelemetry
    │   ├── cost_tracker.py     # Cost accounting
    │   └── governance.py       # Policy enforcement
    │
    └── orchestration/          # Event-driven orchestration
        ├── event_bus.py        # AsyncIO event bus
        └── agent.py            # Agent executor
```

## Getting Started

### Prerequisites

- Node.js 22+ for Gateway
- Python 3.12+ for Core
- PostgreSQL 16 (for L3 episodic memory)
- Redis (optional, for scaling)

### Installation

```bash
# Clone and setup
cd nexus/gateway
npm install

cd ../core
pip install -e .
```

### Running

```bash
# Start Gateway
cd nexus/gateway
npm run dev

# Start Core
cd nexus/core
python -m nexus.core.app
```

## Key Features

- **Adversarial Agents**: Every executor has a paired critic/auditor
- **Human-in-the-Loop**: Critical actions require approval
- **Self-Improvement**: STaR cycles for continuous learning
- **LoRA Hot-Swap**: Switch adapters without downtime
- **Multi-Channel**: Telegram, Discord, Slack, Webhooks, etc.
- **Typed API**: gRPC with Protocol Buffers + ACP

## Documentation

- [SPECIFICATIONS.md](./SPECIFICATIONS.md) - Technical specifications
- [DEVELOPMENT.md](./DEVELOPMENT.md) - DDD design document

## License

MIT