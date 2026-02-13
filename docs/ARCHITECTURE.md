# Beta Graph Architecture

## Overview

Washington hiking trail planner with:
- **MCP servers** – WTA trails (Chroma search + lazy scrape + geocode), weather (OpenWeatherMap)
- **LangGraph agent** – Standalone agent (Gemini + trail + weather tools) for natural-language queries
- **Scripts** – Scrape WTA trails, load into Chroma, run the agent

## Folder Structure

```
beta-graph/
├── keys/                      # API keys (gitignored)
│   ├── google_api_key         # Gemini (agent)
│   ├── openweathermap_api_key # Weather
│   └── google_maps_api_key    # Geocoding (WTA location filter)
├── scripts/
│   ├── load_wta_to_chroma.py     # Scrape WTA → Chroma
│   ├── load_san_juan_trails.py   # Scrape Islands trails → Chroma
│   ├── run_servers.py            # Start WTA, Weather MCP servers
│   ├── run_agent.py              # Run agent (connects to servers)
│   ├── run_agent.py              # Run LangGraph agent (direct tools)
│   └── ...
└── src/beta_graph/
    ├── agent/                 # LangGraph + Gemini agent
    │   └── graph.py           # Hiking agent via MCP (tools from servers)
    │
    ├── shared/                # Shared across servers
    │   ├── chroma.py         # Chroma client, embedding function
    │   └── config.py         # Env vars (CHROMA_*, etc.)
    │
    └── servers/
        ├── weather/          # Weather MCP server
        │   ├── config.py
        │   ├── forecast.py   # Shared logic (OpenWeatherMap API)
        │   └── server.py
        │
        ├── wta/              # WTA MCP server (vector search + lazy scrape)
        │   ├── chroma_store.py
        │   ├── config.py
        │   ├── handlers.py
        │   ├── models.py
        │   ├── scraper.py
        │   └── server.py
        │
        ├── geocode/           # Geocoding API client (used by WTA, no separate server)
        │   └── geocode.py     # Google Maps API
        │
```

## Data Flow

1. **Scrape** (scripts) – `load_wta_to_chroma.py`, `load_san_juan_trails.py` → Chroma
2. **Search** (MCP or agent) – `search_trails`, `get_weather_forecast` tools → natural-language queries

The MCP servers do **not** scrape; they only search/query. Scraping is done by scripts run locally. Lazy scrape runs when a location has no results.

## Entry Points

| Entry Point        | Module                         | Description                         |
|--------------------|--------------------------------|-------------------------------------|
| `weather-mcp`      | weather.server                 | Weather forecast only               |
| `wta-mcp`          | wta.server                     | WTA trails + geocode (Chroma, lazy scrape) |
| `beta-graph-agent` | agent.graph.run_cli           | LangGraph agent (MCP tools)         |

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
| WTA      | Done     | Chroma search, lazy scrape, region pages |
| Weather  | Done     | OpenWeatherMap 5-day forecast |
| Mountain Project | Future | Climbing routes     |
