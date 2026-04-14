/**
 * XenoSys Gateway - Channel Manager
 * Manages all channel adapters
 */

import { readFileSync, existsSync } from 'fs';
import { parse as parseYaml } from 'yaml';
import { ChannelAdapter, ChannelOptions, createChannel, registerChannel } from './base.js';
import { TelegramAdapter } from './telegram.js';
import { DiscordAdapter } from './discord.js';
import { SlackAdapter } from './slack.js';
import { WebhookAdapter } from './webhook.js';
import { APIAdapter } from './api.js';
import { ChannelConfig, ChannelConfigSchema } from '../gateway/types.js';
import { eventBus } from '../gateway/event-bus.js';

// ============================================================================
// Channel Registry
// ============================================================================

// Register built-in channels
registerChannel('telegram', TelegramAdapter);
registerChannel('discord', DiscordAdapter);
registerChannel('slack', SlackAdapter);
registerChannel('webhook', WebhookAdapter);
registerChannel('api', APIAdapter);

// ============================================================================
// Channel Manager
// ============================================================================

export class ChannelManager {
  private static instance: ChannelManager;
  private channels: Map<string, ChannelAdapter> = new Map();
  private configPath: string;
  private initialized = false;

  private constructor(configPath?: string) {
    this.configPath = configPath ?? process.env['CHANNEL_CONFIG_PATH'] ?? './config/channels.yaml';
  }

  static getInstance(configPath?: string): ChannelManager {
    if (!ChannelManager.instance) {
      ChannelManager.instance = new ChannelManager(configPath);
    }
    return ChannelManager.instance;
  }

  /**
   * Initialize all configured channels
   */
  async initialize(): Promise<void> {
    if (this.initialized) return;

    // Load channel configurations
    const configs = await this.loadConfigs();

    // Initialize each channel
    for (const config of configs) {
      if (!config.enabled) {
        console.log(`Channel ${config.id} is disabled, skipping`);
        continue;
      }

      try {
        await this.addChannel(config);
      } catch (error) {
        console.error(`Failed to initialize channel ${config.id}:`, error);
      }
    }

    this.initialized = true;
  }

  /**
   * Load channel configurations from file
   */
  private async loadConfigs(): Promise<ChannelConfig[]> {
    if (!existsSync(this.configPath)) {
      console.warn(`Channel config file not found: ${this.configPath}`);
      return [];
    }

    try {
      const content = readFileSync(this.configPath, 'utf-8');
      const parsed = parseYaml(content);

      // Handle both array and object formats
      const configs = Array.isArray(parsed) ? parsed : parsed['channels'] ?? [];

      // Validate each config
      return configs.map((config: unknown) => {
        const result = ChannelConfigSchema.safeParse(config);
        if (!result.success) {
          console.warn('Invalid channel config:', result.error);
          return null;
        }
        return result.data;
      }).filter(Boolean) as ChannelConfig[];
    } catch (error) {
      console.error(`Failed to load channel configs:`, error);
      return [];
    }
  }

  /**
   * Add and start a channel
   */
  async addChannel(config: ChannelConfig): Promise<ChannelAdapter> {
    if (this.channels.has(config.id)) {
      throw new Error(`Channel ${config.id} already exists`);
    }

    const options: ChannelOptions = {
      config,
      credentials: this.loadCredentials(config.id),
    };

    const adapter = createChannel(options);

    // Set up event forwarding
    adapter.on('message', async (message) => {
      eventBus.publish({
        type: 'message_received',
        timestamp: Date.now(),
        sessionId: undefined,
        userId: message.userId,
        data: { channel: config.id, message },
      });
    });

    adapter.on('connected', () => {
      eventBus.publish({
        type: 'channel_connected',
        timestamp: Date.now(),
        data: { channel: config.id },
      });
    });

    adapter.on('disconnected', () => {
      eventBus.publish({
        type: 'channel_disconnected',
        timestamp: Date.now(),
        data: { channel: config.id },
      });
    });

    // Connect
    await adapter.connect();

    this.channels.set(config.id, adapter);
    console.log(`Channel ${config.id} (${config.type}) initialized`);

    return adapter;
  }

  /**
   * Load credentials for a channel
   */
  private loadCredentials(channelId: string): { type: 'none' | 'api_key' | 'oauth2' | 'webhook_secret' | 'bot_token'; config: Record<string, string> } | undefined {
    const credsPath = process.env[`CREDENTIALS_${channelId.toUpperCase()}_PATH`];
    if (!credsPath || !existsSync(credsPath)) {
      return undefined;
    }

    try {
      const content = readFileSync(credsPath, 'utf-8');
      const creds = JSON.parse(content);
      return {
        type: creds['type'] ?? 'api_key',
        config: creds['config'] ?? creds,
      };
    } catch {
      console.warn(`Failed to load credentials for ${channelId}`);
      return undefined;
    }
  }

  /**
   * Get a channel by ID
   */
  getChannel(id: string): ChannelAdapter | undefined {
    return this.channels.get(id);
  }

  /**
   * Get all channels
   */
  getAllChannels(): ChannelAdapter[] {
    return Array.from(this.channels.values());
  }

  /**
   * Remove a channel
   */
  async removeChannel(id: string): Promise<boolean> {
    const channel = this.channels.get(id);
    if (!channel) return false;

    await channel.disconnect();
    this.channels.delete(id);
    return true;
  }

  /**
   * Check health of all channels
   */
  async healthCheck(): Promise<Record<string, { status: string; latency?: number }>> {
    const results: Record<string, { status: string; latency?: number }> = {};

    for (const [id, channel] of this.channels) {
      try {
        results[id] = await channel.health();
      } catch (error) {
        results[id] = {
          status: 'down',
        };
      }
    }

    return results;
  }

  /**
   * Check if manager is healthy
   */
  isHealthy(): boolean {
    return this.channels.size > 0 && Array.from(this.channels.values()).some(c => c.isConnected());
  }

  /**
   * Shutdown all channels
   */
  async shutdown(): Promise<void> {
    const disconnectPromises = Array.from(this.channels.values()).map(c => c.disconnect());
    await Promise.allSettled(disconnectPromises);
    this.channels.clear();
    this.initialized = false;
  }

  /**
   * Reload configuration
   */
  async reload(): Promise<void> {
    await this.shutdown();
    await this.initialize();
  }
}