import os
import re
import json
import logging
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse, quote_plus
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup
import google.generativeai as genai

from app.models import Claim, ClaimCategory, sanitize_category, is_transient_error
from app.sources.base import EvidenceSource, Fact

logger = logging.getLogger("reelclaim.sources.cross_reference")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36 (compatible; ReelClaimBot/1.0)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

def extract_brand_or_domain_name(target_url: Optional[str]) -> str:
    """Extracts a readable brand or domain name from a URL."""
    if not target_url:
        return ""
    try:
        parsed = urlparse(target_url if "://" in target_url else f"https://{target_url}")
        netloc = parsed.netloc.replace("www.", "").strip()
        if not netloc:
            netloc = target_url.strip()
        parts = netloc.split(".")
        if len(parts) >= 2:
            return parts[0]
        return netloc
    except Exception:
        return target_url or ""

def get_root_domain(domain_or_url: str) -> str:
    """Extracts root registrable domain (e.g. 'fraudsite.io' from 'courses.fraudsite.io')."""
    if not domain_or_url:
        return ""
    try:
        parsed = urlparse(domain_or_url if "://" in domain_or_url else f"https://{domain_or_url}")
        netloc = (parsed.netloc or domain_or_url).replace("www.", "").strip().lower()
        parts = netloc.split(".")
        if len(parts) >= 2:
            return ".".join(parts[-2:])
        return netloc
    except Exception:
        return domain_or_url.lower().strip()

def is_operator_owned_url(url: str, target_url: Optional[str]) -> bool:
    """Returns True if a search result URL belongs to the operator/promoter domain."""
    if not target_url or not url:
        return False
    try:
        t_parsed = urlparse(target_url if "://" in target_url else f"https://{target_url}")
        u_parsed = urlparse(url if "://" in url else f"https://{url}")
        t_domain = t_parsed.netloc.replace("www.", "").lower()
        u_domain = u_parsed.netloc.replace("www.", "").lower()
        if not t_domain or not u_domain:
            return False
        if t_domain == u_domain or u_domain.endswith(f".{t_domain}") or t_domain.endswith(f".{u_domain}"):
            return True
        t_root = get_root_domain(t_domain)
        u_root = get_root_domain(u_domain)
        if t_root and u_root and t_root == u_root:
            return True
        return False
    except Exception:
        return False

