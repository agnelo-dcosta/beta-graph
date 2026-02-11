#!/usr/bin/env python3
"""Test AllTrails scraping with requests (no Playwright).

Usage:
    python scripts/test_scrape_requests.py [URL]
    python scripts/test_scrape_requests.py [URL] --enrich
    python scripts/test_scrape_requests.py [URL] --output explore_rock_climbing.json

    With cookies (paste Cookie header from browser into keys/alltrails_cookies):
    python scripts/test_scrape_requests.py

Scrapes all trail links, parses trail cards, and writes to OUTPUT_FILE (or --output).
By default fetches each trail's detail page for trailGeoStats (length, elevation, duration),
tags, reviews, and coordinates. Use --no-enrich to skip (faster, but reviews empty, trailGeoStats partial).
Saves north_bend_requests_debug.html when 0 trails to inspect response.
"""

import json
import re
import sys
import time
from pathlib import Path

# Add src to path when run from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

# Use requests for detail fetch (matches this script; Playwright may not be installed)
import os
os.environ["USE_PLAYWRIGHT"] = "false"

DEFAULT_URL = "https://www.alltrails.com/us/washington/north-bend"
OUTPUT_FILE = "north_bend_trails_new.json"
EXPLORE_OUTPUT_FILE = "explore_trails.json"
DEBUG_HTML = "north_bend_requests_debug.html"


def main():
    args = [a for a in sys.argv[1:] if a not in ("--enrich", "--no-enrich") and not a.startswith("--output=")]
    enrich = "--no-enrich" not in sys.argv
    url = args[0] if args else DEFAULT_URL

    # Output file: --output=FILE, or explore_trails.json for /explore URLs, else requests_trails.json
    output_file = OUTPUT_FILE
    for a in sys.argv[1:]:
        if a.startswith("--output="):
            output_file = a.split("=", 1)[1].strip()
            break
    if "/explore" in url and output_file == OUTPUT_FILE:
        output_file = EXPLORE_OUTPUT_FILE

    from beta_graph.servers.alltrails.cookies import create_session_with_cookies

    session = create_session_with_cookies()
    has_cookies = "Cookie" in session.headers

    print(f"Fetching {url}...")
    print(f"Cookies: {'yes' if has_cookies else 'no (add keys/alltrails_cookies for better chance)'}")

    try:
        resp = session.get(url, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"Request failed: {e}")
        return

    html = resp.text

    # Check for captcha/block
    if "captcha-delivery.com" in html:
        print("Got captcha page (bot detection).")
    elif "temporarily restricted" in html.lower() or "access is temporarily" in html.lower():
        print("Got 'access temporarily restricted' page.")
    else:
        print("Got page (no obvious captcha/block).")

    # Use the scraper's logic (picks best card per trail)
    from beta_graph.servers.alltrails.scraper import scrape_with_requests

    trails = scrape_with_requests(url, html=html)

    if enrich and trails:
        print("Enriching trails with detail pages (trailGeoStats, tags, reviews, elevation)...")
        from beta_graph.servers.alltrails.trail_detail import enrich_trail_with_detail

        for i, trail in enumerate(trails):
            try:
                enrich_trail_with_detail(trail, session=session)
                print(f"  Enriched {i + 1}/{len(trails)}: {trail.name} ({len(trail.reviews)} reviews)")
            except Exception as e:
                print(f"  Skip {trail.name}: {e}")
            if (i + 1) % 3 == 0:
                time.sleep(1)  # Be nice to the server

    link_count = len(re.findall(r'href="/trail/[a-z]{2}/[a-z0-9-]+/[a-z0-9-]+"', html, re.I))
    print(f"Trail links in HTML: {link_count}")
    print(f"Parsed trails: {len(trails)}")

    # Always write trail cards to file
    out_dir = Path(__file__).parent
    out_json = out_dir / output_file
    def _dump(t):
        d = t.model_dump(mode="json", exclude_none=True)
        # Always show full trailGeoStats structure (elevation from detail page)
        if t.trailGeoStats:
            d["trailGeoStats"] = {
                "length_mi": t.trailGeoStats.length_mi,
                "elevation_gain_ft": t.trailGeoStats.elevation_gain_ft,
                "elevation_max_ft": t.trailGeoStats.elevation_max_ft,
                "duration_formatted": t.trailGeoStats.duration_formatted,
            }
        return d

    data = [_dump(t) for t in trails]
    out_json.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"Wrote {len(trails)} trail cards to {out_json}")

    if trails:
        for t in trails[:5]:
            g = t.trailGeoStats
            print(f"  {t.name} | {t.difficulty} | {f'{g.length_mi} mi' if g and g.length_mi else '?'} | reviews: {len(t.reviews)}")
    else:
        out_html = out_dir / DEBUG_HTML
        out_html.write_text(html, encoding="utf-8")
        print(f"Saved HTML to {out_html} for inspection.")


if __name__ == "__main__":
    main()
