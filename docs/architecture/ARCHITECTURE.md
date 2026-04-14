# XenoSys Architecture

## C4 Model - Context

XenoSys is a **Hybrid AI Personal Operating System** (Fat Server / Thin Client).

- **Users**: Individual developers and teams who want AI sovereignty
- **Systems**: Desktop (Windows/macOS/Linux), Mobile (iOS/Android), VPS (Docker)
- **External**: OpenAI API, Cloudflare Zero Trust, Vector Databases

---

## C4 Model - Container

### Desktop Container

```
┌─────────────────────────────────────────────────────────────┐
│                     Tauri (Rust)                         │
│  ┌─────────────────────────────────────────────────┐  │
│  │                  React (UI)                      │  │
│  │  ┌─────────┐  ┌──────────┐  ┌──────────────┐  │  │
│  │  │ Sidebar │  │  Arena   │  │ Governance │  │  │
│  │  └─────────┘  └──────────┘  └──────────────┘  │  │
│  └─────────────────────────────────────────────────┘  │
│                          │                             │
│  ┌──────────────┐   ┌────────────────────────────┐     │
│  │ Tauri Store  │   │  Sidecar Management     │     │
│  │  (Encrypted) │   │  (PID-based kill)      │     │
│  └──────────────┘   └────────────────────────────┘     │
└─────────────────────────────────────────────────────┘
         │ HTTP/WS           │ gRPC
         ▼                 ▼
┌─────────────────┐  ┌─────────────────┐
│   Gateway       │  │   Core         │
│  (Node.js)     │  │  (Python)      │
│   Port 3000   │  │  Port 50051    │
└─────────────────┘  └─────────────────┘
```

### Mobile Container

```
┌─────────────────────────────────────────────────────────────┐
│                  React Native (Mobile)                     │
│  ┌─────────────────────────────────────────┐            │
│  │           AppNavigator                   │            │
│  │  Chat │ Radar │ Briefing │ Status    │            │
│  └─────────────────────────────────────────┘            │
│                          │                             │
│  ┌─────────────────────────────────────────┐            │
│  │         useTunnelHealth                │            │
│  │  - AsyncStorage (persistent pairing)    │            │
│  │  - AppState listener (foreground event) │            │
│  │  - forceReconnect() on resume         │            │
│  └─────────────────────────────────────────┘            │
└─────────────────────────────────────────────────────────────┘
         │ HTTPS (via Cloudflare Tunnel)
         ▼
┌─────────────────┐
│    Gateway      │
│   (JWT auth)   │
└─────────────────┘
```

---

## IPC and Network Flow

### Ports

| Process | Port | Bind | Protocol | Exposure |
|---------|------|------|----------|----------|
| Gateway | 3000 | 127.0.0.1 | HTTP/WS | Internal only |
| Core | 50051 | 127.0.0.1 | gRPC | Internal only |
| Cloudflared | 443 | Outbound | HTTPS | Internet |

> ⚠️ **AUDIT**: Gateway never binds to `0.0.0.0`. All external traffic via Cloudflare Tunnel.

### Data Flow

1. **UI → Gateway**: REST/WebSocket (`localhost:3000`)
2. **Gateway → Core**: gRPC (`localhost:50051`)
3. **Core → Ollama**: HTTP (`localhost:11434`, optional)
4. **Mobile → Gateway**: HTTPS via Tunnel (JWT required)

---

## State Lifecycle

### State Sovereignty

| Data | Storage | Read/Write | Lifecycle |
|------|--------|---|---|
| Agent State | Redis | R/W | Session-bound |
| Memory | Vector DB | R/W | TTL configurable |
| Tunnel Config | Tauri Store | R/W | Persistent |
| JWT Secret | Tauri Store | W (first boot) | Persistent |
| API Keys | Tauri Store | R/W | Persistent |
| Logs | Memory | W | Culled at 500 |
| Session History | Redis | R/W | Session + 24h TTL |

> ⚠️ **AUDIT**: Python Core does NOT write to disk. All persistence via Redis or Tauri Store.

---

## Mobile Persistence

### AsyncStorage (React Native)

```typescript
// useTunnelHealth.ts
import AsyncStorage from '@react-native-async-storage/async-storage';

const TUNNEL_CONFIG_KEY = '@xenosys/tunnel_config';

// Load on mount
const savedRaw = await AsyncStorage.getItem(TUNNEL_CONFIG_KEY);
if (savedRaw) setConfig(JSON.parse(savedRaw));

// Save on pair
await AsyncStorage.setItem(TUNNEL_CONFIG_KEY, JSON.stringify(config));

// Clear on unpair
await AsyncStorage.removeItem(TUNNEL_CONFIG_KEY);
```

### Reconnection Policy

Mobile reconnect is triggered on `AppState` change to `active` (foreground):

```typescript
// useTunnelHealth.ts
useEffect(() => {
  const subscription = AppState.addEventListener('change', (nextState) => {
    if (appState.current.match(/inactive|background/) && nextState === 'active') {
      forceReconnect(); // Sync + validate
    }
    appState.current = nextState;
  });
  return () => subscription.remove();
}, [forceReconnect]);
```

> ✅ **CROSS-CHECK**: Mobile confirms AsyncStorage + foreground reconnection.

---

## Process Lifecycle

### Sidecar Management (Rust)

Sidecars (Gateway, Core) are managed via exact PIDs:

```rust
// main.rs - Stop sidecars
fn stop_sidecars(state: tauri::State<'_, AppState>) {
    let mut sidecar_state = state.sidecars.lock().unwrap();
    
    // Kill by exact PID, not name
    if let Some(pid) = sidecar_state.gateway_process {
        #[cfg(target_os = "windows")]
        Command::new("taskkill")
            .args(&["/F", "/PID", &pid.to_string()])
            .spawn()
            .ok();
    }
    
    sidecar_state.gateway_running = false;
    // ... same for Core
}
```

> ✅ **CROSS-CHECK**: Desktop termination uses `PID` (taskkill /PID), not string names.

---

## Security

### Network Binding

```typescript
// Gateway - Server.ts
app.listen({
  hostname: '127.0.0.1',  // ✅ Localhost only!
  port: 3000,
});
```

> ⚠️ **AUDIT**: Never `0.0.0.0`.

### Secrets Management

- **OpenAI Key**: Tauri Store → `env()` injection to Gateway process
- **JWT Secret**: Generated at first boot, stored in Tauri Store
- **Cloudflare Token**: Stored in Tauri Store

```rust
// Rust - Pass secrets via environment
Command::new("node")
    .env("OPENAI_API_KEY", api_key)  // ✅ Hidden from ps
    .env("JWT_SECRET", jwt_secret)
    .spawn()
```

> ⚠️ **AUDIT**: Keys NEVER passed as command-line arguments (`argv`).

---

## Extensibility

### MCP Tool Registration

New tools are independent MCP servers - no Core modification:

```typescript
// nexus/gateway/src/plugins/manager.ts
const pluginManager = new PluginManager();

pluginManager.register({
  name: 'notion',
  description: 'Notion API integration',
  server: new NotionMCPServer(config),
});
```

> ✅ **CROSS-CHECK**: Adding tools doesn't modify Core agent.

---

*This document proves the Architecture claims: Stateless Core, PID-based kill, AsyncStorage on Mobile.*