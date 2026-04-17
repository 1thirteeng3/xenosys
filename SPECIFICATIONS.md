# XenoSys — Unified Multi-Agent System
## Technical Specifications Document

**Version:** 2.0  
**Date:** April 14, 2026  
**Classification:** Technical Architecture Document  
**Authors:** XenoSys Development Team  
**Status:** Production Ready

---

## Table of Contents

1. [Identification and Overview](#1-identification-and-overview)
2. [Installation Variants](#2-installation-variants)
3. [Initial Setup Wizard](#3-initial-setup-wizard)
4. [System Architecture](#4-system-architecture)
5. [Data Design (Persistence)](#5-data-design-persistence)
6. [Interface and Component Design](#6-interface-and-component-design)
7. [Non-Functional Requirements and Security](#7-non-functional-requirements-and-security)
8. [Risks and Assumptions](#8-risks-and-assumptions)

---

## 1. Identification and Overview

### 1.1 System Scope

**XenoSys** is a unified multi-agent metacognitive system available across multiple platforms:

- **Multi-Agent Orchestration**: Runtime for managing autonomous agents with adversarial pairing (executor + critic)
- **Multi-Layer Memory**: Three persistent memory layers (Semantic L1, Long-term L2, Episodic L3)
- **Self-Improvement**: STaR (Self-Taught Reasoning) and LoRA adapter evolution
- **Unified Gateway**: TypeScript-based channel adapters, plugin system, ACP protocol
- **LLMOps**: Telemetry, cost tracking, policy enforcement, HITL workflows

### 1.2 Core Capabilities

| Capability | Description |
|------------|-------------|
| Agent Runtime | Multi-agent orchestration with Claude/GPT/OpenAI backends |
| Memory System | L1/L2/L3 persistent memory layers |
| Tool Integration | MCP, browser automation, web scraping |
| Channel Adapters | Telegram, Discord, HTTP, WebSocket |
| LLM Flexibility | API mode (OpenAI/Anthropic) OR local mode (on-demand) |

---

## 2. Installation Variants

### 2.1 Desktop (Linux, Windows, Mac)

| Variant | Size | Use Case |
|---------|------|----------|
| **Desktop Light** | ~200MB | Gateway + settings panel only, connects to cloud APIs |
| **Desktop Full** | ~2GB | Adds local LLM (Ollama) for offline inference |

**Installation Target:** User downloads platform-specific installer
- Linux: `.deb`, `.AppImage`
- Windows: `.exe` installer
- Mac: `.dmg` or `.app`

### 2.2 VPS/Server

| Variant | Docker Size | Services |
|---------|-----------|----------|
| **VPS Light** | ~300MB | Gateway + Redis only |
| **VPS Standard** | ~800MB | + Core + Cortex |
| **VPS Full** | ~2GB | + OpenViking + All features |

**Installation:** `docker compose up` with configurable services

### 2.3 Mobile (Android, iOS)

| Variant | Size | Notes |
|--------|------|-------|
| **Mobile Light** | ~50MB | Connects to remote VPS via WebSocket |
| **Mobile Full** | ~150MB | Local inference via WebLLM |

**Distribution:** App Store / Play Store

### 2.4 Modular Service Architecture

```
                    ┌─────────────────────────────────────┐
                    │     Initial Settings Panel          │
                    │     (First-Run Wizard)            │
                    └──────────────┬──────────────────┘
                                   │
         ┌─────────────────────────┼─────────────────────────┐
         │                        │                        │
         ▼                        ▼                        ▼
┌───────────────┐       ┌───────────────┐       ┌───────────────┐
│  Desktop     │       │  VPS         │       │  Mobile      │
│  (Electron)  │       │  (Docker)     │       │  (React Nat.) │
└───────┬───────┘       └───────┬───────┘       └───────┬───────┘
        │                      │                      │
        │    ┌─────────────────┴─────────────────┐    │
        │    │         On-Demand Modules           │    │
        │    ├───────────────────────────────┤    │
        │    │  • Local LLM (Ollama/WebLLM)    │    │
        │    │  • MCP Memory Server          │    │
        │    │  • Cortex Embeddings         │    │
        │    │  • OpenViking Agent          │    │
        │    └──────────────────────────────┘    │
        │                      │                 │
        └──────────────────────┼──────────────────┘
                               │
                    ┌────────┴────────┐
                    │  Shared Backend  │
                    │  (when remote)    │
                    └──────────────────┘
```

---

## 3. Initial Setup Wizard

### 3.1 First-Run Experience

All installations launch directly into a **Settings Panel Wizard**:

```
┌─────────────────────────────────────────────────────────────┐
│                    XenoSys Setup                           │
├─────────────────────────────────────────────────────────────┤
│   Step 1: Basic Configuration                               │
│   ─────────────────────────────────                         │
│   □ Agent Name: [________________]                          │
│   □ Instance ID: [auto-generated]                          │
│                                                             │
│   Step 2: LLM Provider Selection                            │
│   ─────────────────────────────────                         │
│   ○ Cloud API (default)                                    │
│     • OpenAI API Key                                       │
│     • Anthropic API Key                                    │
│     • Google API Key                                        │
│   ○ Local LLM (optional - will install on-demand)          │
│     • Ollama (Linux/Desktop)                                │
│     • WebLLM (Mobile)                                      │
│                                                             │
│   Step 3: Integrations                                     │
│   ─────────────────────────────────                         │
│   □ Telegram Bot Token                                      │
│   □ Discord Webhook                                         │
│   □ MCP Tools Enabled                                       │
│                                                             │
│   Step 4: Security                                         │
│   ─────────────────────────────────                         │
│   □ Encryption: AES-256-GCM                               │
│   ○ Read-only mode (no tool execution)                      │
│                                                             │
│                      [Continue] →                         │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 On-Demand Module Installer

When user selects "Local LLM" or enables specific integrations:

```
┌─────────────────────────────────────────────────────────────┐
│                  Installing Modules...                      │
├─────────────────────────────────────────────────────────────┤
│   Installing Ollama...        [████████░░] 80%               │
│   Downloading model...       [██████████] 100%              │
│   Verifying installation... [██████████] Done               │
│                                                             │
│   ✓ Module installed successfully                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 3.3 Configuration Storage

Settings stored in:
- **Desktop:** `~/.xenosys/config.yaml` (encrypted secrets)
- **Mobile:** iOS Keychain / Android Keystore
- **VPS:** Docker secrets or environment variables

---

## 4. System Architecture

### 4.1 Architectural Pattern

| Component | Pattern | Description |
|-----------|---------|-------------|
| Gateway | Modular Monolith | Channel adapters, plugin system |
| Core | Event-Driven | Agent orchestration, memory layers |
| Cortex | Microservice | Embeddings, RAG pipeline |
| OpenViking | Microservice | Full-featured agent |

### 4.2 Service Communication

```
┌──────────────┐     gRPC      ┌──────────────┐
│  Gateway    │◄──────────►│    Core     │
│  (TypeScript)              │  (Python)   │
└──────┬───────┘              └──────┬───────┘
       │                            │
       │ HTTP/WS                    │ Redis
       │                            │
       ▼                            ▼
┌──────────────┐              ┌──────────────┐
│   Web UI     │              │   Redis     │
│  (Optional)  │              │  (Broker)   │
└─────────────┘              └──────┬───────┘
                                   │
                    ┌──────────────┼──────────────┐
                    ▼              ▼              ▼
              ┌──────────┐   ┌──────────┐   ┌──────────┐
              │ Cortex   │   │  Open-   │   │   MCP    │
              │ (Embed)  │   │ Viking   │   │ Memory  │
              └──────────┘   └─────────┘   └─────────┘
```

### 4.3 Docker Service Matrix

| Service | Light | Standard | Full |
|---------|-------|----------|------|
| gateway | ✅ | ✅ | ✅ |
| core | ❌ | ✅ | ✅ |
| cortex | ❌ | ✅ | ✅ |
| openviking | ❌ | ❌ | ✅ |
| redis | ✅ | ✅ | ✅ |
| mcp-memory | ❌ | ❌ | ✅ |

---

## 5. Data Design (Persistence)

### 5.1 Storage Strategy

| Layer | Technology | Purpose |
|------|------------|---------|
| L1 Semantic | ChromaDB | Vector similarity search |
| L2 Long-term | File System / Git | Document versioning |
| L3 Episodic | PostgreSQL | Session history |
| Working | Redis | Active state |

### 5.2 Data Model

```
UserConfig:
  - user_id: UUID
  - agent_name: String
  - llm_provider: Enum (openai|anthropic|local)
  - llm_model: String
  - channels: List[ChannelConfig]
  - created_at: DateTime
  - updated_at: DateTime

AgentSession:
  - session_id: UUID
  - user_id: UUID (FK)
  - status: Enum
  - memory_snapshot: JSON
  - created_at: DateTime
```

---

## 6. Interface and Component Design

### 6.1 Gateway Components

```
gateway/
├── src/
│   ├── channels/          # Channel adapters
│   │   ├── telegram.ts
│   │   ├── discord.ts
│   │   ├── http.ts
│   │   └── websocket.ts
│   ├── plugins/        # Plugin system
│   ├── grpc/           # gRPC bridge
│   └── types.ts        # Shared types
```

### 6.2 Core Components

```
nexus/
├── core/
│   ├── app.py                 # Entry point
│   ├── memory/
│   │   ├── l1_semantic/       # ChromaDB integration
│   │   ├── l2_longterm/      # File system + SecondBrain
│   │   └── l3_episodic/      # PostgreSQL sessions
│   └── orchestrator.py       # Agent orchestration
```

### 6.3 API Design

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/ready` | GET | Readiness check |
| `/api/v1/agent/execute` | POST | Execute agent |
| `/api/v1/agent/session` | POST | Create session |
| `/api/v1/memory/search` | POST | Search L1 |

---

## 7. Non-Functional Requirements and Security

### 7.1 Performance Targets

| Metric | Target |
|--------|--------|
| Health check latency | < 50ms |
| Agent response (API mode) | < 2s |
| Agent response (local) | < 5s |
| Memory search | < 100ms |

### 7.2 Security

| Requirement | Implementation |
|-------------|-----------------|
| Secrets | AES-256-GCM encryption at rest |
| API Keys | Environment / Keychain only |
| Communication | TLS 1.3 |
| Authentication | JWT tokens |

### 7.3 Availability

- **Self-healing**: Auto-restart failed services
- **Graceful degradation**: Local-only mode if cloud fails

---

## 8. Risks and Assumptions

### 8.1 Technical Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Local LLM requires ~4GB RAM | Mobile may struggle | Offer cloud-only mobile |
| First-run wizard complexity | User drop-off | Progressive disclosure |
| Module download failures | Broken install | Retry + fallback |

### 8.2 Assumptions

- Network available for initial setup (downloading modules)
- User has API key or accepts cloud-only mode
- Desktop has at least 4GB RAM for local mode