class CrossReferenceSource:
    """
    EvidenceSource that performs independent web searches for:
    "<name> scam", "<name> review", "<name> complaint"
    Filters out operator-owned domains and extracts 3rd-party independent facts.
    Trust weight: high (0.85), is_self_attested: False.
    """
    source_name: str = "cross_reference"
    base_trust_weight: float = 0.85

    def __init__(self, request_timeout: float = 4.0):
        self.timeout = request_timeout

    def fetch(self, claim: Claim, target_url: Optional[str] = None, api_key: Optional[str] = None, **kwargs) -> List[Fact]:
        brand_name = extract_brand_or_domain_name(target_url)
        if not brand_name and not target_url:
            return []

        # Allow passing mock or pre-fetched search results for deterministic testing/custom engines
        injected_results = kwargs.get("mock_search_results")
        if injected_results is not None:
            return self._process_search_snippets(injected_results, claim, brand_name, target_url, api_key=api_key)

        snippets = self._search_web(brand_name, target_url)
        if not snippets:
            return []

        return self._process_search_snippets(snippets, claim, brand_name, target_url, api_key=api_key)

    def _search_web(self, brand_name: str, target_url: Optional[str]) -> List[Dict[str, str]]:
        """
        Executes lightweight searches for scam, review, and complaint queries.
        Extracts independent results, discarding operator-owned URLs.
        """
        queries = [
            f"{brand_name} scam",
            f"{brand_name} review",
            f"{brand_name} complaint"
        ]
        
        all_snippets: List[Dict[str, str]] = []
        seen_urls = set()

        for q in queries:
            try:
                # Use DuckDuckGo HTML interface for lightweight zero-token public search
                url = f"https://html.duckduckgo.com/html/?q={quote_plus(q)}"
                resp = requests.post(
                    url,
                    data={"q": q},
                    headers=HEADERS,
                    timeout=self.timeout
                )
                if resp.status_code != 200:
                    continue

                soup = BeautifulSoup(resp.text, "html.parser")
                results = soup.find_all("div", class_=re.compile(r"result|web-result"))
                for res in results[:4]:
                    link_tag = res.find("a", class_=re.compile(r"result__url|result__snippet|result__title"))
                    href = link_tag.get("href", "") if link_tag else ""
                    
                    # DuckDuckGo wraps URLs in uddg parameter
                    if "uddg=" in href:
                        match = re.search(r"uddg=([^&]+)", href)
                        if match:
                            from urllib.parse import unquote
                            href = unquote(match.group(1))

                    if not href or href in seen_urls:
                        continue

                    # Filter out operator's own domain
                    if is_operator_owned_url(href, target_url):
                        continue

                    title_tag = res.find("a", class_=re.compile(r"result__title|result__a"))
                    title = title_tag.get_text(strip=True) if title_tag else ""

                    snippet_tag = res.find("a", class_=re.compile(r"result__snippet")) or res.find("div", class_=re.compile(r"result__snippet"))
                    snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""

                    if snippet or title:
                        seen_urls.add(href)
                        all_snippets.append({
                            "title": title,
                            "snippet": snippet,
                            "url": href,
                            "query": q
                        })
            except Exception as e:
                logger.debug(f"Search query '{q}' failed gracefully: {e}")
                continue

        return all_snippets

    def _process_search_snippets(
        self,
        snippets: List[Dict[str, str]],
        claim: Claim,
        brand_name: str,
        target_url: Optional[str],
        api_key: Optional[str] = None
    ) -> List[Fact]:
        """
        Extracts structured facts from independent search snippets.
        Uses Gemini LLM if available, with robust fallback to structured text extraction.
        """
        if not snippets:
            return []

        # Filter out any operator URLs that might have leaked into snippets
        valid_snippets = [
            s for s in snippets
            if not is_operator_owned_url(s.get("url", ""), target_url)
        ]

        if not valid_snippets:
            return []

        effective_api_key = (api_key.strip() if api_key and api_key.strip() else None) or os.getenv("GEMINI_API_KEY")

        if effective_api_key:
            try:
                return self._extract_facts_with_llm(valid_snippets, claim, effective_api_key)
            except Exception as e:
                logger.warning(f"LLM fact extraction from search snippets failed ({e}), falling back to direct snippet facts.")

        # Fallback: create Fact items directly from top independent snippets
        facts: List[Fact] = []
        now = datetime.now(timezone.utc)
        for s in valid_snippets[:4]:
            text_content = f"{s.get('title', '')}: {s.get('snippet', '')}".strip(" :")
            if len(text_content) >= 20:
                facts.append(
                    Fact(
                        source_name=self.source_name,
                        trust_weight=self.base_trust_weight,
                        content=text_content,
                        retrieved_at=now,
                        raw_reference=s.get("url") or f"search:{s.get('query', brand_name)}",
                        category=claim.category,
                        is_self_attested=False,
                        metadata={
                            "title": s.get("title", ""),
                            "query": s.get("query", ""),
                            "domain": urlparse(s.get("url", "")).netloc
                        }
                    )
                )
        return facts

    def _extract_facts_with_llm(self, snippets: List[Dict[str, str]], claim: Claim, api_key: str) -> List[Fact]:
        model_name = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
        genai.configure(api_key=api_key)

        model = genai.GenerativeModel(
            model_name=model_name,
            generation_config={"response_mime_type": "application/json"}
        )

        prompt = f"""
You are an independent credibility fact extractor. Analyze the following 3rd-party independent search results regarding a promotional claim.
Extract concrete factual statements regarding complaints, reviews, refunds, pricing, certifications, or legitimacy.

Promotional Claim: "{claim.text}" (Category: {claim.category})

Independent Search Snippets:
{json.dumps(snippets, indent=2)}

Return JSON adhering strictly to this schema:
{{
  "facts": [
    {{
      "category": "{claim.category}",
      "text": "Specific factual summary from independent source",
      "source_url": "URL of the independent source",
      "is_contradicting": false
    }}
  ]
}}
If no meaningful facts exist, return {{"facts": []}}.
"""
        response = model.generate_content(prompt)
        raw_text = response.text or "{}"
        clean_text = raw_text.strip()
        if "```" in clean_text:
            match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", clean_text, re.IGNORECASE)
            if match:
                clean_text = match.group(1).strip()
        data = json.loads(clean_text)

        facts: List[Fact] = []
        now = datetime.now(timezone.utc)
        for item in data.get("facts", []):
            f_text = item.get("text", "").strip()
            f_url = item.get("source_url", "").strip()
            f_cat = sanitize_category(item.get("category", claim.category))
            if f_text:
                facts.append(
                    Fact(
                        source_name=self.source_name,
                        trust_weight=self.base_trust_weight,
                        content=f_text,
                        retrieved_at=now,
                        raw_reference=f_url or "cross_reference_search",
                        category=f_cat,
                        is_self_attested=False,
                        metadata={
                            "extracted_by": "llm_cross_reference",
                            "is_contradicting": item.get("is_contradicting", False)
                        }
                    )
                )
        return facts
