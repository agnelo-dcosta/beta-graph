"""Scrape individual trail pages for coordinates and user reviews.

Coordinates: meta tags place:location:latitude/longitude first, then geocoding.
Reviews: top 20, text + rating + date + photos when present, no author info.
Trail stats: trailGeoStats (length, elevation, duration) embedded in HTML; location from
  embedded JSON or JSON-LD addressLocality.

Note: AllTrails API (/api/) is disallowed by robots.txt - we only parse page HTML.
"""

import json
import re
import time
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from requests import Session

from beta_graph.shared.config import USE_PLAYWRIGHT
from beta_graph.servers.alltrails.cookies import create_session_with_cookies
from beta_graph.servers.alltrails.models import Location, Tag, Trail, TrailGeoStats, TrailReview

# Conversion constants
METERS_TO_MILES = 1 / 1609.344
METERS_TO_FEET = 3.28084


def _extract_trail_id(html: str) -> int | None:
    """Extract numeric trailId from embedded JSON in HTML (e.g. trailId\":10014686)."""
    # Escaped in HTML: trailId\\":10014686
    m = re.search(r'trailId\\":\s*(\d+)', html)
    if m:
        try:
            return int(m.group(1))
        except (TypeError, ValueError):
            return None
    return None


def _extract_json_obj(html: str, key: str) -> dict | None:
    """Extract a JSON object by key from embedded JSON in HTML.

    Finds key (e.g. 'trailGeoStats') and parses the following {...} object.
    Handles escaped quotes in the HTML.

    Args:
        html: Raw HTML string.
        key: JSON key to find (without quotes).

    Returns:
        Parsed dict or None if not found.
    """
    idx = html.find(key)
    if idx == -1:
        return None
    brace_start = html.find("{", idx)
    if brace_start == -1:
        return None
    depth = 1
    i = brace_start + 1
    while i < len(html) and depth > 0:
        c = html[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        i += 1
    if depth != 0:
        return None
    raw = html[brace_start:i]
    # Unescape JSON embedded in HTML (e.g. \\ -> \, \" -> ")
    unescaped = raw.replace("\\\\", "\\").replace('\\"', '"')
    try:
        return json.loads(unescaped)
    except json.JSONDecodeError:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None


def _extract_trail_geo_stats(html: str) -> tuple[dict, TrailGeoStats | None]:
    """Extract trailGeoStats from HTML and convert to human-readable units.

    Returns tuple of (legacy dict for length_mi, elevation_gain_ft, est_time strings)
    and TrailGeoStats object with floats in miles/feet and duration string.
    """
    out: dict = {"length_mi": None, "elevation_gain_ft": None, "est_time": None}
    geo = _extract_json_obj(html, "trailGeoStats")
    if not geo:
        return out, None

    def _float(v):
        if v is None:
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    length_m = geo.get("length")
    miles = None
    if length_m is not None:
        m_val = _float(length_m)
        if m_val is not None:
            miles = m_val * METERS_TO_MILES
            out["length_mi"] = f"{miles:.1f} mi"

    elev_gain_m = geo.get("elevationGain")
    elev_gain_ft = None
    if elev_gain_m is not None:
        m_val = _float(elev_gain_m)
        if m_val is not None:
            elev_gain_ft = int(round(m_val * METERS_TO_FEET))
            out["elevation_gain_ft"] = f"{elev_gain_ft} ft"

    elev_max_m = geo.get("elevationMax")
    elev_max_ft = None
    if elev_max_m is not None:
        m_val = _float(elev_max_m)
        if m_val is not None:
            elev_max_ft = int(round(m_val * METERS_TO_FEET))

    duration_formatted = None
    if geo.get("durationFormatted"):
        duration_formatted = str(geo["durationFormatted"])
        out["est_time"] = duration_formatted
    else:
        dm = geo.get("durationMinutes")
        if dm is not None:
            try:
                mins = int(float(dm))
                h, m = divmod(mins, 60)
                duration_formatted = f"{h} h {m} min" if m else f"{h} h"
                out["est_time"] = duration_formatted
            except (TypeError, ValueError):
                pass
        if not duration_formatted:
            # Fallback: averageTimeToComplete e.g. {"value":"3–3.5","unit":"hr"}
            atc = geo.get("averageTimeToComplete")
            if isinstance(atc, dict) and atc.get("value"):
                val = str(atc["value"]).strip()
                unit = (atc.get("unit") or "hr").strip()
                if val:
                    duration_formatted = f"{val} {unit}" if unit else val
                    out["est_time"] = duration_formatted

    # Fallback: estimate duration from length + elevation (Naismith's rule: 3 mi/h + 2000 ft/h)
    if not duration_formatted and (miles is not None or elev_gain_ft is not None):
        time_h = 0.0
        if miles is not None:
            time_h += miles / 3.0
        if elev_gain_ft is not None:
            time_h += elev_gain_ft / 2000.0
        if time_h > 0:
            h, m = divmod(int(round(time_h * 60)), 60)
            duration_formatted = f"{h} h {m} min" if m else f"{h} h"
            out["est_time"] = duration_formatted

    trail_geo = TrailGeoStats(
        length_mi=round(miles, 2) if miles is not None else None,
        elevation_gain_ft=elev_gain_ft,
        elevation_max_ft=elev_max_ft,
        duration_formatted=duration_formatted,
    )
    return out, trail_geo


def _extract_tags(html: str) -> list[Tag]:
    """Extract tags from embedded JSON (e.g. Forests, Lakes, Views).

    Tags appear in structure like: "tags":[{"name":"Forests","uid":"forest",...}]
    """
    tags: list[Tag] = []
    for needle in ('"tags":', 'tags":', '"tags"'):
        idx = html.find(needle)
        if idx == -1:
            continue
        bracket = html.find("[", idx)
        if bracket == -1:
            continue
        depth = 1
        i = bracket + 1
        while i < len(html) and depth > 0:
            c = html[i]
            if c == "[":
                depth += 1
            elif c == "]":
                depth -= 1
            i += 1
        if depth != 0:
            continue
        raw = html[bracket:i]
        unescaped = raw.replace("\\\\", "\\").replace('\\"', '"')
        try:
            arr = json.loads(unescaped)
        except json.JSONDecodeError:
            continue
        if not isinstance(arr, list):
            continue
        for item in arr:
            if isinstance(item, dict):
                tags.append(Tag(
                    name=item.get("name") or "",
                    uid=item.get("uid") or "",
                    description=item.get("description") or "",
                ))
        break
    return tags


def _extract_location_from_html(html: str, soup: BeautifulSoup) -> Location | None:
    """Extract Location object from embedded JSON or JSON-LD.

    Prefers full location object (city, region, coords) if present; else builds from Review.
    """
    # Match \"location\": (escaped JSON key) or ","location": (sibling in object)
    loc = _extract_json_obj(html, '"location":')
    if not loc:
        loc = _extract_json_obj(html, 'location":')
    if loc:
        def _float(v):
            if v is None:
                return None
            try:
                return float(v)
            except (TypeError, ValueError):
                return None

        try:
            return Location(
                postalCode=loc.get("postalCode"),
                city_id=loc.get("city_id"),
                city=loc.get("city"),
                region=loc.get("region"),
                regionName=loc.get("regionName") or loc.get("region"),
                country=loc.get("country"),
                country_name=loc.get("country_name") or loc.get("countryName"),
                latitude=_float(loc.get("latitude")),
                longitude=_float(loc.get("longitude")),
            )
        except (TypeError, ValueError, KeyError):
            city = loc.get("city")
            region_name = loc.get("regionName") or loc.get("region")
            if city or region_name:
                return Location(
                    city=city,
                    region=region_name,
                    regionName=region_name,
                )
    for script in soup.find_all("script", type="application/ld+json"):
        if not script.string or '"@type":"Review"' not in script.string:
            continue
        try:
            data = json.loads(script.string)
            addr = data.get("itemReviewed", {}).get("address", {})
            locality = addr.get("addressLocality")
            if locality:
                # "City, State" or "City, State, United States"
                parts = [p.strip() for p in locality.split(",")]
                if parts and parts[-1] == "United States":
                    parts = parts[:-1]
                city = parts[0] if parts else None
                region_name = parts[1] if len(parts) > 1 else None
                return Location(
                    city=city,
                    regionName=region_name,
                    country="US",
                    country_name="United States",
                )
        except json.JSONDecodeError:
            continue
    return None


def _extract_coords_from_meta(soup: BeautifulSoup) -> tuple[float | None, float | None]:
    """Extract lat/lng from meta tags place:location:latitude and place:location:longitude.

    Args:
        soup: Parsed HTML of the trail detail page.

    Returns:
        Tuple of (latitude, longitude) or (None, None) if not found.
    """
    lat_tag = soup.find("meta", attrs={"name": "place:location:latitude"})
    lng_tag = soup.find("meta", attrs={"name": "place:location:longitude"})
    if lat_tag and lng_tag and lat_tag.get("content") and lng_tag.get("content"):
        try:
            lat = float(lat_tag["content"])
            lng = float(lng_tag["content"])
            if -90 <= lat <= 90 and -180 <= lng <= 180:
                return lat, lng
        except (TypeError, ValueError):
            pass
    return None, None


def _location_to_str(loc: Location | None) -> str:
    """Build geocoding string from Location."""
    if not loc:
        return ""
    parts = [p for p in (loc.city, loc.regionName or loc.region, loc.country_name) if p]
    return ", ".join(parts)


def _geocode_trail(trail_name: str, location: str | Location | None) -> tuple[float | None, float | None]:
    """Get coordinates via OpenStreetMap Nominatim.

    Free, no API key. Rate limited to ~1 req/sec.

    Args:
        trail_name: Trail name for geocoding query.
        location: Location string or Location object (e.g. 'North Bend, Washington').

    Returns:
        Tuple of (latitude, longitude) or (None, None) if not found.
    """
    loc_str = _location_to_str(location) if isinstance(location, Location) else (location or "")
    if not trail_name or not loc_str:
        return None, None
    try:
        from geopy.geocoders import Nominatim
        from geopy.extra.rate_limiter import RateLimiter

        geolocator = Nominatim(user_agent="beta-graph-trail-planner")
        geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1.1)
        query = f"{trail_name}, {loc_str}"
        result = geocode(query)
        if result:
            return result.latitude, result.longitude
        result = geocode(loc_str)
        if result:
            return result.latitude, result.longitude
    except Exception:
        pass
    return None, None


