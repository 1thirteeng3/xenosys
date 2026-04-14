/**
 * XenoSys Gateway - HTTP/WS Server
 * Main entry point with Hono framework integration
 */

import { serve } from '@hono/node-server';
import { Hono } from 'hono';
import { cors } from 'hono/cors';
import { logger } from 'hono/logger';
import { websocket } from 'hono/ws';
import { v4 as uuid } from 'uuid';
import pino from 'pino';

import { eventBus, EventBus } from './event-bus.js';
import { type Message, type AgentRequest, type Session, MessageSchema, AgentRequestSchema } from './types.js';
import { ChannelManager } from '../channels/manager.js';
import { PluginManager } from '../plugins/manager.js';
import { GRPCBridge } from '../grpc/bridge.js';

// ============================================================================
// Configuration
// ============================================================================

const config = {
  port: parseInt(process.env['PORT'] ?? '3000', 10),
  host: process.env['HOST'] ?? '0.0.0.0',
  logLevel: (process.env['LOG_LEVEL'] ?? 'info') as pino.Level,
  grpcEndpoint: process.env['GRPC_ENDPOINT'] ?? 'localhost:50051',
  wsPath: '/ws',
  apiPrefix: '/api/v1',
  corsOrigins: process.env['CORS_ORIGINS']?.split(',') ?? ['*'],
};

// ============================================================================
// Logger Setup
// ============================================================================

const logger$ = pino({
  level: config.logLevel,
  transport: process.env['NODE_ENV'] === 'development'
    ? { target: 'pino-pretty', options: { colorize: true } }
    : undefined,
});

// ============================================================================
// Application State
// ============================================================================

interface GatewayState {
  nodeId: string;
  startTime: number;
  sessions: Map<string, Session>;
  connectedClients: Set<string>;
}

const state: GatewayState = {
  nodeId: `gateway-${uuid().slice(0, 8)}`,
  startTime: Date.now(),
  sessions: new Map(),
  connectedClients: new Set(),
};

// ============================================================================
// Hono Application
// ============================================================================

const app = new Hono<{ Variables: GatewayState }>();

// Middleware
app.use('*', logger((msg, args) => logger$.info({ args }, msg)));
app.use('*', cors({
  origin: config.corsOrigins,
  credentials: true,
}));

// Request ID middleware
app.use('*', async (c, next) => {
  c.set('requestId', uuid());
  await next();
});

// Health check endpoint
app.get('/health', (c) => {
  const uptime = (Date.now() - state.startTime) / 1000;
  return c.json({
    status: 'healthy',
    nodeId: state.nodeId,
    uptime,
    sessions: state.sessions.size,
    connections: state.connectedClients.size,
    version: '1.0.0',
  });
});

// Readiness check (includes dependency checks)
app.get('/ready', async (c) => {
  const checks = {
    grpc: false,
    channels: false,
  };

  try {
    checks.grpc = await GRPCBridge.getInstance().isHealthy();
  } catch {
    checks.grpc = false;
  }

  try {
    checks.channels = ChannelManager.getInstance().isHealthy();
  } catch {
    checks.channels = false;
  }

  const ready = checks.grpc && checks.channels;

  return c.json({
    ready,
    checks,
    nodeId: state.nodeId,
  }, ready ? 200 : 503);
});

// API Routes
const api = new Hono();

// Get current node info
api.get('/info', (c) => {
  return c.json({
    nodeId: state.nodeId,
    version: '1.0.0',
    capabilities: ['channels', 'acp', 'grpc_bridge', 'websocket'],
  });
});

// Session management
api.get('/sessions', (c) => {
  const sessions = Array.from(state.sessions.values()).map(s => ({
    id: s.id,
    userId: s.userId,
    channel: s.channel,
    status: s.status,
    messageCount: s.messageCount,
    createdAt: s.createdAt,
    lastActivityAt: s.lastActivityAt,
  }));
  return c.json({ sessions });
});

api.get('/sessions/:id', (c) => {
  const session = state.sessions.get(c.req.param('id'));
  if (!session) {
    return c.json({ error: 'Session not found' }, 404);
  }
  return c.json({ session });
});

api.delete('/sessions/:id', (c) => {
  const sessionId = c.req.param('id');
  const deleted = state.sessions.delete(sessionId);
  if (deleted) {
    eventBus.publish({
      type: 'session_ended',
      timestamp: Date.now(),
      sessionId,
    });
  }
  return c.json({ deleted });
});

// Agent execution endpoint
api.post('/agent/execute', async (c) => {
  try {
    const body = await c.req.json();
    const request = AgentRequestSchema.parse(body);

    const session = state.sessions.get(request.sessionId);
    if (!session) {
      return c.json({ error: 'Session not found' }, 404);
    }

    // Publish agent started event
    eventBus.publish({
      type: 'agent_started',
      timestamp: Date.now(),
      sessionId: request.sessionId,
      userId: request.userId,
      data: { channel: request.channel },
    });

    // Execute via gRPC bridge
    const bridge = GRPCBridge.getInstance();
    const response = await bridge.executeAgent(request);

    // Update session
    session.messageCount++;
    session.lastActivityAt = Date.now();
    state.sessions.set(session.id, session);

    // Publish completion
    eventBus.publish({
      type: 'agent_completed',
      timestamp: Date.now(),
      sessionId: request.sessionId,
      data: {
        messageId: response.messageId,
        done: response.done,
        tokens: response.metadata?.tokensOut,
      },
    });

    return c.json(response);
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unknown error';
    logger$.error({ error }, 'Agent execution failed');

    return c.json({
      error: message,
      sessionId: c.req.param('sessionId'),
    }, 500);
  }
});

