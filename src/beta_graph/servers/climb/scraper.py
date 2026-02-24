"""Mountain Project scraper for climbing areas and routes."""

import logging
import re
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from beta_graph.servers.climb.config import (
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

logger = logging.getLogger(__name__)


def _get_with_retry(
    session: requests.Session,
    url: str,
    timeout: int = 15,
) -> requests.Response | None:
    """GET with retry on 503. Sleeps RETRY_ON_503_SLEEP_SEC between retries (max 30s total)."""
    last_exc = None
    for attempt in range(RETRY_ON_503_MAX_RETRIES + 1):
        try:
            r = session.get(url, timeout=timeout)
            if r.status_code == 503 and attempt < RETRY_ON_503_MAX_RETRIES:
                sleep_sec = min(RETRY_ON_503_SLEEP_SEC, 30)
                logger.warning(
                    "503 for %s (attempt %d/%d), sleeping %ds",
                    url, attempt + 1, RETRY_ON_503_MAX_RETRIES + 1, sleep_sec,
                )
                time.sleep(sleep_sec)
                continue
            return r
        except requests.RequestException as e:
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


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })
    return s


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


def scrape_area_page(
    url: str,
    session: requests.Session | None = None,
) -> tuple[str, str | None, str | None, tuple[float, float] | None, float | None, list[str]]:
    """Scrape an area page. Returns (name, description, getting_there, (lat,lon), elevation_ft, route_urls)."""
    sess = session or _session()
    route_urls: list[str] = []
    description = None
    getting_there = None
    gps: tuple[float, float] | None = None
    elevation_ft = None

    try:
        r = _get_with_retry(sess, url, timeout=15)
        if r is None:
            return ("", None, None, None, None, [])
        r.raise_for_status()
    except Exception as e:
        logger.warning("Failed to fetch area %s: %s", url, e)
        return ("", None, None, None, None, [])

    soup = BeautifulSoup(r.text, "html.parser")
    text = soup.get_text()

    # Area name from h1
    name = ""
    h1 = soup.find("h1")
    if h1:
        name = h1.get_text(strip=True).replace(" Climbing", "").replace(" Climb", "")

    # GPS from table row
    for row in soup.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) >= 2:
            label = cells[0].get_text(strip=True)
            val = cells[1].get_text(strip=True)
            if label == "GPS:":
                lat, lon = _parse_gps(val)
                if lat is not None and lon is not None:
                    gps = (lat, lon)
            elif "Elevation" in label:
                elevation_ft = _parse_elevation(val)

    # Description - h2 "Description" followed by content
    for h2 in soup.find_all("h2"):
        if "Description" in h2.get_text():
            block = h2.find_next_sibling()
            if block:
                description = block.get_text(strip=True)[:2000]
            break

    # Getting There
    for h2 in soup.find_all("h2"):
        if "Getting There" in h2.get_text():
            block = h2.find_next_sibling()
            if block:
                getting_there = block.get_text(strip=True)[:800]
            break

    # Route links - from classic table and any route links on page
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        m = ROUTE_LINK_PATTERN.search(href)
        if m:
            full = urljoin(MP_BASE, href.split("?")[0])
            if full not in seen:
                seen.add(full)
                route_urls.append(full)

    # Follow "More Classic Climbs" for full list
    more_link = soup.find("a", href=re.compile(r"/area/classics/"))
    if more_link and more_link.get("href"):
        classics_url = urljoin(MP_BASE, more_link["href"])
        time.sleep(REQUEST_DELAY)
        try:
            r2 = _get_with_retry(sess, classics_url, timeout=15)
            if r2 is None:
                raise requests.RequestException("503 after retries")
            r2.raise_for_status()
            soup2 = BeautifulSoup(r2.text, "html.parser")
            for a in soup2.find_all("a", href=True):
                m = ROUTE_LINK_PATTERN.search(a.get("href", ""))
                if m:
                    full = urljoin(MP_BASE, a["href"].split("?")[0])
                    if full not in seen:
                        seen.add(full)
                        route_urls.append(full)
        except Exception as e:
            logger.warning("Failed to fetch classics page %s: %s", classics_url, e)

    # Sub-areas: follow each to get more route links (e.g. Castle Rock, Rattlesnake Rock)
    base_url_norm = url.rstrip("/").split("?")[0]
    seen_sub: set[str] = set()
    sub_area_urls: list[str] = []
    for a in soup.find_all("a", href=AREA_LINK_PATTERN):
        href = a.get("href", "")
        if "/area/classics/" in href:
            continue
        full = urljoin(MP_BASE, href.split("?")[0])
        if full != base_url_norm and full not in seen_sub:
            seen_sub.add(full)
            sub_area_urls.append(full)

    for sub_url in sub_area_urls[:25]:  # Limit to avoid too many requests
        time.sleep(REQUEST_DELAY)
        try:
            r3 = _get_with_retry(sess, sub_url, timeout=15)
            if r3 is None:
                raise requests.RequestException("503 after retries")
            r3.raise_for_status()
            soup3 = BeautifulSoup(r3.text, "html.parser")
            for a in soup3.find_all("a", href=True):
                m = ROUTE_LINK_PATTERN.search(a.get("href", ""))
                if m:
                    full = urljoin(MP_BASE, a["href"].split("?")[0])
                    if full not in seen:
                        seen.add(full)
                        route_urls.append(full)
        except Exception as e:
            logger.debug("Failed to fetch sub-area %s: %s", sub_url, e)

    return (name, description, getting_there, gps, elevation_ft, route_urls)


