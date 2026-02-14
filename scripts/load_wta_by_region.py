#!/usr/bin/env python3
"""Load WTA trails by region. Scrapes all 11 WTA regions or a specific one.

Usage:
    python scripts/load_wta_by_region.py                    # all regions
    python scripts/load_wta_by_region.py --region "North Cascades"
    python scripts/load_wta_by_region.py -r "Olympic Peninsula"
    python scripts/load_wta_by_region.py --region north     # fuzzy match

Region names (partial match supported):
    Central Cascades, Central Washington, Eastern Washington, Issaquah Alps,
    Mount Rainier Area, North Cascades, Olympic Peninsula,
    Puget Sound and Islands, Snoqualmie Region, South Cascades, Southwest Washington
"""

import argparse
import sys
import time
from pathlib import Path
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from beta_graph.servers.wta.chroma_store import WTAVectorStore
from beta_graph.servers.wta.scraper import (
    REQUEST_DELAY,
    fetch_trail_slugs_from_url,
    scrape_trail_detail,
)

# WTA uses hike_search with region UUIDs (extracted from wta.org option values)
HIKES_SEARCH_URL = "https://www.wta.org/go-outside/hikes/hike_search"

WTA_REGIONS = [
    "Central Cascades",
    "Central Washington",
    "Eastern Washington",
    "Issaquah Alps",
    "Mount Rainier Area",
    "North Cascades",
    "Olympic Peninsula",
    "Puget Sound and Islands",
    "Snoqualmie Region",
    "South Cascades",
    "Southwest Washington",
]

# Region name -> WTA internal UUID (from hike search form)
REGION_UUIDS = {
    "Central Cascades": "b4845d8a21ad6a202944425c86b6e85f",
    "Central Washington": "41f702968848492db697e10b14c14060",
    "Eastern Washington": "9d321b42e903a3224fd4fef44af9bee3",
    "Issaquah Alps": "592fcc9afd9208db3b81fdf93dada567",
    "Mount Rainier Area": "344281caae0d5e845a5003400c0be9ef",
    "North Cascades": "49aff77512c523f32ae13d889f6969c9",
    "Olympic Peninsula": "922e688d784aa95dfb80047d2d79dcf6",
    "Puget Sound and Islands": "0c1d82b18f8023acb08e4daf03173e94",
    "Snoqualmie Region": "04d37e830680c65b61df474e7e655d64",
    "South Cascades": "8a977ce4bf0528f4f833743e22acae5d",
    "Southwest Washington": "2b6f1470ed0a4735a4fc9c74e25096e0",
}


def _match_region(input_str: str) -> str | None:
    """Return exact region name if input loosely matches, else None."""
    lower = input_str.strip().lower()
    for r in WTA_REGIONS:
        if lower in r.lower() or r.lower().replace(" ", "") == lower.replace(" ", ""):
            return r
    return None


def _fetch_slugs_for_region(region: str, page_limit: int = 50) -> list[str]:
    """Fetch trail slugs from region-filtered hike_search with pagination."""
    uid = REGION_UUIDS.get(region)
    if not uid:
        return []
    slugs: set[str] = set()
    for page in range(page_limit):
        params = {"region": uid}
        if page > 0:
            params["b_start:int"] = page * 30
        url = f"{HIKES_SEARCH_URL}?{urlencode(params)}"
        page_slugs = fetch_trail_slugs_from_url(url)
        if not page_slugs and page > 0:
            break
        slugs.update(page_slugs)
        if page > 0:
            time.sleep(REQUEST_DELAY)
    return list(slugs)


def main():
    parser = argparse.ArgumentParser(
        description="Load WTA trails by region. Scrape all regions or a single one."
    )
    parser.add_argument(
        "-r",
        "--region",
        default=None,
        help="Scrape only this region (fuzzy match, e.g. 'north' or 'North Cascades')",
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=50,
        help="Max pages per region (30 trails/page). Default 50",
    )
    parser.add_argument(
        "--no-trip-reports",
        action="store_true",
        help="Skip trip reports (faster scrape)",
    )
    parser.add_argument(
        "--list-regions",
        action="store_true",
        help="List all WTA regions and exit",
    )
    args = parser.parse_args()

    if args.list_regions:
        print("WTA regions:")
        for r in WTA_REGIONS:
            print(f"  - {r}")
        return 0

    regions_to_scrape: list[str]
    if args.region:
        matched = _match_region(args.region)
        if not matched:
            print(f"Unknown region: {args.region!r}")
            print("Use --list-regions to see valid regions.")
            return 1
        regions_to_scrape = [matched]
        print(f"Scraping region: {matched}")
    else:
        regions_to_scrape = WTA_REGIONS
        print(f"Scraping all {len(regions_to_scrape)} regions")

    store = WTAVectorStore()
    total_loaded = 0

    for region in regions_to_scrape:
        print(f"\n--- {region} ---")
        slugs = _fetch_slugs_for_region(region, page_limit=args.pages)
        print(f"  Found {len(slugs)} trail slugs")

        for i, slug in enumerate(slugs):
            trail = scrape_trail_detail(slug, fetch_trip_reports=not args.no_trip_reports)
            if trail and trail.slug and trail.location:
                store.add_trails([trail])
                total_loaded += 1
                if (i + 1) % 10 == 0:
                    print(f"  Loaded {i + 1}/{len(slugs)}...")
            elif trail and trail.slug and not trail.location:
                pass  # Skip trails without coordinates
            if (i + 1) % 5 == 0:
                time.sleep(REQUEST_DELAY)

    print(f"\nLoaded {total_loaded} trails. Total in Chroma: {store.count()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
