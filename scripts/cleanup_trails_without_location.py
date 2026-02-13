#!/usr/bin/env python3
"""Remove trails that have no latitude/longitude from Chroma.

Usage:
    python scripts/cleanup_trails_without_location.py

Run once after switching to location-required to clean existing data.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from beta_graph.servers.wta.chroma_store import WTAVectorStore


def main():
    store = WTAVectorStore()
    before = store.count()
    deleted = store.delete_trails_without_location()
    after = store.count()
    print(f"Removed {deleted} trails without coordinates. Before: {before}, after: {after}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
