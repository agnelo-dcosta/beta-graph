"""Google Maps Geocoding API client."""

import os
from pathlib import Path

import requests

DEFAULT_API_KEY_FILE = "keys/google_maps_api_key"
GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"

# Washington state bounding box for viewport biasing (sw.lat,sw.lng|ne.lat,ne.lng)
_WA_BOUNDS = "45.54,-124.85|49.0,-116.92"


def _query_implies_washington(q: str) -> bool:
    """True if query suggests Washington state (e.g. 'Artist Point, WA')."""
    lower = q.lower().strip()
    return ", wa" in lower or ", washington" in lower or lower.endswith(" wa") or " washington" in lower


def _get_api_key() -> str | None:
    key = os.getenv("GOOGLE_MAPS_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if key:
        return key.strip()
    path = Path(os.getenv("GOOGLE_MAPS_API_KEY_FILE", DEFAULT_API_KEY_FILE))
    if path.is_file():
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    return line
        except OSError:
            return None
    return None


def geocode_forward(
    query: str,
    limit: int = 5,
    country: str | None = "US",
    proximity: tuple[float, float] | None = None,
    bbox: tuple[float, float, float, float] | None = None,
) -> list[dict]:
    """Forward geocode: place name -> coordinates (Google Maps API).

    Args:
        query: Search text (e.g. "Kirkland", "Seattle, WA").
        limit: Max results. Default 5.
        country: ISO country code to bias results. Default US.
        proximity: Optional (lon, lat) - used as region hint if query implies WA.
        bbox: Optional (minLon, minLat, maxLon, maxLat) for viewport biasing.
            When query implies Washington, WA bounds are used by default.

    Returns:
        List of dicts with place_name, latitude, longitude, coordinates [lon, lat].
    """
    key = _get_api_key()
    if not key:
        raise ValueError(
            "Google Maps API key not found. Set GOOGLE_MAPS_API_KEY env var or add key to keys/google_maps_api_key."
        )

    params: dict = {
        "address": query,
        "key": key,
    }
    if _query_implies_washington(query):
        params["bounds"] = _WA_BOUNDS
        params["region"] = "us"
    elif bbox is not None:
        # bbox: minLon, minLat, maxLon, maxLat -> sw.lat,sw.lng|ne.lat,ne.lng
        params["bounds"] = f"{bbox[1]},{bbox[0]}|{bbox[3]},{bbox[2]}"
    if country:
        params["components"] = f"country:{country.upper()}"

    r = requests.get(GEOCODE_URL, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()

    status = data.get("status")
    if status == "ZERO_RESULTS":
        return []
    if status != "OK":
        raise RuntimeError(
            f"Google Geocoding API error: {status} - {data.get('error_message', '')}"
        )

    results = data.get("results", [])
    out = []
    for r in results[:limit]:
        geom = r.get("geometry", {})
        loc = geom.get("location", {})
        lat = loc.get("lat")
        lon = loc.get("lng")
        place = r.get("formatted_address", "")
        coords = [lon, lat] if lon is not None and lat is not None else []
        out.append({
            "place_name": place,
            "latitude": lat,
            "longitude": lon,
            "coordinates": coords,
        })
    return out
