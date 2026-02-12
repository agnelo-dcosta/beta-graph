# Beta Graph Architecture

## Overview

Climbing route planner with:
- **MCP servers** – AllTrails trails (Chroma search), WTA trails (Chroma search), weather (OpenWeatherMap), Mapbox (geocoding)
- **LangGraph agent** – Standalone agent (Gemini + trail + weather tools) for natural-language queries
- **Scripts** – Scrape trails, load into Chroma, run the agent

## Folder Structure

```
beta-graph/
├── keys/                      # API keys (gitignored)
│   ├── google_api_key         # Gemini (agent)
│   ├── openweathermap_api_key # Weather
│   ├── mapbox_api_key         # Geocoding (WTA location filter)
│   └── alltrails_cookies      # Scraping (optional)
├── scripts/
│   ├── load_trails_to_chroma.py   # Load AllTrails JSON → Chroma
│   ├── load_wta_to_chroma.py      # Scrape WTA → Chroma
│   ├── run_agent.py               # Run LangGraph agent
│   ├── scrape_yosemite_climbing.py
│   ├── test_scrape_requests.py
│   └── ...
└── src/beta_graph/
    ├── agent/                 # LangGraph + Gemini agent
    │   ├── graph.py           # create_agent(), run_cli()
    │   └── tools.py          # search_trails, get_weather_forecast, get_trail_count
    │
    ├── shared/                # Shared across servers
    │   ├── chroma.py         # Chroma client, embedding function
    │   └── config.py        # Env vars (CHROMA_*, etc.)
    │
    └── servers/
        ├── alltrails/        # AllTrails MCP server (Chroma search only)
        │   ├── chroma_store.py
        │   ├── config.py
        │   ├── cookies.py    # AllTrails cookies for scraping
        │   ├── models.py
        │   ├── scraper.py   # Used by scripts, not MCP
        │   ├── trail_detail.py
        │   ├── validate.py
        │   └── server.py
        │
        ├── weather/          # Weather MCP server
        │   ├── config.py
        │   ├── forecast.py   # Shared logic (OpenWeatherMap API)
        │   └── server.py
        │
        ├── wta/              # WTA MCP server (vector search + lazy scrape)
        │   ├── chroma_store.py
        │   ├── models.py
        │   ├── scraper.py
        │   └── server.py
        │
        ├── mapbox/           # Mapbox MCP server (geocoding)
        │   ├── geocode.py
        │   └── server.py
        │
```

## Data Flow

1. **Scrape** (scripts) – `scrape_yosemite_climbing.py`, `test_scrape_requests.py` → JSON files
2. **Load** (script) – `load_trails_to_chroma.py` → Chroma vector store
3. **Search** (MCP or agent) – `search_trails`, `get_weather_forecast` tools → natural-language queries

The MCP servers do **not** scrape; they only search/query. Scraping is done by scripts run locally.

## Entry Points

| Entry Point      | Module                           | Description                         |
|------------------|----------------------------------|-------------------------------------|
| `beta-graph-mcp` | alltrails.server                 | AllTrails trails only (Chroma)      |
| `weather-mcp`    | weather.server                   | Weather forecast only               |
| `wta-mcp`        | wta.server                       | WTA trails (Chroma + lazy scrape)   |
| `mapbox-mcp`     | mapbox.server                    | Mapbox geocoding                    |
| `beta-graph-agent` | agent.graph.run_cli           | LangGraph agent (Gemini + tools)     |

## Adding a New Server

1. Create `servers/<name>/` with:
   - `server.py` – FastMCP instance and tools
   - `config.py` – server-specific config
   - Other modules as needed

2. Add entry point in `pyproject.toml`:
   ```toml
   [project.scripts]
   <name>-mcp = "beta_graph.servers.<name>.server:main"
   ```

3. Use `shared/` for Chroma client, config, etc.

## Future Servers

| Server   | Status   | Description            |
|----------|----------|------------------------|
| AllTrails| Done     | Chroma search, scraping via scripts |
| Weather  | Done     | OpenWeatherMap 5-day forecast |
| Mountain Project | Future | Climbing routes     |
