'use client';

import React, { useState, useEffect } from 'react';
import { AuditForm } from '@/components/AuditForm';
import { ReportHeader } from '@/components/ReportHeader';
import { CrawlStatusBanner } from '@/components/CrawlStatusBanner';
import { VerdictCard } from '@/components/VerdictCard';
import { EmptyState } from '@/components/EmptyState';
import { CaseIdBanner } from '@/components/CaseIdBanner';
import { RecentAudits } from '@/components/RecentAudits';
import { FullAuditResponse, ProgressStep } from '@/lib/types';
import { auditReel, fetchAuditById } from '@/lib/api';
import { saveSubmitterAudit } from '@/lib/storage';
import { RotateCcw, FileText, ShieldAlert } from 'lucide-react';
import { DeskLampToggle } from '@/components/DeskLampToggle';

export default function Home() {
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [currentStep, setCurrentStep] = useState<ProgressStep>('idle');
  const [retryDetails, setRetryDetails] = useState<{ retryAttempt?: number; maxRetries?: number; nextDelaySec?: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [auditResult, setAuditResult] = useState<FullAuditResponse | null>(null);
  const [refreshRecentTrigger, setRefreshRecentTrigger] = useState<number>(0);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search);
      const auditId = params.get('audit');
      if (auditId) {
        handleSelectAudit(auditId);
      }
    }
  }, []);

  const handleAuditSubmit = async (params: { caption?: string; videoUrl?: string; overrideUrl?: string; apiKey?: string; youtubeApiKey?: string }) => {
    setIsLoading(true);
    setError(null);
    setAuditResult(null);
    setRetryDetails(null);
    setCurrentStep('extracting');

    try {
      const response = await auditReel(
        {
          caption: params.caption,
          video_url: params.videoUrl,
          override_url: params.overrideUrl,
          gemini_api_key: params.apiKey,
          youtube_api_key: params.youtubeApiKey,
        },
        undefined,
        undefined,
        (step, details) => {
          setCurrentStep(step);
          if (details) setRetryDetails(details);
        }
      );
      setAuditResult(response);
      saveSubmitterAudit(response);
      setCurrentStep('complete');
      setRefreshRecentTrigger((prev) => prev + 1);

      if (response.id && typeof window !== 'undefined') {
        window.history.pushState({}, '', `?audit=${response.id}`);
      }
    } catch (err: any) {
      setError(err.message || 'Audit request failed');
      setCurrentStep('error');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelectAudit = async (auditId: string) => {
    setIsLoading(true);
    setError(null);
    setAuditResult(null);
    setCurrentStep('extracting');

    try {
      const data = await fetchAuditById(auditId);
      setAuditResult(data);
      setCurrentStep('complete');
      if (typeof window !== 'undefined') {
        window.history.pushState({}, '', `?audit=${auditId}`);
      }
    } catch (err: any) {
      setError(err.message || `Audit record #${auditId} not found.`);
      setCurrentStep('error');
    } finally {
      setIsLoading(false);
    }
  };

  const handleReset = () => {
    setAuditResult(null);
    setError(null);
    setRetryDetails(null);
    setCurrentStep('idle');
    if (typeof window !== 'undefined') {
      window.history.pushState({}, '', window.location.pathname);
    }
  };

  return (
    <main
      className="min-h-screen flex flex-col"
      style={{ backgroundColor: 'var(--bg)', color: 'var(--text-primary)' }}
    >
      {/* ── Top Navigation Bar ── */}
      <header
        className="w-full border-b sticky top-0 z-50"
        style={{
          backgroundColor: 'var(--bg-card)',
          borderColor: 'var(--border-subtle)',
        }}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3 flex items-center justify-between">
          {/* Logo: serif "R" in thin circle + wordmark */}
          <div className="flex items-center gap-3">
            <div
              className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0"
              style={{
                border: '1.5px solid var(--border-bright)',
                backgroundColor: 'transparent',
              }}
            >
              <span
                className="font-serif font-bold text-base leading-none select-none"
                style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-serif)' }}
              >
                R
              </span>
            </div>

            <div>
              <span
                className="text-sm leading-none"
                style={{ fontFamily: 'var(--font-serif)' }}
              >
                <span className="font-bold" style={{ color: 'var(--text-primary)' }}>ReelClaim</span>
                <span className="font-normal" style={{ color: 'var(--text-muted)' }}> — case ledger</span>
              </span>
            </div>
          </div>

          {/* Right controls */}
          <div className="flex items-center gap-2.5">
            <DeskLampToggle />

            {auditResult && (
              <button
                type="button"
                onClick={handleReset}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-semibold border cursor-pointer hover:opacity-80"
                style={{
                  backgroundColor: 'var(--bg-elevated)',
                  borderColor: 'var(--border-subtle)',
                  color: 'var(--text-secondary)',
                  fontFamily: 'var(--font-mono)',
                }}
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>New Audit</span>
              </button>
            )}

            <span
              className="text-[10px] px-2 py-0.5 rounded border hidden sm:inline-block"
              style={{
                fontFamily: 'var(--font-mono)',
                backgroundColor: 'transparent',
                borderColor: 'var(--border-subtle)',
                color: 'var(--text-muted)',
              }}
            >
              v4.0
            </span>
          </div>
        </div>
      </header>

      {/* ── Main Two-Panel Desk Layout ── */}
      <div className="flex-1 max-w-7xl mx-auto w-full">
        <div className="grid grid-cols-1 lg:grid-cols-[380px_1fr] min-h-[calc(100vh-120px)]">

          {/* LEFT PANEL: Intake Desk & Recent Audits */}
          <aside
            className="w-full lg:sticky lg:top-14 lg:self-start lg:h-[calc(100vh-56px)] lg:overflow-y-auto panel-divider"
            style={{ padding: '1.5rem 1.5rem 1.5rem 1rem' }}
          >
            <AuditForm
              onSubmit={handleAuditSubmit}
              isLoading={isLoading}
              currentStep={currentStep}
              retryDetails={retryDetails}
              error={error}
            />

            <RecentAudits
              onSelectAudit={handleSelectAudit}
              selectedAuditId={auditResult?.id}
              refreshTrigger={refreshRecentTrigger}
            />
          </aside>

          {/* RIGHT PANEL: Results Ledger */}
          <section
            className="w-full min-w-0"
            style={{ padding: '1.5rem 1.5rem 1.5rem 1.5rem' }}
          >
            {auditResult ? (
              <div id="audit-report-container" className="space-y-5 animate-fadeIn">
                {/* Case ID Banner if audit was persisted */}
                {auditResult.id && (
                  <CaseIdBanner auditId={auditResult.id} />
                )}

                {/* Report Header with trust gauge */}
                {auditResult.check_result && (
                  <ReportHeader
                    checkResult={auditResult.check_result}
                    promotedSite={auditResult.promoted_site}
                    youtubeMetadata={auditResult.youtube_metadata}
                    factsGathered={auditResult.facts_gathered}
                  />
                )}

                {/* Crawl Status Notice */}
                <CrawlStatusBanner
                  crawlStatus={auditResult.crawl_status}
                  promotedSite={auditResult.promoted_site}
                  onRetry={handleReset}
                />

                {/* Claim Entries or Edge States */}
                {auditResult.claims.length === 0 ? (
                  <EmptyState type="zero_claims" onReset={handleReset} />
                ) : auditResult.check_result ? (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <h3
                        className="text-xs font-bold uppercase tracking-widest flex items-center gap-1.5"
                        style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}
                      >
                        <FileText className="w-3.5 h-3.5" />
                        Ledger — {auditResult.check_result?.verdicts?.length ?? auditResult.claims.length} entries
                      </h3>
                    </div>

                    <div className="space-y-3">
                      {(auditResult.check_result?.verdicts || []).map((item, idx) => (
                        <VerdictCard
                          key={idx}
                          verdictItem={item}
                          index={idx}
                          auditId={auditResult.id}
                          submitterToken={auditResult.submitter_token}
                        />
                      ))}
                    </div>
                  </div>
                ) : auditResult.crawl_status === 'blocked' ? (
                  <EmptyState
                    type="blocked_site"
                    message="This site blocked our verification crawler (WAF / bot detection wall)."
                  />
                ) : auditResult.crawl_status === 'failed' ? (
                  <EmptyState
                    type="network_error"
                    message="We couldn't reach or read this site. Try again."
                    onReset={handleReset}
                  />
                ) : null}
              </div>
            ) : currentStep === 'error' ? (
              <EmptyState
                type="network_error"
                message={error || undefined}
                onReset={handleReset}
              />
            ) : (
              /* Idle / empty ledger state */
              <div
                className="flex flex-col items-center justify-center min-h-[420px] text-center space-y-4 py-16"
              >
                <div
                  className="w-12 h-12 rounded-full flex items-center justify-center"
                  style={{ border: '1.5px solid var(--border-med)', backgroundColor: 'transparent' }}
                >
                  <ShieldAlert
                    className="w-5 h-5"
                    style={{ color: 'var(--text-muted)' }}
                  />
                </div>
                <div className="space-y-1.5 max-w-sm">
                  <h3
                    className="text-base font-bold"
                    style={{ fontFamily: 'var(--font-serif)', color: 'var(--text-primary)' }}
                  >
                    Ledger Ready
                  </h3>
                  <p className="text-xs leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                    Submit a reel caption in the intake desk to extract claims, crawl evidence, and output the verification ledger.
                  </p>
                </div>
              </div>
            )}
          </section>

        </div>
      </div>

      {/* ── Audit Trail Footer ── */}
      <footer
        className="w-full border-t py-3.5 mt-auto"
        style={{
          backgroundColor: 'var(--bg-card)',
          borderColor: 'var(--border-subtle)',
        }}
      >
        <div
          className="max-w-7xl mx-auto px-4 sm:px-6 flex flex-col sm:flex-row items-center justify-between gap-2 text-[11px]"
          style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}
        >
          <div className="flex items-center gap-2">
            <span
              className="w-1.5 h-1.5 rounded-full inline-block"
              style={{ backgroundColor: 'var(--verdict-verified-text)' }}
            />
            <span>ReelClaim Core Engine v4.0 · Persistent Ledger Mode</span>
          </div>
          <div className="flex items-center gap-2">
            <span>audit trail stamp</span>
            <span
              suppressHydrationWarning
              className="px-1.5 py-0.5 rounded"
              style={{
                backgroundColor: 'var(--bg-elevated)',
                borderColor: 'var(--border-subtle)',
                color: 'var(--text-secondary)',
                border: '1px solid var(--border-subtle)',
              }}
            >
              {mounted ? `${new Date().toISOString().replace('T', ' ').slice(0, 19)} UTC` : '2026-08-29 11:34:00 UTC'}
            </span>
          </div>
        </div>
      </footer>
    </main>
  );
}
