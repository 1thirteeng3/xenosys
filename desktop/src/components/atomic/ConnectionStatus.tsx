/**
 * ConnectionStatus - Ubiquitous connection indicator
 * 
 * States:
 * - connected: Green - All systems operational
 * - connecting: Cyan - Attempting to connect
 * - disconnected: Red - Connection lost
 * 
 * Features:
 * - Flash animation when transitioning to Local (cyan to green)
 */

import React, { useEffect, useRef } from 'react';
import { clsx } from 'clsx';
import { 
  Wifi, 
  WifiOff, 
  Loader2 
} from 'lucide-react';

export type ConnectionState = 'connected' | 'connecting' | 'disconnected';

interface ConnectionStatusProps {
  state: ConnectionState;
  label?: string;
  latency?: number;
  showLatency?: boolean;
  className?: string;
}

export const ConnectionStatus: React.FC<ConnectionStatusProps> = ({
  state,
  label,
  latency,
  showLatency = false,
  className,
}) => {
  const flashRef = useRef<HTMLDivElement>(null);
  const prevState = useRef(state);

  // Flash effect on state transition (Cloud → Local)
  useEffect(() => {
    if (prevState.current === 'connecting' && state === 'connected' && flashRef.current) {
      // Trigger flash animation
      flashRef.current.classList.add('animate-flash-green');
      setTimeout(() => {
        flashRef.current?.classList.remove('animate-flash-green');
      }, 500);
    }
    prevState.current = state;
  }, [state]);

  const getIcon = () => {
    switch (state) {
      case 'connected':
        return <Wifi className="w-4 h-4" />;
      case 'connecting':
        return <Loader2 className="w-4 h-4 animate-spin" />;
      case 'disconnected':
        return <WifiOff className="w-4 h-4" />;
    }
  };

  const getLabel = () => {
    if (label) return label;
    switch (state) {
      case 'connected': return 'Connected';
      case 'connecting': return 'Connecting...';
      case 'disconnected': return 'Disconnected';
    }
  };

  return (
    <div 
      ref={flashRef}
      className={clsx(
        'flex items-center gap-2 px-3 py-1.5 rounded-full text-sm transition-all duration-200',
        state === 'connected' && 'bg-xeno-accent-active/20 text-xeno-accent-active',
        state === 'connecting' && 'bg-xeno-accent-cloud/20 text-xeno-accent-cloud',
        state === 'disconnected' && 'bg-xeno-accent-error/20 text-xeno-accent-error',
        className
      )}
    >
      {getIcon()}
      <span>{getLabel()}</span>
      {showLatency && latency !== undefined && (
        <span className="text-xs opacity-70 ml-1">{latency}ms</span>
      )}
    </div>
  );
};

export default ConnectionStatus;