def scrape_route_page(
    url: str,
    session: requests.Session | None = None,
    parent_area: str | None = None,
    area_gps: tuple[float, float] | None = None,
    area_elevation_ft: float | None = None,
) -> MPClimb | None:
    """Scrape a single route page."""
    sess = session or _session()
    m = ROUTE_LINK_PATTERN.search(url)
    if not m:
        return None
    route_id = m.group(1)
    slug = m.group(2)

    try:
        r = _get_with_retry(sess, url, timeout=15)
        if r is None:
            return None
        r.raise_for_status()
    except Exception as e:
        logger.warning("Failed to fetch route %s: %s", url, e)
        return None

    soup = BeautifulSoup(r.text, "html.parser")
    text = soup.get_text()

    name = slug.replace("-", " ").title()
    h1 = soup.find("h1")
    if h1:
        name = h1.get_text(strip=True)

    # Difficulty from h2 (e.g. "5.8+ YDS" or "V0 4" for boulders)
    difficulty = None
    for h2 in soup.find_all("h2"):
        diff_text = h2.get_text(strip=True)
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
    for row in soup.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) >= 2:
            label = cells[0].get_text(strip=True)
            val = cells[1].get_text(strip=True)
            if "Type:" in label:
                # Parse "Trad, 300 ft (91 m), 3 pitches"
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
            elif label == "GPS:":
                pass  # handle below

    # GPS - route-specific or fall back to area
    lat, lon = None, None
    for row in soup.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) >= 2 and "GPS" in cells[0].get_text():
            lat, lon = _parse_gps(cells[1].get_text())
            break
    if lat is None and area_gps:
        lat, lon = area_gps

    # Area path from breadcrumb links (e.g. Washington > Leavenworth > Tumwater Canyon > Castle Rock > Upper Castle)
    area_path = None
    area_name = None
    area_links = soup.find_all("a", href=AREA_LINK_PATTERN)
    seen_crumbs: list[str] = []
    for a in area_links:
        t = a.get_text(strip=True)
        if t and t not in seen_crumbs and len(t) > 2:
            seen_crumbs.append(t)
    if seen_crumbs:
        area_path = " > ".join(seen_crumbs)
        area_name = seen_crumbs[-1] if seen_crumbs else None

    # Description
    description = ""
    for h2 in soup.find_all("h2"):
        if "Description" in h2.get_text():
            block = h2.find_next_sibling()
            if block:
                description = block.get_text(strip=True)[:1500]
            break

    # Protection
    protection = None
    for h2 in soup.find_all("h2"):
        if "Protection" in h2.get_text():
            block = h2.find_next_sibling()
            if block:
                protection = block.get_text(strip=True)[:500]
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
    session: requests.Session | None = None,
    max_routes: int | None = None,
) -> list[MPClimb]:
    """Scrape an area and all its routes. area_url e.g. https://www.mountainproject.com/area/105794001/tumwater-canyon."""
    sess = session or _session()
    area_name, description, getting_there, area_gps, elevation_ft, route_urls = scrape_area_page(area_url, sess)

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
            # Ensure parent_area is set
            if not climb.parent_area:
                climb.parent_area = area_name
            climbs.append(climb)
        if (i + 1) % 10 == 0:
            time.sleep(REQUEST_DELAY)

        time.sleep(REQUEST_DELAY)

    return climbs
