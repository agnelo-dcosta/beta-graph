"""MCP server for WTA trails - vector search, lazy scrape, geocoding."""

import asyncio
import logging
import sys

from fastmcp import FastMCP
from fastmcp.server import Context

from beta_graph.servers.geocode.geocode import geocode_forward
from beta_graph.servers.wta import handlers

logger = logging.getLogger(__name__)

mcp = FastMCP("wta-trails")


@mcp.tool()
async def search_trails(
    query: str = "trail",
    n_results: int = 5,
    location: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    radius_miles: float | None = None,
    lazy_scrape: bool = True,
    rescrape: bool = False,
    ctx: Context | None = None,
) -> list[dict]:
    """Semantic search over WTA trails.

    IMPORTANT: Pass location when the user mentions a place (Leavenworth, North Bend,
    Seattle, Olympic NP, etc.). Or pass latitude/longitude when the user gives coordinates.
    Without location or coordinates, results include trails from all of WA.

    Args:
        query: Natural language query (e.g. 'moderate hike', 'dog friendly', 'waterfall').
            Default 'trail' when only coordinates are given.
        n_results: Max results. Default 5.
        location: Place name to filter trails within radius (e.g. 'Leavenworth', 'North Bend').
        latitude: Optional. Latitude (-90 to 90) when user provides coordinates.
        longitude: Optional. Longitude (-180 to 180) when user provides coordinates.
        radius_miles: Max distance from location/coordinates in miles. Default 5.
        lazy_scrape: If True and location given, scrape and load when no/few results.
        rescrape: If True, re-scrape location even if already scraped (default: False).
        ctx: MCP context, injected by server (do not pass).
    """
    logger.info("search_trails(query=%r, location=%r, lat=%s, lon=%s)", query, location, latitude, longitude)
    if ctx:
        loc_desc = f", location={location!r}" if location else (f", coords=({latitude}, {longitude})" if latitude is not None and longitude is not None else "")
        await ctx.info(f"Searching trails: query={query!r}{loc_desc}")
    try:
        result = await asyncio.to_thread(
            handlers.search_trails,
            query=query,
            n_results=n_results,
            location=location,
            latitude=latitude,
            longitude=longitude,
            radius_miles=radius_miles,
            lazy_scrape=lazy_scrape,
            rescrape=rescrape,
        )
    except Exception as e:
        if ctx:
            await ctx.error(f"Trail search failed: {e}")
        raise
    if ctx:
        n = len(result)
        if n and isinstance(result[0], dict):
            if result[0].get("_fetching"):
                await ctx.info("Started background scrape for location – try again in 2–3 minutes")
            elif result[0].get("_geocode_failed"):
                await ctx.warning("Geocode failed for the given location")
            elif result[0].get("_already_scraped"):
                await ctx.info("Location already scraped, no matching trails for query")
            else:
                await ctx.info(f"Found {n} trail(s)")
    return result


@mcp.tool()
def list_stored_trails() -> list[dict]:
    """List all trails currently stored in the WTA vector database."""
    return handlers.list_stored_trails()


@mcp.tool()
def get_trail_count() -> int:
    """Get the number of WTA trails stored in the vector database."""
    return handlers.get_trail_count()


@mcp.tool()
async def geocode(
    query: str,
    limit: int = 5,
    country: str = "US",
    ctx: Context | None = None,
) -> list[dict]:
    """Convert a place name to coordinates (forward geocoding). Use for weather or trail search.

    Args:
        query: Place name (e.g. 'Kirkland', 'Seattle, WA', 'Olympic National Park').
        limit: Max results. Default 5.
        country: ISO country code to bias results. Default US.
        ctx: MCP context, injected by server (do not pass).

    Returns:
        List of results with place_name, latitude, longitude.
    """
    if ctx:
        await ctx.info(f"Geocoding place: {query!r}")
    try:
        result = await asyncio.to_thread(
            geocode_forward, query=query, limit=limit, country=country or "US"
        )
    except Exception as e:
        if ctx:
            await ctx.error(f"Geocode failed for {query!r}: {e}")
        raise
    if ctx and result:
        await ctx.info(f"Geocode returned {len(result)} result(s)")
    return result


@mcp.tool()
async def scrape_region(
    location: str,
    radius_miles: float = 50,
    rescrape: bool = False,
    ctx: Context | None = None,
) -> dict:
    """Manually scrape WTA trails for a region and load into Chroma.

    Use when you want to pre-load trails for a location.

    Args:
        location: Place name (e.g. 'Kirkland', 'Seattle').
        radius_miles: Scrape trails within this many miles. Default 50.

    Returns:
        Dict with added count and status.
    """
    if ctx:
        await ctx.info(f"Scraping trails for {location!r} (radius {radius_miles} mi)")
    try:
        result = await asyncio.to_thread(
            handlers.scrape_region,
            location=location,
            radius_miles=radius_miles,
            rescrape=rescrape,
        )
    except Exception as e:
        if ctx:
            await ctx.error(f"Scrape failed for {location!r}: {e}")
        raise
    if ctx:
        await ctx.info(f"Scrape complete: added {result.get('added', 0)} trails")
    return result


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )
    if "--http" in sys.argv:
        import os
        port = int(os.getenv("WTA_MCP_PORT", "8001"))
        mcp.run(transport="sse", host="0.0.0.0", port=port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
