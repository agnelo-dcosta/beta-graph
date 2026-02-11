#!/usr/bin/env python3
"""Scrape Yosemite climbing trails from El Capitan POI + rock-climbing filter.

Usage:
    python scripts/scrape_yosemite_climbing.py

    With cookies (paste Cookie header from browser into keys/alltrails_cookies):
    python scripts/scrape_yosemite_climbing.py

Combines trails from:
    - https://www.alltrails.com/poi/us/california/el-capitan--2
    - https://www.alltrails.com/us/california/yosemite-valley/rock-climbing

Enriches each trail with detail (trailGeoStats, tags, reviews, coordinates).
Saves to yosemite_trails.json (same format as north_bend / requests_trails).
"""

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
os.environ["USE_PLAYWRIGHT"] = "false"

OUTPUT_FILE = "outputs/yosemite_trails_new.json"
URLS = [
    "https://www.alltrails.com/poi/us/california/el-capitan--2",
    "https://www.alltrails.com/us/california/yosemite-valley/rock-climbing",
]


def _dump_trail(t):
    """Dump trail to dict matching north_bend/requests_trails format."""
    d = t.model_dump(mode="json", exclude_none=True)
    if t.trailGeoStats:
        d["trailGeoStats"] = {
            "length_mi": t.trailGeoStats.length_mi,
            "elevation_gain_ft": t.trailGeoStats.elevation_gain_ft,
            "elevation_max_ft": t.trailGeoStats.elevation_max_ft,
            "duration_formatted": t.trailGeoStats.duration_formatted,
        }
    return d


def main():
    from beta_graph.servers.alltrails.cookies import create_session_with_cookies
    from beta_graph.servers.alltrails.scraper import scrape_with_requests
    from beta_graph.servers.alltrails.trail_detail import enrich_trail_with_detail

    session = create_session_with_cookies()
    has_cookies = "Cookie" in session.headers
    print(f"Cookies: {'yes' if has_cookies else 'no (add keys/alltrails_cookies if you get 403)'}")

    by_slug: dict = {}
    for url in URLS:
        try:
            print(f"Fetching {url}...")
            resp = session.get(url, timeout=15)
            resp.raise_for_status()
            trails = scrape_with_requests(url, html=resp.text)
            print(f"  -> {len(trails)} trails")
            for t in trails:
                if t.slug not in by_slug or len(t.description or "") > len(by_slug[t.slug].description or ""):
                    by_slug[t.slug] = t
        except Exception as e:
            print(f"  -> Failed: {e}")

    trails = list(by_slug.values())
    if not trails:
        print("No trails found. Add cookies to keys/alltrails_cookies and retry.")
        return

    print(f"Enriching {len(trails)} trails (detail pages)...")
    for i, trail in enumerate(trails):
        try:
            enrich_trail_with_detail(trail, session=session)
            print(f"  {i + 1}/{len(trails)}: {trail.name} ({len(trail.reviews)} reviews)")
        except Exception as e:
            print(f"  Skip {trail.name}: {e}")
        if (i + 1) % 3 == 0:
            time.sleep(1)

    out_path = Path(__file__).parent / OUTPUT_FILE
    data = [_dump_trail(t) for t in trails]
    out_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"Wrote {len(trails)} trails to {out_path}")

    for t in trails[:5]:
        g = t.trailGeoStats
        print(f"  {t.name} | {t.difficulty or '?'} | {f'{g.length_mi} mi' if g and g.length_mi else '?'} | {len(t.reviews)} reviews")


if __name__ == "__main__":
    main()
