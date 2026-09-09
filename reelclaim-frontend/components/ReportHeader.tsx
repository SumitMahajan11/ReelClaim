'use client';

import React, { useState } from 'react';
import { CheckResponse, YouTubeMetadata, Fact } from '@/lib/types';
import {
  Info,
  ExternalLink,
  FileText,
  ChevronDown,
  ChevronUp,
  Globe,
  Search,
  Archive,
  Fingerprint,
  CheckCircle2,
  AlertOctagon,
  HelpCircle,
  ShieldCheck,
  Scale
} from 'lucide-react';
import { TrustGauge } from './TrustGauge';

const YoutubeIcon: React.FC<{ className?: string }> = ({ className = "w-3.5 h-3.5" }) => (
  <svg className={className} viewBox="0 0 24 24" fill="currentColor">
    <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
  </svg>
);

interface ReportHeaderProps {
  checkResult: CheckResponse;
  promotedSite: string | null;
  youtubeMetadata?: YouTubeMetadata | null;
  factsGathered?: Fact[];
}

export const ReportHeader: React.FC<ReportHeaderProps> = ({
  checkResult,
  promotedSite,
  youtubeMetadata,
  factsGathered = [],
}) => {
  const [showConsensusWhy, setShowConsensusWhy] = useState<boolean>(false);
  const { confidence_tier, summary_label, score_breakdown, verdicts, source_breakdown } = checkResult;

  // Derive source stats from factsGathered or verdicts
  const siteFactsCount = source_breakdown?.site_crawl ?? factsGathered.filter(f => f.source_name === 'site_crawl').length;
  const searchFactsCount = source_breakdown?.cross_reference ?? factsGathered.filter(f => f.source_name === 'cross_reference').length;
  const waybackFactsCount = source_breakdown?.wayback ?? factsGathered.filter(f => f.source_name === 'wayback').length;
  const whoisFactsCount = source_breakdown?.whois ?? factsGathered.filter(f => f.source_name === 'whois').length;

  const totalContributingSources = [
    siteFactsCount > 0,
    searchFactsCount > 0,
    waybackFactsCount > 0,
    whoisFactsCount > 0
  ].filter(Boolean).length;

  // Check agreement across sources
  const confirmedSources = Array.from(
    new Set(verdicts.filter(v => v.verdict === 'confirmed' && v.evidence_source).map(v => v.evidence_source!))
  );
  const contradictedSources = Array.from(
    new Set(verdicts.filter(v => v.verdict === 'contradicted' && v.evidence_source).map(v => v.evidence_source!))
  );

  const getTierRuleExplanation = () => {
    switch (confidence_tier) {
      case 'VERIFIED':
        return {
          title: 'Rule: Multi-Source Independent Corroboration Met',
          explanation: 'At least one claim is verified by independent, non-self-attested 3rd-party evidence (search/review/registry) with zero contradictions found.',
          accent: 'var(--verdict-verified-text)',
          icon: ShieldCheck,
        };
      case 'LIKELY_TRUE':
        return {
          title: 'Rule: Self-Attestation Cap Applied',
          explanation: 'Claims matched published statements on the promoter\'s own site, but no independent 3rd-party source verified them. ReelClaim caps purely self-attested claims at LIKELY_TRUE to prevent gaming.',
          accent: 'var(--verdict-misleading-text)',
          icon: CheckCircle2,
        };
      case 'CONTRADICTED':
        return {
          title: 'Rule: Contradiction Takes Precedence',
          explanation: 'One or more promotional claims directly contradict published legal terms, pricing pages, or independent review records.',
          accent: 'var(--verdict-false-text)',
          icon: AlertOctagon,
        };
      case 'INSUFFICIENT_EVIDENCE':
      default:
        return {
          title: 'Rule: Insufficient Corroborating Data',
          explanation: 'Neither crawled website pages nor external registries provided verifiable facts regarding the promotional claims.',
          accent: 'var(--verdict-unverified-text)',
          icon: HelpCircle,
        };
    }
  };

  const ruleInfo = getTierRuleExplanation();
  const RuleIcon = ruleInfo.icon;

  return (
    <div
      className="w-full p-5 space-y-5 border-b rounded-xl"
      style={{
        backgroundColor: 'var(--bg-card)',
        borderColor: 'var(--border-subtle)',
      }}
    >
      {/* Optional YouTube Video Ingest Card */}
      {youtubeMetadata && (
        <div
          className="p-3.5 rounded-xl border flex flex-col sm:flex-row items-start gap-3.5 text-xs"
          style={{
            backgroundColor: 'var(--bg-elevated)',
            borderColor: 'var(--border-med)',
          }}
        >
          {youtubeMetadata.thumbnail_url && (
            <div className="relative w-full sm:w-28 h-20 rounded-lg overflow-hidden flex-shrink-0 bg-black/40 border border-border-subtle">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={youtubeMetadata.thumbnail_url}
                alt={youtubeMetadata.title || 'YouTube Short'}
                className="w-full h-full object-cover"
              />
              <span className="absolute bottom-1 right-1 px-1 py-0.2 rounded font-mono text-[9px] bg-red-600 text-white font-bold">
                SHORT
              </span>
            </div>
          )}
          <div className="space-y-1 min-w-0 flex-1">
            <div className="flex items-center gap-1.5 text-red-400 font-semibold text-[11px] uppercase tracking-wider">
              <YoutubeIcon className="w-3.5 h-3.5" />
              <span>Auto-Ingested YouTube Short</span>
            </div>
            <a
              href={youtubeMetadata.video_url}
              target="_blank"
              rel="noopener noreferrer"
              className="font-bold text-sm hover:underline line-clamp-1 block"
              style={{ color: 'var(--text-primary)' }}
            >
              {youtubeMetadata.title || youtubeMetadata.video_url}
            </a>
            {youtubeMetadata.channel_title && (
              <p className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
                Channel: <span className="font-medium" style={{ color: 'var(--text-secondary)' }}>{youtubeMetadata.channel_title}</span>
              </p>
            )}
            {youtubeMetadata.transcript && (
              <details className="pt-1 text-[11px]">
                <summary className="cursor-pointer font-medium hover:opacity-80 transition-opacity flex items-center gap-1" style={{ color: 'var(--text-accent)' }}>
                  <FileText className="w-3 h-3" />
                  <span>View extracted audio transcript ({youtubeMetadata.transcript.length} chars)</span>
                </summary>
                <p className="mt-1.5 p-2 rounded bg-black/20 border border-border-subtle font-mono text-[10px] leading-relaxed max-h-28 overflow-y-auto" style={{ color: 'var(--text-secondary)' }}>
                  {youtubeMetadata.transcript}
                </p>
              </details>
            )}
          </div>
        </div>
      )}

      {/* Target Site & Confidence Tier Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        {/* Left: Target site info */}
        <div className="space-y-1 min-w-0 flex-1">
          <span
            className="text-[10px] uppercase tracking-widest"
            style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}
          >
            Audited Target Site
          </span>
          <div className="flex items-center gap-1.5 min-w-0">
            <ExternalLink className="w-3.5 h-3.5 flex-shrink-0" style={{ color: 'var(--text-muted)' }} />
            <span
              className="truncate text-sm font-semibold"
              style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}
            >
              {promotedSite || 'Site URL'}
            </span>
          </div>
          {summary_label && (
            <p className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>
              {summary_label}
            </p>
          )}
        </div>

        {/* Right: Confidence Tier Badge */}
        <div
          className="border-l-0 sm:border-l sm:pl-5 pt-2 sm:pt-0 flex-shrink-0"
          style={{ borderColor: 'var(--border-subtle)' }}
        >
          <TrustGauge tier={confidence_tier} />
        </div>
      </div>

      {/* Score Breakdown Row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="flex items-center gap-2">
          <span className="text-sm font-bold" style={{ fontFamily: 'var(--font-mono)', color: 'var(--verdict-verified-text)' }}>
            {score_breakdown?.confirmed_count ?? 0}
          </span>
          <div className="text-[10px] uppercase tracking-wider font-semibold" style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
            Confirmed
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-sm font-bold" style={{ fontFamily: 'var(--font-mono)', color: 'var(--verdict-misleading-text)' }}>
            {score_breakdown?.partial_count ?? 0}
          </span>
          <div className="text-[10px] uppercase tracking-wider font-semibold" style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
            Partial
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-sm font-bold" style={{ fontFamily: 'var(--font-mono)', color: 'var(--verdict-false-text)' }}>
            {score_breakdown?.contradicted_count ?? 0}
          </span>
          <div className="text-[10px] uppercase tracking-wider font-semibold" style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
            Contradicted
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-sm font-bold" style={{ fontFamily: 'var(--font-mono)', color: 'var(--verdict-unverified-text)' }}>
            {score_breakdown?.not_found_count ?? 0}
          </span>
          <div className="text-[10px] uppercase tracking-wider font-semibold" style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
            Unverified
          </div>
        </div>
      </div>

      {/* Expandable "Why this tier?" Consensus Drawer Toggle */}
      <div className="pt-1">
        <button
          type="button"
          onClick={() => setShowConsensusWhy(!showConsensusWhy)}
          className="w-full flex items-center justify-between p-2.5 rounded-lg border text-xs font-semibold transition-all cursor-pointer hover:opacity-90"
          style={{
            backgroundColor: 'var(--bg-elevated)',
            borderColor: 'var(--border-subtle)',
            color: 'var(--text-primary)',
          }}
        >
          <div className="flex items-center gap-2">
            <Scale className="w-3.5 h-3.5" style={{ color: ruleInfo.accent }} />
            <span>Why this confidence tier? Source consensus matrix ({totalContributingSources || 4} sources evaluated)</span>
          </div>
          {showConsensusWhy ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>

        {showConsensusWhy && (
          <div
            className="mt-3 p-4 rounded-xl border space-y-4 animate-fadeIn text-xs"
            style={{
              backgroundColor: 'var(--bg-elevated)',
              borderColor: 'var(--border-subtle)',
            }}
          >
            {/* Rule Rationale Box */}
            <div className="flex items-start gap-2.5 p-3 rounded-lg border bg-black/10 border-border-subtle">
              <RuleIcon className="w-4 h-4 flex-shrink-0 mt-0.5" style={{ color: ruleInfo.accent }} />
              <div className="space-y-1">
                <p className="font-bold text-[11px] uppercase tracking-wider font-mono" style={{ color: ruleInfo.accent }}>
                  {ruleInfo.title}
                </p>
                <p className="text-xs leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                  {ruleInfo.explanation}
                </p>
              </div>
            </div>

            {/* Source Contribution & Agreement Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5">
              {/* Source 1: Site Crawl */}
              <div
                className="p-3 rounded-lg border flex flex-col justify-between space-y-2"
                style={{
                  backgroundColor: 'var(--bg-card)',
                  borderColor: 'var(--border-subtle)',
                }}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5 font-semibold text-[11px]" style={{ color: 'var(--text-primary)' }}>
                    <Globe className="w-3.5 h-3.5 text-blue-400" />
                    <span>Site Crawl</span>
                  </div>
                  <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-black/20 text-text-muted">
                    {siteFactsCount} facts
                  </span>
                </div>
                <div className="text-[10px] space-y-0.5">
                  <span className="text-muted block">Weight: Low-Med (Self-Attested)</span>
                  <span className="font-medium" style={{ color: siteFactsCount > 0 ? 'var(--verdict-verified-text)' : 'var(--text-muted)' }}>
                    {siteFactsCount > 0 ? '✓ Pages & terms crawled' : 'No crawl data'}
                  </span>
                </div>
              </div>

              {/* Source 2: Cross Reference Search */}
              <div
                className="p-3 rounded-lg border flex flex-col justify-between space-y-2"
                style={{
                  backgroundColor: 'var(--bg-card)',
                  borderColor: 'var(--border-subtle)',
                }}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5 font-semibold text-[11px]" style={{ color: 'var(--text-primary)' }}>
                    <Search className="w-3.5 h-3.5 text-emerald-400" />
                    <span>3rd-Party Reviews</span>
                  </div>
                  <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-black/20 text-text-muted">
                    {searchFactsCount} facts
                  </span>
                </div>
                <div className="text-[10px] space-y-0.5">
                  <span className="text-muted block">Weight: High (Independent)</span>
                  <span className="font-medium" style={{ color: searchFactsCount > 0 ? 'var(--verdict-verified-text)' : 'var(--text-muted)' }}>
                    {searchFactsCount > 0 ? '✓ Web & scam query checked' : 'No 3rd-party query data'}
                  </span>
                </div>
              </div>

              {/* Source 3: Wayback Archive */}
              <div
                className="p-3 rounded-lg border flex flex-col justify-between space-y-2"
                style={{
                  backgroundColor: 'var(--bg-card)',
                  borderColor: 'var(--border-subtle)',
                }}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5 font-semibold text-[11px]" style={{ color: 'var(--text-primary)' }}>
                    <Archive className="w-3.5 h-3.5 text-purple-400" />
                    <span>Wayback History</span>
                  </div>
                  <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-black/20 text-text-muted">
                    {waybackFactsCount} facts
                  </span>
                </div>
                <div className="text-[10px] space-y-0.5">
                  <span className="text-muted block">Weight: Medium (Historical)</span>
                  <span className="font-medium" style={{ color: waybackFactsCount > 0 ? 'var(--verdict-verified-text)' : 'var(--text-muted)' }}>
                    {waybackFactsCount > 0 ? '✓ Web archive checked' : 'No snapshots'}
                  </span>
                </div>
              </div>

              {/* Source 4: WHOIS Registry */}
              <div
                className="p-3 rounded-lg border flex flex-col justify-between space-y-2"
                style={{
                  backgroundColor: 'var(--bg-card)',
                  borderColor: 'var(--border-subtle)',
                }}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5 font-semibold text-[11px]" style={{ color: 'var(--text-primary)' }}>
                    <Fingerprint className="w-3.5 h-3.5 text-amber-400" />
                    <span>WHOIS Registry</span>
                  </div>
                  <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-black/20 text-text-muted">
                    {whoisFactsCount} facts
                  </span>
                </div>
                <div className="text-[10px] space-y-0.5">
                  <span className="text-muted block">Weight: High (Registry)</span>
                  <span className="font-medium" style={{ color: whoisFactsCount > 0 ? 'var(--verdict-verified-text)' : 'var(--text-muted)' }}>
                    {whoisFactsCount > 0 ? '✓ Domain age verified' : 'No WHOIS record'}
                  </span>
                </div>
              </div>
            </div>

            {/* Source Consensus Statement */}
            <div className="flex items-center justify-between pt-1 border-t border-border-subtle text-[11px]" style={{ color: 'var(--text-secondary)' }}>
              <div>
                <span>Source agreement: </span>
                {contradictedSources.length > 0 ? (
                  <span className="font-bold text-red-400">Contradictions detected in {contradictedSources.join(', ')}</span>
                ) : confirmedSources.length > 1 ? (
                  <span className="font-bold text-emerald-400">Multiple sources ({confirmedSources.join(' & ')}) corroborating claims</span>
                ) : confirmedSources.length === 1 ? (
                  <span className="font-bold text-amber-400">Single source ({confirmedSources[0]}) supporting claims</span>
                ) : (
                  <span className="italic text-muted">No agreement reached across sources</span>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Disclaimer */}
      <div
        className="flex items-start gap-2 p-2.5 rounded border text-xs leading-relaxed"
        style={{
          backgroundColor: 'var(--bg-elevated)',
          borderColor: 'var(--border-subtle)',
          color: 'var(--text-secondary)',
        }}
      >
        <Info className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" style={{ color: 'var(--text-muted)' }} />
        <span>
          <strong style={{ color: 'var(--text-primary)' }}>Disclaimer:</strong>{' '}
          This checks the promoted site&apos;s published claims and independent sources — it does not verify offline legitimacy.
        </span>
      </div>
    </div>
  );
};
