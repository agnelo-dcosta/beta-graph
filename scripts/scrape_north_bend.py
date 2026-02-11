#!/usr/bin/env python3
"""Scrape North Bend trails with Playwright and optionally save to file.

Usage:
    python scripts/scrape_north_bend.py

    With login (browser opens automatically to solve captcha):
    ALLTRAILS_EMAIL=you@example.com ALLTRAILS_PASSWORD=xxx python scripts/scrape_north_bend.py

    Force headed mode without login:
    HEADED=1 python scripts/scrape_north_bend.py

Set SAVE_TO_FILE = False or comment out the save call to skip writing results.
"""

import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

# Add src to path when run from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

# Set to False to skip saving; or comment out the save call in main()
SAVE_TO_FILE = True
OUTPUT_FILE = "outputs/north_bend_trails.json"
DEBUG_HTML_FILE = "north_bend_debug.html"  # Saved when 0 trails (comment out to disable)

NORTH_BEND_URL = "https://www.alltrails.com/us/washington/north-bend"
NORTH_BEND_HIKING_URL = "https://www.alltrails.com/us/washington/north-bend/hiking"
TRAIL_LINK_PATTERN = re.compile(r"^/trail/[a-z]{2}/[a-z0-9-]+/[a-z0-9-]+$", re.I)
LOGIN_URL = "https://www.alltrails.com/login"

# Credentials via env (e.g. ALLTRAILS_EMAIL=... ALLTRAILS_PASSWORD=... python scripts/scrape_north_bend.py)
ALLTRAILS_EMAIL = os.environ.get("ALLTRAILS_EMAIL")
ALLTRAILS_PASSWORD = os.environ.get("ALLTRAILS_PASSWORD")
# Run headed to see browser and solve captcha. Set explicitly or auto when credentials provided.
_headed_env = os.environ.get("HEADED", "").lower()
HEADED = (
    _headed_env in ("1", "true", "yes")
    or (_headed_env != "0" and _headed_env != "false" and bool(ALLTRAILS_EMAIL and ALLTRAILS_PASSWORD))
)


def save_trails_to_file(trails: list, filepath: str | Path) -> None:
    """Write trails to JSON file. Comment out the call in main() to disable saving.

    Args:
        trails: List of Trail instances.
        filepath: Output file path (e.g. north_bend_trails.json).
    """
    path = Path(filepath)
    data = [t.model_dump(mode="json") for t in trails]
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"Saved {len(trails)} trails to {path.resolve()}")


def _login_alltrails(page, email: str, password: str) -> bool:
    """Log in to AllTrails. Returns True if login appears successful."""
    try:
        page.goto(LOGIN_URL, wait_until="networkidle", timeout=20000)
        if HEADED:
            input("  → Solve captcha if shown, then press Enter to continue...")
        else:
            time.sleep(2)

        # Try common form selectors
        email_sel = 'input[type="email"], input[name="user[email]"], input[name="email"], input[placeholder*="mail" i]'
        password_sel = 'input[type="password"], input[name="user[password]"], input[name="password"]'
        submit_sel = 'button[type="submit"], input[type="submit"], [data-testid="login-button"], button:has-text("Log in"), button:has-text("Sign in")'

        page.locator(email_sel).first.fill(email)
        page.locator(password_sel).first.fill(password)
        page.locator(submit_sel).first.click()
        time.sleep(3)  # Wait for redirect

        # Check if we're still on login (captcha or failed)
        if "login" in page.url or "sign_in" in page.url:
            return False
        return True
    except Exception as e:
        print(f"Login failed: {e}")
        return False


