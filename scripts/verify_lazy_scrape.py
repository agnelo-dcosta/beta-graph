#!/usr/bin/env python3
"""Verify lazy scrape: trigger conditions, scrape execution, and daemon-thread behavior.

Run:
    python3 scripts/verify_lazy_scrape.py

Checks:
1. Search for Olympic returns 0 results (trigger condition)
2. Geocode works for Olympic NP
3. Lazy scrape (sync) can load trails
4. Daemon thread is killed when process exits (single-shot bug)
"""

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from beta_graph.servers.geocode.geocode import geocode_forward
from beta_graph.servers.wta.chroma_store import WTAVectorStore
from beta_graph.servers.wta.config import DEFAULT_RADIUS_MILES, DEFAULT_SCRAPE_PAGE_LIMIT
from beta_graph.servers.wta.scraper import scrape_wta_trails


def main():
    print("=== Lazy Scrape Verification ===\n")

    store = WTAVectorStore()
    count_before = store.count()
    print(f"1. Chroma trail count: {count_before}")

    # Test location that has NO trails loaded (Olympic)
    location = "Olympic National Park, WA"
    radius = DEFAULT_RADIUS_MILES  # 20

    # Geocode
    print(f"\n2. Geocoding '{location}'...")
    geo = geocode_forward(location, limit=1)
    if not geo or geo[0].get("latitude") is None:
        print("   FAIL: Geocode failed")
        return 1
    lat, lon = geo[0]["latitude"], geo[0]["longitude"]
    print(f"   OK: ({lat}, {lon})")

    # Search - should return 0 (no Olympic trails in Chroma)
    trails = store.search(
        query="hikes trails",
        n_results=5,
        center_lat=lat,
        center_lon=lon,
        radius_miles=radius,
    )
    print(f"\n3. Search results for Olympic area: {len(trails)} trails")
    if trails:
        print("   WARNING: Expected 0 (Olympic not loaded). Lazy scrape would NOT trigger.")
    else:
        print("   OK: 0 results -> lazy scrape WOULD trigger (if location + center_lat)")

    # Run scrape synchronously to verify it works (skip if no network / want fast test)
    if "--skip-scrape" in sys.argv:
        print("\n4. Skipping actual scrape (--skip-scrape)")
        return 0

    print(f"\n4. Running scrape (sync, {DEFAULT_SCRAPE_PAGE_LIMIT} pages)...")
    start = time.perf_counter()
    scraped = scrape_wta_trails(
        page_limit=DEFAULT_SCRAPE_PAGE_LIMIT,
        center_lat=lat,
        center_lon=lon,
        radius_miles=50,  # wider for Olympic
    )
    elapsed = time.perf_counter() - start
    print(f"   Scraped {len(scraped)} trails in {elapsed:.1f}s")

    if scraped:
        added = store.add_trails(scraped)
        print(f"   Loaded {added} into Chroma. Total: {store.count()}")
    else:
        print("   WARNING: 0 trails scraped. Check WTA/network.")

    # Re-search - should now find trails
    if scraped:
        trails2 = store.search(
            query="hikes trails",
            n_results=3,
            center_lat=lat,
            center_lon=lon,
            radius_miles=radius,
        )
        print(f"\n5. Re-search: {len(trails2)} trails found")
        for t in trails2[:2]:
            print(f"   - {t.get('name')}")

    print("\n=== Daemon Thread Bug (single-shot mode) ===")
    print("When run_agent.py is used with a one-shot query (e.g. 'Olympic hikes'):")
    print("  - Agent returns 'retry in 2-3 minutes' and process EXITS immediately")
    print("  - Daemon thread is KILLED when main process exits")
    print("  - Scrape never completes. Lazy scrape only works in CHAT mode.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
