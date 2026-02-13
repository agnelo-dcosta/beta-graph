#!/usr/bin/env python3
"""Quick script to check Google Maps geocoding results for a query."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from beta_graph.servers.geocode.geocode import geocode_forward


def main():
    query = "Sycamore Access Trail, Squak Mountain, Issaquah, WA"
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    print(f"Geocoding: {query!r}\n")
    try:
        results = geocode_forward(query, limit=5)
        if not results:
            print("No results.")
            return 1
        for i, r in enumerate(results):
            lat = r.get("latitude")
            lon = r.get("longitude")
            name = r.get("place_name", "")
            print(f"{i + 1}. {name}")
            print(f"   lat={lat}, lon={lon}")
            if lat and lon:
                print(f"   https://www.google.com/maps?q={lat},{lon}")
            print()
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
