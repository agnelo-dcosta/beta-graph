"""Combined MCP server - AllTrails trails + weather forecast. One process, both tool sets."""

from fastmcp import FastMCP

from beta_graph.servers.alltrails.chroma_store import TrailVectorStore
from beta_graph.servers.weather.forecast import fetch_forecast

mcp = FastMCP("beta-graph")

# AllTrails store
_store: TrailVectorStore | None = None


def _get_store() -> TrailVectorStore:
    global _store
    if _store is None:
        _store = TrailVectorStore()
    return _store


# --- AllTrails tools ---
@mcp.tool()
def search_trails(query: str, n_results: int = 5) -> list[dict]:
    """Semantic search over stored trails."""
    return _get_store().search(query=query, n_results=n_results)


@mcp.tool()
def list_stored_trails() -> list[dict]:
    """List all trails in the vector database."""
    return _get_store().list_all()


@mcp.tool()
def get_trail_count() -> int:
    """Get the number of trails stored in the vector database."""
    return _get_store().count()


# --- Weather tools ---
@mcp.tool()
def get_weather_forecast(latitude: float, longitude: float, days: int = 5, units: str = "imperial") -> dict:
    """Get weather forecast for a location (1-5 days)."""
    return fetch_forecast(latitude=latitude, longitude=longitude, days=days, units=units)


def main():
    import sys
    if "--http" in sys.argv:
        mcp.run(transport="sse", host="0.0.0.0", port=8000)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
