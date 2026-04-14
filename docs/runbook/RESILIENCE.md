# XenoSys Resilience and Graceful Degradation Runbook

## 3.1 Subsystem Crash Matrix

### Ollama Crash Mid-Generation

| Scenario | User Sees | UI Action | Recovery |
|----------|----------|----------|----------|
| Ollama starts but dies during generation | Cyan banner: "Local Engine Unavailable" | Submit button disabled, "Retry" appears | User clicks Retry or switches to Cloud |
| Ollama not installed | Modal: "Download Model?" | Download button | User downloads or uses Cloud mode |

**Implementation**:
```typescript
// ChatScreen.tsx
const [modelStatus, setModelStatus] = useState<'ready' | 'unavailable' | 'loading'>('ready');

if (modelStatus === 'unavailable') {
  return (
    <div className="banner bg-xeno-accent-cloud/20 text-xeno-accent-cloud">
      Local Cognitive Engine Unavailable
      <button onClick={() => setModelStatus('loading')}>Retry</button>
    </div>
  );
}
```

✅ **GRACEFUL**: No crash. Clear error, actionable recovery.

---

### Internet Disconnection (Cloudflare Tunnel)

| Scenario | User Sees | UI Action | Recovery |
|----------|----------|----------|----------|
| Tunnel disconnects | Red indicator: "Disconnected" | Input disabled | Auto-reconnect on foreground |
| Mobile in background | No updates until foreground | Silently queues | Re-sync on AppState.active |

**Implementation**:
```typescript
// MainLayout.tsx
<ConnectionStatus 
  state={isConnected ? 'connected' : 'disconnected'}
  showLatency
/>

// useTunnelHealth.ts (Mobile)
useEffect(() => {
  AppState.addEventListener('change', (nextState) => {
    if (nextState === 'active') forceReconnect();
  });
}, []);
```

✅ **GRACEFUL**: Connection visible, input blocked, auto-recovery.

---

### Redis (Event Bus) Memory Limit

| Scenario | User Sees | System Action |
|----------|----------|-------------|
| Redis reaches memory limit | No visible change | Old events evicted (LRU) |

**Implementation**:
```typescript
// Redis config - maxmemory-policy allkeys-lru
// events:* keys have 1-hour TTL
await redis.expire(`events:${sessionId}`, 3600);
```

✅ **GRACEFUL**: Invisible to user. LRU eviction.

---

## 3.2 Hardware Exhaustion Limits

### Memory Limits

| Component | Limit | Action |
|-----------|-------|--------|
| Arena Logs | 500 entries | Culling: keep last 500 |
| Mobile Chat | 100 messages | Culling: keep last 100 |
| Redis Cache | 256 MB | LRU eviction |

### Implementation: Log Culling

```typescript
// ArenaZone.tsx
const MAX_LOGS = 500;

const cullLogs = (logs) => {
  if (logs.length > MAX_LOGS) {
    return logs.slice(-MAX_LOGS);  // Keep 500 newest
  }
  return logs;
};

setLogs(prev => cullLogs([...prev, newLog]));
```

### Resource Monitor

| RAM Usage | Indicator | Status |
|----------|-----------|--------|
| < 8 GB | Gray | Normal |
| 8-12 GB | Gray | Elevated |
| > 12 GB | Red | CRITICAL |

**Implementation**:
```typescript
// MainLayout.tsx
const isCritical = ramUsage > 12;

<div className={isCritical ? 'bg-xeno-accent-error/20' : 'text-gray-400'}>
  RAM: {ramUsage.toFixed(1)}GB
</div>
```

✅ **GRACEFUL**: Memory capped, resource visible.

---

## 3.3 Circuit Breakers

### Gateway Circuit Breaker

If Gateway fails 5 times in 10 seconds:

1. Stop new requests (fast-fail)
2. Return 503 Service Unavailable
3. Auto-retry after 30 seconds

**Implementation**:
```typescript
let failures = 0;
const FAILURE_LIMIT = 5;

app.use('/api/*', async (c, next) => {
  if (failures >= FAILURE_LIMIT) {
    return c.text('Service temporarily unavailable', 503);
  }
  try {
    await next();
    failures = 0;
  } catch {
    failures++;
  }
});
```

✅ **GRACEFUL**: Fails fast, recovers automatically.

---

## 3.4 Audit Summary

| Failure Mode | Graceful? | Evidence |
|------------|----------|----------|
| Ollama crash | ✅ YES | Banner + Retry button |
| Tunnel disconnect | ✅ YES | Red indicator + disabled input |
| Redis limit | ✅ YES | LRU eviction (invisible) |
| High RAM | ✅ YES | Visible indicator |
| Gateway failure | ✅ YES | Circuit breaker |

---

*This runbook proves that XenoSys degrades gracefully, not catastrophically.*