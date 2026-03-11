#!/usr/bin/env python3
"""Download satellite/map imagery for given GPS coordinates.

Uses free sources: USGS Imagery (satellite, US default), USGS Topo (map overlay), OpenTopoMap.
Saves to topo-images/ in project root.

Usage:
    python scripts/download_topo.py 47.43045 -121.62089
    python scripts/download_topo.py 47.43045 -121.62089 --provider usgs   # topo overlay
    python scripts/download_topo.py 47.43045 -121.62089 --provider opentopomap --grid-size 5
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from beta_graph.topo.download import download_topo_map

DEFAULT_ZOOM = 17
DEFAULT_GRID = 3


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download topographic map for GPS coordinates"
    )
    parser.add_argument(
        "lat",
        type=float,
        help="Latitude (e.g. 47.43045)",
    )
    parser.add_argument(
        "lon",
        type=float,
        help="Longitude (e.g. -121.62089)",
    )
    parser.add_argument(
        "--zoom",
        type=int,
        default=DEFAULT_ZOOM,
        help=f"Tile zoom (1–17). Higher = more detail. Default {DEFAULT_ZOOM}",
    )
    parser.add_argument(
        "--grid-size",
        type=int,
        default=DEFAULT_GRID,
        help=f"Tiles per side (e.g. 3 = 3x3). Default {DEFAULT_GRID}",
    )
    parser.add_argument(
        "--provider",
        choices=("usgs-imagery", "usgs", "opentopomap"),
        default="usgs-imagery",
        help="Source: usgs-imagery (satellite, default), usgs (topo overlay), or opentopomap",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory. Default: topo-images/ in project root",
    )
    args = parser.parse_args()

    try:
        path = download_topo_map(
            args.lat,
            args.lon,
            zoom=args.zoom,
            grid_size=args.grid_size,
            provider=args.provider,
            output_dir=args.output_dir,
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    print(f"Saved: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
