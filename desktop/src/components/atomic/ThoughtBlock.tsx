/**
 * ThoughtBlock - Processing indicator with expandable log viewer
 * 
 * States:
 * - Closed: Shows "Processing..." with pulsating cyan text
 * - Open: Renders DSPy log in a code block with mono font
 */

import React, { useState } from 'react';
import { ChevronDown, ChevronUp, Loader2 } from 'lucide-react';
import { clsx } from 'clsx';

interface ThoughtBlockProps {
  isProcessing?: boolean;
  logContent?: string;
  timestamp?: string;
  className?: string;
}

export const ThoughtBlock: React.FC<ThoughtBlockProps> = ({
  isProcessing = true,
  logContent = '',
  timestamp,
  className,
}) => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className={clsx('thought-block', className)}>
      {/* Header - Always visible */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={clsx(
          'thought-block-processing w-full flex items-center justify-between',
          'hover:bg-xeno-border/50 transition-colors text-left'
        )}
      >
        <div className="flex items-center gap-2">
          {isProcessing ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin text-xeno-accent-cloud" />
              <span className="text-xeno-accent-cloud animate-pulse">
                Processing...
              </span>
            </>
          ) : (
            <>
              <span className="text-xeno-accent-active">✓ Complete</span>
            </>
          )}
        </div>
        
        {isOpen ? (
          <ChevronUp className="w-4 h-4 text-xeno-border" />
        ) : (
          <ChevronDown className="w-4 h-4 text-xeno-border" />
        )}
      </button>

      {/* Log Content - Expandable */}
      {isOpen && logContent && (
        <div className="thought-block-log border-t border-xeno-border">
          <pre className="whitespace-pre-wrap break-all">
            <code>{logContent}</code>
          </pre>
          {timestamp && (
            <div className="mt-2 pt-2 border-t border-xeno-border text-xs text-xeno-border">
              {timestamp}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ThoughtBlock;