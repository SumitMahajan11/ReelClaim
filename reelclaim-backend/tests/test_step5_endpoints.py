import sys
import json
from pathlib import Path
from fastapi.testclient import TestClient

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.main import app
from app.models import Claim, SiteFact, CheckRequest

from unittest.mock import patch
from app.models import ExtractionResponse

def test_1_extract_claims_endpoint():
    """Verify POST /extract-claims schema and response."""
    with patch("app.main.extract_claims") as mock_extract:
        mock_extract.return_value = ExtractionResponse(
            promoted_site="boot.dev",
            claims=[
                Claim(category="price", text="100% FREE Python backend bootcamp", confidence="high", source_type="caption"),
                Claim(category="certificate", text="verified certificate included", confidence="high", source_type="caption")
            ]
        )
        payload = {"caption": "🔥 100% FREE Python backend bootcamp with verified certificate on boot.dev"}
        res = client.post("/extract-claims", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert "promoted_site" in data
        assert "claims" in data
        assert data["promoted_site"] == "boot.dev"
        assert len(data["claims"]) > 0
        for claim in data["claims"]:
            assert "category" in claim
            assert "text" in claim
            assert "confidence" in claim
            assert "source_type" in claim
            assert claim["category"] in ["price", "certificate", "partnership", "eligibility", "deadline", "salary", "discount", "refund", "other"]

def test_2_crawl_site_mock_verification():
    """Verify POST /crawl-site endpoint handling."""
    # Test invalid payload structure
    res_bad = client.post("/crawl-site", json={})
    assert res_bad.status_code == 422

    # Test crawling a site structure endpoint validation
    res = client.post("/crawl-site", json={"url": "https://httpbin.org/html"})
    assert res.status_code == 200
    data = res.json()
    assert "site_url" in data
    assert "pages_found" in data
    assert "pages_missing" in data
    assert "facts" in data
    assert "crawl_status" in data
    assert data["crawl_status"] in ["success", "blocked", "failed"]

def test_3_check_claims_endpoint():
    """Verify POST /check-claims with valid categories and evidence matching."""
    # Invalid category input -> 422
    invalid_payload = {
        "claims": [{"category": "invalid_category", "text": "free", "confidence": "high", "source_type": "caption"}],
        "site_facts": []
    }
    res_422 = client.post("/check-claims", json=invalid_payload)
    assert res_422.status_code == 422

    # Valid payload
    claims = [
        {"category": "price", "text": "Course costs $99/mo", "confidence": "high", "source_type": "caption"}
    ]
    facts = [
        {"category": "price", "text": "Membership pricing is $99/mo.", "source_page": "pricing", "source_url": "https://example.com/pricing"}
    ]
    res = client.post("/check-claims", json={"claims": claims, "site_facts": facts})
    assert res.status_code == 200
    data = res.json()
    assert data["confidence_tier"] == "LIKELY_TRUE"
    assert data["coverage_status"] == "verified"
    assert len(data["verdicts"]) == 1
    assert data["verdicts"][0]["verdict"] == "confirmed"

def test_4_audit_reel_invalid_body_422():
    """Verify POST /audit-reel returns 422 on invalid request body."""
    # Missing required 'caption' or 'video_url' field
    res = client.post("/audit-reel", json={"url": "https://example.com"})
    assert res.status_code == 422
    detail = res.json()["detail"]
    assert any("caption" in str(err) for err in detail)

def test_5_audit_reel_zero_facts_unverified():
    """Verify POST /audit-reel with a site producing zero facts returns unverified_no_data."""
    # example.com yields zero product facts
    res = client.post("/audit-reel", json={
        "caption": "Get 90% discount on example.com today!",
        "override_url": "https://example.com"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["caption"] == "Get 90% discount on example.com today!"
    assert data["promoted_site"] == "https://example.com"
    assert "claims" in data
    assert data["crawl_status"] == "success"
    assert data["check_result"] is not None
    check = data["check_result"]
    assert check["confidence_tier"] == "INSUFFICIENT_EVIDENCE"
    assert check["coverage_status"] == "unverified_no_data"
    assert "Insufficient Evidence" in check["summary_label"]
    assert check["score_breakdown"]["addressed_claims"] == 0

if __name__ == "__main__":
    test_1_extract_claims_endpoint()
    print("✓ Test 1 passed")
    test_2_crawl_site_mock_verification()
    print("✓ Test 2 passed")
    test_3_check_claims_endpoint()
    print("✓ Test 3 passed")
    test_4_audit_reel_invalid_body_422()
    print("✓ Test 4 passed")
    test_5_audit_reel_zero_facts_unverified()
    print("✓ Test 5 passed")
    print("All Step 5 tests passed successfully!")
