#!/usr/bin/env python3
"""Scrape San Juan Islands trails from WTA and load into Chroma.

Uses WTA's "Hiking in the Islands" page to get trail slugs (Young Hill, Mount Finlayson,
Turtleback, Iceberg Point, Mount Constitution, etc.) instead of the global list where
they're buried many pages in.

Usage:
    python scripts/load_san_juan_trails.py
    python scripts/load_san_juan_trails.py --no-trip-reports  # faster
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from beta_graph.servers.wta.chroma_store import WTAVectorStore
from beta_graph.servers.wta.scraper import fetch_trail_slugs_from_url, scrape_trail_detail

ISLANDS_PAGE = "https://www.wta.org/go-outside/seasonal-hikes/year-round-destinations/hiking-in-the-islands"
REQUEST_DELAY = 0.5


def main():
    parser = argparse.ArgumentParser(description="Load San Juan Islands trails into Chroma")
    parser.add_argument(
        "--no-trip-reports",
        action="store_true",
        help="Skip trip reports (faster scrape)",
    )
    args = parser.parse_args()

    print(f"Fetching trail slugs from: {ISLANDS_PAGE}")
    slugs = fetch_trail_slugs_from_url(ISLANDS_PAGE)
    print(f"Found {len(slugs)} trail slugs")

    trails = []
    for i, slug in enumerate(slugs):
        trail = scrape_trail_detail(
            slug,
            fetch_trip_reports=not args.no_trip_reports,
        )
        if trail:
            trails.append(trail)
            print(f"  [{i + 1}/{len(slugs)}] {trail.name}")
        if (i + 1) % 5 == 0:
            time.sleep(REQUEST_DELAY)

    if not trails:
        print("No trails scraped.")
        return 1

    store = WTAVectorStore()
    count = store.add_trails(trails)
    print(f"\nLoaded {count} trails. Total in Chroma: {store.count()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
