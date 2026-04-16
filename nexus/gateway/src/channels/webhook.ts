import { ChannelAdapter, ChannelOptions } from './base.js';
import { Message } from '../gateway/types.js';
import { v4 as uuid } from 'uuid';

export class WebhookAdapter extends ChannelAdapter { 
  private secret?: string; 

  constructor(options: ChannelOptions) { 
    super(options); 
    this.secret = this.credentials?.config?.['webhook_secret']; 
  } 

  async connect(): Promise<void> { this.connected = true; this.emit('connected'); } 

  async handleWebhook(payload: any, headers: Record<string, string>): Promise<void> { 
    const content = payload?.text ?? payload?.message ?? payload?.content ?? ''; 
    if (!content) return; 

    const message: Message = { 
      id: uuid(), channel: this.id, 
      userId: payload?.user_id ?? payload?.userId ?? 'webhook', 
      content, timestamp: Date.now(), metadata: { rawPayload: payload }, 
    }; 
    await this.emitMessage(message); 
  } 

  async send(): Promise<void> { throw new Error('Webhook does not support sending'); } 
  async health(): Promise<{ status: 'healthy' | 'down' }> { return { status: this.connected ? 'healthy' : 'down' }; } 
  async disconnect(): Promise<void> { this.connected = false; } 
}
