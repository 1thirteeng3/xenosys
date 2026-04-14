/**
 * XenoSys Gateway - gRPC Bridge
 * TypeScript ↔ Python interop via gRPC with TLS
 */

import * as grpc from '@grpc/grpc-js';
import { status } from '@grpc/grpc-js';
import * as protoLoader from '@grpc/proto-loader';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { readFileSync, existsSync } from 'fs';
import { AgentRequest, AgentResponse } from '../gateway/types.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// ============================================================================
// Configuration
// ============================================================================

interface TLSConfig {
  enabled: boolean;
  certPath?: string;
  keyPath?: string;
  caPath?: string;
}

interface GRPCBridgeConfig {
  endpoint: string;
  tls?: TLSConfig;
  connectionTimeout?: number;
}

// ============================================================================
// Proto Service Interface (Generated Stub Pattern)
// ============================================================================

interface NexusRuntimeClient {
  executeAgent(
    request: ExecuteAgentRequest,
    callback: (error: grpc.ServiceError | null, response: ExecuteAgentResponse) => void
  ): void;
  
  streamAgent(
    request: ExecuteAgentRequest,
    metadata?: grpc.Metadata,
    options?: grpc.CallOptions
  ): grpc.ClientReadableStream<ExecuteAgentResponse>;
  
  getStatus(
    request: StatusRequest,
    callback: (error: grpc.ServiceError | null, response: StatusResponse) => void
  ): void;
}

// Proto message types
interface ExecuteAgentRequest {
  session_id?: string;
  user_id?: string;
  message?: string;
  context?: {
    agent_id?: string;
    entity_id?: string;
    system_prompt?: string;
  };
  options?: {
    max_iterations?: number;
    timeout_ms?: number;
    temperature?: number;
    model?: string;
  };
}

interface ExecuteAgentResponse {
  session_id?: string;
  message_id?: string;
  content?: string;
  done?: boolean;
  metadata?: {
    model?: string;
    tokens_in?: number;
    tokens_out?: number;
    cost_usd?: number;
    latency_ms?: number;
    iterations?: number;
  };
  error?: string;
}

interface StatusRequest {
  node_id?: string;
}

interface StatusResponse {
  status?: string;
  version?: string;
}
// ============================================================================
// Error Mapping
// ============================================================================

/**
 * Map gRPC errors to HTTP status codes.
 * Prevents stack trace leaks and provides semantic HTTP responses.
 */
function mapGrpcErrorToHttp(error: any): { status: number; message: string } {
  if (!error || !error.code) {
    return { status: 500, message: 'Internal Server Error' };
  }

  switch (error.code) {
    case status.INVALID_ARGUMENT:
      return { status: 400, message: 'Bad Request' };
    case status.NOT_FOUND:
      return { status: 404, message: 'Not Found' };
    case status.ALREADY_EXISTS:
      return { status: 409, message: 'Conflict' };
    case status.PERMISSION_DENIED:
      return { status: 403, message: 'Forbidden' };
    case status.UNAUTHENTICATED:
      return { status: 401, message: 'Unauthorized' };
    case status.RESOURCE_EXHAUSTED:
      return { status: 429, message: 'Too Many Requests' };
    case status.UNAVAILABLE:
      return { status: 503, message: 'Service Unavailable' };
    case status.DEADLINE_EXCEEDED:
      return { status: 504, message: 'Gateway Timeout' };
    default:
      return { status: 500, message: error.details || 'Unknown Error' };
  }
}

// ============================================================================
// gRPC Bridge
// ============================================================================

export class GRPCBridge {
  private static instance: GRPCBridge;
  private client: NexusRuntimeClient | null = null;
  private server: grpc.Server | null = null;
  private connected = false;
  private config: GRPCBridgeConfig | null = null;
  
  // Circuit breaker state
  private failures = 0;
  private lastFailure: number = 0;
  private readonly circuitBreakerThreshold = 5;
  private readonly circuitBreakerTimeout = 30000; // 30 seconds

  private constructor() {}

  static getInstance(): GRPCBridge {
    if (!GRPCBridge.instance) {
      GRPCBridge.instance = new GRPCBridge();
    }
    return GRPCBridge.instance;
  }

