/**
 * OllamaDownloadModal - Non-blocking download progress modal
 * 
 * UX Requirements:
 * - Opens when user toggles "Local" mode
 * - Non-blocking - allows user to minimize and continue using Cloud
 * - Shows progress bar with time estimate
 * - Flash animation on completion
 */

import React, { useEffect, useRef } from 'react';
import { clsx } from 'clsx';

export interface OllamaProgress {
  status: 'idle' | 'downloading' | 'extracting' | 'complete' | 'error';
  progress: number;
  speed?: number;
  eta?: number;
  error?: string;
}

interface OllamaDownloadModalProps {
  visible: boolean;
  onClose: () => void;
  onMinimize: () => void;
  progress: OllamaProgress;
  onSwitchMode: () => void;
}

export const OllamaDownloadModal: React.FC<OllamaDownloadModalProps> = ({
  visible,
  onClose,
  onMinimize,
  progress,
  onSwitchMode,
}) => {
  const progressRef = useRef<HTMLDivElement>(null);
  const flashRef = useRef<HTMLDivElement>(null);

  // Animate progress bar
  useEffect(() => {
    if (progressRef.current) {
      progressRef.current.style.width = `${progress.progress}%`;
    }
  }, [progress.progress]);

  // Flash effect on completion
  useEffect(() => {
    if (progress.status === 'complete' && flashRef.current) {
      flashRef.current.classList.add('animate-flash-green');
      setTimeout(() => {
        flashRef.current?.classList.remove('animate-flash-green');
      }, 500);
    }
  }, [progress.status]);

  if (!visible && progress.status === 'idle') return null;

  const getStatusText = () => {
    switch (progress.status) {
      case 'idle': return 'Ready to download';
      case 'downloading': return 'Downloading model...';
      case 'extracting': return 'Extracting model...';
      case 'complete': return 'Ready!';
      case 'error': return 'Download failed';
    }
  };

  const getEtaText = () => {
    if (progress.eta && progress.eta > 0) {
      const mins = Math.floor(progress.eta / 60);
      const secs = Math.floor(progress.eta % 60);
      return mins > 0 ? `${mins}m ${secs}s remaining` : `${secs}s remaining`;
    }
    if (progress.speed) return `${progress.speed.toFixed(1)} MB/s`;
    return '';
  };

  return (
    <div className={clsx('fixed inset-0 z-50', !visible && 'hidden')}>
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/80" />
      
      {/* Modal */}
      <div 
        ref={flashRef}
        className={clsx(
          'absolute bottom-24 left-4 right-4 bg-xeno-surface border border-xeno-border rounded-2xl p-5',
          'transition-all duration-300',
          progress.status === 'complete' && 'border-xeno-accent-active/50'
        )}
      >
        {/* Header */}
        <div className="flex justify-between items-start mb-4">
          <div>
            <h3 className="text-lg font-bold text-xeno-accent-active">Ollama Model</h3>
            <p className="text-sm text-xeno-border">llama3.1:8b</p>
          </div>
          <span className={clsx(
            'px-3 py-1 rounded-full text-xs font-semibold',
            progress.status === 'complete' && 'bg-xeno-accent-active/20 text-xeno-accent-active',
            progress.status === 'error' && 'bg-xeno-accent-error/20 text-xeno-accent-error',
            progress.status !== 'complete' && progress.status !== 'error' && 'bg-xeno-accent-cloud/20 text-xeno-accent-cloud'
          )}>
            {getStatusText()}
          </span>
        </div>

        {/* Progress Bar */}
        <div className="relative h-2 bg-xeno-border rounded-full overflow-hidden mb-2">
          <div 
            ref={progressRef}
            className="h-full bg-xeno-accent-cloud rounded-full transition-all duration-300"
            style={{ width: '0%' }}
          />
        </div>
        <p className="text-xs text-xeno-border text-right mb-4">{progress.progress}%</p>

        {/* Stats */}
        <div className="flex justify-between mb-4">
          <div className="text-center">
            <p className="text-xs text-xeno-border">Speed</p>
            <p className="text-sm font-semibold text-gray-200">
              {progress.speed ? `${progress.speed.toFixed(1)} MB/s` : '--'}
            </p>
          </div>
          <div className="text-center">
            <p className="text-xs text-xeno-border">ETA</p>
            <p className="text-sm font-semibold text-gray-200">{getEtaText() || '--'}</p>
          </div>
          <div className="text-center">
            <p className="text-xs text-xeno-border">Size</p>
            <p className="text-sm font-semibold text-gray-200">4.9 GB</p>
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-3">
          <button 
            onClick={onMinimize}
            className="flex-1 py-3 bg-xeno-border rounded-lg text-center text-gray-200 hover:bg-xeno-border/80"
          >
            Minimize
          </button>
          
          {progress.status === 'complete' ? (
            <button 
              onClick={onSwitchMode}
              className="flex-1 py-3 bg-xeno-accent-active text-xeno-bg rounded-lg font-bold text-center hover:bg-xeno-accent-active/90"
            >
              Switch to Local
            </button>
          ) : (
            <button 
              onClick={onClose}
              className="flex-1 py-3 border border-xeno-accent-error text-xeno-accent-error rounded-lg text-center hover:bg-xeno-accent-error/10"
            >
              Cancel
            </button>
          )}
        </div>

        {/* Note */}
        {progress.status !== 'complete' && (
          <p className="text-xs text-gray-600 text-center mt-3">
            You can continue using Cloud mode while downloading
          </p>
        )}
      </div>
    </div>
  );
};

export default OllamaDownloadModal;