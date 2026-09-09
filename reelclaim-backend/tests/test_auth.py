import os
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.models import Claim, CheckResponse, ScoreBreakdown
from app.auth import reset_rate_limits

@pytest.fixture(autouse=True)
def auto_reset_rate_limits():
    reset_rate_limits()
    yield
    reset_rate_limits()

def test_auth_disabled_by_default(tmp_path):
    """When REQUIRE_AUTH is false (default), requests succeed without X-API-Key."""
    with patch.dict(os.environ, {"REQUIRE_AUTH": "false"}):
        client = TestClient(app)
        with patch("app.main.extract_claims") as mock_extract, \
             patch("app.main.crawl_site") as mock_crawl, \
             patch("app.main.gather_all_evidence", return_value=[]) as mock_gather, \
             patch("app.main.cross_check_claims") as mock_check:

            mock_extract.return_value.promoted_site = "https://example.com"
            mock_extract.return_value.claims = [Claim(text="Free trial", category="discount", source_type="caption", confidence="high")]
            mock_crawl.return_value.crawl_status = "success"
            mock_crawl.return_value.facts = []
            mock_check.return_value = CheckResponse(
                confidence_tier="LIKELY_TRUE",
                coverage_status="verified",
                summary_label="Confirmed",
                score_breakdown=ScoreBreakdown(confirmed_count=1, partial_count=0, contradicted_count=0, not_found_count=0, addressed_claims=1, total_claims=1),
                verdicts=[]
            )

            resp = client.post("/audit-reel", json={"caption": "Check out vercel.com/pricing for free hobby plan"})
            assert resp.status_code == 200

def test_auth_missing_key_returns_401():
    """When REQUIRE_AUTH=true, missing X-API-Key returns HTTP 401."""
    with patch.dict(os.environ, {"REQUIRE_AUTH": "true"}):
        client = TestClient(app)
        resp = client.post("/audit-reel", json={"caption": "Test caption"})
        assert resp.status_code == 401
        assert "Invalid or missing X-API-Key header" in resp.json()["detail"]

def test_auth_invalid_key_returns_401():
    """When REQUIRE_AUTH=true, invalid X-API-Key returns HTTP 401."""
    with patch.dict(os.environ, {"REQUIRE_AUTH": "true"}):
        client = TestClient(app)
        resp = client.post(
            "/audit-reel",
            json={"caption": "Test caption"},
            headers={"X-API-Key": "rc_live_invalidkey12345"}
        )
        assert resp.status_code == 401
        assert "Invalid or inactive API key" in resp.json()["detail"]

def test_auth_valid_key_success():
    """When REQUIRE_AUTH=true, a registered key allows requests to succeed."""
    with patch.dict(os.environ, {"REQUIRE_AUTH": "true"}):
        client = TestClient(app)

        # Register key
        reg_resp = client.post("/auth/register-key", json={"name": "test-user", "rate_limit_per_hour": 10})
        assert reg_resp.status_code == 200
        raw_key = reg_resp.json()["api_key"]

        with patch("app.main.extract_claims") as mock_extract, \
             patch("app.main.crawl_site") as mock_crawl, \
             patch("app.main.gather_all_evidence", return_value=[]) as mock_gather, \
             patch("app.main.cross_check_claims") as mock_check:

            mock_extract.return_value.promoted_site = "https://example.com"
            mock_extract.return_value.claims = [Claim(text="Free trial", category="discount", source_type="caption", confidence="high")]
            mock_crawl.return_value.crawl_status = "success"
            mock_crawl.return_value.facts = []
            mock_check.return_value = CheckResponse(
                confidence_tier="LIKELY_TRUE",
                coverage_status="verified",
                summary_label="Confirmed",
                score_breakdown=ScoreBreakdown(confirmed_count=1, partial_count=0, contradicted_count=0, not_found_count=0, addressed_claims=1, total_claims=1),
                verdicts=[]
            )

            resp = client.post(
                "/audit-reel",
                json={"caption": "Check out vercel.com/pricing for free hobby plan"},
                headers={"X-API-Key": raw_key}
            )
            assert resp.status_code == 200

def test_auth_rate_limiting_returns_429():
    """When rate limit is exceeded, endpoint returns HTTP 429 with Retry-After header."""
    with patch.dict(os.environ, {"REQUIRE_AUTH": "true"}):
        client = TestClient(app)

        # Register key with limit of 2 per hour
        reg_resp = client.post("/auth/register-key", json={"name": "rate-limit-test", "rate_limit_per_hour": 2})
        assert reg_resp.status_code == 200
        raw_key = reg_resp.json()["api_key"]

        with patch("app.main.extract_claims") as mock_extract, \
             patch("app.main.crawl_site") as mock_crawl, \
             patch("app.main.gather_all_evidence", return_value=[]) as mock_gather, \
             patch("app.main.cross_check_claims") as mock_check:

            mock_extract.return_value.promoted_site = "https://example.com"
            mock_extract.return_value.claims = []
            mock_crawl.return_value.crawl_status = "success"
            mock_crawl.return_value.facts = []
            mock_check.return_value = CheckResponse(
                confidence_tier="INSUFFICIENT_EVIDENCE",
                coverage_status="verified",
                summary_label="Confirmed",
                score_breakdown=ScoreBreakdown(confirmed_count=0, partial_count=0, contradicted_count=0, not_found_count=0, addressed_claims=0, total_claims=0),
                verdicts=[]
            )

            # Request 1: OK
            resp1 = client.post("/audit-reel", json={"caption": "Cap 1"}, headers={"X-API-Key": raw_key})
            assert resp1.status_code == 200

            # Request 2: OK
            resp2 = client.post("/audit-reel", json={"caption": "Cap 2"}, headers={"X-API-Key": raw_key})
            assert resp2.status_code == 200

            # Request 3: Rate limited -> 429
            resp3 = client.post("/audit-reel", json={"caption": "Cap 3"}, headers={"X-API-Key": raw_key})
            assert resp3.status_code == 429
            assert "Retry-After" in resp3.headers
            assert int(resp3.headers["Retry-After"]) > 0
            assert "Rate limit exceeded" in resp3.json()["detail"]

