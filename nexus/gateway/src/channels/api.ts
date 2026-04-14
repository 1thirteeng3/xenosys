/**
 * XenoSys Gateway - API Channel Adapter
 * REST API inbound integration
 */

import { ChannelAdapter, ChannelOptions } from './base.js';
import { Message } from '../gateway/types.js';
import { v4 as uuid } from 'uuid';

// ============================================================================
// API Adapter
// ============================================================================

interface APIRequest {
  user_id?: string;
  userId?: string;
  message?: string;
  content?: string;
  text?: string;
  attachments?: Array<{
    type: string;
    url: string;
    name?: string;
    data?: string; // base64
  }>;
  metadata?: Record<string, unknown>;
}

export class APIAdapter extends ChannelAdapter {
  private apiKey?: string;
  private trustedIps: string[] = [];

  constructor(options: ChannelOptions) {
    super(options);
    this.apiKey = this.credentials?.config['api_key'];
    this.trustedIps = this.credentials?.config['trusted_ips']?.split(',') ?? [];
  }

  /**
   * Connect (API is passive)
   */
  async connect(): Promise<void> {
    this.connected = true;
    this.emit('connected');
  }

  /**
   * Handle incoming API request
   */
  async handleRequest(
    request: APIRequest,
    headers: Record<string, string>,
    ip?: string
  ): Promise<void> {
    // Validate API key if configured
    if (this.apiKey) {
      const providedKey = headers['x-api-key'] ?? headers['authorization']?.replace('Bearer ', '');
      if (providedKey !== this.apiKey) {
        throw new Error('Invalid API key');
      }
    }

    // Validate IP if trusted IPs configured
    if (this.trustedIps.length > 0 && ip && !this.trustedIps.includes(ip)) {
      throw new Error('IP not trusted');
    }

    const content = request.message ?? request.content ?? request.text ?? '';

    if (!content && !request.attachments?.length) {
      throw new Error('Empty request');
    }

    const attachments = request.attachments?.map(a => ({
      type: (a.type as 'image' | 'file' | 'audio' | 'video') ?? 'file',
      url: a.url,
      name: a.name,
    })) ?? [];

    const message: Message = {
      id: uuid(),
      channel: this.id,
      userId: request.user_id ?? request.userId ?? 'api',
      content,
      timestamp: Date.now(),
      attachments: attachments.length > 0 ? attachments : undefined,
      metadata: {
        rawRequest: request,
        headers,
        ip,
      },
    };

    await this.emitMessage(message);
  }

  /**
   * Send response (not typical for inbound API)
   */
  async send(target: string, content: string, options?: Record<string, unknown>): Promise<void> {
    // API adapter is primarily for inbound
    // This would be used for acknowledgment responses
    console.log(`API send to ${target}: ${content}`);
  }

  /**
   * Check health
   */
  async health(): Promise<{ status: 'healthy' | 'degraded' | 'down'; latency?: number; error?: string }> {
    return {
      status: this.connected ? 'healthy' : 'down',
    };
  }

  /**
   * Disconnect
   */
  async disconnect(): Promise<void> {
    this.connected = false;
    this.emit('disconnected');
  }

  /**
   * Get API endpoint path
   */
  getAPIPath(): string {
    return `/api/inbound/${this.id}`;
  }
}