# Running MCP Servers Manually (to see logs)

By default, Cursor spawns each MCP server when you use its tools. You won't see scrape logs because they go to Cursor's spawned process.

To see logs (including background scrape), run the server yourself and point Cursor to it:

## 1. Run WTA server with HTTP transport

```bash
cd /Users/srasane/shivaniProject/beta-graph
python3 -m beta_graph.servers.wta.server --http
```

Server starts on `http://localhost:8001`.

## 2. Point Cursor to your server

Edit `mcp.json` (or Cursor Settings → MCP) and use `url` instead of `command` for wta-trails:

```json
{
  "mcpServers": {
    "wta-trails": {
      "url": "http://localhost:8001/sse"
    },
    "mapbox-geocode": { ... },
    "weather": { ... }
  }
}
```

## 3. Restart Cursor's MCP connection

Reload MCP (or restart Cursor) so it connects to your server instead of spawning one.

## 4. Trigger a scrape

Search for a region with no trails yet, e.g. **"Olympic National Park hikes"**. You'll see:

```
14:04:09 [INFO] beta_graph.servers.wta.server: search_trails(query='hikes', location='Olympic National Park, WA')
14:04:09 [INFO] beta_graph.servers.wta.handlers: Background scrape started for 'Olympic National Park, WA' (radius=20 mi)
14:04:09 [INFO] beta_graph.servers.wta.handlers: Background scrape: geocoding 'Olympic National Park, WA'
...
```

## Revert to auto-spawn

Change wta-trails back to command in mcp.json:

```json
"wta-trails": {
  "command": "python3",
  "args": ["-m", "beta_graph.servers.wta.server"],
  "cwd": "/Users/srasane/shivaniProject/beta-graph"
}
```
