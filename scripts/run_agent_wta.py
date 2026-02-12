#!/usr/bin/env python3
"""Run the WTA + Mapbox + Weather agent with Gemini.

The agent uses MCP servers. Start the WTA server first:
  python3 -m beta_graph.servers.wta.server --http

Usage:
    python3 scripts/run_agent_wta.py              # Chat mode
    python3 scripts/run_agent_wta.py --chat        # Same
    python3 scripts/run_agent_wta.py "hikes near North Bend with good weather"
    python3 scripts/run_agent_wta.py --verbose "moderate hikes"

In chat mode, type 'quit' or 'exit' to stop.

Requires:
    - GOOGLE_API_KEY or keys/google_api_key (https://aistudio.google.com/apikey)
    - keys/openweathermap_api_key for weather
    - keys/mapbox_api_key for geocoding (place names -> lat/lon)
    - WTA trails loaded: python3 scripts/load_wta_to_chroma.py
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

# Show background scrape logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

from beta_graph.agent.graph_wta import run_cli

if __name__ == "__main__":
    run_cli()
