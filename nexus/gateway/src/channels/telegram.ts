/**
 * XenoSys Gateway - Telegram Channel Adapter
 * Telegram Bot API integration
 */

import { v4 as uuid } from 'uuid';
import { ChannelAdapter, ChannelOptions } from './base.js';
import { Message, MessageSchema } from '../gateway/types.js';

// ============================================================================
// Telegram Types
// ============================================================================

interface TelegramUpdate {
  update_id: number;
  message?: TelegramMessage;
  edited_message?: TelegramMessage;
  callback_query?: TelegramCallbackQuery;
}

interface TelegramMessage {
  message_id: number;
  from?: TelegramUser;
  chat: TelegramChat;
  text?: string;
  caption?: string;
  photo?: TelegramPhoto[];
  document?: TelegramDocument;
  voice?: TelegramVoice;
  entities?: TelegramEntity[];
  reply_to_message?: TelegramMessage;
}

interface TelegramUser {
  id: number;
  is_bot: boolean;
  first_name: string;
  last_name?: string;
  username?: string;
  language_code?: string;
}

interface TelegramChat {
  id: number;
  type: 'private' | 'group' | 'supergroup' | 'channel';
  title?: string;
  username?: string;
}

interface TelegramPhoto {
  file_id: string;
  width: number;
  height: number;
  file_size?: number;
}

interface TelegramDocument {
  file_id: string;
  file_name?: string;
  mime_type: string;
  file_size?: number;
}

interface TelegramVoice {
  file_id: string;
  duration: number;
  mime_type?: string;
  file_size?: number;
}

interface TelegramEntity {
  type: string;
  offset: number;
  length: number;
  url?: string;
  user?: TelegramUser;
}

interface TelegramCallbackQuery {
  id: string;
  from: TelegramUser;
  chat_instance: string;
  data?: string;
  message?: TelegramMessage;
}

interface TelegramResponse<T> {
  ok: boolean;
  result?: T;
  description?: string;
  error_code?: number;
}

// ============================================================================
// Telegram Adapter
// ============================================================================

export class TelegramAdapter extends ChannelAdapter {
  private botToken: string;
  private apiBase = 'https://api.telegram.org';
  private webhookSecret?: string;
  private longPollOffset = 0;
  private longPollTimeout = 55; // Telegram recommended timeout
  private stopping = false;

  constructor(options: ChannelOptions) {
    super(options);
    this.botToken = this.credentials?.config['bot_token'] ?? '';
    this.webhookSecret = this.credentials?.config['webhook_secret'];
  }

  /**
   * Connect to Telegram (start long polling)
   */
  async connect(): Promise<void> {
    if (this.connected) return;

    if (!this.botToken) {
      throw new Error('Telegram bot token not configured');
    }

    // Verify bot token
    await this.apiCall('getMe');

    // Start long polling
    this.startLongPolling();

    this.connected = true;
    this.emit('connected');
  }

  /**
   * Start long polling for updates
   */
  private async startLongPolling(): Promise<void> {
    while (!this.stopping) {
      try {
        const updates = await this.getUpdates();
        for (const update of updates) {
          await this.handleUpdate(update);
        }
      } catch (error) {
        console.error('Long polling error:', error);
        // Wait before retrying
        await this.sleep(5000);
      }
    }
  }

  /**
   * Get updates via long polling
   */
  private async getUpdates(): Promise<TelegramUpdate[]> {
    const response = await this.apiCall<TelegramResponse<TelegramUpdate[]>>('getUpdates', {
      offset: this.longPollOffset,
      timeout: this.longPollTimeout,
      allowed_updates: ['message', 'edited_message', 'callback_query'],
    });

    if (!response.ok || !response.result) {
      return [];
    }

    // Update offset to acknowledge processed updates
    if (response.result.length > 0) {
      const lastUpdate = response.result[response.result.length - 1];
      this.longPollOffset = lastUpdate.update_id + 1;
    }

    return response.result;
  }

  /**
   * Handle incoming Telegram update
   */
  private async handleUpdate(update: TelegramUpdate): Promise<void> {
    try {
      if (update.message) {
        await this.handleMessage(update.message);
      } else if (update.edited_message) {
        // Handle edited message if needed
      } else if (update.callback_query) {
        await this.handleCallbackQuery(update.callback_query);
      }
    } catch (error) {
      console.error('Error handling update:', error);
    }
  }

