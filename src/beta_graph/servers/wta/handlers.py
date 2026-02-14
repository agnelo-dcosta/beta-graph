"""Shared WTA trail handlers - used by WTA server."""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from beta_graph.servers.geocode.geocode import geocode_forward
from beta_graph.servers.wta.chroma_store import WTAVectorStore
from beta_graph.servers.wta.config import (
    DEFAULT_RADIUS_MILES,
    ENABLE_FRESH_RAG,
    LAZY_SCRAPE_RADIUS_MILES,
    RAG_FETCH_CONDITIONS,
)
from beta_graph.servers.wta.scraper import fetch_fresh_trail_info, scrape_wta_trails_for_location

logger = logging.getLogger(__name__)

# Locations too generic for lazy scrape (state-only, or trail-like – not a real place)
_LAZY_SCRAPE_SKIP_LOCATIONS = frozenset({
    "washington", "wa", "washington state",
    "california", "ca", "oregon", "or", "idaho", "id",
    "seattle area", "puget sound",  # too broad
})

_store: WTAVectorStore | None = None
_scraping_locations: set[str] = set()
_scraped_locations: set[str] = set()  # Locations we already scraped (avoid re-scraping)
_scraping_lock = threading.Lock()


def get_store() -> WTAVectorStore:
    global _store
    if _store is None:
        _store = WTAVectorStore()
    return _store


def lazy_scrape_and_load(location: str, radius_miles: float) -> int:
    """Geocode location, scrape WTA trails within radius, load into Chroma incrementally."""
    logger.info("Background scrape: geocoding '%s'", location)
    results = geocode_forward(location, limit=1)
    if not results or results[0].get("latitude") is None:
        logger.warning("Background scrape: geocode failed for '%s'", location)
        return 0
    lat = results[0]["latitude"]
    lon = results[0]["longitude"]
    logger.info("Background scrape: %s -> (%.4f, %.4f), radius=%.0f mi", location, lat, lon, radius_miles)
    store = get_store()

    def add_each(trail):
        store.add_trails([trail])
        logger.info("Background scrape: loaded %s", trail.name)

    trails = scrape_wta_trails_for_location(
        center_lat=lat,
        center_lon=lon,
        radius_miles=radius_miles,
        fetch_trip_reports=False,
        on_trail=add_each,
    )
    if not trails:
        logger.warning("Background scrape: 0 trails for '%s'", location)
        return 0
    loc_key = f"{location.lower().strip()}|{radius_miles}"
    with _scraping_lock:
        _scraped_locations.add(loc_key)
    logger.info("Background scrape: finished %d trails for '%s' (total: %d)", len(trails), location, store.count())
    return len(trails)


