import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from app.models import Claim, ClaimCategory
from app.sources.base import Fact, EvidenceSource
from app.sources.site_crawl import SiteCrawlSource
from app.sources.cross_reference import CrossReferenceSource, is_operator_owned_url, extract_brand_or_domain_name
from app.sources.wayback import WaybackSource
from app.sources.whois import WhoisSource, extract_clean_domain
from app.sources.orchestrator import gather_all_evidence


def test_fact_model_properties():
    fact = Fact(
        source_name="cross_reference",
        trust_weight=0.85,
        content="Independent review on Trustpilot indicates hidden fees.",
        raw_reference="https://trustpilot.com/review/example.com",
        category="price",
        is_self_attested=False,
        metadata={"domain": "trustpilot.com"}
    )
    assert fact.text == "Independent review on Trustpilot indicates hidden fees."
    assert fact.source_url == "https://trustpilot.com/review/example.com"
    assert fact.source_page == "cross_reference"
    assert fact.is_self_attested is False
    assert fact.trust_weight == 0.85


def test_site_crawl_source_conversion():
    source = SiteCrawlSource()
    assert isinstance(source, EvidenceSource)
    assert source.source_name == "site_crawl"

    claim = Claim(category="price", text="Course costs $0", confidence="high")

    # Pass mock SiteFact items via kwargs
    from app.models import SiteFact
    mock_site_facts = [
        SiteFact(category="price", text="The hobby plan costs $0 per month.", source_page="pricing", source_url="https://example.com/pricing", is_self_attested=True)
    ]

    facts = source.fetch(claim, target_url="https://example.com", site_facts=mock_site_facts)
    assert len(facts) == 1
    assert facts[0].source_name == "site_crawl"
    assert facts[0].trust_weight == 0.5
    assert facts[0].is_self_attested is True
    assert "hobby plan costs $0" in facts[0].content


def test_cross_reference_operator_domain_filtering():
    target = "https://courses.fraudsite.io/enroll"
    assert is_operator_owned_url("https://fraudsite.io/about", target) is True
    assert is_operator_owned_url("https://help.fraudsite.io/terms", target) is True
    assert is_operator_owned_url("https://trustpilot.com/review/fraudsite.io", target) is False
    assert is_operator_owned_url("https://reddit.com/r/scams/comments/xyz", target) is False


def test_cross_reference_brand_extraction():
    assert extract_brand_or_domain_name("https://www.nextgenacademy.com/pricing") == "nextgenacademy"
    assert extract_brand_or_domain_name("https://boot.dev") == "boot"


def test_cross_reference_source_processing():
    source = CrossReferenceSource()
    assert isinstance(source, EvidenceSource)
    assert source.source_name == "cross_reference"

    claim = Claim(category="refund", text="100% money back guarantee with no questions asked", confidence="high")
    
    mock_snippets = [
        {
            "title": "NextGen Academy Scam Complaints - BBB Business Profile",
            "snippet": "Consumers report multiple issues getting refund requests honored after 30-day window.",
            "url": "https://bbb.org/reviews/nextgenacademy",
            "query": "nextgenacademy complaint"
        },
        {
            "title": "Official NextGen Academy Home Page",
            "snippet": "We guarantee our courses!",
            "url": "https://nextgenacademy.com",
            "query": "nextgenacademy review"
        }
    ]

    facts = source.fetch(
        claim,
        target_url="https://nextgenacademy.com",
        mock_search_results=mock_snippets
    )

    # Operator URL https://nextgenacademy.com should be filtered out!
    assert len(facts) == 1
    assert facts[0].source_name == "cross_reference"
    assert facts[0].trust_weight == 0.85
    assert facts[0].is_self_attested is False
    assert "bbb.org" in facts[0].raw_reference
    assert "refund requests" in facts[0].content.lower()


def test_wayback_source_analysis():
    source = WaybackSource()
    assert isinstance(source, EvidenceSource)
    assert source.source_name == "wayback"

    claim = Claim(category="price", text="Lifetime access is completely free", confidence="high")

    # Test 1: Historical snapshot contains matching text
    mock_snapshot_consistent = {
        "url": "https://web.archive.org/web/20230501/https://example.com",
        "timestamp": "20230501120000",
        "content_text": "Welcome to our portal where lifetime access is completely free for all verified students."
    }

    facts = source.fetch(claim, target_url="https://example.com", mock_snapshot=mock_snapshot_consistent)
    assert len(facts) == 1
    assert facts[0].source_name == "wayback"
    assert facts[0].metadata.get("status") == "historical_consistency"

    # Test 2: Historical snapshot does not contain newly added claim
    mock_snapshot_new_claim = {
        "url": "https://web.archive.org/web/20230501/https://example.com",
        "timestamp": "20230501120000",
        "content_text": "Standard paid tuition applies. Monthly subscription required."
    }
    facts_new = source.fetch(claim, target_url="https://example.com", mock_snapshot=mock_snapshot_new_claim)
    assert len(facts_new) == 1
    assert facts_new[0].metadata.get("status") == "newly_added_claim"


def test_whois_source_domain_age_modifiers():
    source = WhoisSource()
    assert isinstance(source, EvidenceSource)
    assert source.source_name == "whois"

    claim = Claim(category="salary", text="Guaranteed $150k tech job upon graduation", confidence="high")

    # 1. Established domain (registered in 2018)
    mock_rdap_old = {
        "events": [
            {"eventAction": "registration", "eventDate": "2018-01-15T00:00:00Z"}
        ],
        "entities": []
    }
    facts_old = source.fetch(claim, target_url="https://established-platform.com", mock_whois_data=mock_rdap_old)
    assert len(facts_old) == 1
    assert facts_old[0].trust_weight == 1.0
    assert "years old" in facts_old[0].content

    # 2. Brand new domain (registered 5 days ago)
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00Z")
    mock_rdap_new = {
        "events": [
            {"eventAction": "registration", "eventDate": now_iso}
        ],
        "entities": []
    }
    facts_new = source.fetch(claim, target_url="https://get-rich-quick-site.xyz", mock_whois_data=mock_rdap_new)
    assert len(facts_new) == 1
    assert facts_new[0].trust_weight == 0.20
    assert "brand new" in facts_new[0].content


def test_gather_all_evidence_orchestrator():
    claims = [
        Claim(category="price", text="Zero monthly costs", confidence="high")
    ]
    target_url = "https://example.com"

    mock_site_facts = [
        Fact(source_name="site_crawl", trust_weight=0.5, content="Free tier available", raw_reference="https://example.com", is_self_attested=True)
    ]

    all_facts = gather_all_evidence(claims, target_url=target_url, site_facts=mock_site_facts)
    # Orchestrator runs all 4 sources and returns a combined list of Fact items
    assert isinstance(all_facts, list)
    assert any(f.source_name == "site_crawl" for f in all_facts)


def test_source_failure_graceful_degradation():
    class FailingSource:
        source_name = "failing_api"
        def fetch(self, claim, target_url=None, **kwargs):
            raise ConnectionError("Upstream server timeout (504)")

    claims = [Claim(category="price", text="Test claim", confidence="low")]
    facts = gather_all_evidence(claims, target_url="https://example.com", sources=[FailingSource()])
    # Should not raise exception and return clean empty list
    assert facts == []
