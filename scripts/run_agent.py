#!/usr/bin/env python3
"""Run the WTA trail+weather agent with Gemini (uses MCP servers).

Usage:
    python3 scripts/run_agent.py              # Chat mode (multi-turn, remembers context)
    python3 scripts/run_agent.py --chat        # Same
    python3 scripts/run_agent.py "one question" # Single shot
    python3 scripts/run_agent.py --verbose "moderate hikes"

In chat mode, type 'quit' or 'exit' to stop. The agent remembers the conversation.

Requires:
    - Servers running: python3 scripts/run_servers.py (or run each in separate terminal)
    - GOOGLE_API_KEY or keys/google_api_key (get from https://aistudio.google.com/apikey)
    - keys/openweathermap_api_key, keys/google_maps_api_key
    - Trails: python3 scripts/load_wta_to_chroma.py or lazy scrape on first query
"""

import logging
import sys
from pathlib import Path

# Show background scrape logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from beta_graph.agent.graph import run_cli

if __name__ == "__main__":
    run_cli()
