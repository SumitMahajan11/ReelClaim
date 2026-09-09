import logging
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse
from datetime import datetime, timezone

import requests

from app.models import Claim
from app.sources.base import EvidenceSource, Fact

logger = logging.getLogger("reelclaim.sources.whois")

RDAP_BOOTSTRAP_URL = "https://rdap.org/domain/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ReelClaimBot/1.0; +https://github.com/SumitMahajan11/ReelClaim)",
    "Accept": "application/rdap+json, application/json",
}

def extract_clean_domain(url: str) -> str:
    if not url:
        return ""
    try:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        netloc = parsed.netloc.replace("www.", "").strip().lower()
        if not netloc:
            netloc = url.strip().lower()
        # Strip port if present
        if ":" in netloc:
            netloc = netloc.split(":")[0]
        return netloc
    except Exception:
        return url.strip().lower()

class WhoisSource:
    """
    EvidenceSource implementing free WHOIS/RDAP domain age lookup.
    Calculates domain age and returns a Fact with a numeric trust_weight modifier.
    (New domains registered < 30-90 days ago receive lower trust weights).
    """
    source_name: str = "whois"

    def __init__(self, timeout: float = 3.5):
        self.timeout = timeout

    def fetch(self, claim: Claim, target_url: Optional[str] = None, api_key: Optional[str] = None, **kwargs) -> List[Fact]:
        if not target_url:
            return []

        domain = extract_clean_domain(target_url)
        if not domain or "." not in domain:
            return []

        # Allow passing mock RDAP/WHOIS data for testing
        mock_data = kwargs.get("mock_whois_data")
        if mock_data is not None:
            return self._build_fact_from_rdap(domain, mock_data, claim)

        rdap_data = self._lookup_rdap(domain)
        if not rdap_data:
            return []

        return self._build_fact_from_rdap(domain, rdap_data, claim)

    def _lookup_rdap(self, domain: str) -> Optional[Dict[str, Any]]:
        """
        Queries the public RDAP bootstrap service for domain registration events.
        """
        try:
            url = f"{RDAP_BOOTSTRAP_URL}{domain}"
            resp = requests.get(url, headers=HEADERS, timeout=self.timeout)
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception as e:
            logger.debug(f"RDAP lookup failed gracefully for {domain}: {e}")
            return None

    def _build_fact_from_rdap(self, domain: str, rdap_data: Dict[str, Any], claim: Claim) -> List[Fact]:
        events = rdap_data.get("events", [])
        registration_date_str = None

        for event in events:
            action = event.get("eventAction", "").lower()
            if action in ["registration", "created", "initial"]:
                registration_date_str = event.get("eventDate")
                break

        now = datetime.now(timezone.utc)
        domain_age_days = None
        trust_modifier = 0.85  # default moderate weight

        if registration_date_str:
            try:
                # ISO date parsing e.g. "2021-04-12T15:00:00Z"
                cleaned_date_str = registration_date_str.replace("Z", "+00:00")
                reg_dt = datetime.fromisoformat(cleaned_date_str)
                age_delta = now - reg_dt
                domain_age_days = max(age_delta.days, 0)

                if domain_age_days >= 730:      # >= 2 years old
                    trust_modifier = 1.0
                    age_summary = f"{domain_age_days // 365} years old (registered {reg_dt.strftime('%Y-%m-%d')})"
                elif domain_age_days >= 180:    # 6 months - 2 years
                    trust_modifier = 0.85
                    age_summary = f"{domain_age_days // 30} months old (registered {reg_dt.strftime('%Y-%m-%d')})"
                elif domain_age_days >= 30:     # 1 - 6 months
                    trust_modifier = 0.50
                    age_summary = f"{domain_age_days} days old (registered {reg_dt.strftime('%Y-%m-%d')})"
                else:                           # < 30 days old (brand new)
                    trust_modifier = 0.20
                    age_summary = f"brand new ({domain_age_days} days old, registered {reg_dt.strftime('%Y-%m-%d')})"

                content = f"Domain '{domain}' is {age_summary}. RDAP registration record verified."
            except Exception:
                content = f"Domain '{domain}' registration record found on RDAP."
        else:
            content = f"Domain '{domain}' RDAP registry entry confirmed."

        registrar_name = None
        entities = rdap_data.get("entities", [])
        for ent in entities:
            roles = ent.get("roles", [])
            if "registrar" in roles:
                vcard = ent.get("vcardArray", [])
                if len(vcard) > 1:
                    for prop in vcard[1]:
                        if prop and prop[0] == "fn":
                            registrar_name = prop[3]
                            break

        return [
            Fact(
                source_name=self.source_name,
                trust_weight=trust_modifier,
                content=content,
                retrieved_at=now,
                raw_reference=f"rdap:{domain}",
                category="other",
                is_self_attested=False,
                metadata={
                    "domain": domain,
                    "domain_age_days": domain_age_days,
                    "registration_date": registration_date_str,
                    "registrar": registrar_name,
                    "trust_modifier": trust_modifier
                }
            )
        ]
