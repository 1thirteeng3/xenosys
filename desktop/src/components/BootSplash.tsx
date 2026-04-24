/**
 * BootSplash - Startup synchronization barrier
 * Prevents race condition where UI loads before sidecars are ready
 * 
 * SECURITY FIX: Grace period timeout with clear error message
 * If sidecars don't start within 30s, offer clear exit strategy
 */

import React, { useEffect, useState } from 'react';

interface BootSplashProps {
  onReady: () => void;
}

// Maximum wait time before showing error (30 seconds)
const MAX_BOOT_ATTEMPTS = 30;
const RETRY_INTERVAL_MS = 1000;

export const BootSplash: React.FC<BootSplashProps> = ({ onReady }) => {
  const [status, setStatus] = useState('Initializing cognitive engine...');
  const [attempt, setAttempt] = useState(0);
  const [failed, setFailed] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    const checkHealth = async () => {
      try {
        const response = await fetch('http://127.0.0.1:3000/ready');
        
        if (response.ok) {
          const data = await response.json();
          
          if (data.ready && isMounted) {
            setStatus('Systems online. Connecting...');
            setTimeout(onReady, 500);
            return;
          } else if (isMounted) {
            setStatus(`Syncing sidecars... (attempt ${attempt + 1})`);
          }
        }
        
        if (isMounted) {
          setStatus('Waiting for sidecar synchronization...');
        }
      } catch (e) {
        if (isMounted) {
          // Specific error detection for port conflicts
          if (e instanceof TypeError && e.message.includes('fetch')) {
            setErrorMessage('Port 3000 may be in use by another application');
          }
          setStatus('Waiting for cognitive engine...');
        }
      }
      
      if (isMounted) {
        const nextAttempt = attempt + 1;
        
        // Check for timeout - grace period exceeded
        if (nextAttempt >= MAX_BOOT_ATTEMPTS) {
          setFailed(true);
          setStatus('Startup timeout exceeded');
          return;
        }
        
        setAttempt(nextAttempt);
        setTimeout(checkHealth, RETRY_INTERVAL_MS);
      }
    };

    checkHealth();

    return () => {
      isMounted = false;
    };
  }, [onReady, attempt]);

  const handleManualRetry = () => {
    setFailed(false);
    setAttempt(0);
    setErrorMessage(null);
    setStatus('Retrying...');
  };

  const handleExit = () => {
    // On Tauri, this would open system dialog to change port
    window.open('https://docs.xenosys.ai/troubleshooting/port-conflict', '_blank');
  };

  if (failed) {
    return (
      <div className="flex flex-col items-center justify-center h-screen bg-[#0A0A0A] text-[#FF3366] font-mono">
        <div className="text-4xl mb-4">⚠️</div>
        
        <p className="text-lg text-center mb-2">Failed to start XenoSys</p>
        
        {errorMessage && (
          <p className="text-sm text-gray-400 text-center mb-4">
            {errorMessage}
          </p>
        )}
        
        <p className="text-sm text-gray-500 text-center mb-6">
          Port 3000 or 50051 may be in use by another application.
          <br />
          Close other apps or change port in settings.
        </p>
        
        <div className="flex gap-4">
          <button 
            onClick={handleManualRetry}
            className="px-4 py-2 bg-[#00FF9D] text-black rounded hover:bg-[#00FF9D]/80 transition-colors"
          >
            Retry
          </button>
          
          <button 
            onClick={handleExit}
            className="px-4 py-2 border border-[#FF3366] text-[#FF3366] rounded hover:bg-[#FF3366]/10 transition-colors"
          >
            Get Help
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center h-screen bg-[#0A0A0A] text-[#00FF9D] font-mono">
      <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-[#00FF9D] mb-4"></div>
      
      <p className="text-lg">{status}</p>
      
      <div className="mt-4 w-48 h-1 bg-[#1A1A1A] rounded overflow-hidden">
        <div 
          className="h-full bg-[#00FF9D] transition-all duration-300"
          style={{ width: `${Math.min((attempt / MAX_BOOT_ATTEMPTS) * 100, 100)}%` }}
        />
      </div>
      
      {attempt > 0 && (
        <p className="text-xs text-gray-600 mt-2">
          {attempt}/{MAX_BOOT_ATTEMPTS} attempts
        </p>
      )}
    </div>
  );
};

export default BootSplash;