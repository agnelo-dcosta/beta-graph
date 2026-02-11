# beta-graph

Climbing route planner using AI. MCP server for AllTrails North Bend trails with Chroma vector search.

## Sources
1. Mountain project
2. All Trails
3. GCP
4. Strava
5. Google maps

## AllTrails MCP Server

Loads trail data from JSON files into Chroma for semantic search. Scraping is done via scripts (run locally); the MCP server only loads and searches.

### Quick Start

```bash
# Install
pip install -e .

# Scrape trails (run locally first; add cookies to keys/alltrails_cookies if needed)
python3 scripts/scrape_yosemite_climbing.py   # or test_scrape_requests.py

# Run AllTrails MCP server (stdio for Cursor)
python3 -m beta_graph.servers.alltrails.server

# Or HTTP mode
python3 -m beta_graph.servers.alltrails.server --http
```

### Tools (for your agent)
- `search_trails` – Semantic search: "easy family hike", "waterfall", etc.
- `list_stored_trails` – List stored trails
- `get_trail_count` – Count of trails

See [docs/MCP_SETUP.md](docs/MCP_SETUP.md) for Cursor config. See [docs/GCP_DEPLOYMENT.md](docs/GCP_DEPLOYMENT.md) for GCP deployment.

---

## GCP login

```bash
gcloud config configurations create beta-graph-personal
gcloud config set account rostydev101@gmail.com
gcloud config set project rostydev101
gcloud config configurations activate beta-graph-personal
gcloud auth application-default login
```

