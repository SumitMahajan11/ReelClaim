import os
import uuid
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.models import Claim, CheckResponse, ScoreBreakdown
from app.db import save_audit_record, get_audit_record_by_id

client = TestClient(app)

def test_submit_feedback_success():
    """Submitter can successfully flag a verdict on their own audit using submitter_token."""
    submitter_token = f"sub_{uuid.uuid4().hex}"
    audit_id = save_audit_record(
        caption="Earn $500/day guaranteed with zero work at fakebot.io",
        promoted_site="https://fakebot.io",
        override_url=None,
        claims=[{"text": "Guaranteed $500/day", "category": "salary", "confidence": "high", "source_type": "caption"}],
        crawl_status="success",
        check_result=CheckResponse(
            confidence_tier="CONTRADICTED",
            coverage_status="verified",
            summary_label="Contradicted: 1 contradicted",
            score_breakdown=ScoreBreakdown(confirmed_count=0, partial_count=0, contradicted_count=1, not_found_count=0, addressed_claims=1, total_claims=1),
            verdicts=[{
                "claim_text": "Guaranteed $500/day",
                "category": "salary",
                "source_type": "caption",
                "verdict": "contradicted",
                "evidence_text": "No income is guaranteed",
                "source_url": "https://fakebot.io/terms",
                "reasoning": "Terms explicitly state earnings are not guaranteed.",
                "is_self_attested": True
            }]
        ),
        submitter_token=submitter_token
    )

    feedback_payload = {
        "claim_index": 0,
        "feedback_type": "wrong_verdict",
        "expected_verdict": "confirmed",
        "user_notes": "The video actually referred to the affiliate promotion tier, not standard tier.",
        "submitter_token": submitter_token
    }

    resp = client.post(f"/audits/{audit_id}/feedback", json=feedback_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "recorded"
    assert data["audit_id"] == audit_id
    assert "feedback_id" in data

    # Verify audit record now contains the feedback
    audit_data = get_audit_record_by_id(audit_id)
    if audit_data:
        assert len(audit_data["feedback"]) >= 1
        fb = audit_data["feedback"][-1]
        assert fb["claim_index"] == 0
        assert fb["feedback_type"] == "wrong_verdict"
        assert fb["expected_verdict"] == "confirmed"
        assert "affiliate promotion" in fb["user_notes"]

def test_submit_feedback_via_header():
    """Submitter token passed via X-Submitter-Token header is accepted."""
    submitter_token = f"sub_{uuid.uuid4().hex}"
    audit_id = save_audit_record(
        caption="Free certificates for everyone",
        promoted_site="https://example.org",
        override_url=None,
        claims=[],
        crawl_status="success",
        check_result=None,
        submitter_token=submitter_token
    )

    feedback_payload = {
        "claim_index": None,
        "feedback_type": "missed_evidence",
        "expected_verdict": "VERIFIED",
        "user_notes": "Missed the certificate link in footer."
    }

    resp = client.post(
        f"/audits/{audit_id}/feedback",
        json=feedback_payload,
        headers={"X-Submitter-Token": submitter_token}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "recorded"

def test_submit_feedback_unauthorized_token_rejected():
    """Submitter token mismatch returns HTTP 403 Forbidden."""
    correct_token = f"sub_{uuid.uuid4().hex}"
    attacker_token = f"sub_wrongtoken12345"

    audit_id = save_audit_record(
        caption="Some private audit",
        promoted_site="https://example.com",
        override_url=None,
        claims=[],
        crawl_status="success",
        check_result=None,
        submitter_token=correct_token
    )

    feedback_payload = {
        "claim_index": 0,
        "feedback_type": "wrong_verdict",
        "submitter_token": attacker_token
    }

    resp = client.post(f"/audits/{audit_id}/feedback", json=feedback_payload)
    assert resp.status_code == 403
    assert "Forbidden" in resp.json()["detail"]

def test_submit_feedback_nonexistent_audit_404():
    """Submitting feedback for non-existent audit ID returns HTTP 404."""
    fake_id = str(uuid.uuid4())
    resp = client.post(
        f"/audits/{fake_id}/feedback",
        json={"feedback_type": "other", "user_notes": "test"}
    )
    assert resp.status_code == 404
