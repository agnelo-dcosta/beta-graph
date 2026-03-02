"""Mountain Project scraper for climbing areas and routes - Scrapling-based."""

import contextlib
import logging
import re
import time
from urllib.parse import parse_qs, urljoin, urlparse

from scrapling.fetchers import Fetcher, FetcherSession

from beta_graph.servers.climb.config import (
    MAX_PAGINATION_PAGES,
    MAX_RECURSION_DEPTH,
    REQUEST_DELAY,
    RETRY_ON_503_MAX_RETRIES,
    RETRY_ON_503_SLEEP_SEC,
)
from beta_graph.servers.climb.models import Location, MPClimb

MP_BASE = "https://www.mountainproject.com"
# Area URL pattern: /area/105794001/tumwater-canyon
# Route URL pattern: /route/105790788/canary
ROUTE_LINK_PATTERN = re.compile(r"/route/(\d+)/([a-z0-9-]+)", re.I)
AREA_LINK_PATTERN = re.compile(r"/area/(\d+)/([a-z0-9-]+)", re.I)
# Route counts in "Areas in X" table: "51 / 6 / 2 / 0 / 0 / 0 / 0 / 0 / 56" - identifies child areas
ROUTE_COUNT_ROW_PATTERN = re.compile(r"\d+\s*/\s*\d+")

logger = logging.getLogger(__name__)


def _ensure_session(session=None):
    """Context manager: use provided session or create FetcherSession."""
    if session is not None:
        return contextlib.nullcontext(session)
    return FetcherSession(impersonate="chrome")


def _fetch_with_retry(session, url: str, timeout: int = 15):
    """GET url with retry on 503. Return Response or None."""
    last_exc = None
    for attempt in range(RETRY_ON_503_MAX_RETRIES + 1):
        try:
            if session is not None:
                page = session.get(url, timeout=timeout)
            else:
                page = Fetcher.get(url, timeout=timeout)
            if page.status == 503 and attempt < RETRY_ON_503_MAX_RETRIES:
                sleep_sec = min(RETRY_ON_503_SLEEP_SEC, 30)
                logger.warning(
                    "503 for %s (attempt %d/%d), sleeping %ds",
                    url, attempt + 1, RETRY_ON_503_MAX_RETRIES + 1, sleep_sec,
                )
                time.sleep(sleep_sec)
                continue
            if page.status >= 400:
                return None
            return page
        except Exception as e:
            last_exc = e
            if attempt < RETRY_ON_503_MAX_RETRIES:
                sleep_sec = min(RETRY_ON_503_SLEEP_SEC, 30)
                logger.warning("Request failed for %s: %s, sleeping %ds", url, e, sleep_sec)
                time.sleep(sleep_sec)
            else:
                break
    if last_exc:
        raise last_exc
    return None


def _parse_gps(text: str) -> tuple[float | None, float | None]:
    """Extract lat, lon from text like '47.60098, -120.71325'."""
    match = re.search(r"(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)", text)
    if match:
        try:
            return (float(match.group(1)), float(match.group(2)))
        except ValueError:
            pass
    return (None, None)


def _parse_elevation(text: str) -> float | None:
    """Extract elevation in feet from '1,551 ft' or '473 m'."""
    match = re.search(r"([\d,]+)\s*ft", text, re.I)
    if match:
        try:
            return float(match.group(1).replace(",", ""))
        except ValueError:
            pass
    return None


def _collect_route_urls_from_page(page, seen: set[str]) -> list[str]:
    """Extract route URLs from a page, deduplicated via seen set."""
    out: list[str] = []
    for a in page.css("a[href]"):
        href = a.attrib.get("href", "")
        m = ROUTE_LINK_PATTERN.search(href)
        if m:
            full = urljoin(MP_BASE, href.split("?")[0])
            if full not in seen:
                seen.add(full)
                out.append(full)
    return out


