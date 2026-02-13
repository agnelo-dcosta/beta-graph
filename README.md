# beta-graph

Washington hiking trail planner using AI. WTA trails, Google Places API (location lookup), and weather via MCP servers.

## How to Run

### 1. Install

```bash
pip install -e .
```

### 2. API Keys (one-time)

Add keys to the `keys/` folder (see `keys/README.md`):
- `google_api_key` – Gemini (agent)
- `openweathermap_api_key` – Weather forecasts
- `google_maps_api_key` – Location lookup (Google Places API; enable Places API in GCP)

### 3. Load Trails (one-time)

```bash
python3 scripts/load_wta_by_region.py   # all regions, or: --region "North Cascades"
python3 scripts/load_wta_to_chroma.py --location "North Bend"   # or single location
```

### 4. Start Servers (run first, before agent)

**Option A – All in one terminal** (logs mixed):
```bash
python3 scripts/run_servers.py
```

**Option B – Separate terminals** (clean logs per server):
```bash
# Terminal 1
python3 -m beta_graph.servers.wta.server --http      # port 8001 (includes geocode)

# Terminal 2
python3 -m beta_graph.servers.weather.server --http  # port 8003
```

**Option C – Background** (logs to `servers.log`):
```bash
python3 scripts/run_servers.py --background
```

### 5. Run Agent

```bash
python3 scripts/run_agent.py
```

Or single question:
```bash
python3 scripts/run_agent.py "easy hikes near North Bend with good weather"
```

---

## MCP Servers (SSE)

| Server | Port | Tools |
|--------|------|-------|
| WTA trails | 8001 | `search_trails`, `list_stored_trails`, `get_trail_count`, `scrape_region`, `geocode` |
| Weather | 8003 | `get_weather_forecast` |

See [docs/MCP_SETUP.md](docs/MCP_SETUP.md) for Cursor config. See [docs/GCP_DEPLOYMENT.md](docs/GCP_DEPLOYMENT.md) for GCP deployment.

---

## Sources
1. Mountain project
2. WTA (Washington Trails Association)
3. GCP
4. Strava
5. Google maps

---

## GCP login

```bash
gcloud config configurations create beta-graph-personal
gcloud config set account rostydev101@gmail.com
gcloud config set project rostydev101
gcloud config configurations activate beta-graph-personal
gcloud auth application-default login
```
