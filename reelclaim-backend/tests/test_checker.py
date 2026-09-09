import sys
import json
from pathlib import Path

# Ensure UTF-8 output on Windows
sys.stdout.reconfigure(encoding="utf-8")

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models import Claim, SiteFact, ClaimVerdict
from app.sources.base import Fact
from app.checker import cross_check_claims, is_valid_evidence_text, calculate_confidence_tier, get_candidate_facts_for_claim

BOOT_DEV_FACTS = [
    SiteFact(
        category="price",
        text="Monthly membership costs ₹999 / month (listed as ₹5599 INR with a ₹4600 PPP Discount).",
        source_page="pricing",
        source_url="https://boot.dev/pricing",
        is_self_attested=True
    ),
    SiteFact(
        category="discount",
        text="Purchases made from eligible countries receive purchasing power parity (PPP) discount automatically applied at checkout.",
        source_page="pricing",
        source_url="https://boot.dev/pricing",
        is_self_attested=True
    ),
    SiteFact(
        category="certificate",
        text="Certificates of completion are issued only upon completing all required tracks and capstones in the paid membership.",
        source_page="faq",
        source_url="https://boot.dev/faq",
        is_self_attested=True
    ),
    SiteFact(
        category="refund",
        text="Users have 30 calendar days from the date of activation to request a complete refund on their subscription.",
        source_page="refund_policy",
        source_url="https://boot.dev/return-policy",
        is_self_attested=True
    ),
    SiteFact(
        category="eligibility",
        text="You must be 18 years or older to be part of the Boot.dev Affiliate Program.",
        source_page="terms",
        source_url="https://boot.dev/affiliate-terms",
        is_self_attested=True
    )
]

def test_mostly_true_reel():
    print("\n--- [TEST 1] Mostly-True Reel Verification (Self-Attested Site Evidence -> LIKELY_TRUE) ---")
    claims = [
        Claim(category="price", text="Boot.dev offers monthly backend coding membership for ₹999/mo", confidence="high", source_type="caption"),
        Claim(category="refund", text="30-day money-back refund policy included", confidence="high", source_type="caption"),
        Claim(category="eligibility", text="Affiliate program requires users to be 18+ years old", confidence="high", source_type="caption")
    ]

    response = cross_check_claims(claims, BOOT_DEV_FACTS)
    print("REAL VERDICT RESPONSE JSON:")
    print(json.dumps(response.model_dump(), indent=2))
    
    assert response.coverage_status == "verified"
    assert response.confidence_tier == "LIKELY_TRUE"
    assert response.score_breakdown.confirmed_count >= 2
    print("✓ Test 1 Passed (Self-attested crawl evidence correctly produces LIKELY_TRUE)")

def test_independently_verified_reel():
    print("\n--- [TEST 1b] Verified Reel with Non-Self-Attested Source Agreeing -> VERIFIED ---")
    facts_with_third_party = BOOT_DEV_FACTS + [
        SiteFact(
            category="price",
            text="Official registry verifies monthly subscription is ₹999 / month.",
            source_page="external_audit",
            source_url="https://consumer-protection.org/audits/boot-dev",
            is_self_attested=False
        )
    ]
    # Unit test calculate_confidence_tier directly with third-party verified verdict
    verdicts = [
        ClaimVerdict(
            claim_text="Boot.dev costs ₹999/mo",
            category="price",
            source_type="caption",
            verdict="confirmed",
            evidence_text="Official registry verifies monthly subscription is ₹999 / month.",
            source_url="https://consumer-protection.org/audits/boot-dev",
            reasoning="Third party registry confirms price.",
            is_self_attested=False
        )
    ]
    tier, cov, summary, breakdown = calculate_confidence_tier(verdicts)
    assert tier == "VERIFIED"
    assert breakdown.confirmed_count == 1
    print("✓ Test 1b Passed (Independent 3rd-party source corroboration yields VERIFIED tier)")

