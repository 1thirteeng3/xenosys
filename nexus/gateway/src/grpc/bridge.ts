/**
 * XenoSys Gateway - gRPC Bridge
 * TypeScript ↔ Python interop via gRPC
 */

import * as grpc from '@grpc/grpc-js';
import * as protoLoader from '@grpc/proto-loader';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { AgentRequest, AgentResponse } from '../gateway/types.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// ============================================================================
// gRPC Service Definition
// ============================================================================

interface NexusService {
  ExecuteAgent(
    call: grpc.ServerUnaryCall<AgentRequest, AgentResponse>,
    callback: (error: grpc.ServiceError | null, response?: AgentResponse) => void
  ): void;

  StreamAgent(
    call: grpc.ServerWritableStream<AgentRequest, AgentResponse>
  ): void;

  GetStatus(
    call: grpc.ServerUnaryCall<{ node_id: string }, { status: string; version: string }>,
    callback: (error: grpc.ServiceError | null, response?: { status: string; version: string }) => void
  ): void;
}

interface HealthCheckResult {
  healthy: boolean;
  latencyMs?: number;
}

// ============================================================================
// gRPC Bridge
// ============================================================================

export class GRPCBridge {
  private static instance: GRPCBridge;
  private client: grpc.Client | null = null;
  private server: grpc.Server | null = null;
  private connected = false;
  private endpoint = '';

  private constructor() {}

  static getInstance(): GRPCBridge {
    if (!GRPCBridge.instance) {
      GRPCBridge.instance = new GRPCBridge();
    }
    return GRPCBridge.instance;
  }

  /**
   * Connect as client to Python runtime
   */
  async connect(endpoint: string): Promise<void> {
    if (this.client) {
      throw new Error('Already connected');
    }

    this.endpoint = endpoint;

    // Load proto file
    const packageDefinition = protoLoader.loadSync(
      resolve(__dirname, '../../proto/nexus.proto'),
      {
        keepCase: false,
        longs: String,
        enums: String,
        defaults: true,
        oneofs: true,
      }
    );

    const protoDescriptor = grpc.loadPackageDefinition(packageDefinition);
    const nexusProto = (protoDescriptor as any)['nexus'] ?? (protoDescriptor as any)['xenosys'];

    this.client = new nexusProto.Runtime(
      endpoint,
      grpc.credentials.createInsecure()
    );

    // Wait for connection
    await this.waitForConnection();
    this.connected = true;
  }

  /**
   * Start as server (Python runtime connects to us)
   */
  async startServer(port: number): Promise<void> {
    if (this.server) {
      throw new Error('Server already running');
    }

    // Load proto file
    const packageDefinition = protoLoader.loadSync(
      resolve(__dirname, '../../proto/nexus.proto'),
      {
        keepCase: false,
        longs: String,
        enums: String,
        defaults: true,
        oneofs: true,
      }
    );

    const protoDescriptor = grpc.loadPackageDefinition(packageDefinition);
    const nexusProto = (protoDescriptor as any)['nexus'] ?? (protoDescriptor as any)['xenosys'];

    this.server = new grpc.Server();

    this.server.addService(nexusProto.Runtime.service, {
      ExecuteAgent: this.handleExecuteAgent.bind(this),
      StreamAgent: this.handleStreamAgent.bind(this),
      GetStatus: this.handleGetStatus.bind(this),
    });

    await new Promise<void>((resolve, reject) => {
      this.server!.bindAsync(
        `0.0.0.0:${port}`,
        grpc.ServerCredentials.createInsecure(),
        (error, port) => {
          if (error) {
            reject(error);
          } else {
            console.log(`gRPC server listening on port ${port}`);
            resolve();
          }
        }
      );
    });
  }

  /**
   * Execute agent via gRPC
   */
  async executeAgent(request: AgentRequest): Promise<AgentResponse> {
    if (!this.client) {
      throw new Error('Not connected to Python runtime');
    }

    return new Promise((resolve, reject) => {
      this.client!.makeUnaryRequest(
        'ExecuteAgent',
        this.toProtoRequest,
        this.fromProtoResponse,
        request,
        (error: grpc.ServiceError | null, response?: AgentResponse) => {
          if (error) {
            reject(error);
          } else {
            resolve(response!);
          }
        }
      );
    });
  }

