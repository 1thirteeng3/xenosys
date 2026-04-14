/**
 * XenoSys Gateway - Slack Channel Adapter
 * Slack API integration with Bolt framework
 */

import { ChannelAdapter, ChannelOptions } from './base.js';
import { Message } from '../gateway/types.js';
import { v4 as uuid } from 'uuid';

// ============================================================================
// Slack Types
// ============================================================================

interface SlackMessage {
  type: string;
  channel: string;
  user: string;
  text: string;
  ts: string;
  thread_ts?: string;
  files?: SlackFile[];
  attachments?: SlackAttachment[];
  edited?: { user: string; ts: string };
}

interface SlackFile {
  id: string;
  name: string;
  mimetype: string;
  url_private: string;
  url_private_download: string;
  size: number;
}

interface SlackAttachment {
  fallback?: string;
  color?: string;
  pretext?: string;
  author_name?: string;
  title?: string;
  title_link?: string;
  text?: string;
  fields?: { title: string; value: string; short?: boolean }[];
  image_url?: string;
  thumb_url?: string;
}

interface SlackEventCallback {
  type: 'event_callback';
  token: string;
  team_id: string;
  api_app_id: string;
  event: {
    type: string;
    channel?: string;
    user?: string;
    text?: string;
    ts?: string;
    thread_ts?: string;
    files?: SlackFile[];
    channel_type?: string;
  };
  authed_users: string[];
}

interface SlackInteractionPayload {
  type: string;
  user: { id: string; name: string };
  channel: { id: string; name: string };
  team: { id: string; domain: string };
  actions?: { action_id: string; value: string; type: string }[];
  message?: SlackMessage;
}

// ============================================================================
// Slack Adapter
// ============================================================================

export class SlackAdapter extends ChannelAdapter {
  private botToken: string;
  private signingSecret: string;
  private appToken?: string;
  private webhookPath: string;

  constructor(options: ChannelOptions) {
    super(options);
    this.botToken = this.credentials?.config['bot_token'] ?? '';
    this.signingSecret = this.credentials?.config['signing_secret'] ?? '';
    this.appToken = this.credentials?.config['app_token'];
    this.webhookPath = `/slack/events/${this.id}`;
  }

  /**
   * Connect to Slack
   */
  async connect(): Promise<void> {
    if (this.connected) return;

    if (!this.botToken || !this.signingSecret) {
      throw new Error('Slack bot token and signing secret required');
    }

    // Verify bot token
    await this.apiCall('/auth/test');

    this.connected = true;
    this.emit('connected');
  }

  /**
   * Handle incoming Slack event (webhook)
   */
  async handleWebhook(payload: unknown): Promise<void> {
    const data = payload as { type?: string; challenge?: string; event?: unknown };

    // URL verification challenge
    if (data['type'] === 'url_verification') {
      return;
    }

    // Event callback
    if (data['type'] === 'event_callback') {
      const eventData = data as SlackEventCallback;
      await this.handleEventCallback(eventData.event);
    }

    // Block Kit interactive payload
    if (data['type'] === 'block_actions' || data['type'] === 'interactive_message') {
      const interaction = data as SlackInteractionPayload;
      await this.handleInteraction(interaction);
    }
  }

  /**
   * Handle event callback
   */
  private async handleEventCallback(event: SlackEventCallback['event']): Promise<void> {
    if (event['type'] === 'message' && !event['thread_ts']) {
      const msg = event as unknown as SlackMessage;

      // Skip bot messages and events from us
      if (!msg.user || !msg.text) return;

      const attachments = msg.files?.map(f => ({
        type: 'file' as const,
        url: f.url_private,
        name: f.name,
        mimeType: f.mimetype,
      })) ?? [];

      const message: Message = {
        id: uuid(),
        channel: this.id,
        userId: msg.user,
        content: msg.text,
        timestamp: parseFloat(msg.ts) * 1000,
        attachments: attachments.length > 0 ? attachments : undefined,
        metadata: {
          channelId: msg.channel,
          threadTs: msg.thread_ts,
        },
      };

      await this.emitMessage(message);
    }
  }

  /**
   * Handle interactive payload
   */
  private async handleInteraction(payload: SlackInteractionPayload): Promise<void> {
    const action = payload.actions?.[0];
    if (!action) return;

    const message: Message = {
      id: uuid(),
      channel: this.id,
      userId: payload.user.id,
      content: action.value || action.action_id,
      timestamp: Date.now(),
      metadata: {
        type: 'interaction',
        actionType: action.type,
        channelId: payload.channel.id,
        teamId: payload.team.id,
      },
    };

    await this.emitMessage(message);
  }

  /**
   * Send a message
   */
  async send(target: string, content: string, options?: Record<string, unknown>): Promise<void> {
    const threadTs = options?.thread_ts as string | undefined;
    const blocks = options?.blocks as unknown[] | undefined;
    const attachments = options?.attachments as unknown[] | undefined;

    const payload: Record<string, unknown> = {
      channel: target,
      text: content,
    };

    if (threadTs) {
      payload['thread_ts'] = threadTs;
    }

    if (blocks) {
      payload['blocks'] = blocks;
    }

    if (attachments) {
      payload['attachments'] = attachments;
    }

    await this.apiCall('/chat.postMessage', payload);
    await this.emitSent(target, content);
  }

  /**
   * Reply in thread
   */
  async replyInThread(target: string, threadTs: string, content: string, blocks?: unknown[]): Promise<void> {
    await this.send(target, content, { thread_ts: threadTs, blocks });
  }

  /**
   * Update a message
   */
  async updateMessage(channel: string, ts: string, content: string): Promise<void> {
    await this.apiCall('/chat.update', {
      channel,
      ts,
      text: content,
    });
  }

  /**
   * Check health
   */
  async health(): Promise<{ status: 'healthy' | 'degraded' | 'down'; latency?: number; error?: string }> {
    const start = Date.now();

    try {
      const result = await this.apiCall('/auth.test');
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
    this.connected = false;
    this.emit('disconnected');
  }

  /**
   * Make API call
   */
  private async apiCall(endpoint: string, data?: Record<string, unknown>): Promise<unknown> {
    const url = `https://slack.com/api${endpoint}`;
    const response = await fetch(url, {
      method: data ? 'POST' : 'GET',
      headers: {
        'Authorization': `Bearer ${this.botToken}`,
        'Content-Type': 'application/json',
      },
      body: data ? JSON.stringify(data) : undefined,
    });

    const result = await response.json() as { ok: boolean; error?: string };

    if (!result.ok) {
      throw new Error(`Slack API error: ${result.error}`);
    }

    return result;
  }
}