/**
 * XenoSys Gateway - Channel System
 * Base channel adapter interface
 */

import { EventEmitter } from 'events';
import { v4 as uuid } from 'uuid';
import { z } from 'zod';
import { ChannelConfig, ChannelConfigSchema, Message, MessageSchema } from '../gateway/types.js';
import { eventBus } from '../gateway/event-bus.js';

// ============================================================================
// Channel Configuration
// ============================================================================

export interface ChannelCredentials {
  type: 'none' | 'api_key' | 'oauth2' | 'webhook_secret' | 'bot_token';
  config: Record<string, string>;
}

export interface ChannelOptions {
  config: ChannelConfig;
  credentials?: ChannelCredentials;
  eventBus?: typeof eventBus;
}

// ============================================================================
// Channel Adapter Interface
// ============================================================================

export abstract class ChannelAdapter extends EventEmitter {
  readonly id: string;
  readonly type: string;
  protected config: ChannelConfig;
  protected credentials?: ChannelCredentials;
  protected connected = false;
  protected messageHandler?: (message: Message) => Promise<void>;

  constructor(options: ChannelOptions) {
    super();
    this.id = options.config.id;
    this.type = options.config.type;
    this.config = options.config;
    this.credentials = options.credentials;
  }

  /**
   * Connect to the channel
   */
  abstract connect(): Promise<void>;

  /**
   * Disconnect from the channel
   */
  abstract disconnect(): Promise<void>;

  /**
   * Send a message to a target
   */
  abstract send(target: string, content: string, options?: Record<string, unknown>): Promise<void>;

  /**
   * Get channel health status
   */
  abstract health(): Promise<{ status: 'healthy' | 'degraded' | 'down'; latency?: number; error?: string }>;

  /**
   * Set the message handler for incoming messages
   */
  onMessage(handler: (message: Message) => Promise<void>): void {
    this.messageHandler = handler;
  }

  /**
   * Check if connected
   */
  isConnected(): boolean {
    return this.connected;
  }

  /**
   * Get channel metadata
   */
  getMetadata(): Record<string, unknown> {
    return {
      id: this.id,
      type: this.type,
      connected: this.connected,
    };
  }

  /**
   * Emit a received message through the event bus
   */
  protected async emitMessage(message: Message): Promise<void> {
    // Validate message
    const parsed = MessageSchema.safeParse(message);
    if (!parsed.success) {
      console.error('Invalid message:', parsed.error);
      return;
    }

    // Store handler reference
    const validMessage = parsed.data;

    // Publish to event bus
    await eventBus.publish({
      type: 'message_received',
      timestamp: Date.now(),
      sessionId: undefined,
      userId: validMessage.userId,
      data: { channel: this.id, message: validMessage },
    });

    // Call local handler if set
    if (this.messageHandler) {
      await this.messageHandler(validMessage);
    }

    // Emit local event
    this.emit('message', validMessage);
  }

  /**
   * Emit a sent message event
   */
  protected async emitSent(target: string, content: string): Promise<void> {
    await eventBus.publish({
      type: 'message_sent',
      timestamp: Date.now(),
      data: { channel: this.id, target, content },
    });
  }
}

// ============================================================================
// Channel Factory
// ============================================================================

export type ChannelAdapterConstructor = new (options: ChannelOptions) => ChannelAdapter;

const channelRegistry: Map<string, ChannelAdapterConstructor> = new Map();

/**
 * Register a channel adapter
 */
export function registerChannel(type: string, adapter: ChannelAdapterConstructor): void {
  channelRegistry.set(type, adapter);
}

/**
 * Create a channel adapter by type
 */
export function createChannel(options: ChannelOptions): ChannelAdapter {
  const Constructor = channelRegistry.get(options.config.type);
  if (!Constructor) {
    throw new Error(`Unknown channel type: ${options.config.type}`);
  }
  return new Constructor(options);
}

/**
 * Get all registered channel types
 */
export function getRegisteredChannels(): string[] {
  return Array.from(channelRegistry.keys());
}