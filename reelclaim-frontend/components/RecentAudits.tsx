'use client';

import React, { useEffect, useState } from 'react';
import { getSubmitterAudits, clearSubmitterAudits } from '@/lib/storage';
import { RecentAuditItem } from '@/lib/types';
import { History, RefreshCw, ChevronRight, Shield, Trash2 } from 'lucide-react';

interface RecentAuditsProps {
  onSelectAudit: (auditId: string) => void;
  selectedAuditId?: string;
  refreshTrigger?: number;
}

export function RecentAudits({ onSelectAudit, selectedAuditId, refreshTrigger }: RecentAuditsProps) {
  const [audits, setAudits] = useState<RecentAuditItem[]>([]);

  const loadAudits = () => {
    const data = getSubmitterAudits();
    setAudits(data);
  };

  useEffect(() => {
    loadAudits();
  }, [refreshTrigger]);

  const handleClear = (e: React.MouseEvent) => {
    e.stopPropagation();
    clearSubmitterAudits();
    setAudits([]);
  };

  const getTierBadgeStyle = (tier: string | null | undefined) => {
    switch (tier) {
      case 'VERIFIED':
        return {
          bg: 'var(--verdict-verified-bg)',
          text: 'var(--verdict-verified-text)',
          label: 'VERIFIED',
        };
      case 'LIKELY_TRUE':
        return {
          bg: 'var(--verdict-misleading-bg)',
          text: 'var(--verdict-misleading-text)',
          label: 'LIKELY TRUE',
        };
      case 'CONTRADICTED':
        return {
          bg: 'var(--verdict-false-bg)',
          text: 'var(--verdict-false-text)',
          label: 'CONTRADICTED',
        };
      case 'INSUFFICIENT_EVIDENCE':
      default:
        return {
          bg: 'var(--verdict-unverified-bg)',
          text: 'var(--verdict-unverified-text)',
          label: 'INSUFFICIENT',
        };
    }
  };

  return (
    <div className="mt-6 pt-4 pb-4 border-t" style={{ borderColor: 'var(--border-subtle)' }}>
      <div className="flex items-center justify-between mb-3">
        <div
          className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider"
          style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}
        >
          <History className="w-3.5 h-3.5" />
          <span>Your Audits ({audits.length})</span>
        </div>
        <div className="flex items-center gap-1">
          {audits.length > 0 && (
            <button
              type="button"
              onClick={handleClear}
              className="p-1 rounded hover:opacity-80 transition-opacity"
              title="Clear local session history"
              style={{ color: 'var(--text-muted)' }}
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          )}
          <button
            type="button"
            onClick={loadAudits}
            className="p-1 rounded hover:opacity-80 transition-opacity"
            title="Refresh list"
            style={{ color: 'var(--text-muted)' }}
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {audits.length === 0 ? (
        <p className="text-xs italic" style={{ color: 'var(--text-muted)' }}>
          No local audits yet in this browser session.
        </p>
      ) : (
        <div className="space-y-2 max-h-[280px] overflow-y-auto pr-1">
          {audits.map((item) => {
            const isSelected = selectedAuditId === item.id;
            const createdDate = item.created_at ? new Date(item.created_at).toLocaleDateString() : '';
            const tierStyle = getTierBadgeStyle(item.confidence_tier);

            return (
              <button
                key={item.id}
                type="button"
                onClick={() => onSelectAudit(item.id)}
                className={`w-full text-left p-2.5 rounded border text-xs transition-all flex items-start justify-between gap-2 group ${
                  isSelected ? 'border-primary' : 'hover:border-bright'
                }`}
                style={{
                  backgroundColor: isSelected ? 'var(--bg-elevated)' : 'var(--bg-card)',
                  borderColor: isSelected ? 'var(--border-bright)' : 'var(--border-subtle)',
                }}
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span
                      className="font-mono text-[10px] px-1.5 py-0.5 rounded border"
                      style={{
                        backgroundColor: 'var(--bg)',
                        borderColor: 'var(--border-subtle)',
                        color: 'var(--text-secondary)',
                      }}
                    >
                      {item.id.substring(0, 8)}
                    </span>
                    <span
                      className="font-mono text-[10px] font-bold px-1.5 py-0.5 rounded uppercase"
                      style={{
                        backgroundColor: tierStyle.bg,
                        color: tierStyle.text,
                      }}
                    >
                      {tierStyle.label}
                    </span>
                  </div>
                  <p className="line-clamp-2 leading-relaxed" style={{ color: 'var(--text-primary)' }}>
                    {item.caption}
                  </p>
                  {createdDate && (
                    <span className="text-[10px] mt-1 block" style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                      {createdDate}
                    </span>
                  )}
                </div>
                <ChevronRight className="w-4 h-4 flex-shrink-0 mt-1 opacity-40 group-hover:opacity-100 transition-opacity" style={{ color: 'var(--text-muted)' }} />
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

