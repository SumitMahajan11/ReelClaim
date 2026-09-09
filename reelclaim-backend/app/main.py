import re
import uuid
from typing import Optional
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from app.models import (
    ExtractionRequest,
    ExtractionResponse,
    CrawlRequest,
    CrawlResponse,
    CheckRequest,
    CheckResponse,
    FullAuditRequest,
    FullAuditResponse,
    YouTubeMetadata,
    YouTubeIngestRequest,
    YouTubeIngestResponse,
    FeedbackRequest,
    FeedbackResponse,
    is_plausible_gemini_key
)
from app.extraction import extract_claims
from app.crawler import crawl_site
from app.checker import cross_check_claims
from app.sources import gather_all_evidence
from app.youtube import is_youtube_url, ingest_youtube_short
from app.db import (
    init_db,
    save_audit_record,
    get_audit_record_by_id,
    save_audit_feedback
)
from app.auth import verify_api_key, register_new_api_key


# Initialize DB on module import (degrades to persistence disabled if DATABASE_URL unset)
init_db()

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(
    title="ReelClaim Backend Service",
    description="Phase 1, 2, 3 & 4: Claim Extraction, Multi-Source Evidence Gathering, Cross-Check Engine & Web UI API",
    version="4.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

def validate_and_get_api_key(request_key: Optional[str]) -> Optional[str]:
    """
    Validates per-request BYOK Gemini API key format if provided.
    Returns stripped key or None. Raises HTTP 400 if malformed.
    """
    if request_key and request_key.strip():
        k = request_key.strip()
        if not is_plausible_gemini_key(k):
            raise HTTPException(
                status_code=400,
                detail="Invalid Gemini API key format. Key must start with 'AIza' and be 30-60 characters long."
            )
        return k
    return None

def handle_api_exception(e: Exception, context_msg: str):
    """
    Sanitizes exception messages to ensure API keys are never logged or echoed back.
    Maps invalid key or client errors to HTTP 400 cleanly.
    """
    err_str = str(e)
    clean_err = re.sub(r'AIza[A-Za-z0-9_\-]{30,60}', '[REDACTED]', err_str)
    err_lower = clean_err.lower()

    if any(term in err_lower for term in ["invalid_argument", "api_key", "apikey", "invalid api key", "unauthorized", "permission_denied", "api key not valid"]):
        raise HTTPException(status_code=400, detail=f"Gemini API key rejected: {clean_err}")
    raise HTTPException(status_code=500, detail=f"{context_msg}: {clean_err}")

class RegisterKeyRequest(BaseModel):
    name: str = Field(..., description="User or application name for this API key")
    rate_limit_per_hour: int = Field(60, ge=1, le=1000, description="Allowed requests per hour")

@app.post("/auth/register-key")
def register_key_endpoint(request: RegisterKeyRequest):
    """
    Registers a new API key for authenticating with ReelClaim service.
    Returns the plaintext API key once. Store it securely.
    """
    return register_new_api_key(name=request.name, rate_limit_per_hour=request.rate_limit_per_hour)

@app.get("/")
def health_check():
    return {
        "status": "healthy",
        "service": "ReelClaim Backend",
        "phase": 4,
        "endpoints": [
            "POST /auth/register-key",
            "POST /extract-claims",
            "POST /crawl-site",
            "POST /check-claims",
            "POST /ingest-youtube",
            "POST /audit-reel",
            "GET /audits/{audit_id}",
            "POST /audits/{audit_id}/feedback"
        ]
    }

@app.post("/extract-claims", response_model=ExtractionResponse)
def extract_claims_endpoint(request: ExtractionRequest, auth: Optional[dict] = Depends(verify_api_key)):
    """
    Phase 1: Extracts promotional claims and promoted site from a given social media reel caption.
    Supports optional BYOK per-request gemini_api_key.
    """
    api_key = validate_and_get_api_key(request.gemini_api_key)
    try:
        result = extract_claims(request.caption, api_key=api_key)
        return result
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        handle_api_exception(e, "Extraction error")

@app.post("/crawl-site", response_model=CrawlResponse)
def crawl_site_endpoint(request: CrawlRequest, auth: Optional[dict] = Depends(verify_api_key)):
    """
    Phase 2: Crawls target website, discovers key pages, and extracts verifiable facts per page.
    Supports optional BYOK per-request gemini_api_key.
    """
    api_key = validate_and_get_api_key(request.gemini_api_key)
    try:
        result = crawl_site(request.url, api_key=api_key)
        return result
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        handle_api_exception(e, "Crawl error")

@app.post("/check-claims", response_model=CheckResponse)
def check_claims_endpoint(request: CheckRequest, auth: Optional[dict] = Depends(verify_api_key)):
    """
    Phase 3: Compares extracted claims against site facts and multi-source evidence to generate verdicts.
    Supports optional BYOK per-request gemini_api_key.
    """
    api_key = validate_and_get_api_key(request.gemini_api_key)
    try:
        result = cross_check_claims(request.claims, site_facts=request.site_facts, facts=request.facts, api_key=api_key)
        return result
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        handle_api_exception(e, "Cross-check error")

@app.post("/ingest-youtube", response_model=YouTubeIngestResponse)
def ingest_youtube_endpoint(request: YouTubeIngestRequest, auth: Optional[dict] = Depends(verify_api_key)):
    """
    Direct endpoint to extract metadata (title, description, channel) and audio transcript
    from a public YouTube Shorts or Video URL.
    """
    try:
        result = ingest_youtube_short(request.video_url, api_key=request.youtube_api_key)
        return YouTubeIngestResponse(
            video_id=result.video_id,
            video_url=result.video_url,
            title=result.title,
            description=result.description,
            channel_title=result.channel_title,
            thumbnail_url=result.thumbnail_url,
            transcript=result.transcript,
            combined_text=result.combined_text,
            detected_site=result.detected_site,
            status=result.status,
            error_message=result.error_message
        )
    except Exception as e:
        handle_api_exception(e, "YouTube ingest error")

@app.post("/audit-reel", response_model=FullAuditResponse)
def audit_reel_endpoint(request: FullAuditRequest, auth: Optional[dict] = Depends(verify_api_key)):
    """
    End-to-End Multi-Source Evidence Pipeline:
    1. Ingests video metadata and audio transcript if a YouTube URL is provided (or auto-detected)
    2. Extracts claims from social caption / YouTube transcript corpus (Phase 1)
    3. Gathers multi-source evidence (SiteCrawl, Whois, Wayback, CrossReference)
    4. Cross-checks claims against multi-source evidence to calculate confidence tier and 'why'
    5. Persists audit result and facts per source to database if DATABASE_URL is configured.
    """
    api_key = validate_and_get_api_key(request.gemini_api_key)
    try:
        caption_text = request.caption or ""
        video_url = request.video_url or ""
        override_url = request.override_url
        youtube_meta = None

        # Check if caption itself is a YouTube URL or if video_url is provided
        if not video_url and caption_text and is_youtube_url(caption_text.strip()):
            video_url = caption_text.strip()
            caption_text = ""

        # Step 0: Ingest YouTube metadata and transcript if video_url is present
        if video_url and is_youtube_url(video_url):
            ingest_res = ingest_youtube_short(video_url, api_key=request.youtube_api_key)
            if ingest_res.status != "error":
                youtube_meta = YouTubeMetadata(
                    video_id=ingest_res.video_id,
                    video_url=ingest_res.video_url,
                    title=ingest_res.title,
                    description=ingest_res.description,
                    channel_title=ingest_res.channel_title,
                    thumbnail_url=ingest_res.thumbnail_url,
                    transcript=ingest_res.transcript,
                    detected_site=ingest_res.detected_site
                )
                if not caption_text.strip():
                    caption_text = ingest_res.combined_text
                if not override_url and ingest_res.detected_site:
                    override_url = ingest_res.detected_site

        if not caption_text.strip():
            raise HTTPException(
                status_code=422,
                detail="No claim text provided. Please provide a caption or a valid public YouTube Short URL."
            )

        # Step 1: Extract claims
        extraction = extract_claims(caption_text, api_key=api_key)
        target_url = override_url or extraction.promoted_site

        response = None
        if not target_url:
            response = FullAuditResponse(
                caption=caption_text,
                promoted_site=None,
                claims=extraction.claims,
                crawl_status="no_url_found",
                check_result=None,
                facts_gathered=[],
                youtube_metadata=youtube_meta
            )
        else:
            # Step 2: Gather evidence across all 4 sources
            crawl = crawl_site(target_url, api_key=api_key)
            crawl_status = crawl.crawl_status

            if crawl_status in ["blocked", "failed", "busy", "overloaded", "no_url_found"] and not crawl.facts:
                # Still attempt cross-reference, Wayback, and Whois even if site crawl was blocked
                all_facts = gather_all_evidence(extraction.claims, target_url=target_url, api_key=api_key, site_facts=[])
                if all_facts:
                    check = cross_check_claims(extraction.claims, facts=all_facts, api_key=api_key)
                    response = FullAuditResponse(
                        caption=caption_text,
                        promoted_site=target_url,
                        claims=extraction.claims,
                        crawl_status=crawl_status,
                        check_result=check,
                        facts_gathered=all_facts,
                        youtube_metadata=youtube_meta
                    )
                else:
                    response = FullAuditResponse(
                        caption=caption_text,
                        promoted_site=target_url,
                        claims=extraction.claims,
                        crawl_status=crawl_status,
                        check_result=None,
                        facts_gathered=[],
                        youtube_metadata=youtube_meta
                    )
            else:
                all_facts = gather_all_evidence(extraction.claims, target_url=target_url, api_key=api_key, site_facts=crawl.facts)
                check = cross_check_claims(extraction.claims, facts=all_facts, api_key=api_key)
                response = FullAuditResponse(
                    caption=caption_text,
                    promoted_site=target_url,
                    claims=extraction.claims,
                    crawl_status=crawl_status,
                    check_result=check,
                    facts_gathered=all_facts,
                    youtube_metadata=youtube_meta
                )

        # Step 4: Generate submitter session token and persist result to database
        submitter_token = f"sub_{uuid.uuid4().hex}"
        audit_id = save_audit_record(
            caption=response.caption,
            promoted_site=response.promoted_site,
            override_url=override_url,
            claims=response.claims,
            crawl_status=response.crawl_status,
            check_result=response.check_result,
            facts=response.facts_gathered,
            submitter_token=submitter_token
        )

        response.submitter_token = submitter_token
        if audit_id:
            response.id = audit_id
            response.created_at = datetime.now(timezone.utc).isoformat()

        return response
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        handle_api_exception(e, "Audit reel error")

@app.get("/audits/{audit_id}")
def get_audit_endpoint(audit_id: str):
    """
    Fetches a persisted audit record by unique ID (accessible to submitter or via direct share ID).
    """
    record = get_audit_record_by_id(audit_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Audit record '{audit_id}' not found.")
    return record

@app.post("/audits/{audit_id}/feedback", response_model=FeedbackResponse)
def submit_audit_feedback_endpoint(
    audit_id: str,
    request: FeedbackRequest,
    x_submitter_token: Optional[str] = Header(None, alias="X-Submitter-Token")
):
    """
    Lightweight Submitter Feedback Mechanism:
    Allows the submitter to flag a verdict or claim as incorrect on their own audit.
    Auth-gated to the audit owner via submitter_token (in header or body).
    Stores feedback for ongoing accuracy benchmarking and evaluation.
    """
    token = request.submitter_token or x_submitter_token
    success, feedback_id, message = save_audit_feedback(
        audit_id=audit_id,
        feedback_data=request.model_dump(),
        submitter_token=token
    )
    if not success:
        if "not found" in message.lower():
            raise HTTPException(status_code=404, detail=message)
        if "forbidden" in message.lower() or "unauthorized" in message.lower():
            raise HTTPException(status_code=403, detail=message)
        raise HTTPException(status_code=400, detail=message)

    return FeedbackResponse(
        status="recorded",
        audit_id=audit_id,
        feedback_id=feedback_id or "local",
        created_at=datetime.now(timezone.utc).isoformat(),
        message="Feedback recorded successfully for benchmark tuning."
    )

