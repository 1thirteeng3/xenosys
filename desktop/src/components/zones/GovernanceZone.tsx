/**
 * Governance Zone - HITL Queue
 * 
 * Dense table/grid for Human-in-the-Loop approval requests
 */

import React from 'react';
import { Check, X, AlertTriangle, DollarSign } from 'lucide-react';
import { clsx } from 'clsx';
import { CyberBadge } from '../atomic';

interface HITLRequest {
  id: string;
  timestamp: Date;
  type: 'financial' | 'operational' | 'security';
  description: string;
  amount?: number;
  risk: 'low' | 'medium' | 'high';
  agent: string;
}

const MOCK_REQUESTS: HITLRequest[] = [
  {
    id: '1',
    timestamp: new Date(),
    type: 'financial',
    description: 'Execute payment to vendor for infrastructure costs',
    amount: 2500.00,
    risk: 'high',
    agent: 'FinanceAgent',
  },
  {
    id: '2',
    timestamp: new Date(Date.now() - 60000),
    type: 'operational',
    description: 'Scale up Kubernetes cluster nodes',
    risk: 'medium',
    agent: 'OpsAgent',
  },
  {
    id: '3',
    timestamp: new Date(Date.now() - 120000),
    type: 'security',
    description: 'Revoke access for user john.doe@company.com',
    risk: 'low',
    agent: 'SecurityAgent',
  },
];

export const GovernanceZone: React.FC = () => {
  const handleApprove = (id: string) => {
    console.log('Approved:', id);
    // TODO: Call Tauri command
  };

  const handleReject = (id: string) => {
    console.log('Rejected:', id);
    // TODO: Call Tauri command
  };

  return (
    <div className="p-6">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-xeno-accent-active">Governance Queue</h1>
        <CyberBadge variant="alert" pulse>
          {MOCK_REQUESTS.length} Pending
        </CyberBadge>
      </div>

      {/* Request List */}
      <div className="space-y-3">
        {MOCK_REQUESTS.map((request) => (
          <div
            key={request.id}
            className="panel p-4 hover:border-xeno-accent-alert/50 transition-colors"
          >
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-center gap-3">
                <CyberBadge 
                  variant={request.type === 'financial' ? 'alert' : request.type === 'security' ? 'error' : 'cloud'}
                >
                  {request.type.toUpperCase()}
                </CyberBadge>
                <span className="text-sm text-gray-400">
                  {request.agent}
                </span>
              </div>
              <span className="text-xs text-xeno-border">
                {request.timestamp.toLocaleTimeString()}
              </span>
            </div>

            <p className="text-sm text-gray-200 mb-3">
              {request.description}
            </p>

            {request.amount && (
              <div className="flex items-center gap-2 mb-3 text-xeno-accent-alert">
                <DollarSign className="w-4 h-4" />
                <span className="font-mono font-bold">
                  ${request.amount.toLocaleString()}
                </span>
              </div>
            )}

            <div className="flex items-center justify-between pt-3 border-t border-xeno-border">
              <div className="flex items-center gap-2">
                <AlertTriangle className={clsx(
                  'w-4 h-4',
                  request.risk === 'high' && 'text-xeno-accent-error',
                  request.risk === 'medium' && 'text-xeno-accent-alert',
                  request.risk === 'low' && 'text-xeno-accent-active'
                )} />
                <span className={clsx(
                  'text-xs',
                  request.risk === 'high' && 'text-xeno-accent-error',
                  request.risk === 'medium' && 'text-xeno-accent-alert',
                  request.risk === 'low' && 'text-xeno-accent-active'
                )}>
                  Risk: {request.risk.toUpperCase()}
                </span>
              </div>

              <div className="flex gap-2">
                <button
                  onClick={() => handleReject(request.id)}
                  className="flex items-center gap-1.5 px-3 py-1.5 border border-xeno-accent-error text-xeno-accent-error rounded hover:bg-xeno-accent-error/10 transition-colors text-sm"
                >
                  <X className="w-4 h-4" />
                  Reject
                </button>
                <button
                  onClick={() => handleApprove(request.id)}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-xeno-accent-active text-xeno-bg rounded hover:bg-xeno-accent-active/90 transition-colors text-sm font-bold"
                >
                  <Check className="w-4 h-4" />
                  Approve
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default GovernanceZone;