def search_trails(
    query: str,
    n_results: int = 5,
    location: str | None = None,
    radius_miles: float | None = None,
    lazy_scrape: bool = True,
    rescrape: bool = False,
) -> list[dict]:
    """Semantic search over WTA trails. Returns results or retry message if lazy scrape started."""
    store = get_store()
    radius = radius_miles if radius_miles is not None else DEFAULT_RADIUS_MILES
    center_lat = center_lon = None

    if location:
        try:
            geo = geocode_forward(location, limit=1)
            if geo and geo[0].get("latitude") is not None:
                center_lat = geo[0]["latitude"]
                center_lon = geo[0]["longitude"]
        except Exception:
            pass
        # Don't return unfiltered results when geocode failed - user asked for a specific place
        if center_lat is None:
            return [{
                "_geocode_failed": True,
                "message": f"Could not find coordinates for '{location}'. Try a nearby place (e.g. 'Mt. Baker, WA', 'Heather Meadows, WA', 'Glacier, WA') or a broader area.",
            }]

    results = store.search(
        query=query,
        n_results=n_results,
        center_lat=center_lat,
        center_lon=center_lon,
        radius_miles=radius if center_lat else None,
    )

    # Fallback: no/few results with default radius but we have location → retry with wider radius
    # (trails near Artist Point, Heather Meadows etc. can be 5–15 mi apart)
    if center_lat is not None and radius == DEFAULT_RADIUS_MILES and len(results) < 3:
        wider = LAZY_SCRAPE_RADIUS_MILES
        wider_results = store.search(
            query=query,
            n_results=n_results,
            center_lat=center_lat,
            center_lon=center_lon,
            radius_miles=wider,
        )
        if len(wider_results) > len(results):
            results = wider_results

    # RAG: enrich with fresh alerts and conditions (fetch at query time)
    if results and ENABLE_FRESH_RAG:
        slug_to_result = {r.get("slug"): r for r in results if r.get("slug")}
        with ThreadPoolExecutor(max_workers=min(5, len(slug_to_result))) as ex:
            futures = {
                ex.submit(
                    fetch_fresh_trail_info,
                    slug,
                    fetch_conditions=RAG_FETCH_CONDITIONS,
                ): slug
                for slug in slug_to_result
            }
            for future in as_completed(futures):
                slug = futures[future]
                try:
                    fresh = future.result()
                    r = slug_to_result.get(slug)
                    if r:
                        r["alerts"] = fresh.get("alerts") or []
                        r["trip_reports"] = fresh.get("trip_reports") or []
                except Exception as e:
                    logger.warning("RAG fetch failed for %s: %s", slug, e)

    # Lazy scrape: few or no results + location → start background scrape to enrich DB
    loc_normalized = location.lower().strip() if location else ""
    few_results = len(results) < 3
    should_scrape = (not results or few_results) and location and lazy_scrape and center_lat is not None

    if should_scrape:
        if loc_normalized in _LAZY_SCRAPE_SKIP_LOCATIONS:
            return [{
                "_skip_scrape": True,
                "message": f"'{location}' is too broad – try a specific place (e.g. Olympic National Park, North Bend, Leavenworth).",
            }]
        if any(w in loc_normalized for w in ("spruce", "cedar", "mosses")):
            return [{
                "_skip_scrape": True,
                "message": f"'{location}' looks like a trail or feature, not a place. Try a location (e.g. Olympic National Park, WA) or search by name without location.",
            }]
        if not results and loc_normalized == (query or "").lower().strip():
            return [{
                "_skip_scrape": True,
                "message": f"Search for '{query}' returned no trails. Try a place name (e.g. Olympic NP, North Bend) or different keywords.",
            }]
        else:
            scrape_radius = LAZY_SCRAPE_RADIUS_MILES
            loc_key = f"{loc_normalized}|{scrape_radius}"
            with _scraping_lock:
                already_scraped = loc_key in _scraped_locations and not rescrape
                in_progress = loc_key in _scraping_locations

            if not results and already_scraped:
                return [{
                    "_already_scraped": True,
                    "message": f"We've already loaded trails for '{location}'. No results match your query – try different keywords or a broader search.",
                }]
            if not results and in_progress:
                return [{
                    "_fetching": True,
                    "message": f"Trails for '{location}' are being fetched. Please retry in 2–3 minutes.",
                }]
            if few_results and already_scraped and not rescrape:
                pass  # don't re-scrape; return results
            elif in_progress:
                pass  # scrape running; return results
            else:
                with _scraping_lock:
                    if loc_key not in _scraping_locations:
                        _scraping_locations.add(loc_key)

                        def _run_scrape():
                            try:
                                logger.info("Background scrape started for '%s' (radius=%.0f mi)", location, scrape_radius)
                                added = lazy_scrape_and_load(location, scrape_radius)
                                with _scraping_lock:
                                    _scraped_locations.add(loc_key)
                                logger.info("Background scrape finished for '%s': %d trails", location, added)
                            except Exception as e:
                                logger.exception("Background scrape failed for '%s': %s", location, e)
                            finally:
                                with _scraping_lock:
                                    _scraping_locations.discard(loc_key)

                        thread = threading.Thread(target=_run_scrape, daemon=False)
                        thread.start()

            if not results:
                return [{
                    "_fetching": True,
                    "message": f"No trails for '{location}' yet. Fetching in background – please retry in 2–3 minutes.",
                }]
            # few_results: return what we have; scrape runs in background for next time

    return results


def list_stored_trails() -> list[dict]:
    """List all trails in Chroma."""
    return get_store().list_all()


def get_trail_count() -> int:
    """Count of trails in Chroma."""
    return get_store().count()


def scrape_region(location: str, radius_miles: float = 50, rescrape: bool = False) -> dict:
    """Manually scrape a region and load into Chroma.
    rescrape: If True, clear location from scrape cache so future searches will re-scrape.
    """
    try:
        if rescrape:
            loc_key = f"{location.lower().strip()}|{radius_miles}"
            with _scraping_lock:
                _scraped_locations.discard(loc_key)
        added = lazy_scrape_and_load(location, radius_miles)
        return {"added": added, "status": "ok", "location": location, "radius_miles": radius_miles}
    except Exception as e:
        return {"added": 0, "status": "error", "error": str(e)}
