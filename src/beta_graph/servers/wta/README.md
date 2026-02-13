# WTA MCP Server

Washington Trails Association trail search with vector semantic search and lazy scrape.

## Features

- **Vector search** – Semantic search on keywords (e.g. "easy waterfalls", "dog friendly")
- **Location filter** – Filter trails within N miles of a place (via Google Places API)
- **Lazy scrape** – When a location query returns no results, automatically scrape WTA and load into Chroma
- **Same embedding model** – Uses `all-MiniLM-L6-v2` (shared across Chroma stores)

## Tools

| Tool | Description |
|------|-------------|
| `search_trails` | Semantic search. Optional `location`, `radius_miles` (default 5), `lazy_scrape` (default true), `rescrape` (default false) |
| `list_stored_trails` | List all trails in Chroma |
| `get_trail_count` | Count of stored trails |
| `scrape_region` | Manually scrape and load a region (e.g. "Kirkland", radius 50 mi). Optional `rescrape` to clear cache. |

## Setup

1. **Google Maps** (for location) – Add `keys/google_maps_api_key` or set `GOOGLE_MAPS_API_KEY`
2. **Chroma** – Uses shared Chroma (local persist or HTTP)
3. **Pre-load** (optional) – Run `python scripts/load_wta_to_chroma.py`

## Run

```bash
wta-mcp
# or
python -m beta_graph.servers.wta.server
# HTTP mode
wta-mcp --http   # port 8001
```
