/**
 * CyberBadge - Status indicator with subtle glow effect
 * 
 * Variants:
 * - active: Cyber Green (#00FF9D) - Active/Approved
 * - alert: Amber (#FFB000) - Pending/HITL
 * - error: Pink/Red (#FF3366) - Error/Rejected
 * - cloud: Cyan (#00B8FF) - Cloud/Neutral Action
 */

import React from 'react';
import { clsx } from 'clsx';

export type BadgeVariant = 'active' | 'alert' | 'error' | 'cloud';

interface CyberBadgeProps {
  variant: BadgeVariant;
  children: React.ReactNode;
  className?: string;
  pulse?: boolean;
}

export const CyberBadge: React.FC<CyberBadgeProps> = ({
  variant,
  children,
  className,
  pulse = false,
}) => {
  return (
    <span
      className={clsx(
        'cyber-badge',
        variant,
        pulse && 'animate-pulse-slow',
        className
      )}
    >
      {children}
    </span>
  );
};

export default CyberBadge;