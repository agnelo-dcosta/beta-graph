"""GraphHopper Route API – trail distance, elevation, and turn-by-turn instructions."""

import logging
import os
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

GRAPHHOPPER_ROUTE_URL = "https://graphhopper.com/api/1/route"
GRAPHHOPPER_MATRIX_URL = "https://graphhopper.com/api/1/matrix"
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


def get_matrix_distances(
    from_points: list[tuple[float, float]],
    to_point: tuple[float, float],
    profile: str = "foot",
) -> list[float | None] | None:
    """Get route distances from multiple origins to one destination (Matrix API).

    Returns list of distances in meters, same order as from_points. None for failed/unreachable.
    Returns None if API call fails.
    """
    key = _get_api_key()
    if not key:
        logger.warning("GraphHopper API key not configured")
        return None
    if not from_points:
        return []

    from_strs = [f"{lat},{lon}" for lat, lon in from_points]
    to_str = f"{to_point[0]},{to_point[1]}"

    params = {
        "profile": profile,
        "key": key,
        "out_array": "distances",
        "fail_fast": "false",
    }

    try:
        r = requests.get(
            GRAPHHOPPER_MATRIX_URL,
            params={**params, "from_point": from_strs, "to_point": [to_str]},
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        logger.warning("GraphHopper matrix request failed: %s", e)
        return None

    dist_matrix = data.get("distances")
    if not dist_matrix or not isinstance(dist_matrix, list):
        return None
    # Matrix: [[from0->to0, from0->to1, ...], [from1->to0, ...], ...]
    # We have one to_point, so distances[i][0] = from i to destination
    return [row[0] if row and row[0] is not None else None for row in dist_matrix]


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