def _find_next_page_url(page, current_url: str) -> str | None:
    """Find pagination link: rel='next', or 'Next'/'»' link, or ?page=N+1."""
    # rel="next"
    for a in page.css('a[rel="next"]'):
        href = a.attrib.get("href", "")
        if href:
            return urljoin(MP_BASE, href)
    # Text "Next" or "»"
    for a in page.css("a[href]"):
        text = str(a.get_all_text(strip=True))
        if text in ("Next", "»", "›", ">") and a.attrib.get("href"):
            return urljoin(MP_BASE, a.attrib["href"].split("#")[0])
    # ?page=N pattern
    parsed = urlparse(current_url)
    params = parse_qs(parsed.query)
    page_num = int(params.get("page", ["1"])[0]) if params.get("page") else 1
    next_num = page_num + 1
    base = parsed._replace(query="").geturl()
    sep = "&" if "?" in current_url else "?"
    next_url = f"{base}{sep}page={next_num}" if "?" in base else f"{base}?page={next_num}"
    # Verify a next link exists (some sites use page=2 etc in links)
    for a in page.css("a[href]"):
        href = a.attrib.get("href", "")
        if f"page={next_num}" in href or f"page={next_num}&" in href:
            return urljoin(MP_BASE, href)
    return None


def _fetch_paginated_route_urls(
    sess,
    start_url: str,
    seen: set[str],
    max_pages: int = MAX_PAGINATION_PAGES,
) -> None:
    """Fetch a URL and follow pagination, adding route URLs to seen."""
    url = start_url
    pages_fetched = 0
    while url and pages_fetched < max_pages:
        time.sleep(REQUEST_DELAY)
        page = _fetch_with_retry(sess, url, timeout=15)
        if page is None:
            break
        _collect_route_urls_from_page(page, seen)
        pages_fetched += 1
        url = _find_next_page_url(page, url)


def _process_area_page_recursive(
    page,
    area_url: str,
    sess,
    seen_routes: set[str],
    visited_areas: set[str],
    depth: int,
    max_depth: int,
) -> None:
    """Process an area page (already fetched): collect routes, follow classics+paginate, recurse into sub-areas."""
    base_norm = area_url.rstrip("/").split("?")[0]
    if base_norm in visited_areas or depth > max_depth:
        return
    visited_areas.add(base_norm)

    _collect_route_urls_from_page(page, seen_routes)

    # Classics page - full route list for this area (with pagination)
    more_links = page.css('a[href*="/area/classics/"]')
    for ml in more_links[:1]:
        href = ml.attrib.get("href", "")
        if href:
            classics_url = urljoin(MP_BASE, href)
            _fetch_paginated_route_urls(sess, classics_url, seen_routes)

    # Sub-areas: prefer child areas (in "Areas in X" table with route counts).
    # Fall back to all area links if strict filter yields none (e.g. Washington state page).
    seen_sub: set[str] = set()
    sub_area_urls: list[str] = []
    fallback_urls: list[str] = []

    for a in page.css("a[href]"):
        href = a.attrib.get("href", "")
        if not AREA_LINK_PATTERN.search(href) or "/area/classics/" in href:
            continue
        full = urljoin(MP_BASE, href.split("?")[0])
        if full == base_norm or full in visited_areas or full in seen_sub:
            continue
        # Child areas appear in rows with route counts (e.g. "51 / 6 / 2 / 0 ...")
        parent = getattr(a, "parent", None)
        found = False
        for _ in range(8):  # Walk up to find containing row/block
            if parent is None:
                break
            row_text = str(parent.get_all_text()) if hasattr(parent, "get_all_text") else ""
            if ROUTE_COUNT_ROW_PATTERN.search(row_text):
                seen_sub.add(full)
                sub_area_urls.append(full)
                found = True
                break
            parent = getattr(parent, "parent", None)
        if not found:
            fallback_urls.append(full)

    # Use fallback only when strict filter finds nothing (some pages use different HTML)
    if not sub_area_urls and fallback_urls:
        for u in fallback_urls:
            if u not in visited_areas and u not in seen_sub:
                seen_sub.add(u)
                sub_area_urls.append(u)

    for sub_url in sub_area_urls:
        sub_norm = sub_url.rstrip("/").split("?")[0]
        if sub_norm in visited_areas:
            continue
        time.sleep(REQUEST_DELAY)
        sub_page = _fetch_with_retry(sess, sub_url, timeout=15)
        if sub_page is not None:
            _process_area_page_recursive(
                sub_page, sub_url, sess, seen_routes, visited_areas, depth + 1, max_depth
            )