  /**
   * Connect as client to Python runtime with TLS
   */
  async connect(config: GRPCBridgeConfig): Promise<void> {
    if (this.client) {
      throw new Error('Already connected');
    }

    this.config = config;

    // Check circuit breaker
    if (this.isCircuitOpen()) {
      throw new Error('Circuit breaker is open');
    }

    // Load proto file with proper path resolution
    const protoPath = this.resolveProtoPath();
    
    if (!existsSync(protoPath)) {
      throw new Error(`Proto file not found: ${protoPath}`);
    }

    const packageDefinition = protoLoader.loadSync(protoPath, {
      keepCase: false,
      longs: String,
      enums: String,
      defaults: true,
      oneofs: true,
      includeDirs: [resolve(__dirname, '../../proto')],
    });

    const protoDescriptor = grpc.loadPackageDefinition(packageDefinition);
    
    // STRICT namespace access - no blind fallback
    const nexusProto = (protoDescriptor as Record<string, unknown>)['nexus'];
    
    if (!nexusProto) {
      throw new Error('Failed to load nexus proto - namespace "nexus" not found');
    }
    
    const runtime = (nexusProto as Record<string, unknown>)['Runtime'];
    
    if (!runtime) {
      throw new Error('Failed to load Runtime service from nexus package');
    }

    // Create credentials (TLS or insecure)
    const credentials = this.createCredentials(config.tls);

    // Create client using the service constructor
    this.client = new runtime(
      config.endpoint,
      credentials
    ) as NexusRuntimeClient;

    // Wait for connection
    await this.waitForConnection(config.connectionTimeout ?? 10000);
    this.connected = true;
    this.failures = 0;
    
    console.log(`gRPC bridge connected to ${config.endpoint}`);
  }

