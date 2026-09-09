import sys
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

# Ensure root directory is on python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models import Claim, SiteFact, is_transient_error
from app.extraction import extract_claims
from app.checker import verify_single_claim, cross_check_claims
from app.main import app

client = TestClient(app)

def test_is_transient_error_classification():
    """Verify is_transient_error correctly identifies 429 and 5xx vs 400 and safety errors."""
    assert is_transient_error(Exception("429 ResourceExhausted: Quota exceeded")) is True
    assert is_transient_error(Exception("503 Service Unavailable")) is True
    assert is_transient_error(Exception("500 Internal Server Error")) is True
    assert is_transient_error(Exception("502 Bad Gateway")) is True

    # Non-transient errors must return False
    assert is_transient_error(Exception("400 Bad Request: Invalid JSON payload")) is False
    assert is_transient_error(Exception("401 Unauthorized: Invalid API Key")) is False
    assert is_transient_error(Exception("403 Forbidden: Access denied")) is False
    assert is_transient_error(Exception("Prompt blocked by safety filters")) is False

@patch("time.sleep")
@patch("google.generativeai.GenerativeModel.generate_content")
def test_phase1_claim_extraction_429_retry_and_graceful_exhaustion(mock_generate, mock_sleep):
    """
    Verify Phase 1 claim extraction:
    - Retries 3 times on 429 error
    - Performs exponential backoff (2s, 4s)
    - Returns graceful ExtractionResponse on exhaustion without throwing 500 error
    """
    mock_generate.side_effect = Exception("429 ResourceExhausted: Rate limit exceeded")

    import pytest
    with pytest.raises(RuntimeError, match="Extraction service unavailable"):
        extract_claims("🔥 FREE AI Course with certificate on boot.dev")

    # Assert model was called 3 times
    assert mock_generate.call_count == 3

    # Assert sleep called twice with backoff 2 and 4
    assert mock_sleep.call_count == 2
    mock_sleep.assert_any_call(2)
    mock_sleep.assert_any_call(4)

@patch("time.sleep")
@patch("google.generativeai.GenerativeModel.generate_content")
def test_phase3_cross_check_429_retry_and_partial_result_on_exhaustion(mock_generate, mock_sleep):
    """
    Verify Phase 3 cross-check engine:
    - Retries 429 error 3 times for failing claim
    - Backs off with [2, 4]
    - Keeps successful verdicts for non-failing claims
    - Returns usable (partial) audit result after exhaustion instead of crashing
    """
    # First call succeeds for claim 1, second claim hits 429 repeatedly
    successful_response = MagicMock()
    successful_response.text = json.dumps({
        "verdict": "confirmed",
        "evidence_text": "Monthly membership costs ₹999 / month (listed as ₹5599 INR with a ₹4600 PPP Discount).",
        "source_url": "https://boot.dev/pricing",
        "reasoning": "Price matches site fact."
    })

    rate_limit_exception = Exception("429 Too Many Requests: Quota exceeded")

    # Claim 1 -> 1 call (success). Claim 2 -> 3 calls (429 rate limit). Total = 4 calls.
    mock_generate.side_effect = [
        successful_response,
        rate_limit_exception,
        rate_limit_exception,
        rate_limit_exception
    ]

    claim1 = Claim(category="price", text="Boot.dev costs ₹999/mo", confidence="high", source_type="caption")
    claim2 = Claim(category="refund", text="30-day money-back refund", confidence="high", source_type="caption")

    facts = [
        SiteFact(
            category="price",
            text="Monthly membership costs ₹999 / month (listed as ₹5599 INR with a ₹4600 PPP Discount).",
            source_page="pricing",
            source_url="https://boot.dev/pricing"
        ),
        SiteFact(
            category="refund",
            text="Users have 30 calendar days to request a refund.",
            source_page="refund_policy",
            source_url="https://boot.dev/return-policy"
        )
    ]

    result = cross_check_claims([claim1, claim2], facts)

    # 1 call for claim 1 + 3 calls for claim 2 = 4 total calls
    assert mock_generate.call_count == 4

    # Backoff sleep called for claim 2 (2s and 4s)
    sleep_args = [call.args[0] for call in mock_sleep.call_args_list if call.args[0] in [2, 4]]
    assert 2 in sleep_args
    assert 4 in sleep_args

    # Check verdicts: claim1 is confirmed, claim2 gracefully degraded to not_found with error reasoning
    assert len(result.verdicts) == 2
    assert result.verdicts[0].verdict == "confirmed"
    assert result.verdicts[1].verdict == "not_found"
    assert "Verification service unavailable: 429" in result.verdicts[1].reasoning

    # Partial audit result is valid and usable
    assert result.coverage_status == "partially_verified"
    assert result.score_breakdown.confirmed_count == 1
    assert result.score_breakdown.not_found_count == 1
    assert result.confidence_tier == "LIKELY_TRUE"

@patch("time.sleep")
@patch("google.generativeai.GenerativeModel.generate_content")
def test_non_transient_400_error_no_retry(mock_generate, mock_sleep):
    """Verify non-transient 400 Bad Request error fails fast without retrying or sleeping."""
    mock_generate.side_effect = Exception("400 Bad Request: Invalid prompt parameters")

    claim = Claim(category="price", text="Course costs $99", confidence="high", source_type="caption")
    facts = [SiteFact(category="price", text="Course costs $99", source_page="pricing", source_url="https://example.com")]

    verdict = verify_single_claim(claim, facts)

    # Should attempt exactly 1 time and NOT retry
    assert mock_generate.call_count == 1
    assert mock_sleep.call_count == 0
    assert verdict.verdict == "not_found"
    assert "400 Bad Request" in verdict.reasoning

@patch("time.sleep")
@patch("google.generativeai.GenerativeModel.generate_content")
def test_full_audit_api_endpoint_handles_rate_limit_gracefully(mock_generate, mock_sleep):
    """Verify POST /audit-reel returns HTTP 200 OK usable response when Gemini API is rate-limited."""
    mock_generate.side_effect = Exception("503 Service Unavailable: High load")

    response = client.post("/audit-reel", json={
        "caption": "🔥 Check out this awesome free tool at example.com!",
        "override_url": "https://example.com"
    })

    assert response.status_code == 500
    data = response.json()
    assert "Audit reel error: Extraction service unavailable" in data["detail"]