def scrape_area_page(
    url: str,
    session=None,
    max_depth: int = MAX_RECURSION_DEPTH,
) -> tuple[str, str | None, str | None, tuple[float, float] | None, float | None, list[str]]:
    """Scrape an area page recursively. Returns (name, description, getting_there, (lat,lon), elevation_ft, route_urls).

    Collects routes from: main page, classics (with pagination), and all sub-areas recursively
    down to leaf crags. No sub-area limit; follows pagination on classics pages.
    """
    description = None
    getting_there = None
    gps: tuple[float, float] | None = None
    elevation_ft = None
    name = ""
    seen_routes: set[str] = set()
    visited_areas: set[str] = set()

    with _ensure_session(session) as sess:
        try:
            time.sleep(REQUEST_DELAY)
            page = _fetch_with_retry(sess, url, timeout=15)
            if page is None:
                return ("", None, None, None, None, [])
        except Exception as e:
            logger.warning("Failed to fetch area %s: %s", url, e)
            return ("", None, None, None, None, [])

        text = str(page.get_all_text(separator=" ", strip=True))

        # Area name from h1
        h1_list = page.css("h1")
        if h1_list:
            name = str(h1_list[0].get_all_text(strip=True)).replace(" Climbing", "").replace(" Climb", "")

        # GPS from table row
        for row in page.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) >= 2:
                label = str(cells[0].get_all_text(strip=True))
                val = str(cells[1].get_all_text(strip=True))
                if label == "GPS:":
                    lat, lon = _parse_gps(val)
                    if lat is not None and lon is not None:
                        gps = (lat, lon)
                elif "Elevation" in label:
                    elevation_ft = _parse_elevation(val)

        # Description - h2 "Description" followed by content
        for h2 in page.find_all("h2"):
            if "Description" in str(h2.get_all_text()):
                nxt = getattr(h2, "next", None)
                if nxt is not None:
                    description = str(nxt.get_all_text(strip=True))[:2000]
                break

        # Getting There
        for h2 in page.find_all("h2"):
            if "Getting There" in str(h2.get_all_text()):
                nxt = getattr(h2, "next", None)
                if nxt is not None:
                    getting_there = str(nxt.get_all_text(strip=True))[:800]
                break

        # Recursive collection: routes from this page, classics (paginated), all sub-areas (no limit)
        _process_area_page_recursive(
            page, url, sess, seen_routes, visited_areas, 0, max_depth
        )

    route_urls = list(seen_routes)
    return (name, description, getting_there, gps, elevation_ft, route_urls)


