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

interface NexusRuntimeClient {
  executeAgent(request: any, callback: any): void;
  streamAgent(request: any, metadata?: grpc.Metadata, options?: grpc.CallOptions): any;
  getStatus(request: any, callback: any): void;
}

function mapGrpcErrorToHttp(error: any): { status: number; message: string } {
  if (!error || !error.code) return { status: 500, message: 'Internal Server Error' };
  switch (error.code) {
    case status.INVALID_ARGUMENT: return { status: 400, message: 'Bad Request' };
    case status.NOT_FOUND: return { status: 404, message: 'Not Found' };
    case status.ALREADY_EXISTS: return { status: 409, message: 'Conflict' };
    case status.PERMISSION_DENIED: return { status: 403, message: 'Forbidden' };
    case status.UNAUTHENTICATED: return { status: 401, message: 'Unauthorized' };
    case status.RESOURCE_EXHAUSTED: return { status: 429, message: 'Too Many Requests' };
    case status.UNAVAILABLE: return { status: 503, message: 'Service Unavailable' };
    case status.DEADLINE_EXCEEDED: return { status: 504, message: 'Gateway Timeout' };
    default: return { status: 500, message: error.details || 'Unknown Error' };
  }
}

export class GRPCBridge {
  private static instance: GRPCBridge;
  private client: NexusRuntimeClient | null = null;
  private server: grpc.Server | null = null;
  private connected = false;
  private config: GRPCBridgeConfig | null = null;
  
  private failures = 0;
  private lastFailure: number = 0;
  private readonly circuitBreakerThreshold = 5;
  private readonly circuitBreakerTimeout = 30000;

  private constructor() {}

  static getInstance(): GRPCBridge {
    if (!GRPCBridge.instance) GRPCBridge.instance = new GRPCBridge();
    return GRPCBridge.instance;
  }

  async connect(config: GRPCBridgeConfig): Promise<void> {
    if (this.client) throw new Error('Already connected');
    this.config = config;

    if (this.isCircuitOpen()) throw new Error('Circuit breaker is open');

    const protoPath = this.resolveProtoPath();
    if (!existsSync(protoPath)) throw new Error(`Proto file not found: ${protoPath}`);

    const packageDefinition = protoLoader.loadSync(protoPath, {
      keepCase: false, longs: String, enums: String, defaults: true, oneofs: true,
      includeDirs: [resolve(__dirname, '../../proto')],
    });

    const protoDescriptor = grpc.loadPackageDefinition(packageDefinition);
    
    // HOTFIX: Cast para 'any' para evitar erro TS2351
    const nexusProto = (protoDescriptor as any)['nexus'];
    if (!nexusProto) throw new Error('Failed to load nexus proto');
    
    const runtime = (nexusProto as any)['Runtime'];
    if (!runtime) throw new Error('Failed to load Runtime service');

    const credentials = this.createCredentials(config.tls);

    this.client = new runtime(config.endpoint, credentials) as NexusRuntimeClient;

    await this.waitForConnection(config.connectionTimeout ?? 10000);
    this.connected = true;
    this.failures = 0;
    console.log(`gRPC bridge connected to ${config.endpoint}`);
  }

  async startServer(port: number, tlsConfig?: TLSConfig): Promise<void> {
    if (this.server) throw new Error('Server already running');

    const protoPath = this.resolveProtoPath();
    if (!existsSync(protoPath)) throw new Error(`Proto file not found: ${protoPath}`);

    const packageDefinition = protoLoader.loadSync(protoPath, {
      keepCase: false, longs: String, enums: String, defaults: true, oneofs: true,
      includeDirs: [resolve(__dirname, '../../proto')],
    });

    const protoDescriptor = grpc.loadPackageDefinition(packageDefinition);
    const nexusProto = (protoDescriptor as any)['nexus'];
    const runtime = (nexusProto as any)['Runtime'];

    this.server = new grpc.Server();
    this.server.addService(runtime.service, {
      ExecuteAgent: this.handleExecuteAgent.bind(this),
      StreamAgent: this.handleStreamAgent.bind(this),
      GetStatus: this.handleGetStatus.bind(this),
    });

    const serverCreds = tlsConfig?.enabled 
      ? this.createServerCredentials(tlsConfig)
      : grpc.ServerCredentials.createInsecure();

    await new Promise<void>((resolve, reject) => {
      this.server!.bindAsync(`0.0.0.0:${port}`, serverCreds, (error, port) => {
        if (error) reject(error);
        else { console.log(`gRPC server listening on port ${port}`); resolve(); }
      });
    });
  }

