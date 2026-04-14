/**
 * XenoSys Gateway - Discord Channel Adapter
 * Discord API integration using WebSocket Gateway
 */

import { ChannelAdapter, ChannelOptions } from './base.js';
import { Message } from '../gateway/types.js';
import { v4 as uuid } from 'uuid';

// ============================================================================
// Discord Types
// ============================================================================

interface DiscordMessage {
  id: string;
  channel_id: string;
  guild_id?: string;
  author: DiscordUser;
  content: string;
  timestamp: string;
  edited_timestamp?: string;
  tts: boolean;
  mention_everyone: boolean;
  mentions: DiscordUser[];
  mention_roles: string[];
  attachments: DiscordAttachment[];
  embeds: DiscordEmbed[];
  reactions?: DiscordReaction[];
  type: number;
  nonce?: string;
  referenced_message?: DiscordMessage;
}

interface DiscordUser {
  id: string;
  username: string;
  bot?: boolean;
  discriminator: string;
  avatar?: string;
  roles?: string[];
}

interface DiscordAttachment {
  id: string;
  filename: string;
  size: number;
  url: string;
  proxy_url: string;
  content_type?: string;
  width?: number;
  height?: number;
}

interface DiscordEmbed {
  title?: string;
  type?: string;
  description?: string;
  url?: string;
  timestamp?: string;
  color?: number;
  footer?: {
    text: string;
    icon_url?: string;
    proxy_icon_url?: string;
  };
  image?: { url: string; proxy_url?: string; width?: number; height?: number };
  thumbnail?: { url: string; proxy_url?: string; width?: number; height?: number };
  video?: { url: string; proxy_url?: string; width?: number; height?: number };
  provider?: { name?: string; url?: string };
  author?: { name: string; url?: string; icon_url?: string; proxy_icon_url?: string };
  fields?: { name: string; value: string; inline?: boolean }[];
}

interface DiscordReaction {
  count: number;
  me: boolean;
  emoji: DiscordEmoji;
}

interface DiscordEmoji {
  id?: string;
  name: string;
  animated?: boolean;
}

interface DiscordInteraction {
  id: string;
  application_id: string;
  type: number;
  data?: {
    custom_id?: string;
    component_type?: number;
    values?: string[];
  };
  guild_id?: string;
  channel_id: string;
  member?: DiscordMember;
  user?: DiscordUser;
  token: string;
  version: number;
}

interface DiscordMember {
  user?: DiscordUser;
  nick?: string;
  roles: string[];
}

// Discord Gateway OpCodes
const DISCORD_GATEWAY_OPCODES = {
  DISPATCH: 0,
  HEARTBEAT: 1,
  IDENTIFY: 2,
  PRESENCE_UPDATE: 3,
  VOICE_STATE_UPDATE: 4,
  RESUME: 6,
  RECONNECT: 7,
  REQUEST_GUILD_MEMBERS: 8,
  INVALID_SESSION: 9,
  HELLO: 10,
  HEARTBEAT_ACK: 11,
};

// Discord Intent flags
const DISCORD_INTENTS = {
  GUILDS: 1 << 0,
  GUILD_MEMBERS: 1 << 1,
  GUILD_BANS: 1 << 2,
  GUILD_EMOJIS: 1 << 3,
  GUILD_INTEGRATIONS: 1 << 4,
  GUILD_WEBHOOKS: 1 << 5,
  GUILD_INVITES: 1 << 6,
  GUILD_VOICE_STATES: 1 << 7,
  GUILD_PRESENCES: 1 << 8,
  GUILD_MESSAGES: 1 << 9,
  GUILD_MESSAGE_REACTIONS: 1 << 10,
  GUILD_MESSAGE_TYPING: 1 << 11,
  DIRECT_MESSAGES: 1 << 12,
  DIRECT_MESSAGE_REACTIONS: 1 << 13,
  DIRECT_MESSAGE_TYPING: 1 << 14,
  MESSAGE_CONTENT: 1 << 15,
  GUILD_SCHEDULED_EVENTS: 1 << 16,
};

// ============================================================================
// Discord Adapter
// ============================================================================

export class DiscordAdapter extends ChannelAdapter {
  private botToken: string;
  private gatewayUrl = 'wss://gateway.discord.gg';
  private ws?: WebSocket;
  private sessionId?: string;
  private sequenceNumber?: number;
  private heartbeatInterval?: ReturnType<typeof setInterval>;
  private lastHeartbeatAck = true;
  private intents = DISCORD_INTENTS.GUILD_MESSAGES | DISCORD_INTENTS.DIRECT_MESSAGES | DISCORD_INTENTS.MESSAGE_CONTENT;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private stopping = false;

