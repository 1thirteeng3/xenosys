# XenoSys System Architecture Document (SAD)

## 1.1 Network Topology and Port Diagram

### Processes and Ports

| Process | Language | Port | Protocol | Direction | Purpose |
|---------|----------|------|----------|----------|---------|
| Gateway | Node.js | 3000 | HTTP/WS | Internal | REST API + WebSocket |
| Core | Python | 50051 | gRPC | Internal | DSPy orchestration |
| Cloudflared | Binary | N/A | HTTPS | Outbound | Zero Trust tunnel |
| Ollama | Binary | 11434 | HTTP | Internal | Local LLM inference |
| Tauri | Rust | N/A | IPC | Parent | UI ↔ Sidecar bridge |

### Traffic Flow

```
┌─────────────────────────────────────────────────────────────┐
│                     User Machine                           │
│  ┌──────────┐     ┌──────────┐     ┌──────────┐            │
│  │  Tauri   │────▶│ Gateway  │────▶│   Core   │            │
│  │   (UI)   │◀────│  (3000)  │◀────│ (50051)  │            │
│  └──────────┘     └──────────┘     └──────────┘            │
│       ▲                 │                                  │
│       │                 │                                  │
│       │                 ▼                                  │
│       │           ┌──────────┐                             │
│       │           │ Cloudflare│──▶ Internet                 │
│       │           │  Tunnel   │   (HTTPS 443 Outbound)      │
│       └───────────└──────────┘                             │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Mobile Device                           │
│  ┌──────────┐                                          │
│  │  React   │◀─── HTTPS (via Cloudflare Tunnel)          │
│  │ Native  │                                           │
│  └──────────┘                                          │
└─────────────────────────────────────────────────────────────┘
```

### Port Exposure

**✓ SECURE**: Only Cloudflare Tunnel (HTTPS 443 Outbound) is exposed to the internet.

**PROHIBITED**:
- ❌ Gateway on 0.0.0.0:3000 (would expose REST API)
- ❌ Core on 0.0.0.0:50051 (would expose gRPC)
- ❌ Ollama on 0.0.0.0:11434 (would expose local LLM)

All sidecars bind to `127.0.0.1` (localhost only).

---

## 1.2 Interprocess Communication (IPC) Matrix

### Tauri → Gateway (Environment Variable Injection)

The OpenAI key travels via **hidden environment variables**, NOT:

- ❌ Command line arguments (visible in `ps`)
- ❌ Temporary .env files (written to disk)
- ❌ HTTP headers (visible in logs)

**Safe Flow**:

```
Tauri Store (encrypted)
        │
        ▼ (spawn_with_env)
Child Process
  └── process.env.OPENAI_API_KEY (hidden from ps)
```

**Implementation** (Rust):
```rust
Command::new("node")
    .arg("nexus/gateway/src/index.ts")
    .env("OPENAI_API_KEY", api_key)  // In-memory only
    .env("JWT_SECRET", jwt_secret)      // Generated at first boot
    .spawn()
```

### Gateway ↔ Core (gRPC)

| Method | Direction | Protocol | Payload |
|--------|----------|----------|----------|
| `/agent/execute` | Gateway → Core | gRPC | JSON (AgentRequest) |
| `/agent/stream` | Core → Gateway | gRPC (streaming) | Delta (Token deltas) |
| `/memory/store` | Gateway → Core | gRPC | JSON (MemoryItem) |
| `/memory/query` | Core → Gateway | gRPC | JSON (MemoryResult) |

### Gateway ← Mobile (HTTPS via Cloudflare Tunnel)

| Endpoint | Auth | Purpose |
|-----------|------|----------|
| `/api/v1/agent/execute` | JWT Bearer | Execute agent |
| `/api/v1/governance/pending` | JWT Bearer | HITL queue |
| `/api/v1/sessions/current/sync` | JWT Bearer | Message sync |

---

## 1.3 Audit Results

| Check | Status | Notes |
|-------|--------|-------|
| No public port exposure | ✅ PASS | All bind to 127.0.0.1 |
| Credentials via env var | ✅ PASS | `spawn_with_env` |
| gRPC internal only | ✅ PASS | No external exposure |
| Mobile via tunnel only | ✅ PASS | HTTPS 443 only |

---

*This document proves the Network Topology claim: "Sovereignty and Security"*