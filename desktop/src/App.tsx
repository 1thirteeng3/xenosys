/**
 * XenoSys Desktop Application
 * Main entry point with BootSplash barrier for sidecar synchronization
 */

import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MainLayout } from './components/layout/MainLayout';
import { ArenaZone } from './components/zones/ArenaZone';
import { GovernanceZone } from './components/zones/GovernanceZone';
import { NetworkSettings } from './components/NetworkSettings';
import { useUIStore } from './store/uiStore';
import './styles.css';

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

const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <MainLayout>
        <ZoneRouter />
      </MainLayout>
    </QueryClientProvider>
  );
};

export default App;