"""AllTrails scraper for region trail pages."""

import re
import time
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from beta_graph.shared.config import USE_PLAYWRIGHT
from beta_graph.servers.alltrails.cookies import create_session_with_cookies
from beta_graph.servers.alltrails.models import Location, Trail, TrailGeoStats

TRAIL_LINK_PATTERN = re.compile(r"^/trail/[a-z]{2}/[a-z0-9-]+/[a-z0-9-]+$", re.I)
# Also matches absolute URLs (e.g. https://alltrails.com/trail/us/washington/slug)
TRAIL_LINK_PATTERN_FLEX = re.compile(r"/trail/[a-z]{2}/[a-z0-9-]+/[a-z0-9-]+", re.I)


def _extract_slug(url: str) -> str:
    """Extract the trail slug (last path segment) from a trail URL.

    Args:
        url: Full trail URL (e.g. https://alltrails.com/trail/us/washington/rattlesnake-ledge).

    Returns:
        Slug string (e.g. 'rattlesnake-ledge').
    """
    path = urlparse(url).path
    parts = path.rstrip("/").split("/")
    return parts[-1] if parts else ""


def _find_trail_card_ancestor(link):
    """Find the smallest ancestor that contains both rating and distance (trail card).

    Must have all trail links pointing to the same trail (same href) to avoid
    mixing FAQ/embed links with the main trail list cards.
    """
    def _path(h):
        return urlparse(h).path if (h or "").startswith("http") else (h or "")

    href = link.get("href", "")
    link_path = _path(href)
    p = link.parent
    while p and p.name != "body":
        rating_el = p.find(attrs={"data-testid": "rating"})
        dist_el = p.find(attrs={"data-testid": "distance"})
        if rating_el and dist_el and rating_el.get_text(strip=True) and dist_el.get_text(strip=True):
            trail_links = p.find_all("a", href=TRAIL_LINK_PATTERN_FLEX)
            # All links in card must point to same trail (no multi-trail container)
            if trail_links and all(_path(tl.get("href")) == link_path for tl in trail_links):
                return p
        p = getattr(p, "parent", None)
    return None


def _parse_trail_card(card, base_url: str) -> Trail | None:
    """Parse a trail card element from the region page into a Trail model.

    Uses data-testid elements (rating, difficulty, distance, duration) when present,
    otherwise falls back to regex on card text. Supports both km and mi.

    Args:
        card: BeautifulSoup element containing the trail link and metadata.
        base_url: Base URL for resolving relative links.

    Returns:
        Trail instance or None if parsing fails.
    """
    link = card.find("a", href=TRAIL_LINK_PATTERN_FLEX)
    if not link:
        return None

    href = link.get("href", "")
    full_url = urljoin(base_url, href)
    slug = _extract_slug(full_url)

    name = link.get_text(strip=True) or ""
    name = re.sub(r"^#\d+\s*-\s*", "", name)

    # Prefer data-testid elements (modern AllTrails structure)
    rating_el = card.find(attrs={"data-testid": "rating"})
    diff_el = card.find(attrs={"data-testid": "difficulty"})
    dist_el = card.find(attrs={"data-testid": "distance"})
    dura_el = card.find(attrs={"data-testid": "duration"})

    rating = rating_el.get_text(strip=True) if rating_el else None
    difficulty = None
    if diff_el:
        d = (diff_el.get_text(strip=True) or "").lstrip("\u00b7\u00a0 ")
        difficulty = d if d else None
    est_time = None
    if dura_el:
        t = (dura_el.get_text(strip=True) or "").lstrip("\u00b7\u00a0 ")
        est_time = t if t else None

    mi_val = None
    if dist_el:
        dist_text = dist_el.get_text(strip=True)
        mi_match = re.search(r"(\d+\.?\d*)\s*mi", dist_text, re.I)
        km_match = re.search(r"(\d+\.?\d*)\s*km", dist_text, re.I)
        if mi_match:
            mi_val = float(mi_match.group(1))
        elif km_match:
            mi_val = float(km_match.group(1)) / 1.60934

    # Fallback to regex on card text
    card_text = card.get_text(separator=" ", strip=True)
    if not rating:
        m = re.search(r"(\d+\.\d+)\s*\(\d+\)", card_text)
        rating = m.group(0) if m else None
    if not difficulty:
        for d in ("Easy", "Moderate", "Hard", "Strenuous"):
            if d in card_text:
                difficulty = d
                break
    if mi_val is None:
        mi_match = re.search(r"(\d+\.?\d*)\s*mi", card_text, re.I)
        km_match = re.search(r"(\d+\.?\d*)\s*km", card_text, re.I)
        if mi_match:
            mi_val = float(mi_match.group(1))
        elif km_match:
            mi_val = float(km_match.group(1)) / 1.60934
    if not est_time:
        m = re.search(r"Est\.\s*[\d]+h\s*[\d]+m", card_text)
        est_time = m.group(0) if m else None

    desc_elem = card.find("p") or card.find(class_=re.compile(r"description|summary|overview", re.I))
    description = desc_elem.get_text(strip=True) if desc_elem else ""

    path = urlparse(base_url).path
    parts = [p for p in path.strip("/").split("/") if p]
    # e.g. /us/washington/north-bend -> city=North Bend; /explore -> no region, use Unknown
    if parts and parts[0].lower() == "explore" and len(parts) == 1:
        city, region_name, region = "Unknown", None, None
        location = Location(city="Unknown")
    else:
        city = parts[-1].replace("-", " ").title() if parts else None
        region_name = parts[-2].replace("-", " ").title() if len(parts) >= 2 else None
        region = region_name
        location = Location(
            city=city or "Unknown",
            region=region,
            regionName=region_name,
            country="US" if any(p.lower() == "us" for p in parts) else None,
            country_name="United States" if any(p.lower() == "us" for p in parts) else None,
        ) if city else None

    # trailGeoStats from region page (length_mi, duration); detail page fills elevation
    trail_geo = None
    if mi_val is not None:
        trail_geo = TrailGeoStats(length_mi=round(mi_val, 2), duration_formatted=est_time)

    return Trail(
        name=name or slug.replace("-", " ").title(),
        url=full_url,
        slug=slug,
        rating=rating,
        difficulty=difficulty,
        trailGeoStats=trail_geo,
        est_time=est_time,
        description=description[:500] if description else "",
        location=location or Location(city="Unknown"),
    )