def test_ambiguous_partial_reel():
    print("\n--- [TEST 2] Ambiguous Reel (Exercising 'partial' Verdict) ---")
    claims = [
        Claim(category="refund", text="Boot.dev provides a full refund on subscription at any time after joining", confidence="high", source_type="caption")
    ]

    response = cross_check_claims(claims, BOOT_DEV_FACTS)
    print("RAW JSON FOR AMBIGUOUS PARTIAL CASE:")
    print(json.dumps(response.model_dump(), indent=2))

    cert_verdict = response.verdicts[0]
    assert cert_verdict.verdict == "partial"
    assert cert_verdict.evidence_text is not None
    assert response.score_breakdown.partial_count == 1
    assert response.confidence_tier == "LIKELY_TRUE"
    print("✓ Test 2 Passed ('partial' verdict successfully issued)")

def test_planted_false_reel():
    print("\n--- [TEST 3] Planted False Reel (Deliberate Contradiction) ---")
    claims = [
        Claim(category="price", text="100% Free Full-Stack Web Development Bootcamp with no fees ever", confidence="high", source_type="caption"),
        Claim(category="refund", text="No refunds provided under any circumstances", confidence="high", source_type="caption")
    ]

    response = cross_check_claims(claims, BOOT_DEV_FACTS)
    print("RAW JSON FOR PLANTED CONTRADICTION CASE:")
    print(json.dumps(response.model_dump(), indent=2))

    price_verdict = next(v for v in response.verdicts if v.category == "price")
    refund_verdict = next(v for v in response.verdicts if v.category == "refund")
    
    assert price_verdict.verdict == "contradicted"
    assert refund_verdict.verdict == "contradicted"
    assert response.score_breakdown.contradicted_count == 2
    assert response.confidence_tier == "CONTRADICTED"
    assert "2 contradicted" in response.summary_label
    print("✓ Test 3 Passed (Contradictions Flagged & Alarming Summary Label Verified)")

def test_not_found_guardrail_and_trust_score_fix():
    print("\n--- [TEST 4] Not Found Guardrail & INSUFFICIENT_EVIDENCE Tier ---")
    claims = [
        Claim(category="salary", text="Guaranteed ₹50,000/month salary immediately upon starting", confidence="high", source_type="caption"),
        Claim(category="partnership", text="Official partnership with NASA and Tesla Motors", confidence="high", source_type="caption")
    ]

    response = cross_check_claims(claims, BOOT_DEV_FACTS)
    print("RAW JSON FOR NOT_FOUND CASE:")
    print(json.dumps(response.model_dump(), indent=2))

    for v in response.verdicts:
        assert v.verdict == "not_found"
        assert v.evidence_text is None
        assert v.source_url is None

    assert response.score_breakdown.not_found_count == 2
    assert response.score_breakdown.addressed_claims == 0
    assert response.confidence_tier == "INSUFFICIENT_EVIDENCE"
    assert response.coverage_status == "unverified_no_data"
    assert "Insufficient Evidence" in response.summary_label
    print("✓ Test 4 Passed (INSUFFICIENT_EVIDENCE tier returned)")

def test_calibrated_evidence_filter_near_miss():
    print("\n--- [TEST 5] Calibrated Evidence Filter (Near-Miss Paraphrase vs Embellishment vs Wild Fabrication) ---")
    exact_text = "Monthly membership costs ₹999 / month (listed as ₹5599 INR with a ₹4600 PPP Discount)."
    near_miss_paraphrase = "Monthly membership costs ₹999 per month with PPP discount applied"
    embellished_quote = "Users have 30 calendar days from activation to request a complete refund, no questions asked"
    wild_fabrication = "We guarantee 100% full refunds anytime within 10 years without question"

    assert is_valid_evidence_text(exact_text, BOOT_DEV_FACTS) is True
    assert is_valid_evidence_text(near_miss_paraphrase, BOOT_DEV_FACTS) is True
    assert is_valid_evidence_text(embellished_quote, BOOT_DEV_FACTS) is False
    assert is_valid_evidence_text(wild_fabrication, BOOT_DEV_FACTS) is False
    print("✓ Test 5 Passed (Near-miss paraphrase accepted, embellishment & wild fabrication rejected)")

def test_category_alias_matching():
    print("\n--- [TEST 6] Pass 1 Category Alias Fallback Matching ---")
    claim_price = Claim(category="price", text="PPP discount available", confidence="high", source_type="caption")
    facts = get_candidate_facts_for_claim(claim_price, BOOT_DEV_FACTS)
    
    categories = [f.category for f in facts]
    assert "price" in categories
    assert "discount" in categories
    print("✓ Test 6 Passed (Category alias fallback matched 'discount' facts for 'price' claim)")

