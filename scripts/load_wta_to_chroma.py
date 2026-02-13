#!/usr/bin/env python3
"""Load WTA trails into Chroma. Pre-scrape regions for initial data.

Usage:
    python scripts/load_wta_to_chroma.py
    python scripts/load_wta_to_chroma.py --location "Seattle" --radius 30
    python scripts/load_wta_to_chroma.py --location "Kirkland" --pages 5

Scrapes WTA hikes and upserts into the wta_trails Chroma collection.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from beta_graph.servers.wta.chroma_store import WTAVectorStore
from beta_graph.servers.wta.scraper import scrape_wta_trails, scrape_wta_trails_for_location


def main():
    parser = argparse.ArgumentParser(description="Load WTA trails into Chroma")
    parser.add_argument("--location", default=None, help="Geocode and scrape within radius (e.g. Seattle)")
    parser.add_argument("--radius", type=float, default=50, help="Miles from location. Default 50")
    parser.add_argument("--pages", type=int, default=5, help="Max list pages to scrape. Default 5")
    parser.add_argument("--no-location", action="store_true", help="Scrape all (no geo filter)")
    parser.add_argument(
        "--no-trip-reports",
        action="store_true",
        help="Skip trip reports (faster scrape, no conditions)",
    )
    args = parser.parse_args()

    center_lat = center_lon = None
    if args.location and not args.no_location:
        from beta_graph.servers.geocode.geocode import geocode_forward
        try:
            geo = geocode_forward(args.location, limit=1)
            if geo and geo[0].get("latitude") is not None:
                center_lat = geo[0]["latitude"]
                center_lon = geo[0]["longitude"]
                print(f"Geocoded {args.location} -> ({center_lat:.4f}, {center_lon:.4f})")
        except Exception as e:
            print(f"Geocoding failed: {e}. Scraping without location filter.")
            args.no_location = True

    if args.no_location or not args.location:
        center_lat = center_lon = None
        args.radius = 999  # No filter

    fetch_reports = not args.no_trip_reports
    print(
        f"Scraping WTA (location={args.location}, radius={args.radius} mi, "
        f"trip_reports={fetch_reports})..."
    )
    if center_lat is not None and center_lon is not None:
        trails = scrape_wta_trails_for_location(
            center_lat=center_lat,
            center_lon=center_lon,
            radius_miles=args.radius,
            fetch_trip_reports=fetch_reports,
        )
    else:
        trails = scrape_wta_trails(
            page_limit=args.pages,
            fetch_trip_reports=fetch_reports,
        )

    if not trails:
        print("No trails found.")
        return 1

    store = WTAVectorStore()
    deleted = store.delete_trails_without_location()
    if deleted:
        print(f"Removed {deleted} trails without coordinates from store.")
    count = store.add_trails(trails)
    print(f"Loaded {count} trails. Total in Chroma: {store.count()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