def scrape_with_requests(url: str, *, html: str | None = None) -> list[Trail]:
    """Scrape region page using HTTP requests. Uses cookies from file if present.

    May fail if AllTrails serves bot block. Put cookies in keys/alltrails_cookies (or
    ALLTRAILS_COOKIE_FILE) to bypass; paste the Cookie header value from Postman.

    Args:
        url: AllTrails region URL.
        html: Optional pre-fetched HTML. If provided, skips the request.

    Returns:
        List of Trail instances.
    """
    if html is None:
        session = create_session_with_cookies()
        resp = session.get(url)
        resp.raise_for_status()
        html = resp.text
    soup = BeautifulSoup(html, "html.parser")

    # Collect all links per slug; use the card with the most metadata (rating, length, etc.)
    links_by_slug: dict[str, list] = {}
    for link in soup.find_all("a", href=TRAIL_LINK_PATTERN_FLEX):
        href = link.get("href", "")
        full_url = urljoin(url, href)
        slug = _extract_slug(full_url)
        if not slug:
            continue
        if slug not in links_by_slug:
            links_by_slug[slug] = []
        links_by_slug[slug].append(link)

    trails: list[Trail] = []
    for slug, links in links_by_slug.items():
        best_card = None
        best_score = -1
        for link in links:
            # Prefer ancestor with data-testid rating+distance (actual trail card)
            card = _find_trail_card_ancestor(link)
            if not card:
                parent = link.find_parent(["li", "article", "div"], class_=True) or link.find_parent("div")
                card = parent if parent else link
            card_text = card.get_text(separator=" ", strip=True)
            # Score: data-testid card > regex-based (rating, length, est_time)
            has_testid = bool(card.find(attrs={"data-testid": "rating"})) and bool(card.find(attrs={"data-testid": "distance"}))
            score = 10 if has_testid else 0
            score += sum(1 for x in (r"(\d+\.\d+)\(\d+\)", r"\d+\.?\d*\s*km", r"\d+\.?\d*\s*mi", r"Est\.\s*[\d]+h") if re.search(x, card_text, re.I))
            if score > best_score:
                best_score = score
                best_card = card
        if best_card:
            trail = _parse_trail_card(best_card, url)
            if trail and trail.slug:
                trails.append(trail)

    by_slug: dict[str, Trail] = {}
    for t in trails:
        if t.slug not in by_slug or len(t.description or "") > len(by_slug[t.slug].description or ""):
            by_slug[t.slug] = t
    return list(by_slug.values())


def scrape_with_playwright(url: str) -> list[Trail]:
    """Scrape region page using Playwright (real browser). Bypasses bot detection.

    Args:
        url: AllTrails region URL.

    Returns:
        List of Trail instances.
    """
    from playwright.sync_api import sync_playwright

    trails: list[Trail] = []
    seen_slugs: set[str] = set()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"})
        page.goto(url, wait_until="networkidle", timeout=30000)
        time.sleep(2)
        html = page.content()
        browser.close()

    soup = BeautifulSoup(html, "html.parser")
    for link in soup.find_all("a", href=TRAIL_LINK_PATTERN_FLEX):
        href = link.get("href", "")
        full_url = urljoin(url, href)
        slug = _extract_slug(full_url)
        if slug in seen_slugs:
            continue
        seen_slugs.add(slug)
        parent = link.find_parent(["li", "article", "div"], class_=True) or link.find_parent("div")
        card = parent if parent else link
        trail = _parse_trail_card(card, url)
        if trail and trail.slug:
            trails.append(trail)

    by_slug: dict[str, Trail] = {}
    for t in trails:
        if t.slug not in by_slug or len(t.description) > len(by_slug[t.slug].description):
            by_slug[t.slug] = t
    return list(by_slug.values())


def scrape_trails(url: str, include_details: bool = False) -> list[Trail]:
    """Scrape trails from an AllTrails region page.

    Uses Playwright or requests based on USE_PLAYWRIGHT config. Caller must validate URL first.

    Args:
        url: AllTrails region URL (caller must validate first).
        include_details: If True, fetch each trail's detail page for coordinates and reviews.
            Slower but richer data.

    Returns:
        List of Trail instances.
    """
    if USE_PLAYWRIGHT:
        trails = scrape_with_playwright(url)
    else:
        trails = scrape_with_requests(url)

    if include_details and trails:
        from beta_graph.servers.alltrails.trail_detail import enrich_trail_with_detail

        for i, trail in enumerate(trails):
            try:
                enrich_trail_with_detail(trail)
            except Exception:
                pass  # Keep trail even if detail fetch fails
            if (i + 1) % 5 == 0:
                time.sleep(1)  # Be nice to the server

    return trails
