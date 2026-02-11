#!/usr/bin/env python3
"""Run the trail+weather agent with Gemini.

Usage:
    python3 scripts/run_agent.py              # Chat mode (multi-turn, remembers context)
    python3 scripts/run_agent.py --chat        # Same
    python3 scripts/run_agent.py "one question" # Single shot
    python3 scripts/run_agent.py --verbose "moderate hikes"

In chat mode, type 'quit' or 'exit' to stop. The agent remembers the conversation.

Requires:
    - GOOGLE_API_KEY or keys/google_api_key (get from https://aistudio.google.com/apikey)
    - keys/openweathermap_api_key for weather
    - Trails loaded: python3 scripts/load_trails_to_chroma.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from beta_graph.agent.graph import run_cli

if __name__ == "__main__":
    run_cli()
