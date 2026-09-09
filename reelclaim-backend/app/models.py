from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field

ClaimCategory = Literal[
    "price",
    "certificate",
    "partnership",
    "eligibility",
    "deadline",
    "salary",
    "discount",
    "refund",
    "other"
]

VALID_CLAIM_CATEGORIES = {
    "price", "certificate", "partnership", "eligibility",
    "deadline", "salary", "discount", "refund", "other"
}

CATEGORY_SYNONYMS = {
    "pricing": "price",
    "cost": "price",
    "fee": "price",
    "fees": "price",
    "discounts": "discount",
    "refunds": "refund",
    "certification": "certificate",
    "credentials": "certificate",
    "endorsed": "partnership",
    "partner": "partnership",
    "prerequisites": "eligibility",
    "qualification": "eligibility",
    "stipend": "salary",
    "compensation": "salary",
    "pay": "salary"
}

def sanitize_category(val: Optional[str]) -> str:
    if not val:
        return "other"
    cat = str(val).strip().lower()
    if cat in VALID_CLAIM_CATEGORIES:
        return cat
    return CATEGORY_SYNONYMS.get(cat, "other")

def is_transient_error(e: Exception) -> bool:
    """
    Determines if an exception is a transient error suitable for retry:
    - 429 Rate Limit / Quota / ResourceExhausted / TooManyRequests
    - Transient 5xx server errors (500, 502, 503, 504)
    Returns False for non-transient errors (400 Bad Request, 401 Unauthorized, 403 Forbidden, safety/content filters).
    """
    err_str = f"{type(e).__name__}: {str(e)}".lower()

    # Non-retryable error signatures (400, 401, 403, client invalid input, content policy/safety blocks)
    non_retryable = [
        "400", "bad request", "invalid_argument", "invalidargument",
        "401", "unauthorized",
        "403", "forbidden", "permission_denied", "permissiondenied",
        "safety", "blocked", "content_filter", "recitation"
    ]
    if any(sig in err_str for sig in non_retryable):
        return False

    # Retryable error signatures (429 rate limit/quota and 5xx server errors)
    retryable = [
        "429", "resourceexhausted", "resource_exhausted", "toomanyrequests", "quota", "too many requests", "rate limit",
        "500", "502", "503", "504", "internalservererror", "internal server error", "serviceunavailable", "service unavailable",
        "badgateway", "bad gateway", "gatewaytimeout", "gateway timeout", "overloaded", "transient"
    ]
    if any(sig in err_str for sig in retryable):
        return True

    return False


ConfidenceLevel = Literal["high", "medium", "low"]

import re

def is_plausible_gemini_key(key: Optional[str]) -> bool:
    """Validates that a per-request key is a plausible Google Gemini API key format."""
    if not key or not isinstance(key, str):
        return False
    k = key.strip()
    if not k.startswith("AIza"):
        return False
    if len(k) < 30 or len(k) > 60:
        return False
    if not re.match(r"^[A-Za-z0-9_\-]+$", k):
        return False
    return True

# Phase 1 Models

class Claim(BaseModel):
    category: ClaimCategory = Field(..., description="Category of the claim")
    text: str = Field(..., description="Specific text description of the extracted claim (full text for display)")
    core_text: str = Field(default="", description="Core assertion of the claim without qualifiers (for verification)")
    qualifiers: List[str] = Field(default_factory=list, description="List of condition, scope, or superlative qualifiers")
    confidence: ConfidenceLevel = Field(..., description="Confidence level: high, medium, or low")
    source_type: Literal["caption", "comment"] = Field("caption", description="Origin of the claim: caption or comment")

class ExtractionRequest(BaseModel):
    caption: str = Field(..., description="Raw promotional social media caption text")
    gemini_api_key: Optional[str] = Field(None, description="Optional per-request Gemini API key for BYOK")

class ExtractionResponse(BaseModel):
    promoted_site: Optional[str] = Field(None, description="Promoted website URL, domain, or handle mentioned in caption; null if none mentioned")
    claims: List[Claim] = Field(default_factory=list, description="List of extracted claims")


# Phase 2 Models
PageType = Literal["home", "pricing", "terms", "faq", "registration", "refund_policy"]

