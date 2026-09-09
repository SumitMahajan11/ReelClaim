'use client';

import React from 'react';
import { ConfidenceTier } from '@/lib/types';
import { ShieldCheck, CheckCircle2, AlertOctagon, HelpCircle, AlertTriangle } from 'lucide-react';

interface TrustGaugeProps {
  tier?: ConfidenceTier | null;
  score?: number | null; // Optional fallback compatibility
  status?: string | null;
  className?: string;
}

export const TrustGauge: React.FC<TrustGaugeProps> = ({
  tier,
  status,
  className = '',
}) => {
  const getTierConfig = () => {
    if (status === 'blocked' || status === 'failed') {
      return {
        label: 'CRAWL BLOCKED',
        sublabel: 'Could not access site',
        color: 'var(--verdict-false-text)',
        bg: 'var(--verdict-false-bg)',
        border: 'var(--verdict-false-border)',
        icon: AlertTriangle,
      };
    }

    switch (tier) {
      case 'VERIFIED':
        return {
          label: 'VERIFIED',
          sublabel: '3rd-Party Corroborated',
          color: 'var(--verdict-verified-text)',
          bg: 'var(--verdict-verified-bg)',
          border: 'var(--verdict-verified-border)',
          icon: ShieldCheck,
        };
      case 'LIKELY_TRUE':
        return {
          label: 'LIKELY TRUE',
          sublabel: 'Promoter Self-Attested',
          color: 'var(--verdict-misleading-text)',
          bg: 'var(--verdict-misleading-bg)',
          border: 'var(--verdict-misleading-border)',
          icon: CheckCircle2,
        };
      case 'CONTRADICTED':
        return {
          label: 'CONTRADICTED',
          sublabel: 'Contradicted by Evidence',
          color: 'var(--verdict-false-text)',
          bg: 'var(--verdict-false-bg)',
          border: 'var(--verdict-false-border)',
          icon: AlertOctagon,
        };
      case 'INSUFFICIENT_EVIDENCE':
      default:
        return {
          label: 'INSUFFICIENT EVIDENCE',
          sublabel: 'No Verifiable Data Found',
          color: 'var(--verdict-unverified-text)',
          bg: 'var(--verdict-unverified-bg)',
          border: 'var(--verdict-unverified-border)',
          icon: HelpCircle,
        };
    }
  };

  const config = getTierConfig();
  const IconComponent = config.icon;

  return (
    <div className={`flex items-center gap-3.5 select-none ${className}`}>
      {/* Tier Badge Box */}
      <div
        className="px-4 py-2.5 rounded-lg border-2 flex items-center gap-2.5 transition-all shadow-sm"
        style={{
          backgroundColor: config.bg,
          borderColor: config.border,
          color: config.color,
        }}
      >
        <IconComponent className="w-5 h-5 flex-shrink-0 animate-fadeIn" />
        <div className="flex flex-col">
          <span
            className="text-[10px] uppercase tracking-wider font-semibold font-mono opacity-80"
          >
            Confidence Tier
          </span>
          <span
            className="text-sm sm:text-base font-extrabold tracking-wide font-mono uppercase"
          >
            {config.label}
          </span>
          <span className="text-[10px] font-medium opacity-90">
            {config.sublabel}
          </span>
        </div>
      </div>
    </div>
  );
};

