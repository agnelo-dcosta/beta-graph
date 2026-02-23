#!/usr/bin/env python3
"""Re-scrape existing trails in Chroma to fill in improved description and getting_there.

Use after improving the scraper (e.g. full narrative from hike-major-section, fixed getting_there).
Updates description (up to 4000 chars) and getting_there for all trails in Chroma.

Usage:
    python scripts/update_trail_descriptions.py              # update all trails
    python scripts/update_trail_descriptions.py --limit 50 # update first 50
    python scripts/update_trail_descriptions.py tumwater-pipeline-trail rattlesnake-ledge  # specific slugs
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from beta_graph.servers.wta.chroma_store import WTAVectorStore
from beta_graph.servers.wta.scraper import scrape_trail_detail


def main():
    parser = argparse.ArgumentParser(description="Re-scrape trails to update description and getting_there")
    parser.add_argument("slugs", nargs="*", help="Specific slugs to update (default: all in Chroma)")
    parser.add_argument("--limit", type=int, default=0, help="Max trails to update (0 = no limit)")
    parser.add_argument("--dry-run", action="store_true", help="List slugs that would be updated, don't scrape")
    args = parser.parse_args()

    store = WTAVectorStore()

    if args.slugs:
        slugs = [s.strip().lower() for s in args.slugs if s.strip()]
        res = store.collection.get(include=[])
        existing = set(res.get("ids") or [])
        slugs = [s for s in slugs if s in existing]
        missing = [s for s in args.slugs if s.strip().lower() not in existing]
        if missing:
            print(f"Not in Chroma (skipped): {missing}")
    else:
        res = store.collection.get(include=[])
        slugs = res.get("ids") or []
        if not slugs:
            print("Chroma has no trails. Load some first with load_trail_by_slug.py or load_wta_by_region.py")
            return 1

    if args.limit:
        slugs = slugs[: args.limit]

    print(f"Updating {len(slugs)} trail(s)...")

    if args.dry_run:
        for s in slugs:
            print(f"  {s}")
        return 0

    updated = 0
    for i, slug in enumerate(slugs):
        trail = scrape_trail_detail(slug, fetch_trip_reports=False)
        if trail and trail.slug and trail.location:
            store.add_trails([trail])
            updated += 1
            desc_len = len(trail.description or "")
            gt_len = len(trail.getting_there or "")
            print(f"  [{i+1}/{len(slugs)}] {trail.name}: desc={desc_len} chars, getting_there={gt_len} chars")
        else:
            print(f"  [{i+1}/{len(slugs)}] Failed: {slug}")
        time.sleep(0.3)  # Rate limit WTA

    print(f"\nUpdated {updated} trail(s). Total in Chroma: {store.count()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
