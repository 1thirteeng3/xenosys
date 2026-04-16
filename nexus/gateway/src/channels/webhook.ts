import { ChannelAdapter, type ChannelOptions } from './base.js';
import { type Message } from '../gateway/types.js';
import { v4 as uuid } from 'uuid';

interface WebhookPayload {
  text?: string;
  message?: string;
  content?: string;
  user_id?: string;
  userId?: string;
  [key: string]: unknown;
}

export class WebhookAdapter extends ChannelAdapter {
  private secret?: string;

  constructor(options: ChannelOptions) {
    super(options);
    this.secret = this.credentials?.config?.['webhook_secret'];
  }

  async connect(): Promise<void> {
    this.connected = true;
    this.emit('connected');
  }

  async handleWebhook(payload: WebhookPayload, headers: Record<string, string>): Promise<void> {
    const content = payload?.text ?? payload?.message ?? payload?.content ?? '';
    if (!content) return;

    const message: Message = {
      id: uuid(),
      channel: this.id,
      userId: payload?.user_id ?? payload?.userId ?? 'webhook',
      content,
      timestamp: Date.now(),
      metadata: { rawPayload: payload },
    };
    await this.emitMessage(message);
  }

  async send(): Promise<void> {
    throw new Error('Webhook does not support sending');
  }

  async health(): Promise<{ status: 'healthy' | 'down' }> {
    return { status: this.connected ? 'healthy' : 'down' };
  }

  async disconnect(): Promise<void> {
    this.connected = false;
  }
}
