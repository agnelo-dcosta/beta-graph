# AllTrails MCP Server

MCP server that loads trail data from JSON and exposes semantic search in Chroma. No scraping in the server.

## Overview

Scraping is done separately via scripts (e.g. `scrape_yosemite_climbing.py`, `test_scrape_requests.py`). The MCP server loads from JSON files and provides search. An agent can search trails with natural language (e.g. "easy dog-friendly hike", "waterfall views").

## Files

| File | Purpose |
|------|---------|
| `server.py` | MCP server entry point; defines tools and wires them to store |
| `chroma_store.py` | Chroma vector store: add, search, list, count trails |
| `models.py` | `Trail` and `TrailReview` Pydantic models |
| `config.py` | Chroma collection name |
| `scraper.py` | Scrapes region pages (used by scripts only, not in MCP) |
| `trail_detail.py` | Fetches trail detail pages (used by scripts only, not in MCP) |
| `validate.py` | Validates AllTrails URLs (used by scripts only, not in MCP) |
| `cookies.py` | Load cookies from file (used by scripts only, not in MCP) |

## Tools

| Tool | Description |
|------|-------------|
| `search_trails` | Semantic search over stored trails. Pass a natural-language query and optional `n_results`. |
| `list_stored_trails` | List all trails in the vector store. |
| `get_trail_count` | Return the number of stored trails. |

## Data Flow

1. **Scrape (scripts)** – Run `python3 scripts/scrape_yosemite_climbing.py` or `python3 scripts/test_scrape_requests.py` locally to scrape and save JSON.
2. **Load (script)** – Run `python3 scripts/load_trails_to_chroma.py` to load JSON into Chroma.
3. **Search (MCP)** – Agent queries with natural language via `search_trails`; Chroma returns nearest trails by embedding similarity.

## Configuration

- `CHROMA_COLLECTION` – Chroma collection name; env var `CHROMA_COLLECTION` or `alltrails_north_bend`.

## Starting the server

Commands to launch the MCP server (so Cursor or other clients can call the tools):

```bash
# Stdio (for Cursor MCP)
python3 -m beta_graph.servers.alltrails.server

# HTTP (for remote clients)
python3 -m beta_graph.servers.alltrails.server --http
```
