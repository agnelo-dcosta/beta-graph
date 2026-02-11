"""LangChain tools wrapping trail search and weather."""

import json
from typing import Annotated

from langchain_core.tools import tool

from beta_graph.servers.alltrails.chroma_store import TrailVectorStore
from beta_graph.servers.weather.forecast import fetch_forecast

_store: TrailVectorStore | None = None


def _get_store() -> TrailVectorStore:
    global _store
    if _store is None:
        _store = TrailVectorStore()
    return _store


def _parse_json_field(obj: dict, key: str) -> dict:
    """Parse a JSON string field in metadata."""
    val = obj.get(key)
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val) or {}
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def _extract_lat_lon(trail_meta: dict) -> tuple[float | None, float | None]:
    """Extract latitude/longitude from trail metadata (location may be JSON string)."""
    loc = _parse_json_field(trail_meta, "location")
    return loc.get("latitude"), loc.get("longitude")


def _format_trail(trail_meta: dict) -> str:
    """Format a trail for display."""
    loc = _parse_json_field(trail_meta, "location")
    geo = _parse_json_field(trail_meta, "trailGeoStats")
    name = trail_meta.get("name", "?")
    difficulty = trail_meta.get("difficulty", "?")
    length_mi = geo.get("length_mi")
    city = loc.get("city", "")
    region = loc.get("regionName", "")
    lat, lon = loc.get("latitude"), loc.get("longitude")
    coords = f" (lat={lat}, lon={lon})" if lat is not None and lon is not None else ""
    loc_str = f"{city}, {region}".strip(", ") if (city or region) else "?"
    return f"{name} | {difficulty} | {length_mi or '?'} mi | {loc_str}{coords}"


@tool
def search_trails(
    query: Annotated[str, "Natural language trail query, e.g. 'moderate hike', 'waterfall', 'family friendly'"],
    n_results: Annotated[int, "Max trails to return"] = 5,
) -> str:
    """Search for hiking trails by semantic query. Returns trails with name, difficulty, length, location, and coordinates if available."""
    store = _get_store()
    trails = store.search(query=query, n_results=n_results)
    if not trails:
        return "No trails found."
    return "\n".join(f"{i}. {_format_trail(t)}" for i, t in enumerate(trails, 1))


@tool
def get_weather_forecast(
    latitude: Annotated[float, "Latitude (-90 to 90)"],
    longitude: Annotated[float, "Longitude (-180 to 180)"],
    days: Annotated[int, "Days of forecast (1-5)"] = 3,
    units: Annotated[str, "imperial (F), metric (C), or standard"] = "imperial",
) -> str:
    """Get weather forecast for a location. Returns daily temp range, conditions, and rain chance."""
    result = fetch_forecast(latitude=latitude, longitude=longitude, days=days, units=units)
    if "error" in result:
        return f"Weather error: {result['error']}"
    loc = result.get("location", "Unknown")
    forecast = result.get("forecast", [])
    lines = [f"Weather for {loc} ({units}):"]
    for d in forecast:
        conds = ", ".join(d.get("conditions", [])) or "—"
        pop = d.get("pop_max")
        pop_str = f" | Rain {pop}%" if pop is not None else ""
        lines.append(
            f"  {d['date']}: {d.get('temp_min')}–{d.get('temp_max')}° {conds}{pop_str}"
        )
    return "\n".join(lines)


@tool
def get_trail_count() -> str:
    """Get the number of trails stored in the database."""
    store = _get_store()
    return str(store.count())
