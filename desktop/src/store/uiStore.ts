/**
 * XenoSys UI State Management - Zustand Store
 * 
 * Manages:
 * - Layout state (sidebar, active zone)
 * - Theme preferences
 * - Agent focus state
 * - UI preferences
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type AppZone = 
  | 'arena'      // Home - Chat + Logs
  | 'orchestration'  // State Monitor
  | 'governance'     // HITL Queue
  | 'memory'        // L1-L4 Memory
  | 'settings'      // Configuration
  | 'network';      // Tunnel settings

interface UIState {
  // Layout
  sidebarOpen: boolean;
  activeZone: AppZone;
  
  // Agent focus
  focusedAgentId: string | null;
  
  // UI preferences
  theme: 'dark' | 'light';
  compactMode: boolean;
  
  // Actions
  toggleSidebar: () => void;
  setActiveZone: (zone: AppZone) => void;
  setFocusedAgent: (agentId: string | null) => void;
  setTheme: (theme: 'dark' | 'light') => void;
  toggleCompactMode: () => void;
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      // Initial state
      sidebarOpen: true,
      activeZone: 'arena',
      focusedAgentId: null,
      theme: 'dark',
      compactMode: false,
      
      // Actions
      toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
      
      setActiveZone: (zone) => set({ activeZone: zone }),
      
      setFocusedAgent: (agentId) => set({ focusedAgentId: agentId }),
      
      setTheme: (theme) => set({ theme }),
      
      toggleCompactMode: () => set((state) => ({ compactMode: !state.compactMode })),
    }),
    {
      name: 'xenosys-ui-storage',
      partialize: (state) => ({
        sidebarOpen: state.sidebarOpen,
        theme: state.theme,
        compactMode: state.compactMode,
      }),
    }
  )
);

export default useUIStore;