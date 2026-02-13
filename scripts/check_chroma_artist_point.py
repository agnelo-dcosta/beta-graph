#!/usr/bin/env python3
"""Check if Artist Point area trails are in Chroma."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

# Artist Point coordinates (Mt. Baker)
ARTIST_POINT_LAT = 48.846
ARTIST_POINT_LON = -121.692


def main():
    from beta_graph.servers.wta.chroma_store import WTAVectorStore

    store = WTAVectorStore()
    total = store.count()
    print(f"Total trails in Chroma: {total}")

    if total == 0:
        print("No trails loaded. Run: python3 scripts/load_wta_to_chroma.py --location 'Mt. Baker, WA' --radius 35")
        return 0

    # Search for hikes near Artist Point (25 mile radius)
    results = store.search(
        query="hikes trails",
        n_results=20,
        center_lat=ARTIST_POINT_LAT,
        center_lon=ARTIST_POINT_LON,
        radius_miles=25,
    )
    print(f"\nTrails within 25 miles of Artist Point: {len(results)}")
    for r in results:
        name = r.get("name", "?")
        dist = r.get("distance_miles")
        region = r.get("region", "")
        print(f"  - {name} ({dist} mi)" + (f" [{region}]" if region else ""))

    if len(results) < 3:
        print("\nFew trails near Artist Point. Load more with:")
        print("  python3 scripts/load_wta_to_chroma.py --location 'Mt. Baker, WA' --radius 35")
    return 0


if __name__ == "__main__":
    sys.exit(main())