class SiteFact(BaseModel):
    category: ClaimCategory = Field(..., description="Category of the extracted fact")
    text: str = Field(..., description="Extracted fact statement from website page")
    source_page: str = Field(..., description="Standardized page type where fact was found (e.g. home, pricing, faq)")
    source_url: str = Field(..., description="Exact URL of the source page")
    is_self_attested: bool = Field(True, description="True if evidence is from the promoter's own site/landing page (self-attestation), False if from an independent 3rd-party source")

class CrawlRequest(BaseModel):
    url: str = Field(..., description="Target website URL to crawl")
    gemini_api_key: Optional[str] = Field(None, description="Optional per-request Gemini API key for BYOK")

class CrawlResponse(BaseModel):
    site_url: str = Field(..., description="Base target site URL")
    pages_found: List[str] = Field(default_factory=list, description="List of standardized page types successfully discovered and crawled")
    pages_missing: List[str] = Field(default_factory=list, description="List of standardized page types not found or uncrawled")
    facts: List[SiteFact] = Field(default_factory=list, description="All extracted facts from crawled pages")
    crawl_status: Literal["success", "blocked", "failed", "degraded", "busy", "overloaded"] = Field(..., description="Overall crawl execution status")


# Phase 3 Models (Cross-Check Engine)
VerdictType = Literal["confirmed", "contradicted", "partial", "not_found"]
ConfidenceTier = Literal["VERIFIED", "LIKELY_TRUE", "CONTRADICTED", "INSUFFICIENT_EVIDENCE"]

class ClaimVerdict(BaseModel):
    claim_text: str = Field(..., description="Text of the evaluated claim")
    category: ClaimCategory = Field(..., description="Category of the claim")
    source_type: Literal["caption", "comment"] = Field("caption", description="Origin of the claim")
    verdict: VerdictType = Field(..., description="Cross-check verdict: confirmed, contradicted, partial, or not_found")
    evidence_text: Optional[str] = Field(None, description="Exact quoted text from site fact used as evidence, or null if not_found")
    source_url: Optional[str] = Field(None, description="Source page URL where evidence was found, or null")
    reasoning: str = Field(..., description="One sentence explanation of the verdict")
    is_self_attested: bool = Field(True, description="Whether the backing evidence is self-attested by the promoter site")
    evidence_source: Optional[str] = Field(None, description="Name of the backing evidence source: site_crawl, cross_reference, wayback, whois")
    trust_weight: Optional[float] = Field(None, description="Trust weight of the backing source")

class ScoreBreakdown(BaseModel):
    confirmed_count: int = Field(0, description="Number of confirmed claims")
    partial_count: int = Field(0, description="Number of partially supported claims")
    contradicted_count: int = Field(0, description="Number of contradicted claims")
    not_found_count: int = Field(0, description="Number of claims with no supporting/contradicting evidence found")
    addressed_claims: int = Field(0, description="Number of claims addressed by site facts (confirmed + partial + contradicted)")
    total_claims: int = Field(0, description="Total number of evaluated claims")

class CheckRequest(BaseModel):
    claims: List[Claim] = Field(..., description="List of extracted claims from Phase 1")
    site_facts: Optional[List[SiteFact]] = Field(default_factory=list, description="Legacy list of extracted site facts from Phase 2")
    facts: Optional[List[Any]] = Field(default_factory=list, description="Multi-source facts gathered from evidence plugins")
    gemini_api_key: Optional[str] = Field(None, description="Optional per-request Gemini API key for BYOK")

class CheckResponse(BaseModel):
    confidence_tier: ConfidenceTier = Field(..., description="Overall confidence tier: VERIFIED, LIKELY_TRUE, CONTRADICTED, INSUFFICIENT_EVIDENCE")
    coverage_status: Literal["verified", "partially_verified", "unverified_no_data"] = Field(..., description="Overall evidence coverage status")
    summary_label: str = Field(..., description="Explainable, non-defamatory summary of claims vs evidence")
    score_breakdown: ScoreBreakdown = Field(..., description="Detailed breakdown of verdict counts")
    verdicts: List[ClaimVerdict] = Field(..., description="List of verdicts per claim")
    source_breakdown: Optional[Dict[str, int]] = Field(default_factory=dict, description="Count of facts contributed per evidence source")

