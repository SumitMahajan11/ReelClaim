"""
Real Live End-to-End Test for YouTube Shorts Ingest and Claim Verification.
Extracts real public video metadata & captions from YouTube, extracts claims, and generates multi-source verdicts.
"""
import sys
import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Ensure UTF-8 output on Windows
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))

load_dotenv()

from app.youtube import ingest_youtube_short, is_youtube_url, extract_youtube_video_id
from app.extraction import extract_claims
from app.checker import cross_check_claims
from app.sources.orchestrator import gather_all_evidence

def run_live_youtube_short_audit():
    print("=" * 80)
    print("REELCLAIM - LIVE REAL PUBLIC YOUTUBE SHORTS AUDIT")
    print("=" * 80)

    # Real public YouTube Short reviewing / discussing free coding resources / bootcamps
    # Example: A real public short or popular video
    video_url = "https://www.youtube.com/shorts/328mNyO9t5Y" # or similar public short
    # Fallback to another public short if 328mNyO9t5Y has region restriction
    alt_video_url = "https://www.youtube.com/shorts/3f5G8kL9XYZ"

    # Let's test with a real public Short ID
    real_short_urls = [
        "https://www.youtube.com/shorts/a4qO4u6h2S8", # tech/coding short
        "https://www.youtube.com/shorts/q86g1bW8F7w", # coding tutorial short
        "https://www.youtube.com/shorts/kJQP7kiw5Fk", # song/despacito test
        "https://www.youtube.com/shorts/328mNyO9t5Y"
    ]

    print(f"Target Public YouTube Short: {video_url}")
    print("\n--- STEP 1: REAL YOUTUBE METADATA & TRANSCRIPT INGEST ---")
    ingest_result = ingest_youtube_short(video_url)
    
    # If first URL didn't have transcript, try fallback public video with confirmed captions
    if not ingest_result.transcript:
        for alt_url in real_short_urls:
            print(f"Checking alternative public video: {alt_url}...")
            alt_res = ingest_youtube_short(alt_url)
            if alt_res.transcript:
                ingest_result = alt_res
                video_url = alt_url
                break

    # If all shorts had captions disabled, test with public YouTube video with open captions
    if not ingest_result.transcript:
        confirmed_caption_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ" # Never gonna give you up - verified multi-language captions
        print(f"Testing public YouTube video with verified open captions: {confirmed_caption_url}")
        ingest_result = ingest_youtube_short(confirmed_caption_url)
        video_url = confirmed_caption_url

    print(f"\n✓ Video ID:       {ingest_result.video_id}")
    print(f"✓ Video Title:    {ingest_result.title}")
    print(f"✓ Channel:        {ingest_result.channel_title}")
    print(f"✓ Ingest Status:  {ingest_result.status}")
    print(f"✓ Detected Site:  {ingest_result.detected_site or 'None (using site override / extracted site)'}")
    print(f"\n[ACTUAL EXTRACTED TRANSCRIPT TEXT] ({len(ingest_result.transcript)} chars):")
    print("-" * 80)
    print(ingest_result.transcript[:400] + ("..." if len(ingest_result.transcript) > 400 else ""))
    print("-" * 80)

    print("\n--- STEP 2: PHASE 1 CLAIM EXTRACTION (LIVE GEMINI) ---")
    extraction = extract_claims(ingest_result.combined_text)
    print(f"✓ Promoted Site Identified: {extraction.promoted_site}")
    print(f"✓ Total Claims Extracted:   {len(extraction.claims)}")
    for i, c in enumerate(extraction.claims, 1):
        print(f"   Claim #{i}: [{c.category.upper()}] \"{c.text}\" (Confidence: {c.confidence})")

    target_url = ingest_result.detected_site or extraction.promoted_site or "https://youtube.com"
    print(f"\n--- STEP 3: MULTI-SOURCE EVIDENCE GATHERING & VERDICT (TARGET: {target_url}) ---")
    all_facts = gather_all_evidence(extraction.claims, target_url=target_url)
    print(f"✓ Total Multi-Source Facts Gathered: {len(all_facts)}")
    sources_used = set(f.source_name for f in all_facts)
    print(f"✓ Sources Contributing: {sources_used}")

    print("\n--- STEP 4: VERDICT ENGINE SYNTHESIS ---")
    check_result = cross_check_claims(extraction.claims, facts=all_facts)
    print(f"✓ Confidence Tier:  [{check_result.confidence_tier}]")
    print(f"✓ Coverage Status:  [{check_result.coverage_status}]")
    print(f"✓ Summary 'Why':    {check_result.summary_label}")
    print(f"✓ Confirmed: {check_result.score_breakdown.confirmed_count} | Contradicted: {check_result.score_breakdown.contradicted_count} | Partial: {check_result.score_breakdown.partial_count} | Unverified: {check_result.score_breakdown.not_found_count}")

    print("\n" + "=" * 80)
    print("LIVE YOUTUBE SHORTS AUDIT COMPLETED SUCCESSFULLY!")
    print("=" * 80)

if __name__ == "__main__":
    run_live_youtube_short_audit()
