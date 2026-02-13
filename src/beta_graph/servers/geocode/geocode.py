"""Google Places API client for location lookup (replaces Geocoding API).

Uses Places Text Search to resolve place names to coordinates.
Returns same interface as former Geocoding API for compatibility.
"""

import os
from pathlib import Path

import requests

DEFAULT_API_KEY_FILE = "keys/google_maps_api_key"
PLACES_TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"

# Washington state center for location biasing (lat, lng)
_WA_CENTER = "47.4,-120.5"
_WA_RADIUS_M = 500000  # ~310 miles, covers state


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
    """Resolve place name to coordinates (Google Places API Text Search).

    Args:
        query: Search text (e.g. "Artist Point", "Seattle, WA").
        limit: Max results. Default 5.
        country: Ignored (Places uses region). Kept for API compatibility.
        proximity: Optional (lon, lat) - used as location bias if query implies WA.
        bbox: Optional (minLon, minLat, maxLon, maxLat). Used as location bias.

    Returns:
        List of dicts with place_name, latitude, longitude, coordinates [lon, lat].
    """
    key = _get_api_key()
    if not key:
        raise ValueError(
            "Google Maps API key not found. Set GOOGLE_MAPS_API_KEY env var or add key to keys/google_maps_api_key."
        )

    params: dict = {
        "query": query,
        "key": key,
        "region": "us",
    }

    # Location bias for Washington queries
    if _query_implies_washington(query):
        params["location"] = _WA_CENTER
        params["radius"] = _WA_RADIUS_M
    elif proximity is not None:
        params["location"] = f"{proximity[1]},{proximity[0]}"
        params["radius"] = 100000
    elif bbox is not None:
        # bbox: minLon, minLat, maxLon, maxLat -> center
        cx = (bbox[0] + bbox[2]) / 2
        cy = (bbox[1] + bbox[3]) / 2
        params["location"] = f"{cy},{cx}"
        params["radius"] = 150000

    r = requests.get(PLACES_TEXT_SEARCH_URL, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()

    status = data.get("status")
    if status == "ZERO_RESULTS":
        return []
    if status == "REQUEST_DENIED":
        raise RuntimeError(
            f"Google Places API error: {status} - {data.get('error_message', '')}. "
            "Ensure Places API is enabled and API key has Places API permission."
        )
    if status != "OK":
        raise RuntimeError(
            f"Google Places API error: {status} - {data.get('error_message', '')}"
        )

    results = data.get("results", [])
    out = []
    for r in results[:limit]:
        geom = r.get("geometry", {})
        loc = geom.get("location", {})
        lat = loc.get("lat")
        lon = loc.get("lng")
        place = r.get("formatted_address") or r.get("name", "")
        coords = [lon, lat] if lon is not None and lat is not None else []
        out.append({
            "place_name": place,
            "latitude": lat,
            "longitude": lon,
            "coordinates": coords,
        })
    return out