def _extract_reviews(soup: BeautifulSoup, base_url: str = "https://www.alltrails.com") -> list[TrailReview]:
    """Extract top 20 reviews from JSON-LD and nearby HTML.

    Includes text, rating, date, and photo URLs when present. No author info.

    Args:
        soup: Parsed HTML of the trail detail page.
        base_url: Base URL for resolving relative image URLs.

    Returns:
        List of TrailReview instances (max 20).
    """
    reviews: list[TrailReview] = []
    seen: set[str] = set()

    # Find review containers (ReviewItem_reviewContainer or parent of JSON-LD Review)
    for script in soup.find_all("script", type="application/ld+json"):
        if not script.string or '"@type":"Review"' not in script.string and '"@type": "Review"' not in script.string:
            continue
        try:
            data = json.loads(script.string)
            if data.get("@type") != "Review":
                continue
            body = data.get("reviewBody") or ""
            if not body or len(body) < 10:
                continue
            body = body.strip()[:500]
            if body in seen:
                continue
            seen.add(body)

            rating_val = None
            r = data.get("reviewRating")
            if isinstance(r, dict) and "ratingValue" in r:
                rating_val = str(r["ratingValue"])
            elif isinstance(r, (int, float)):
                rating_val = str(r)

            # Find photos in same parent container
            photo_urls: list[str] = []
            parent = script.find_parent(["div", "article"])
            if parent:
                photos_cont = parent.find(attrs={"data-testid": "trail-review-photos"})
                if photos_cont:
                    for img in photos_cont.find_all("img", src=True):
                        src = img.get("src", "")
                        if src and ("alltrails" in src or "images." in src):
                            if src.startswith("//"):
                                src = "https:" + src
                            elif src.startswith("/"):
                                src = urljoin(base_url, src)
                            if src not in photo_urls:
                                photo_urls.append(src)

            # Date from nearby HTML if not in JSON-LD
            date_val = None
            if parent:
                date_elem = parent.find(string=re.compile(r"\d{4}|\d{1,2}/\d{1,2}|yesterday|today", re.I))
                if date_elem and hasattr(date_elem, "strip"):
                    date_val = date_elem.strip() if date_elem else None

            reviews.append(TrailReview(text=body, date=date_val, rating=rating_val, photo_urls=photo_urls))
            if len(reviews) >= 20:
                break
        except json.JSONDecodeError:
            continue
    return reviews


