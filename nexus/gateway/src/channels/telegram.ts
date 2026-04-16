import { v4 as uuid } from 'uuid';
import { ChannelAdapter, ChannelOptions } from './base.js';
import { Message } from '../gateway/types.js';

interface TelegramUpdate { update_id: number; message?: any; edited_message?: any; callback_query?: any; }

export class TelegramAdapter extends ChannelAdapter {
  private botToken: string;
  private apiBase = 'https://api.telegram.org'; 
  private longPollOffset = 0; 
  private stopping = false; 

  constructor(options: ChannelOptions) { 
    super(options); 
    this.botToken = this.credentials?.config?.['bot_token'] ?? ''; 
  } 

  async connect(): Promise<void> { 
    if (this.connected) return; 
    if (!this.botToken) throw new Error('Telegram bot token not configured'); 
    await this.apiCall('getMe'); 
    this.startLongPolling(); 
    this.connected = true; 
    this.emit('connected'); 
  } 

  private async startLongPolling(): Promise<void> { 
    while (!this.stopping) { 
      try { 
        const updates = await this.getUpdates(); 
        for (const update of updates) { 
          if (update?.message) await this.handleMessage(update.message); 
        } 
      } catch (error) { await new Promise(r => setTimeout(r, 5000)); } 
    } 
  } 

  private async getUpdates(): Promise<TelegramUpdate[]> { 
    const response: any = await this.apiCall('getUpdates', { offset: this.longPollOffset, timeout: 55 }); 
    if (!response?.ok || !response?.result) return []; 
    if (response.result.length > 0) { 
      this.longPollOffset = response.result[response.result.length - 1].update_id + 1; 
    } 
    return response.result; 
  } 

  private async handleMessage(msg: any): Promise<void> { 
    const userId = msg.from?.id?.toString() ?? 'unknown'; 
    const content = msg?.text ?? msg?.caption ?? ''; 
    if (!content) return; 

    const message: Message = { 
      id: uuid(), channel: this.id, userId, content, timestamp: Date.now(), 
      metadata: { chatId: msg?.chat?.id?.toString() }, 
    }; 
    await this.emitMessage(message); 
  } 

  async send(target: string, content: string): Promise<void> { 
    const response: any = await this.apiCall('sendMessage', { chat_id: target, text: content }); 
    if (!response?.ok) throw new Error("Telegram API error: " + response?.description); 
  } 

  async health(): Promise<{ status: 'healthy' | 'degraded' | 'down' }> { 
    try { 
      const response: any = await this.apiCall('getMe'); 
      return { status: response?.ok ? 'healthy' : 'down' }; 
    } catch { return { status: 'down' }; } 
  } 

  async disconnect(): Promise<void> { this.stopping = true; this.connected = false; } 

  private async apiCall<T>(method: string, params?: Record<string, unknown>): Promise<T> { 
    const url = this.apiBase + "/bot" + this.botToken + "/" + method; 
    const response = await fetch(url, { 
      method: 'POST', headers: { 'Content-Type': 'application/json' }, 
      body: params ? JSON.stringify(params) : undefined, 
    }); 
    return response.json() as Promise<T>; 
  }
}