  /**
   * Stream agent execution
   */
  async *streamAgent(request: AgentRequest): AsyncGenerator<AgentResponse> {
    if (!this.client) {
      throw new Error('Not connected to Python runtime');
    }

    const call = this.client.makeServerStreamingRequest(
      'StreamAgent',
      this.toProtoRequest,
      this.fromProtoResponse,
      request
    );

    yield* call;
  }

  /**
   * Check health
   */
  async isHealthy(): Promise<boolean> {
    if (!this.client) return false;

    const start = Date.now();

    try {
      return new Promise((resolve) => {
        this.client!.makeUnaryRequest(
          'GetStatus',
          (req: unknown) => req,
          (res: unknown) => res,
          {},
          (error: grpc.ServiceError | null, response?: { status: string }) => {
            if (error || !response) {
              resolve(false);
            } else {
              resolve(response.status === 'healthy');
            }
          }
        );
      });
    } catch {
      return false;
    }
  }

  /**
   * Disconnect
   */
  async disconnect(): Promise<void> {
    if (this.client) {
      this.client.close();
      this.client = null;
    }

    if (this.server) {
      this.server.tryShutdown();
      this.server = null;
    }

    this.connected = false;
  }

  // ========================================================================
  // Server Handlers
  // ========================================================================

  private handleExecuteAgent(
    call: grpc.ServerUnaryCall<AgentRequest, AgentResponse>,
    callback: (error: grpc.ServiceError | null, response?: AgentResponse) => void
  ): void {
    const request = this.fromProtoRequest(call.request);

    // Forward to Python runtime (or handle locally)
    this.executeInRuntime(request)
      .then((response) => {
        callback(null, this.toProtoResponse(response));
      })
      .catch((error) => {
        callback({
          name: 'ExecuteError',
          message: error instanceof Error ? error.message : 'Unknown error',
          code: grpc.status.INTERNAL,
        });
      });
  }

  private handleStreamAgent(call: grpc.ServerWritableStream<AgentRequest, AgentResponse>): void {
    const request = this.fromProtoRequest(call.request);

    this.streamInRuntime(request)
      .then(async function* (responses) {
        for await (const response of responses) {
          call.write(this.toProtoResponse(response));
        }
        call.end();
      }.bind(this))
      .catch((error) => {
        call.emit('error', {
          name: 'StreamError',
          message: error instanceof Error ? error.message : 'Unknown error',
          code: grpc.status.INTERNAL,
        });
      });
  }

  private handleGetStatus(
    call: grpc.ServerUnaryCall<{ node_id: string }, { status: string; version: string }>,
    callback: (error: grpc.ServiceError | null, response?: { status: string; version: string }) => void
  ): void {
    callback(null, {
      status: 'healthy',
      version: '1.0.0',
    });
  }

  // ========================================================================
  // Runtime Integration
  // ========================================================================

  /**
   * Execute agent in Python runtime (placeholder for actual integration)
   */
  private async executeInRuntime(request: AgentRequest): Promise<AgentResponse> {
    // In production, this would forward to Python runtime
    // For now, return a mock response
    return {
      sessionId: request.sessionId,
      messageId: `msg-${Date.now()}`,
      content: 'Agent execution delegated via gRPC bridge',
      done: true,
      metadata: {
        model: 'gpt-4',
        tokensIn: 100,
        tokensOut: 50,
        costUsd: 0.001,
        latencyMs: 100,
        iterations: 1,
      },
    };
  }

  /**
   * Stream agent execution from Python runtime
   */
  private async *streamInRuntime(request: AgentRequest): AsyncGenerator<AgentResponse> {
    // In production, yield from Python runtime stream
    yield {
      sessionId: request.sessionId,
      messageId: `msg-${Date.now()}`,
      content: 'Streaming...',
      done: false,
    };

    yield {
      sessionId: request.sessionId,
      messageId: `msg-${Date.now()}`,
      content: 'Done',
      done: true,
    };
  }

  // ========================================================================
  // Serialization Helpers
  // ========================================================================

