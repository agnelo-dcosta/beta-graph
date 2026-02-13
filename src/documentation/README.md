# Cursor Setup

## MCP Server Config

Add this to your Cursor MCP config (`~/.cursor/mcp.json`) or use Settings → MCP:

### MCP servers (Cursor starts each when needed)

```json
{
  "mcpServers": {
    "wta-trails": {
      "command": "python3",
      "args": ["-m", "beta_graph.servers.wta.server"],
      "cwd": "/Users/srasane/shivaniProject/beta-graph"
    },
    "weather": {
      "command": "python3",
      "args": ["-m", "beta_graph.servers.weather.server"],
      "cwd": "/Users/srasane/shivaniProject/beta-graph"
    }
  }
}
```

## API Keys (keys/ folder)

All API keys go in the `keys/` folder. See `keys/README.md` for setup.

1. Copy `keys/openweathermap_api_key.example` to `keys/openweathermap_api_key`
2. Copy `keys/google_api_key.example` to `keys/google_api_key`
3. Paste your keys (sign up at openweathermap.org and aistudio.google.com)

Or set env vars: `OPENWEATHERMAP_API_KEY`, `GOOGLE_API_KEY`.

## How to Run Servers

- **Automatic**: Cursor starts each server from mcp.json when you use its tools.
- **Manual** (separate terminals to see logs): `python3 -m beta_graph.servers.wta.server`, `python3 -m beta_graph.servers.weather.server`, etc.

## How to Run the Agent (LangGraph + Gemini)

Standalone agent that searches trails and fetches weather using LangChain, LangGraph, and Google Gemini (free tier).

### Setup (one-time)

1. **Gemini API key** – Get one at https://aistudio.google.com/apikey (free)  
   - Add to `keys/google_api_key`, or set `GOOGLE_API_KEY` env var

2. **Weather API key** – Add your key to `keys/openweathermap_api_key` (see API Keys above)

3. **Load trails** – Run once:  
   `python3 scripts/load_wta_by_region.py` or `python3 scripts/load_wta_to_chroma.py --location "North Bend"`

4. **Start MCP servers** – `python3 scripts/run_servers.py` (or run each in separate terminal for isolated logs)

### Run

```bash
# Chat mode (multi-turn, remembers context) – type quit to exit
python3 scripts/run_agent.py

# Single question
python3 scripts/run_agent.py "easy family hikes near North Bend"
python3 scripts/run_agent.py "easy family hikes with good weather"

# Or: python3 -m beta_graph.agent.graph (from project root)
# Or: beta-graph-agent (after pip install -e .)
```

### Debug

Use `--verbose` to see the message sequence if the agent returns nothing:

```bash
python3 scripts/run_agent.py --verbose "how many trails?"
```

## How to Run the Agent (Cursor MCP)

1. **Load trails** (once): `python3 scripts/load_wta_by_region.py` or `python3 scripts/load_wta_to_chroma.py`
2. **Weather**: Add API key to `keys/openweathermap_api_key`
3. **Start Cursor** – MCP auto-starts when you use the agent
4. **Use tools**: `search_trails`, `list_stored_trails`, `get_trail_count`, `get_weather_forecast`
