/**
 * XenoSys Gateway - Security Middleware
 * Integrates security with Hono HTTP server
 */

import type { Context, Next } from 'hono';
import { SecurityManager, HMACValidator, APIKeyValidator, JWTValidator } from './security.js';

// ============================================================================
// Middleware Factories
// ============================================================================

/**
 * HMAC signature validation middleware for webhooks
 */
export function hmacMiddleware(validator: HMACValidator, signatureHeader = 'x-signature') {
  return async (c: Context, next: Next) => {
    const signature = c.req.header(signatureHeader);
    
    if (!signature) {
      return c.json({ error: 'Missing signature' }, 401);
    }
    
    // Read body
    const body = await c.req.text();
    
    // Verify signature
    if (!validator.validateWebhook(body, signature)) {
      return c.json({ error: 'Invalid signature' }, 401);
    }
    
    // Continue to handler
    await next();
  };
}

/**
 * API key validation middleware
 */
export function apiKeyMiddleware(validator: APIKeyValidator, keyHeader = 'x-api-key') {
  return async (c: Context, next: Next) => {
    const apiKey = c.req.header(keyHeader);
    
    if (!apiKey) {
      return c.json({ error: 'Missing API key' }, 401);
    }
    
    // Support key in header or as Bearer token
    let keyId = 'default';
    let keyValue = apiKey;
    
    if (apiKey.startsWith('key-')) {
      const parts = apiKey.split(':');
      if (parts.length === 2) {
        keyId = parts[0];
        keyValue = parts[1];
      }
    }
    
    const config = validator.validateKey(keyId, keyValue);
    
    if (!config) {
      return c.json({ error: 'Invalid API key' }, 401);
    }
    
    // Attach key config to context
    c.set('apiKey', config);
    
    await next();
  };
}

/**
 * JWT authentication middleware
 */
export function jwtMiddleware(validator: JWTValidator) {
  return async (c: Context, next: Next) => {
    const authHeader = c.req.header('Authorization');
    
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
    
    // Attach user to context
    c.set('user', payload);
    
    await next();
  };
}

/**
 * Role-based access control middleware
 */
export function rbacMiddleware(allowedRoles: string[]) {
  return async (c: Context, next: Next) => {
    const user = c.get('user');
    
    if (!user) {
      return c.json({ error: 'Authentication required' }, 401);
    }
    
    // Check if user has any required role
    const hasRole = user.roles.some((role: string) => allowedRoles.includes(role));
    
    if (!hasRole) {
      return c.json({ error: 'Insufficient permissions' }, 403);
    }
    
    await next();
  };
}

/**
 * Rate limiting middleware (simple in-memory)
 */
export function rateLimitMiddleware(
  windowMs: number = 60000,
  maxRequests: number = 100
) {
  const requests = new Map<string, { count: number; resetAt: number }>();
  
  return async (c: Context, next: Next) => {
    const ip = c.req.header('x-forwarded-for') || c.req.header('x-real-ip') || 'unknown';
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
    
    // Set rate limit headers
    c.res.headers.set('X-RateLimit-Limit', String(maxRequests));
    c.res.headers.set('X-RateLimit-Remaining', String(maxRequests - record.count));
    c.res.headers.set('X-RateLimit-Reset', String(Math.ceil(record.resetAt / 1000)));
    
    await next();
  };
}

// ============================================================================
// Security Router
// ============================================================================

export function createSecurityRoutes(security: SecurityManager) {
  const routes = {
    
    // Health check (no auth) - CORRIGIDO AQUI
    '/health': { GET: () => new Response(JSON.stringify({ status: 'ok' })) },
    
    // Generate API key (requires admin JWT)
    '/api/v1/security/keys': {
      POST: async (c: Context) => {
        if (!security.apiKeys) {
          return c.json({ error: 'API keys not configured' }, 500);
        }
        
        const body = await c.req.json();
        const keyId = `key-${Date.now()}`;
        const key = security.apiKeys.addKey(keyId, {
          name: body.name || 'API Key',
          permissions: body.permissions || ['read'],
          createdAt: Date.now(),
          expiresAt: body.expiresAt,
        });
        
        return c.json({ id: keyId, key });
      },
    },
    
    // List API keys (requires admin JWT)
    '/api/v1/security/keys/list': {
      GET: async (c: Context) => {
        if (!security.apiKeys) {
          return c.json({ error: 'API keys not configured' }, 500);
        }
        
        const keys = security.apiKeys.listKeys().map(id => ({
          id,
          ...security.apiKeys!.getKey(id),
          key: '***hidden***', // Don't expose actual keys
        }));
        
        return c.json({ keys });
      },
    },
    
    // Revoke API key
    '/api/v1/security/keys/:id': {
      DELETE: async (c: Context) => {
        if (!security.apiKeys) {
          return c.json({ error: 'API keys not configured' }, 500);
        }
        
        const id = c.req.param('id');
        const removed = security.apiKeys.removeKey(id);
        
        return c.json({ success: removed });
      },
    },
    
    // Refresh JWT
    '/api/v1/auth/refresh': {
      POST: async (c: Context) => {
        if (!security.jwt) {
          return c.json({ error: 'JWT not configured' }, 500);
        }
        
        const body = await c.req.json();
        const newToken = security.jwt.refresh(body.token);
        
        if (!newToken) {
          return c.json({ error: 'Invalid token' }, 401);
        }
        
        return c.json({ token: newToken });
      },
    },
  };
  
  return routes;
}

export default {
  hmacMiddleware,
  apiKeyMiddleware,
  jwtMiddleware,
  rbacMiddleware,
  rateLimitMiddleware,
  createSecurityRoutes,
};
