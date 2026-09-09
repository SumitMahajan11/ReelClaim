import { FullAuditResponse, RecentAuditItem } from './types';

const LOCAL_STORAGE_KEY = 'reelclaim_submitter_audits';

export function getSubmitterAudits(): RecentAuditItem[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = localStorage.getItem(LOCAL_STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch (e) {
    console.error('Failed to read submitter audits from localStorage', e);
    return [];
  }
}

export function saveSubmitterAudit(audit: FullAuditResponse): void {
  if (typeof window === 'undefined' || !audit.id) return;
  try {
    const existing = getSubmitterAudits();
    const item: RecentAuditItem = {
      id: audit.id,
      created_at: audit.created_at || new Date().toISOString(),
      caption: audit.caption,
      promoted_site: audit.promoted_site,
      crawl_status: audit.crawl_status,
      confidence_tier: audit.check_result?.confidence_tier || null,
      coverage_status: audit.check_result?.coverage_status || null,
      summary_label: audit.check_result?.summary_label || null,
      total_claims: audit.claims.length,
      status: 'completed'
    };
    const filtered = existing.filter((a) => a.id !== audit.id);
    const updated = [item, ...filtered].slice(0, 25);
    localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(updated));
  } catch (e) {
    console.error('Failed to save submitter audit to localStorage', e);
  }
}

export function clearSubmitterAudits(): void {
  if (typeof window === 'undefined') return;
  try {
    localStorage.removeItem(LOCAL_STORAGE_KEY);
  } catch (e) {
    console.error('Failed to clear submitter audits', e);
  }
}