  private toProtoRequest(request: AgentRequest): unknown {
    return {
      session_id: request.sessionId,
      user_id: request.userId,
      channel: request.channel,
      message: request.message,
      attachments: request.attachments ?? [],
      context: request.context ? {
        agent_id: request.context.agentId ?? '',
        entity_id: request.context.entityId ?? '',
        memory_filters: JSON.stringify(request.context.memoryFilters ?? {}),
        system_prompt: request.context.systemPrompt ?? '',
      } : undefined,
      options: request.options ? {
        max_iterations: request.options.maxIterations ?? 0,
        timeout_ms: request.options.timeoutMs ?? 0,
        temperature: request.options.temperature ?? 0,
        model: request.options.model ?? '',
      } : undefined,
    };
  }

  private fromProtoRequest(proto: unknown): AgentRequest {
    const p = proto as Record<string, unknown>;
    return {
      sessionId: (p['session_id'] as string) ?? '',
      userId: (p['user_id'] as string) ?? '',
      channel: (p['channel'] as string) ?? '',
      message: (p['message'] as string) ?? '',
      attachments: (p['attachments'] as string[] | undefined) ?? [],
      context: p['context'] ? {
        agentId: (p['context'] as Record<string, unknown>)['agent_id'] as string | undefined,
        entityId: (p['context'] as Record<string, unknown>)['entity_id'] as string | undefined,
        memoryFilters: JSON.parse(((p['context'] as Record<string, unknown>)['memory_filters'] as string) ?? '{}'),
        systemPrompt: (p['context'] as Record<string, unknown>)['system_prompt'] as string | undefined,
      } : undefined,
      options: p['options'] ? {
        maxIterations: (p['options'] as Record<string, unknown>)['max_iterations'] as number | undefined,
        timeoutMs: (p['options'] as Record<string, unknown>)['timeout_ms'] as number | undefined,
        temperature: (p['options'] as Record<string, unknown>)['temperature'] as number | undefined,
        model: (p['options'] as Record<string, unknown>)['model'] as string | undefined,
      } : undefined,
    };
  }

  private toProtoResponse(response: AgentResponse): unknown {
    return {
      session_id: response.sessionId,
      message_id: response.messageId,
      content: response.content,
      done: response.done,
      metadata: response.metadata ? {
        model: response.metadata.model,
        tokens_in: response.metadata.tokensIn,
        tokens_out: response.metadata.tokensOut,
        cost_usd: response.metadata.costUsd,
        latency_ms: response.metadata.latencyMs,
        iterations: response.metadata.iterations,
      } : undefined,
      tool_calls: response.toolCalls?.map(tc => ({
        name: tc.name,
        args: JSON.stringify(tc.args),
        result: tc.result ?? '',
        error: tc.error ?? '',
      })),
      error: response.error ?? '',
    };
  }

  private fromProtoResponse(proto: unknown): AgentResponse {
    const p = proto as Record<string, unknown>;
    return {
      sessionId: (p['session_id'] as string) ?? '',
      messageId: (p['message_id'] as string) ?? '',
      content: (p['content'] as string) ?? '',
      done: (p['done'] as boolean) ?? false,
      metadata: p['metadata'] ? {
        model: (p['metadata'] as Record<string, unknown>)['model'] as string,
        tokensIn: (p['metadata'] as Record<string, unknown>)['tokens_in'] as number,
        tokensOut: (p['metadata'] as Record<string, unknown>)['tokens_out'] as number,
        costUsd: (p['metadata'] as Record<string, unknown>)['cost_usd'] as number,
        latencyMs: (p['metadata'] as Record<string, unknown>)['latency_ms'] as number,
        iterations: (p['metadata'] as Record<string, unknown>)['iterations'] as number,
      } : undefined,
      toolCalls: (p['tool_calls'] as Array<Record<string, unknown>> | undefined)?.map(tc => ({
        name: tc['name'] as string,
        args: JSON.parse(tc['args'] as string),
        result: tc['result'] as string | undefined,
        error: tc['error'] as string | undefined,
      })),
      error: (p['error'] as string) ?? undefined,
    };
  }

  private waitForConnection(): Promise<void> {
    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(new Error('Connection timeout'));
      }, 10000);

      this.client!.waitForReady(Date.now() + 10000, (error) => {
        clearTimeout(timeout);
        if (error) {
          reject(error);
        } else {
          resolve();
        }
      });
    });
  }
}