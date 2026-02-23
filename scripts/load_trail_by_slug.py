#!/usr/bin/env python3
"""Load a specific WTA trail (or trails) by slug into Chroma.

Use when a trail you want isn't in the DB yet – e.g. Tumwater Pipeline Trail.

Usage:
    python scripts/load_trail_by_slug.py tumwater-pipeline-trail
    python scripts/load_trail_by_slug.py rattlesnake-ledge tumwater-pipeline-trail
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from beta_graph.servers.wta.chroma_store import WTAVectorStore
from beta_graph.servers.wta.scraper import scrape_trail_detail


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/load_trail_by_slug.py <slug> [slug2 ...]")
        print("Example: python scripts/load_trail_by_slug.py tumwater-pipeline-trail")
        return 1

    slugs = [s.strip().lower() for s in sys.argv[1:] if s.strip()]
    store = WTAVectorStore()
    loaded = 0

    for slug in slugs:
        trail = scrape_trail_detail(slug, fetch_trip_reports=False)
        if trail and trail.slug and trail.location:
            store.add_trails([trail])
            loaded += 1
            print(f"Loaded: {trail.name} ({slug})")
        elif trail and trail.slug and not trail.location:
            print(f"Skipped (no coordinates): {trail.name}")
        else:
            print(f"Failed to scrape: {slug}")

    if loaded:
        print(f"\nAdded {loaded} trail(s). Total in Chroma: {store.count()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
