/**
 * Main Layout - Desktop Command Center
 * 
 * Structure:
 * - Sidebar (w-64 when open)
 * - Main Content Area (flex-1)
 */

import React from 'react';
import { clsx } from 'clsx';
import { Sidebar } from './Sidebar';
import { useUIStore } from '../../store/uiStore';
import { ConnectionStatus } from '../atomic';

interface MainLayoutProps {
  children: React.ReactNode;
  connectionState?: 'connected' | 'connecting' | 'disconnected';
}

export const MainLayout: React.FC<MainLayoutProps> = ({ 
  children,
  connectionState = 'connected'
}) => {
  const { sidebarOpen } = useUIStore();

  return (
    <div className="flex h-screen bg-xeno-bg overflow-hidden">
      {/* Sidebar */}
      <Sidebar />
      
      {/* Main Content */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Top Bar - Connection Status */}
        <header className="h-12 border-b border-xeno-border flex items-center justify-between px-4 bg-xeno-surface">
          <div className="text-sm text-gray-400">
            XenoSys <span className="text-xeno-accent-active">Engine</span>
          </div>
          <ConnectionStatus 
            state={connectionState} 
            showLatency 
            latency={12}
          />
        </header>
        
        {/* Zone Content */}
        <div className={clsx(
          'flex-1 overflow-hidden transition-all duration-300',
          sidebarOpen ? 'ml-0' : 'ml-0'
        )}>
          {children}
        </div>
      </main>
    </div>
  );
};

export default MainLayout;