def _scrape_with_debug(url: str, email: str | None = None, password: str | None = None) -> tuple[list, str | None]:
    """Scrape region page. Optionally log in first if email/password provided. Returns (trails, html)."""
    from playwright.sync_api import sync_playwright

    from beta_graph.servers.alltrails.models import Trail
    from beta_graph.servers.alltrails.scraper import (
        _extract_slug,
        _parse_trail_card,
    )
    from bs4 import BeautifulSoup

    trails: list = []
    html_content: str | None = None

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not HEADED)
        page = browser.new_page()
        page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        })

        if email and password:
            print("Logging in...")
            if _login_alltrails(page, email, password):
                print("Login OK, proceeding to scrape.")
            else:
                print("Login may have failed (captcha?). Continuing anyway...")

        page.goto(url, wait_until="networkidle", timeout=30000)
        if HEADED:
            input("  → If you see captcha on the region page, solve it and press Enter...")
        time.sleep(3)

        # Scroll to trigger lazy-loaded trails
        for _ in range(5):
            page.evaluate("window.scrollBy(0, 800)")
            time.sleep(1.5)

        html_content = page.content()
        browser.close()

    soup = BeautifulSoup(html_content, "html.parser")
    seen: set[str] = set()
    for link in soup.find_all("a", href=TRAIL_LINK_PATTERN):
        href = link.get("href", "")
        full_url = urljoin(url, href)
        slug = _extract_slug(full_url)
        if slug in seen:
            continue
        seen.add(slug)
        parent = link.find_parent(["li", "article", "div"], class_=True) or link.find_parent("div")
        card = parent if parent else link
        trail = _parse_trail_card(card, url)
        if trail and trail.slug:
            trails.append(trail)

    by_slug: dict = {}
    for t in trails:
        if t.slug not in by_slug or len(t.description) > len(by_slug[t.slug].description):
            by_slug[t.slug] = t
    trails = list(by_slug.values())

    return trails, html_content


def main():
    os.environ["USE_PLAYWRIGHT"] = "true"

    if HEADED:
        print("Running in headed mode (browser window will open)...")
    # Try hiking subpage first (trail list may load better)
    print(f"Scraping {NORTH_BEND_HIKING_URL} with Playwright...")
    trails, html = _scrape_with_debug(
        NORTH_BEND_HIKING_URL,
        email=ALLTRAILS_EMAIL,
        password=ALLTRAILS_PASSWORD,
    )

    if not trails and html:
        print("Trying base region URL...")
        trails, html = _scrape_with_debug(
            NORTH_BEND_URL,
            email=ALLTRAILS_EMAIL,
            password=ALLTRAILS_PASSWORD,
        )

    if not trails and html:
        # Count trail links (pattern without anchors for findall)
        link_count = len(re.findall(r'href="/trail/[a-z]{2}/[a-z0-9-]+/[a-z0-9-]+"', html, re.I))
        print(f"DEBUG: Found {link_count} /trail/... links in HTML")
        if DEBUG_HTML_FILE:
            Path(DEBUG_HTML_FILE).write_text(html, encoding="utf-8")
            print(f"DEBUG: Saved page HTML to {DEBUG_HTML_FILE}. Inspect it to see what AllTrails returned.")

    if trails:
        from beta_graph.servers.alltrails.scraper import scrape_trails
        from beta_graph.servers.alltrails.trail_detail import enrich_trail_with_detail

        print(f"Fetching details for {len(trails)} trails...")
        for i, trail in enumerate(trails):
            try:
                enrich_trail_with_detail(trail)
            except Exception:
                pass
            if (i + 1) % 5 == 0:
                time.sleep(1)
    else:
        print("Got 0 trails. Possible causes: bot detection, login wall, or page structure changed.")

    print(f"Got {len(trails)} trails")

    for t in trails[:5]:
        g = t.trailGeoStats
        loc = t.location.city if t.location else ""
        print(f"  {t.name} | {f'{g.length_mi} mi' if g and g.length_mi else '?'} | {f'{g.elevation_gain_ft} ft' if g and g.elevation_gain_ft else '?'} | {loc}")

    if SAVE_TO_FILE and trails:
        save_trails_to_file(trails, OUTPUT_FILE)


if __name__ == "__main__":
    main()
