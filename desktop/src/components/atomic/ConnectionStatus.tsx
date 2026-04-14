/**
 * ConnectionStatus - Ubiquitous connection indicator
 * 
 * States:
 * - connected: Green - All systems operational
 * - connecting: Cyan - Attempting to connect
 * - disconnected: Red - Connection lost
 * 
 * Display format: [Status Dot] "Status Text" [optional: latency]
 */

import React from 'react';
import { Wifi, WifiOff, Loader2 } from 'lucide-react';
import { clsx } from 'clsx';

export type ConnectionState = 'connected' | 'connecting' | 'disconnected';

interface ConnectionStatusProps {
  state: ConnectionState;
  label?: string;
  latency?: number; // in ms
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
      case 'connected':
        return 'Connected';
      case 'connecting':
        return 'Connecting...';
      case 'disconnected':
        return 'Disconnected';
    }
  };

  return (
    <div className={clsx('connection-indicator', state, className)}>
      {getIcon()}
      <span>{getLabel()}</span>
      {showLatency && latency !== undefined && (
        <span className="text-xs opacity-70 ml-1">
          {latency}ms
        </span>
      )}
    </div>
  );
};

export default ConnectionStatus;