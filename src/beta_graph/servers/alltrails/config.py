"""AllTrails server configuration."""

import os

CHROMA_COLLECTION_NAME = os.getenv("CHROMA_COLLECTION", "alltrails_north_bend")
