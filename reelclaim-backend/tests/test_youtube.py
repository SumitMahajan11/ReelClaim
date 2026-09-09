import os
import json
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.youtube import (
    extract_youtube_video_id,
    is_youtube_url,
    extract_promoted_urls_from_text,
    fetch_youtube_metadata,
    fetch_youtube_transcript,
    ingest_youtube_short,
    YouTubeIngestResult
)
from app.models import (
    Claim,
    CheckResponse,
    ScoreBreakdown,
    ClaimVerdict
)

client = TestClient(app)

def test_extract_youtube_video_id_variants():
    # Standard shorts URL
    assert extract_youtube_video_id("https://www.youtube.com/shorts/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    # Shorts with query parameters
    assert extract_youtube_video_id("https://youtube.com/shorts/dQw4w9WgXcQ?feature=share&si=123") == "dQw4w9WgXcQ"
    # youtu.be shortlink
    assert extract_youtube_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    # Standard watch URL
    assert extract_youtube_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    # Mobile URL
    assert extract_youtube_video_id("https://m.youtube.com/shorts/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    # Direct 11-char ID
    assert extract_youtube_video_id("dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    # Invalid URLs
    assert extract_youtube_video_id("https://instagram.com/reel/Cx12345") is None
    assert extract_youtube_video_id("") is None
    assert extract_youtube_video_id("not-a-youtube-url") is None

def test_is_youtube_url():
    assert is_youtube_url("https://www.youtube.com/shorts/3f5G8kL9XYZ") is True
    assert is_youtube_url("https://youtu.be/3f5G8kL9XYZ") is True
    assert is_youtube_url("https://www.instagram.com/reel/12345") is False
    assert is_youtube_url("Some text without links") is False

def test_extract_promoted_urls_from_text():
    sample_text = (
        "Check out our full course at https://boot.dev/pricing! "
        "Also follow us on https://youtube.com/c/bootdev and https://instagram.com/bootdev. "
        "Get extra discounts at https://courses.example.org/discount"
    )
    urls = extract_promoted_urls_from_text(sample_text)
    assert "https://boot.dev/pricing" in urls
    assert "https://courses.example.org/discount" in urls
    # Social platforms should be filtered out
    assert not any("youtube.com" in u for u in urls)
    assert not any("instagram.com" in u for u in urls)

def test_fetch_youtube_metadata_with_data_api():
    video_id = "test_vid_123"
    fake_api_response = {
        "items": [{
            "snippet": {
                "title": "Top 5 Free Coding Bootcamps in 2026",
                "description": "Learn coding with 100% free certificates at https://boot.dev",
                "channelTitle": "TechReviewer",
                "thumbnails": {
                    "high": {"url": "https://i.ytimg.com/vi/test_vid_123/hqdefault.jpg"}
                }
            }
        }]
    }

    with patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = fake_api_response

        meta = fetch_youtube_metadata(video_id, api_key="AIzaSyFakeKey123")
        assert meta["title"] == "Top 5 Free Coding Bootcamps in 2026"
        assert "https://boot.dev" in meta["description"]
        assert meta["channel_title"] == "TechReviewer"
        assert "hqdefault.jpg" in meta["thumbnail_url"]

def test_fetch_youtube_metadata_oembed_fallback():
    video_id = "test_vid_456"
    fake_oembed_response = {
        "title": "Learn Python Free in 60 Seconds",
        "author_name": "CodeQuick",
        "thumbnail_url": "https://i.ytimg.com/vi/test_vid_456/hqdefault.jpg"
    }

    # When no API key is provided, oEmbed is used
    with patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = fake_oembed_response

        meta = fetch_youtube_metadata(video_id, api_key=None)
        assert meta["title"] == "Learn Python Free in 60 Seconds"
        assert meta["channel_title"] == "CodeQuick"
        assert meta["thumbnail_url"] == "https://i.ytimg.com/vi/test_vid_456/hqdefault.jpg"

def test_fetch_youtube_transcript_mocked():
    video_id = "test_transcript_vid"

    with patch("youtube_transcript_api.YouTubeTranscriptApi.fetch") as mock_fetch:
        mock_snippet1 = MagicMock()
        mock_snippet1.text = "Hey guys, today I am showing you this course."
        mock_snippet2 = MagicMock()
        mock_snippet2.text = "It is completely free and includes a full refund policy."
        mock_fetch.return_value = [mock_snippet1, mock_snippet2]

        transcript = fetch_youtube_transcript(video_id)
        assert "Hey guys" in transcript
        assert "completely free and includes a full refund policy" in transcript

def test_ingest_youtube_short_orchestrator():
    url = "https://www.youtube.com/shorts/abc12345678"

    with patch("app.youtube.fetch_youtube_metadata") as mock_meta, \
         patch("app.youtube.fetch_youtube_transcript") as mock_trans:

        mock_meta.return_value = {
            "title": "Free Full-Stack Bootcamp",
            "description": "Enroll today at https://boot.dev/pricing",
            "channel_title": "DeveloperGuide",
            "thumbnail_url": "https://i.ytimg.com/vi/abc12345678/hqdefault.jpg"
        }
        mock_trans.return_value = "Boot dev offers free interactive tracks and a 30-day refund window."

        res = ingest_youtube_short(url)
        assert res.video_id == "abc12345678"
        assert res.title == "Free Full-Stack Bootcamp"
        assert res.detected_site == "https://boot.dev/pricing"
        assert "Audio Transcript:" in res.combined_text
        assert res.status == "success"

def test_ingest_youtube_endpoint_api():
    with patch("app.main.ingest_youtube_short") as mock_ingest:
        mock_ingest.return_value = YouTubeIngestResult(
            video_id="xyz98765432",
            video_url="https://www.youtube.com/shorts/xyz98765432",
            title="Python Course Reel",
            description="Link: https://python.org",
            channel_title="PythonCoder",
            thumbnail_url="https://i.ytimg.com/vi/xyz98765432/hqdefault.jpg",
            transcript="Python is 100% open source and free forever.",
            combined_text="Video Title: Python Course Reel\n\nAudio Transcript:\nPython is 100% open source and free forever.",
            detected_site="https://python.org",
            status="success"
        )

        response = client.post("/ingest-youtube", json={"video_url": "https://www.youtube.com/shorts/xyz98765432"})
        assert response.status_code == 200
        data = response.json()
        assert data["video_id"] == "xyz98765432"
        assert data["title"] == "Python Course Reel"
        assert data["detected_site"] == "https://python.org"
        assert "open source" in data["transcript"]

def test_audit_reel_youtube_url_only_submission():
    with patch("app.main.ingest_youtube_short") as mock_ingest, \
         patch("app.main.extract_claims") as mock_extract, \
         patch("app.main.crawl_site") as mock_crawl, \
         patch("app.main.gather_all_evidence") as mock_gather, \
         patch("app.main.cross_check_claims") as mock_check:

        mock_ingest.return_value = YouTubeIngestResult(
            video_id="short1234567",
            video_url="https://www.youtube.com/shorts/short1234567",
            title="Free Trial Reel",
            description="Visit https://example.com/trial",
            channel_title="SaaSReviewer",
            thumbnail_url="https://i.ytimg.com/vi/short1234567/hqdefault.jpg",
            transcript="Get a 14-day free trial on example.com with no credit card required.",
            combined_text="Video Title: Free Trial Reel\n\nTranscript: Get a 14-day free trial on example.com with no credit card required.",
            detected_site="https://example.com/trial",
            status="success"
        )

        mock_extract.return_value.promoted_site = "https://example.com/trial"
        mock_extract.return_value.claims = [
            Claim(text="14-day free trial with no credit card required", category="discount", source_type="caption", confidence="high")
        ]

        mock_crawl.return_value.crawl_status = "success"
        mock_crawl.return_value.facts = []
        mock_gather.return_value = []

        mock_check.return_value = CheckResponse(
            confidence_tier="LIKELY_TRUE",
            coverage_status="verified",
            summary_label="14-day trial confirmed on site",
            score_breakdown=ScoreBreakdown(confirmed_count=1, total_claims=1, addressed_claims=1),
            verdicts=[
                ClaimVerdict(
                    claim_text="14-day free trial with no credit card required",
                    category="discount",
                    source_type="caption",
                    verdict="confirmed",
                    evidence_text="Start your 14-day free trial now, no credit card required.",
                    source_url="https://example.com/trial",
                    reasoning="Confirmed on landing page.",
                    is_self_attested=True,
                    evidence_source="site_crawl",
                    trust_weight=0.5
                )
            ]
        )

        # Submit with ONLY video_url (no caption, no override_url)
        response = client.post("/audit-reel", json={"video_url": "https://www.youtube.com/shorts/short1234567"})
        assert response.status_code == 200
        data = response.json()
        assert data["promoted_site"] == "https://example.com/trial"
        assert len(data["claims"]) == 1
        assert data["youtube_metadata"] is not None
        assert data["youtube_metadata"]["video_id"] == "short1234567"
        assert data["youtube_metadata"]["title"] == "Free Trial Reel"
        assert data["check_result"]["confidence_tier"] == "LIKELY_TRUE"

def test_audit_reel_no_input_returns_422():
    response = client.post("/audit-reel", json={})
    assert response.status_code == 422
