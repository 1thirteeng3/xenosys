/**
 * InitialSettingsPanel - First-Run Setup Wizard
 * This is the initial settings panel where users configure their XenoSys installation.
 * Users select between API mode or Local LLM mode.
 */

import React, { useState, useEffect } from 'react';
import { saveApiKey, getApiKey } from './store';
import { STORAGE_KEYS, DEFAULT_CONFIG } from './config';
import type { UserConfig, LLMMode, LLMProvider, APIKeyConfig } from './config';

// Generate a unique instance ID
const generateInstanceId = (): string => {
  return `xs-${Date.now().toString(36)}-${Math.random().toString(36).substring(2, 9)}`;
};

interface InitialSettingsPanelProps {
  onComplete: (config: UserConfig) => void;
}

export const InitialSettingsPanel: React.FC<InitialSettingsPanelProps> = ({ onComplete }) => {
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Step 1: Basic Configuration
  const [agentName, setAgentName] = useState('');
  const [instanceId, setInstanceId] = useState(generateInstanceId());
  
  // Step 2: LLM Configuration
  const [llmMode, setLlmMode] = useState<LLMMode>('api');
  const [llmProvider, setLlmProvider] = useState<LLMProvider>('openai');
  const [apiKey, setApiKey] = useState('');
  
  // Local LLM (for later step 3)
  const [ollamaUrl, setOllamaUrl] = useState('http://localhost:11434');
  const [ollamaModel, setOllamaModel] = useState('llama2');
  
  // Step 3: Integrations
  const [telegramEnabled, setTelegramEnabled] = useState(false);
  const [telegramToken, setTelegramToken] = useState('');
  const [discordEnabled, setDiscordEnabled] = useState(false);
  const [discordWebhook, setDiscordWebhook] = useState('');
  const [mcpEnabled, setMcpEnabled] = useState(true);
  
  // Step 4: Security
  const [encryption, setEncryption] = useState(true);
  const [readOnlyMode, setReadOnlyMode] = useState(false);
  
  // Loading existing config
  useEffect(() => {
    const loadExistingConfig = async () => {
      try {
        const completed = await getApiKey(STORAGE_KEYS.SETUP_COMPLETED);
        if (completed === 'true') {
          // Setup already completed, load config
          const savedAgentName = await getApiKey(STORAGE_KEYS.AGENT_NAME);
          const savedLlmMode = await getApiKey(STORAGE_KEYS.LLM_MODE);
          const savedLlmProvider = await getApiKey(STORAGE_KEYS.LLM_PROVIDER);
          
          if (savedAgentName) {
            const config: UserConfig = {
              agentName: savedAgentName,
              instanceId: generateInstanceId(),
              createdAt: new Date().toISOString(),
              updatedAt: new Date().toISOString(),
              llmMode: (savedLlmMode as LLMMode) || 'api',
              llmProvider: (savedLlmProvider as LLMProvider) || 'openai',
              apiKeys: [],
              integrations: [],
              encryption: true,
              readOnlyMode: false,
              setupCompleted: true,
              setupStep: 4,
            };
            onComplete(config);
          }
        }
      } catch (e) {
        console.log('[Setup] No existing config found, starting fresh');
      }
    };
    
    loadExistingConfig();
  }, [onComplete]);
  
  // Handle Step 1 - Basic Config
  const handleStep1Submit = async () => {
    if (!agentName.trim()) {
      setError('Please enter an agent name');
      return;
    }
    await saveApiKey(STORAGE_KEYS.AGENT_NAME, agentName);
    await saveApiKey(STORAGE_KEYS.INSTANCE_ID, instanceId);
    setError(null);
    setStep(2);
  };
  
  // Handle Step 2 - LLM Configuration  
  const handleStep2Submit = async () => {
    if (llmMode === 'api') {
      if (!apiKey.trim()) {
        setError('Please enter an API key');
        return;
      }
      
      // Save the API key
      let keyName: string;
      switch (llmProvider) {
        case 'openai':
          keyName = 'openai_api_key';
          break;
        case 'anthropic':
          keyName = 'anthropic_api_key';
          break;
        case 'google':
          keyName = 'google_api_key';
          break;
        default:
          keyName = 'api_key';
      }
      
      await saveApiKey(keyName, apiKey);
      await saveApiKey(STORAGE_KEYS.LLM_MODE, 'api');
      await saveApiKey(STORAGE_KEYS.LLM_PROVIDER, llmProvider);
    } else {
      // Local LLM mode - save configuration for later installation
      await saveApiKey(STORAGE_KEYS.LLM_MODE, 'local');
      await saveApiKey(STORAGE_KEYS.LLM_PROVIDER, 'ollama');
      await saveApiKey('ollama_url', ollamaUrl);
      await saveApiKey('ollama_model', ollamaModel);
    }
    
    setError(null);
    setStep(3);
  };
  
  // Handle Step 3 - Integrations
  const handleStep3Submit = async () => {
    if (telegramEnabled && telegramToken.trim()) {
      await saveApiKey('telegram_token', telegramToken);
    }
    if (discordEnabled && discordWebhook.trim()) {
      await saveApiKey('discord_webhook', discordWebhook);
    }
    await saveApiKey(STORAGE_KEYS.INTEGRATIONS, JSON.stringify({
      telegram: telegramEnabled,
      discord: discordEnabled,
      mcp: mcpEnabled,
    }));
    
    setError(null);
    setStep(4);
  };
  
  // Handle Step 4 - Security and Complete
  const handleStep4Submit = async () => {
    await saveApiKey(STORAGE_KEYS.ENCRYPTION, encryption ? 'true' : 'false');
    await saveApiKey(STORAGE_KEYS.READ_ONLY, readOnlyMode ? 'true' : 'false');
    await saveApiKey(STORAGE_KEYS.SETUP_COMPLETED, 'true');
    
    const config: UserConfig = {
      agentName,
      instanceId,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      llmMode,
      llmProvider,
      apiKeys: llmMode === 'api' ? [{ provider: llmProvider, apiKey }] : [],
      localLLM: llmMode === 'local' ? { provider: 'ollama', baseUrl: ollamaUrl, model: ollamaModel } : undefined,
      integrations: [
        ...(telegramEnabled ? [{ type: 'telegram' as const, enabled: true, config: { token: telegramToken } }] : []),
        ...(discordEnabled ? [{ type: 'discord' as const, enabled: true, config: { webhook: discordWebhook } }] : []),
        ...(mcpEnabled ? [{ type: 'mcp' as const, enabled: true, config: {} }] : []),
      ],
      encryption,
      readOnlyMode,
      setupCompleted: true,
      setupStep: 4,
    };
    
    setLoading(false);
    onComplete(config);
  };
  
  // Render Step 1: Basic Configuration
  const renderStep1 = () => (
    <div className="space-y-4">
      <h2 className="text-xl font-bold text-[#00FF9D]">Step 1: Basic Configuration</h2>
      
      <div>
        <label className="block text-sm text-gray-400 mb-1">Agent Name</label>
        <input
          type="text"
          value={agentName}
          onChange={(e) => setAgentName(e.target.value)}
          placeholder="My AI Assistant"
          className="w-full bg-[#1A1A1A] border border-[#333] rounded px-3 py-2 text-white focus:border-[#00FF9D] outline-none"
        />
      </div>
      
      <div>
        <label className="block text-sm text-gray-400 mb-1">Instance ID</label>
        <input
          type="text"
          value={instanceId}
          onChange={(e) => setInstanceId(e.target.value)}
          className="w-full bg-[#1A1A1A] border border-[#333] rounded px-3 py-2 text-gray-500"
          disabled
        />
        <p className="text-xs text-gray-600 mt-1">Auto-generated unique identifier</p>
      </div>
    </div>
  );
  
  // Render Step 2: LLM Configuration
  const renderStep2 = () => (
    <div className="space-y-4">
      <h2 className="text-xl font-bold text-[#00FF9D]">Step 2: LLM Provider Selection</h2>
      
      <div className="space-y-2">
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="radio"
            name="llmMode"
            value="api"
            checked={llmMode === 'api'}
            onChange={() => setLlmMode('api')}
            className="accent-[#00FF9D]"
          />
          <span className="text-white">Use API LLM (default)</span>
        </label>
        <p className="text-sm text-gray-500 ml-6">Uses cloud APIs (OpenAI, Anthropic, Google) - lightweight installation</p>
        
        <label className="flex items-center gap-2 cursor-pointer mt-4">
          <input
            type="radio"
            name="llmMode"
            value="local"
            checked={llmMode === 'local'}
            onChange={() => setLlmMode('local')}
            className="accent-[#00FF9D]"
          />
          <span className="text-white">Use Local LLM</span>
        </label>
        <p className="text-sm text-gray-500 ml-6">Will install Ollama on-demand for offline inference</p>
      </div>
      
      {llmMode === 'api' ? (
        <div className="space-y-4 mt-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">Provider</label>
            <select
              value={llmProvider}
              onChange={(e) => setLlmProvider(e.target.value as LLMProvider)}
              className="w-full bg-[#1A1A1A] border border-[#333] rounded px-3 py-2 text-white focus:border-[#00FF9D] outline-none"
            >
              <option value="openai">OpenAI</option>
              <option value="anthropic">Anthropic (Claude)</option>
              <option value="google">Google (Gemini)</option>
            </select>
          </div>
          
          <div>
            <label className="block text-sm text-gray-400 mb-1">API Key</label>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={llmProvider === 'openai' ? 'sk-...' : ''}
              className="w-full bg-[#1A1A1A] border border-[#333] rounded px-3 py-2 text-white focus:border-[#00FF9D] outline-none"
            />
          </div>
        </div>
      ) : (
        <div className="space-y-4 mt-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">Ollama URL</label>
            <input
              type="text"
              value={ollamaUrl}
              onChange={(e) => setOllamaUrl(e.target.value)}
              placeholder="http://localhost:11434"
              className="w-full bg-[#1A1A1A] border border-[#333] rounded px-3 py-2 text-white focus:border-[#00FF9D] outline-none"
            />
          </div>
          
          <div>
            <label className="block text-sm text-gray-400 mb-1">Model</label>
            <select
              value={ollamaModel}
              onChange={(e) => setOllamaModel(e.target.value)}
              className="w-full bg-[#1A1A1A] border border-[#333] rounded px-3 py-2 text-white focus:border-[#00FF9D] outline-none"
            >
              <option value="llama2">Llama 2</option>
              <option value="llama3">Llama 3</option>
              <option value="mistral">Mistral</option>
              <option value="phi">Phi</option>
            </select>
          </div>
        </div>
      )}
    </div>
  );
  
  // Render Step 3: Integrations
  const renderStep3 = () => (
    <div className="space-y-4">
      <h2 className="text-xl font-bold text-[#00FF9D]">Step 3: Integrations</h2>
      
      <div className="space-y-3">
        <label className="flex items-center justify-between bg-[#1A1A1A] p-3 rounded cursor-pointer">
          <div>
            <span className="text-white">Telegram Bot</span>
            <p className="text-xs text-gray-500">Connect via Telegram</p>
          </div>
          <input
            type="checkbox"
            checked={telegramEnabled}
            onChange={(e) => setTelegramEnabled(e.target.checked)}
            className="accent-[#00FF9D]"
          />
        </label>
        
        {telegramEnabled && (
          <input
            type="text"
            value={telegramToken}
            onChange={(e) => setTelegramToken(e.target.value)}
            placeholder="Telegram Bot Token"
            className="w-full bg-[#1A1A1A] border border-[#333] rounded px-3 py-2 text-white focus:border-[#00FF9D] outline-none"
          />
        )}
        
        <label className="flex items-center justify-between bg-[#1A1A1A] p-3 rounded cursor-pointer">
          <div>
            <span className="text-white">Discord Webhook</span>
            <p className="text-xs text-gray-500">Send notifications to Discord</p>
          </div>
          <input
            type="checkbox"
            checked={discordEnabled}
            onChange={(e) => setDiscordEnabled(e.target.checked)}
            className="accent-[#00FF9D]"
          />
        </label>
        
        {discordEnabled && (
          <input
            type="text"
            value={discordWebhook}
            onChange={(e) => setDiscordWebhook(e.target.value)}
            placeholder="Discord Webhook URL"
            className="w-full bg-[#1A1A1A] border border-[#333] rounded px-3 py-2 text-white focus:border-[#00FF9D] outline-none"
          />
        )}
        
        <label className="flex items-center justify-between bg-[#1A1A1A] p-3 rounded cursor-pointer">
          <div>
            <span className="text-white">MCP Tools</span>
            <p className="text-xs text-gray-500">Enable Model Context Protocol tools</p>
          </div>
          <input
            type="checkbox"
            checked={mcpEnabled}
            onChange={(e) => setMcpEnabled(e.target.checked)}
            className="accent-[#00FF9D]"
          />
        </label>
      </div>
    </div>
  );
  
  // Render Step 4: Security
  const renderStep4 = () => (
    <div className="space-y-4">
      <h2 className="text-xl font-bold text-[#00FF9D]">Step 4: Security</h2>
      
      <label className="flex items-center gap-2 cursor-pointer">
        <input
          type="checkbox"
          checked={encryption}
          onChange={(e) => setEncryption(e.target.checked)}
          className="accent-[#00FF9D]"
        />
        <span className="text-white">Enable AES-256-GCM encryption</span>
      </label>
      
      <label className="flex items-center gap-2 cursor-pointer mt-4">
        <input
          type="checkbox"
          checked={readOnlyMode}
          onChange={(e) => setReadOnlyMode(e.target.checked)}
          className="accent-[#00FF9D]"
        />
        <span className="text-white">Read-only mode (no tool execution)</span>
      </label>
    </div>
  );
  
  // Main render
  const renderStep = () => {
    switch (step) {
      case 1:
        return renderStep1();
      case 2:
        return renderStep2();
      case 3:
        return renderStep3();
      case 4:
        return renderStep4();
      default:
        return null;
    }
  };
  
  const handleSubmit = () => {
    switch (step) {
      case 1:
        handleStep1Submit();
        break;
      case 2:
        handleStep2Submit();
        break;
      case 3:
        handleStep3Submit();
        break;
      case 4:
        handleStep4Submit();
        break;
    }
  };
  
  return (
    <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-[#111] border border-[#333] rounded-lg p-6">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold text-[#00FF9D]">XenoSys Setup</h1>
          <span className="text-gray-500">Step {step}/4</span>
        </div>
        
        {/* Progress bar */}
        <div className="w-full h-1 bg-[#1A1A1A] rounded mb-6">
          <div
            className="h-full bg-[#00FF9D] transition-all duration-300"
            style={{ width: `${(step / 4) * 100}%` }}
          />
        </div>
        
        {error && (
          <div className="bg-[#FF3366]/20 border border-[#FF3366] text-[#FF3366] px-3 py-2 rounded mb-4">
            {error}
          </div>
        )}
        
        {renderStep()}
        
        <button
          onClick={handleSubmit}
          disabled={loading}
          className="w-full mt-6 bg-[#00FF9D] text-black font-bold py-3 rounded hover:bg-[#00FF9D]/80 transition-colors disabled:opacity-50"
        >
          {loading ? 'Saving...' : step === 4 ? 'Complete Setup' : 'Continue'}
        </button>
        
        {step > 1 && (
          <button
            onClick={() => setStep(step - 1)}
            className="w-full mt-2 text-gray-500 hover:text-white transition-colors"
          >
            Back
          </button>
        )}
      </div>
    </div>
  );
};

export default InitialSettingsPanel;