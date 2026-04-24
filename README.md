# XenoSys

**A Hybrid AI Personal Operating System**

> Sovereignty. Transparency. Control.

XenoSys is a "Fat Server / Thin Client" AI operating system that runs AI agents on your local machine while providing secure remote access via mobile.

---

## 1. Value Proposition

XenoSys is a **Hybrid AI Personal Operating System** that gives you:

- **Sovereignty**: Your AI processing runs locally (or on your VPS), not in the cloud
- **Transparency**: Every agent decision is visible; you approve sensitive actions
- **Control**: Hit "Local Mode" for fully offline operation; switch to "Cloud Mode" for scale

### Support Matrix

| Platform | Standard | Plus | Notes |
|-----------|----------|------|-------|
| Windows Desktop | ✅ | ✅ | API mode, can add local LLM |
| macOS Desktop | ✅ | ✅ | API mode, can add local LLM |
| Linux Desktop | ✅ | ✅ | API mode, can add local LLM |
| iOS Mobile | Cloud Only | - | Connects to Desktop/VPS |
| Android Mobile | Cloud Only | - | Connects to Desktop/VPS |
| VPS (Docker) | ✅ | ✅ | API mode, can add local LLM |

---

## 2. Quick Start

### Step 1: Choose Your Platform

#### Desktop (Windows/macOS/Linux)
Download the installer for your platform:
- **Desktop Standard** (~200MB): All features, uses API mode
- **Desktop Plus** (~2GB): All features + local LLM (Ollama)

1. Go to https://xenosys.ai/download
2. Download `XenoSys-Setup.exe` (Windows) or `.dmg` (macOS)
3. Run the installer (Next → Next → Finish)
4. App opens to Step 2: Initial Settings Panel

#### VPS (Docker)
Choose your version:
- **VPS Standard**: `docker compose -f docker-compose.standard.yml up -d`
- **VPS Plus** (with local LLM): `docker compose -f docker-compose.plus.yml up -d`

#### Mobile (iOS/Android)
1. Install from App Store / Play Store
2. Connect to Desktop or VPS via WebSocket

### Step 2: Initial Settings Panel

After installation, the Settings Panel wizard appears:

1. **Basic Configuration**: Agent name, Instance ID
2. **LLM Provider Selection**:
   - **API Mode** (default): Enter API key for OpenAI/Anthropic/Google
   - **Local Mode**: Will install Ollama on-demand (~1.8GB)
3. **Integrations**: Telegram, Discord, MCP Tools
4. **Security**: Encryption, read-only mode

### Step 3: On-Demand Modules (Optional)

If you selected Local LLM mode, the on-demand module installer will:
1. Download and install Ollama
2. Download the selected model
3. Verify installation

### Post-Setup: Connect Mobile

After Desktop is running:
1. Go to **Network** → **Start Tunnel** → **Show QR Code**
2. Open mobile app → **Scan QR Code**

```bash
# Clone and run
git clone https://github.com/xenosys-ai/xenosys.git
cd xenosys/nexus
docker compose up -d
```

---

## 3. Architecture Overview

### Process Topology

```
┌────────────────────────────────────────────────────────────┐
│                    Desktop Mode                        │
│                                                        │
│  ┌────────┐     ┌──────────┐     ┌────────────┐      │
│  │ Tauri  │────▶│ Gateway  │────▶│   Core    │      │
│  │  (UI)  │◀────│  (3000)  │◀────│ (DSPy)   │      │
│  └────────┘     └──────────┘     └────────────┘      │
│       ▲                  │                              │
│       │                  ▼                              │
│       │           ┌────────────┐                    │
│       │           │ Cloudflare │─── Internet        │
│       │           │  Tunnel   │                  │
│       └───────────┴──────────┘                  │
└────────────────────────────────────────────────────────────┘
```

### State Sovereignty

| Data Type | Storage | Lifecycle |
|----------|--------|----------|
| Agent State | Redis (Event Bus) | Session-bound |
| Memory | Vector DB | Configurable TTL |
| Tunnel Config | Tauri Store | Persistent |
| Agent Logs | Memory (500 culled) | Session-bound |

**⚠️ AUDIT**: Python Core does NOT write to disk (except ephemeral logs).

### Network Security

- Gateway binds to `127.0.0.1:3000` (localhost only)
- No public port exposure
- Mobile connects via Cloudflare Tunnel (HTTPS 443)
- All API endpoints require JWT Bearer token

---

## 4. Security Model

### Secrets Management

- **OpenAI Key**: Stored in Tauri encrypted store → injected as environment variable to Gateway
- **Cloudflare Token**: Stored in Tauri store
- **JWT Secret**: Generated at first boot, never leaves machine

> ⚠️ **AUDIT TRIGGER**: API keys are NEVER passed as command-line arguments.

### MCP XSS Protection

All MCP tool responses are sanitized in the React layer (presentation) via DOMPurify:

```typescript
// MCPWidgetRenderer.tsx
import DOMPurify from 'dompurify';

const sanitized = DOMPurify.sanitize(payload, {
  ALLOWED_TAGS: ['b', 'i', 'em', 'strong'],
});
```

---

## 5. Survival Manual

### Fault Matrix

| Failure | UI Response | Recovery |
|---------|------------|----------|
| Ollama crash | Cyan banner: "Local Engine Unavailable" | Retry button or Cloud switch |
| Tunnel disconnect | Red indicator: "Disconnected" | Auto-reconnect on foreground |
| Redis OOM | Silent LRU eviction | Invisible to user |

### Resource Limits

- **Arena Logs**: 500 max (culled)
- **Gateway RAM**: Displayed in header
- **If > 12GB RAM**: Red indicator warning

---

## 6. Development

### Prerequisites

- Node.js 18+
- Python 3.11+
- Rust (latest stable)
- Ollama (optional, for local mode)

### Local Development

```bash
# Frontend
cd desktop && npm install && npm run dev

# Gateway
cd nexus/gateway && npm install && npm run dev

# Core
cd nexus/core && pip install -r requirements.txt
```

### Creating New Tools

MCP tools are independent. To add a new tool:

1. Create new MCP server in `nexus/gateway/src/mcp/`
2. Register in `nexus/gateway/src/plugins/manager.ts`
3. No modification to Core agent required

---

## 7. License

MIT License - See LICENSE file.

---

## 8. Links

- **Website**: https://xenosys.ai
- **Documentation**: https://docs.xenosys.ai
- **Discord**: https://discord.gg/xenosys
- **GitHub**: https://github.com/xenosys-ai/xenosys

---

*XenoSys: Your AI, Your Machine, Your Rules.*