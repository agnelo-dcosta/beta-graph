"""Shared climb handlers - used by climb server."""

import logging

from beta_graph.servers.climb.chroma_store import ClimbVectorStore
from beta_graph.servers.climb.scraper import scrape_area
from beta_graph.servers.geocode.geocode import geocode_forward

logger = logging.getLogger(__name__)

_store: ClimbVectorStore | None = None


def get_store() -> ClimbVectorStore:
    global _store
    if _store is None:
        _store = ClimbVectorStore()
    return _store


def search_climbs(
    query: str,
    n_results: int = 5,
    location: str | None = None,
    radius_miles: float | None = None,
) -> list[dict]:
    """Semantic search over Mountain Project climbs."""
    store = get_store()
    radius = radius_miles if radius_miles is not None else 25
    center_lat = center_lon = None

    if location:
        try:
            geo = geocode_forward(location, limit=1)
            if geo and geo[0].get("latitude") is not None:
                center_lat = geo[0]["latitude"]
                center_lon = geo[0]["longitude"]
        except Exception:
            pass
        if center_lat is None:
            return [{
                "_geocode_failed": True,
                "message": f"Could not find coordinates for '{location}'.",
            }]

    return store.search(
        query=query,
        n_results=n_results,
        center_lat=center_lat,
        center_lon=center_lon,
        radius_miles=radius if center_lat else None,
    )


def list_stored_climbs() -> list[dict]:
    """List all climbs in Chroma."""
    return get_store().list_all()


def get_climb_count() -> int:
    """Count of climbs in Chroma."""
    return get_store().count()


def scrape_and_load(area_url: str, max_routes: int | None = None) -> dict:
    """Scrape a Mountain Project area and load climbs into Chroma."""
    try:
        climbs = scrape_area(area_url, max_routes=max_routes)
        if not climbs:
            return {"added": 0, "status": "ok", "message": "No climbs found", "area_url": area_url}
        store = get_store()
        added = store.add_climbs(climbs)
        return {
            "added": added,
            "status": "ok",
            "area_url": area_url,
            "total_in_store": store.count(),
        }
    except Exception as e:
        logger.exception("Scrape failed for %s", area_url)
        return {"added": 0, "status": "error", "error": str(e), "area_url": area_url}
