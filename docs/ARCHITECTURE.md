# Beta Graph Architecture

## Overview

Washington hiking trail planner with:
- **MCP servers** – WTA trails (Chroma search + lazy scrape + Places location lookup), weather (OpenWeatherMap)
- **LangGraph agent** – Standalone agent (Gemini + trail + weather tools) for natural-language queries
- **Scripts** – Scrape WTA trails, load into Chroma, run the agent

## Folder Structure

```
beta-graph/
├── keys/                      # API keys (gitignored)
│   ├── google_api_key         # Gemini (agent)
│   ├── openweathermap_api_key # Weather
│   └── google_maps_api_key    # Places API (WTA location filter)
├── scripts/
│   ├── load_wta_to_chroma.py     # Scrape WTA → Chroma
│   ├── load_wta_by_region.py     # Scrape trails by WTA region
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
        ├── geocode/           # Location lookup (Places API, used by WTA, no separate server)
        │   └── geocode.py     # Google Places API
        │
```

## Data Flow

1. **Scrape** (scripts) – `load_wta_by_region.py`, `load_wta_to_chroma.py` → Chroma
2. **Search** (MCP or agent) – `search_trails`, `get_weather_forecast` tools → natural-language queries

The MCP servers do **not** scrape; they only search/query. Scraping is done by scripts run locally. Lazy scrape runs when a location has no results.

## Entry Points

| Entry Point        | Module                         | Description                         |
|--------------------|--------------------------------|-------------------------------------|
| `weather-mcp`      | weather.server                 | Weather forecast only               |
| `wta-mcp`          | wta.server                     | WTA trails + Places (Chroma, lazy scrape) |
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
