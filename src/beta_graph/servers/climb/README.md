# Climb MCP Server

Mountain Project climbing route search with vector semantic search. Scrapes area pages and stores routes in Chroma.

## Features

- **Vector search** – Semantic search on keywords (e.g. "easy trad", "5.10 sport", "boulder")
- **Location filter** – Filter climbs within N miles of a place (via Google Places API)
- **Scrape areas** – Load climbs from any Mountain Project area URL (e.g. Tumwater Canyon)

## Tools

| Tool | Description |
|------|-------------|
| `search_climbs` | Semantic search. Optional `location`, `radius_miles` (default 25) |
| `list_stored_climbs` | List all climbs in Chroma |
| `get_climb_count` | Count of stored climbs |
| `scrape_area` | Scrape and load an area (e.g. Tumwater Canyon URL) |

## Setup

1. **Google Maps** (for location filter) – Add `keys/google_maps_api_key` or set `GOOGLE_MAPS_API_KEY`
2. **Chroma** – Uses shared Chroma (local persist or HTTP)
3. **Pre-load** – Run `python scripts/load_climb_to_chroma.py`

## Run

```bash
climb-mcp
# or
python -m beta_graph.servers.climb.server
# HTTP mode
climb-mcp --http   # port 8002
```
