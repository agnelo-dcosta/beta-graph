"""MCP server for AllTrails trails - vector search only.

Use load_trails_to_chroma.py to load JSON into Chroma. MCP exposes search only.
"""

from fastmcp import FastMCP

from beta_graph.servers.alltrails.chroma_store import TrailVectorStore

mcp = FastMCP("alltrails-trails")

_store: TrailVectorStore | None = None


def _get_store() -> TrailVectorStore:
    global _store
    if _store is None:
        _store = TrailVectorStore()
    return _store


@mcp.tool()
def search_trails(query: str, n_results: int = 5) -> list[dict]:
    """Semantic search over stored trails.

    Args:
        query: Natural language query (e.g. 'easy family hike', 'waterfall', 'dog friendly').
        n_results: Maximum number of trails to return. Default 5.

    Returns:
        List of matching trails with metadata and relevance scores.
    """
    store = _get_store()
    return store.search(query=query, n_results=n_results)


@mcp.tool()
def list_stored_trails() -> list[dict]:
    """List all trails currently stored in the vector database.

    Returns:
        List of trail metadata dicts for each stored trail.
    """
    store = _get_store()
    return store.list_all()


@mcp.tool()
def get_trail_count() -> int:
    """Get the number of trails stored in the vector database.

    Returns:
        Count of stored trails.
    """
    store = _get_store()
    return store.count()


def main():
    """Run the MCP server. Use --http for HTTP transport on port 8000."""
    import sys
    if "--http" in sys.argv:
        mcp.run(transport="sse", host="0.0.0.0", port=8000)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