  /**
   * Start as server (Python runtime connects to us)
   */
  async startServer(port: number, tlsConfig?: TLSConfig): Promise<void> {
    if (this.server) {
      throw new Error('Server already running');
    }

    const protoPath = this.resolveProtoPath();
    
    if (!existsSync(protoPath)) {
      throw new Error(`Proto file not found: ${protoPath}`);
    }

    const packageDefinition = protoLoader.loadSync(protoPath, {
      keepCase: false,
      longs: String,
      enums: String,
      defaults: true,
      oneofs: true,
      includeDirs: [resolve(__dirname, '../../proto')],
    });

    const protoDescriptor = grpc.loadPackageDefinition(packageDefinition);
    
    // STRICT namespace access
    const nexusProto = (protoDescriptor as Record<string, unknown>)['nexus'];
    
    if (!nexusProto) {
      throw new Error('Failed to load nexus proto');
    }
    
    const runtime = (nexusProto as Record<string, unknown>)['Runtime'];
    
    if (!runtime) {
      throw new Error('Runtime service not found');
    }

    this.server = new grpc.Server();

    this.server.addService(
      runtime.service,
      {
        ExecuteAgent: this.handleExecuteAgent.bind(this),
        StreamAgent: this.handleStreamAgent.bind(this),
        GetStatus: this.handleGetStatus.bind(this),
      }
    );

    const serverCreds = tlsConfig?.enabled 
      ? this.createServerCredentials(tlsConfig)
      : grpc.ServerCredentials.createInsecure();

    await new Promise<void>((resolve, reject) => {
      this.server!.bindAsync(
        `0.0.0.0:${port}`,
        serverCreds,
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
   * Execute agent via gRPC using generated stub
   */
  async executeAgent(request: AgentRequest): Promise<AgentResponse> {
    if (!this.client) {
      throw new Error('Not connected to Python runtime');
    }

    // Check circuit breaker
    if (this.isCircuitOpen()) {
      throw new Error('Circuit breaker is open - service unavailable');
    }

    // Convert to proto request
    const protoRequest: ExecuteAgentRequest = this.toProtoRequest(request);

    return new Promise((resolve, reject) => {
      // Use generated stub method instead of makeUnaryRequest
      this.client!.executeAgent(
        protoRequest,
        (error: grpc.ServiceError | null, response?: ExecuteAgentResponse) => {
          if (error) {
            this.recordFailure();
            reject(this.formatError(error));
          } else if (response) {
            this.resetFailures();
            resolve(this.fromProtoResponse(response));
          } else {
            reject(new Error('Empty response from gRPC'));
          }
        }
      );
    });
  }

  /**
   * Stream agent execution using generated stub
   */
  async *streamAgent(request: AgentRequest): AsyncGenerator<AgentResponse> {
    if (!this.client) {
      throw new Error('Not connected to Python runtime');
    }

    const protoRequest = this.toProtoRequest(request);

    // Use generated stub method instead of makeServerStreamingRequest
    const call = this.client.streamAgent(protoRequest);

    return yield* call;
  }

  /**
   * Check health using generated stub
   */
  async isHealthy(): Promise<boolean> {
    if (!this.client) return false;

    return new Promise((resolve) => {
      // Use generated stub method
      this.client!.getStatus(
        { node_id: 'gateway' },
        (error: grpc.ServiceError | null, response?: StatusResponse) => {
          if (error || !response) {
            resolve(false);
          } else {
            resolve(response.status === 'healthy');
          }
        }
      );
    });
  }

  /**
   * Disconnect
   */
  async disconnect(): Promise<void> {
    if (this.client) {
      // @ts-ignore - close method exists
      this.client.close?.();
      this.client = null;
    }

    if (this.server) {
      this.server.tryShutdown();
      this.server = null;
    }

    this.connected = false;
    console.log('gRPC bridge disconnected');
  }

  // ========================================================================
  // Server Handlers
  // ========================================================================

  private handleExecuteAgent(
    call: grpc.ServerUnaryCall<ExecuteAgentRequest, ExecuteAgentResponse>,
    callback: (error: grpc.ServiceError | null, response?: ExecuteAgentResponse) => void
  ): void {
    const request = this.fromProtoRequest(call.request);

    this.executeInRuntime(request)
      .then((response) => {
        callback(null, this.toProtoResponse(response));
      })
      .catch((error) => {
        callback(this.createServiceError('ExecuteError', error), undefined);
      });
  }

  private handleStreamAgent(call: grpc.ServerWritableStream<ExecuteAgentRequest, ExecuteAgentResponse>): void {
    const request = this.fromProtoRequest(call.request);

    this.streamInRuntime(request)
      .then(async function* (responses) {
        for await (const response of responses) {
          call.write(this.toProtoResponse(response));
        }
        call.end();
      }.bind(this))
      .catch((error) => {
        call.emit('error', this.createServiceError('StreamError', error));
      });
  }

  private handleGetStatus(
    call: grpc.ServerUnaryCall<StatusRequest, StatusResponse>,
    callback: (error: grpc.ServiceError | null, response?: StatusResponse) => void
  ): void {
    callback(null, {
      status: 'healthy',
      version: '1.0.0',
    });
  }

  // ========================================================================
  // Runtime Integration (placeholders)
  // ========================================================================

  private async executeInRuntime(request: AgentRequest): Promise<AgentResponse> {
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

  private async *streamInRuntime(request: AgentRequest): AsyncGenerator<AgentResponse> {
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

  private toProtoRequest(request: AgentRequest): ExecuteAgentRequest {
    return {
      session_id: request.sessionId,
      user_id: request.userId,
      message: request.message,
      context: request.context ? {
        agent_id: request.context.agentId,
        entity_id: request.context.entityId,
        system_prompt: request.context.systemPrompt,
      } : undefined,
      options: request.options ? {
        max_iterations: request.options.maxIterations,
        timeout_ms: request.options.timeoutMs,
        temperature: request.options.temperature,
        model: request.options.model,
      } : undefined,
    };
  }

  private fromProtoRequest(proto: ExecuteAgentRequest): AgentRequest {
    return {
      sessionId: proto.session_id ?? '',
      userId: proto.user_id ?? '',
      channel: '',
      message: proto.message ?? '',
      context: proto.context ? {
        agentId: proto.context.agent_id,
        entityId: proto.context.entity_id,
        systemPrompt: proto.context.system_prompt,
      } : undefined,
      options: proto.options ? {
        maxIterations: proto.options.max_iterations,
        timeoutMs: proto.options.timeout_ms,
        temperature: proto.options.temperature,
        model: proto.options.model,
      } : undefined,
    };
  }

  private toProtoResponse(response: AgentResponse): ExecuteAgentResponse {
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
      error: response.error,
    };
  }

  private fromProtoResponse(proto: ExecuteAgentResponse): AgentResponse {
    return {
      sessionId: proto.session_id ?? '',
      messageId: proto.message_id ?? '',
      content: proto.content ?? '',
      done: proto.done ?? false,
      metadata: proto.metadata ? {
        model: proto.metadata.model ?? '',
        tokensIn: proto.metadata.tokens_in ?? 0,
        tokensOut: proto.metadata.tokens_out ?? 0,
        costUsd: proto.metadata.cost_usd ?? 0,
        latencyMs: proto.metadata.latency_ms ?? 0,
        iterations: proto.metadata.iterations ?? 0,
      } : undefined,
      error: proto.error,
    };
  }

  // ========================================================================
  // Helper Methods
  // ========================================================================

  private resolveProtoPath(): string {
    // Priority order: 
    // 1. Production: dist/grpc/../proto (relative to compiled bridge.js)
    // 2. Development: src/grpc/../proto (relative to source)
    // 3. Project root: proto/nexus.proto
    const possiblePaths = [
      resolve(__dirname, '../proto/nexus.proto'),  // Production: dist/proto/
      resolve(__dirname, '../../proto/nexus.proto'), // Dev: src/proto from grpc/
      resolve(__dirname, '../../../proto/nexus.proto'), // Alt dev path
      resolve(process.cwd(), 'proto/nexus.proto'), // Project root
      resolve(process.cwd(), 'src/proto/nexus.proto'), // Src root
    ];

    for (const p of possiblePaths) {
      if (existsSync(p)) {
        console.log(`Using proto file: ${p}`);
        return p;
      }
    }

    return possiblePaths[0];
  }

  private createCredentials(tlsConfig?: TLSConfig): grpc.ChannelCredentials {
    if (!tlsConfig?.enabled) {
      return grpc.credentials.createInsecure();
    }

    if (tlsConfig.caPath && existsSync(tlsConfig.caPath)) {
      return grpc.credentials.createSsl(readFileSync(tlsConfig.caPath));
    }
    
    return grpc.credentials.createSsl();
  }

  private createServerCredentials(tlsConfig: TLSConfig): grpc.ServerCredentials {
    if (!tlsConfig.enabled || !tlsConfig.certPath || !tlsConfig.keyPath) {
      return grpc.ServerCredentials.createInsecure();
    }

    return grpc.ServerCredentials.createSsl(
      tlsConfig.caPath ? readFileSync(tlsConfig.caPath) : undefined,
      [
        {
          cert_chain: readFileSync(tlsConfig.certPath),
          private_key: readFileSync(tlsConfig.keyPath),
        },
      ],
      false
    );
  }

  private waitForConnection(timeout: number): Promise<void> {
    return new Promise((resolve, reject) => {
      const timeoutId = setTimeout(() => {
        reject(new Error(`Connection timeout after ${timeout}ms`));
      }, timeout);

      // @ts-ignore
      this.client!.waitForReady(Date.now() + timeout, (error) => {
        clearTimeout(timeoutId);
        if (error) {
          reject(error);
        } else {
          resolve();
        }
      });
    });
  }

  private isCircuitOpen(): boolean {
    if (this.failures >= this.circuitBreakerThreshold) {
      const timeSinceFailure = Date.now() - this.lastFailure;
      if (timeSinceFailure < this.circuitBreakerTimeout) {
        return true;
      }
      this.failures = 0;
    }
    return false;
  }

  private recordFailure(): void {
    this.failures++;
    this.lastFailure = Date.now();
  }

  private resetFailures(): void {
    this.failures = 0;
  }

  private formatError(error: grpc.ServiceError): Error {
    // Use the mapper to prevent stack trace leaks
    const httpError = mapGrpcErrorToHttp(error);
    return new Error(`[${httpError.status}] ${httpError.message}`);
  }

  private createServiceError(name: string, error: unknown): grpc.ServiceError {
    return {
      name,
      message: error instanceof Error ? error.message : 'Unknown error',
      code: grpc.status.INTERNAL,
    };
  }
}

export default GRPCBridge.getInstance();