  /**
   * Handle incoming message
   */
  private async handleMessage(msg: TelegramMessage): Promise<void> {
    const userId = msg.from?.id.toString() ?? 'unknown';
    const chatId = msg.chat.id.toString();
    const content = msg.text ?? msg.caption ?? '';

    // Skip empty messages
    if (!content && !msg.photo?.length && !msg.document && !msg.voice) {
      return;
    }

    // Build attachments if any
    const attachments = [];
    if (msg.photo?.length) {
      // Use highest resolution photo
      const photo = msg.photo[msg.photo.length - 1];
      attachments.push({
        type: 'image' as const,
        url: await this.getFileUrl(photo.file_id),
        name: `photo_${photo.file_id}.jpg`,
        mimeType: 'image/jpeg',
      });
    }
    if (msg.document) {
      attachments.push({
        type: 'file' as const,
        url: await this.getFileUrl(msg.document.file_id),
        name: msg.document.file_name,
        mimeType: msg.document.mime_type,
      });
    }
    if (msg.voice) {
      attachments.push({
        type: 'audio' as const,
        url: await this.getFileUrl(msg.voice.file_id),
        mimeType: msg.voice.mime_type ?? 'audio/ogg',
      });
    }

    const message: Message = {
      id: uuid(),
      channel: this.id,
      userId,
      content,
      timestamp: Date.now(),
      attachments: attachments.length > 0 ? attachments : undefined,
      metadata: {
        chatId,
        messageId: msg.message_id,
        entities: msg.entities,
      },
    };

    await this.emitMessage(message);
  }

  /**
   * Handle callback query (inline button clicks)
   */
  private async handleCallbackQuery(query: TelegramCallbackQuery): Promise<void> {
    // Answer the callback query first
    await this.apiCall('answerCallbackQuery', {
      callback_query_id: query.id,
    });

    // Emit callback data as message
    if (query.data) {
      const message: Message = {
        id: uuid(),
        channel: this.id,
        userId: query.from.id.toString(),
        content: query.data,
        timestamp: Date.now(),
        metadata: {
          type: 'callback_query',
          callbackId: query.id,
          chatId: query.message?.chat.id.toString(),
        },
      };
      await this.emitMessage(message);
    }
  }

  /**
   * Send a message
   */
  async send(target: string, content: string, options?: Record<string, unknown>): Promise<void> {
    const chatId = target;
    const parseMode = (options?.parse_mode as string) ?? 'Markdown';
    const replyTo = options?.reply_to as number | undefined;

    const params: Record<string, unknown> = {
      chat_id: chatId,
      text: content,
      parse_mode: parseMode,
    };

    if (replyTo) {
      params['reply_to_message_id'] = replyTo;
    }

    if (options?.reply_markup) {
      params['reply_markup'] = options['reply_markup'];
    }

    const response = await this.apiCall('sendMessage', params);

    if (!response.ok) {
      throw new Error(`Telegram send failed: ${response.description}`);
    }

    await this.emitSent(chatId, content);
  }

  /**
   * Send a reply with inline keyboard
   */
  async sendWithKeyboard(target: string, content: string, keyboard: { text: string; data: string }[]): Promise<void> {
    const inlineKeyboard = keyboard.map(btn => [{
      text: btn.text,
      callback_data: btn.data,
    }]);

    await this.apiCall('sendMessage', {
      chat_id: target,
      text: content,
      reply_markup: {
        inline_keyboard: inlineKeyboard,
      },
    });
  }

  /**
   * Get file URL from Telegram
   */
  private async getFileUrl(fileId: string): Promise<string> {
    const response = await this.apiCall<{ ok: boolean; result: { file_path: string } }>('getFile', {
      file_id: fileId,
    });

    if (!response.ok || !response.result) {
      return '';
    }

    return `${this.apiBase}/file/bot${this.botToken}/${response.result.file_path}`;
  }

  /**
   * Check channel health
   */
  async health(): Promise<{ status: 'healthy' | 'degraded' | 'down'; latency?: number; error?: string }> {
    const start = Date.now();

    try {
      const response = await this.apiCall('getMe');
      const latency = Date.now() - start;

      if (!response.ok) {
        return { status: 'down', error: response.description };
      }

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
   * Disconnect from Telegram
   */
  async disconnect(): Promise<void> {
    this.stopping = true;
    this.connected = false;
    this.emit('disconnected');
  }

  /**
   * Make API call to Telegram
   */
  private async apiCall<T>(method: string, params?: Record<string, unknown>): Promise<T> {
    const url = `${this.apiBase}/bot${this.botToken}/${method}`;

    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: params ? JSON.stringify(params) : undefined,
    });

    return response.json() as Promise<T>;
  }

  /**
   * Sleep helper
   */
  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}