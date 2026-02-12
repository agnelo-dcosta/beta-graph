"""WTA scraper for trail pages - requests-based, no bot blocking."""

import json
import re
import time
from collections.abc import Callable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from beta_graph.servers.wta.models import (
    Location,
    TripReport,
    TripReportCondition,
    WTATrail,
)

WTA_BASE = "https://www.wta.org"
HIKES_LIST_URL = f"{WTA_BASE}/go-outside/hikes"
# Match both relative (/go-hiking/hikes/slug) and absolute (https://.../go-hiking/hikes/slug)
TRAIL_LINK_PATTERN = re.compile(r"/go-hiking/hikes/([a-z0-9-]+)/?$", re.I)

# Rate limit between requests
REQUEST_DELAY = 0.5

# Max trip reports to fetch per trail
MAX_TRIP_REPORTS = 10


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })
    return s


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance in miles between two points."""
    import math
    R = 3959  # Earth radius in miles
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def _parse_trip_report_page(url: str, session: requests.Session) -> TripReport | None:
    """Fetch and parse a single trip report page."""
    try:
        r = session.get(url, timeout=15)
        r.raise_for_status()
    except Exception:
        return None

    soup = BeautifulSoup(r.text, "html.parser")

    # Extract date from URL or page
    date_str: str | None = None
    match = re.search(r"trip_report-(\d{4})-(\d{2})-(\d{2})", url)
    if match:
        date_str = f"{match.group(1)}-{match.group(2)}-{match.group(3)}"

    # Conditions from #trip-conditions - each div.trip-condition has h4 (label) + value
    cond = TripReportCondition()
    tc = soup.find(id="trip-conditions")
    if tc:
        for div in tc.find_all("div", class_="trip-condition"):
            h4 = div.find("h4")
            label = h4.get_text(strip=True) if h4 else ""
            full = div.get_text(strip=True)
            val = full.replace(label, "", 1).strip() if label else full
            if not val:
                continue
            if label == "Type of Hike":
                cond.type_of_hike = val
            elif label == "Trail Conditions":
                cond.trail_conditions = val
            elif label == "Road":
                cond.road = val
            elif label == "Bugs":
                cond.bugs = val
            elif label == "Snow":
                cond.snow = val

    # Description - look for narrative (exclude nav/header junk)
    _NAV_JUNK = ("menu", "home", "our work", "explore our work", "trails for everyone", "site search", "donate", "go outside")
    description = ""
    for div in soup.find_all(["div", "p"], class_=re.compile(r"description|content|report-body|story", re.I)):
        txt = div.get_text(strip=True)
        if 80 < len(txt) < 1500 and "trail" in txt.lower():
            if "type of hike" not in txt.lower() and "trail conditions" not in txt.lower():
                if "washington trails" not in txt.lower() and "association" not in txt.lower():
                    if not any(j in txt.lower()[:100] for j in _NAV_JUNK):
                        description = txt[:500]
                        break

    # If no narrative, use conditions as summary
    if not description and (cond.trail_conditions or cond.snow):
        parts = []
        if cond.type_of_hike:
            parts.append(cond.type_of_hike)
        if cond.trail_conditions:
            parts.append(cond.trail_conditions)
        if cond.road:
            parts.append(cond.road)
        if cond.snow:
            parts.append(cond.snow)
        description = ". ".join(parts) if parts else ""

    # Photos - trip report images
    photos: list[str] = []
    for img in soup.find_all("img", src=True):
        src = img.get("src", "")
        if "site_images/trip-reports" in src or "tripreport-image" in src:
            full = urljoin(WTA_BASE, src)
            if full not in photos:
                photos.append(full)

    return TripReport(
        description=description,
        date=date_str,
        condition=cond,
        photos=photos[:10],
    )


def _fetch_trip_report_urls(slug: str, session: requests.Session, max_reports: int = 10) -> list[str]:
    """Fetch trip report URLs for a trail from @@related_tripreport_listing."""
    url = f"{WTA_BASE}/go-hiking/hikes/{slug}/@@related_tripreport_listing"
    params = {"b_size": max_reports}
    try:
        r = session.get(url, params=params, timeout=15)
        r.raise_for_status()
    except Exception:
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    urls: list[str] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        if "go-hiking/trip-reports/trip_report-" in href:
            full = urljoin(WTA_BASE, href)
            if full not in seen:
                seen.add(full)
                urls.append(full)
    return urls[:max_reports]


def fetch_trail_slugs_from_list(session: requests.Session | None = None, page_limit: int = 10) -> list[str]:
    """Fetch trail slugs from the hikes list page(s) with pagination.

    Args:
        session: Optional requests session.
        page_limit: Max number of pages to scrape (30 trails per page).

    Returns:
        List of unique trail slugs.
    """
    sess = session or _session()
    slugs: set[str] = set()

    for page in range(page_limit):
        url = HIKES_LIST_URL if page == 0 else f"{HIKES_LIST_URL}?b_start:int={page * 30}"
        try:
            r = sess.get(url, timeout=15)
            r.raise_for_status()
        except Exception:
            break

        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            m = TRAIL_LINK_PATTERN.search(href)
            if m:
                slugs.add(m.group(1))

        if page > 0:
            time.sleep(REQUEST_DELAY)

    return list(slugs)


def scrape_trail_detail(
    slug: str, session: requests.Session | None = None, fetch_trip_reports: bool = True
) -> WTATrail | None:
    """Scrape a single trail's detail page. Extracts JSON-LD, HTML stats, features, and trip reports.

    Args:
        slug: Trail slug (e.g. rattlesnake-ledge).
        session: Optional requests session.
        fetch_trip_reports: If True, fetch up to MAX_TRIP_REPORTS trip reports.

    Returns:
        WTATrail or None if parsing fails.
    """
    sess = session or _session()
    url = f"{WTA_BASE}/go-hiking/hikes/{slug}"

    try:
        r = sess.get(url, timeout=15)
        r.raise_for_status()
    except Exception:
        return None

    soup = BeautifulSoup(r.text, "html.parser")
    text = soup.get_text()

    # JSON-LD
    ld_data: dict | None = None
    for sc in soup.find_all("script", type="application/ld+json"):
        if sc.string:
            try:
                d = json.loads(sc.string)
                if isinstance(d, dict) and d.get("@type") in ("LocalBusiness", "Place", "HikingTrail"):
                    ld_data = d
                    break
            except json.JSONDecodeError:
                continue

    name = slug.replace("-", " ").title()
    description = ""
    lat = lon = None
    rating = None

    if ld_data:
        name = ld_data.get("name", name)
        description = ld_data.get("description", "") or ""
        geo = ld_data.get("geo", {})
        if isinstance(geo, dict):
            lat = geo.get("latitude")
            lon = geo.get("longitude")
        ar = ld_data.get("aggregateRating", {})
        if isinstance(ar, dict):
            rating = ar.get("ratingValue")

    # Location
    location: Location | None = None
    if lat is not None and lon is not None:
        try:
            location = Location(latitude=float(lat), longitude=float(lon))
        except (TypeError, ValueError):
            pass

    # Parse length and elevation from HTML
    length_mi = None
    elevation_gain_ft = None

    mi_match = re.search(r"([\d.]+)\s*mi(?:les)?\b", text, re.I)
    if mi_match:
        try:
            length_mi = float(mi_match.group(1))
        except ValueError:
            pass

    elev_match = re.search(r"(?:elevation\s+gain|gain)\s*[:\s]*([\d,]+)\s*(?:ft|feet)", text, re.I)
    if not elev_match:
        elev_match = re.search(r"([\d,]+)\s*(?:ft|feet)\s*(?:gain|elevation)", text, re.I)
    if elev_match:
        try:
            elevation_gain_ft = float(elev_match.group(1).replace(",", ""))
        except ValueError:
            pass

    # Highest Point (e.g. "Highest Point5,065 feet")
    high_match = re.search(r"Highest\s+Point\s*([\d,]+)\s*(?:ft|feet)", text, re.I)
    highest_point_ft: float | None = None
    if high_match:
        try:
            highest_point_ft = float(high_match.group(1).replace(",", ""))
        except ValueError:
            pass

    # Calculated Difficulty (e.g. "Moderate/Hard", "Easy", "Hard")
    diff_match = re.search(
        r"Calculated\s+Difficulty[\s\S]*?((?:Easy|Moderate|Hard)(?:\/(?:Easy|Moderate|Hard))?)\b",
        text,
        re.I,
    )
    calculated_difficulty: str | None = diff_match.group(1).strip() if diff_match else None

    # Features from wta-icon-list
    features: list[str] = []
    ul = soup.find("ul", class_="wta-icon-list")
    if ul:
        features = [li.get_text(strip=True) for li in ul.find_all("li") if li.get_text(strip=True)]

    # Parking Pass/Entry Fee - from h4 label
    parking_pass_entry_fee: str | None = None
    permits_required: str | None = None
    for h4 in soup.find_all("h4"):
        label = h4.get_text(strip=True)
        if "Parking Pass" in label or "Entry Fee" in label:
            parent = h4.parent
            full = parent.get_text(separator=" ", strip=True) if parent else ""
            val = full.replace(label, "", 1).strip() if label else full
            parking_pass_entry_fee = val or "None"
        elif "Permits Required" in label:
            parent = h4.parent
            full = parent.get_text(separator=" ", strip=True) if parent else ""
            val = full.replace(label, "", 1).strip() if label else full
            if val and "add hike" not in val.lower():
                permits_required = val[:200]

    # Getting There - h2 "Getting There" followed by directions
    getting_there: str | None = None
    for h2 in soup.find_all("h2"):
        if "Getting There" in h2.get_text():
            block = h2.find_parent(["div", "section"])
            if block:
                txt = block.get_text(separator=" ", strip=True)
                idx = txt.find("From ")
                if idx >= 0:
                    end = txt.find("Add Hike", idx)
                    if end < 0:
                        end = txt.find("WTA Pro Tip", idx)
                    if end < 0:
                        end = len(txt)
                    getting_there = txt[idx:end].strip()[:800]
            break

    # Alerts - wta-note--red or wta-note with alert icon (closures, warnings, unsanctioned, etc.)
    alerts: list[str] = []
    for note in soup.find_all(class_=re.compile(r"wta-note", re.I)):
        if "wta-note--red" not in str(note.get("class", [])):
            if not note.find("img", src=re.compile(r"alert", re.I)):
                continue
        txt = note.get_text(strip=True)
        if "trip reports for this trail" in txt.lower():
            continue
        if len(txt) > 30:
            if txt not in alerts:
                alerts.append(txt[:500])

    # Trip reports
    trip_reports: list[TripReport] = []
    if fetch_trip_reports:
        report_urls = _fetch_trip_report_urls(slug, sess, max_reports=MAX_TRIP_REPORTS)
        for report_url in report_urls:
            report = _parse_trip_report_page(report_url, sess)
            if report:
                trip_reports.append(report)
            time.sleep(REQUEST_DELAY * 0.5)

    return WTATrail(
        name=name,
        slug=slug,
        url=url,
        description=description[:1000] if description else "",
        location=location,
        length_mi=length_mi,
        elevation_gain_ft=elevation_gain_ft,
        highest_point_ft=highest_point_ft,
        calculated_difficulty=calculated_difficulty,
        permits_required=permits_required,
        rating=float(rating) if rating is not None else None,
        features=features,
        parking_pass_entry_fee=parking_pass_entry_fee,
        getting_there=getting_there,
        alerts=alerts,
        trip_reports=trip_reports,
    )


def fetch_fresh_trail_info(
    slug: str,
    session: requests.Session | None = None,
    fetch_conditions: bool = True,
) -> dict:
    """Fetch fresh alerts and conditions for a trail (RAG pattern).

    Returns dict with: alerts (list[str]), trip_reports (list[dict]).
    """
    sess = session or _session()
    url = f"{WTA_BASE}/go-hiking/hikes/{slug}"
    out: dict = {"alerts": [], "trip_reports": []}
    try:
        r = sess.get(url, timeout=10)
        r.raise_for_status()
    except Exception:
        return out

    soup = BeautifulSoup(r.text, "html.parser")

    # Alerts - wta-note--red or wta-note with alert icon
    for note in soup.find_all(class_=re.compile(r"wta-note", re.I)):
        if "wta-note--red" not in str(note.get("class", [])):
            if not note.find("img", src=re.compile(r"alert", re.I)):
                continue
        txt = note.get_text(strip=True)
        if "trip reports for this trail" in txt.lower():
            continue
        if len(txt) > 30:
            if txt not in out["alerts"]:
                out["alerts"].append(txt[:500])

    # Conditions from latest trip reports
    if fetch_conditions:
        report_urls = _fetch_trip_report_urls(slug, sess, max_reports=2)
        for report_url in report_urls:
            report = _parse_trip_report_page(report_url, sess)
            if report:
                out["trip_reports"].append(report.model_dump())
            time.sleep(REQUEST_DELAY * 0.5)

    return out


def scrape_wta_trails(
    page_limit: int = 5,
    center_lat: float | None = None,
    center_lon: float | None = None,
    radius_miles: float = 50,
    fetch_trip_reports: bool = True,
    on_trail: Callable[[WTATrail], None] | None = None,
) -> list[WTATrail]:
    """Scrape WTA trails. Optionally filter by distance from center.

    Args:
        page_limit: Max list pages to scrape.
        center_lat: If set, only return trails within radius_miles.
        center_lon: If set, only return trails within radius_miles.
        radius_miles: Max distance in miles from center.
        fetch_trip_reports: If True, fetch trip reports for each trail.
        on_trail: If provided, called with each trail as it's scraped (for incremental load).

    Returns:
        List of WTATrail within constraints.
    """
    sess = _session()
    slugs = fetch_trail_slugs_from_list(sess, page_limit=page_limit)

    trails: list[WTATrail] = []
    for i, slug in enumerate(slugs):
        trail = scrape_trail_detail(slug, session=sess, fetch_trip_reports=fetch_trip_reports)
        if trail and trail.slug:
            if (
                center_lat is not None
                and center_lon is not None
                and trail.location
            ):
                dist = _haversine_miles(
                    center_lat, center_lon,
                    trail.location.latitude,
                    trail.location.longitude,
                )
                if dist > radius_miles:
                    continue
            if on_trail:
                on_trail(trail)
            trails.append(trail)
        if (i + 1) % 5 == 0:
            time.sleep(REQUEST_DELAY)

    return trails
