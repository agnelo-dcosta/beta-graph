"""WTA server configuration."""

import os

CHROMA_COLLECTION_NAME = os.getenv("WTA_CHROMA_COLLECTION", "wta_trails")
DEFAULT_SCRAPE_PAGE_LIMIT = int(os.getenv("WTA_SCRAPE_PAGE_LIMIT", "10"))
DEFAULT_RADIUS_MILES = float(os.getenv("WTA_DEFAULT_RADIUS_MILES", "5"))
LAZY_SCRAPE_RADIUS_MILES = float(os.getenv("WTA_LAZY_SCRAPE_RADIUS", "35"))
