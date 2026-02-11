# MCP Server Setup

## Add to Cursor

Add to your Cursor MCP config (`~/.cursor/mcp.json` or project `.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "alltrails-trails": {
      "command": "python3",
      "args": ["-m", "beta_graph.servers.alltrails.server"],
      "cwd": "/path/to/beta-graph"
    }
  }
}
```

## Available Tools

| Tool | Description |
|------|-------------|
| `search_trails` | Semantic search - "easy family hike", "waterfall", etc. |
| `list_stored_trails` | List all trails in the store |
| `get_trail_count` | Get count of stored trails |

## First Run

1. Scrape trails locally: `python3 scripts/scrape_yosemite_climbing.py` (or `test_scrape_requests.py`)
2. Load into Chroma: `python3 scripts/load_trails_to_chroma.py`
3. Start the MCP server and use `search_trails` for natural language queries
