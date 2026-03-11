#!/usr/bin/env python3
"""Inspect trails or climbs stored in ChromaDB.

Usage:
    python scripts/inspect_chroma.py           # WTA trails (first 20)
    python scripts/inspect_chroma.py --climbs # Mountain Project climbs
    python scripts/inspect_chroma.py --count  # WTA count only
    python scripts/inspect_chroma.py --climbs --count  # climb count only
    python scripts/inspect_chroma.py --climbs --all     # show all climbs
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from beta_graph.servers.climb.config import CHROMA_COLLECTION_NAME as CLIMB_COLLECTION
from beta_graph.servers.wta.config import CHROMA_COLLECTION_NAME as WTA_COLLECTION
from beta_graph.shared.chroma import get_chroma_client


def main():
    args = sys.argv[1:]
    climbs_mode = "--climbs" in args
    count_only = "--count" in args
    show_all = "--all" in args

    collection_name = CLIMB_COLLECTION if climbs_mode else WTA_COLLECTION
    kind = "Climbs" if climbs_mode else "Trails"

    try:
        client = get_chroma_client()
        collection = client.get_collection(name=collection_name)
    except Exception as e:
        print(f"Collection {collection_name} not found: {e}")
        return 1

    count = collection.count()
    print(f"{kind} in Chroma: {count}")

    if count_only:
        return 0

    res = collection.get(include=["metadatas"])
    items = res.get("metadatas") or []
    limit = None if show_all else 20

    for t in items[:limit] if limit else items:
        if climbs_mode:
            name = t.get("name", "?")
            diff = t.get("difficulty", "")
            ctype = t.get("climb_type", "")
            area = t.get("area_name", "")
            parent = t.get("parent_area", "")
            print(f"  {name} | {diff} {ctype} | {area or parent}")
        else:
            name = t.get("name", "?")
            slug = t.get("slug", "?")
            region = t.get("region", "")
            print(f"  {name} | {slug} | {region}")

    if limit and count > limit:
        print(f"  ... and {count - limit} more")


if __name__ == "__main__":
    sys.exit(main() or 0)