  async executeAgent(request: AgentRequest): Promise<AgentResponse> {
    if (!this.client) throw new Error('Not connected to Python runtime');
    if (this.isCircuitOpen()) throw new Error('Circuit breaker is open');

    const protoRequest = this.toProtoRequest(request);

    return new Promise((resolve, reject) => {
      this.client!.executeAgent(protoRequest, (error: grpc.ServiceError | null, response?: any) => {
        if (error) {
          this.recordFailure();
          reject(this.formatError(error));
        } else if (response) {
          this.resetFailures();
          resolve(this.fromProtoResponse(response));
        } else {
          reject(new Error('Empty response from gRPC'));
        }
      });
    });
  }

  async *streamAgent(request: AgentRequest): AsyncGenerator<AgentResponse> {
    if (!this.client) throw new Error('Not connected');
    const protoRequest = this.toProtoRequest(request);
    const call = this.client.streamAgent(protoRequest);
    return yield* call;
  }

  async isHealthy(): Promise<boolean> {
    if (!this.client) return false;
    return new Promise((resolve) => {
      this.client!.getStatus({ node_id: 'gateway' }, (error: grpc.ServiceError | null, response?: any) => {
        resolve(!error && response?.status === 'healthy');
      });
    });
  }

  async disconnect(): Promise<void> {
    if (this.client) {
      (this.client as any).close?.();
      this.client = null;
    }
    if (this.server) {
      // HOTFIX: Adicionado callback vazio exigido pelas novas versões do gRPC
      this.server.tryShutdown(() => {});
      this.server = null;
    }
    this.connected = false;
  }

  private handleExecuteAgent(call: any, callback: any): void {
    const request = this.fromProtoRequest(call.request);
    this.executeInRuntime(request)
      .then((response) => callback(null, this.toProtoResponse(response)))
      .catch((error) => callback(this.createServiceError('ExecuteError', error), undefined));
  }

  private handleStreamAgent(call: any): void {
  const request = this.fromProtoRequest(call.request);

  // Executa o stream em uma função assíncrona blindada
  (async () => {
    try {
      for await (const response of this.streamInRuntime(request)) {
        call.write(this.toProtoResponse(response));
      }
      call.end();
    } catch (error: any) {
      call.emit('error', this.createServiceError('StreamError', error));
    }
  })();
}

  private handleGetStatus(call: any, callback: any): void {
    callback(null, { status: 'healthy', version: '1.0.0' });
  }

  private async executeInRuntime(request: AgentRequest): Promise<AgentResponse> {
    return { sessionId: request.sessionId, messageId: `msg-${Date.now()}`, content: 'Agent execution delegated', done: true };
  }

  private async *streamInRuntime(request: AgentRequest): AsyncGenerator<AgentResponse> {
    yield { sessionId: request.sessionId, messageId: `msg-${Date.now()}`, content: 'Done', done: true };
  }

  private toProtoRequest(request: AgentRequest): any {
    return {
      session_id: request.sessionId, user_id: request.userId, message: request.message,
      context: request.context ? { agent_id: request.context.agentId, entity_id: request.context.entityId, system_prompt: request.context.systemPrompt } : undefined,
      options: request.options ? { max_iterations: request.options.maxIterations, timeout_ms: request.options.timeoutMs, temperature: request.options.temperature, model: request.options.model } : undefined,
    };
  }

  private fromProtoRequest(proto: any): AgentRequest {
    return {
      sessionId: proto.session_id ?? '', userId: proto.user_id ?? '', channel: '', message: proto.message ?? '',
      context: proto.context ? { agentId: proto.context.agent_id, entityId: proto.context.entity_id, systemPrompt: proto.context.system_prompt } : undefined,
      options: proto.options ? { maxIterations: proto.options.max_iterations, timeoutMs: proto.options.timeout_ms, temperature: proto.options.temperature, model: proto.options.model } : undefined,
    };
  }