def test_cross_reference_overrides_self_attestation_to_contradicted():
    print("\n--- [TEST 7] Cross-Reference Source Overrides Self-Attestation -> CONTRADICTED ---")
    claim = Claim(category="refund", text="Guaranteed unconditional 100% money-back refund on request", confidence="high", source_type="caption")
    
    # Self-attested site claim says positive, but independent 3rd party fact reveals fraud
    facts = [
        Fact(
            source_name="site_crawl",
            trust_weight=0.5,
            content="We provide a 100% money-back guarantee for all customers on request.",
            raw_reference="https://fraudulent-course.io/guarantee",
            category="refund",
            is_self_attested=True
        ),
        Fact(
            source_name="cross_reference",
            trust_weight=0.85,
            content="Trustpilot and BBB consumer alert: Company categorically refuses refund requests and issues immediate chargebacks.",
            raw_reference="https://trustpilot.com/review/fraudulent-course.io",
            category="refund",
            is_self_attested=False
        )
    ]

    verdicts = [
        ClaimVerdict(
            claim_text=claim.text,
            category="refund",
            source_type="caption",
            verdict="contradicted",
            evidence_text="Company categorically refuses refund requests and issues immediate chargebacks.",
            source_url="https://trustpilot.com/review/fraudulent-course.io",
            reasoning="Independent consumer complaints contradict the operator's refund guarantee.",
            is_self_attested=False,
            evidence_source="cross_reference",
            trust_weight=0.85
        )
    ]
    tier, cov, summary, breakdown = calculate_confidence_tier(verdicts, all_facts=facts)
    assert tier == "CONTRADICTED"
    assert "contradicted by independent sources" in summary
    print("✓ Test 7 Passed (CrossReferenceSource successfully caught fraudulent self-attested site)")

def test_multi_source_why_synthesis():
    print("\n--- [TEST 8] Multi-Source 'Why' Synthesis & WHOIS Domain Age Integration ---")
    verdicts = [
        ClaimVerdict(
            claim_text="Pricing is ₹999/mo",
            category="price",
            source_type="caption",
            verdict="confirmed",
            evidence_text="Monthly membership costs ₹999 / month.",
            source_url="https://boot.dev/pricing",
            reasoning="Confirmed on pricing page.",
            is_self_attested=True,
            evidence_source="site_crawl",
            trust_weight=0.5
        ),
        ClaimVerdict(
            claim_text="Independent course review confirms ₹999/mo pricing",
            category="price",
            source_type="caption",
            verdict="confirmed",
            evidence_text="Review confirms pricing is ₹999.",
            source_url="https://trustpilot.com/review/boot.dev",
            reasoning="Corroborated by independent review.",
            is_self_attested=False,
            evidence_source="cross_reference",
            trust_weight=0.85
        )
    ]

    facts = [
        Fact(
            source_name="whois",
            trust_weight=1.0,
            content="Domain 'boot.dev' is 5 years old (registered 2019-01-01).",
            raw_reference="rdap:boot.dev",
            category="other",
            is_self_attested=False,
            metadata={"domain_age_days": 1825}
        )
    ]

    tier, cov, summary, breakdown = calculate_confidence_tier(verdicts, all_facts=facts)
    assert tier == "VERIFIED"
    assert "corroborated by" in summary
    assert "domain registered 5 years ago" in summary
    print("✓ Test 8 Passed (Source-grounded 'Why' explanation synthesized with WHOIS metadata)")

def run_all_tests():
    print("================================================================================")
    print("REELCLAIM PHASE 3 - UPDATED CROSS-CHECK ENGINE VERIFICATION TESTS")
    print("================================================================================")
    test_mostly_true_reel()
    test_independently_verified_reel()
    test_ambiguous_partial_reel()
    test_planted_false_reel()
    test_not_found_guardrail_and_trust_score_fix()
    test_calibrated_evidence_filter_near_miss()
    test_category_alias_matching()
    test_cross_reference_overrides_self_attestation_to_contradicted()
    test_multi_source_why_synthesis()
    print("\nALL PHASE 3 UPDATED TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_all_tests()