  constructor(options: ChannelOptions) {
    super(options);
    this.botToken = this.credentials?.config['bot_token'] ?? '';
  }

  /**
   * Connect to Discord Gateway
   */
  async connect(): Promise<void> {
    if (this.connected) return;

    if (!this.botToken) {
      throw new Error('Discord bot token not configured');
    }

    // Get gateway URL with intents
    const gatewayUrl = `${this.gatewayUrl}?v=10&encoding=json&intents=${this.intents}`;

    this.connectWebSocket(gatewayUrl);

    this.connected = true;
    this.emit('connected');
  }

  /**
   * Connect WebSocket to gateway
   */
  private connectWebSocket(url: string): void {
    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      console.log('Discord WebSocket connected');
      this.reconnectAttempts = 0;
    };

    this.ws.onmessage = async (event) => {
      try {
        const data = JSON.parse(event.data);
        await this.handleGatewayMessage(data);
      } catch (error) {
        console.error('Failed to parse gateway message:', error);
      }
    };

    this.ws.onerror = (error) => {
      console.error('Discord WebSocket error:', error);
    };

    this.ws.onclose = (event) => {
      console.log('Discord WebSocket closed:', event.code, event.reason);
      this.handleDisconnect();
    };
  }

  /**
   * Handle incoming gateway message
   */
  private async handleGatewayMessage(data: { op: number; d?: unknown; s?: number; t?: string }): Promise<void> {
    switch (data.op) {
      case DISCORD_GATEWAY_OPCODES.HELLO:
        await this.handleHello(data.d as { heartbeat_interval: number });
        break;

      case DISCORD_GATEWAY_OPCODES.HEARTBEAT:
        this.sendHeartbeat();
        break;

      case DISCORD_GATEWAY_OPCODES.HEARTBEAT_ACK:
        this.lastHeartbeatAck = true;
        break;

      case DISCORD_GATEWAY_OPCODES.DISPATCH:
        this.sequenceNumber = data.s;
        await this.handleDispatch(data.t!, data.d);
        break;

      case DISCORD_GATEWAY_OPCODES.RECONNECT:
        console.log('Discord requested reconnect');
        this.ws?.close();
        break;

      case DISCORD_GATEWAY_OPCODES.INVALID_SESSION:
        console.log('Invalid session, reconnecting');
        await this.sleep(3000);
        this.reconnect();
        break;
    }
  }

  /**
   * Handle HELLO opcode
   */
  private async handleHello(d: { heartbeat_interval: number }): Promise<void> {
    // Start heartbeat
    this.startHeartbeat(d.heartbeat_interval);

    // Identify
    await this.identify();
  }

  /**
   * Start heartbeat interval
   */
  private startHeartbeat(intervalMs: number): void {
    this.heartbeatInterval = setInterval(() => {
      if (!this.lastHeartbeatAck) {
        console.warn('Heartbeat ACK not received, reconnecting');
        this.reconnect();
        return;
      }
      this.lastHeartbeatAck = false;
      this.sendHeartbeat();
    }, intervalMs);
  }

  /**
   * Send heartbeat
   */
  private sendHeartbeat(): void {
    this.sendOpcode(DISCORD_GATEWAY_OPCODES.HEARTBEAT, this.sequenceNumber);
  }

  /**
   * Identify with bot token
   */
  private async identify(): Promise<void> {
    this.sendOpcode(DISCORD_GATEWAY_OPCODES.IDENTIFY, {
      token: this.botToken,
      intents: this.intents,
      properties: {
        os: 'linux',
        browser: 'xenosys-gateway',
        device: 'xenosys-gateway',
      },
      presence: {
        status: 'online',
        activities: [{
          name: 'XenoSys',
          type: 0,
        }],
      },
    });
  }

  /**
   * Reconnect to gateway
   */
  private reconnect(): void {
    if (this.stopping) return;

    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max reconnect attempts reached');
      this.disconnect();
      return;
    }

    this.reconnectAttempts++;
    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);

    console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);

    setTimeout(() => {
      const gatewayUrl = `${this.gatewayUrl}?v=10&encoding=json&intents=${this.intents}`;
      this.connectWebSocket(gatewayUrl);
    }, delay);
  }

  /**
   * Handle disconnect
   */
  private handleDisconnect(): void {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
    }

    if (!this.stopping) {
      this.reconnect();
    }
  }

  /**
   * Handle dispatch events
   */
  private async handleDispatch(type: string, data: unknown): Promise<void> {
    switch (type) {
      case 'READY':
        await this.handleReady(data as { session_id: string });
        break;
      case 'MESSAGE_CREATE':
        await this.handleMessageCreate(data as DiscordMessage);
        break;
      case 'INTERACTION_CREATE':
        await this.handleInteraction(data as DiscordInteraction);
        break;
    }
  }

  /**
   * Handle READY event
   */
  private async handleReady(data: { session_id: string }): Promise<void> {
    this.sessionId = data.session_id;
    console.log('Discord bot ready, session:', this.sessionId);
  }

  /**
   * Handle new message
   */
  private async handleMessageCreate(msg: DiscordMessage): Promise<void> {
    // Ignore bot messages
    if (msg.author.bot) return;

    const attachments = msg.attachments.map(a => ({
      type: 'file' as const,
      url: a.url,
      name: a.filename,
      mimeType: a.content_type,
    }));

    const message: Message = {
      id: msg.id,
      channel: this.id,
      userId: msg.author.id,
      content: msg.content,
      timestamp: new Date(msg.timestamp).getTime(),
      attachments: attachments.length > 0 ? attachments : undefined,
      metadata: {
        guildId: msg.guild_id,
        channelId: msg.channel_id,
        username: msg.author.username,
      },
    };

    await this.emitMessage(message);
  }

  /**
   * Handle interaction (slash commands, buttons)
   */
  private async handleInteraction(interaction: DiscordInteraction): Promise<void> {
    const userId = interaction.member?.user?.id ?? interaction.user?.id ?? 'unknown';
    const content = interaction.data?.custom_id ?? JSON.stringify(interaction.data);

    const message: Message = {
      id: uuid(),
      channel: this.id,
      userId,
      content,
      timestamp: Date.now(),
      metadata: {
        type: 'interaction',
        interactionType: interaction.type,
        interactionData: interaction.data,
        token: interaction.token,
        channelId: interaction.channel_id,
        guildId: interaction.guild_id,
      },
    };

    await this.emitMessage(message);
  }

  /**
   * Send a message
   */
  async send(target: string, content: string, options?: Record<string, unknown>): Promise<void> {
    const embed = options?.embed as DiscordEmbed | undefined;
    const replyTo = options?.reply_to as string | undefined;
    const components = options?.components as unknown[] | undefined;

    const payload: Record<string, unknown> = {
      content,
    };

    if (embed) {
      payload['embeds'] = [embed];
    }

    if (replyTo) {
      payload['message_reference'] = { message_id: replyTo };
    }

    if (components) {
      payload['components'] = components;
    }

    await this.apiCall(`/channels/${target}/messages`, payload);
    await this.emitSent(target, content);
  }

  /**
   * Reply to interaction
   */
  async replyToInteraction(token: string, content: string, ephemeral = false): Promise<void> {
    await this.apiCall(`/interactions/${token}/callback`, {
      type: 4, // ChannelMessageWithSource
      data: {
        content,
        flags: ephemeral ? 64 : 0, // Ephemeral flag
      },
    });
  }

  /**
   * Create follow-up message
   */
  async followUp(token: string, content: string): Promise<void> {
    await this.apiCall(`/webhooks/${this.config.settings?.application_id ?? ''}/${token}`, {
      content,
    });
  }

  /**
   * Check health
   */
  async health(): Promise<{ status: 'healthy' | 'degraded' | 'down'; latency?: number; error?: string }> {
    const start = Date.now();

    try {
      await this.apiCall('/users/@me');
      const latency = Date.now() - start;

      return {
        status: latency > 1000 ? 'degraded' : 'healthy',
        latency,
      };
    } catch (error) {
      return {
        status: 'down',
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  }

  /**
   * Disconnect
   */
  async disconnect(): Promise<void> {
    this.stopping = true;

    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
    }

    this.ws?.close(1000, 'Client disconnect');
    this.connected = false;
    this.emit('disconnected');
  }

  /**
   * Send opcode to gateway
   */
  private sendOpcode(opcode: number, data: unknown): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ op: opcode, d: data }));
    }
  }

  /**
   * Make REST API call
   */
  private async apiCall(endpoint: string, data?: Record<string, unknown>): Promise<unknown> {
    const url = `https://discord.com/api/v10${endpoint}`;
    const response = await fetch(url, {
      method: data ? 'POST' : 'GET',
      headers: {
        'Authorization': `Bot ${this.botToken}`,
        'Content-Type': 'application/json',
      },
      body: data ? JSON.stringify(data) : undefined,
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`Discord API error: ${response.status} ${error}`);
    }

    return response.json();
  }

  /**
   * Sleep helper
   */
  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}