class YouTubeMetadata(BaseModel):
    video_id: str = Field(..., description="YouTube 11-character video ID")
    video_url: str = Field(..., description="Canonical YouTube Shorts or Video URL")
    title: Optional[str] = Field("", description="Video title")
    description: Optional[str] = Field("", description="Video description")
    channel_title: Optional[str] = Field("", description="Channel or creator name")
    thumbnail_url: Optional[str] = Field(None, description="Video thumbnail image URL")
    transcript: Optional[str] = Field("", description="Extracted audio transcript / captions text")
    detected_site: Optional[str] = Field(None, description="Automatically detected promoted website URL")

class YouTubeIngestRequest(BaseModel):
    video_url: str = Field(..., description="YouTube Shorts or Video URL")
    youtube_api_key: Optional[str] = Field(None, description="Optional YouTube Data API v3 key")

class YouTubeIngestResponse(BaseModel):
    video_id: str
    video_url: str
    title: str = ""
    description: str = ""
    channel_title: str = ""
    thumbnail_url: Optional[str] = None
    transcript: str = ""
    combined_text: str = ""
    detected_site: Optional[str] = None
    status: str = "success"
    error_message: Optional[str] = None

from pydantic import BaseModel, Field, model_validator

class FullAuditRequest(BaseModel):
    caption: Optional[str] = Field(None, description="Social media post caption (required for manual mode, optional for YouTube URL mode)")
    video_url: Optional[str] = Field(None, description="Optional YouTube Shorts or Video URL for automatic ingest")
    override_url: Optional[str] = Field(None, description="Optional target URL to crawl if not extracted from caption/video")
    gemini_api_key: Optional[str] = Field(None, description="Optional per-request Gemini API key for BYOK")
    youtube_api_key: Optional[str] = Field(None, description="Optional per-request YouTube Data API v3 key")

    @model_validator(mode="after")
    def validate_caption_or_video_url(self) -> "FullAuditRequest":
        if not self.caption and not self.video_url:
            raise ValueError("Field 'caption' or 'video_url' must be provided.")
        return self

class FeedbackRequest(BaseModel):
    claim_index: Optional[int] = Field(None, description="Index of the claim verdict being flagged (0-indexed), or null if whole audit")
    feedback_type: Literal["wrong_verdict", "missed_evidence", "incorrect_claim", "other"] = Field("wrong_verdict", description="Type of feedback")
    expected_verdict: Optional[Literal["confirmed", "contradicted", "partial", "not_found", "VERIFIED", "LIKELY_TRUE", "CONTRADICTED", "INSUFFICIENT_EVIDENCE"]] = Field(None, description="Expected verdict according to submitter")
    user_notes: Optional[str] = Field(None, description="Submitter explanation or context on why the verdict is wrong")
    submitter_token: Optional[str] = Field(None, description="Submitter authorization token for gating feedback to the audit owner")

class FeedbackResponse(BaseModel):
    status: Literal["recorded", "error"] = "recorded"
    audit_id: str = Field(..., description="Target audit ID")
    feedback_id: str = Field(..., description="Unique ID for this feedback submission")
    created_at: str = Field(..., description="ISO timestamp of submission")
    message: str = "Feedback recorded successfully for benchmark tuning."

class FullAuditResponse(BaseModel):
    id: Optional[str] = Field(None, description="Persisted audit ID if database persistence is enabled")
    created_at: Optional[str] = Field(None, description="ISO timestamp of audit creation")
    caption: str = Field(..., description="Input caption or video text corpus")
    promoted_site: Optional[str] = Field(None, description="Promoted website URL")
    claims: List[Claim] = Field(default_factory=list, description="Extracted claims")
    crawl_status: Optional[str] = Field(None, description="Crawl status")
    check_result: Optional[CheckResponse] = Field(None, description="Cross-check verification response")
    facts_gathered: Optional[List[Any]] = Field(default_factory=list, description="List of all multi-source facts gathered for this audit")
    youtube_metadata: Optional[YouTubeMetadata] = Field(None, description="Structured YouTube metadata if ingested from a YouTube Short/Video")
    submitter_token: Optional[str] = Field(None, description="Submitter session token authorizing feedback submission for this audit")





