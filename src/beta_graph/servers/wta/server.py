"""MCP server for WTA trails - vector search, lazy scrape on empty location."""

import logging
import sys

from fastmcp import FastMCP

from beta_graph.servers.wta import handlers

logger = logging.getLogger(__name__)

mcp = FastMCP("wta-trails")


@mcp.tool()
def search_trails(
    query: str,
    n_results: int = 5,
    location: str | None = None,
    radius_miles: float | None = None,
    lazy_scrape: bool = True,
) -> list[dict]:
    """Semantic search over WTA trails.

    IMPORTANT: Pass location when the user mentions a place (Leavenworth, North Bend,
    Seattle, Olympic NP, etc.). Without it, results include trails from all of WA.

    Args:
        query: Natural language query (e.g. 'moderate hike', 'dog friendly', 'waterfall').
        n_results: Max results. Default 5.
        location: Place name to filter trails within radius (e.g. 'Leavenworth', 'North Bend').
        radius_miles: Max distance from location in miles. Default 20.
        lazy_scrape: If True and location given, scrape and load when no results.
    """
    logger.info("search_trails(query=%r, location=%r)", query, location)
    return handlers.search_trails(
        query=query,
        n_results=n_results,
        location=location,
        radius_miles=radius_miles,
        lazy_scrape=lazy_scrape,
    )


@mcp.tool()
def list_stored_trails() -> list[dict]:
    """List all trails currently stored in the WTA vector database."""
    return handlers.list_stored_trails()


@mcp.tool()
def get_trail_count() -> int:
    """Get the number of WTA trails stored in the vector database."""
    return handlers.get_trail_count()


@mcp.tool()
def scrape_region(location: str, radius_miles: float = 50) -> dict:
    """Manually scrape WTA trails for a region and load into Chroma.

    Use when you want to pre-load trails for a location.

    Args:
        location: Place name (e.g. 'Kirkland', 'Seattle').
        radius_miles: Scrape trails within this many miles. Default 50.

    Returns:
        Dict with added count and status.
    """
    return handlers.scrape_region(location=location, radius_miles=radius_miles)


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )
    if "--http" in sys.argv:
        mcp.run(transport="sse", host="0.0.0.0", port=8001)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
