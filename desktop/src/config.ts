/**
 * XenoSys Configuration Types
 * Defines the configuration structure for initial setup
 */

export type LLMMode = 'api' | 'local';

export type LLMProvider = 'openai' | 'anthropic' | 'google' | 'ollama' | 'local';

export interface APIKeyConfig {
  provider: LLMProvider;
  apiKey: string;
  model?: string;
}

export interface LocalLLMConfig {
  provider: 'ollama';
  baseUrl: string;
  model: string;
}

export interface IntegrationConfig {
  type: 'telegram' | 'discord' | 'mcp';
  enabled: boolean;
  config: Record<string, string>;
}

export interface UserConfig {
  // Step 1: Basic Configuration
  agentName: string;
  instanceId: string;
  createdAt: string;
  updatedAt: string;
  
  // Step 2: LLM Configuration
  llmMode: LLMMode;
  llmProvider: LLMProvider;
  apiKeys: APIKeyConfig[];
  localLLM?: LocalLLMConfig;
  
  // Step 3: Integrations
  integrations: IntegrationConfig[];
  
  // Step 4: Security
  encryption: boolean;
  readOnlyMode: boolean;
  
  // Setup state
  setupCompleted: boolean;
  setupStep: number;
}

export const DEFAULT_CONFIG: Partial<UserConfig> = {
  llmMode: 'api',
  llmProvider: 'openai',
  apiKeys: [],
  integrations: [],
  encryption: true,
  readOnlyMode: false,
  setupCompleted: false,
  setupStep: 1,
};

// Storage keys
export const STORAGE_KEYS = {
  CONFIG: 'xenosys_config',
  AGENT_NAME: 'agent_name',
  INSTANCE_ID: 'instance_id',
  LLM_MODE: 'llm_mode',
  LLM_PROVIDER: 'llm_provider',
  API_KEYS: 'api_keys',
  LOCAL_LLM: 'local_llm',
  INTEGRATIONS: 'integrations',
  ENCRYPTION: 'encryption',
  READ_ONLY: 'read_only_mode',
  SETUP_COMPLETED: 'setup_completed',
} as const;