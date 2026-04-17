/**
 * XenoSys Desktop Application
 * Main entry point with BootSplash barrier for sidecar synchronization
 */

import React, { useState, useEffect } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MainLayout } from './components/layout/MainLayout';
import { ArenaZone } from './components/zones/ArenaZone';
import { GovernanceZone } from './components/zones/GovernanceZone';
import { SettingsZone } from './components/zones/SettingsZone';
import { NetworkSettings } from './components/NetworkSettings';
import { InitialSettingsPanel } from './components/InitialSettingsPanel';
import { ModuleInstaller } from './components/ModuleInstaller';
import { useUIStore } from './store/uiStore';
import { getApiKey } from './store';
import { STORAGE_KEYS, type UserConfig } from './config';
import './styles.css';

// Check if setup is completed
const checkSetupCompleted = async (): Promise<boolean> => {
  const completed = await getApiKey(STORAGE_KEYS.SETUP_COMPLETED);
  return completed === 'true';
};

// React Query client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60,
      retry: 1,
    },
  },
});

// Zone router
const ZoneRouter: React.FC = () => {
  const { activeZone } = useUIStore();
  
  switch (activeZone) {
    case 'arena':
      return <ArenaZone />;
    case 'governance':
      return <GovernanceZone />;
    case 'settings':
      return <SettingsZone />;
    case 'network':
      return (
        <div className="p-6">
          <NetworkSettings />
        </div>
      );
    default:
      return (
        <div className="flex items-center justify-center h-full text-gray-500">
          <p>{activeZone} - Coming Soon</p>
        </div>
      );
  }
};

// Module type for on-demand installation
type ModuleType = 'ollama' | 'mcp-tools' | 'extra-features';

const App: React.FC = () => {
  const [showSetup, setShowSetup] = useState<boolean>(false);
  const [showModuleInstaller, setShowModuleInstaller] = useState<boolean>(false);
  const [installingModule, setInstallingModule] = useState<ModuleType | null>(null);
  const [userConfig, setUserConfig] = useState<UserConfig | null>(null);
  
  // Check setup status on mount
  useEffect(() => {
    const initApp = async () => {
      const completed = await checkSetupCompleted();
      if (!completed) {
        setShowSetup(true);
      }
    };
    
    initApp();
  }, []);
  
  // Handle setup completion
  const handleSetupComplete = (config: UserConfig) => {
    setUserConfig(config);
    setShowSetup(false);
    
    // If user selected local LLM mode, prompt for module installation
    if (config.llmMode === 'local') {
      setInstallingModule('ollama');
      setShowModuleInstaller(true);
    }
  };
  
  // Handle module installation completion
  const handleModuleInstallComplete = () => {
    setShowModuleInstaller(false);
    setInstallingModule(null);
  };
  
  // Handle request to install module later (for settings panel)
  const handleRequestModuleInstall = (moduleType: ModuleType) => {
    setInstallingModule(moduleType);
    setShowModuleInstaller(true);
  };
  
  // Render setup wizard
  if (showSetup) {
    return (
      <QueryClientProvider client={queryClient}>
        <InitialSettingsPanel onComplete={handleSetupComplete} />
      </QueryClientProvider>
    );
  }
  
  // Render module installer
  if (showModuleInstaller && installingModule) {
    return (
      <QueryClientProvider client={queryClient}>
        <ModuleInstaller
          moduleType={installingModule}
          onSuccess={handleModuleInstallComplete}
          onCancel={() => setShowModuleInstaller(false)}
        />
      </QueryClientProvider>
    );
  }
  
  // Render main app
  return (
    <QueryClientProvider client={queryClient}>
      <MainLayout>
        <ZoneRouter />
      </MainLayout>
    </QueryClientProvider>
  );
};

export default App;