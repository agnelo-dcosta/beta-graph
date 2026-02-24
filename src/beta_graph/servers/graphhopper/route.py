"""GraphHopper Route API – trail distance, elevation, and turn-by-turn instructions."""

import logging
import os
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

GRAPHHOPPER_ROUTE_URL = "https://graphhopper.com/api/1/route"
DEFAULT_API_KEY_FILE = "keys/graphhopper_api_key"


def _get_api_key() -> str | None:
    key = os.getenv("GRAPHHOPPER_API_KEY")
    if key:
        return key.strip()
    path = Path(os.getenv("GRAPHHOPPER_API_KEY_FILE", DEFAULT_API_KEY_FILE))
    if path.is_file():
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    return line
        except OSError:
            return None
    return None


def _naismith_hiking_minutes(distance_miles: float, elevation_gain_ft: float) -> int:
    """Estimate hiking time using Naismith's rule (accounts for steepness).

    Naismith: 3 mph on flat + 1 hour per 2000 ft ascent.
    Adds 25% buffer for breaks, rough terrain, and trail conditions.
    """
    time_hours = (distance_miles / 3.0) + (elevation_gain_ft / 2000.0)
    time_hours *= 1.25  # Buffer for breaks, terrain, conditions
    return int(round(time_hours * 60))


def get_route_to_point(
    trailhead_lat: float,
    trailhead_lon: float,
    target_lat: float,
    target_lon: float,
) -> dict | None:
    """Get route from trailhead to target point using GraphHopper foot profile.

    Returns dict with:
        distance_miles: Trail distance in miles
        elevation_gain_ft: Ascent in feet
        elevation_loss_ft: Descent in feet
        hiking_time_minutes: Estimated time (Naismith's rule)
        instructions: List of turn-by-turn instruction strings
        map_url: GraphHopper Maps URL for interactive route view
    """
    key = _get_api_key()
    if not key:
        logger.warning("GraphHopper API key not configured")
        return None

    params = {
        "profile": "foot",
        "locale": "en",
        "key": key,
        "elevation": "true",
        "instructions": "true",
        "points_encoded": "false",
    }
    # Multiple point params: point=lat1,lon1&point=lat2,lon2
    point_strs = [f"{trailhead_lat},{trailhead_lon}", f"{target_lat},{target_lon}"]

    try:
        r = requests.get(
            GRAPHHOPPER_ROUTE_URL,
            params={**params, "point": point_strs},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        logger.warning("GraphHopper route request failed: %s", e)
        return None

    paths = data.get("paths")
    if not paths:
        return None

    path = paths[0]
    distance_m = path.get("distance", 0)
    ascend_m = path.get("ascend", 0)
    descend_m = path.get("descend", 0)

    distance_miles = round(distance_m / 1609.344, 2)
    elevation_gain_ft = int(round(ascend_m * 3.28084))
    elevation_loss_ft = int(round(descend_m * 3.28084))
    hiking_time_minutes = _naismith_hiking_minutes(distance_miles, elevation_gain_ft)

    instructions = []
    for inst in path.get("instructions", []):
        text = inst.get("text", "").strip()
        if text and text != "Arrive at destination":
            instructions.append(text)

    # GraphHopper Maps URL – interactive map with route (no API key needed)
    map_url = (
        f"https://graphhopper.com/maps/?point={trailhead_lat},{trailhead_lon}_Trailhead"
        f"&point={target_lat},{target_lon}_Your+coordinates"
        "&profile=foot"
    )

    return {
        "distance_miles": distance_miles,
        "elevation_gain_ft": elevation_gain_ft,
        "elevation_loss_ft": elevation_loss_ft,
        "hiking_time_minutes": hiking_time_minutes,
        "instructions": instructions,
        "map_url": map_url,
    }
