/**
 * XenoSys Gateway - Webhook Channel Adapter
 * Generic webhook inbound integration
 */

import { ChannelAdapter, ChannelOptions } from './base.js';
import { Message } from '../gateway/types.js';
import { v4 as uuid } from 'uuid';

// ============================================================================
// Webhook Adapter
// ============================================================================

interface WebhookPayload {
  text?: string;
  message?: string;
  content?: string;
  user_id?: string;
  userId?: string;
  user?: string;
  from?: string;
  sender?: string;
  attachments?: Array<{
    url: string;
    name?: string;
    type?: string;
  }>;
  metadata?: Record<string, unknown>;
}

export class WebhookAdapter extends ChannelAdapter {
  private secret?: string;
  private signatureHeader = 'x-webhook-signature';
  private acceptAnyToken = false;

  constructor(options: ChannelOptions) {
    super(options);
    this.secret = this.credentials?.config['webhook_secret'];
    this.acceptAnyToken = this.credentials?.config['accept_any_token'] === 'true';
  }

  /**
   * Connect (webhook is passive, just validate config)
   */
  async connect(): Promise<void> {
    // Webhook doesn't need active connection
    // Just validate that we have required config

    if (!this.acceptAnyToken && !this.secret) {
      console.warn(`Webhook ${this.id}: No secret configured, accepting any token`);
    }

    this.connected = true;
    this.emit('connected');
  }

  /**
   * Handle incoming webhook
   */
  async handleWebhook(
    payload: WebhookPayload,
    headers: Record<string, string>
  ): Promise<void> {
    // Validate signature if configured
    if (!this.acceptAnyToken && this.secret) {
      const signature = headers[this.signatureHeader] ?? headers['x-hub-signature-256'];
      if (!signature) {
        throw new Error('Missing webhook signature');
      }

      if (!this.validateSignature(payload, signature)) {
        throw new Error('Invalid webhook signature');
      }
    }

    // Extract content from various formats
    const content = payload.text ?? payload.message ?? payload.content ?? '';

    if (!content) {
      console.warn(`Webhook ${this.id}: Empty payload received`);
      return;
    }

    const message: Message = {
      id: uuid(),
      channel: this.id,
      userId: payload.user_id ?? payload.userId ?? payload.user ?? payload.from ?? payload.sender ?? 'webhook',
      content,
      timestamp: Date.now(),
      metadata: {
        rawPayload: payload,
        headers,
        attachments: payload.attachments,
      },
    };

    await this.emitMessage(message);
  }

  /**
   * Validate HMAC signature
   */
  private validateSignature(payload: WebhookPayload, signature: string): boolean {
    if (!this.secret) return false;

    // HMAC-SHA256 signature
    const encoder = new TextEncoder();
    const key = encoder.encode(this.secret);
    const data = encoder.encode(JSON.stringify(payload));

    // Simple comparison - in production use crypto.subtle
    const expectedSig = `sha256=${this.computeHMAC(data, key)}`;
    return signature === expectedSig;
  }

  /**
   * Compute HMAC-SHA256
   */
  private computeHMAC(data: Uint8Array, key: Uint8Array): string {
    // Basic implementation - use crypto module in production
    let hash = 0;
    const combined = new Uint8Array(data.length + key.length);
    combined.set(key);
    combined.set(data, key.length);

    for (let i = 0; i < combined.length; i++) {
      hash = ((hash << 5) - hash + combined[i]) | 0;
    }

    return Math.abs(hash).toString(16).padStart(8, '0');
  }

  /**
   * Send is not supported for webhooks
   */
  async send(target: string, content: string, options?: Record<string, unknown>): Promise<void> {
    throw new Error('Webhook channel does not support sending');
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
   * Get webhook endpoint path
   */
  getWebhookPath(): string {
    return `/webhook/${this.id}`;
  }
}