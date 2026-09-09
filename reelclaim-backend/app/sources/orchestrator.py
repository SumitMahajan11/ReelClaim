import logging
from typing import List, Optional, Dict, Any

from app.models import Claim
from app.sources.base import Fact, EvidenceSource
from app.sources.site_crawl import SiteCrawlSource
from app.sources.cross_reference import CrossReferenceSource
from app.sources.wayback import WaybackSource
from app.sources.whois import WhoisSource

logger = logging.getLogger("reelclaim.sources.orchestrator")

DEFAULT_SOURCES = [
    SiteCrawlSource(),
    WhoisSource(),
    WaybackSource(),
    CrossReferenceSource()
]

def gather_all_evidence(
    claims: List[Claim],
    target_url: Optional[str] = None,
    api_key: Optional[str] = None,
    sources: Optional[List[EvidenceSource]] = None,
    **kwargs
) -> List[Fact]:
    """
    Orchestrates evidence gathering across all pluggable EvidenceSource implementations.
    Executes each source with defensive exception barriers so failures degrade gracefully.
    """
    active_sources = sources or DEFAULT_SOURCES
    all_facts: List[Fact] = []

    for source in active_sources:
        try:
            # For sources that can process per claim or globally
            if source.source_name == "cross_reference":
                # For cross-reference, fetch for each claim to get targeted 3rd-party evidence
                for claim in claims:
                    facts = source.fetch(claim, target_url=target_url, api_key=api_key, **kwargs)
                    all_facts.extend(facts)
            elif claims:
                # SiteCrawl, Whois, and Wayback can run with the first claim or overarching target_url
                facts = source.fetch(claims[0], target_url=target_url, api_key=api_key, **kwargs)
                all_facts.extend(facts)
            elif target_url:
                # Fallback if no claims were extracted yet
                dummy_claim = Claim(category="other", text=target_url, confidence="low")
                facts = source.fetch(dummy_claim, target_url=target_url, api_key=api_key, **kwargs)
                all_facts.extend(facts)
        except Exception as e:
            logger.warning(f"Evidence source '{source.source_name}' failed gracefully: {e}")
            continue

    return all_facts
