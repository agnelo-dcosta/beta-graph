#!/usr/bin/env python3
"""Load trail JSON files into ChromaDB. Standalone script (not in MCP server).

Usage:
    python scripts/load_trails_to_chroma.py
    python scripts/load_trails_to_chroma.py scripts/yosemite_trails_new.json scripts/north_bend_trails_new.json
    python scripts/load_trails_to_chroma.py scripts/*.json

Loads JSON files produced by scrape scripts and upserts into Chroma.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from beta_graph.servers.alltrails.chroma_store import TrailVectorStore
from beta_graph.servers.alltrails.models import Trail

DEFAULT_FILES = [
    "yosemite_trails_new.json",
    "north_bend_trails_new.json",
]


def load_trails_from_file(path: Path) -> list[Trail]:
    """Load trails from a JSON file."""
    data = path.read_text(encoding="utf-8")
    items = json.loads(data)
    if not isinstance(items, list):
        return []
    trails = []
    for item in items:
        if isinstance(item, dict):
            try:
                trails.append(Trail.model_validate(item))
            except Exception:
                pass
    return trails


def main():
    script_dir = Path(__file__).parent
    args = sys.argv[1:]
    if args:
        paths = [Path(p).expanduser().resolve() for p in args]
    else:
        paths = [script_dir / f for f in DEFAULT_FILES]

    store = TrailVectorStore()
    total = 0

    for path in paths:
        if not path.is_file():
            print(f"Skip (not found): {path}")
            continue
        trails = load_trails_from_file(path)
        if not trails:
            print(f"Skip (no valid trails): {path}")
            continue
        count = store.add_trails(trails)
        total += count
        print(f"Loaded {count} trails from {path.name}")

    print(f"\nTotal: {total} trails in Chroma. Count: {store.count()}")


if __name__ == "__main__":
    main()
