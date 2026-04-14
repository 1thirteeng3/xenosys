/**
 * XenoSys Desktop Application
 * Main entry point with BootSplash barrier for sidecar synchronization
 */

import React, { useState } from 'react';
import { BootSplash } from './components/BootSplash';
import { NetworkSettings } from './components/NetworkSettings';

const App: React.FC = () => {
  const [isReady, setIsReady] = useState(false);
  const [showSettings, setShowSettings] = useState(false);

  if (!isReady) {
    return <BootSplash onReady={() => setIsReady(true)} />;
  }

  return (
    <div className="flex flex-col items-center justify-center h-screen bg-[#0A0A0A] text-[#00FF9D] font-mono">
      <h1 className="text-4xl font-bold mb-4">XenoSys</h1>
      <p className="text-lg">Cognitive Engine Online</p>
      
      {/* Settings toggle */}
      <button
        onClick={() => setShowSettings(!showSettings)}
        className="mt-4 px-4 py-2 border border-[#00FF9D] rounded hover:bg-[#00FF9D] hover:text-[#0A0A0A]"
      >
        {showSettings ? 'Fechar Configurações' : 'Configurações de Rede'}
      </button>
      
      {/* Network Settings Panel */}
      {showSettings && (
        <div className="mt-4 w-full max-w-md">
          <NetworkSettings />
        </div>
      )}
      
      {/* Dashboard placeholder */}
      {!showSettings && (
        <div className="mt-8 p-4 border border-[#00FF9D] rounded">
          <p>Dashboard - Coming Soon</p>
        </div>
      )}
    </div>
  );
};

export default App;