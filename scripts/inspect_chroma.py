#!/usr/bin/env python3
"""Inspect trails stored in ChromaDB.

Usage:
    python scripts/inspect_chroma.py
    python scripts/inspect_chroma.py --count
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from beta_graph.servers.alltrails.config import CHROMA_COLLECTION_NAME
from beta_graph.shared.chroma import get_chroma_client


def main():
    client = get_chroma_client()
    collection = client.get_collection(name=CHROMA_COLLECTION_NAME)
    count = collection.count()
    print(f"Trails in Chroma: {count}")

    if "--count" in sys.argv:
        return

    res = collection.get(include=["metadatas"])
    trails = res.get("metadatas") or []
    for t in trails[:20]:
        name = t.get("name", "?")
        slug = t.get("slug", "?")
        tid = t.get("trailId", "?")
        loc = t.get("location", "")
        if isinstance(loc, str) and len(loc) > 50:
            loc = loc[:50] + "..."
        print(f"  {name} | {slug} | trailId={tid}")

    if count > 20:
        print(f"  ... and {count - 20} more")


if __name__ == "__main__":
    main()
