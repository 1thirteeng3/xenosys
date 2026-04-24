/**
 * XenoSys Gateway - Core Types
 * Type definitions for the unified gateway layer
 */

import { z } from 'zod';

// ============================================================================
// Schema Definitions
// ============================================================================

export const MessageSchema = z.object({
  id: z.string(),
  channel: z.string(),
  userId: z.string(),
  content: z.string(),
  metadata: z.record(z.string(), z.unknown()).optional(),
  timestamp: z.number(),
  attachments: z.array(z.object({
    type: z.enum(['image', 'file', 'audio', 'video']),
    url: z.string(),
    name: z.string().optional(),
    mimeType: z.string().optional(),
  })).optional(),
});

export type Message = z.infer<typeof MessageSchema>;

export const ChannelConfigSchema = z.object({
  id: z.string(),
  type: z.string(),
  enabled: z.boolean().default(true),
  settings: z.record(z.string(), z.unknown()).optional(),
  auth: z.object({
    type: z.enum(['none', 'api_key', 'oauth2', 'webhook_secret']),
    credentials: z.record(z.string(), z.string()).optional(),
  }).optional(),
});

export type ChannelConfig = z.infer<typeof ChannelConfigSchema>;

export const UserSchema = z.object({
  id: z.string(),
  name: z.string().optional(),
  email: z.string().email().optional(),
  channels: z.record(z.string(), z.string()).optional(), // channel -> external_id
  metadata: z.record(z.string(), z.unknown()).optional(),
  createdAt: z.number(),
  lastSeenAt: z.number().optional(),
});

export type User = z.infer<typeof UserSchema>;

export const SessionSchema = z.object({
  id: z.string(),
  userId: z.string(),
  channel: z.string(),
  agentId: z.string().optional(),
  entityId: z.string().optional(),
  status: z.enum(['active', 'waiting', 'ended']),
  createdAt: z.number(),
  lastActivityAt: z.number(),
  messageCount: z.number().default(0),
  tokenCount: z.number().default(0),
});

export type Session = z.infer<typeof SessionSchema>;

// ============================================================================
// Agent Communication Protocol (ACP) Types
// ============================================================================

export const ACPMessageTypeSchema = z.enum([
  'request',
  'response',
  'error',
  'event',
  'stream_start',
  'stream_chunk',
  'stream_end',
  'heartbeat',
]);

export type ACPMessageType = z.infer<typeof ACPMessageTypeSchema>;

export const ACPMessageSchema = z.object({
  version: z.literal('1.0'),
  type: ACPMessageTypeSchema,
  id: z.string(),
  requestId: z.string().optional(), // For correlating responses
  timestamp: z.number(),
  source: z.object({
    nodeId: z.string(),
    agentId: z.string().optional(),
  }),
  target: z.object({
    nodeId: z.string(),
    agentId: z.string().optional(),
  }).optional(),
  payload: z.record(z.string(), z.unknown()),
  metadata: z.object({
    correlationId: z.string().optional(),
    ttl: z.number().optional(),
    priority: z.number().optional(),
  }).optional(),
});

export type ACPMessage = z.infer<typeof ACPMessageSchema>;

// ============================================================================
// Agent Execution Types
// ============================================================================

export const AgentRequestSchema = z.object({
  sessionId: z.string(),
  userId: z.string(),
  channel: z.string(),
  message: z.string(),
  attachments: z.array(z.string()).optional(),
  context: z.object({
    agentId: z.string().optional(),
    entityId: z.string().optional(),
    memoryFilters: z.record(z.string(), z.unknown()).optional(),
    systemPrompt: z.string().optional(),
  }).optional(),
  options: z.object({
    maxIterations: z.number().optional(),
    timeoutMs: z.number().optional(),
    temperature: z.number().optional(),
    model: z.string().optional(),
  }).optional(),
});

export type AgentRequest = z.infer<typeof AgentRequestSchema>;

export const AgentResponseSchema = z.object({
  sessionId: z.string(),
  messageId: z.string(),
  content: z.string(),
  done: z.boolean(),
  metadata: z.object({
    model: z.string(),
    tokensIn: z.number(),
    tokensOut: z.number(),
    costUsd: z.number(),
    latencyMs: z.number(),
    iterations: z.number(),
  }).optional(),
  toolCalls: z.array(z.object({
    name: z.string(),
    args: z.record(z.string(), z.unknown()),
    result: z.string().optional(),
    error: z.string().optional(),
  })).optional(),
  error: z.string().optional(),
});

export type AgentResponse = z.infer<typeof AgentResponseSchema>;

// ============================================================================
// Plugin System Types
// ============================================================================

export const PluginCapabilitySchema = z.enum([
  'channel',
  'tool',
  'memory_provider',
  'transform',
  'middleware',
  'analytics',
]);

export const PluginSchema = z.object({
  id: z.string(),
  name: z.string(),
  version: z.string(),
  description: z.string().optional(),
  capabilities: z.array(PluginCapabilitySchema),
  dependencies: z.array(z.string()).optional(),
  config: z.record(z.string(), z.unknown()).optional(),
  permissions: z.array(z.string()).optional(),
});

export type Plugin = z.infer<typeof PluginSchema>;

export const PluginHookSchema = z.object({
  name: z.string(),
  priority: z.number().default(0),
  handler: z.function(),
});

export type PluginHook = z.infer<typeof PluginHookSchema>;

// ============================================================================
// Gateway State
// ============================================================================

export interface GatewayState {
  nodeId: string;
  connected: boolean;
  sessions: Map<string, Session>;
  channels: Map<string, ChannelAdapter>;
  plugins: Map<string, PluginInstance>;
}

export interface ChannelAdapter {
  config: ChannelConfig;
  connect(): Promise<void>;
  disconnect(): Promise<void>;
  send(target: string, content: string, options?: Record<string, unknown>): Promise<void>;
  onMessage(handler: (message: Message) => Promise<void>): void;
  onConnect?(handler: () => void): void;
  onDisconnect?(handler: () => void): void;
  health(): Promise<{ status: 'healthy' | 'degraded' | 'down'; latency?: number }>;
}

export interface PluginInstance {
  plugin: Plugin;
  hooks: Map<string, Array<{ priority: number; handler: (ctx: unknown) => Promise<unknown> }>>;
  state: Map<string, unknown>;
  initialize(config: Record<string, unknown>): Promise<void>;
  shutdown(): Promise<void>;
}

// ============================================================================
// Event Types
// ============================================================================

export const GatewayEventSchema = z.object({
  type: z.enum([
    'message_received',
    'message_sent',
    'session_created',
    'session_ended',
    'agent_started',
    'agent_completed',
    'agent_error',
    'tool_called',
    'tool_result',
    'channel_connected',
    'channel_disconnected',
    'plugin_loaded',
    'plugin_unloaded',
    'hitl_pending',
    'hitl_approved',
    'hitl_rejected',
  ]),
  timestamp: z.number(),
  sessionId: z.string().optional(),
  userId: z.string().optional(),
  data: z.record(z.string(), z.unknown()).optional(),
});

export type GatewayEvent = z.infer<typeof GatewayEventSchema>;

export { z } from 'zod';
