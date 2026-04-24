/**
 * Main Layout - Desktop Command Center
 * 
 * Structure:
 * - Sidebar (w-64 when open)
 * - Main Content Area (flex-1)
 * - Resource Monitor in Header
 */

import React from 'react';
import { clsx } from 'clsx';
import { Sidebar } from './Sidebar';
import { useUIStore } from '../../store/uiStore';
import { ConnectionStatus } from '../atomic';

interface MainLayoutProps {
  children: React.ReactNode;
  connectionState?: 'connected' | 'connecting' | 'disconnected';
  ramUsage?: number; // GB
  vramUsage?: number; // GB
}

export const MainLayout: React.FC<MainLayoutProps> = ({ 
  children,
  connectionState = 'connected',
  ramUsage = 0,
  vramUsage = 0,
}) => {
  const { sidebarOpen } = useUIStore();

  // Resource indicator with threshold warning
  const isResourceCritical = ramUsage > 12; // >12GB = red
  
  return (
    <div className="flex h-screen bg-xeno-bg overflow-hidden">
      {/* Sidebar */}
      <Sidebar />
      
      {/* Main Content */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Top Bar - Connection Status + Resource Monitor */}
        <header className="h-12 border-b border-xeno-border flex items-center justify-between px-4 bg-xeno-surface">
          <div className="text-sm text-gray-400">
            XenoSys <span className="text-xeno-accent-active">Engine</span>
          </div>
          
          <div className="flex items-center gap-4">
            {/* Resource Monitor */}
            {(ramUsage > 0 || vramUsage > 0) && (
              <div className={clsx(
                'flex items-center gap-2 text-xs font-mono px-2 py-1 rounded',
                isResourceCritical 
                  ? 'bg-xeno-accent-error/20 text-xeno-accent-error' 
                  : 'text-gray-400'
              )}>
                <span>RAM: {ramUsage.toFixed(1)}GB</span>
                {vramUsage > 0 && (
                  <span className="text-xeno-border">|</span>
                )}
                {vramUsage > 0 && (
                  <span>VRAM: {vramUsage.toFixed(1)}GB</span>
                )}
              </div>
            )}
            
            <ConnectionStatus 
              state={connectionState} 
              showLatency 
              latency={12}
            />
          </div>
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