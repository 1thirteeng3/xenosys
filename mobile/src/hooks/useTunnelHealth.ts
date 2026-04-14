/**
 * Tunnel Health Hook
 * Monitors connection to desktop via Cloudflare tunnel/SSE
 * - Manages pairing state
 * - Tracks pending HITL count
 * - Handles offline graceful degradation
 */

import { useState, useEffect, useCallback } from 'react';
import { useStorage } from '@react-native-hooks/async-storage';

// Types
interface TunnelConfig {
  tunnelUrl: string;
  token: string;
  pairedAt?: number;
}

interface TunnelHealth {
  isConnected: boolean;
  isPaired: boolean;
  isLoading: boolean;
  latency: number;
  pendingCount: number;
  error: string | null;
}

// Storage keys
const TUNNEL_CONFIG_KEY = '@xenosys/tunnel_config';

export const useTunnelHealth = () => {
  const [config, setConfig] = useStorage<TunnelConfig | null>(TUNNEL_CONFIG_KEY, null);
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [latency, setLatency] = useState(0);
  const [pendingCount, setPendingCount] = useState(0);
  const [error, setError] = useState<string | null>(null);

  // Initialize on mount
  useEffect(() => {
    const init = async () => {
      try {
        // Load saved config
        const saved = await fetch(TUNNEL_CONFIG_KEY);
        if (saved) {
          setConfig(saved);
          // Validate connection
          await validateConnection(saved.tunnelUrl);
        }
      } catch (e) {
        setError('Failed to load configuration');
      } finally {
        setIsLoading(false);
      }
    };
    init();
  }, []);

  // Validate tunnel connection
  const validateConnection = useCallback(async (url: string) => {
    const start = Date.now();
    try {
      const response = await fetch(`${url}/api/health`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });
      
      if (response.ok) {
        setIsConnected(true);
        setLatency(Date.now() - start);
        setError(null);
        return true;
      }
    } catch (e) {
      setIsConnected(false);
      setError('Server unreachable');
    }
    return false;
  }, []);

  // Pair with desktop
  const pair = useCallback(async (tunnelUrl: string, token: string) => {
    setIsLoading(true);
    setError(null);
    
    try {
      // Validate first
      const valid = await validateConnection(tunnelUrl);
      if (!valid) {
        setError('Could not connect to server');
        setIsLoading(false);
        return false;
      }
      
      // Save config
      const newConfig: TunnelConfig = {
        tunnelUrl,
        token,
        pairedAt: Date.now(),
      };
      
      await store(TUNNEL_CONFIG_KEY, newConfig);
      setConfig(newConfig);
      setIsConnected(true);
      return true;
    } catch (e) {
      setError('Pairing failed');
      return false;
    } finally {
      setIsLoading(false);
    }
  }, [validateConnection]);

  // Unpair
  const unpair = useCallback(async () => {
    await remove(TUNNEL_CONFIG_KEY);
    setConfig(null);
    setIsConnected(false);
    setPendingCount(0);
  }, []);

  // Check pending HITL items
  useEffect(() => {
    if (!config || !isConnected) return;
    
    const checkPending = async () => {
      try {
        const response = await fetch(`${config.tunnelUrl}/api/governance/pending`);
        if (response.ok) {
          const data = await response.json();
          setPendingCount(data.count || 0);
        }
      } catch (e) {
        // Ignore errors in polling
      }
    };
    
    checkPending();
    const interval = setInterval(checkPending, 5000);
    return () => clearInterval(interval);
  }, [config, isConnected]);

  // Health check interval
  useEffect(() => {
    if (!config) return;
    
    const check = async () => {
      await validateConnection(config.tunnelUrl);
    };
    
    const interval = setInterval(check, 30000);
    return () => clearInterval(interval);
  }, [config, validateConnection]);

  return {
    isConnected,
    isPaired: !!config && isConnected,
    isLoading,
    latency,
    pendingCount,
    error,
    pair,
    unpair,
    tunnelUrl: config?.tunnelUrl,
  };
};

export default useTunnelHealth;