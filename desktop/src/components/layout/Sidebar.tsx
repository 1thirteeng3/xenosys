/**
 * Sidebar Navigation Component
 * 
 * 6 zones with minimalist icons (Lucide React):
 * - Arena (Home)
 * - Orchestration (State Monitor)
 * - Governance (HITL Queue)
 * - Memory (L1-L4)
 * - Settings
 * - Network
 */

import React from 'react';
import { 
  Home, 
  Network, 
  Shield, 
  Database, 
  Settings, 
  Wifi,
  ChevronLeft,
  ChevronRight
} from 'lucide-react';
import { clsx } from 'clsx';
import { useUIStore, AppZone } from '../../store/uiStore';

interface NavItem {
  id: AppZone;
  label: string;
  icon: React.ReactNode;
}

const NAV_ITEMS: NavItem[] = [
  { id: 'arena', label: 'Arena', icon: <Home className="w-5 h-5" /> },
  { id: 'orchestration', label: 'Orchestration', icon: <Network className="w-5 h-5" /> },
  { id: 'governance', label: 'Governance', icon: <Shield className="w-5 h-5" /> },
  { id: 'memory', label: 'Memory', icon: <Database className="w-5 h-5" /> },
  { id: 'settings', label: 'Settings', icon: <Settings className="w-5 h-5" /> },
  { id: 'network', label: 'Network', icon: <Wifi className="w-5 h-5" /> },
];

export const Sidebar: React.FC = () => {
  const { sidebarOpen, activeZone, setActiveZone, toggleSidebar } = useUIStore();

  return (
    <aside
      className={clsx(
        'h-screen bg-xeno-surface border-r border-xeno-border flex flex-col',
        'transition-all duration-300 ease-in-out',
        sidebarOpen ? 'w-64' : 'w-16'
      )}
    >
      {/* Header / Logo */}
      <div className="h-14 flex items-center justify-between px-4 border-b border-xeno-border">
        {sidebarOpen && (
          <span className="font-bold text-xl text-xeno-accent-active tracking-wider">
            XENOSYS
          </span>
        )}
        <button
          onClick={toggleSidebar}
          className="p-1.5 rounded hover:bg-xeno-border transition-colors text-xeno-border"
        >
          {sidebarOpen ? <ChevronLeft className="w-5 h-5" /> : <ChevronRight className="w-5 h-5" />}
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4 overflow-y-auto">
        <ul className="space-y-1 px-2">
          {NAV_ITEMS.map((item) => (
            <li key={item.id}>
              <button
                onClick={() => setActiveZone(item.id)}
                className={clsx(
                  'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg',
                  'transition-all duration-200',
                  activeZone === item.id
                    ? 'bg-xeno-accent-active/10 text-xeno-accent-active border border-xeno-accent-active/30'
                    : 'text-gray-400 hover:bg-xeno-border hover:text-xeno-accent-active'
                )}
              >
                <span className={clsx(
                  activeZone === item.id ? 'text-xeno-accent-active' : 'text-gray-500'
                )}>
                  {item.icon}
                </span>
                {sidebarOpen && (
                  <span className="text-sm font-medium">{item.label}</span>
                )}
              </button>
            </li>
          ))}
        </ul>
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-xeno-border">
        {sidebarOpen && (
          <div className="text-xs text-xeno-border">
            v1.0.0
          </div>
        )}
      </div>
    </aside>
  );
};

export default Sidebar;