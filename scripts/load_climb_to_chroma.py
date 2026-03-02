#!/usr/bin/env python3
"""Load Mountain Project climbs into Chroma. Scrapes an area URL and upserts routes.

Recursively collects routes from the area, classics page (with pagination), and all
child sub-areas down to leaf crags. Use --max-depth to limit recursion.

Usage:
    python scripts/load_climb_to_chroma.py
    python scripts/load_climb_to_chroma.py --url "https://www.mountainproject.com/area/105794001/tumwater-canyon"
    python scripts/load_climb_to_chroma.py --url "..." --max-routes 50 --max-depth 2

Default URL: Tumwater Canyon
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from beta_graph.servers.climb.chroma_store import ClimbVectorStore
from beta_graph.servers.climb.config import MAX_RECURSION_DEPTH
from beta_graph.servers.climb.scraper import scrape_area

DEFAULT_AREA_URL = "https://www.mountainproject.com/area/105794001/tumwater-canyon"


def main():
    parser = argparse.ArgumentParser(description="Load Mountain Project climbs into Chroma")
    parser.add_argument(
        "--url",
        default=DEFAULT_AREA_URL,
        help=f"Mountain Project area URL. Default: {DEFAULT_AREA_URL}",
    )
    parser.add_argument(
        "--max-routes",
        type=int,
        default=None,
        help="Max routes to scrape (default: all)",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=MAX_RECURSION_DEPTH,
        help=f"Max recursion depth for sub-areas (default: {MAX_RECURSION_DEPTH})",
    )
    args = parser.parse_args()

    print(f"Scraping {args.url} (max_depth={args.max_depth})...")
    climbs = scrape_area(args.url, max_routes=args.max_routes, max_depth=args.max_depth)

    if not climbs:
        print("No climbs found.")
        return 1

    store = ClimbVectorStore()
    count = store.add_climbs(climbs)
    print(f"Loaded {count} climbs. Total in Chroma: {store.count()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
