# MCP Server Setup

## Add to Cursor

Add to your Cursor MCP config (`~/.cursor/mcp.json` or project `mcp.json`):

```json
{
  "mcpServers": {
    "wta-trails": {
      "url": "http://localhost:8001/sse"
    }
  }
}
```

For stdio transport instead:
```json
{
  "mcpServers": {
    "wta-trails": {
      "command": "python3",
      "args": ["-m", "beta_graph.servers.wta.server"],
      "cwd": "/path/to/beta-graph"
    }
  }
}
```

## Available Tools

| Tool | Description |
|------|-------------|
| `search_trails` | Semantic search - "easy family hike", "waterfall", etc. Supports location filter. |
| `list_stored_trails` | List all trails in the store |
| `get_trail_count` | Get count of stored trails |

## First Run

1. Start WTA MCP server: `python3 -m beta_graph.servers.wta.server --http` (port 8001)
2. Load trails: `python3 scripts/load_wta_by_region.py` or `python3 scripts/load_wta_to_chroma.py --location "North Bend"`
3. Use `search_trails` for natural language queries (with location for lazy scrape)