// HITL approval endpoint
api.post('/hitl/:requestId/approve', async (c) => {
  const requestId = c.req.param('requestId');

  eventBus.publish({
    type: 'hitl_approved',
    timestamp: Date.now(),
    data: { requestId },
  });

  return c.json({ success: true, requestId });
});

api.post('/hitl/:requestId/reject', async (c) => {
  const requestId = c.req.param('requestId');

  eventBus.publish({
    type: 'hitl_rejected',
    timestamp: Date.now(),
    data: { requestId },
  });

  return c.json({ success: true, requestId });
});

// Event subscription (SSE)
api.get('/events', async (c) => {
  const eventTypes = c.req.query('types')?.split(',') as string[] | undefined;
  const sessionId = c.req.query('sessionId');

  const headers = new Headers({
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    'X-Accel-Buffering': 'no',
  });

  c.res = new Response(new ReadableStream({
    start(controller) {
      const clientId = uuid();
      state.connectedClients.add(clientId);

      // Send initial connection event
      controller.enqueue(`data: ${JSON.stringify({ type: 'connected', clientId })}\n\n`);

      // Subscribe to events
      const subscriptionId = eventBus.subscribe(
        eventTypes as any || '*',
        async (event) => {
          // Filter by session if specified
          if (sessionId && event.sessionId !== sessionId) return;

          const data = `data: ${JSON.stringify(event)}\n\n`;
          try {
            controller.enqueue(data);
          } catch {
            // Client disconnected
            state.connectedClients.delete(clientId);
            eventBus.unsubscribe(subscriptionId);
          }
        }
      );

      // Heartbeat
      const heartbeat = setInterval(() => {
        try {
          controller.enqueue(`: heartbeat\n\n`);
        } catch {
          clearInterval(heartbeat);
          state.connectedClients.delete(clientId);
          eventBus.unsubscribe(subscriptionId);
        }
      }, 30000);

      // Cleanup on close
      c.req.raw.signal.addEventListener('abort', () => {
        clearInterval(heartbeat);
        state.connectedClients.delete(clientId);
        eventBus.unsubscribe(subscriptionId);
      });
    },
  }), { headers });
});

// Mount API routes
app.route(config.apiPrefix, api);

// WebSocket endpoint
app.get(config.wsPath, async (c) => {
  // WebSocket handling would go here
  // For now, return upgrade header error
  return c.json({ error: 'WebSocket upgrade required' }, 426);
});

// Error handler
app.onError((err, c) => {
  logger$.error({ err, path: c.req.path }, 'Unhandled error');
  return c.json({
    error: 'Internal server error',
    requestId: c.get('requestId'),
  }, 500);
});

// 404 handler
app.notFound((c) => {
  return c.json({
    error: 'Not found',
    path: c.req.path,
  }, 404);
});

// ============================================================================
// Server Lifecycle
// ============================================================================

async function startServer() {
  logger$.info({ config }, 'Starting XenoSys Gateway');

  // Initialize gRPC bridge
  try {
    await GRPCBridge.getInstance().connect(config.grpcEndpoint);
    logger$.info('gRPC bridge connected');
  } catch (error) {
    logger$.warn({ error }, 'gRPC bridge connection failed - will retry');
  }

  // Initialize channel manager
  try {
    await ChannelManager.getInstance().initialize();
    logger$.info('Channel manager initialized');
  } catch (error) {
    logger$.warn({ error }, 'Channel manager initialization failed');
  }

  // Initialize plugin manager
  try {
    await PluginManager.getInstance().loadPlugins();
    logger$.info('Plugins loaded');
  } catch (error) {
    logger$.warn({ error }, 'Plugin loading failed');
  }

  // Start HTTP server
  const server = serve({
    fetch: app.fetch,
    port: config.port,
    hostname: config.host,
  });

  logger$.info(`Server listening on ${config.host}:${config.port}`);
  logger$.info(`API endpoint: http://${config.host}:${config.port}${config.apiPrefix}`);
  logger$.info(`Health check: http://${config.host}:${config.port}/health`);

  // Graceful shutdown
  const shutdown = async (signal: string) => {
    logger$.info({ signal }, 'Shutdown signal received');

    // Stop accepting connections
    server.close();

    // Cleanup resources
    await GRPCBridge.getInstance().disconnect();
    await ChannelManager.getInstance().shutdown();
    await PluginManager.getInstance().unloadAll();

    logger$.info('Server shutdown complete');
    process.exit(0);
  };

  process.on('SIGTERM', () => shutdown('SIGTERM'));
  process.on('SIGINT', () => shutdown('SIGINT'));

  return server;
}

// Start server if running directly
startServer().catch((error) => {
  logger$.error({ error }, 'Failed to start server');
  process.exit(1);
});

export { app, state, startServer };