def scrape_route_page(
    url: str,
    session=None,
    parent_area: str | None = None,
    area_gps: tuple[float, float] | None = None,
    area_elevation_ft: float | None = None,
) -> MPClimb | None:
    """Scrape a single route page."""
    m = ROUTE_LINK_PATTERN.search(url)
    if not m:
        return None
    route_id = m.group(1)
    slug = m.group(2)

    with _ensure_session(session) as sess:
        try:
            page = _fetch_with_retry(sess, url, timeout=15)
            if page is None:
                return None
        except Exception as e:
            logger.warning("Failed to fetch route %s: %s", url, e)
            return None

        text = str(page.get_all_text(separator=" ", strip=True))

        name = slug.replace("-", " ").title()
        h1_list = page.css("h1")
        if h1_list:
            name = str(h1_list[0].get_all_text(strip=True))

        # Difficulty from h2 (e.g. "5.8+ YDS" or "V0 4" for boulders)
        difficulty = None
        for h2 in page.find_all("h2"):
            diff_text = str(h2.get_all_text(strip=True))
            if any(x in diff_text for x in ("YDS", "V0", "V1", "V2", "French", "5.")):
                yd_match = re.search(r"(5\.\d+[a-d]?\+?|V\d+\+?|\d+[a-d])", diff_text)
                if yd_match:
                    difficulty = yd_match.group(1).strip()
                break

        # Rating from "Avg: 3.4 from 308 votes"
        rating = None
        votes = None
        avg_match = re.search(r"Avg:\s*([\d.]+)\s+from\s+(\d+)\s+votes", text, re.I)
        if avg_match:
            try:
                rating = float(avg_match.group(1))
                votes = int(avg_match.group(2))
            except ValueError:
                pass

        # Type and stats from table: "Type: | Trad, 300 ft (91 m), 3 pitches, Grade II"
        climb_type = None
        length_ft = None
        pitches = None
        for row in page.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) >= 2:
                label = str(cells[0].get_all_text(strip=True))
                val = str(cells[1].get_all_text(strip=True))
                if "Type:" in label:
                    climb_type = val.split(",")[0].strip()
                    ft_match = re.search(r"([\d.]+)\s*ft", val)
                    if ft_match:
                        try:
                            length_ft = float(ft_match.group(1))
                        except ValueError:
                            pass
                    pitch_match = re.search(r"(\d+)\s*pitches?", val, re.I)
                    if pitch_match:
                        try:
                            pitches = int(pitch_match.group(1))
                        except ValueError:
                            pass

        # GPS - route-specific or fall back to area
        lat, lon = None, None
        for row in page.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) >= 2 and "GPS" in str(cells[0].get_all_text()):
                lat, lon = _parse_gps(str(cells[1].get_all_text()))
                break
        if lat is None and area_gps:
            lat, lon = area_gps

        # Area path from breadcrumb links (e.g. Washington > Leavenworth > Tumwater Canyon)
        area_path = None
        area_name = None
        area_links = page.css("a[href*='/area/']")
        seen_crumbs: list[str] = []
        for a in area_links:
            href = a.attrib.get("href", "")
            if AREA_LINK_PATTERN.search(href):
                t = str(a.get_all_text(strip=True))
                if t and t not in seen_crumbs and len(t) > 2:
                    seen_crumbs.append(t)
        if seen_crumbs:
            area_path = " > ".join(seen_crumbs)
            area_name = seen_crumbs[-1] if seen_crumbs else None

        # Description
        description = ""
        for h2 in page.find_all("h2"):
            if "Description" in str(h2.get_all_text()):
                nxt = getattr(h2, "next", None)
                if nxt is not None:
                    description = str(nxt.get_all_text(strip=True))[:1500]
                break

        # Protection
        protection = None
        for h2 in page.find_all("h2"):
            if "Protection" in str(h2.get_all_text()):
                nxt = getattr(h2, "next", None)
                if nxt is not None:
                    protection = str(nxt.get_all_text(strip=True))[:500]
                break

        location = None
        if lat is not None and lon is not None:
            location = Location(latitude=lat, longitude=lon)

        return MPClimb(
            name=name,
            route_id=route_id,
            url=url,
            difficulty=difficulty,
            climb_type=climb_type,
            rating=rating,
            votes=votes,
            pitches=pitches,
            length_ft=length_ft,
            description=description,
            protection=protection,
            location=location,
            area_name=area_name,
            area_path=area_path,
            parent_area=parent_area,
            elevation_ft=area_elevation_ft,
        )


def scrape_area(
    area_url: str,
    session=None,
    max_routes: int | None = None,
    max_depth: int = MAX_RECURSION_DEPTH,
) -> list[MPClimb]:
    """Scrape an area and all its routes. area_url e.g. https://www.mountainproject.com/area/105794001/tumwater-canyon."""
    with _ensure_session(session) as sess:
        area_name, description, getting_there, area_gps, elevation_ft, route_urls = scrape_area_page(
            area_url, sess, max_depth=max_depth
        )

        if not area_name:
            area_name = "Unknown Area"

        logger.info("Area %s: %d routes found", area_name, len(route_urls))

        climbs: list[MPClimb] = []
        for i, route_url in enumerate(route_urls):
            if max_routes and len(climbs) >= max_routes:
                break
            climb = scrape_route_page(
                route_url,
                session=sess,
                parent_area=area_name,
                area_gps=area_gps,
                area_elevation_ft=elevation_ft,
            )
            if climb:
                if not climb.parent_area:
                    climb.parent_area = area_name
                climbs.append(climb)
            if (i + 1) % 10 == 0:
                time.sleep(REQUEST_DELAY)
            time.sleep(REQUEST_DELAY)

        return climbs
