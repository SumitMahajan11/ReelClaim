"""
Live end-to-end execution against real internet sources (DuckDuckGo, Wayback, WHOIS RDAP).
"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))

from app.models import Claim
from app.sources.whois import WhoisSource
from app.sources.wayback import WaybackSource
from app.sources.cross_reference import CrossReferenceSource
from app.sources.site_crawl import SiteCrawlSource
from app.sources.orchestrator import gather_all_evidence

def live_run():
    print("=" * 80)
    print("LIVE REAL-WORLD EVIDENCE SOURCE GATHERING TEST")
    print("=" * 80)

    target_url = "https://boot.dev"
    claim = Claim(
        category="price",
        text="Monthly subscription for computer science courses",
        confidence="high",
        source_type="caption"
    )

    print(f"Target URL: {target_url}")
    print(f"Claim:      {claim.text}")

    # 1. Whois live RDAP
    print("\n1. Testing WhoisSource (Live RDAP lookup)...")
    whois_src = WhoisSource()
    whois_facts = whois_src.fetch(claim, target_url=target_url)
    for f in whois_facts:
        print(f"   ✓ [WHOIS] Weight: {f.trust_weight} | Content: {f.content}")

    # 2. Wayback live API
    print("\n2. Testing WaybackSource (Live Wayback API)...")
    wayback_src = WaybackSource()
    wayback_facts = wayback_src.fetch(claim, target_url=target_url)
    for f in wayback_facts:
        print(f"   ✓ [WAYBACK] Weight: {f.trust_weight} | Content: {f.content}")

    # 3. CrossReference live Search
    print("\n3. Testing CrossReferenceSource (Live Web Search)...")
    cross_src = CrossReferenceSource()
    cross_facts = cross_src.fetch(claim, target_url=target_url)
    print(f"   ✓ [CROSS-REF] Retrieved {len(cross_facts)} independent search facts.")
    for f in cross_facts[:3]:
        print(f"     • {f.raw_reference}: {f.content[:90]}...")

    # 4. Orchestrator live run
    print("\n4. Testing gather_all_evidence Orchestrator (Parallel multi-source)...")
    all_facts = gather_all_evidence([claim], target_url=target_url)
    print(f"   ✓ Total Facts Gathered: {len(all_facts)}")
    sources_represented = set(f.source_name for f in all_facts)
    print(f"   ✓ Sources Active: {sources_represented}")
    print("\nLIVE RUN COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    live_run()