def fetch_trail_detail(trail_url: str, trail: Trail | None = None, session: Session | None = None) -> dict:
    """Fetch trail detail page using HTTP requests.

    May fail if AllTrails serves bot block. Extracts coordinates (meta or geocode),
    reviews, trailGeoStats (length, elevation, duration), and location.

    Args:
        trail_url: Full URL of the trail detail page.
        trail: Optional Trail instance for geocoding fallback.
        session: Optional requests Session.

    Returns:
        Dict with keys: latitude, longitude, directions_url, reviews, length_mi,
        elevation_gain_ft, est_time, location.
    """
    result: dict = {
        "latitude": None,
        "longitude": None,
        "directions_url": None,
        "reviews": [],
        "length_mi": None,
        "elevation_gain_ft": None,
        "est_time": None,
        "location": None,
        "trailGeoStats": None,
        "tags": [],
        "trailId": None,
    }

    sess = session or create_session_with_cookies()

    try:
        resp = sess.get(trail_url, timeout=15)
        resp.raise_for_status()
    except Exception:
        return result

    html = resp.text
    soup = BeautifulSoup(html, "html.parser")

    lat, lng = _extract_coords_from_meta(soup)
    if lat is None and trail:
        lat, lng = _geocode_trail(trail.name, trail.location)

    result["latitude"] = lat
    result["longitude"] = lng
    result["reviews"] = _extract_reviews(soup)
    result["location"] = _extract_location_from_html(html, soup)
    result["tags"] = _extract_tags(html)

    geo_dict, trail_geo = _extract_trail_geo_stats(html)
    result["length_mi"] = geo_dict["length_mi"]
    result["elevation_gain_ft"] = geo_dict["elevation_gain_ft"]
    result["est_time"] = geo_dict["est_time"]
    result["trailGeoStats"] = trail_geo
    result["trailId"] = _extract_trail_id(html)

    if result["latitude"] and result["longitude"]:
        result["directions_url"] = f"https://www.google.com/maps?q={result['latitude']},{result['longitude']}"
    return result