  private toProtoResponse(response: AgentResponse): any {
    return {
      session_id: response.sessionId, message_id: response.messageId, content: response.content, done: response.done,
      metadata: response.metadata ? { model: response.metadata.model, tokens_in: response.metadata.tokensIn, tokens_out: response.metadata.tokensOut, cost_usd: response.metadata.costUsd, latency_ms: response.metadata.latencyMs, iterations: response.metadata.iterations } : undefined,
      error: response.error,
    };
  }

  private fromProtoResponse(proto: any): AgentResponse {
    return {
      sessionId: proto.session_id ?? '', messageId: proto.message_id ?? '', content: proto.content ?? '', done: proto.done ?? false,
      metadata: proto.metadata ? { model: proto.metadata.model ?? '', tokensIn: proto.metadata.tokens_in ?? 0, tokensOut: proto.metadata.tokens_out ?? 0, costUsd: proto.metadata.cost_usd ?? 0, latencyMs: proto.metadata.latency_ms ?? 0, iterations: proto.metadata.iterations ?? 0 } : undefined,
      error: proto.error,
    };
  }

  private resolveProtoPath(): string {
    const possiblePaths = [
      resolve(__dirname, '../proto/nexus.proto'),
      resolve(__dirname, '../../proto/nexus.proto'),
      resolve(__dirname, '../../../proto/nexus.proto'),
      resolve(process.cwd(), 'proto/nexus.proto'),
      resolve(process.cwd(), 'src/proto/nexus.proto'),
    ];
    for (const p of possiblePaths) {
      if (existsSync(p)) return p;
    }
    return possiblePaths[0];
  }

  private createCredentials(tlsConfig?: TLSConfig): grpc.ChannelCredentials {
    if (!tlsConfig?.enabled) return grpc.credentials.createInsecure();
    if (tlsConfig.caPath && existsSync(tlsConfig.caPath)) return grpc.credentials.createSsl(readFileSync(tlsConfig.caPath));
    return grpc.credentials.createSsl();
  }

  private createServerCredentials(tlsConfig: TLSConfig): grpc.ServerCredentials {
    if (!tlsConfig.enabled || !tlsConfig.certPath || !tlsConfig.keyPath) return grpc.ServerCredentials.createInsecure();
    return grpc.ServerCredentials.createSsl(
      tlsConfig.caPath ? readFileSync(tlsConfig.caPath) : undefined,
      [{ cert_chain: readFileSync(tlsConfig.certPath), private_key: readFileSync(tlsConfig.keyPath) }],
      false
    );
  }

  private waitForConnection(timeout: number): Promise<void> {
    return new Promise((resolve, reject) => {
      const timeoutId = setTimeout(() => reject(new Error(`Connection timeout`)), timeout);
      (this.client as any).waitForReady(Date.now() + timeout, (error: any) => {
        clearTimeout(timeoutId);
        if (error) reject(error); else resolve();
      });
    });
  }

  private isCircuitOpen(): boolean {
    if (this.failures >= this.circuitBreakerThreshold) {
      if (Date.now() - this.lastFailure < this.circuitBreakerTimeout) return true;
      this.failures = 0;
    }
    return false;
  }

  private recordFailure(): void { this.failures++; this.lastFailure = Date.now(); }
  private resetFailures(): void { this.failures = 0; }
  private formatError(error: grpc.ServiceError): Error {
    const httpError = mapGrpcErrorToHttp(error);
    return new Error(`[${httpError.status}] ${httpError.message}`);
  }

  // HOTFIX: Adicionado metadados exigidos pela nova interface do gRPC
  private createServiceError(name: string, error: unknown): grpc.ServiceError {
    return {
      name,
      message: error instanceof Error ? error.message : 'Unknown error',
      code: grpc.status.INTERNAL,
      details: error instanceof Error ? error.message : '',
      metadata: new grpc.Metadata()
    };
  }
}

export default GRPCBridge.getInstance();
