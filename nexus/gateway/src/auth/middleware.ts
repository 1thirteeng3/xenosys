/**
 * XenoSys Gateway - Security Middleware
 * Integrates security with Hono HTTP server
 */
import type { Context, Next } from 'hono';
import { type SecurityManager, type HMACValidator, type APIKeyValidator, type JWTValidator } from './security.js';

// ============================================================================
// Middleware Factories
// ============================================================================

export function hmacMiddleware(validator: HMACValidator, signatureHeader = 'x-signature') {
  return async (c: Context, next: Next): Promise<Response> => {
    const signature = c.req.header(signatureHeader);
    if (!signature) {
      return c.json({ error: 'Missing signature' }, 401);
    }
    const body = await c.req.text();
    if (!validator.validateWebhook(body, signature)) {
      return c.json({ error: 'Invalid signature' }, 401);
    }
    await next();
    return new Response(null, { status: 200 });
  };
}

export function apiKeyMiddleware(validator: APIKeyValidator, keyHeader = 'x-api-key') {
  return async (c: Context, next: Next): Promise<Response> => {
    const apiKey = c.req.header(keyHeader) ?? '';
    if (!apiKey) {
      return c.json({ error: 'Missing API key' }, 401);
    }
    let keyId = 'default';
    let keyValue = apiKey;
    if (apiKey.startsWith('key-')) {
      const parts = apiKey.split(':');
      if (parts.length === 2) {
        keyId = parts[0] ?? 'default';
        keyValue = parts[1] ?? apiKey;
      }
    }
    const config = validator.validateKey(keyId, keyValue);
    if (!config) {
      return c.json({ error: 'Invalid API key' }, 401);
    }
    c.set('apiKey', config);
    await next();
    return new Response(null, { status: 200 });
  };
}

export function jwtMiddleware(validator: JWTValidator) {
  return async (c: Context, next: Next): Promise<Response> => {
    const authHeader = c.req.header('Authorization') ?? '';
    if (!authHeader) {
      return c.json({ error: 'Missing Authorization header' }, 401);
    }
    const token = validator.extractFromHeader(authHeader);
    if (!token) {
      return c.json({ error: 'Invalid Authorization format' }, 401);
    }
    const payload = validator.verify(token);
    if (!payload) {
      return c.json({ error: 'Invalid or expired token' }, 401);
    }
    c.set('user', payload);
    await next();
    return new Response(null, { status: 200 });
  };
}

export function rbacMiddleware(allowedRoles: string[]) {
  return async (c: Context, next: Next): Promise<Response> => {
    const user = c.get('user');
    if (!user) {
      return c.json({ error: 'Authentication required' }, 401);
    }
    const hasRole = user.roles?.some((role: string) => allowedRoles.includes(role)) ?? false;
    if (!hasRole) {
      return c.json({ error: 'Insufficient permissions' }, 403);
    }
    await next();
    return new Response(null, { status: 200 });
  };
}

export function rateLimitMiddleware(
  windowMs: number = 60000,
  maxRequests: number = 100
) {
  const requests = new Map<string, { count: number; resetAt: number }>();
  return async (c: Context, next: Next): Promise<Response> => {
    const ip = c.req.header('x-forwarded-for') ?? c.req.header('x-real-ip') ?? 'unknown';
    const now = Date.now();
    let record = requests.get(ip);
    if (!record || now > record.resetAt) {
      record = { count: 0, resetAt: now + windowMs };
      requests.set(ip, record);
    }
    record.count++;
    if (record.count > maxRequests) {
      return c.json(
        { error: 'Rate limit exceeded', retryAfter: Math.ceil((record.resetAt - now) / 1000) },
        429
      );
    }
    c.res?.headers?.set('X-RateLimit-Limit', String(maxRequests));
    c.res?.headers?.set('X-RateLimit-Remaining', String(Math.max(0, maxRequests - record.count)));
    c.res?.headers?.set('X-RateLimit-Reset', String(Math.ceil(record.resetAt / 1000)));
    await next();
    return new Response(null, { status: 200 });
  };
}

export function createSecurityRoutes(security: SecurityManager) {
  return {
    '/health': { GET: () => new Response(JSON.stringify({ status: 'ok' })) },
    '/api/v1/security/keys': {
      POST: async (c: Context) => {
        if (!security.apiKeys) {
          return c.json({ error: 'API keys not configured' }, 500);
        }
        const body = await c.req.json() as Record<string, unknown> ?? {};
        const keyId = 'key-' + Date.now();
        const key = security.apiKeys.addKey(keyId, {
          name: (body.name as string) ?? 'API Key',
          permissions: (body.permissions as string[]) ?? ['read'],
          createdAt: Date.now(),
          expiresAt: body.expiresAt as number | undefined,
        });
        return c.json({ id: keyId, key });
      },
    },
    '/api/v1/security/keys/list': {
      GET: async (c: Context) => {
        if (!security.apiKeys) {
          return c.json({ error: 'API keys not configured' }, 500);
        }
        const keys = security.apiKeys.listKeys().map(id => ({
          id,
          ...security.apiKeys!.getKey(id),
          key: '***hidden***',
        }));
        return c.json({ keys });
      },
    },
    '/api/v1/security/keys/:id': {
      DELETE: async (c: Context) => {
        if (!security.apiKeys) {
          return c.json({ error: 'API keys not configured' }, 500);
        }
        const id = c.req.param('id') ?? '';
        const removed = security.apiKeys.removeKey(id);
        return c.json({ success: removed });
      },
    },
    '/api/v1/auth/refresh': {
      POST: async (c: Context) => {
        if (!security.jwt) {
          return c.json({ error: 'JWT not configured' }, 500);
        }
        const body = await c.req.json() as Record<string, unknown> ?? {};
        const newToken = security.jwt.refresh((body.token as string) ?? '');
        if (!newToken) {
          return c.json({ error: 'Invalid token' }, 401);
        }
        return c.json({ token: newToken });
      },
    },
  };
}

export default {
  hmacMiddleware,
  apiKeyMiddleware,
  jwtMiddleware,
  rbacMiddleware,
  rateLimitMiddleware,
  createSecurityRoutes,
};
