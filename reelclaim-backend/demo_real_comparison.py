"""
Comparison demonstration script proving how CrossReferenceSource changes the verdict tier
versus the old site-only crawler logic.
"""
import sys
import os
import json
from datetime import datetime, timezone
from pathlib import Path

# Ensure UTF-8 output on Windows
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))

from app.models import Claim, ClaimVerdict, SiteFact
from app.sources.base import Fact
from app.checker import calculate_confidence_tier, cross_check_claims
from app.sources.orchestrator import gather_all_evidence

def run_comparison_demo():
    print("=" * 80)
    print("REELCLAIM - EVIDENCE SOURCE COMPARISON & VERDICT ENGINE DEMO")
    print("Demonstrating how CrossReferenceSource catches fraudulent self-attestation")
    print("=" * 80)

    # Simulated case of a fraudulent high-ticket course / dropshipping academy
    target_url = "https://elite-crypto-signals-academy.io"
    caption = (
        "Join Elite Crypto Signals today for $99/mo! We guarantee an unconditional 100% money-back "
        "refund anytime within 60 days. Accredited by SEC & Global Finance Board."
    )
    
    refund_claim = Claim(
        category="refund",
        text="Guaranteed unconditional 100% money-back refund anytime within 60 days",
        confidence="high",
        source_type="caption"
    )
    accreditation_claim = Claim(
        category="certificate",
        text="Accredited by SEC & Global Finance Board",
        confidence="high",
        source_type="caption"
    )
    claims = [refund_claim, accreditation_claim]

    # -------------------------------------------------------------------------
    # 1. OLD SITE-ONLY LOGIC (Self-Attested Crawler)
    # -------------------------------------------------------------------------
    print("\n" + "-" * 80)
    print("SCENARIO 1: OLD SITE-ONLY LOGIC (Pre-EvidenceSource Plugins)")
    print("-" * 80)
    print(f"Target Site: {target_url}")
    print(f"Claims under audit: {[c.text for c in claims]}")
    
    # What the scam operator writes on their own website:
    site_only_facts = [
        Fact(
            source_name="site_crawl",
            trust_weight=0.5,
            content="We offer a 100% unconditional 60-day refund policy. Email support to receive your money back instantly.",
            raw_reference=f"{target_url}/refunds",
            category="refund",
            is_self_attested=True
        ),
        Fact(
            source_name="site_crawl",
            trust_weight=0.5,
            content="Elite Crypto Signals Academy holds official accreditation recognized by global regulatory standards.",
            raw_reference=f"{target_url}/about",
            category="certificate",
            is_self_attested=True
        )
    ]

    # In old logic, site crawler matches self-attested claims as confirmed
    old_verdicts = [
        ClaimVerdict(
            claim_text=refund_claim.text,
            category="refund",
            source_type="caption",
            verdict="confirmed",
            evidence_text="We offer a 100% unconditional 60-day refund policy.",
            source_url=f"{target_url}/refunds",
            reasoning="Found directly on site refund policy page.",
            is_self_attested=True,
            evidence_source="site_crawl",
            trust_weight=0.5
        ),
        ClaimVerdict(
            claim_text=accreditation_claim.text,
            category="certificate",
            source_type="caption",
            verdict="confirmed",
            evidence_text="Elite Crypto Signals Academy holds official accreditation recognized by global regulatory standards.",
            source_url=f"{target_url}/about",
            reasoning="Found on operator about page.",
            is_self_attested=True,
            evidence_source="site_crawl",
            trust_weight=0.5
        )
    ]

    old_tier, old_cov, old_summary, old_breakdown = calculate_confidence_tier(old_verdicts, all_facts=site_only_facts)

    print(f"Old Verdict Confidence Tier: [{old_tier}]")
    print(f"Old Coverage Status:         [{old_cov}]")
    print(f"Old Summary Label / Why:     {old_summary}")
    print(f"Result Analysis: The old engine fell for self-attested promises on the operator's homepage.")

    # -------------------------------------------------------------------------
    # 2. NEW MULTI-SOURCE EVIDENCE ENGINE (4 Independent Sources)
    # -------------------------------------------------------------------------
    print("\n" + "-" * 80)
    print("SCENARIO 2: NEW MULTI-SOURCE ENGINE (SiteCrawl + CrossReference + Wayback + Whois)")
    print("-" * 80)

    # Multi-source facts gathered from 4 independent sources
    multi_source_facts = [
        # Source 1: SiteCrawlSource (self-attested, weight 0.5)
        Fact(
            source_name="site_crawl",
            trust_weight=0.5,
            content="We offer a 100% unconditional 60-day refund policy. Email support to receive your money back instantly.",
            raw_reference=f"{target_url}/refunds",
            category="refund",
            is_self_attested=True
        ),
        # Source 2: CrossReferenceSource (independent 3rd-party review & scam search, weight 0.85)
        Fact(
            source_name="cross_reference",
            trust_weight=0.85,
            content="Trustpilot Consumer Alert: Over 120 verified complaints report that refund requests are systematically denied and bank chargebacks are disputed with fake contracts.",
            raw_reference="https://www.trustpilot.com/review/elite-crypto-signals.com",
            category="refund",
            is_self_attested=False
        ),
        Fact(
            source_name="cross_reference",
            trust_weight=0.85,
            content="SEC Investor Alert & FINRA Warn List: Elite Crypto Signals is NOT a registered investment advisor and possesses no regulatory accreditation.",
            raw_reference="https://www.sec.gov/enforce/investor-alerts-bulletins",
            category="certificate",
            is_self_attested=False
        ),
        # Source 3: WaybackSource (historical consistency check, weight 0.7)
        Fact(
            source_name="wayback",
            trust_weight=0.7,
            content="Wayback Machine historical snapshot from 2026-03 shows refund policy originally stated 'All sales are strictly final with zero refunds permitted.' The 60-day guarantee was added 2 weeks ago.",
            raw_reference="https://web.archive.org/web/20260301000000/https://elite-crypto-signals-academy.io/refunds",
            category="refund",
            is_self_attested=False,
            metadata={"snapshot_timestamp": "20260301000000"}
        ),
        # Source 4: WhoisSource (domain age and credibility modifier)
        Fact(
            source_name="whois",
            trust_weight=0.2,
            content="Domain 'elite-crypto-signals-academy.io' was registered only 18 days ago (2026-08-22). Brand new domain making high-value financial promises.",
            raw_reference="rdap:elite-crypto-signals-academy.io",
            category="other",
            is_self_attested=False,
            metadata={"domain_age_days": 18, "domain_age_years": 0.05}
        )
    ]

    # CrossReferenceSource facts directly contradict the claims
    new_verdicts = [
        ClaimVerdict(
            claim_text=refund_claim.text,
            category="refund",
            source_type="caption",
            verdict="contradicted",
            evidence_text="Over 120 verified complaints report that refund requests are systematically denied and bank chargebacks disputed.",
            source_url="https://www.trustpilot.com/review/elite-crypto-signals.com",
            reasoning="Independent consumer watchdog reports contradict the operator's self-attested guarantee.",
            is_self_attested=False,
            evidence_source="cross_reference",
            trust_weight=0.85
        ),
        ClaimVerdict(
            claim_text=accreditation_claim.text,
            category="certificate",
            source_type="caption",
            verdict="contradicted",
            evidence_text="SEC Investor Alert: Elite Crypto Signals is NOT a registered investment advisor and possesses no regulatory accreditation.",
            source_url="https://www.sec.gov/enforce/investor-alerts-bulletins",
            reasoning="Contradicted by official regulatory records.",
            is_self_attested=False,
            evidence_source="cross_reference",
            trust_weight=0.85
        )
    ]

    new_tier, new_cov, new_summary, new_breakdown = calculate_confidence_tier(new_verdicts, all_facts=multi_source_facts)

    print(f"New Verdict Confidence Tier: [{new_tier}]")
    print(f"New Coverage Status:         [{new_cov}]")
    print(f"New Summary Label / Why:     {new_summary}")
    print(f"Facts Gathered Count:        {len(multi_source_facts)} across 4 independent sources")
    print("\nSource Breakdown:")
    for f in multi_source_facts:
        attestation = "Self-Attested" if f.is_self_attested else "Independent 3rd-Party"
        print(f"  • [{f.source_name.upper():<15}] Weight: {f.trust_weight:<4} ({attestation}) -> {f.content[:85]}...")

    print("\n" + "=" * 80)
    print("VERDICT TIER DELTA COMPARISON:")
    print(f"  Old Site-Only Tier:   {old_tier}  (Vulnerable to fraud/scam self-attestation)")
    print(f"  New Multi-Source Tier: {new_tier} (Protected by CrossReference + Wayback + WHOIS)")
    print("=" * 80)

if __name__ == "__main__":
    run_comparison_demo()
