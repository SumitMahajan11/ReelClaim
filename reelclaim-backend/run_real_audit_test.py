import sys
import json
import time
from pathlib import Path

# Ensure UTF-8 output encoding for Windows terminal
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parent))

from app.main import audit_reel_endpoint
from app.models import FullAuditRequest

STRESS_TEST_CASES = [
    {
        "id": 1,
        "name": "WAF/Anti-Bot Blocked Site Crawl",
        "description": "Tests handling when a target URL blocks web requests with anti-bot/WAF challenges.",
        "request": FullAuditRequest(
            caption="🔥 Check out the top coding answers and discussions on Quora today at https://www.quora.com",
            override_url="https://www.quora.com"
        ),
        "expected_check": lambda res: res.crawl_status == "blocked" and res.check_result is None
    },
    {
        "id": 2,
        "name": "Caption with Zero Extractable Claims",
        "description": "Tests handling when a social reel caption contains no promotional product claims.",
        "request": FullAuditRequest(
            caption="Just hanging out with friends on a sunny Saturday afternoon! ☀️ High vibes only #weekend #fun",
            override_url="https://example.com"
        ),
        "expected_check": lambda res: len(res.claims) == 0 and (res.check_result is None or res.check_result.coverage_status == "unverified_no_data")
    },
    {
        "id": 3,
        "name": "JS-Heavy SPA Site (Playwright Fallback)",
        "description": "Tests client-rendered SPA site (empty initial HTML) forcing Playwright fallback without timing out.",
        "request": FullAuditRequest(
            caption="🚀 Learn React for free at https://react.dev with modern hooks and components!",
            override_url="https://react.dev"
        ),
        "expected_check": lambda res: res.crawl_status in ["success", "blocked"]
    },
    {
        "id": 4,
        "name": "Genuinely Contradicted Claims",
        "description": "Tests claim verification when caption makes false claims contradicted by actual site facts.",
        "request": FullAuditRequest(
            caption="🎉 Boot.dev is 100% free with unlimited access forever and zero fees for all backend courses!",
            override_url="https://boot.dev"
        ),
        "expected_check": lambda res: (
            res.check_result is not None and 
            res.check_result.score_breakdown.contradicted_count > 0 and
            res.check_result.confidence_tier == "CONTRADICTED"
        )
    }
]

def run_stress_tests():
    import argparse
    import requests

    parser = argparse.ArgumentParser(description="ReelClaim Stress Test Suite")
    parser.add_argument("--url", type=str, default=None, help="Target backend base URL (e.g. https://reelclaim-backend.onrender.com)")
    args = parser.parse_args()

    print("=" * 80)
    print("REELCLAIM — REAL-WORLD EDGE-CASE STRESS TEST SUITE")
    if args.url:
        print(f"Targeting Live Remote Backend: {args.url}")
    else:
        print("Targeting Local In-Memory Python Engine")
    print("=" * 80)

    results_summary = []

    for test in STRESS_TEST_CASES:
        print(f"\n--- [CASE {test['id']}] {test['name']} ---")
        print(f"Goal: {test['description']}")
        print(f"Caption: \"{test['request'].caption}\"")
        print(f"Override URL: {test['request'].override_url}")
        
        start_time = time.time()
        elapsed = 0.0
        try:
            if args.url:
                base = args.url.rstrip('/')
                endpoint = f"{base}/audit-reel"
                payload = test["request"].model_dump()
                resp = requests.post(endpoint, json=payload, timeout=150)
                if resp.status_code == 404:
                    endpoint = f"{base}/api/audit-reel"
                    resp = requests.post(endpoint, json=payload, timeout=150)
                resp.raise_for_status()
                res_dict = resp.json()
                from app.models import FullAuditResponse
                res = FullAuditResponse(**res_dict)
            else:
                res = audit_reel_endpoint(test["request"])
                res_dict = res.model_dump()
            
            elapsed = round(time.time() - start_time, 2)
            passed = test["expected_check"](res)
            status_symbol = "✓ PASS" if passed else "❌ FAIL (Unexpected Schema/Verdict)"

            print(f"Elapsed Time: {elapsed}s")
            print(f"Crawl Status: {res.crawl_status}")
            print(f"Extracted Claims Count: {len(res.claims)}")
            if res.check_result:
                print(f"Confidence Tier: {res.check_result.confidence_tier}")
                print(f"Coverage Status: {res.check_result.coverage_status}")
                print(f"Summary Label: {res.check_result.summary_label}")
                print(f"Breakdown: {res.check_result.score_breakdown}")
            else:
                print("Check Result: None (Graceful Short-Circuit)")
                
            print(f"VERIFICATION: {status_symbol}")
            print("\nREAL JSON RESPONSE:")
            print(json.dumps(res_dict, indent=2))
            
            results_summary.append((test["id"], test["name"], status_symbol, elapsed))
        except Exception as e:
            elapsed = round(time.time() - start_time, 2)
            print(f"❌ ERROR EXECUTING TEST: {e}")
            results_summary.append((test["id"], test["name"], f"❌ EXCEPTION: {e}", elapsed))

        print("-" * 80)
        # Sleep slightly between live E2E tests to respect Gemini rate limits
        time.sleep(3)

    print("\n" + "=" * 80)
    print("STRESS TEST SUMMARY REPORT")
    print("=" * 80)
    for tid, tname, status, ttime in results_summary:
        print(f"Case {tid}: {tname:<45} | Status: {status:<30} | Duration: {ttime}s")
    print("=" * 80)

if __name__ == "__main__":
    run_stress_tests()
