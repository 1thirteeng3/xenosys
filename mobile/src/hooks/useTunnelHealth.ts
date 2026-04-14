/**
 * Tunnel Health Hook
 * Monitors connection to desktop via Cloudflare tunnel/SSE
 * - Manages pairing state
 * - Tracks pending HITL count
 * - Handles offline graceful degradation
 * - MOBILE RESILIENCE: Reconnection on foreground return
 * - FIX: Persistent storage using AsyncStorage
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { AppState, AppStateStatus } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';

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
  const [config, setConfig] = useState<TunnelConfig | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [latency, setLatency] = useState(0);
  const [pendingCount, setPendingCount] = useState(0);
  const [error, setError] = useState<string | null>(null);
  
  const appState = useRef<AppStateStatus>(AppState.currentState);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

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

  // Force reconnection when app returns from background
  const forceReconnect = useCallback(async () => {
    if (!config) return;
    
    console.log('App returned to foreground. Forcing tunnel sync...');
    setIsLoading(true);
    
    try {
      // 1. Validate connection
      await validateConnection(config.tunnelUrl);
      
      // 2. Sync missing messages
      await fetch(`${config.tunnelUrl}/api/v1/sessions/current/sync`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${config.token}`,
          'Content-Type': 'application/json',
        },
      });
    } catch (e) {
      console.error('Reconnection failed:', e);
    } finally {
      setIsLoading(false);
    }
  }, [config, validateConnection]);

  // Initialize on mount - FIX: Load from persistent storage
  useEffect(() => {
    const init = async () => {
      try {
        // FIX: Actually load config from AsyncStorage
        const savedRaw = await AsyncStorage.getItem(TUNNEL_CONFIG_KEY);
        if (savedRaw) {
          const saved = JSON.parse(savedRaw) as TunnelConfig;
          setConfig(saved);
          await validateConnection(saved.tunnelUrl);
        }
      } catch (e) {
        setError('Failed to load configuration');
      } finally {
        setIsLoading(false);
      }
    };
    init();
  }, [validateConnection]);

  // App state listener for mobile resilience
  useEffect(() => {
    const subscription = AppState.addEventListener('change', (nextAppState) => {
      // Detect background → foreground transition
      if (
        appState.current.match(/inactive|background/) && 
        nextAppState === 'active'
      ) {
        forceReconnect();
      }
      appState.current = nextAppState;
    });

    return () => {
      subscription.remove();
    };
  }, [forceReconnect]);

  // Periodic health check
  useEffect(() => {
    if (!config) return;
    
    const check = async () => {
      await validateConnection(config.tunnelUrl);
    };
    
    // Initial check
    check();
    
    // Interval polling
    intervalRef.current = setInterval(check, 30000);
    
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [config, validateConnection]);

  // Check pending HITL items
  useEffect(() => {
    if (!config || !isConnected) return;
    
    const checkPending = async () => {
      try {
        const response = await fetch(`${config.tunnelUrl}/api/governance/pending`, {
          headers: {
            'Authorization': `Bearer ${config.token}`,
          },
        });
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

  // Pair with desktop - FIX: Save to persistent storage
  const pair = useCallback(async (tunnelUrl: string, token: string) => {
    setIsLoading(true);
    setError(null);
    
    try {
      const valid = await validateConnection(tunnelUrl);
      if (!valid) {
        setError('Could not connect to server');
        setIsLoading(false);
        return false;
      }
      
      const newConfig: TunnelConfig = {
        tunnelUrl,
        token,
        pairedAt: Date.now(),
      };
      
      // FIX: Save to AsyncStorage for persistence
      await AsyncStorage.setItem(TUNNEL_CONFIG_KEY, JSON.stringify(newConfig));
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

  // Unpair - FIX: Clear from storage
  const unpair = useCallback(async () => {
    await AsyncStorage.removeItem(TUNNEL_CONFIG_KEY);
    setConfig(null);
    setIsConnected(false);
    setPendingCount(0);
  }, []);

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