"""WTA server configuration."""

import os

CHROMA_COLLECTION_NAME = os.getenv("WTA_CHROMA_COLLECTION", "wta_trails")
DEFAULT_SCRAPE_PAGE_LIMIT = int(os.getenv("WTA_SCRAPE_PAGE_LIMIT", "10"))
DEFAULT_RADIUS_MILES = float(os.getenv("WTA_DEFAULT_RADIUS_MILES", "20"))
LAZY_SCRAPE_RADIUS_MILES = float(os.getenv("WTA_LAZY_SCRAPE_RADIUS", "50"))

# RAG: fetch fresh alerts/conditions at query time (not from stored Chroma data)
ENABLE_FRESH_RAG = os.getenv("WTA_ENABLE_FRESH_RAG", "true").lower() in ("true", "1", "yes")
RAG_FETCH_CONDITIONS = os.getenv("WTA_RAG_FETCH_CONDITIONS", "true").lower() in ("true", "1", "yes")
