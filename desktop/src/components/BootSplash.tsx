/**
 * BootSplash - Startup synchronization barrier
 * Prevents race condition where UI loads before sidecars are ready
 */

import React, { useEffect, useState } from 'react';

interface BootSplashProps {
  onReady: () => void;
}

/**
 * BootSplash component that polls the /ready endpoint
 * until all sidecars (Gateway + Core) are synchronized
 */
export const BootSplash: React.FC<BootSplashProps> = ({ onReady }) => {
  const [status, setStatus] = useState('Initializing cognitive engine...');
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let isMounted = true;

    const checkHealth = async () => {
      try {
        // Poll /ready endpoint which checks both Gateway and Core (gRPC)
        const response = await fetch('http://127.0.0.1:3000/ready');
        
        if (response.ok) {
          const data = await response.json();
          
          if (data.ready && isMounted) {
            setStatus('Systems online. Connecting...');
            // Smooth transition
            setTimeout(onReady, 500);
            return;
          } else if (isMounted) {
            setStatus(`Syncing sidecars... (attempt ${attempt + 1})`);
          }
        }
        
        if (isMounted) {
          setStatus('Waiting for sidecar synchronization...');
          // Retry in 1 second
          setTimeout(checkHealth, 1000);
          setAttempt(prev => prev + 1);
        }
      } catch {
        if (isMounted) {
          setStatus('Waiting for cognitive engine...');
          // Retry in 1 second
          setTimeout(checkHealth, 1000);
          setAttempt(prev => prev + 1);
        }
      }
    };

    // Start polling
    checkHealth();

    return () => {
      isMounted = false;
    };
  }, [onReady, attempt]);

  return (
    <div className="flex flex-col items-center justify-center h-screen bg-[#0A0A0A] text-[#00FF9D] font-mono">
      {/* Animated loading indicator */}
      <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-[#00FF9D] mb-4"></div>
      
      {/* Status text */}
      <p className="text-lg">{status}</p>
      
      {/* Subtle progress indicator */}
      <div className="mt-4 w-48 h-1 bg-[#1A1A1A] rounded overflow-hidden">
        <div 
          className="h-full bg-[#00FF9D] transition-all duration-300"
          style={{ width: `${Math.min((attempt / 30) * 100, 100)}%` }}
        />
      </div>
    </div>
  );
};

export default BootSplash;