def fetch_trail_detail_playwright(trail_url: str, trail: Trail | None = None) -> dict:
    """Fetch trail detail using Playwright (real browser). Bypasses bot detection.

    Args:
        trail_url: Full URL of the trail detail page.
        trail: Optional Trail instance for geocoding fallback.

    Returns:
        Dict with keys: latitude, longitude, directions_url, reviews, length_mi,
        elevation_gain_ft, est_time, location.
    """
    from playwright.sync_api import sync_playwright

    result: dict = {
        "latitude": None,
        "longitude": None,
        "directions_url": None,
        "reviews": [],
        "length_mi": None,
        "elevation_gain_ft": None,
        "est_time": None,
        "location": None,
        "trailGeoStats": None,
        "tags": [],
        "trailId": None,
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"})
        try:
            page.goto(trail_url, wait_until="networkidle", timeout=20000)
            time.sleep(2)
            html = page.content()
        finally:
            browser.close()

    soup = BeautifulSoup(html, "html.parser")
    lat, lng = _extract_coords_from_meta(soup)
    if lat is None and trail:
        lat, lng = _geocode_trail(trail.name, trail.location)

    result["latitude"] = lat
    result["longitude"] = lng
    result["reviews"] = _extract_reviews(soup)
    result["location"] = _extract_location_from_html(html, soup)
    result["tags"] = _extract_tags(html)

    geo_dict, trail_geo = _extract_trail_geo_stats(html)
    result["length_mi"] = geo_dict["length_mi"]
    result["elevation_gain_ft"] = geo_dict["elevation_gain_ft"]
    result["est_time"] = geo_dict["est_time"]
    result["trailGeoStats"] = trail_geo
    result["trailId"] = _extract_trail_id(html)

    if result["latitude"] and result["longitude"]:
        result["directions_url"] = f"https://www.google.com/maps?q={result['latitude']},{result['longitude']}"
    return result


def enrich_trail_with_detail(trail: Trail, session: Session | None = None) -> Trail:
    """Fetch trail detail page and add coordinates, directions_url, reviews, and stats.

    Uses Playwright or requests based on USE_PLAYWRIGHT config.

    Args:
        trail: Trail instance to enrich (must have url and location set).
        session: Optional requests Session (reuses cookies; use when enriching multiple trails).

    Returns:
        The same Trail instance with latitude, longitude, directions_url, reviews,
        trailGeoStats (length, elevation, duration), tags, location populated.
    """
    if USE_PLAYWRIGHT:
        detail = fetch_trail_detail_playwright(trail.url, trail=trail)
    else:
        detail = fetch_trail_detail(trail.url, trail=trail, session=session)

    trail.reviews = detail["reviews"]
    if detail.get("trailGeoStats"):
        trail.trailGeoStats = detail["trailGeoStats"]
        # Preserve duration from region page if detail didn't have it
        if trail.trailGeoStats.duration_formatted is None and trail.est_time:
            trail.trailGeoStats.duration_formatted = trail.est_time
    if detail.get("tags"):
        trail.tags = detail["tags"]
    loc = detail.get("location")
    if loc:
        trail.location = loc
    # Set or update location coords and directions
    if trail.location is None:
        trail.location = Location()
    lat, lng = detail.get("latitude"), detail.get("longitude")
    if lat is not None or lng is not None:
        trail.location.latitude = lat or trail.location.latitude
        trail.location.longitude = lng or trail.location.longitude
    if detail.get("directions_url"):
        trail.location.directions_url = detail["directions_url"]
    if detail.get("trailId") is not None:
        trail.trailId = detail["trailId"]
    return trail
