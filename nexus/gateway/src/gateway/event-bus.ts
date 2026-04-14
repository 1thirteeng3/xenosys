/**
 * XenoSys Gateway - Event Bus
 * Core event-driven communication system
 */

import { EventEmitter } from 'events';
import { v4 as uuid } from 'uuid';
import { GatewayEvent, GatewayEventSchema } from './types.js';

type EventHandler = (event: GatewayEvent) => Promise<void> | void;
type SubscriptionId = string;

interface Subscription {
  id: SubscriptionId;
  eventTypes: Set<GatewayEvent['type']> | '*';
  handler: EventHandler;
  filter?: (event: GatewayEvent) => boolean;
  once: boolean;
}

/**
 * Event Bus - Central pub/sub system for gateway events
 * Implements observer pattern with filtering and priority
 */
export class EventBus extends EventEmitter {
  private subscriptions: Map<SubscriptionId, Subscription> = new Map();
  private eventQueue: GatewayEvent[] = [];
  private processing = false;
  private readonly maxQueueSize = 10000;
  private readonly processBatchSize = 100;

  constructor() {
    super();
    this.setMaxListeners(1000);
  }

  /**
   * Subscribe to events
   */
  subscribe(
    eventTypes: GatewayEvent['type'][] | '*',
    handler: EventHandler,
    options?: { filter?: Subscription['filter']; once?: boolean }
  ): SubscriptionId {
    const id = uuid();
    const subscription: Subscription = {
      id,
      eventTypes: eventTypes === '*' ? '*' : new Set(eventTypes),
      handler,
      filter: options?.filter,
      once: options?.once ?? false,
    };

    this.subscriptions.set(id, subscription);
    return id;
  }

  /**
   * Subscribe once - handler removed after first event
   */
  subscribeOnce(
    eventTypes: GatewayEvent['type'][] | '*',
    handler: EventHandler,
    filter?: (event: GatewayEvent) => boolean
  ): SubscriptionId {
    return this.subscribe(eventTypes, handler, { filter, once: true });
  }

  /**
   * Unsubscribe by ID
   */
  unsubscribe(id: SubscriptionId): boolean {
    return this.subscriptions.delete(id);
  }

  /**
   * Unsubscribe all handlers for specific event types
   */
  unsubscribeAll(eventTypes?: GatewayEvent['type'][]): number {
    if (!eventTypes) {
      const count = this.subscriptions.size;
      this.subscriptions.clear();
      return count;
    }

    let count = 0;
    const typesSet = new Set(eventTypes);
    for (const [id, sub] of this.subscriptions) {
      if (sub.eventTypes === '*' || [...typesSet].some(t => sub.eventTypes.has(t))) {
        this.subscriptions.delete(id);
        count++;
      }
    }
    return count;
  }

  /**
   * Publish an event
   */
  async publish(event: GatewayEvent): Promise<void> {
    // Validate event schema
    const parsed = GatewayEventSchema.safeParse(event);
    if (!parsed.success) {
      console.error('Invalid event:', parsed.error);
      return;
    }

    const validEvent = parsed.data;

    // Add to queue if processing
    if (this.processing) {
      if (this.eventQueue.length < this.maxQueueSize) {
        this.eventQueue.push(validEvent);
      } else {
        console.warn('Event queue full, dropping event:', validEvent.type);
      }
      return;
    }

    await this.processEvent(validEvent);
  }

  /**
   * Process a single event
   */
  private async processEvent(event: GatewayEvent): Promise<void> {
    const handlers: Array<{ handler: EventHandler; once: boolean }> = [];

    for (const sub of this.subscriptions.values()) {
      // Check if subscription matches event type
      const matches =
        sub.eventTypes === '*' || sub.eventTypes.has(event.type);

      if (!matches) continue;

      // Check custom filter
      if (sub.filter && !sub.filter(event)) continue;

      handlers.push({ handler: sub.handler, once: sub.once });
    }

    // Remove 'once' subscriptions
    for (const { handler: _handler, once } of handlers) {
      if (once) {
        for (const [id, sub] of this.subscriptions) {
          if (sub.once && sub.handler === _handler) {
            this.subscriptions.delete(id);
            break;
          }
        }
      }
    }

    // Execute handlers (don't await to not block)
    for (const { handler } of handlers) {
      try {
        const result = handler(event);
        if (result instanceof Promise) {
          result.catch(err => console.error('Event handler error:', err));
        }
      } catch (err) {
        console.error('Event handler threw:', err);
      }
    }

    // Process queued events
    this.scheduleQueueProcessing();
  }

  /**
   * Schedule queue processing
   */
  private scheduleQueueProcessing(): void {
    if (this.processing || this.eventQueue.length === 0) return;

    setImmediate(() => this.processQueue());
  }

  /**
   * Process queued events in batches
   */
  private async processQueue(): Promise<void> {
    if (this.eventQueue.length === 0) return;

    this.processing = true;

    while (this.eventQueue.length > 0) {
      const batch = this.eventQueue.splice(0, this.processBatchSize);

      for (const event of batch) {
        await this.processEvent(event);
      }

      // Yield to event loop between batches
      await new Promise(resolve => setImmediate(resolve));
    }

    this.processing = false;
  }

  /**
   * Get subscription count
   */
  getSubscriptionCount(): number {
    return this.subscriptions.size;
  }

  /**
   * Get event type counts
   */
  getEventCounts(): Record<string, number> {
    const counts: Record<string, number> = {};
    for (const sub of this.subscriptions.values()) {
      if (sub.eventTypes === '*') {
        counts['*'] = (counts['*'] ?? 0) + 1;
      } else {
        for (const type of sub.eventTypes) {
          counts[type] = (counts[type] ?? 0) + 1;
        }
      }
    }
    return counts;
  }
}

// Singleton instance
export const eventBus = new EventBus();