"""MCP server for Mountain Project climbs - vector search and scrape."""

import asyncio
import logging
import sys

from fastmcp import FastMCP
from fastmcp.server import Context

from beta_graph.servers.climb import handlers

logger = logging.getLogger(__name__)

mcp = FastMCP("climb")


@mcp.tool()
async def search_climbs(
    query: str,
    n_results: int = 5,
    location: str | None = None,
    radius_miles: float | None = None,
    ctx: Context | None = None,
) -> list[dict]:
    """Semantic search over Mountain Project climbs.

    Args:
        query: Natural language query (e.g. 'easy trad', '5.10 sport', 'boulder problems').
        n_results: Max results. Default 5.
        location: Place name to filter climbs within radius (e.g. 'Leavenworth').
        radius_miles: Max distance from location in miles. Default 25.
        ctx: MCP context (do not pass).
    """
    if ctx:
        await ctx.info(f"Searching climbs: {query!r}" + (f" near {location!r}" if location else ""))
    try:
        result = await asyncio.to_thread(
            handlers.search_climbs,
            query=query,
            n_results=n_results,
            location=location,
            radius_miles=radius_miles,
        )
    except Exception as e:
        if ctx:
            await ctx.error(f"Climb search failed: {e}")
        raise
    if ctx and result and not (isinstance(result[0], dict) and result[0].get("_geocode_failed")):
        await ctx.info(f"Found {len(result)} climb(s)")
    return result


@mcp.tool()
def list_stored_climbs() -> list[dict]:
    """List all climbs currently stored in the vector database."""
    return handlers.list_stored_climbs()


@mcp.tool()
def get_climb_count() -> int:
    """Get the number of climbs stored in the vector database."""
    return handlers.get_climb_count()


@mcp.tool()
async def scrape_area(
    area_url: str,
    max_routes: int | None = None,
    ctx: Context | None = None,
) -> dict:
    """Scrape a Mountain Project area and load climbs into Chroma.

    Args:
        area_url: Full URL e.g. https://www.mountainproject.com/area/105794001/tumwater-canyon
        max_routes: Optional limit on number of routes to scrape.
        ctx: MCP context (do not pass).

    Returns:
        Dict with added count and status.
    """
    if ctx:
        await ctx.info(f"Scraping area: {area_url}")
    try:
        result = await asyncio.to_thread(
            handlers.scrape_and_load,
            area_url=area_url,
            max_routes=max_routes,
        )
    except Exception as e:
        if ctx:
            await ctx.error(f"Scrape failed: {e}")
        raise
    if ctx:
        await ctx.info(f"Scrape complete: added {result.get('added', 0)} climbs")
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
        port = int(os.getenv("CLIMB_MCP_PORT", "8002"))
        mcp.run(transport="sse", host="0.0.0.0", port=port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
