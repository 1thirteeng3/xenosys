/**
 * XenoSys Gateway - HTTP/WS Server
 * Main entry point with Hono framework integration
 */
import { serve } from '@hono/node-server';
import { Hono } from 'hono';
import { cors } from 'hono/cors';
import { logger } from 'hono/logger';
import { v4 as uuid } from 'uuid';
import * as os from 'os';
import pino from 'pino';

import { eventBus } from './event-bus.js';
import { type Message, type AgentRequest, type Session, AgentRequestSchema } from './types.js';
import { ChannelManager } from '../channels/manager.js';
import { PluginManager } from '../plugins/manager.js';
import { GRPCBridge } from '../grpc/bridge.js';

const config = { 
  port: parseInt(process.env['PORT'] ?? '3000', 10), 
  isDesktop: process.env['TAURI_ENV'] === 'true', 
  host: process.env['HOST'] ?? (process.env['TAURI_ENV'] === 'true' ? '127.0.0.1' : '0.0.0.0'), 
  logLevel: process.env['LOG_LEVEL'] ?? 'info', 
  grpcEndpoint: process.env['GRPC_ENDPOINT'] ?? 'localhost:50051', 
  wsPath: '/ws', 
  apiPrefix: '/api/v1', 
  corsOrigins: process.env['CORS_ORIGINS']?.split(',') ?? ['*'],
};

const logger$ = pino({ 
  level: config.logLevel,
});

interface GatewayState { 
  nodeId: string; 
  startTime: number; 
  sessions: Map<string, Session>; 
  connectedClients: Set<string>;
}

const state: GatewayState = { 
  nodeId: 'gateway-' + uuid().slice(0, 8), 
  startTime: Date.now(), 
  sessions: new Map(), 
  connectedClients: new Set(),
};

const app = new Hono<{ Variables: GatewayState & { requestId: string } }>();

app.use('*', logger((msg: string) => logger$.info(msg)));
app.use('*', cors({ origin: config.corsOrigins, credentials: true }));

app.use('*', async (c, next) => { 
  c.set('requestId', uuid()); 
  await next();
});

app.get('/health', (c) => { 
  const uptime = (Date.now() - state.startTime) / 1000; 
  const freeMem = os.freemem(); 
  const totalMem = os.totalmem(); 
  const usedMemPercent = ((totalMem - freeMem) / totalMem) * 100; 
  const cpus = os.cpus(); 
  let cpuIdle = 0; 
  let cpuTotal = 0; 
  for (const cpu of cpus) { 
    for (const type in cpu.times) { 
      cpuTotal += cpu.times[type as keyof typeof cpu.times]; 
    } 
    cpuIdle += cpu.times.idle; 
  } 
  const cpuUsagePercent = ((cpuTotal - cpuIdle) / cpuTotal) * 100; 

  return c.json({ 
    status: 'healthy', 
    nodeId: state.nodeId, 
    uptime, 
    sessions: state.sessions.size, 
    connections: state.connectedClients.size, 
    hardware: { 
      ramUsagePercent: usedMemPercent.toFixed(2), 
      totalRamGB: (totalMem / 1024 / 1024 / 1024).toFixed(2), 
      cpuUsagePercent: cpuUsagePercent.toFixed(2), 
      cpuCores: cpus.length, 
    }, 
    version: '1.0.0', 
  });
});

app.get('/ready', async (c) => { 
  const checks = { grpc: false, channels: false }; 
  try { checks.grpc = await GRPCBridge.getInstance().isHealthy(); } catch { checks.grpc = false; } 
  try { checks.channels = ChannelManager.getInstance().isHealthy(); } catch { checks.channels = false; } 
  const ready = checks.grpc && checks.channels; 
  return c.json({ ready, checks, nodeId: state.nodeId }, ready ? 200 : 503);
});

const api = new Hono();

api.get('/info', (c) => c.json({ nodeId: state.nodeId, version: '1.0.0', capabilities: ['channels', 'acp', 'grpc_bridge'] }));

api.get('/sessions', (c) => { 
  const sessions = Array.from(state.sessions.values()).map(s => ({ 
    id: s.id, userId: s.userId, channel: s.channel, status: s.status, 
    messageCount: s.messageCount, createdAt: s.createdAt, lastActivityAt: s.lastActivityAt, 
  })); 
  return c.json({ sessions });
});

api.get('/sessions/:id', (c) => { 
  const session = state.sessions.get(c.req.param('id') ?? ''); 
  if (!session) return c.json({ error: 'Session not found' }, 404); 
  return c.json({ session });
});

api.delete('/sessions/:id', (c) => { 
  const sessionId = c.req.param('id') ?? ''; 
  const deleted = state.sessions.delete(sessionId ?? ''); 
  if (deleted && sessionId) { 
    eventBus.publish({ type: 'session_ended', timestamp: Date.now(), sessionId }); 
  } 
  return c.json({ deleted });
});

api.post('/agent/execute', async (c) => { 
  try { 
    const body = await c.req.json(); 
    const request = AgentRequestSchema.parse(body); 
    const session = state.sessions.get(request.sessionId); 
    if (!session) return c.json({ error: 'Session not found' }, 404); 

    eventBus.publish({ 
      type: 'agent_started', timestamp: Date.now(), sessionId: request.sessionId, userId: request.userId, data: { channel: request.channel }, 
    }); 

    const bridge = GRPCBridge.getInstance(); 
    const response = await bridge.executeAgent(request); 

    session.messageCount++; 
    session.lastActivityAt = Date.now(); 
    state.sessions.set(session.id, session); 

    eventBus.publish({ 
      type: 'agent_completed', timestamp: Date.now(), sessionId: request.sessionId, 
      data: { messageId: response.messageId, done: response.done, tokens: response.metadata?.tokensOut }, 
    }); 

    return c.json(response); 
  } catch (error) { 
    const message = error instanceof Error ? error.message : 'Unknown error'; 
    logger$.error({ error }, 'Agent execution failed'); 
    return c.json({ error: message, sessionId: c.req.param('sessionId') }, 500); 
  }
});

app.route(config.apiPrefix, api);

app.onError((err, c) => { 
  logger$.error({ err, path: c.req.path }, 'Unhandled error'); 
  return c.json({ error: 'Internal server error', requestId: c.get('requestId') }, 500);
});

app.notFound((c) => c.json({ error: 'Not found', path: c.req.path }, 404));

async function startServer() { 
  logger$.info({ config }, 'Starting XenoSys Gateway'); 
  try { 
    await GRPCBridge.getInstance().connect({ endpoint: config.grpcEndpoint }); 
    logger$.info('gRPC bridge connected'); 
  } catch (error) { 
    logger$.warn({ error }, 'gRPC bridge connection failed - will retry'); 
  } 

  const server = serve({ fetch: app.fetch, port: config.port, hostname: config.host }); 
  logger$.info('Server listening on ' + config.host + ':' + config.port); 

  const shutdown = async() => { 
    logger$.info('Shutdown signal received'); 
    server.close(); 
    await GRPCBridge.getInstance().disconnect(); 
    process.exit(0); 
  }; 

  process.on('SIGTERM', shutdown); 
  process.on('SIGINT', shutdown);

  return server;
}

startServer().catch((error) => {
  logger$.error({ error }, 'Failed to start server');
  process.exit(1);
});

export { app, state, startServer };
