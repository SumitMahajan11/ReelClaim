export type ClaimCategory = 
  | "price"
  | "certificate"
  | "partnership"
  | "eligibility"
  | "deadline"
  | "salary"
  | "discount"
  | "refund"
  | "other";

export type VerdictType = "confirmed" | "contradicted" | "partial" | "not_found";

export type ConfidenceTier = "VERIFIED" | "LIKELY_TRUE" | "CONTRADICTED" | "INSUFFICIENT_EVIDENCE";

export type CoverageStatus = "verified" | "partially_verified" | "unverified_no_data";

export interface Claim {
  category: ClaimCategory;
  text: string;
  confidence: "high" | "medium" | "low";
  source_type: "caption" | "comment";
}

export interface Fact {
  source_name: string;
  trust_weight: number;
  content: string;
  retrieved_at: string;
  raw_reference: string;
  category: ClaimCategory;
  is_self_attested?: boolean;
  metadata?: Record<string, any>;
}

export interface SiteFact {
  category: ClaimCategory;
  text: string;
  source_page: string;
  source_url: string;
  is_self_attested?: boolean;
}

export interface ClaimVerdict {
  claim_text: string;
  category: ClaimCategory;
  source_type: "caption" | "comment";
  verdict: VerdictType;
  evidence_text: string | null;
  source_url: string | null;
  reasoning: string;
  is_self_attested?: boolean;
  evidence_source?: string | null;
  trust_weight?: number | null;
}

export interface ScoreBreakdown {
  confirmed_count: number;
  partial_count: number;
  contradicted_count: number;
  not_found_count: number;
  addressed_claims: number;
  total_claims: number;
}

export interface CheckResponse {
  confidence_tier: ConfidenceTier;
  coverage_status: CoverageStatus;
  summary_label: string;
  score_breakdown: ScoreBreakdown;
  verdicts: ClaimVerdict[];
  source_breakdown?: Record<string, number>;
}

export interface YouTubeMetadata {
  video_id: string;
  video_url: string;
  title?: string;
  description?: string;
  channel_title?: string;
  thumbnail_url?: string | null;
  transcript?: string;
  detected_site?: string | null;
}

export interface FullAuditRequest {
  caption?: string;
  video_url?: string;
  override_url?: string;
  gemini_api_key?: string;
  youtube_api_key?: string;
}

export type CrawlStatus = "success" | "degraded" | "busy" | "overloaded" | "blocked" | "failed" | "no_url_found";

export interface FullAuditResponse {
  id?: string;
  created_at?: string;
  caption: string;
  promoted_site: string | null;
  claims: Claim[];
  crawl_status: CrawlStatus | string | null;
  check_result: CheckResponse | null;
  facts_gathered?: Fact[];
  youtube_metadata?: YouTubeMetadata | null;
  submitter_token?: string | null;
}

export interface FeedbackRequest {
  claim_index?: number | null;
  feedback_type: "wrong_verdict" | "missed_evidence" | "incorrect_claim" | "other";
  expected_verdict?: string | null;
  user_notes?: string | null;
  submitter_token?: string | null;
}

export interface FeedbackResponse {
  status: "recorded" | "error";
  audit_id: string;
  feedback_id: string;
  created_at: string;
  message: string;
}

export interface RecentAuditItem {
  id: string;
  created_at: string | null;
  caption: string;
  promoted_site: string | null;
  crawl_status: string | null;
  confidence_tier: ConfidenceTier | null;
  coverage_status: string | null;
  summary_label: string | null;
  total_claims: number;
  status: string;
}

export type ProgressStep = "idle" | "extracting" | "crawling" | "crawling_busy" | "cross_checking" | "complete" | "error";
