import re
import json
import logging
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from app.models import Claim, ClaimCategory
from app.sources.base import EvidenceSource, Fact

logger = logging.getLogger("reelclaim.sources.wayback")

WAYBACK_AVAILABILITY_API = "https://archive.org/wayback/available"
WAYBACK_CDX_API = "https://web.archive.org/cdx/search/cdx"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ReelClaimBot/1.0; +https://github.com/SumitMahajan11/ReelClaim)",
    "Accept": "application/json, text/html",
}

class WaybackSource:
    """
    EvidenceSource implementation querying the Wayback Machine's free API
    to inspect historical snapshots of the target domain and detect whether
    claims were recently altered, newly introduced, or removed.
    Trust weight: 0.70.
    """
    source_name: str = "wayback"
    base_trust_weight: float = 0.70

    def __init__(self, timeout: float = 4.0):
        self.timeout = timeout

    def fetch(self, claim: Claim, target_url: Optional[str] = None, api_key: Optional[str] = None, **kwargs) -> List[Fact]:
        if not target_url:
            return []

        # Allow passing mock snapshot info for testing
        mock_snapshot = kwargs.get("mock_snapshot")
        if mock_snapshot is not None:
            return self._analyze_snapshot(mock_snapshot, claim, target_url)

        snapshot_info = self._get_historical_snapshot(target_url)
        if not snapshot_info:
            return []

        return self._analyze_snapshot(snapshot_info, claim, target_url)

    def _get_historical_snapshot(self, target_url: str) -> Optional[Dict[str, Any]]:
        """
        Queries the Wayback Machine availability API for a snapshot from ~6-12 months prior.
        """
        try:
            # Query availability for 6 months ago
            timestamp_target = "20240101"
            resp = requests.get(
                WAYBACK_AVAILABILITY_API,
                params={"url": target_url, "timestamp": timestamp_target},
                headers=HEADERS,
                timeout=self.timeout
            )
            if resp.status_code != 200:
                return None

            data = resp.json()
            archived_snapshots = data.get("archived_snapshots", {})
            closest = archived_snapshots.get("closest")
            if closest and closest.get("available"):
                return {
                    "url": closest.get("url"),
                    "timestamp": closest.get("timestamp"),
                    "status": closest.get("status")
                }
            return None
        except Exception as e:
            logger.debug(f"Wayback Machine API check failed gracefully for {target_url}: {e}")
            return None

    def _analyze_snapshot(self, snapshot_info: Dict[str, Any], claim: Claim, target_url: str) -> List[Fact]:
        """
        Analyzes historical snapshot availability and content.
        """
        snapshot_url = snapshot_info.get("url", "")
        raw_ts = str(snapshot_info.get("timestamp", ""))
        
        # Format human-readable timestamp e.g. "2024-03-15"
        formatted_date = raw_ts[:8]
        if len(formatted_date) == 8:
            formatted_date = f"{formatted_date[:4]}-{formatted_date[4:6]}-{formatted_date[6:8]}"
        else:
            formatted_date = "prior snapshot"

        facts: List[Fact] = []
        now = datetime.now(timezone.utc)

        # If historical page content is provided or fetchable
        historical_text = snapshot_info.get("content_text")
        if not historical_text and snapshot_url:
            try:
                r = requests.get(snapshot_url, headers=HEADERS, timeout=self.timeout)
                if r.status_code == 200:
                    soup = BeautifulSoup(r.text, "html.parser")
                    for tag in soup(["script", "style", "nav", "footer"]):
                        tag.decompose()
                    historical_text = soup.get_text(separator=" ", strip=True)[:4000]
            except Exception:
                historical_text = None

        if historical_text:
            # Check for claim keywords in historical text
            claim_words = set(re.sub(r"[^\w\s]", "", claim.text).lower().split())
            hist_words = set(re.sub(r"[^\w\s]", "", historical_text).lower().split())
            common_words = claim_words.intersection(hist_words)
            overlap_ratio = len(common_words) / max(len(claim_words), 1)

            if overlap_ratio > 0.6:
                fact_content = f"Historical snapshot ({formatted_date}) contains consistent terms matching: '{claim.text[:80]}'."
                facts.append(
                    Fact(
                        source_name=self.source_name,
                        trust_weight=self.base_trust_weight,
                        content=fact_content,
                        retrieved_at=now,
                        raw_reference=snapshot_url,
                        category=claim.category,
                        is_self_attested=True,
                        metadata={
                            "snapshot_date": formatted_date,
                            "snapshot_url": snapshot_url,
                            "status": "historical_consistency"
                        }
                    )
                )
            else:
                fact_content = f"Historical snapshot ({formatted_date}) did not contain this claim. The promise appears newly added or materially changed."
                facts.append(
                    Fact(
                        source_name=self.source_name,
                        trust_weight=self.base_trust_weight,
                        content=fact_content,
                        retrieved_at=now,
                        raw_reference=snapshot_url,
                        category=claim.category,
                        is_self_attested=True,
                        metadata={
                            "snapshot_date": formatted_date,
                            "snapshot_url": snapshot_url,
                            "status": "newly_added_claim"
                        }
                    )
                )
        else:
            # Snapshot existence metadata fact
            facts.append(
                Fact(
                    source_name=self.source_name,
                    trust_weight=0.5,
                    content=f"Domain has historical archived web presence indexed on Wayback Machine as of {formatted_date}.",
                    retrieved_at=now,
                    raw_reference=snapshot_url or f"https://web.archive.org/web/*/{target_url}",
                    category="other",
                    is_self_attested=True,
                    metadata={
                        "snapshot_date": formatted_date,
                        "snapshot_url": snapshot_url
                    }
                )
            )

        return facts
