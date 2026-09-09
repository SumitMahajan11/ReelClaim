import logging
from typing import List, Optional
from datetime import datetime, timezone

from app.models import Claim
from app.sources.base import EvidenceSource, Fact
from app.crawler import crawl_site

logger = logging.getLogger("reelclaim.sources.site_crawl")

class SiteCrawlSource:
    """
    EvidenceSource implementation that crawls the promoter's target website
    using the existing 2-tier (Requests + Playwright) crawler.
    Assigns medium trust weight (0.5) because facts are self-attested.
    """
    source_name: str = "site_crawl"
    base_trust_weight: float = 0.5

    def fetch(self, claim: Claim, target_url: Optional[str] = None, api_key: Optional[str] = None, **kwargs) -> List[Fact]:
        """
        Crawls the target site (or uses pre-crawled facts if supplied in kwargs)
        and converts SiteFact objects to standardized Fact instances.
        """
        if not target_url:
            return []

        # If pre-crawled facts were passed in kwargs (for efficiency across multiple claims)
        precrawled_facts = kwargs.get("site_facts")
        if precrawled_facts is not None:
            return self._convert_site_facts(precrawled_facts)

        try:
            crawl_response = crawl_site(target_url, api_key=api_key)
            if crawl_response.crawl_status in ["blocked", "failed", "no_url_found"]:
                logger.info(f"Site crawl status for {target_url}: {crawl_response.crawl_status}")
                return []
            return self._convert_site_facts(crawl_response.facts)
        except Exception as e:
            logger.warning(f"SiteCrawlSource fetch failed gracefully for {target_url}: {e}")
            return []

    def _convert_site_facts(self, site_facts: list) -> List[Fact]:
        facts: List[Fact] = []
        now = datetime.now(timezone.utc)
        for sf in site_facts:
            category = getattr(sf, "category", "other")
            text = getattr(sf, "text", "")
            source_page = getattr(sf, "source_page", "home")
            source_url = getattr(sf, "source_url", "")
            is_self_attested = getattr(sf, "is_self_attested", True)

            if text and text.strip():
                facts.append(
                    Fact(
                        source_name=self.source_name,
                        trust_weight=self.base_trust_weight,
                        content=text.strip(),
                        retrieved_at=now,
                        raw_reference=source_url or "target_site",
                        category=category,
                        is_self_attested=is_self_attested,
                        metadata={
                            "source_page": source_page,
                            "source_url": source_url
                        }
                    )
                )
        return facts
