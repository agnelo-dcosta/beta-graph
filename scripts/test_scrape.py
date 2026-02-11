#!/usr/bin/env python3
"""Test AllTrails scraping without the MCP server.

Usage:
    python scripts/test_scrape.py [URL]     # scrape live URL
    python scripts/test_scrape.py --file PATH  # test extraction on saved HTML

Examples:
    python scripts/test_scrape.py
    python scripts/test_scrape.py https://www.alltrails.com/us/washington/north-bend
    python scripts/test_scrape.py --file ../rattlesnake.html
"""

import sys
from pathlib import Path

# Add src to path when run from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from beta_graph.servers.alltrails.scraper import scrape_trails
from beta_graph.servers.alltrails.trail_detail import (
    _extract_trail_geo_stats,
    _extract_location_from_html,
    _extract_reviews,
)
from bs4 import BeautifulSoup


def test_from_file(html_path: str) -> None:
    """Test extraction on a saved HTML file (no network)."""
    path = Path(html_path)
    if not path.exists():
        print(f"File not found: {path}")
        return
    html = path.read_text()
    soup = BeautifulSoup(html, "html.parser")

    geo_dict, _ = _extract_trail_geo_stats(html)
    geo = geo_dict
    loc = _extract_location_from_html(html, soup)
    reviews = _extract_reviews(soup)

    print(f"From {path.name}:")
    print(f"  length_mi: {geo['length_mi']}")
    print(f"  elevation_gain_ft: {geo['elevation_gain_ft']}")
    print(f"  est_time: {geo['est_time']}")
    print(f"  location: {loc}")
    print(f"  reviews: {len(reviews)}")


def main():
    args = sys.argv[1:]
    if args and args[0] == "--file":
        if len(args) < 2:
            print("Usage: python scripts/test_scrape.py --file PATH")
            return
        test_from_file(args[1])
        return

    url = args[0] if args else "https://www.alltrails.com/us/washington/north-bend"
    print(f"Scraping {url}...")

    # Without details (faster)
    trails = scrape_trails(url, include_details=False)
    print(f"\nWithout details: {len(trails)} trails")
    for t in trails[:5]:
        g = t.trailGeoStats
        print(f"  {t.name} | {t.difficulty} | {f'{g.length_mi} mi' if g and g.length_mi else '?'}")

    # With details (coordinates, reviews, length_mi, elevation, etc.)
    print("\nFetching details (this may take a while)...")
    trails = scrape_trails(url, include_details=True)
    print(f"\nWith details: {len(trails)} trails")
    for t in trails[:5]:
        print(f"  {t.name}")
        g = t.trailGeoStats
        print(f"    length: {g.length_mi} mi | elev: {g.elevation_gain_ft} ft | time: {g.duration_formatted}")
        loc = t.location
        coords = f"{loc.latitude},{loc.longitude}" if loc and loc.latitude and loc.longitude else "?"
        print(f"    location: {t.location} | coords: {coords}")
        print(f"    reviews: {len(t.reviews)}")


if __name__ == "__main__":
    main()
