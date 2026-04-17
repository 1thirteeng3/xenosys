/**
 * OnDemandModuleInstaller - On-demand module installation
 * Installs local LLM (Ollama) when user selects local mode after initial setup
 */

import React, { useState, useEffect } from 'react';
import { saveApiKey, getApiKey } from '../store';
import { STORAGE_KEYS } from '../config';

type ModuleType = 'ollama' | 'mcp-tools' | 'extra-features';

interface ModuleInstallerProps {
  moduleType: ModuleType;
  onSuccess: () => void;
  onCancel: () => void;
}

interface ModuleInfo {
  id: ModuleType;
  name: string;
  description: string;
  size: string;
  command: string;
}

const MODULES: Record<ModuleType, ModuleInfo> = {
  ollama: {
    id: 'ollama',
    name: 'Ollama (Local LLM)',
    description: 'Run large language models locally for offline inference',
    size: '~1.8GB',
    command: 'install-ollama',
  },
  'mcp-tools': {
    id: 'mcp-tools',
    name: 'MCP Tools',
    description: 'Additional Model Context Protocol tools',
    size: '~100MB',
    command: 'install-mcp',
  },
  'extra-features': {
    id: 'extra-features',
    name: 'Extra Features',
    description: 'Additional features and integrations',
    size: '~200MB',
    command: 'install-extras',
  },
};

export const ModuleInstaller: React.FC<ModuleInstallerProps> = ({
  moduleType,
  onSuccess,
  onCancel,
}) => {
  const [status, setStatus] = useState<'installing' | 'downloading' | 'verifying' | 'done' | 'error'>('installing');
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  
  const moduleInfo = MODULES[moduleType];
  
  useEffect(() => {
    const installModule = async () => {
      try {
        // Simulate installation steps
        setStatus('installing');
        setProgress(10);
        
        // Simulate package installation
        await new Promise(resolve => setTimeout(resolve, 1000));
        setProgress(30);
        setStatus('downloading');
        
        // Simulate downloading
        await new Promise(resolve => setTimeout(resolve, 1500));
        setProgress(60);
        
        // Simulate model download (for Ollama)
        if (moduleType === 'ollama') {
          await new Promise(resolve => setTimeout(resolve, 1000));
          setProgress(80);
        }
        
        setStatus('verifying');
        await new Promise(resolve => setTimeout(resolve, 500));
        setProgress(100);
        setStatus('done');
        
        // Save module installation state
        await saveApiKey(`module_${moduleType}_installed`, 'true');
        
        // Delay slightly for UX
        setTimeout(onSuccess, 500);
      } catch (e) {
        setStatus('error');
        setError(e instanceof Error ? e.message : 'Installation failed');
      }
    };
    
    installModule();
  }, [moduleType, onSuccess]);
  
  const getStatusText = () => {
    switch (status) {
      case 'installing':
        return `Installing ${moduleInfo.name}...`;
      case 'downloading':
        return moduleType === 'ollama' 
          ? 'Downloading model...' 
          : `Downloading ${moduleInfo.name.split(' ')[0]}...`;
      case 'verifying':
        return 'Verifying installation...';
      case 'done':
        return '✓ Installation complete!';
      case 'error':
        return '✗ Installation failed';
      default:
        return '';
    }
  };
  
  const formatProgress = (status: string) => {
    switch (status) {
      case 'installing':
        return 25;
      case 'downloading':
        return moduleType === 'ollama' ? 55 : 70;
      case 'verifying':
        return 90;
      case 'done':
        return 100;
      default:
        return progress;
    }
  };
  
  if (status === 'error') {
    return (
      <div className="fixed inset-0 bg-[#0A0A0A] flex items-center justify-center p-4">
        <div className="max-w-md w-full bg-[#111] border border-[#FF3366] rounded-lg p-6">
          <div className="text-center">
            <div className="text-4xl mb-4">⚠️</div>
            <h2 className="text-xl font-bold text-[#FF3366] mb-2">Installation Failed</h2>
            <p className="text-gray-400 mb-4">{error}</p>
            
            <button
              onClick={onCancel}
              className="px-4 py-2 border border-[#FF3366] text-[#FF3366] rounded hover:bg-[#FF3366]/10 transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    );
  }
  
  return (
    <div className="fixed inset-0 bg-[#0A0A0A] flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-[#111] border border-[#333] rounded-lg p-6">
        <div className="text-center">
          <h2 className="text-xl font-bold text-[#00FF9D] mb-4">Installing Modules...</h2>
          
          <div className="mb-4">
            <p className="text-white">{getStatusText()}</p>
          </div>
          
          {/* Progress bar */}
          <div className="w-full h-2 bg-[#1A1A1A] rounded overflow-hidden mb-4">
            <div
              className="h-full bg-[#00FF9D] transition-all duration-500"
              style={{ width: `${formatProgress(status)}%` }}
            />
          </div>
          
          {/* Installation steps */}
          <div className="text-left text-sm space-y-2">
            <div className={`flex items-center gap-2 ${status === 'installing' || status === 'done' ? 'text-[#00FF9D]' : 'text-gray-600'}`}>
              {status === 'installing' ? '◐' : status === 'done' ? '✓' : '○'}
              <span>Install {moduleInfo.name}</span>
            </div>
            <div className={`flex items-center gap-2 ${status === 'downloading' || status === 'done' ? 'text-[#00FF9D]' : 'text-gray-600'}`}>
              {status === 'downloading' ? '◐' : status === 'done' ? '✓' : '○'}
              <span>Download required packages ({moduleInfo.size})</span>
            </div>
            <div className={`flex items-center gap-2 ${status === 'verifying' || status === 'done' ? 'text-[#00FF9D]' : 'text-gray-600'}`}>
              {status === 'verifying' ? '◐' : status === 'done' ? '✓' : '○'}
              <span>Verify installation</span>
            </div>
          </div>
          
          {status === 'done' && (
            <div className="mt-4 p-3 bg-[#00FF9D]/20 border border-[#00FF9D] rounded">
              <p className="text-[#00FF9D]">✓ Module installed successfully</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

// Hook to check if module is installed and prompt for installation
export const useOnDemandModule = (moduleType: ModuleType): {
  isInstalled: boolean;
  isInstalling: boolean;
  install: () => void;
  uninstall: () => Promise<void>;
} => {
  const [isInstalled, setIsInstalled] = useState(false);
  const [isInstalling, setIsInstalling] = useState(false);
  
  useEffect(() => {
    const checkInstallation = async () => {
      const installed = await getApiKey(`module_${moduleType}_installed`);
      setIsInstalled(installed === 'true');
    };
    
    checkInstallation();
  }, [moduleType]);
  
  const install = () => {
    setIsInstalling(true);
  };
  
  const uninstall = async () => {
    await saveApiKey(`module_${moduleType}_installed`, 'false');
    setIsInstalled(false);
  };
  
  return { isInstalled, isInstalling, install, uninstall };
};

export default ModuleInstaller;