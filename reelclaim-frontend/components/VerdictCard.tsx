'use client';

import React, { useState } from 'react';
import { ClaimVerdict, FeedbackRequest } from '@/lib/types';
import { submitAuditFeedback } from '@/lib/api';
import { ExternalLink, ChevronDown, ChevronUp, Flag, Check, AlertCircle } from 'lucide-react';

interface VerdictCardProps {
  verdictItem: ClaimVerdict;
  index: number;
  auditId?: string;
  submitterToken?: string | null;
}

export const VerdictCard: React.FC<VerdictCardProps> = ({
  verdictItem,
  index,
  auditId,
  submitterToken,
}) => {
  const [showReasoning, setShowReasoning] = useState<boolean>(false);
  const [showFeedback, setShowFeedback] = useState<boolean>(false);
  const [feedbackType, setFeedbackType] = useState<FeedbackRequest['feedback_type']>('wrong_verdict');
  const [expectedVerdict, setExpectedVerdict] = useState<string>('confirmed');
  const [notes, setNotes] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [feedbackSuccess, setFeedbackSuccess] = useState<boolean>(false);
  const [feedbackError, setFeedbackError] = useState<string | null>(null);

  const { claim_text, verdict, evidence_text, source_url, reasoning } = verdictItem;

  // Format index as 01, 02, 03... using IBM Plex Mono
  const formattedIndex = String(index + 1).padStart(2, '0');

  // Helper to extract domain name cleanly from source_url
  const getDomainName = (url: string | null): string => {
    if (!url) return 'target domain';
    try {
      const parsed = new URL(url);
      return parsed.hostname.replace(/^www\./, '');
    } catch {
      return url;
    }
  };

  // Map API verdict to display label, colors, border accent, and stamp rotation angle
  const getVerdictDetails = () => {
    switch (verdict) {
      case 'confirmed':
        return {
          label: 'VERIFIED',
          stampColor: 'var(--verdict-verified-text)',
          stampBorder: 'var(--verdict-verified-border)',
          stampBg: 'var(--verdict-verified-bg)',
          leftAccentBorder: 'var(--verdict-verified-text)',
          rotateAngle: '-4deg',
        };
      case 'contradicted':
        return {
          label: 'CONTRADICTED',
          stampColor: 'var(--verdict-false-text)',
          stampBorder: 'var(--verdict-false-border)',
          stampBg: 'var(--verdict-false-bg)',
          leftAccentBorder: 'var(--verdict-false-text)',
          rotateAngle: '6deg',
        };
      case 'partial':
        return {
          label: 'PARTIAL',
          stampColor: 'var(--verdict-misleading-text)',
          stampBorder: 'var(--verdict-misleading-border)',
          stampBg: 'var(--verdict-misleading-bg)',
          leftAccentBorder: 'var(--verdict-misleading-text)',
          rotateAngle: '-3deg',
        };
      case 'not_found':
      default:
        return {
          label: 'UNVERIFIED',
          stampColor: 'var(--verdict-unverified-text)',
          stampBorder: 'var(--verdict-unverified-border)',
          stampBg: 'var(--verdict-unverified-bg)',
          leftAccentBorder: 'var(--border-bright)',
          rotateAngle: '5deg',
        };
    }
  };

  const handleFeedbackSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!auditId) {
      setFeedbackError('Feedback is only available for persisted audits.');
      return;
    }

    setIsSubmitting(true);
    setFeedbackError(null);

    try {
      await submitAuditFeedback(
        auditId,
        {
          claim_index: index,
          feedback_type: feedbackType,
          expected_verdict: expectedVerdict,
          user_notes: notes.trim(),
        },
        submitterToken
      );
      setFeedbackSuccess(true);
    } catch (err: any) {
      setFeedbackError(err.message || 'Failed to submit feedback.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const details = getVerdictDetails();
  const domainName = getDomainName(source_url);

  return (
    <div
      className="w-full rounded-xl border p-4.5 sm:p-5 transition-all space-y-3 shadow-sm relative overflow-hidden"
      style={{
        backgroundColor: 'var(--bg-card)',
        borderColor: 'var(--border-subtle)',
        boxShadow: 'var(--shadow-card)',
      }}
    >
      {/* Top Main Section: Flex layout with entry content on left & stamp badge on right */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        
        {/* Left Column: Numbered Entry + Claim Content + Left Accent Border */}
        <div className="flex items-start gap-3.5 flex-1 min-w-0">
          {/* Entry Number (01, 02, ...) in IBM Plex Mono */}
          <span
            className="text-xs sm:text-sm font-bold tracking-wider pt-0.5 select-none flex-shrink-0"
            style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}
          >
            {formattedIndex}
          </span>

          {/* Claim Text and Evidence block with left border accent */}
          <div
            className="border-l-2 pl-3.5 space-y-1.5 flex-1 min-w-0"
            style={{ borderColor: details.leftAccentBorder }}
          >
            {/* Main Claim Text */}
            <p className="text-sm font-medium leading-relaxed" style={{ color: 'var(--text-primary)' }}>
              {claim_text}
            </p>

            {/* Short Evidence Line + Source Link + Source Attribution Badge */}
            <div className="flex flex-wrap items-center gap-1.5 text-xs" style={{ color: 'var(--text-secondary)' }}>
              {verdictItem.evidence_source && (
                <span
                  className="font-mono text-[10px] px-1.5 py-0.5 rounded border uppercase tracking-wider font-semibold"
                  style={{
                    backgroundColor: verdictItem.is_self_attested ? 'var(--bg-elevated)' : 'var(--verdict-verified-bg)',
                    color: verdictItem.is_self_attested ? 'var(--text-muted)' : 'var(--verdict-verified-text)',
                    borderColor: 'var(--border-subtle)',
                  }}
                >
                  {verdictItem.evidence_source === 'cross_reference'
                    ? '3rd-Party Review'
                    : verdictItem.evidence_source === 'wayback'
                    ? 'Wayback History'
                    : verdictItem.evidence_source === 'whois'
                    ? 'Domain Registry'
                    : 'Site Crawl (Self-Attested)'}
                </span>
              )}

              {evidence_text ? (
                <span>
                  &ldquo;{evidence_text}&rdquo; —{' '}
                  <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>
                    {domainName}
                  </span>
                </span>
              ) : (
                <span className="italic text-[11px]" style={{ color: 'var(--text-muted)' }}>
                  No matching claim found on {domainName}
                </span>
              )}

              {source_url && (
                <a
                  href={source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-[11px] font-medium hover:underline ml-1"
                  style={{ color: 'var(--text-accent)' }}
                >
                  <span>Link</span>
                  <ExternalLink className="w-3 h-3" />
                </a>
              )}
            </div>
          </div>
        </div>

        {/* Right Column: Rotated Stamp Badge with "thud" Animation */}
        <div className="self-end sm:self-center flex-shrink-0 pt-1 sm:pt-0">
          <div
            className="animate-stamp-thud inline-block px-3 py-1.5 rounded border-2 text-xs font-black tracking-widest uppercase shadow-sm select-none"
            style={{
              fontFamily: 'var(--font-mono)',
              color: details.stampColor,
              borderColor: details.stampBorder,
              backgroundColor: details.stampBg,
              ['--stamp-angle' as any]: details.rotateAngle,
              transform: `rotate(${details.rotateAngle})`,
            }}
          >
            {details.label}
          </div>
        </div>

      </div>

      {/* Action Bar: "Why this verdict?" and "Flag as incorrect" */}
      <div className="pt-2 border-t flex items-center justify-between gap-3 text-xs" style={{ borderColor: 'var(--border-subtle)' }}>
        <button
          type="button"
          onClick={() => setShowReasoning(!showReasoning)}
          className="inline-flex items-center gap-1 transition-colors cursor-pointer font-medium hover:opacity-80"
          style={{ color: 'var(--text-muted)' }}
        >
          <span>Why this verdict?</span>
          {showReasoning ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        </button>

        <button
          type="button"
          onClick={() => setShowFeedback(!showFeedback)}
          className="inline-flex items-center gap-1 transition-colors cursor-pointer text-[11px] font-medium hover:opacity-80"
          style={{ color: feedbackSuccess ? 'var(--verdict-verified-text)' : 'var(--text-muted)' }}
        >
          <Flag className="w-3 h-3" />
          <span>{feedbackSuccess ? 'Feedback Submitted ✓' : 'Flag as wrong'}</span>
        </button>
      </div>

      {/* Expandable Reasoning */}
      {showReasoning && (
        <div
          className="mt-2 p-3 rounded-lg border text-xs leading-relaxed animate-fadeIn"
          style={{
            backgroundColor: 'var(--bg-elevated)',
            borderColor: 'var(--border-subtle)',
            color: 'var(--text-secondary)',
          }}
        >
          <span className="font-semibold" style={{ color: 'var(--text-secondary)' }}>Reasoning: </span>
          {reasoning}
        </div>
      )}

      {/* Expandable Feedback Form */}
      {showFeedback && (
        <div
          className="mt-2 p-3.5 rounded-xl border text-xs space-y-3 animate-fadeIn"
          style={{
            backgroundColor: 'var(--bg-elevated)',
            borderColor: 'var(--border-subtle)',
          }}
        >
          {feedbackSuccess ? (
            <div className="flex items-center gap-2 p-2.5 rounded border border-emerald-500/30 bg-emerald-500/10 text-emerald-400">
              <Check className="w-4 h-4 flex-shrink-0" />
              <span>Feedback recorded! Your correction will help improve ReelClaim&apos;s accuracy benchmark.</span>
            </div>
          ) : (
            <form onSubmit={handleFeedbackSubmit} className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="font-bold text-[11px] uppercase tracking-wider font-mono" style={{ color: 'var(--text-primary)' }}>
                  Flag Verdict #{formattedIndex}
                </span>
                <span className="text-[10px] text-muted">Owner Session Auth</span>
              </div>

              {feedbackError && (
                <div className="flex items-center gap-1.5 p-2 rounded border border-red-500/30 bg-red-500/10 text-red-400 text-[11px]">
                  <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />
                  <span>{feedbackError}</span>
                </div>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                <div>
                  <label className="block text-[10px] uppercase tracking-wider font-mono font-semibold mb-1" style={{ color: 'var(--text-muted)' }}>
                    What went wrong?
                  </label>
                  <select
                    value={feedbackType}
                    onChange={(e) => setFeedbackType(e.target.value as any)}
                    className="w-full p-1.5 rounded border text-xs outline-none"
                    style={{
                      backgroundColor: 'var(--bg-card)',
                      borderColor: 'var(--border-subtle)',
                      color: 'var(--text-primary)',
                    }}
                  >
                    <option value="wrong_verdict">Wrong Verdict (Model error)</option>
                    <option value="missed_evidence">Missed Site Evidence</option>
                    <option value="incorrect_claim">Misunderstood Claim Text</option>
                    <option value="other">Other Issue</option>
                  </select>
                </div>

                <div>
                  <label className="block text-[10px] uppercase tracking-wider font-mono font-semibold mb-1" style={{ color: 'var(--text-muted)' }}>
                    Expected Verdict
                  </label>
                  <select
                    value={expectedVerdict}
                    onChange={(e) => setExpectedVerdict(e.target.value)}
                    className="w-full p-1.5 rounded border text-xs outline-none"
                    style={{
                      backgroundColor: 'var(--bg-card)',
                      borderColor: 'var(--border-subtle)',
                      color: 'var(--text-primary)',
                    }}
                  >
                    <option value="confirmed">Confirmed (Verified)</option>
                    <option value="contradicted">Contradicted (False)</option>
                    <option value="partial">Partial / Misleading</option>
                    <option value="not_found">Unverified (Not Found)</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-[10px] uppercase tracking-wider font-mono font-semibold mb-1" style={{ color: 'var(--text-muted)' }}>
                  Submitter Notes / Link Context (Optional)
                </label>
                <textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Explain why this verdict is wrong, or quote the true policy clause..."
                  rows={2}
                  className="w-full p-2 rounded border text-xs outline-none resize-none"
                  style={{
                    backgroundColor: 'var(--bg-card)',
                    borderColor: 'var(--border-subtle)',
                    color: 'var(--text-primary)',
                  }}
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => setShowFeedback(false)}
                  className="px-2.5 py-1 rounded text-xs border cursor-pointer hover:opacity-80"
                  style={{
                    backgroundColor: 'transparent',
                    borderColor: 'var(--border-subtle)',
                    color: 'var(--text-muted)',
                  }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-3 py-1 rounded text-xs font-semibold cursor-pointer transition-opacity hover:opacity-90 disabled:opacity-50"
                  style={{
                    backgroundColor: 'var(--accent)',
                    color: '#fff',
                  }}
                >
                  {isSubmitting ? 'Recording...' : 'Submit Feedback'}
                </button>
              </div>
            </form>
          )}
        </div>
      )}
    </div>
  );
};
