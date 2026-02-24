"""Climb server configuration."""

import os

CHROMA_COLLECTION_NAME = os.getenv("CLIMB_CHROMA_COLLECTION", "mp_climbs")
REQUEST_DELAY = float(os.getenv("CLIMB_SCRAPE_DELAY", "0.5"))
RETRY_ON_503_SLEEP_SEC = int(os.getenv("CLIMB_503_SLEEP", "10"))
RETRY_ON_503_MAX_RETRIES = 3
