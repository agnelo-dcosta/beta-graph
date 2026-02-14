"""Shared configuration for beta-graph MCP servers."""

import os
from pathlib import Path

# Chroma configuration
CHROMA_PERSIST_DIR = Path(os.getenv("CHROMA_PERSIST_DIR", "./chroma_data"))

# For GCP: use HttpClient when these are set
CHROMA_SERVER_HOST = os.getenv("CHROMA_SERVER_HOST")
CHROMA_SERVER_PORT = int(os.getenv("CHROMA_SERVER_PORT", "8000"))

# Scraper configuration (used by servers that scrape)
SCRAPE_DELAY_SECONDS = float(os.getenv("SCRAPE_DELAY", "2.0"))
USE_PLAYWRIGHT = os.getenv("USE_PLAYWRIGHT", "true").lower() == "true"
